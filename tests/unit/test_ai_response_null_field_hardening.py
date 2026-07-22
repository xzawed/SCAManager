"""AI 응답 null/비-dict 필드 하드닝 회귀 가드 (종합감사 P1-2·P1-7·P1-10, Grok cross-verify REAL).
Regression guards for the AI-response null/non-dict field crash class (audit P1-2/7/10).

🔴 근본: LLM 이 문법상 유효한 JSON 이지만 빈 컬렉션을 `[]` 대신 `null` 로, 원소를 `dict` 대신
`str` 로 emit 하는 흔한 패턴. `data.get(k, [])` 는 **present-null 을 coerce 하지 않으므로**
`for x in None` → TypeError / `str.get()` → AttributeError 로, 정상 채점된 리뷰가 api_error·점수
NULL 로 붕괴하거나 PR 코멘트가 소실되거나 /dashboard?mode=insight 가 500 이 된다.
Root: a model may emit valid JSON with a null array or a str element; `.get(k, [])` does not
coerce present-null, so a scored review collapses / a comment drops / the insight route 500s.
"""
from src.analyzer.io.ai_review import _parse_response
from src.notifier.github_comment import _file_feedback_lines
from src.services.dashboard_service import _parse_insight_cards


# ── P1-2: ai_review._parse_response ──────────────────────────────────────

_VALID_SCORES = '"commit_message_score":15,"direction_score":16,"test_score":8,"summary":"ok"'


def test_parse_response_null_arrays_do_not_collapse_scored_review():
    """🔴 suggestions/file_feedbacks 가 null 이어도 정상 채점 리뷰가 보존된다(api_error 붕괴 X)."""
    text = "{" + _VALID_SCORES + ',"suggestions":null,"file_feedbacks":null}'
    result = _parse_response(text)  # 예외 없이 반환되어야 함 / must not raise
    assert result.suggestions == []
    assert result.file_feedbacks == []
    # 점수 보존 — null 배열이 채점을 무너뜨리지 않음
    assert result.commit_score == 15 and result.ai_score == 16


def test_parse_response_filters_non_dict_file_feedback():
    """비-dict file_feedback 원소(str)는 원천에서 걸러진다 — 소비처 AttributeError 예방(P1-7 페어)."""
    text = "{" + _VALID_SCORES + ',"file_feedbacks":["config.py: needs tests", {"file":"a.py","issues":["x"]}]}'
    result = _parse_response(text)
    assert result.file_feedbacks == [{"file": "a.py", "issues": ["x"]}]


# ── P1-7: github_comment._file_feedback_lines ────────────────────────────

def test_file_feedback_lines_skips_non_dict_element():
    """🔴 file_feedbacks 에 str 원소가 섞여도 .get() AttributeError 없이 dict 만 렌더."""
    result = {"file_feedbacks": ["a bare string", {"file": "a.py", "issues": ["issue1"]}]}
    lines = _file_feedback_lines(result)  # must not raise
    joined = "\n".join(lines)
    assert "a.py" in joined and "issue1" in joined
    assert "a bare string" not in joined  # 비-dict 는 건너뜀


def test_file_feedback_lines_empty_on_null():
    """null file_feedbacks 는 빈 섹션(기존 falsy 가드 회귀 방지)."""
    assert _file_feedback_lines({"file_feedbacks": None}) == []


# ── P1-10: dashboard_service._parse_insight_cards ────────────────────────

def test_parse_insight_cards_null_array_yields_empty_not_500():
    """🔴 null 배열 필드 → TypeError 로 500 되지 않고 정규화된 카드 반환."""
    text = '{"positive_highlights":null,"focus_areas":[],"key_metrics":[],"next_actions":[]}'
    cards = _parse_insight_cards(text)  # must not raise
    assert cards is not None
    assert cards["positive_highlights"] == []


def test_parse_insight_cards_non_dict_json_returns_none():
    """비-dict JSON(스칼라/배열)은 graceful None(parse_error 카드 경로) — 500 아님."""
    assert _parse_insight_cards('"just a string"') is None
    assert _parse_insight_cards("[1, 2, 3]") is None
