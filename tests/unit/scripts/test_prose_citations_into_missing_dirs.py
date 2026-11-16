"""문장 속 리포 경로 인용이 디렉터리째 사라진 곳을 가리키면 빨강 (회고 원장 이관 K21 P2-40).

## 사고

#1636 의 죽은 좌표 가드는 «메모리 → 리포» 한 방향뿐이었다. 리포 안의 문장(주석 · 독스트링 · 문서)이 지워진 트리 —
옛 규칙 · 정책 디렉터리 · 설계 문서 · 옮겨 간 분석기 도구 — 를 정본처럼 가리키는 인용이 34파일에 남았다.

## 이 파일이 잠그는 것

1. 추적 파일의 문장(파이썬 = 주석 · 독스트링, `.md` · `.mjs` · `.yml` = 본문)이 리포 경로를 인용하면 그 파일이 있거나
   적어도 그 디렉터리가 있어야 한다. 시험 입력용 가짜 경로는 대개 코드의 문자열 값이라 보지 않고, 실재 디렉터리의
   가짜 이름(`scripts/x.py`)도 통과한다 — 이 가드는 «통째로 사라진 트리» 를 잡는다.
2. 이력 문서(`docs/reports/`)와 마이그레이션(`alembic/versions/`)은 그때의 경로를 적으므로 뺀다.
3. 의도된 인용은 면제 표에 사유와 함께 둔다 — 그 인용이 사라진 면제도 빨강(죽은 면제 금지).
4. 공허화 방어 — 훑은 문장이 0 이거나 심은 죽은 인용을 못 보면 빨강.
"""
from __future__ import annotations

import ast
import io
import posixpath
import re
import subprocess
import tokenize
from pathlib import Path, PurePosixPath

_ROOT = Path(__file__).resolve().parents[3]

_CITATION = re.compile(
    r"(?<![\w/.@-])((?:docs|src|scripts|tests|e2e|alembic|\.claude|\.github)/[\w./-]*\w"
    r"\.(?:md|py|html|css|js|yml|yaml|json|mjs|toml))(?![\w/-])")
_HISTORY_ROOTS = ("docs/reports/", "alembic/versions/")
_PROSE_SUFFIXES = (".py", ".md", ".mjs", ".yml", ".yaml")

# 의도된 인용 — (인용한 파일, 인용 경로) → 사유. 인용이 사라지면 이 줄도 지운다(아래 시험이 잡는다).
_EXEMPT = {
    (".claude/hooks/posttool_pytest_smoke.py", "src/.claude/hooks/x.py"):
        "긴 루트를 먼저 보는 이유 — 짧은 루트가 먼저 잡던 Grok 반례 경로",
    ("tests/unit/hooks/test_posttool_pytest_smoke.py", "src/.claude/hooks/x.py"):
        "같은 반례를 시험이 적는다",
    ("tests/unit/hooks/test_check_edit_allowed.py", "docs/alembic/versions_guide.md"):
        "보호 경로 판정이 부분 문자열로 잡는다는 것을 보이는 시험 입력",
    ("tests/unit/i18n/test_translation_path_citations.py", "docs/_archive/runbooks/sentry-activation.md"):
        "운영자 화면에 죽은 경로가 렌더되던 사고의 기록 — 그 경로가 증거다",
    ("tests/unit/scripts/test_hook_command_cwd_independence.py", "scripts/../../../x.py"):
        "작업 폴더 밖으로 나가는 훅 명령을 거부하는지 보는 시험 입력",
    ("scripts/extract_design_tokens.py", "docs/design/brief/01-current-tokens.json"):
        "스크립트의 출력 경로 — 실행할 때 만든다",
}


def _python_prose(text: str) -> list[tuple[int, str]]:
    """파이썬 소스의 문장 — 주석과 모듈 · 클래스 · 함수 독스트링(코드의 문자열 값은 시험 입력이라 뺀다)."""
    out: list[tuple[int, str]] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                out.append((tok.start[0], tok.string))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None and node.body:  # 빈 독스트링도 문장이다(Grok 반례 `""""""`)
                out.append((node.body[0].lineno, doc))
    return out


def _directories(tracked: set[str]) -> set[str]:
    """추적 파일의 모든 조상 디렉터리 — 리포 루트(`.`)도 실재한다."""
    dirs: set[str] = {"."}
    for path in tracked:
        parent = PurePosixPath(path).parent
        while str(parent) not in (".", ""):
            dirs.add(str(parent))
            parent = parent.parent
    return dirs


