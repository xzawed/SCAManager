"""Application settings loaded from environment variables via pydantic-settings."""
import logging
from pydantic_settings import BaseSettings
from pydantic import field_validator

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
    claude_review_model: str = "claude-sonnet-4-6"  # AI 코드리뷰 모델 (환경변수 CLAUDE_REVIEW_MODEL로 오버라이드)
    api_key: str = ""  # 빈 문자열이면 인증 건너뜀
    github_client_id: str = ""
    github_client_secret: str = ""
    session_secret: str = "dev-secret-change-in-production"
    app_base_url: str = ""  # Railway 등 리버스 프록시 환경에서 HTTPS redirect_uri 강제 지정
    # GitHub OAuth 토큰 Fernet 암호화 키 (없으면 평문 저장 — 운영환경 필수 설정)
    # 생성: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    token_encryption_key: str = ""
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
        return cls._normalize_pg_url(v)

    @field_validator("database_url_fallback")
    @classmethod
    def fix_fallback_url(cls, v: str) -> str:
        """DATABASE_URL_FALLBACK의 postgres:// 스킴을 postgresql://로 변환한다."""
        if not v:
            return v
        return cls._normalize_pg_url(v)


settings = Settings()
