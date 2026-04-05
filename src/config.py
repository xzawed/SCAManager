from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    github_webhook_secret: str
    github_token: str
    telegram_bot_token: str
    telegram_chat_id: str

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
