"""stage_timer 견고성 검사 — 예약 키 보호·엣지 케이스.

기존 test_stage_metrics.py가 정상/예외 경로 기본 동작을 검증하므로,
이 파일은 보안 방어(예약 키 오버라이드 차단)와 실제 사용에서 자주
나타나는 엣지 케이스에 집중한다.

검증 항목:
  - ctx 딕셔너리가 예약 키(pipeline_stage/duration_ms/status)를 덮어쓸 수 없음
  - extra_fields 인자도 예약 키를 덮어쓸 수 없음
  - 중첩된 stage_timer가 독립적으로 동작함
  - error_type 필드가 예외 시에만 기록됨 (정상 경로에는 없음)
"""
import logging

import pytest

from src.shared.stage_metrics import stage_timer


class TestReservedKeyProtection:
    """ctx 또는 extra_fields로 예약 키를 덮어쓰려 해도 차단되어야 한다.

    CLAUDE.md 주석: "예약 키는 마지막에 병합해 extra_fields나 ctx가
    덮어쓸 수 없게 한다 — 로그 인젝션 방어."
    """

    def test_ctx_cannot_override_pipeline_stage(self, caplog):
        """ctx["pipeline_stage"] 를 설정해도 실제 stage 이름이 사용된다."""
        with caplog.at_level(logging.INFO, logger="src.shared.stage_metrics"):
            with stage_timer("real_stage") as ctx:
                ctx["pipeline_stage"] = "injected_stage"

        record = caplog.records[-1]
        assert getattr(record, "pipeline_stage") == "real_stage", (
            "ctx가 예약 키 pipeline_stage를 덮어썼음 — 로그 인젝션 방어 실패"
        )

    def test_ctx_cannot_override_status(self, caplog):
        """ctx["status"] 를 설정해도 실제 status=success 가 사용된다."""
        with caplog.at_level(logging.INFO, logger="src.shared.stage_metrics"):
            with stage_timer("some_stage") as ctx:
                ctx["status"] = "hacked"

        record = caplog.records[-1]
        assert getattr(record, "status") == "success"

    def test_extra_fields_cannot_override_pipeline_stage(self, caplog):
        """extra_fields로 pipeline_stage를 전달해도 실제 stage 이름이 우선된다."""
        with caplog.at_level(logging.INFO, logger="src.shared.stage_metrics"):
            with stage_timer("real_stage", pipeline_stage="injected"):
                pass

        record = caplog.records[-1]
        assert getattr(record, "pipeline_stage") == "real_stage"

    def test_extra_fields_cannot_override_status(self, caplog):
        """extra_fields로 status를 전달해도 실제 status=success 가 기록된다."""
        with caplog.at_level(logging.INFO, logger="src.shared.stage_metrics"):
            with stage_timer("some_stage", status="fake"):
                pass

        record = caplog.records[-1]
        assert getattr(record, "status") == "success"

    def test_error_path_reserved_keys_still_protected(self, caplog):
        """예외 경로에서도 ctx가 status를 덮어쓸 수 없다."""
        with caplog.at_level(logging.WARNING, logger="src.shared.stage_metrics"):
            with pytest.raises(ValueError):
                with stage_timer("failing_stage") as ctx:
                    ctx["status"] = "success"  # 공격 시도
                    raise ValueError("test")

        record = caplog.records[-1]
        assert getattr(record, "status") == "error"


class TestNestedAndEdgeCases:
    """중첩 사용·엣지 케이스 검증."""

    def test_nested_stage_timers_are_independent(self, caplog):
        """두 stage_timer가 중첩될 때 각각 독립적으로 로그를 남긴다."""
        with caplog.at_level(logging.INFO, logger="src.shared.stage_metrics"):
            with stage_timer("outer") as outer_ctx:
                outer_ctx["level"] = "outer"
                with stage_timer("inner") as inner_ctx:
                    inner_ctx["level"] = "inner"

        assert len(caplog.records) == 2
        stages = [getattr(r, "pipeline_stage") for r in caplog.records]
        assert "inner" in stages
        assert "outer" in stages

        inner_record = next(r for r in caplog.records if getattr(r, "pipeline_stage") == "inner")
        outer_record = next(r for r in caplog.records if getattr(r, "pipeline_stage") == "outer")
        assert getattr(inner_record, "level") == "inner"
        assert getattr(outer_record, "level") == "outer"

    def test_error_type_absent_on_success(self, caplog):
        """정상 경로에서는 error_type 필드가 LogRecord에 없어야 한다."""
        with caplog.at_level(logging.INFO, logger="src.shared.stage_metrics"):
            with stage_timer("clean_stage"):
                pass

        record = caplog.records[-1]
        assert not hasattr(record, "error_type"), (
            "성공 경로에서 error_type 필드가 존재함 — 오진 가능성"
        )

    def test_error_type_present_on_exception(self, caplog):
        """예외 경로에서는 error_type 필드가 정확한 클래스명을 담아야 한다."""
        with caplog.at_level(logging.WARNING, logger="src.shared.stage_metrics"):
            with pytest.raises(TypeError):
                with stage_timer("typed_error_stage"):
                    raise TypeError("type mismatch")

        record = caplog.records[-1]
        assert getattr(record, "error_type") == "TypeError"

    def test_empty_ctx_does_not_crash(self, caplog):
        """ctx를 전혀 수정하지 않아도 정상 동작한다."""
        with caplog.at_level(logging.INFO, logger="src.shared.stage_metrics"):
            with stage_timer("empty_ctx_stage"):
                pass  # ctx 미사용

        assert caplog.records[-1].getMessage() != ""

    def test_zero_duration_recorded(self, caplog):
        """순간적으로 완료되는 단계도 duration_ms >= 0 으로 기록된다."""
        with caplog.at_level(logging.INFO, logger="src.shared.stage_metrics"):
            with stage_timer("instant_stage"):
                pass

        record = caplog.records[-1]
        assert getattr(record, "duration_ms") >= 0
