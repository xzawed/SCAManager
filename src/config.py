from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    database_url: str
    github_webhook_secret: str
    github_token: str
    telegram_bot_token: str
    telegram_chat_id: str
    anthropic_api_key: str = ""  # 빈 문자열이면 AI 리뷰 건너뜀

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("database_url")
    @classmethod
    def fix_postgres_url(cls, v: str) -> str:
        # SQLAlchemy 2.x는 'postgres://' 미지원, 'postgresql://'로 변환
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v


settings = Settings()
