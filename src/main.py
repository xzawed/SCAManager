"""SCAManager FastAPI application — entry point, lifespan, and router registration."""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from alembic import command
from alembic.config import Config

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.config import settings
from src.constants import GITHUB_API
from src.middleware.rate_limiter import limiter
from src.shared.http_client import close_http_client, init_http_client
from src.webhook.router import router as webhook_router
from src.api.repos import router as api_repos_router
from src.api.repo_report import router as api_repo_report_router
from src.api.stats import router as api_stats_router
from src.api.hook import router as api_hook_router
from src.api.users import router as api_users_router
from src.api.internal_cron import router as api_internal_cron_router
from src.api.admin import router as api_admin_router
from src.api.issue_registration import router as issue_registration_router
from src.ui.routes.admin import router as ui_admin_router
from src.ui.router import router as ui_router
from src.auth.github import router as auth_router

logger = logging.getLogger(__name__)


class LimitBodySizeMiddleware(BaseHTTPMiddleware):  # pylint: disable=too-few-public-methods
    """요청 본문 크기를 제한한다 (DoS 방어).
    Limits request body size to prevent DoS via oversized payloads."""

    _MAX_BODY = 10 * 1024 * 1024  # 10 MB

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                body_size = int(content_length)
            except ValueError:
                # 비정형 Content-Length 헤더 — 500 전파 차단
                # Malformed Content-Length header — prevent 500 propagation
                return Response("Invalid Content-Length", status_code=400)
            if body_size > self._MAX_BODY:
                return Response("Request body too large", status_code=413)
        return await call_next(request)


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
        # S4: CSP — 외부 리소스 로드 차단. script/style 'unsafe-inline' 은 HTMX + 인라인
        # IIFE 스크립트 지원을 위해 허용 (nonce 기반 strict CSP는 향후 개선 목표).
        # S4: CSP — blocks external resource loading. 'unsafe-inline' for script/style
        # is required to support HTMX and inline IIFE scripts (nonce-based strict
        # CSP is a future improvement goal).
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "connect-src 'self'; "
            "font-src 'self' data:; "
            "frame-ancestors 'none';"
        )
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
    is_prod_like = settings.app_base_url.startswith("https")
    _DEFAULT_SESSION_SECRET = "dev-secret-change-in-production"  # nosec B105
    if settings.session_secret == _DEFAULT_SESSION_SECRET:  # nosec B105
        if is_prod_like:
            # S2: 프로덕션(HTTPS)에서 공개 기본값 사용 금지 — 세션 위조 가능
            # S2: Refuse to start in production with a publicly-known session secret
            raise RuntimeError(
                "SESSION_SECRET must be changed in production — "
                "the default value is publicly known and allows session forgery. "
                "Set SESSION_SECRET to a random string of 32+ characters."
            )
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
    if is_prod_like and not (settings.telegram_webhook_secret or "").strip():
        # Telegram webhook 시크릿 미설정 시 /webhooks/telegram 인증이 완전히 우회됨.
        # When TELEGRAM_WEBHOOK_SECRET is not set, /webhooks/telegram auth is bypassed entirely.
        logger.warning(
            "SECURITY: TELEGRAM_WEBHOOK_SECRET is not set in production "
            "(APP_BASE_URL=%s). The /webhooks/telegram endpoint will accept "
            "requests without authentication. Set TELEGRAM_WEBHOOK_SECRET to "
            "the value configured in your Telegram bot's webhook settings.",
            settings.app_base_url,
        )
    try:
        await asyncio.wait_for(asyncio.to_thread(_run_migrations), timeout=30)
        logger.info("DB migration completed")
    except asyncio.TimeoutError:
        logger.error("DB migration timed out after 30s — starting app anyway")
    except Exception:  # pylint: disable=broad-exception-caught  # noqa: BLE001
        # Phase H PR-6A: logger.exception 으로 stack trace 보존
        # Railway 로그에서 마이그레이션 실패 원인 추적 가능
        # logger.exception preserves stack trace; Railway logs surface failure cause
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
        await warmup_client.get(f"{GITHUB_API}/zen", timeout=3.0)
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
# slowapi rate limiting 등록 — IP 기반 60req/min (API 엔드포인트 DoS 방어)
# Register slowapi rate limiting — IP-based 60 req/min (DoS defense for API endpoints)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(LimitBodySizeMiddleware)
# A4: CORS — APP_BASE_URL 기반 명시적 출처 허용 (allow_origins=["*"] 금지)
# A4: CORS — explicit origin from APP_BASE_URL, never allow_origins=["*"]
if settings.app_base_url:
    _origin = settings.app_base_url.rstrip("/")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