def violations(files: dict[str, str], tracked: set[str]) -> tuple[list[tuple[str, int, str]], int]:
    """(인용한 파일, 줄, 인용 경로) 목록 — 그 경로도 그 디렉터리도 추적 트리에 없는 것. 그리고 훑은 문장 수."""
    dirs = _directories(tracked)
    found: list[tuple[str, int, str]] = []
    scanned = 0
    for rel, text in sorted(files.items()):
        if rel.startswith(_HISTORY_ROOTS) or not rel.endswith(_PROSE_SUFFIXES):
            continue
        chunks = _python_prose(text) if rel.endswith(".py") else [(1, text)]
        scanned += len(chunks)
        for line, chunk in chunks:
            for m in _CITATION.finditer(chunk):
                ref = m.group(1)
                # `..` 를 풀어 판정한다 — `scripts/foo/../x.py` 는 실재하는 `scripts/` 로 돌아온다(Grok 반례).
                norm = posixpath.normpath(ref)
                if norm not in tracked and (posixpath.dirname(norm) or ".") not in dirs:
                    found.append((rel, line, ref))
    return found, scanned


def _repo_files() -> tuple[dict[str, str], set[str]]:
    out = subprocess.run(["git", "ls-files"], cwd=_ROOT, capture_output=True, text=True, encoding="utf-8",
                         check=True).stdout
    tracked = {p for p in out.split("\n") if p}
    files = {}
    for rel in tracked:
        if rel.endswith(_PROSE_SUFFIXES):
            try:
                files[rel] = (_ROOT / rel).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
    return files, tracked


def test_prose_citations_point_into_existing_directories():
    """🔴 문장이 디렉터리째 사라진 리포 경로를 정본처럼 가리키지 않는다 — 의도된 인용은 `_EXEMPT` 에 사유와 함께."""
    files, tracked = _repo_files()
    found, scanned = violations(files, tracked)
    assert scanned > 0, "훑은 문장이 0 — 가드가 공허하다"
    live = [f"{rel}:{line}  {ref}" for rel, line, ref in found if (rel, ref) not in _EXEMPT]
    assert not live, "사라진 트리를 가리키는 인용:\n" + "\n".join(live)


def test_every_exemption_is_still_needed():
    """죽은 면제 금지 — 면제한 인용이 더는 없으면 그 면제 줄을 지운다."""
    files, tracked = _repo_files()
    found, _ = violations(files, tracked)
    seen = {(rel, ref) for rel, _, ref in found}
    stale = sorted(set(_EXEMPT) - seen)
    assert not stale, f"쓰이지 않는 면제: {stale}"


# witness-corpus: 인용으로 볼 꼴 · 아닌 꼴 — 사라진 트리 · 실재 디렉터리의 가짜 이름 · 코드 문자열 값 · 리포 밖 경로 · 이력 문서
_PLANTED = {
    "src/a.py": '# 정본은 `.claude/rules/testing.md` 다\nX = 1\n',
    "src/b.py": '"""모듈 설명 — docs/design/plan.md 참고."""\n',
    "src/c.py": '# 예시: `scripts/x.py` 는 가짜 이름이다\nP = ".claude/rules/in_code_value.md"\n',
    "src/d.py": "# 돌아오는 경로 `scripts/foo/../x.py` 는 실재하는 scripts/ 다\n",
    "docs/workflow/x.md": "자세히는 `README.md` · `node_modules/a.js` · `build/out.py`.\n",
    "docs/reports/2026-01-01-retro.md": "그때는 `.claude/rules/old.md` 였다.\n",
}
_PLANTED_TRACKED = set(_PLANTED) | {"scripts/real.py"}


def test_the_detector_sees_planted_dead_citations_and_nothing_else():
    """🔴 계기 뒤집기 — 사라진 트리를 가리키는 주석 · 독스트링은 잡고, 실재 디렉터리의 가짜 이름 · `..` 로 실재
    디렉터리에 돌아오는 경로 · 코드 문자열 값 · 리포 밖 경로 · 이력 문서는 잡지 않는다."""
    found, scanned = violations(_PLANTED, _PLANTED_TRACKED)
    assert scanned >= 5, scanned
    assert sorted((rel, ref) for rel, _, ref in found) == [
        ("src/a.py", ".claude/rules/testing.md"),
        ("src/b.py", "docs/design/plan.md"),
    ], found


def test_an_empty_docstring_is_still_prose():
    """빈 독스트링도 문장 조각으로 돌려준다 — 주석 · 독스트링을 «정확히» 돌려준다는 계약(Grok 반례 `""\"""\"`)."""
    assert _python_prose('def f():\n    """"""\n') == [(2, "")]
