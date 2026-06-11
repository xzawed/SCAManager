"""Application settings loaded from environment variables via pydantic-settings."""
import logging
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, model_validator
from src.constants import MERGE_VERIFIER_BAND_DEFAULT

logger = logging.getLogger(__name__)

_SESSION_SECRET_MIN_LEN = 32  # 보안 권고: 32자 이상


class Settings(BaseSettings):
    """Centralised configuration — all values read from environment / .env file."""
    database_url: str
    github_webhook_secret: str = ""   # 레거시 리포 fallback (optional)
    github_token: str = ""            # 레거시 리포 fallback (optional)
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_webhook_secret: str = ""  # Telegram setWebhook secret_token — 설정 시 헤더 검증
    anthropic_api_key: str = ""  # 빈 문자열이면 AI 리뷰 건너뜀
    # 머지 검증자 (2nd-LLM) — 빈 키면 비활성(비용 0, 동작 변화 0)
    # Merge verifier (2nd-LLM) — empty key disables it (zero cost, zero behavior change)
    openai_api_key: str = ""
    openai_verifier_model: str = "gpt-5-mini"  # 저비용 소형 — 구현 시 최신 저가 모델로 확정/오버라이드
    # Low-cost small model — confirm/override with latest cheap model at implementation time
    # 경계 밴드 폭(점) — >= 1 강제 (0/음수면 모든 score 가 밴드 밖 = 검증 silent 무효화 방지)
    # Band width in points — enforce >= 1 (0/negative would silently disable verification while key set)
    merge_verifier_band: int = Field(default=MERGE_VERIFIER_BAND_DEFAULT, ge=1)
    claude_review_model: str = "claude-sonnet-4-6"  # AI 코드리뷰 모델 (환경변수 CLAUDE_REVIEW_MODEL로 오버라이드)
    # Phase 2 d-🅓 (사이클 74) — Insight narrative 영역 한정 모델 (default Haiku — 67% 비용 절감)
    # AI 리뷰 (review_code) 는 claude_review_model (Sonnet) 보존 — 명시 제외 영역 (메모리 feedback-ai-review-quality-protect.md)
    # Phase 2 d-🅓 (Cycle 74) — model for Insight narrative only (default Haiku — 67% cheaper).
    # AI review (review_code) keeps Sonnet (memory feedback-ai-review-quality-protect.md exclusion).
    claude_insight_model: str = "claude-haiku-4-5"
    # 운영 opt-out — Anthropic prompt caching (5분 ephemeral) 비활성화 (default-on)
    # Operational opt-out — disables Anthropic prompt caching (default-on, 5-min ephemeral)
    disable_prompt_cache: bool = False
    api_key: str = ""  # 빈 문자열이면 인증 건너뜀
    internal_cron_api_key: str = ""  # 내부 cron 엔드포인트 전용 키 (admin api_key와 분리)
    # Internal cron endpoint key — separate from admin api_key
    github_client_id: str = ""
    github_client_secret: str = ""
    session_secret: str = "dev-secret-change-in-production"
    app_base_url: str = ""  # Railway 등 리버스 프록시 환경에서 HTTPS redirect_uri 강제 지정
    # GitHub OAuth 토큰 Fernet 암호화 키 (없으면 평문 저장 — 운영환경 필수 설정)
    # 생성: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    token_encryption_key: str = ""
    # 강한 모드 (Phase 2): True 면 prod (HTTPS) 환경에서 token_encryption_key 미설정 시
    # lifespan startup 차단. False(기본) 는 backwards compatible warning 만 출력.
    # Strict mode (Phase 2): when True, refuses to start in prod (HTTPS) without
    # a token_encryption_key. Defaults to False for backwards-compatible warnings.
    strict_token_encryption: bool = False
    n8n_webhook_secret: str = ""  # n8n 전송 HMAC 서명 시크릿 (빈 문자열이면 서명 생략)
    # n8n issue 릴레이에 GitHub repo 토큰 포함 여부 — 명시적 opt-in (default off, 자격증명 유출 차단)
    # Whether to include the GitHub repo token in the n8n issue relay — explicit opt-in (default off)
    n8n_relay_repo_token: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    # DB 연결 설정 (온프레미스 PostgreSQL 지원)
    db_sslmode: str = ""        # "require", "verify-full" 등 (빈 문자열=미적용)
    db_force_ipv4: bool = False  # True=Railway IPv4 강제 (온프레미스에서는 False)
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30   # seconds
    db_pool_recycle: int = 1800  # seconds
    # DB Failover 설정 (빈 문자열이면 failover 비활성)
    database_url_fallback: str = ""
    db_failover_probe_interval: int = 30  # Primary 복구 확인 주기(초)
    # background 전용 DB URL — RLS role 분리 옵션 A (rls-role-separation.md Phase 2)
    # 빈 문자열이면 DATABASE_URL 팩토리 재사용 (현행 동작 보존)
    # Background-only DB URL — RLS role separation Option A (Phase 2).
    # Empty string reuses the DATABASE_URL factory (preserves current behavior).
    database_url_worker: str = ""
    # Auto-merge unknown 상태 재시도 (Phase F Quick Win) — 운영 중 튜닝용
    merge_unknown_retry_limit: int = 3        # 기본 3회
    merge_unknown_retry_delay: float = 3.0    # 기본 3초 간격 (총 최대 9초)
    # 자기 분석 무한 루프 킬 스위치 — True 시 모든 webhook 분석 skip (Phase 9)
    # Kill-switch to disable self-analysis entirely — skips all webhook pipeline (Phase 9)
    scamanager_self_analysis_disabled: bool = False
    # Cycle 79 PR 2 — SaaS admin allow-list (CSV email 형식)
    # 빈 문자열 = admin 영역 비활성 (모든 admin 엔드포인트 503 반환)
    # 명시 = ',' 분리 email allow-list — `current_user.email in saas_admin_emails`
    # Cycle 79 PR 2 — SaaS admin allow-list (CSV email format)
    # Empty = admin area disabled (all admin endpoints return 503)
    # Set = comma-separated email allow-list — `current_user.email in saas_admin_emails`
    saas_admin_emails: str = ""
    # Phase 12: CI-aware Auto Merge 재시도 설정
    # Phase 12: CI-aware Auto Merge retry configuration
    # False 시 레거시 단일 시도 동작 / False falls back to legacy single-attempt behavior
    merge_retry_enabled: bool = True
    # 큐 행당 최대 재시도 횟수 (>= 1 — 0·음수 시 재시도 즉시 terminal)
    # Maximum retry attempts per queue row (>= 1 — 0/negative makes retries immediately terminal)
    merge_retry_max_attempts: int = Field(default=30, ge=1)
    # 큐 행 만료 시간 (시간, >= 1 — 0 시 즉시 만료)
    # Queue row expiry time in hours (>= 1 — 0 expires instantly)
    merge_retry_max_age_hours: int = Field(default=24, ge=1)
    # 첫 재시도 백오프 (초, >= 1 — 0·음수 시 백오프 소멸)
    # Initial retry backoff in seconds (>= 1 — 0/negative removes backoff)
    merge_retry_initial_backoff_seconds: int = Field(default=60, ge=1)
    # 최대 백오프 (초, >= 1, initial 이상 — model_validator 로 경계 강제)
    # Maximum retry backoff in seconds (>= 1, >= initial — enforced by model_validator)
    merge_retry_max_backoff_seconds: int = Field(default=600, ge=1)
    # check_suite 웹훅 활성화 / Enable check_suite webhook
    merge_retry_check_suite_webhook_enabled: bool = True
    # cron sweep 1회 처리 최대 행 수 (>= 1 — 0 시 sweep 무처리)
    # Max rows per cron sweep (>= 1 — 0 processes nothing)
    merge_retry_worker_batch_size: int = Field(default=50, ge=1)

    # Phase 1 PR-1a (사이클 84 — 다국어 지원 i18n 인프라)
    # 다국어 지원 (영어/한국어/일본어) — 5 환경변수 + I18N_DISABLED kill-switch
    # Phase 1 PR-1a (Cycle 84 — i18n infrastructure for multilingual support)
    # Multilingual support (English/Korean/Japanese) — 5 env vars + I18N_DISABLED kill-switch
    default_locale: str = "en"
    # 신규 사용자 기본 언어 (User.preferred_language 초기값 — alembic 0030 페어)
    # Default locale for new users (initial value for User.preferred_language — alembic 0030 pair)

    supported_locales: str = "en,ko,ja"
    # 지원 언어 목록 (쉼표 구분, 공백 제거 의무 — field_validator 정규화)
    # Supported language codes (comma-separated, whitespace stripped — field_validator normalized)

    locale_fallback: str = "en"
    # 모든 감지 실패 시 극한 fallback (번역 파일 미존재 / 미지원 locale 등)
    # Ultimate fallback when all detection fails (missing translation file / unsupported locale)

    i18n_translations_dir: str = "src/i18n/translations"
    # Babel + Jinja2 i18n 번역 파일 위치 (상대 또는 절대 경로)
    # Path to Babel + Jinja2 i18n translation files (relative or absolute)

    i18n_disabled: bool = False
    # i18n 기능 kill-switch — `I18N_DISABLED=1` 시 LocaleMiddleware skip + 영문 hardcoded fallback
    # i18n feature kill-switch — `I18N_DISABLED=1` skips LocaleMiddleware + English hardcoded fallback
    # 운영 사고 시 즉각 비활성 default — 사이클 78 NEW-P0-2 패턴 페어 (`is_disabled("I18N")`)
    # Operational incident response — pairs with Cycle 78 NEW-P0-2 pattern (`is_disabled("I18N")`)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @staticmethod
    def _normalize_pg_url(v: str) -> str:
        """postgres:// → postgresql:// 변환 + Supabase SSL 자동 추가."""
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)
        if 'supabase.co' in v and 'sslmode' not in v:
            v += '?sslmode=require'
        return v

    @field_validator("session_secret")
    @classmethod
    def validate_session_secret(cls, v: str) -> str:
        """SESSION_SECRET 유효성 검사.

        - 기본값 사용 시: 보안 경고 로그만 출력 (개발 환경 호환)
        - 커스텀 값이지만 32자 미만: ValueError 발생 (배포 전 실수 방지)
        """
        _default = "dev-secret-change-in-production"
        if v == _default:
            logger.warning(
                "SECURITY: SESSION_SECRET is using the default value. "
                "Set a strong random secret (>= %d chars) in production!",
                _SESSION_SECRET_MIN_LEN,
            )
            return v
        if len(v) < _SESSION_SECRET_MIN_LEN:
            raise ValueError(
                f"SESSION_SECRET must be at least {_SESSION_SECRET_MIN_LEN} characters long "
                f"(current: {len(v)} chars). "
                f"Generate one with: openssl rand -hex 32"
            )
        return v

    @field_validator("smtp_port", mode="before")
    @classmethod
    def coerce_smtp_port(cls, v: object) -> object:
        """Railway에서 SMTP_PORT=""(빈 문자열)로 설정된 경우 기본값 587로 대체."""
        if v == "" or v is None:
            return 587
        return v

    @field_validator("database_url")
    @classmethod
    def fix_postgres_url(cls, v: str) -> str:
        """DATABASE_URL의 postgres:// 스킴을 postgresql://로 변환한다."""
        return cls._normalize_pg_url(v)

    @field_validator("database_url_fallback")
    @classmethod
    def fix_fallback_url(cls, v: str) -> str:
        """DATABASE_URL_FALLBACK의 postgres:// 스킴을 postgresql://로 변환한다."""
        if not v:
            return v
        return cls._normalize_pg_url(v)

    @field_validator("database_url_worker")
    @classmethod
    def fix_worker_url(cls, v: str) -> str:
        """DATABASE_URL_WORKER의 postgres:// 스킴을 postgresql://로 변환한다.
        Normalize the postgres:// scheme of DATABASE_URL_WORKER to postgresql://."""
        if not v:
            return v
        return cls._normalize_pg_url(v)

    @model_validator(mode="after")
    def _validate_retry_backoff_bounds(self) -> "Settings":
        """최대 백오프는 초기 백오프 이상이어야 한다 (지수 백오프 단조성 보장).
        Max backoff must be >= initial backoff (preserves exponential backoff monotonicity).

        max < initial 이면 compute_next_retry_at 의 min(initial*2^n, max) 가 항상 max 로
        capped 되어 백오프 증가가 소멸한다 (retry_policy.py compute_next_retry_at 페어).
        If max < initial, compute_next_retry_at's min(initial*2^n, max) is always capped at max,
        so the intended growth disappears (paired with retry_policy.py compute_next_retry_at).
        """
        if self.merge_retry_max_backoff_seconds < self.merge_retry_initial_backoff_seconds:
            raise ValueError(
                "merge_retry_max_backoff_seconds "
                f"({self.merge_retry_max_backoff_seconds}) must be >= "
                "merge_retry_initial_backoff_seconds "
                f"({self.merge_retry_initial_backoff_seconds})"
            )
        return self

    # Phase 1 PR-1a — i18n 환경변수 4 field_validator (사이클 84)
    # i18n env var validators (Cycle 84)

    @field_validator("supported_locales")
    @classmethod
    def validate_supported_locales(cls, v: str) -> str:
        """SUPPORTED_LOCALES 유효성 검사 + 정규화.

        - 쉼표 구분 + 공백 제거
        - 최소 1개 언어 코드 의무
        - 각 코드 = 2~10 자 영숫자/하이픈 (ISO 639-1/BCP 47 호환)

        Validate and normalize SUPPORTED_LOCALES.
        - Comma-separated, whitespace stripped
        - At least one language code required
        - Each code = 2~10 chars alphanumeric/hyphen (ISO 639-1/BCP 47)
        """
        if not v or not v.strip():
            raise ValueError(
                "SUPPORTED_LOCALES must not be empty. "
                "Set at least one language code (e.g., 'en,ko,ja')"
            )
        langs = [lang.strip() for lang in v.split(",")]
        langs = [lang for lang in langs if lang and " " not in lang]
        if not langs:
            raise ValueError(
                "SUPPORTED_LOCALES must contain at least one non-empty language code"
            )
        for lang in langs:
            if not 2 <= len(lang) <= 10:
                raise ValueError(
                    f"Language code '{lang}' must be 2~10 characters "
                    "(e.g., 'en', 'ko', 'zh-Hans')"
                )
            if not all(c.isalnum() or c == "-" for c in lang):
                raise ValueError(
                    f"Language code '{lang}' must contain only alphanumeric "
                    "characters and hyphens"
                )
        return ",".join(langs)

    @field_validator("default_locale")
    @classmethod
    def validate_default_locale(cls, v: str) -> str:
        """DEFAULT_LOCALE 유효성 검사 + 좌우 공백 제거.

        Validate DEFAULT_LOCALE — strip and validate format.
        """
        if not v or not v.strip():
            raise ValueError(
                "DEFAULT_LOCALE must not be empty. "
                "Set a valid language code (e.g., 'en', 'ko')"
            )
        v = v.strip()
        if not 2 <= len(v) <= 10:
            raise ValueError(
                f"DEFAULT_LOCALE '{v}' must be 2~10 characters"
            )
        if not all(c.isalnum() or c == "-" for c in v):
            raise ValueError(
                f"DEFAULT_LOCALE '{v}' must contain only alphanumeric "
                "characters and hyphens"
            )
        return v

    @field_validator("locale_fallback")
    @classmethod
    def validate_locale_fallback(cls, v: str) -> str:
        """LOCALE_FALLBACK 유효성 검사 — 극한 fallback 영역 (특히 신중).

        Validate LOCALE_FALLBACK — ultimate fallback (handle with care).
        """
        if not v or not v.strip():
            raise ValueError(
                "LOCALE_FALLBACK must not be empty. "
                "Set a valid language code (e.g., 'en')"
            )
        v = v.strip()
        if not 2 <= len(v) <= 10:
            raise ValueError(
                f"LOCALE_FALLBACK '{v}' must be 2~10 characters"
            )
        if not all(c.isalnum() or c == "-" for c in v):
            raise ValueError(
                f"LOCALE_FALLBACK '{v}' must contain only alphanumeric "
                "characters and hyphens"
            )
        return v


settings = Settings()
