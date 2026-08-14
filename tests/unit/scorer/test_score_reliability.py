"""R46 — score reliability classification (Axis A).

Pin expected cases as literals — never import the expected set from the module under test.
"""
from __future__ import annotations

from src.scorer.reliability import score_is_unreliable, should_null_persist_score


def test_reliable_success_is_not_unreliable():
    result = {
        "source": "pr",
        "ai_review_status": "success",
        "breakdown": {"code_quality": 25, "security": 20},
        "static_analysis_incomplete": False,
        "static_uncovered_languages": [],
    }
    assert score_is_unreliable(result) is False
    assert should_null_persist_score(result) is False


def test_api_error_is_unreliable_and_null_persist():
    result = {"ai_review_status": "api_error", "breakdown": {"ai_defaults_applied": True}}
    assert score_is_unreliable(result) is True
    assert should_null_persist_score(result) is True


def test_parse_error_is_unreliable_and_null_persist():
    result = {"ai_review_status": "parse_error", "breakdown": {"ai_defaults_applied": True}}
    assert score_is_unreliable(result) is True
    assert should_null_persist_score(result) is True


def test_cli_source_is_unreliable_but_not_null_persist():
    """CLI rows keep score on detail page; aggregates exclude via flag (least destructive)."""
    result = {
        "source": "cli",
        "ai_review_status": "success",
        "static_analysis_incomplete": True,
        "breakdown": {},
    }
    assert score_is_unreliable(result) is True
    assert should_null_persist_score(result) is False


def test_cli_source_alone_is_unreliable():
    """🔴 **CLI 축만 재는 대조군** — 위 테스트는 이 축을 관측하지 못했다.

    ## 사고 (2026-08-15 뮤테이션 실측)

    `test_cli_source_is_unreliable_but_not_null_persist` 의 픽스처는 `source: "cli"` 와
    `static_analysis_incomplete: True` 를 **함께** 달고 있다. 두 조건이 각각 독립으로
    unreliable 을 만들므로, `score_is_unreliable` 에서 **`source == "cli"` 분기를 통째로
    지워도 그 테스트는 GREEN** 이었다(실측: 21 passed).

    그런데 CLI 축이야말로 사용자가 보는 결함의 본체다 — CLI 훅이 저장하는 무검증 45점이
    대시보드 평균에 섞이는 것이 R46 의 (a) 이다. 그 축에 관측자가 없었다.

    실제 CLI 행이 항상 `static_analysis_incomplete` 를 함께 달지는 **보장되지 않는다** —
    `hook.py` 가 정적 분석기를 하나라도 돌린 경우를 생각하면 그 플래그 없이 `source=cli`
    만 남을 수 있다. 그때 이 분기가 유일한 방어선이다.

    A doubly-marked fixture cannot observe either condition alone.
    """
    assert score_is_unreliable({
        "source": "cli",
        "ai_review_status": "success",
        "breakdown": {},
    }) is True


def test_static_incomplete_is_unreliable_but_not_null_persist():
    result = {
        "source": "push",
        "ai_review_status": "success",
        "static_analysis_incomplete": True,
    }
    assert score_is_unreliable(result) is True
    assert should_null_persist_score(result) is False


def test_ai_defaults_applied_is_unreliable_but_not_null_persist():
    result = {
        "source": "pr",
        "ai_review_status": "success",
        "breakdown": {"ai_defaults_applied": True},
    }
    assert score_is_unreliable(result) is True
    assert should_null_persist_score(result) is False


def test_disabled_status_is_unreliable_but_not_null_persist():
    result = {"source": "pr", "ai_review_status": "disabled", "breakdown": {}}
    assert score_is_unreliable(result) is True
    assert should_null_persist_score(result) is False


def test_no_api_key_and_empty_diff_are_unreliable_but_not_null_persist():
    for status in ("no_api_key", "empty_diff"):
        result = {"ai_review_status": status, "breakdown": {}}
        assert score_is_unreliable(result) is True, status
        assert should_null_persist_score(result) is False, status


def test_uncovered_languages_are_unreliable_but_not_null_persist():
    result = {
        "source": "pr",
        "ai_review_status": "success",
        "static_uncovered_languages": ["lua", "r"],
    }
    assert score_is_unreliable(result) is True
    assert should_null_persist_score(result) is False


def test_truncated_alone_is_still_reliable_for_aggregate():
    """C22: input-diff truncation keeps score; not reclassified as unreliable here."""
    result = {
        "source": "pr",
        "ai_review_status": "success",
        "ai_review_truncated": True,
        "breakdown": {},
        "static_uncovered_languages": [],
    }
    assert score_is_unreliable(result) is False
    assert should_null_persist_score(result) is False


def test_none_and_empty_result_are_reliable():
    assert score_is_unreliable(None) is False
    assert score_is_unreliable({}) is False
    assert should_null_persist_score(None) is False
