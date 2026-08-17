"""PR 본문은 **하드닝된 단일 리더**를 통해서만 읽힌다 (회고 N-P0-1).

## 사고 — 이미 한 번 값을 치른 결함의 3중 재발

`check_claim_review_trace` 는 backlog R20 결함 1 · Grok `019fbe32` 를 거치며
`strip_html_comments` 로 축 하나를 닫았다: **HTML 주석 안의 마커는 GitHub 렌더에서
리뷰어에게 보이지 않으므로 게이트를 만족시켜서는 안 된다.**

그런데 2026-08-08 창에서 새로 만든 게이트 **셋 다** `os.environ["PR_BODY"]` 원문을
정규식에 넘겼다 — 면제 마커 관용구는 복제하면서 하드닝은 복제하지 않은 것이다.

| 게이트 | 마커 | 은닉 면제(수정 전) |
|---|---|---|
| `check_reverse_mutation` | `reverse-mutation-not-applicable:` | 🔴 통과 |
| `check_test_count_sync` | `STATE-sync-deferred:` | 🔴 통과 |

🔴 **교훈은 "복제하지 말라" 가 아니다** — 관용구는 앞으로도 복제된다. 교훈은
**"읽는 지점을 하나로 두라"** 다. 그래야 다음 하드닝도 자동으로 따라간다.

## 이 파일이 강제하는 것

1. `scripts/*.py` 중 환경에서 `PR_BODY` 를 **직접** 읽는 모듈은 정확히 하나다 (AST 판정).
2. 마커 게이트 3종은 `read_pr_body()` 를 **실제로 호출**한다 (배선 — 불변식 3).
3. 은닉 마커는 매치되지 않고, **가시 마커는 여전히 매치된다** (과교정 대조군).
4. 🔴 대조군 — 원문에서는 은닉 마커가 매치된다. 이게 거짓이면 위 단언들은
   리더를 지워도 통과한다(가드 자살).

산문 grep 이 아니라 실제 컴파일된 패턴과 실제 모듈 AST 로 판정한다.
Enforces a single hardened reader for the PR body: AST for the wiring, real compiled
patterns for the behavior, and a control proving the hardening is load-bearing.
"""
from __future__ import annotations

import ast
import importlib
import os
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS = _ROOT / "scripts"
_HOOKS = _ROOT / ".claude" / "hooks"

# 🔴 환경에서 PR_BODY 를 직접 읽어도 되는 **유일한** 모듈.
# 여기를 늘리려면 그 모듈이 스트리핑을 자체 수행함을 증명해야 한다.
_SOLE_READER = "check_claim_review_trace.py"

# 면제/이월 마커로 PR 본문을 판정하는 게이트 — 전부 단일 리더를 거쳐야 한다.
_MARKER_GATES = {
    "check_reverse_mutation": ("_EXEMPT", "reverse-mutation-not-applicable"),
    "check_test_count_sync": ("_DEFERRED", "STATE-sync-deferred"),
}


def _script_files() -> list[Path]:
    """🔴 범위 = `scripts/*.py` **+ `.claude/hooks/*.py`**.

    초판은 `scripts/` 만 봤다 — 훅도 환경을 읽는 실행 표면이라 두 번째 리더가 거기
    생기면 가드가 침묵했다(Grok claim-review `019fe026` 지적).
    """
    files = sorted(_SCRIPTS.glob("*.py")) + sorted(_HOOKS.glob("*.py"))
    assert _SCRIPTS.glob("*.py"), "scripts/*.py 가 0건 — 범위 붕괴"
    assert files, "검사 대상이 0건 — 빈 범위 위의 ✅ 는 fail-open"
    return files