# Phase 3 postlude — RLS 운영 활성화 미들웨어. Starlette LIFO 미들웨어 스택:
# add_middleware 마지막 호출이 outer (request 먼저 처리). 원하는 흐름 = SessionMiddleware → RLSSessionMiddleware → route
# 따라서 RLS 먼저 등록 (inner), SessionMiddleware 나중 등록 (outer — RLS 보다 먼저 호출).
# Phase 3 postlude — RLS runtime activation. Starlette LIFO middleware stack:
# Last add_middleware becomes outer (called first). Desired flow: SessionMiddleware → RLSSessionMiddleware → route
# Therefore register RLS first (inner) so that SessionMiddleware (outer) populates session before RLS reads it.
# alembic 0026 RLS policy + database.py event listener 페어 — 본 미들웨어 부재 시
# RLS = "deny-all + legacy admin only 모드" 동작 (운영 사고 위험).
from src.middleware.rls_session import RLSSessionMiddleware  # noqa: E402  # pylint: disable=wrong-import-position
# Phase 1 PR-1b — i18n LocaleMiddleware (다국어 지원 인프라)
# locale 감지 → scope["state"]["locale"] 주입. 사용자 명시 선택 (Cookie) > Accept-Language > default.
# Detect locale → inject scope["state"]["locale"]. User explicit (Cookie) > Accept-Language > default.
# LIFO 등록 = SessionMiddleware (outer) → LocaleMiddleware (inner) — locale 은 session 무관 영역
# LIFO order = SessionMiddleware (outer) → LocaleMiddleware (inner) — locale doesn't depend on session
from src.middleware.locale import LocaleMiddleware  # noqa: E402  # pylint: disable=wrong-import-position

app.add_middleware(LocaleMiddleware)
app.add_middleware(RLSSessionMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    https_only=_is_prod,
    same_site="lax",
    max_age=60 * 60 * 24 * 7,  # 7 days
)


# 정적 파일 캐시 — 버전 해시 없는 URL(`/static/js/effects.js` 등)이라 immutable 장기 캐시 금지.
# immutable+1년은 배포 후에도 브라우저가 구 캐시본을 최대 1년 서빙 → JS/CSS 수정이 재방문 사용자에게
# 도달 못 하는 stale 사고(2026-06-18, count-up "0/100" fix 라이브 미반영). `no-cache`(ETag 재검증)로
# 변경 시 즉시 전파 — 미변경 시 304(본문 재다운로드 없음, 대역폭 보존). 무버전 자산의 표준 패턴.
# Static cache — un-versioned URLs, so NO immutable long cache (it served stale JS/CSS for up to a year
# after deploy — 2026-06-18 incident). `no-cache` revalidates via ETag: fresh on change, 304 (no
# re-download) when unchanged. Set on 200 + 304 so the directive persists on the cached entry.
class CachedStaticFiles(StaticFiles):
    """정적 응답에 `no-cache`(ETag 재검증) Cache-Control 을 붙인다 — 무버전 자산 stale 방지.
    Adds `no-cache` (ETag-revalidating) Cache-Control so un-versioned static assets never go stale."""

    async def get_response(self, path: str, scope: Any) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code in (200, 304):
            response.headers["cache-control"] = "no-cache"
        return response


# Step C (UI 감사): Chart.js vendoring 정적 마운트 — CDN 차단/오프라인 시 빈 차트 회피
# Step C: vendored Chart.js for offline/CDN-blocked environments (avoid empty chart frames)
_STATIC_DIR = Path(__file__).resolve().parent / "static"
if _STATIC_DIR.exists():
    app.mount("/static", CachedStaticFiles(directory=str(_STATIC_DIR)), name="static")

app.include_router(auth_router)
app.include_router(webhook_router)
app.include_router(api_repos_router)
app.include_router(api_repo_report_router)
app.include_router(api_stats_router)
app.include_router(api_hook_router)
app.include_router(api_users_router)
app.include_router(api_internal_cron_router)
app.include_router(api_admin_router)
app.include_router(issue_registration_router)
app.include_router(ui_admin_router)
app.include_router(ui_router)


@app.get("/health")
def health():
    """Liveness probe — Railway/infra 헬스체크용. 내부 구현 세부사항은 노출하지 않는다.
    Liveness probe for Railway/infra health checks. Does not expose implementation details."""
    return {"status": "ok"}
