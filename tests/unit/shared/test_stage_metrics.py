"""stage_metrics — 파이프라인 단계별 타이밍 로깅 테스트 (Phase E.2c).

TDD Red: src/shared/stage_metrics.py 모듈은 아직 없음.
"""
import logging
import time

import pytest

from src.shared import stage_metrics  # noqa: E402


class TestStageTimerSuccess:
    """stage_timer context manager — 정상 완료 경로"""

    def test_logs_stage_and_duration(self, caplog):
        with caplog.at_level(logging.INFO, logger="src.shared.stage_metrics"):
            with stage_metrics.stage_timer("collect_files"):
                time.sleep(0.01)  # 10ms 대기
        assert len(caplog.records) >= 1
        record = caplog.records[-1]
        msg = record.getMessage()
        assert "collect_files" in msg
        assert "success" in msg
        # duration_ms 가 extra 에 포함
        assert getattr(record, "pipeline_stage", None) == "collect_files"
        assert getattr(record, "duration_ms", 0) >= 5  # 적어도 5ms

    def test_extra_fields_included_in_log(self, caplog):
        # 호출 시 extra_fields 를 전달하면 LogRecord extra 로 병합됨
        with caplog.at_level(logging.INFO, logger="src.shared.stage_metrics"):
            with stage_metrics.stage_timer("analyze", language="python"):
                pass
        record = caplog.records[-1]
        assert getattr(record, "language", None) == "python"

    def test_ctx_dict_merges_to_log(self, caplog):
        # ctx.update() 로 추가한 필드도 로그에 포함
        with caplog.at_level(logging.INFO, logger="src.shared.stage_metrics"):
            with stage_metrics.stage_timer("collect_files") as ctx:
                ctx["file_count"] = 5
        record = caplog.records[-1]
        assert getattr(record, "file_count", None) == 5

    def test_status_success_on_normal_exit(self, caplog):
        with caplog.at_level(logging.INFO, logger="src.shared.stage_metrics"):
            with stage_metrics.stage_timer("noop"):
                pass
        record = caplog.records[-1]
        assert getattr(record, "status", None) == "success"


class TestStageTimerException:
    """stage_timer context manager — 예외 경로"""

    def test_logs_error_on_exception(self, caplog):
        with caplog.at_level(logging.WARNING, logger="src.shared.stage_metrics"):
            with pytest.raises(ValueError):
                with stage_metrics.stage_timer("faulty_stage"):
                    raise ValueError("boom")
        # 예외 경로도 로그 발생
        assert len(caplog.records) >= 1
        record = caplog.records[-1]
        assert getattr(record, "status", None) == "error"
        assert getattr(record, "error_type", None) == "ValueError"
        assert getattr(record, "pipeline_stage", None) == "faulty_stage"

    def test_propagates_original_exception(self):
        # 예외는 반드시 전파되어야 함 (swallow 금지)
        with pytest.raises(RuntimeError, match="test-exc"):
            with stage_metrics.stage_timer("stage"):
                raise RuntimeError("test-exc")

    def test_duration_captured_even_on_exception(self, caplog):
        with caplog.at_level(logging.WARNING, logger="src.shared.stage_metrics"):
            with pytest.raises(Exception):
                with stage_metrics.stage_timer("slow_fail"):
                    time.sleep(0.01)
                    raise RuntimeError("fail")
        record = caplog.records[-1]
        assert getattr(record, "duration_ms", 0) >= 5
