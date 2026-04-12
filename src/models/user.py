"""User ORM 모델 — GitHub OAuth 인증 사용자 정보."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from src.database import Base


class User(Base):
    """GitHub OAuth 로그인 사용자 테이블."""

    __tablename__ = "users"

    id                  = Column(Integer, primary_key=True, index=True)
    github_id           = Column(String, unique=True, nullable=False, index=True)
    github_login        = Column(String, nullable=True)
    github_access_token = Column(String, nullable=True)  # Fernet 암호화 저장
    email               = Column(String, unique=True, nullable=False)
    display_name        = Column(String, nullable=False)
    created_at          = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    repositories = relationship("Repository", back_populates="owner")

    @property
    def plaintext_token(self) -> str:
        """DB에 암호화 저장된 GitHub 액세스 토큰을 복호화하여 반환.

        TOKEN_ENCRYPTION_KEY 미설정 시 평문 그대로 반환(하위 호환).
        """
        from src.crypto import decrypt_token  # pylint: disable=import-outside-toplevel
        return decrypt_token(self.github_access_token or "")
