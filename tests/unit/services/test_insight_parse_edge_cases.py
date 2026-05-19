"""insight_narrative — Claude 응답 파싱 경계 케이스 단위 테스트.

unit tests for Claude response parsing edge cases in insight_narrative.

검증 대상:
    src/services/dashboard_service.py::_extract_insight_json()
    src/services/dashboard_service.py::_parse_insight_cards()

담당 케이스 4종:
    1. 빈 문자열 응답 → parse_error
    2. JSON 포맷이지만 필수 키 누락 (positive_highlights, focus_areas 만 있고
       key_metrics, next_actions 없음) → success (빈 list 허용 — get() 기본값)
    3. 마크다운 코드블록 안에 JSON (```json ... ```) → success (코드 블록 제거 지원)
    4. 앞뒤 prose가 붙은 JSON → success (_extract_insight_json first/last { } fallback)
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from src.services.dashboard_service import (
    _extract_insight_json,
    _parse_insight_cards,
)


# ─── 공유 헬퍼 ─────────────────────────────────────────────────────────────


_FULL_VALID_JSON = json.dumps(
    {
        "positive_highlights": ["강점 1", "강점 2", "강점 3"],
        "focus_areas": ["개선 1", "개선 2", "개선 3"],
        "key_metrics": [
            {"label": "평균 점수", "value": "84.2", "delta": "+3.1"},
            {"label": "분석 건수", "value": "5", "delta": "+2"},
            {"label": "보안 HIGH", "value": "0", "delta": "0"},
            {"label": "Auto-merge 성공", "value": "100%", "delta": "+10%"},
        ],
        "next_actions": ["액션 1", "액션 2"],
    },
    ensure_ascii=False,
)


def _make_anthropic_response(text: str) -> MagicMock:
    """Anthropic Messages API 응답 mock — content[0].text 형식.

    Builds a MagicMock matching the Anthropic Messages API response shape.
    """
    fake_msg = MagicMock()
    text_block = MagicMock()
    text_block.text = text
    fake_msg.content = [text_block]
    fake_msg.usage = MagicMock(
        input_tokens=100,
        output_tokens=50,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=100,
    )
    return fake_msg


# ─── Case 1: 빈 문자열 응답 ────────────────────────────────────────────────


class TestEmptyStringResponse:
    """Case 1 — 빈 문자열 응답은 parse_error 를 반환해야 한다.

    Case 1 — Empty string response must yield parse_error.
    """

    def test_extract_insight_json_returns_empty_string_for_empty_input(self):
        """`_extract_insight_json("")` → 빈 문자열 반환 (JSON 없음).

        Confirm _extract_insight_json returns empty string for empty input.
        """
        result = _extract_insight_json("")
        assert result == ""

    def test_parse_insight_cards_returns_none_for_empty_string(self):
        """`_parse_insight_cards("")` → None (json.loads 실패 → parse_error 경로).

        _parse_insight_cards on empty string returns None, triggering parse_error downstream.
        """
        result = _parse_insight_cards("")
        assert result is None

    def test_parse_insight_cards_none_maps_to_parse_error_contract(self):
        """None 반환은 insight_narrative 에서 parse_error 로 매핑됨을 명시적으로 검증.

        Explicitly verify that a None return maps to parse_error in insight_narrative flow.
        The actual mapping lives at dashboard_service.py line ~856:
            if cards is None:
                return _build_insight_response(status="parse_error", days=days)
        """
        # _make_anthropic_response 를 통한 end-to-end 파싱 경로 재현
        # Reproduce end-to-end parsing path via the mock response helper
        response = _make_anthropic_response("")
        text = response.content[0].text
        cards = _parse_insight_cards(text)
        assert cards is None, (
            "빈 문자열 응답은 _parse_insight_cards 에서 None 을 반환해 "
            "insight_narrative 의 parse_error 경로로 진입해야 합니다."
        )


# ─── Case 2: 필수 키 누락 JSON ─────────────────────────────────────────────


class TestMissingRequiredKeysJson:
    """Case 2 — 필수 키 일부 누락 JSON 처리 검증.

    Case 2 — JSON missing required keys (key_metrics, next_actions).

    _parse_insight_cards 는 json.loads 성공 후 data.get() 기본값 빈 list 사용 →
    키 누락 시에도 success 경로 (None 반환 X, 빈 list 포함 dict 반환).
    _parse_insight_cards uses data.get() with empty list defaults after json.loads,
    so missing keys produce success (empty lists), not parse_error.
    """

    _PARTIAL_JSON = json.dumps(
        {
            "positive_highlights": ["강점 1", "강점 2"],
            "focus_areas": ["개선 1", "개선 2"],
            # key_metrics, next_actions 의도적 누락
            # key_metrics and next_actions intentionally omitted
        },
        ensure_ascii=False,
    )

    def test_extract_insight_json_returns_raw_json_for_well_formed_input(self):
        """`_extract_insight_json` 은 유효한 JSON 문자열을 그대로 반환.

        _extract_insight_json returns the raw JSON string unchanged for well-formed input.
        """
        result = _extract_insight_json(self._PARTIAL_JSON)
        # first { ~ last } 추출 — 원본과 동일해야 함
        # First { to last } extraction — must equal the original
        assert json.loads(result) == json.loads(self._PARTIAL_JSON)

    def test_parse_insight_cards_returns_dict_not_none_for_partial_keys(self):
        """`_parse_insight_cards` 는 키 누락 JSON 에도 None 이 아닌 dict 반환.

        _parse_insight_cards returns a dict (not None) even when required keys are missing.
        This is a success path — missing keys default to empty lists via data.get().
        """
        result = _parse_insight_cards(self._PARTIAL_JSON)
        assert result is not None, (
            "키 누락 JSON 은 json.loads 자체는 성공하므로 None 이 아닌 dict 를 반환해야 합니다. "
            "insight_narrative 는 success 상태로 진행합니다."
        )
        assert isinstance(result, dict)

    def test_parse_insight_cards_fills_missing_keys_with_empty_lists(self):
        """누락된 key_metrics, next_actions 는 빈 list 로 채워져야 한다.

        Missing key_metrics and next_actions must be filled with empty lists.
        """
        result = _parse_insight_cards(self._PARTIAL_JSON)
        assert result is not None
        # 존재하는 키는 원본 값 유지
        # Existing keys preserve their original values
        assert result["positive_highlights"] == ["강점 1", "강점 2"]
        assert result["focus_areas"] == ["개선 1", "개선 2"]
        # 누락 키는 빈 list 기본값
        # Missing keys default to empty list
        assert result["key_metrics"] == []
        assert result["next_actions"] == []

    def test_partial_json_status_is_success_not_parse_error(self):
        """키 누락 JSON 의 status 가 success 임을 명시적으로 기록.

        Explicitly document that partial-key JSON yields status=success (not parse_error).
        This is intentional: _parse_insight_cards does not enforce schema strictness —
        it uses .get() defaults. The system prompt instructs Claude to include all keys,
        but the parser is lenient on the reader side.
        """
        cards = _parse_insight_cards(self._PARTIAL_JSON)
        # None 이 아니면 insight_narrative 는 success 로 진행 (parse_error 아님)
        # Non-None cards → insight_narrative proceeds to success (not parse_error)
        assert cards is not None
        # status 매핑은 insight_narrative 내부 로직이므로 여기서는 None 여부만 확인
        # Status mapping is internal to insight_narrative; only check None vs dict here


# ─── Case 3: 마크다운 코드블록 안에 JSON ───────────────────────────────────


class TestMarkdownCodeBlockJson:
    """Case 3 — 마크다운 코드블록 패턴 ``json ... `` 처리 검증.

    Case 3 — Markdown fenced code block pattern handling.

    많은 LLM 이 ``json\\n{...}\\n`` 형식으로 응답함.
    _extract_insight_json 은 re.search(r"``(?:json)?\\s*(\\{.*?\\})\\s*``") 으로
    코드 블록 제거를 지원하므로 → success 경로.

    Many LLMs respond with ``json\\n{...}\\n`` format.
    _extract_insight_json uses a regex to strip fenced blocks → success path.
    """

    _CODE_BLOCK_RESPONSE = f"```json\n{_FULL_VALID_JSON}\n```"
    _CODE_BLOCK_NO_LANG = f"```\n{_FULL_VALID_JSON}\n```"

    def test_extract_insight_json_strips_json_code_block(self):
        """`_extract_insight_json` 은 ```json ... ``` 블록에서 JSON 본문을 추출한다.

        _extract_insight_json extracts JSON body from ```json ... ``` fenced block.
        """
        result = _extract_insight_json(self._CODE_BLOCK_RESPONSE)
        parsed = json.loads(result)
        assert "positive_highlights" in parsed
        assert "key_metrics" in parsed

    def test_extract_insight_json_strips_bare_code_block(self):
        """`_extract_insight_json` 은 언어 지정 없는 ``` ... ``` 블록도 처리한다.

        _extract_insight_json handles bare ``` ... ``` block (no language specifier).
        """
        result = _extract_insight_json(self._CODE_BLOCK_NO_LANG)
        parsed = json.loads(result)
        assert "positive_highlights" in parsed

    def test_parse_insight_cards_succeeds_for_code_block_response(self):
        """`_parse_insight_cards` 는 코드블록 응답에서 4 카드 dict 를 반환한다.

        _parse_insight_cards returns a 4-card dict for a code-block-wrapped response.
        This is the key behavior: Claude often returns JSON inside ```json``` blocks,
        and the parser must handle this gracefully (not return None / parse_error).
        """
        result = _parse_insight_cards(self._CODE_BLOCK_RESPONSE)
        assert result is not None, (
            "마크다운 코드블록 응답은 parse_error 가 아닌 success 여야 합니다. "
            "_extract_insight_json 의 regex 가 코드 블록 제거를 지원합니다."
        )
        assert len(result["positive_highlights"]) == 3
        assert len(result["focus_areas"]) == 3
        assert len(result["key_metrics"]) == 4
        assert len(result["next_actions"]) == 2

    def test_parse_insight_cards_via_mock_response_code_block(self):
        """_make_anthropic_response 경유 코드블록 파싱 — end-to-end 재현.

        End-to-end reproduction via _make_anthropic_response with a code-block payload.
        """
        response = _make_anthropic_response(self._CODE_BLOCK_RESPONSE)
        text = response.content[0].text
        cards = _parse_insight_cards(text)
        assert cards is not None
        # key_metrics 4건 존재 + label 필드 검증
        # Verify 4 key_metrics items with label fields
        assert all("label" in m for m in cards["key_metrics"])


# ─── Case 4: 앞뒤 prose가 붙은 JSON ──────────────────────────────────────


class TestProseWrappedJson:
    """Case 4 — 앞뒤 prose 텍스트로 감싸진 JSON 처리 검증.

    Case 4 — JSON wrapped by leading/trailing prose text.

    일부 LLM 이 "Here is the analysis:\\n{...}\\nHope this helps!" 형식으로 응답.
    _extract_insight_json 은 first `{` ~ last `}` fallback 으로 추출 → success 경로.

    Some LLMs respond with prose before/after the JSON.
    _extract_insight_json uses first `{` to last `}` fallback → success path.
    """

    _PROSE_WRAPPED_RESPONSE = (
        "Here is the analysis:\n"
        + _FULL_VALID_JSON
        + "\nHope this helps!"
    )

    _KOREAN_PROSE_WRAPPED_RESPONSE = (
        "다음은 분석 결과입니다.\n\n"
        + _FULL_VALID_JSON
        + "\n\n이상입니다. 도움이 되길 바랍니다."
    )

    def test_extract_insight_json_extracts_from_prose_wrapped_response(self):
        """`_extract_insight_json` 은 앞뒤 prose 텍스트에서 JSON 본문을 추출한다.

        _extract_insight_json extracts JSON body from leading/trailing prose.
        Uses first `{` to last `}` substring extraction as fallback.
        """
        result = _extract_insight_json(self._PROSE_WRAPPED_RESPONSE)
        parsed = json.loads(result)
        assert "positive_highlights" in parsed
        assert "next_actions" in parsed

    def test_extract_insight_json_handles_korean_prose(self):
        """한국어 prose 앞뒤에 감싸인 JSON 도 추출 가능해야 한다.

        _extract_insight_json handles JSON wrapped by Korean prose text.
        """
        result = _extract_insight_json(self._KOREAN_PROSE_WRAPPED_RESPONSE)
        parsed = json.loads(result)
        assert "key_metrics" in parsed

    def test_parse_insight_cards_succeeds_for_prose_wrapped_response(self):
        """`_parse_insight_cards` 는 prose 감싸인 응답에서 4 카드 dict 를 반환한다.

        _parse_insight_cards returns a 4-card dict for a prose-wrapped response.
        This confirms the first/last { } fallback in _extract_insight_json works correctly.
        """
        result = _parse_insight_cards(self._PROSE_WRAPPED_RESPONSE)
        assert result is not None, (
            "앞뒤 prose 감싸인 응답은 parse_error 가 아닌 success 여야 합니다. "
            "_extract_insight_json 의 first/last { } fallback 이 지원합니다."
        )
        assert len(result["positive_highlights"]) == 3
        assert len(result["key_metrics"]) == 4

    def test_parse_insight_cards_via_mock_response_prose_wrapped(self):
        """_make_anthropic_response 경유 prose 감싸인 파싱 — end-to-end 재현.

        End-to-end reproduction via _make_anthropic_response with prose-wrapped payload.
        """
        response = _make_anthropic_response(self._PROSE_WRAPPED_RESPONSE)
        text = response.content[0].text
        cards = _parse_insight_cards(text)
        assert cards is not None
        # next_actions 2건 존재 + str 타입 검증
        # Verify 2 next_actions items with str type
        assert len(cards["next_actions"]) == 2
        assert all(isinstance(s, str) for s in cards["next_actions"])


# ─── 크로스-케이스 요약 테스트 ──────────────────────────────────────────────


class TestParseSummaryMatrix:
    """4 케이스 요약 — _parse_insight_cards 반환값 / None 여부 matrix.

    Summary matrix test for all 4 cases:
    - empty string    → None  (parse_error)
    - partial keys    → dict  (success, missing keys filled with [])
    - code block      → dict  (success, fenced block stripped)
    - prose wrapped   → dict  (success, first/last {} fallback)
    """

    _PARTIAL_JSON = json.dumps(
        {"positive_highlights": [], "focus_areas": []}, ensure_ascii=False
    )
    _CODE_BLOCK = f"```json\n{_FULL_VALID_JSON}\n```"
    _PROSE_WRAPPED = "Analysis:\n" + _FULL_VALID_JSON + "\nDone."

    @pytest.mark.parametrize(
        "text, expect_none, case_label",
        [
            ("", True, "빈 문자열 → parse_error (None)"),
            (_PARTIAL_JSON, False, "필수 키 누락 JSON → success (dict, 빈 list 기본값)"),
            (_CODE_BLOCK, False, "마크다운 코드블록 → success (코드 블록 제거)"),
            (_PROSE_WRAPPED, False, "앞뒤 prose → success (first/last {} fallback)"),
        ],
    )
    def test_parse_matrix(self, text: str, expect_none: bool, case_label: str):
        """4 케이스 파라미터화 요약 테스트.

        Parameterized summary test for all 4 parsing edge cases.
        """
        result = _parse_insight_cards(text)
        if expect_none:
            assert result is None, (
                f"케이스 [{case_label}]: None 을 기대했으나 {result!r} 를 반환했습니다."
            )
        else:
            assert result is not None, (
                f"케이스 [{case_label}]: dict 를 기대했으나 None 을 반환했습니다."
            )
            assert isinstance(result, dict)
            # 4 카드 키 모두 존재 검증
            # Verify all 4 card keys are present
            for key in ("positive_highlights", "focus_areas", "key_metrics", "next_actions"):
                assert key in result, (
                    f"케이스 [{case_label}]: 카드 키 '{key}' 가 결과에 없습니다."
                )
