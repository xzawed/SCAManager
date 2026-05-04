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

    # ── Phase 1 (g-G1) — cache 비용 모델 반영 ───────────────────────────
    # cache_read = input 정가의 1/10 (Anthropic 정책 — 5분 ephemeral)
    # cache_creation = input 정가의 1.25× (캐시 등록 비용 — 5분 TTL 내 회수)
    def test_cache_read_costs_one_tenth_of_input(self):
        """cache_read_tokens 는 input rate × 0.1 비용 (10배 절감)."""
        cost = claude_metrics.estimate_claude_cost_usd(
            model="claude-sonnet-4-6",
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=1_000_000,
        )
        # sonnet input $3/M × 0.1 = $0.30
        assert cost == pytest.approx(0.30)

    def test_cache_creation_costs_one_quarter_more_than_input(self):
        """cache_creation_tokens 는 input rate × 1.25 비용 (캐시 등록)."""
        cost = claude_metrics.estimate_claude_cost_usd(
            model="claude-sonnet-4-6",
            input_tokens=0,
            output_tokens=0,
            cache_creation_tokens=1_000_000,
        )
        # sonnet input $3/M × 1.25 = $3.75
        assert cost == pytest.approx(3.75)

    def test_cache_fields_default_zero_backwards_compat(self):
        """cache_*_tokens 인자 부재 시 기존 동작 보존 (backward compat)."""
        cost = claude_metrics.estimate_claude_cost_usd(
            model="claude-sonnet-4-6",
            input_tokens=8000,
            output_tokens=1000,
        )
        assert cost == pytest.approx(0.039)

    def test_combined_cost_with_cache(self):
        """cache + input + output 합산 — 운영 cache hit 시나리오."""
        # 실제: 5000 cache_read (재사용) + 3000 input (신규) + 1000 output
        cost = claude_metrics.estimate_claude_cost_usd(
            model="claude-sonnet-4-6",
            input_tokens=3000,
            output_tokens=1000,
            cache_read_tokens=5000,
        )
        # 5000 * 0.30 + 3000 * 3.0 + 1000 * 15.0 = 1500 + 9000 + 15000 = 25500 µ$
        assert cost == pytest.approx(0.0255)


class TestCacheStats:
    """get_cache_stats — 메모리 카운터 헬퍼 (g-G2)"""

    def setup_method(self):
        # 테스트 격리 — 이전 테스트의 카운터 누적 차단
        # Test isolation — clear counters from previous tests.
        claude_metrics.reset_cache_stats()

    def test_initial_stats_all_zero(self):
        stats = claude_metrics.get_cache_stats()
        assert stats == {
            "total_calls": 0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "input_tokens": 0,
            "cache_hit_rate": 0.0,
        }

    def test_log_call_accumulates_counters(self, caplog):
        with caplog.at_level(logging.INFO, logger="src.shared.claude_metrics"):
            claude_metrics.log_claude_api_call(
                model="claude-sonnet-4-6", duration_ms=100,
                input_tokens=3000, output_tokens=500, status="success",
                cache_read_tokens=5000, cache_creation_tokens=0,
            )
        stats = claude_metrics.get_cache_stats()
        assert stats["total_calls"] == 1
        assert stats["cache_read_tokens"] == 5000
        assert stats["input_tokens"] == 3000
        # cache_hit_rate = read / (read + input) = 5000/8000 = 0.625
        assert stats["cache_hit_rate"] == pytest.approx(0.625)

    def test_silent_fallback_warning_on_creation_without_read(self, caplog):
        """캐시 생성만 반복되고 read 가 0 — silent fallback 의심 — WARNING (신규 발견 2)."""
        with caplog.at_level(logging.WARNING, logger="src.shared.claude_metrics"):
            # 5회 연속 creation > 0 + read == 0 → WARNING 발화
            # 5 consecutive creation > 0 + read == 0 → WARNING expected.
            for _ in range(5):
                claude_metrics.log_claude_api_call(
                    model="claude-sonnet-4-6", duration_ms=100,
                    input_tokens=1000, output_tokens=500, status="success",
                    cache_read_tokens=0, cache_creation_tokens=600,
                )
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert any("cache_read=0" in r.getMessage() or "silent" in r.getMessage().lower()
                   for r in warnings), \
            "5회 연속 cache_creation>0 + cache_read=0 시 WARNING 의무"


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
        # All essential fields must be present.
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
