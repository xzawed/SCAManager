"""SCAManager FastAPI application — entry point, lifespan, and router registration."""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from alembic import command
from alembic.config import Config

from src.config import settings
from src.shared.http_client import close_http_client, init_http_client
from src.shared.observability import init_sentry
from src.webhook.router import router as webhook_router
from src.api.repos import router as api_repos_router
from src.api.stats import router as api_stats_router
from src.api.hook import router as api_hook_router
from src.api.users import router as api_users_router
from src.api.internal_cron import router as api_internal_cron_router
from src.api.insights import router as api_insights_router
from src.ui.router import router as ui_router
from src.auth.github import router as auth_router

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):  # pylint: disable=too-few-public-methods
    """보안 응답 헤더를 모든 응답에 추가한다.
    Adds security response headers to all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if settings.app_base_url.startswith("https"):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response


def _run_migrations() -> None:
    """Run Alembic migrations to head."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Run DB migrations on startup, then yield control to the application."""
    if settings.session_secret == "dev-secret-change-in-production":
        logger.warning(
            "SESSION_SECRET is using the default insecure value — "
            "set SESSION_SECRET environment variable in production!"
        )
    if not (settings.anthropic_api_key or "").strip():
        logger.warning(
            "ANTHROPIC_API_KEY is empty — AI 리뷰가 비활성화됩니다. "
            "모든 분석이 기본값(89/B)으로 fallback 됩니다. "
            "Railway Variables 또는 .env 에 키를 설정하세요."
        )
    is_prod_like = settings.app_base_url.startswith("https")
    if is_prod_like and not (settings.token_encryption_key or "").strip():
        # Phase 2 — opt-in fail-fast: 14-에이전트 감사에서 P1 보안 위험으로 식별
        # (DB 유출 시 모든 GitHub OAuth token + Railway API token 평문 노출).
        # 기본값은 backwards compatible warning 유지. 운영자가 명시적으로
        # `STRICT_TOKEN_ENCRYPTION=true` 설정 시 lifespan startup 차단.
        # Phase 2 — opt-in fail-fast: flagged P1 by the 14-agent audit (DB leak
        # would expose every OAuth token in plaintext). Default behavior keeps
        # the legacy warning for backwards compatibility; setting
        # `STRICT_TOKEN_ENCRYPTION=true` makes lifespan startup abort instead.
        warning_msg = (
            "SECURITY: TOKEN_ENCRYPTION_KEY is not set in production "
            f"(APP_BASE_URL={settings.app_base_url}). GitHub OAuth tokens will be "
            "stored in plaintext. Generate with: python -c \"from cryptography.fernet "
            "import Fernet; print(Fernet.generate_key().decode())\""
        )
        if settings.strict_token_encryption:
            logger.error(
                "STRICT_TOKEN_ENCRYPTION=true and TOKEN_ENCRYPTION_KEY is missing — "
                "refusing to start. %s", warning_msg,
            )
            raise RuntimeError(
                "TOKEN_ENCRYPTION_KEY required when STRICT_TOKEN_ENCRYPTION=true"
            )
        logger.warning("%s", warning_msg)
    init_sentry()  # Sentry SDK — SENTRY_DSN 설정 시만 활성
    try:
        await asyncio.wait_for(asyncio.to_thread(_run_migrations), timeout=30)
        logger.info("DB migration completed")
    except asyncio.TimeoutError:
        logger.error("DB migration timed out after 30s — starting app anyway")
    except Exception:  # pylint: disable=broad-exception-caught  # noqa: BLE001
        # Phase H PR-6A: logger.exception 으로 stack trace 보존
        # Sentry/Railway 로그에서 마이그레이션 실패 원인 추적 가능
        logger.exception("DB migration failed")
    await init_http_client()

    # Phase 2 — GitHub API warm-up ping. PR #105 silent skip 사고 분석에서 cold
    # start 의 첫 요청 PyGithub Auth + DNS resolve + TLS handshake 지연이 실패
    # vector 의 일부로 식별됨. lifespan startup 마지막에 무해한 zen API 1회
    # 호출로 connection pool / DNS 캐시 워밍업. 실패는 silent — best-effort.
    # Phase 2 — GitHub API warm-up ping. The PR #105 silent-skip post-mortem
    # flagged the first-request PyGithub auth + DNS + TLS as part of the failure
    # vector. A harmless `/zen` GET pre-warms the pool. Failures are ignored.
    try:
        from src.shared.http_client import get_http_client  # pylint: disable=import-outside-toplevel
        warmup_client = get_http_client()
        await warmup_client.get("https://api.github.com/zen", timeout=3.0)
        logger.info("GitHub API warm-up ping succeeded")
    except Exception as warmup_exc:  # pylint: disable=broad-exception-caught
        logger.info("GitHub API warm-up ping skipped: %s", type(warmup_exc).__name__)

    try:
        yield
    finally:
        await close_http_client()


_is_prod = settings.app_base_url.startswith("https")

app = FastAPI(
    title="SCAManager",
    version="0.1.0",
    lifespan=lifespan,
    # /docs, /redoc 프로덕션 환경에서 비활성화 — API 구조 정보 노출 방지
    # Disable /docs and /redoc in production to prevent API structure disclosure.
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    https_only=_is_prod,
    same_site="lax",
    max_age=60 * 60 * 24 * 7,  # 7 days
)
# Step C (UI 감사): Chart.js vendoring 정적 마운트 — CDN 차단/오프라인 시 빈 차트 회피
# Step C: vendored Chart.js for offline/CDN-blocked environments (avoid empty chart frames)
_STATIC_DIR = Path(__file__).resolve().parent / "static"
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

app.include_router(auth_router)
app.include_router(webhook_router)
app.include_router(api_repos_router)
app.include_router(api_stats_router)
app.include_router(api_hook_router)
app.include_router(api_users_router)
app.include_router(api_internal_cron_router)
app.include_router(api_insights_router)
app.include_router(ui_router)


@app.get("/health")
def health():
    """Liveness probe — Railway/infra 헬스체크용. 내부 구현 세부사항은 노출하지 않는다.
    Liveness probe for Railway/infra health checks. Does not expose implementation details."""
    return {"status": "ok"}
