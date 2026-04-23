"""claude_metrics — Claude API 비용 추정 + 호출 메트릭 로깅 테스트 (Phase E.2b).

TDD Red: src/shared/claude_metrics.py 모듈은 아직 없음.
"""
import logging
from unittest.mock import MagicMock

import pytest

from src.shared import claude_metrics  # noqa: E402


class TestEstimateCostUsd:
    """estimate_claude_cost_usd — 모델별 가격 정책 (USD/MTok)"""

    def test_sonnet_rates(self):
        # sonnet: $3/M input, $15/M output
        cost = claude_metrics.estimate_claude_cost_usd(
            model="claude-sonnet-4-6",
            input_tokens=1_000_000,
            output_tokens=0,
        )
        assert cost == pytest.approx(3.0)

    def test_sonnet_output_cost(self):
        cost = claude_metrics.estimate_claude_cost_usd(
            model="claude-sonnet-4-6",
            input_tokens=0,
            output_tokens=1_000_000,
        )
        assert cost == pytest.approx(15.0)

    def test_opus_rates(self):
        # opus: $15/M input, $75/M output
        cost = claude_metrics.estimate_claude_cost_usd(
            model="claude-opus-4",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        assert cost == pytest.approx(15.0 + 75.0)

    def test_haiku_rates(self):
        # haiku: $1/M input, $5/M output
        cost = claude_metrics.estimate_claude_cost_usd(
            model="claude-haiku-4-5",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        assert cost == pytest.approx(1.0 + 5.0)

    def test_unknown_model_defaults_to_sonnet(self):
        # 미지의 모델 → sonnet 가격 사용 (보수적 추정)
        cost = claude_metrics.estimate_claude_cost_usd(
            model="gemini-pro-2",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        assert cost == pytest.approx(3.0 + 15.0)

    def test_zero_tokens_returns_zero(self):
        cost = claude_metrics.estimate_claude_cost_usd(
            model="claude-sonnet-4-6",
            input_tokens=0,
            output_tokens=0,
        )
        assert cost == 0.0

    def test_realistic_review_cost(self):
        # 실제 리뷰 1건: ~8k input + 1k output (sonnet)
        cost = claude_metrics.estimate_claude_cost_usd(
            model="claude-sonnet-4-6",
            input_tokens=8000,
            output_tokens=1000,
        )
        # 8000 * 3 + 1000 * 15 = 24000 + 15000 = 39000 µ$ = $0.039
        assert cost == pytest.approx(0.039)


class TestLogClaudeApiCall:
    """log_claude_api_call — 구조화된 로그 출력"""

    def test_success_log_contains_core_fields(self, caplog):
        with caplog.at_level(logging.INFO, logger="src.shared.claude_metrics"):
            claude_metrics.log_claude_api_call(
                model="claude-sonnet-4-6",
                duration_ms=1234.5,
                input_tokens=8000,
                output_tokens=1000,
                status="success",
            )
        assert len(caplog.records) >= 1
        record = caplog.records[-1]
        msg = record.getMessage()
        # 핵심 필드 모두 포함
        assert "claude-sonnet-4-6" in msg
        assert "1234" in msg or "1235" in msg  # duration ms
        assert "8000" in msg  # input tokens
        assert "1000" in msg  # output tokens
        assert "success" in msg

    def test_log_includes_cost_estimate(self, caplog):
        with caplog.at_level(logging.INFO, logger="src.shared.claude_metrics"):
            claude_metrics.log_claude_api_call(
                model="claude-sonnet-4-6",
                duration_ms=1000,
                input_tokens=8000,
                output_tokens=1000,
                status="success",
            )
        msg = caplog.records[-1].getMessage()
        # cost 는 $0.039 근처 — "0.039" 또는 "0.04" 포함
        assert "0.03" in msg or "0.04" in msg or "cost" in msg.lower()

    def test_log_error_status(self, caplog):
        with caplog.at_level(logging.WARNING, logger="src.shared.claude_metrics"):
            claude_metrics.log_claude_api_call(
                model="claude-sonnet-4-6",
                duration_ms=500,
                input_tokens=0,
                output_tokens=0,
                status="error",
                error_type="TimeoutError",
            )
        assert len(caplog.records) >= 1
        msg = caplog.records[-1].getMessage()
        assert "error" in msg.lower()
        assert "TimeoutError" in msg

    def test_log_uses_extra_dict_for_structured_fields(self, caplog):
        # 구조화 필드가 LogRecord 의 extra 로 전달되어야 함
        # (structured log shipper 가 파싱할 수 있도록)
        with caplog.at_level(logging.INFO, logger="src.shared.claude_metrics"):
            claude_metrics.log_claude_api_call(
                model="claude-sonnet-4-6",
                duration_ms=1000,
                input_tokens=8000,
                output_tokens=1000,
                status="success",
            )
        record = caplog.records[-1]
        # extra 는 LogRecord 의 속성으로 병합됨
        assert getattr(record, "claude_model", None) == "claude-sonnet-4-6"
        assert getattr(record, "duration_ms", None) == 1000
        assert getattr(record, "input_tokens", None) == 8000
        assert getattr(record, "output_tokens", None) == 1000
        assert getattr(record, "cost_usd", None) is not None
        assert getattr(record, "status", None) == "success"


class TestExtractUsage:
    """extract_anthropic_usage — response.usage 에서 토큰 추출"""

    def test_extracts_input_output_tokens(self):
        mock_response = MagicMock()
        mock_response.usage.input_tokens = 8000
        mock_response.usage.output_tokens = 1000
        input_tok, output_tok = claude_metrics.extract_anthropic_usage(mock_response)
        assert input_tok == 8000
        assert output_tok == 1000

    def test_returns_zero_when_usage_missing(self):
        # response 가 usage 필드 없을 수 있음 (stream, 에러 등)
        mock_response = MagicMock()
        del mock_response.usage
        input_tok, output_tok = claude_metrics.extract_anthropic_usage(mock_response)
        assert input_tok == 0
        assert output_tok == 0

    def test_returns_zero_when_tokens_missing(self):
        mock_response = MagicMock()
        mock_response.usage = MagicMock(spec=[])  # 속성 없음
        input_tok, output_tok = claude_metrics.extract_anthropic_usage(mock_response)
        assert input_tok == 0
        assert output_tok == 0
