"""Application settings loaded from environment variables via pydantic-settings."""
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """Centralised configuration — all values read from environment / .env file."""
    database_url: str
    github_webhook_secret: str = ""   # 레거시 리포 fallback (optional)
    github_token: str = ""            # 레거시 리포 fallback (optional)
    telegram_bot_token: str
    telegram_chat_id: str
    anthropic_api_key: str = ""  # 빈 문자열이면 AI 리뷰 건너뜀
    api_key: str = ""  # 빈 문자열이면 인증 건너뜀
    github_client_id: str = ""
    github_client_secret: str = ""
    session_secret: str = "dev-secret-change-in-production"
    app_base_url: str = ""  # Railway 등 리버스 프록시 환경에서 HTTPS redirect_uri 강제 지정
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
        if not v:
            return v
        return cls._normalize_pg_url(v)


settings = Settings()
