"""인사이트 서술 JSON 추출 — 서술 문자열 안의 펜스가 완결 본문을 이기지 않는다 (#1702).

두 추출기(`dashboard_service._extract_insight_json` · `repo_insight_service._extract_narrative_json`)는
```` ```{…}``` ```` 펜스를 바깥 객체보다 먼저 골랐다. 서술 문자열에 ```` ```{}``` ```` 가 들어 있으면
그 `{}` 를 읽어, 대시보드는 **빈 카드 success**, 리포는 **원문 JSON 전체를 text 로** 내보냈다.
바깥 객체가 스키마 모양(카드 키 · `{"text": 문자열}`)으로 읽히면 그것이 본문이다.

Both extractors preferred a fenced block over the outer object, so a fence inside a narrative
string won: the dashboard returned empty cards as success and the repo returned the raw JSON as
text. When the outer object parses into the schema shape, it is the body.
"""
from __future__ import annotations

import json

import pytest

from src.services.dashboard_service import _parse_insight_cards
from src.services.repo_insight_service import _NarrativeTruncated, _narrative_text

_FENCED_PHRASE = "코드 블록은 ```{}``` 처럼 감싼다"
_CARDS = {
    "positive_highlights": [_FENCED_PHRASE],
    "focus_areas": ["보안 이슈 1건"],
    "key_metrics": [{"label": "평균 점수", "value": "82", "delta": "+3"}],
    "next_actions": ["테스트 보강"],
}
_CARDS_WITH_FENCE = json.dumps(_CARDS, ensure_ascii=False)
# 펜스 문구가 없는 카드 — 「진짜 펜스 본문」 사례가 펜스-속-펜스 문제와 섞이지 않게
# Cards without the fence phrase, so the real-fenced-payload cases do not mix in fence-in-fence.
_PLAIN_CARDS = {**_CARDS, "positive_highlights": ["점수가 안정적이다"]}
_TEXT_WITH_FENCE = json.dumps({"text": _FENCED_PHRASE}, ensure_ascii=False)


def test_dashboard_fence_inside_a_card_string_keeps_the_full_cards():
    """🔴 잡혀야 — 카드 문자열 안의 펜스를 본문으로 읽지 않는다(수정 전: 네 목록 모두 빈 success).
    A fence inside a card string must not replace the body (before: four empty lists).
    """
    cards = _parse_insight_cards(_CARDS_WITH_FENCE)

    assert cards == _CARDS


def test_dashboard_real_fenced_payload_after_a_stray_object_still_wins():
    """🔴 무시돼야(부분문자열≠상태) — 앞의 `{"meta": "positive_highlights"}` 는 키 이름을 «문자열로»
    품었을 뿐 카드가 아니다. 바깥 범위는 JSON 이 아니므로 펜스 안의 진짜 본문을 고른다.
    The key name inside a string is not a card key; the outer span is not JSON, so the fence wins.
    """
    text = f'{{"meta": "positive_highlights"}}\n```json\n{json.dumps(_PLAIN_CARDS, ensure_ascii=False)}\n```'

    assert _parse_insight_cards(text) == _PLAIN_CARDS


def test_repo_fence_inside_text_returns_the_text_not_the_raw_json():
    """🔴 잡혀야 — 상한이 아닌 멈춤(수정 전: `{}` 를 읽고 폴백으로 원문 JSON 전체가 text).
    Non-cap stop: before, `{}` was read and the raw JSON fell back into text.
    """
    assert _narrative_text(_TEXT_WITH_FENCE, at_cap=False) == _FENCED_PHRASE


def test_repo_fence_inside_text_at_the_cap_is_a_closed_body():
    """🔴 잡혀야 — 상한 멈춤(수정 전: `{}` 를 읽어 `max_tokens` 로 버렸다). 닫힌 본문이다.
    At the cap: before, `{}` was read and the closed body was discarded as max_tokens.
    """
    assert _narrative_text(_TEXT_WITH_FENCE, at_cap=True) == _FENCED_PHRASE


def test_repo_real_fenced_payload_after_a_stray_object_still_wins():
    """🔴 무시돼야(부분문자열≠상태) — `{"meta": "text"}` 는 `text` 를 값으로 품었을 뿐이다.
    `{"meta": "text"}` only carries "text" as a value; the fenced body is the payload.
    """
    text = '{"meta": "text"}\n```json\n{"text": "본문"}\n```'

    assert _narrative_text(text, at_cap=False) == "본문"


@pytest.mark.parametrize("body", ['{"text": 3}', '{"summary": "x"}'])
def test_repo_outer_object_without_a_string_text_is_still_refused_at_the_cap(body):
    """대조군 — 바깥이 JSON 이어도 `{"text": 문자열}` 이 아니면 상한에서는 여전히 잘림이다(#1700 계약).
    Control: at the cap, an outer object without a string `text` is still truncation.
    """
    with pytest.raises(_NarrativeTruncated):
        _narrative_text(body, at_cap=True)


@pytest.mark.parametrize("value", [True, 5, "문자열", {"a": 1}])
def test_dashboard_card_value_that_is_not_a_list_becomes_empty(value):
    """🔴 잡혀야 — 목록 자리의 비-목록 값(`true` · 숫자 · 문자열 · 객체)은 빈 목록이다.
    수정 전: `true`·숫자는 `TypeError`(상한 판정에선 api_error, `_finish_insight` 에선 미포착 500),
    문자열은 글자 하나하나가 카드가 됐다 (Grok `caa22077` 적발).
    A non-list card value folds to an empty list (before: TypeError for bool/int, one card per
    character for a string).
    """
    body = json.dumps({**_PLAIN_CARDS, "positive_highlights": value}, ensure_ascii=False)

    cards = _parse_insight_cards(body)

    assert cards is not None
    assert cards["positive_highlights"] == []
    assert cards["focus_areas"] == _PLAIN_CARDS["focus_areas"]
