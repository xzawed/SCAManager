"""파이프라인 단계별 타이밍 로깅 — Phase E.2c.

`stage_timer` context manager 로 단계마다 duration_ms + status + extra 필드를
구조화된 로그로 기록. 비동기 함수 안에서도 사용 가능 (`with` 문은 sync/async
공용).
"""
import contextlib
import logging
import time
from typing import Iterator

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def stage_timer(stage: str, **extra_fields: object) -> Iterator[dict]:
    """파이프라인 단계 1개의 시작~종료를 측정하고 구조화된 로그를 낸다.

    Args:
        stage: 단계 이름 (예: "collect_files", "analyze", "save_and_gate")
        **extra_fields: LogRecord extra 로 병합될 고정 필드

    Yields:
        ctx: dict — block 내부에서 `ctx["key"] = value` 로 필드 추가 가능

    Usage:
        with stage_timer("collect_files") as ctx:
            files = await _collect_files(...)
            ctx["file_count"] = len(files)

    동작:
        - 정상 종료: INFO "pipeline_stage ... status=success" 로그
        - 예외: WARNING "pipeline_stage ... status=error error_type=..." + 예외 재전파
        - LogRecord 의 extra 에 pipeline_stage/duration_ms/status + extra_fields + ctx
          필드가 모두 병합되어 structured log shipper 가 파싱 가능
    """
    start = time.perf_counter()
    ctx: dict = {}
    try:
        yield ctx
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        # 예약 키(pipeline_stage / duration_ms / status / error_type) 는 마지막에 병합해
        # extra_fields 나 ctx 가 덮어쓸 수 없게 한다 — 로그 인젝션 방어.
        extra = {
            **extra_fields,
            **ctx,
            "pipeline_stage": stage,
            "duration_ms": duration_ms,
            "status": "error",
            "error_type": type(exc).__name__,
        }
        logger.warning(
            "pipeline_stage stage=%s duration_ms=%.0f status=error error_type=%s",
            stage, duration_ms, type(exc).__name__,
            extra=extra,
        )
        raise
    else:
        duration_ms = (time.perf_counter() - start) * 1000
        extra = {
            **extra_fields,
            **ctx,
            "pipeline_stage": stage,
            "duration_ms": duration_ms,
            "status": "success",
        }
        logger.info(
            "pipeline_stage stage=%s duration_ms=%.0f status=success",
            stage, duration_ms,
            extra=extra,
        )
