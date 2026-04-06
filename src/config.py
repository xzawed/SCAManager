from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    database_url: str
    github_webhook_secret: str
    github_token: str
    telegram_bot_token: str
    telegram_chat_id: str
    anthropic_api_key: str = ""  # 빈 문자열이면 AI 리뷰 건너뜀
    api_key: str = ""  # 빈 문자열이면 인증 건너뜀

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("database_url")
    @classmethod
    def fix_postgres_url(cls, v: str) -> str:
        # SQLAlchemy 2.x는 'postgres://' 미지원, 'postgresql://'로 변환
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)
        # 비밀번호에 @ 포함 시 자동 인코딩
        # rpartition('@')로 마지막 @ 기준 분리 → 진짜 host 구분자
        scheme_creds, at, hostpath = v.rpartition('@')
        if at and '://' in scheme_creds:
            scheme, _, creds = scheme_creds.partition('//')
            if ':' in creds:
                user, _, password = creds.partition(':')
                password = password.replace('@', '%40')
                v = f"{scheme}//{user}:{password}@{hostpath}"
        # Supabase는 SSL 필수
        if 'supabase.co' in v and 'sslmode' not in v:
            v += '?sslmode=require'
        return v


settings = Settings()
