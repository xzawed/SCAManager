"""SCAManager FastAPI application — entry point, lifespan, and router registration."""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

# 🔴 alembic 은 저장소 루트에 동명 패키지(`alembic/`)가 있어 pylint 가 first-party 로 본다.
# 서드파티 블록과 분리해 두어야 C0411(wrong-import-order)이 재발하지 않는다.
# pylint treats `alembic` as first-party (a local package shares the name); keep it separated.
from alembic import command
from alembic.config import Config

from src import scheduler
from src.config import settings
from src.logging_config import configure_logging
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

# 🔴 import 시점 설정 — 이후 모든 모듈 logger 의 INFO 가 실제로 출력된다.
# 미호출 시 Python last-resort 핸들러가 WARNING 이상만 내보내 앱 INFO 로그가 전부 소실된다
# (2026-07-19 발견: 출시 이래 `retention sweep — purged …` 등이 한 번도 보이지 않았음).
# Configure at import so every module logger's INFO actually emits.
configure_logging()

logger = logging.getLogger(__name__)

# `.env.example` / `config.py` 기본값과 동일한 개발용 세션 시크릿 — 운영에서 이 값이면 기동 차단.
# The dev-only session secret; if production still carries it, startup aborts.
_DEFAULT_SESSION_SECRET = "dev-secret-change-in-production"  # nosec B105


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
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response