def _reads_pr_body_literal(source: str) -> bool:
    """AST 로 PR_BODY 를 **환경에서 직접 읽는지** 본다.

    주석은 AST 에 없으므로 설명 주석은 걸리지 않는다.

    🔴 정확 일치(`== "PR_BODY"`)만 보면 `"PR_" + "BODY"` 나 f-string 조각으로 빠져나간다
    (Grok claim-review `019fe026` 실측). 그래서 **부분 문자열 + 상수 접기**로 본다.
    docstring 은 제외한다 — 이 규칙을 **설명**하는 산문까지 위반이 되면 가드 자살이다.

    🔴 **정직 기준 — 이 탐지기가 잡지 못하는 것**: `"".join(["PR_", "BODY"])` 같은 런타임
    조립, `chr()` 산술, `GITHUB_EVENT_PATH` JSON 직접 파싱. 이 가드의 목적은 *관용구를
    복제하다 하드닝을 빠뜨리는* 실제 관찰된 사고를 막는 것이지, 작정한 우회를 막는 것이
    아니다. 작정한 우회는 정적으로 닫히지 않는다(정책 17 — 오탐>진탐이면 가드 자살).
    """
    tree = ast.parse(source)
    docstrings = {
        ast.get_docstring(n, clean=False)
        for n in ast.walk(tree)
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

    def _hits(value: object) -> bool:
        return isinstance(value, str) and "PR_BODY" in value and value not in docstrings

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and _hits(node.value):
            return True
        # `"PR_" + "BODY"` — 상수 접기 없이는 조각 어느 쪽도 매치하지 않는다.
        # (`ast.literal_eval` 은 문자열 `+` 를 접지 않는다 — 숫자 전용이다.)
        if isinstance(node, ast.BinOp) and _hits(_fold_str(node)):
            return True
    return False


def _fold_str(node: ast.AST) -> str | None:
    """문자열 상수의 `+` 연결만 접는다. 접을 수 없으면 None."""
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _fold_str(node.left), _fold_str(node.right)
        return None if left is None or right is None else left + right
    return None


def _calls(source: str, func_name: str) -> bool:
    """`func_name()` 이 **실제 호출**되는지 — import 만 하고 안 부르는 것을 배제한다."""
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == func_name
        for node in ast.walk(ast.parse(source))
    )


# ── ① 단일 리더 ───────────────────────────────────────────────────────────


def test_only_one_script_reads_pr_body_from_the_environment():
    """🔴 봉인 — 두 번째 리더가 생기면 하드닝이 다시 갈라진다."""
    readers = [
        p.name for p in _script_files()
        if _reads_pr_body_literal(p.read_text(encoding="utf-8"))
    ]

    assert readers == [_SOLE_READER], (
        f"PR_BODY 를 직접 읽는 스크립트: {readers} (허용: [{_SOLE_READER!r}])\n"
        "→ 새 게이트는 `read_pr_body()` 를 부를 것. 원문을 정규식에 넘기면 HTML 주석 안\n"
        "   마커가 '리뷰어 비가시 + 게이트 통과' 를 성립시킨다(회고 N-P0-1)."
    )


def test_the_sole_reader_actually_strips():
    """단일 리더가 **스트리핑을 실제로 수행**하는지 — 이름만 그럴듯한 껍데기 배제."""
    trace = importlib.import_module("scripts.check_claim_review_trace")
    source = Path(trace.__file__).read_text(encoding="utf-8")
    reader = next(
        n for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.FunctionDef) and n.name == "read_pr_body"
    )

    assert _calls(ast.unparse(reader), "strip_html_comments"), (
        "read_pr_body 가 strip_html_comments 를 부르지 않는다 — 리더가 공허하다"
    )


# ── ② 배선 (불변식 3 — 정의 ≠ 배선) ──────────────────────────────────────


@pytest.mark.parametrize("module_name", sorted(_MARKER_GATES))
def test_marker_gate_goes_through_the_hardened_reader(module_name: str):
    """마커 게이트가 `read_pr_body()` 를 **호출**하는지 (import 만으로는 불충분)."""
    source = (_SCRIPTS / f"{module_name}.py").read_text(encoding="utf-8")

    assert _calls(source, "read_pr_body"), (
        f"{module_name} 이 read_pr_body() 를 호출하지 않는다 — 배선 끊김"
    )


# ── ③ 행동: 은닉은 막고 가시는 통과 ──────────────────────────────────────


def _hidden(marker: str) -> str:
    """멀티라인 HTML 주석 안에 마커를 숨긴 본문 — GitHub 에서 **렌더되지 않는다**."""
    return f"## 요약\n\n<!--\n{marker}: 리뷰어에게 보이지 않는 곳에 적은 면제 사유입니다\n-->\n\n끝\n"


