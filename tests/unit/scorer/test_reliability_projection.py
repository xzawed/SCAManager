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

# 판정에 참여하는 함수들 — `score_is_unreliable` 이 위임하는 것까지 포함한다.
_PREDICATE_SOURCES = ("src/scorer/reliability.py", "src/gate/_common.py")
_PREDICATE_FUNCS = {"score_is_unreliable", "ai_review_failed"}


def _keys_read_by_predicates() -> set[str]:
    """판정 함수들이 실제로 접근하는 문자열 키를 AST 로 수집한다.

    `x.get("k")` 와 `x["k"]` 양쪽을 본다. 어느 dict 에 대한 접근인지는 구분하지 않는다 —
    과잉 수집은 선언을 넓히게 할 뿐 **누락을 놓치지 않는다**(안전 방향).
    """
    keys: set[str] = set()
    for rel in _PREDICATE_SOURCES:
        tree = ast.parse(Path(rel).read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef) or fn.name not in _PREDICATE_FUNCS:
                continue
            for node in ast.walk(fn):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "get" and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)):
                    keys.add(node.args[0].value)
                elif (isinstance(node, ast.Subscript)
                      and isinstance(node.slice, ast.Constant)
                      and isinstance(node.slice.value, str)):
                    keys.add(node.slice.value)
    return keys


def test_the_ast_scan_is_not_vacuous():
    """가드가 아무것도 못 읽으면 아래 단언이 공허하다."""
    keys = _keys_read_by_predicates()
    assert keys, "판정 함수에서 키를 하나도 못 읽었다 — 함수명이 바뀌었거나 파싱이 깨졌다"
    assert "ai_review_status" in keys, f"알려진 키가 안 잡혔다: {sorted(keys)}"


def test_every_key_the_predicate_reads_is_declared_for_projection():
    """🔴 판정이 읽는 키가 전부 선언돼 있어야 한다 — 빠지면 그 마커가 투영에서 사라진다."""
    declared = {key for path in RELIABILITY_RESULT_PATHS for key in path}
    missing = _keys_read_by_predicates() - declared
    assert not missing, (
        f"판정은 읽는데 투영 선언에 없는 키: {sorted(missing)}.\n"
        "→ src/scorer/reliability.py 의 RELIABILITY_RESULT_PATHS 에 경로를 추가할 것. "
        "빠진 채로 두면 GET / 의 평균에서 그 사유가 조용히 무시된다."
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


def test_json_bool_normalization_is_measured_not_assumed():
    """정규화 표 — 0/1·'true'/'false'·bool 을 모두 받는다."""
    assert R._json_bool(1) is True
    assert R._json_bool(0) is False
    assert R._json_bool(True) is True
    assert R._json_bool("true") is True
    assert R._json_bool("false") is False
    assert R._json_bool(None) is None
    assert R._json_bool("cli") == "cli", "문자열 값은 손대지 않는다"


def test_overview_route_does_not_select_the_whole_result_column():
    """🔴 배선 축 — 라우트가 투영 컬럼을 쓰는가. 함수가 있어도 안 부르면 무의미하다."""
    from src.ui.routes import overview  # pylint: disable=import-outside-toplevel

    src = inspect.getsource(overview)
    assert "_RELIABILITY_COLUMNS" in src, "투영 컬럼이 쿼리에 배선되지 않았다"
    assert "Analysis.result)" not in src.replace("_json_path(Analysis.result, path)", ""), (
        "쿼리가 아직 Analysis.result 전체를 select 한다"
    )
