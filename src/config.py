from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @field_validator("database_url")
    @classmethod
    def fix_postgres_url(cls, v: str) -> str:
        # SQLAlchemy 2.x는 'postgres://' 미지원, 'postgresql://'로 변환
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)
        # Supabase는 SSL 필수
        if 'supabase.co' in v and 'sslmode' not in v:
            v += '?sslmode=require'
        return v


settings = Settings()