def _run_migrations() -> None:
    """Run Alembic migrations to head."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


def _validate_startup_config() -> None:
    """프로덕션 시작 전 필수 설정 검증 — 위험 설정 시 RuntimeError 또는 경고 로그.

    Validate critical config before startup; raise RuntimeError or log a warning on risky settings.
    프로덕션(HTTPS) 판정은 APP_BASE_URL 기준. lifespan 에서 startup 직전 1회 호출.
    """
    is_prod_like = settings.is_production
    # 🔴 유효 모드를 startup 에 명시 로깅 — prod 하드닝이 무성 다운그레이드되지 않도록 가시화(#14).
    # 운영자가 Railway 로그에서 "production hardening = OFF"를 보면 오설정을 즉시 인지한다.
    # 🔴 Log the effective mode at startup so a silent prod→dev downgrade is visible (#14).
    logger.info(
        "startup: production hardening = %s (ENVIRONMENT=%s, APP_BASE_URL=%s)",
        "ON" if is_prod_like else "OFF",
        settings.environment or "(unset)",
        settings.app_base_url or "(unset)",
    )
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
    # P1-①: 비-empty 이지만 형식이 잘못된 키는 _get_fernet() 예외→silent 평문 fallback 을 유발한다.
    # startup 에서 Fernet 생성 가능 여부를 검증해, strict/prod 면 fail-fast (false assurance 차단).
    # P1-①: a non-empty but malformed key triggers a silent plaintext fallback in _get_fernet().
    # Validate it can build a Fernet here; under strict/prod, fail fast (close the false-assurance gap).
    token_key = settings.token_encryption_key
    if is_prod_like and isinstance(token_key, str) and token_key.strip():
        from cryptography.fernet import Fernet  # pylint: disable=import-outside-toplevel
        try:
            Fernet(token_key.strip().encode())
        except (ValueError, TypeError) as exc:
            invalid_msg = (
                "SECURITY: TOKEN_ENCRYPTION_KEY is set but is not a valid Fernet key "
                "(must be a 32-byte url-safe base64 key). Tokens would be stored in "
                "PLAINTEXT. Generate with: python -c \"from cryptography.fernet import "
                "Fernet; print(Fernet.generate_key().decode())\""
            )
            if settings.strict_token_encryption:
                logger.error("%s", invalid_msg)
                raise RuntimeError(
                    "TOKEN_ENCRYPTION_KEY is invalid when STRICT_TOKEN_ENCRYPTION=true"
                ) from exc
            logger.warning("%s", invalid_msg)
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
    if is_prod_like and not (settings.internal_cron_api_key or "").strip():
        # 🔴 INTERNAL_CRON_API_KEY 미설정 시 모든 스케줄 작업(주간 리포트·트렌드 경보·머지 재시도
        # sweep)이 503 으로 조용히 실패한다(internal_cron.py:42 — "Cron API key not configured").
        # railway.toml cron 의 curl 은 -f 없이 성공 종료해 운영자가 인지하기 어렵다 → startup 경고(#15).
        # 🔴 Without INTERNAL_CRON_API_KEY every scheduled job (weekly report, trend alert, merge-retry
        # sweep) fails silently with 503. Surface it at startup so the operator notices.
        logger.warning(
            "INTERNAL_CRON_API_KEY is not set in production — all scheduled cron jobs "
            "(weekly report, trend alert, merge-retry sweep) will return 503 and never run. "
            "Set INTERNAL_CRON_API_KEY to enable the /api/internal/cron/* endpoints."
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Run DB migrations on startup, then yield control to the application."""
    _validate_startup_config()
    try:
        await asyncio.wait_for(asyncio.to_thread(_run_migrations), timeout=30)
        logger.info("DB migration completed")
    except asyncio.TimeoutError as exc:
        logger.error("DB migration timed out after 30s")
        # P1-②: STRICT_MIGRATION=true 면 fail-fast — 마이그레이션 없는 stale 스키마로 서비스 차단.
        # P1-②: with STRICT_MIGRATION=true, fail fast instead of serving on a stale schema.
        if settings.strict_migration:
            raise RuntimeError(
                "DB migration timed out and STRICT_MIGRATION=true — refusing to start"
            ) from exc
        logger.error("starting app anyway (set STRICT_MIGRATION=true to fail fast)")
    except Exception as exc:  # pylint: disable=broad-exception-caught  # noqa: BLE001
        # Phase H PR-6A: logger.exception 으로 stack trace 보존
        # Railway 로그에서 마이그레이션 실패 원인 추적 가능
        # logger.exception preserves stack trace; Railway logs surface failure cause
        logger.exception("DB migration failed")
        # P1-②: STRICT_MIGRATION=true 면 fail-fast (온프레미스/비-Railway prod 의 fail-open 차단).
        # P1-②: with STRICT_MIGRATION=true, fail fast (closes the fail-open on non-Railway prod).
        if settings.strict_migration:
            raise RuntimeError(
                "DB migration failed and STRICT_MIGRATION=true — refusing to start"
            ) from exc
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

    # 🔴 인앱 주기 작업 스케줄러 기동 (2026-07-19 P0 — Railway cron 미실행 사고 대체).
    # railway.toml `[[deploy.cronJobs]]` 는 Railway 스키마에 없는 키라 조용히 무시됐고,
    # weekly/trend/retry/orphan/retention 5종이 한 번도 실행되지 않았다. 상세: src/scheduler.py
    # 운영(is_production)에서만 기동 — 테스트/로컬의 lifespan 은 태스크를 띄우지 않는다.
    # In-app scheduler replacing the Railway cron config that never ran; production-only.
    scheduler_tasks = scheduler.start(settings)

    try:
        yield
    finally:
        await scheduler.stop(scheduler_tasks)
        await close_http_client()


_is_prod = settings.is_production

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

# A4: CORS — APP_BASE_URL 기반 명시적 출처 허용 (allow_origins=["*"] 금지).
# 🔴 CORSMiddleware 는 반드시 마지막 add_middleware (outermost) — SonarCloud S8414.
# outermost 여야 preflight OPTIONS + CORS 헤더가 Session/RLS 등 inner 미들웨어의
# 인증·세션 거부 응답에도 적용된다 (CORS 가 inner 면 거부 응답에 CORS 헤더 누락).
# A4: CORS — explicit origin from APP_BASE_URL, never allow_origins=["*"].
# CORSMiddleware MUST be the last add_middleware (outermost) — SonarCloud S8414 — so that
# preflight + CORS headers apply even when inner middleware (Session/RLS) reject the request.
if settings.app_base_url:
    _CORS_ORIGIN = settings.app_base_url.rstrip("/")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[_CORS_ORIGIN],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
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