def _visible(marker: str) -> str:
    return f"## 요약\n\n{marker}: 리뷰어에게 보이는 곳에 적은 정당한 면제 사유입니다\n"


@pytest.mark.parametrize("module_name", sorted(_MARKER_GATES))
def test_marker_hidden_in_an_html_comment_does_not_exempt(module_name: str, monkeypatch):
    """🔴 봉인 본체 — 은닉 마커는 면제가 아니다."""
    attr, marker = _MARKER_GATES[module_name]
    module = importlib.import_module(f"scripts.{module_name}")
    pattern = getattr(module, attr)
    monkeypatch.setenv("PR_BODY", _hidden(marker))

    assert pattern.search(module.read_pr_body()) is None, (
        f"{module_name}: HTML 주석 안 마커가 면제로 인정됐다 — 리뷰어 비가시 + 게이트 통과"
    )


@pytest.mark.parametrize("module_name", sorted(_MARKER_GATES))
def test_raw_body_would_have_been_exempted(module_name: str, monkeypatch):
    """🔴 대조군 — 원문이었다면 통과했다.

    이 단언이 없으면 위 테스트는 마커 오타 하나로도 통과한다(가드 자살).
    """
    attr, marker = _MARKER_GATES[module_name]
    module = importlib.import_module(f"scripts.{module_name}")
    pattern = getattr(module, attr)
    monkeypatch.setenv("PR_BODY", _hidden(marker))

    assert pattern.search(os.environ["PR_BODY"]) is not None, (
        "원문에서도 매치가 안 된다 — 픽스처가 마커를 잘못 적었다(테스트가 공허)"
    )


@pytest.mark.parametrize("module_name", sorted(_MARKER_GATES))
def test_visible_marker_still_exempts(module_name: str, monkeypatch):
    """🔴 과교정 대조군 — 정당한 면제까지 막으면 그것도 결함이다(정책 17)."""
    attr, marker = _MARKER_GATES[module_name]
    module = importlib.import_module(f"scripts.{module_name}")
    pattern = getattr(module, attr)
    monkeypatch.setenv("PR_BODY", _visible(marker))

    assert pattern.search(module.read_pr_body()) is not None, (
        f"{module_name}: 가시 면제까지 차단됐다 — 게이트가 쓸 수 없게 됐다"
    )


def test_empty_environment_is_not_an_exemption(monkeypatch):
    """`PR_BODY` 미설정(push 이벤트 등)이 면제로 읽히지 않는지 — fail-closed."""
    monkeypatch.delenv("PR_BODY", raising=False)
    trace = importlib.import_module("scripts.check_claim_review_trace")

    assert trace.read_pr_body() == ""


# ── ④ 우회 형태 (Grok claim-review 019fe026 이 실측한 것) ────────────────


@pytest.mark.parametrize(
    ("snippet", "why"),
    [
        ('x = os.environ.get("PR_BODY", "")', "정확 리터럴"),
        ('x = os.getenv("PR_BODY")', "os.getenv 경유"),
        ('x = os.environ["PR_" + "BODY"]', "문자열 결합으로 쪼갠 키"),
        ('k = f"PR_BODY"; x = os.environ[k]', "f-string 경유"),
        ('x = os.environ.get("PR_BODY")', "기본값 없는 get"),
    ],
)
def test_detector_catches_the_known_evasions(snippet: str, why: str):
    """🔴 탐지기가 우회 형태를 잡는지 — 이게 없으면 단일 리더 단언이 종잇장이다."""
    source = "\n".join(["import os", snippet, ""])

    assert _reads_pr_body_literal(source), f"놓친 우회: {why}"


def test_detector_does_not_flag_prose_about_the_variable():
    """🔴 과교정 대조군 — 산문으로 PR_BODY 를 **설명**하는 것은 리더가 아니다.

    이게 없으면 이 파일 자신과 문서화 주석이 전부 위반이 된다(가드 자살).
    """
    source = '''"""이 모듈은 PR_BODY 를 설명만 한다."""


def helper():
    """PR_BODY 를 직접 읽지 말고 read_pr_body() 를 쓰라."""
    return 1
'''
    assert not _reads_pr_body_literal(source)
