"""🔴 투영 경로 선언이 판정 함수와 어긋나면 평균이 **조용히** 틀린다.

🔴 A stale projection declaration silently corrupts aggregates.

`GET /` 는 result 블롭 전량 대신 `RELIABILITY_RESULT_PATHS` 만 SQL 에서 투영한다
(실측 30 MB → 80 kB, 운영 DB 2026-08-23). 판정 로직은 여전히 `score_is_unreliable`
하나뿐이지만, **입력이 그 5경로로 좁혀졌다**. 그래서 새 마커를 판정에 추가하고 선언에
안 넣으면 투영 경로에서 그 값이 늘 `None` 이라 **걸리지 않는다** — 예외도 red 도 없이
집계만 틀어진다.

이 파일은 두 축으로 그것을 막는다:
  ① 선언 ↔ 함수 본문 대조 (AST — 손 목록이 아니라 소스에서 파생)
  ② 전체 dict ↔ 투영 dict 판정 일치 (백엔드 타입 차이 포함)
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from src.scorer import reliability as R
from src.scorer.reliability import (
    RELIABILITY_RESULT_PATHS,
    result_from_projection,
    score_is_unreliable,
)

# 판정 진입점 — 여기서 **호출을 따라가며** 참여 함수를 넓힌다(손 목록 금지).
_PREDICATE_SOURCES = ("src/scorer/reliability.py", "src/gate/_common.py")
_ENTRY = "score_is_unreliable"


def _functions() -> dict[str, ast.FunctionDef]:
    out: dict[str, ast.FunctionDef] = {}
    for rel in _PREDICATE_SOURCES:
        for node in ast.walk(ast.parse(Path(rel).read_text(encoding="utf-8"))):
            if isinstance(node, ast.FunctionDef):
                out.setdefault(node.name, node)
    return out


def _reachable_from_entry() -> set[str]:
    """🔴 진입점에서 **호출로 도달 가능한** 함수 전부.

    Grok claim-review `01a02f14` Q2 적발: 초판은 참여 함수를 **손으로** 적었다
    (`{score_is_unreliable, ai_review_failed}`). 그러면 판정이 새 도우미로 마커를 읽는
    순간 가드가 눈을 감는다:

        def _truncated(result): return bool(result.get("ai_review_truncated"))
        def score_is_unreliable(result):
            if _truncated(result): return True     # AST 가 _truncated 안으로 안 들어간다

    호출 그래프를 따라가면 그 형태가 닫힌다.
    Follow the call graph instead of hand-listing the participating functions.
    """
    funcs = _functions()
    seen, stack = set(), [_ENTRY]
    while stack:
        name = stack.pop()
        if name in seen or name not in funcs:
            continue
        seen.add(name)
        for node in ast.walk(funcs[name]):
            if isinstance(node, ast.Call):
                fn = node.func
                target = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
                if target in funcs:
                    stack.append(target)
    return seen


def _accesses() -> tuple[set[tuple[str, str]], list[str]]:
    """(수신자, 키) 쌍과 **정적 분석 불가 형태** 목록.

    🔴 못 읽는 형태를 조용히 건너뛰지 않는다 — 건너뛰면 가드가 「봤다」고 거짓말한다.
    `result.get(CONST)` · `result.items()` · `for k in result` 는 이 가드가 원리적으로
    못 읽으므로 목록으로 돌려주고 호출부가 red 로 만든다.
    Unverifiable forms are returned, not skipped: a guard that cannot see must say so.
    """
    funcs, reachable = _functions(), _reachable_from_entry()
    pairs: set[tuple[str, str]] = set()
    opaque: list[str] = []
    for name in sorted(reachable):
        fn = funcs[name]
        param = fn.args.args[0].arg if fn.args.args else ""
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                recv = node.func.value
                recv_name = recv.id if isinstance(recv, ast.Name) else "?"
                if node.func.attr in ("items", "keys", "values") and recv_name != "?":
                    opaque.append(f"{name}: {recv_name}.{node.func.attr}()")
                elif node.func.attr == "get" and node.args and recv_name != "?":
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        pairs.add((recv_name, arg.value))
                    else:
                        opaque.append(f"{name}: {recv_name}.get(<비-리터럴>)")
            elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
                if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                    pairs.add((node.value.id, node.slice.value))
                elif node.value.id == param:
                    opaque.append(f"{name}: {node.value.id}[<비-리터럴>]")
            elif (isinstance(node, ast.For) and isinstance(node.iter, ast.Name)
                  and node.iter.id == param):
                opaque.append(f"{name}: for … in {param}")
    return pairs, opaque


def test_the_ast_scan_is_not_vacuous():
    """가드가 아무것도 못 읽으면 아래 단언들이 공허하다."""
    reachable = _reachable_from_entry()
    assert _ENTRY in reachable, "진입점을 못 찾았다"
    assert "ai_review_failed" in reachable, (
        f"호출 그래프 추적이 위임 함수를 못 잡았다: {sorted(reachable)}"
    )
    pairs, _ = _accesses()
    assert pairs, "판정 함수에서 키를 하나도 못 읽었다 — 파싱이 깨졌다"
    assert ("result", "ai_review_status") in pairs, f"알려진 접근이 안 잡혔다: {sorted(pairs)}"


def test_no_unverifiable_key_access_in_the_predicate():
    """🔴 가드가 **못 읽는 형태**가 있으면 red — 조용히 초록을 내지 않는다.

    키가 정적이지 않으면 이 파일은 그 마커의 선언 여부를 확인할 방법이 없다.
    그런데도 통과시키면 「검사했다」는 거짓 보증이 된다.
    """
    _, opaque = _accesses()
    assert not opaque, (
        "판정에 정적 분석 불가 접근이 있다 — 투영 선언 누락을 못 잡는다:\n  "
        + "\n  ".join(opaque)
        + "\n→ 키를 리터럴로 쓰거나, 그 마커를 RELIABILITY_RESULT_PATHS 에 넣고 "
          "이 가드가 읽을 수 있는 형태로 바꿀 것."
    )


def test_every_key_the_predicate_reads_is_declared_at_the_right_depth():
    """🔴 키가 **선언된 깊이에 있어야** 한다 — 평탄화 비교는 구멍이다.

    Grok `01a02f14` Q2-③: 초판은 선언을 평탄한 키 집합으로 폈다. 그러면
    `result.get("ai_defaults_applied")` (최상위)가 `("breakdown","ai_defaults_applied")`
    선언 덕분에 통과한다 — SQL 은 여전히 중첩 경로만 뽑으므로 그 마커는 늘 None 이다.

    최상위 접근(수신자 = 판정 함수 첫 인자)은 **1-요소 경로**로 선언돼 있어야 하고,
    중첩 접근은 어떤 경로의 **2번째 이후 요소**여야 한다.
    """
    # 최상위에서 정당한 키 = 1-요소 경로의 잎  ∪  더 긴 경로의 **컨테이너**(첫 요소).
    # 컨테이너를 빼면 `result.get("breakdown")` 같은 정상 접근이 오탐이 된다.
    top_level = {p[0] for p in RELIABILITY_RESULT_PATHS}
    nested = {k for p in RELIABILITY_RESULT_PATHS if len(p) > 1 for k in p[1:]}

    pairs, _ = _accesses()
    missing = []
    for recv, key in sorted(pairs):
        if recv == "result":
            if key not in top_level:
                missing.append(f"최상위 result.get({key!r}) — 1-요소 경로로 선언 필요")
        elif key not in nested:
            missing.append(f"중첩 {recv}.get({key!r}) — 중첩 경로 요소로 선언 필요")

    assert not missing, (
        "판정은 읽는데 투영 선언과 깊이가 맞지 않는 키:\n  " + "\n  ".join(missing)
        + "\n→ src/scorer/reliability.py 의 RELIABILITY_RESULT_PATHS 를 고칠 것. "
        "빠지거나 깊이가 어긋나면 GET / 평균에서 그 사유가 조용히 무시된다."
    )


# ── ② 전체 dict ↔ 투영 dict 판정 일치 ────────────────────────────────────────

def _project(result: dict | None, *, sqlite: bool) -> list[object]:
    """SQL 경로 추출을 흉내낸다. `sqlite=True` 면 불린을 0/1 정수로 준다(실측 동작)."""
    out: list[object] = []
    for path in RELIABILITY_RESULT_PATHS:
        node: object = result
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
        if sqlite and isinstance(node, bool):
            node = int(node)
        out.append(node)
    return out


_CORPUS = [
    None,
    {},
    {"ai_review_status": "success"},
    {"ai_review_status": "api_error"},
    {"ai_review_status": "parse_error"},
    {"ai_review_status": "disabled"},
    {"ai_review_status": "no_api_key"},
    {"ai_review_status": "empty_diff"},
    {"static_analysis_incomplete": True},
    {"static_analysis_incomplete": False},
    {"source": "cli"},
    {"source": "webhook"},
    {"breakdown": {"ai_defaults_applied": True, "code_quality": 20}},
    {"breakdown": {"ai_defaults_applied": False}},
    {"breakdown": {}},
    {"static_uncovered_languages": ["rust"]},
    {"static_uncovered_languages": []},
    # 블롭에만 있고 판정과 무관한 무거운 키 — 투영이 버려도 판정이 같아야 한다
    {"ai_review_status": "success", "issues": [{"m": "x"} for _ in range(50)],
     "ai_review": "long text " * 200},
    {"ai_review_status": "api_error", "source": "cli",
     "breakdown": {"ai_defaults_applied": True},
     "static_uncovered_languages": ["zig"], "static_analysis_incomplete": True},
]


@pytest.mark.parametrize("sqlite", [True, False], ids=["sqlite-0/1", "postgres-bool"])
@pytest.mark.parametrize("result", _CORPUS, ids=range(len(_CORPUS)))
def test_projection_yields_the_same_verdict_as_the_full_blob(result, sqlite):
    """🔴 투영이 판정을 바꾸지 않는다 — 두 백엔드의 불린 표현 차이를 포함해서.

    SQLite 는 JSON 불린을 0/1 정수로 준다. `score_is_unreliable` 은
    `ai_defaults_applied is True` 로 엄격 비교하므로, 정규화가 없으면 이 축이 red 다.
    """
    expected = score_is_unreliable(result)
    got = score_is_unreliable(result_from_projection(_project(result, sqlite=sqlite)))
    assert got == expected, (
        f"판정이 갈렸다: 전체={expected} 투영={got} (sqlite={sqlite})\n입력={result}"
    )


def test_projection_length_mismatch_is_loud():
    """길이가 안 맞으면 조용히 None 을 채우지 않는다 — 선언 변경 시 즉시 드러난다."""
    with pytest.raises(ValueError, match="투영값"):
        result_from_projection([None])


def test_json_bool_touches_only_integer_0_and_1():
    """🔴 정규화 범위 — 정수 0/1 **만**. 문자열은 손대지 않는다.

    Grok `01a02f14` Q1: 초판은 `"true"`/`"false"` 도 변환했는데, 그것이 **없던 발산을
    만들었다**. 전체 blob 경로에서 `"true" is True` 는 False 이므로 투영만 True 로
    바꾸면 두 경로가 갈린다. 넓은 정규화가 오히려 틀렸다.
    """
    assert R._json_bool(1) is True
    assert R._json_bool(0) is False
    assert R._json_bool(True) is True
    assert R._json_bool(False) is False
    assert R._json_bool(None) is None
    assert R._json_bool("true") == "true", "문자열은 그대로 — 바꾸면 전체 blob 과 갈린다"
    assert R._json_bool("false") == "false"
    assert R._json_bool("cli") == "cli"
    assert R._json_bool(2) == 2, "0/1 이 아닌 정수는 불린이 아니다"


def test_normalization_applies_only_to_the_strict_identity_path():
    """🔴 정규화는 `is True` 로 비교하는 경로에만 걸린다.

    truthy 판정 경로(`static_analysis_incomplete` 등)에 걸면 SQLite 의 0/1 이 아니라
    **문자열 값**에서 발산한다 — `"false"` 는 전체 blob 에서 truthy 다.
    """
    from src.scorer.reliability import _STRICT_BOOL_PATHS  # pylint: disable=import-outside-toplevel

    assert _STRICT_BOOL_PATHS == {("breakdown", "ai_defaults_applied")}, (
        "엄격 비교 경로 집합이 바뀌었다 — 판정 함수의 `is True` 사용처와 대조할 것"
    )
    # `static_analysis_incomplete: "false"` 는 양쪽 모두 truthy 여야 한다
    case = {"static_analysis_incomplete": "false"}
    assert score_is_unreliable(case) is True
    assert score_is_unreliable(result_from_projection(_project(case, sqlite=True))) is True


def test_stored_numeric_one_diverges_and_it_diverges_fail_closed():
    """🔴 남는 발산 1건을 **사실대로** 고정한다 — 방향까지 함께.

    `_json_bool` 은 정수 `1` 을 True 로 되돌린다(SQLite 가 JSON 불린을 그렇게 주기
    때문). 그래서 저장값이 **진짜 숫자 1** 이면:

        전체 blob : `1 is True` → False → 집계에 **포함**
        투영      : `_json_bool(1)` → True → 집계에서 **제외**

    🔴 이 발산은 백엔드와 무관하다 — 초판 단언은 "PostgreSQL 에는 없다" 였는데
    **틀렸다**. 정규화는 값 타입만 보지 방언을 모른다.

    남겨 두는 근거: (1) 현재 기록자는 항상 불린을 저장한다
    (`scorer/calculator.py` · `worker/pipeline.py`), (2) 발산 방향이 **fail-closed**
    다 — 의심스러운 행을 평균에서 빼는 쪽이라 점수를 부풀리지 않는다.

    없애려면 판정의 `is True` 를 truthy 비교로 바꾸면 된다(불린 값에는 무영향).
    그것은 신뢰도 규칙 변경이라 별도 판단이 필요해 이 PR 에서는 하지 않았다.
    """
    numeric = {"breakdown": {"ai_defaults_applied": 1}}
    assert score_is_unreliable(numeric) is False, "전체 blob 은 `1 is True` 라 False"
    for sqlite in (True, False):
        projected = score_is_unreliable(result_from_projection(_project(numeric, sqlite=sqlite)))
        assert projected is True, (
            f"sqlite={sqlite}: 발산이 사라졌다면 이 테스트와 위 서술을 함께 지울 것"
        )


def test_boolean_values_never_diverge_on_either_backend():
    """대조군 — **실제로 저장되는 값**(불린)에는 발산이 없다. 위 한계의 경계를 못박는다."""
    for stored in (True, False):
        case = {"breakdown": {"ai_defaults_applied": stored}}
        expected = score_is_unreliable(case)
        for sqlite in (True, False):
            got = score_is_unreliable(result_from_projection(_project(case, sqlite=sqlite)))
            assert got == expected, f"{stored!r} sqlite={sqlite}: {got} != {expected}"
