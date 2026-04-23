"""Sentry SDK 통합 — SENTRY_DSN 설정 시만 활성, 미설정 또는 SDK 부재 시 no-op.

Phase E.2a — 프로덕션 예외·성능 추적 기반 구축.
`sentry-sdk[fastapi]` 가 설치되지 않은 환경 (예: DNS 제약 있는 devcontainer) 에서도
앱이 크래시하지 않도록 graceful ImportError 처리.
"""
import logging

from src.config import settings

logger = logging.getLogger(__name__)

try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    _SENTRY_AVAILABLE = True
except ImportError:  # pragma: no cover — DNS 제약 dev env 전용 경로
    sentry_sdk = None  # type: ignore[assignment]
    FastApiIntegration = None  # type: ignore[assignment,misc]
    _SENTRY_AVAILABLE = False


def init_sentry() -> bool:
    """Sentry SDK 를 초기화. 조건 미충족 시 no-op.

    조건:
      1. `sentry-sdk` 가 import 가능해야 함
      2. `settings.sentry_dsn` 이 비어있지 않아야 함

    Returns:
        True if Sentry was initialized, False otherwise.
    """
    if not _SENTRY_AVAILABLE:
        logger.info("Sentry disabled (sentry-sdk not installed)")
        return False
    if not (settings.sentry_dsn or "").strip():
        logger.info("Sentry disabled (SENTRY_DSN empty)")
        return False
    try:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.sentry_environment,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            integrations=[FastApiIntegration()],
        )
        logger.info("Sentry initialized (env=%s)", settings.sentry_environment)
        return True
    except Exception:  # noqa: BLE001 — sentry init 실패는 앱 가용성에 영향 주면 안 됨  # pylint: disable=broad-exception-caught
        logger.exception("Sentry init failed")
        return False
