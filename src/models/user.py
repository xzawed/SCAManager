"""User ORM 모델 — GitHub OAuth 인증 사용자 정보.
User ORM model — GitHub OAuth authenticated user information.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from src.database import Base


# pylint: disable=too-few-public-methods
class User(Base):
    """GitHub OAuth 로그인 사용자 테이블.
    Table for GitHub OAuth logged-in users.
    """

    __tablename__ = "users"

    id                  = Column(Integer, primary_key=True, index=True)
    github_id           = Column(String, unique=True, nullable=False, index=True)
    github_login        = Column(String, nullable=True)
    # Fernet 암호화 저장 — Stored with Fernet encryption.
    github_access_token = Column(String, nullable=True)
    email               = Column(String, unique=True, nullable=False)
    display_name        = Column(String, nullable=False)
    created_at          = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Telegram 연동 컬럼 — Telegram integration columns.
    # telegram_user_id: Telegram 사용자 고유 ID (연동 완료 시 설정)
    # telegram_user_id: Telegram user unique ID (set upon successful linking).
    telegram_user_id      = Column(String, nullable=True, unique=True)
    # telegram_otp: 연동 인증용 일회용 패스코드
    # telegram_otp: One-time passcode for Telegram account linking.
    telegram_otp          = Column(String, nullable=True)
    # telegram_otp_expires_at: OTP 만료 시각 (타임존 포함)
    # telegram_otp_expires_at: OTP expiry timestamp with timezone.
    telegram_otp_expires_at = Column(DateTime(timezone=True), nullable=True)

    repositories = relationship("Repository", back_populates="owner")

    @property
    def plaintext_token(self) -> str:
        """DB에 암호화 저장된 GitHub 액세스 토큰을 복호화하여 반환.
        Decrypts and returns the GitHub access token stored encrypted in DB.

        TOKEN_ENCRYPTION_KEY 미설정 시 평문 그대로 반환(하위 호환).
        Falls back to plaintext when TOKEN_ENCRYPTION_KEY is not set (backward-compat).
        """
        from src.crypto import decrypt_token  # pylint: disable=import-outside-toplevel
        return decrypt_token(self.github_access_token or "")

    @property
    def is_telegram_connected(self) -> bool:
        """Telegram 연동 여부를 반환한다.
        Returns True when this user has a linked Telegram account.
        """
        return self.telegram_user_id is not None
