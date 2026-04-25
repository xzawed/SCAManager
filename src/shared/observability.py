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


def _before_send(event: dict, _hint: dict) -> dict:
    """Sentry 이벤트 전송 전 민감 데이터 스크러빙 — PII/secret 누수 방어.

    GitHub webhook 처리 중 발생한 예외는 request body·URL query·headers 에
    토큰/시크릿/사용자 입력이 포함될 수 있다. Sentry 기본 수집 범위를 명시적으로
    제한해 외부 SaaS 에 민감 정보가 유출되지 않도록 한다.
    """
    request = event.get("request") or {}
    # URL query string 제거 — ?token=xxx, ?api_key=yyy 등 유출 방지
    url = request.get("url")
    if isinstance(url, str) and "?" in url:
        request["url"] = url.split("?", 1)[0]
    # Cookies 제거 — 세션 쿠키가 그대로 Sentry 에 가는 것 방어
    if "cookies" in request:
        request["cookies"] = {}
    # Authorization 헤더 등 민감 헤더 제거
    headers = request.get("headers") or {}
    if isinstance(headers, dict):
        for key in list(headers.keys()):
            if key.lower() in ("authorization", "x-api-key", "x-hub-signature-256", "cookie"):
                headers[key] = "[Filtered]"
    event["request"] = request
    # body 는 Sentry 기본값이 이미 제외하지만 명시적으로 제거
    # Body is excluded by Sentry's defaults, but removed explicitly for defence in depth.
    if "data" in request:
        request["data"] = "[Filtered]"
    return event


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
            before_send=_before_send,  # PII/secret 스크러빙
            send_default_pii=False,    # 기본값이지만 명시적 방어
        )
        logger.info("Sentry initialized (env=%s)", settings.sentry_environment)
        return True
    except Exception:  # noqa: BLE001 — sentry init 실패는 앱 가용성에 영향 주면 안 됨  # pylint: disable=broad-exception-caught
        logger.exception("Sentry init failed")
        return False
