"""e2e 하네스가 «모든 자격증명» 을 CI 와 같은 값으로 못박는가.

## 무엇이 문제였나

`build_settings()` 는 `.env` 를 읽는다. e2e 하네스(`e2e/conftest.py::_start_uvicorn`)는
GitHub·Telegram·세션 같은 자격증명을 더미로 덮어쓰지만 **목록을 손으로 적고 있었다.**
그 목록에서 빠진 `ANTHROPIC_API_KEY` 는 개발 PC 의 `.env` 값이 그대로 살아, 로컬 e2e 가
`?mode=insight`·`/repos/<repo>/insights` 에서 **실제 Anthropic API 를 호출**했다
(CI 는 `.env` 가 없어 조용했다 — 그래서 3개월 동안 아무도 못 봤다).

실측(2026-09-12): `.env` 에 값이 있는 키 9개 중 하네스가 안 덮는 «자격증명류» 는
`ANTHROPIC_API_KEY` 하나였다. 돈이 나가는 바로 그 하나였다.

## 🔴 목록이 아니라 파생

새 벤더 키가 `Settings` 에 생기면 이 가드가 **먼저** 빨개진다. 손으로 적은 목록은
새 항목이 조용히 빠지는 자리를 다시 만든다.
"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_CONFIG = ROOT / "src" / "config.py"
_CONFTEST = ROOT / "e2e" / "conftest.py"

# 이름으로 «자격증명» 을 고른다 — 값이 새면 돈·권한이 새는 부류.
_CRED_WORDS = ("key", "token", "secret", "password", "dsn")


def _credential_settings() -> set[str]:
    """`Settings` 의 문자열 자격증명 필드 → 환경변수 이름 집합(대문자)."""
    tree = ast.parse(_CONFIG.read_text(encoding="utf-8"))
    cls = next((n for n in ast.walk(tree)
                if isinstance(n, ast.ClassDef) and n.name == "Settings"), None)
    assert cls is not None, "`Settings` 클래스를 찾지 못했다 — 파생이 죽었다"
    out = set()
    for node in cls.body:
        if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
            continue
        name = node.target.id
        ann = ast.unparse(node.annotation)
        # 🔴 `str` 만 본다 — `claude_review_max_tokens`(int)·`strict_token_encryption`(bool)
        #    처럼 이름만 자격증명 같은 필드를 끌고 오면 하네스가 «빈 문자열» 을 넣게 되고
        #    부팅이 깨진다. 타입까지 봐야 판정이 상태를 대신한다.
        if "str" not in ann:
            continue
        if any(w in name for w in _CRED_WORDS):
            out.add(name.upper())
    return out


def _harness_assigned() -> set[str]:
    """`_start_uvicorn` 이 **실제로 `os.environ[...] = ` 로 못박는** 이름 집합.

    🔴 「함수 본문에 그 대문자 문자열이 있는가」로 세면 안 된다 — `os.environ.get("X")`
    처럼 **읽기만** 해도, 심지어 무관한 리터럴이어도 «못박았다» 로 읽힌다
    (Grok `01a095c7` 이 첫 판의 이 구멍을 지적했다). 대입문만 센다.
    두 형태를 모두 인정한다: 리터럴 대입과 «튜플을 도는 루프 안의 대입».
    """
    tree = ast.parse(_CONFTEST.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "_start_uvicorn"), None)
    assert fn is not None, "`_start_uvicorn` 을 찾지 못했다 — 하네스 구조가 바뀌었다"

    out: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
            names = [e.value for e in getattr(node.iter, "elts", [])
                     if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            body = "\n".join(ast.unparse(b) for b in node.body)
            # 루프 변수로 «대입» 할 때만 그 튜플의 이름들을 인정한다.
            if names and f"os.environ[{node.target.id}] =" in body:
                out.update(names)
    for node in ast.walk(fn):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not (isinstance(target, ast.Subscript)
                    and ast.unparse(target.value) == "os.environ"):
                continue
            if isinstance(target.slice, ast.Constant) and isinstance(target.slice.value, str):
                out.add(target.slice.value)
    return out


def test_every_credential_setting_is_pinned_by_the_e2e_harness():
    """🔴 `.env` 값이 e2e 로 새면 안 된다 — 자격증명은 전부 하네스가 못박는다.

    red 로 만드는 뮤테이션: `_start_uvicorn` 에서 `ANTHROPIC_API_KEY` 못박기를 빼면 red.
    """
    creds = _credential_settings()
    assert creds, "자격증명 필드를 0개 찾았다 — 파생이 죽었다(공허한 초록)"
    missing = sorted(creds - _harness_assigned())
    assert not missing, (
        "e2e 하네스가 못박지 않는 자격증명이 있다 — 개발 PC 의 `.env` 값이 그대로 쓰인다"
        "(로컬만 다르게 동작하고, 벤더 키면 «실제 호출·과금» 이다):\n  "
        + "\n  ".join(missing))


def test_the_anthropic_base_url_is_unroutable_in_e2e():
    """🔴 키가 어떤 경로로든 살아나도 호출이 기계 밖으로 나가면 안 된다.

    `anthropic` SDK 는 `base_url` 미지정 시 `ANTHROPIC_BASE_URL` 을 읽는다. 하네스가
    그것을 도달 불가 주소로 고정하는지 본다 — 이 한 줄이 «벨트+멜빵» 이다.

    red 로 만드는 뮤테이션: 그 대입을 지우거나 실제 주소로 바꾸면 red.
    """
    src = _CONFTEST.read_text(encoding="utf-8")
    m = re.search(r"os\.environ\[[\"']ANTHROPIC_BASE_URL[\"']\]\s*=\s*[\"']([^\"']+)[\"']", src)
    assert m, "`ANTHROPIC_BASE_URL` 을 하네스가 고정하지 않는다"
    url = m.group(1)
    assert url.startswith("http://127.0.0.1:") or url.startswith("http://localhost:"), (
        f"`ANTHROPIC_BASE_URL` 이 {url!r} — 루프백이 아니면 호출이 밖으로 나갈 수 있다")
