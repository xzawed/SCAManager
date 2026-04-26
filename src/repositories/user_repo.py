"""UserRepo — User ORM 쿼리 단일 출처.
UserRepo — Single source of truth for User ORM queries.

Note: filter() 기반 — 기존 mock 패턴 (`db.query(...).filter(...).first()`)
호환 유지.
Note: filter()-based — keeps backward-compat with existing mock pattern.
"""
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.user import User


def find_by_id(db: Session, user_id: int) -> User | None:
    """PK 로 조회.
    Find a user by primary key.
    """
    return db.query(User).filter(User.id == user_id).first()


def find_by_github_id(db: Session, github_id: str) -> User | None:
    """GitHub 계정 ID(문자열) 로 조회 (OAuth 로그인 경로).
    Find a user by GitHub account ID string (OAuth login path).
    """
    return db.query(User).filter(User.github_id == github_id).first()


def find_by_otp(db: Session, otp: str) -> User | None:
    """만료되지 않은 OTP로 사용자를 조회한다.
    Find a user by unexpired OTP.

    Note: 호출자는 OTP 비교 타이밍 공격(enumeration attack)을 방지하기 위해
    응답 속도를 일정하게 유지하거나 hmac.compare_digest를 활용해야 한다.
    Callers should ensure constant-time OTP comparison or add response latency
    padding to mitigate timing-based enumeration attacks.
    """
    # 현재 UTC 시각을 기준으로 만료 여부 판정
    # Use current UTC time to determine whether the OTP has expired.
    now = datetime.now(timezone.utc)
    return db.scalar(
        select(User)
        .where(User.telegram_otp == otp)
        .where(User.telegram_otp_expires_at > now)
    )


def set_telegram_user_id(
    db: Session,
    user_id: int,
    telegram_user_id: str,
) -> None:
    """Telegram user_id를 매핑하고 OTP를 무효화한다.
    Map telegram_user_id and nullify the OTP.

    Raises:
        ValueError: telegram_user_id가 이미 다른 사용자에게 매핑된 경우.
                    Raised if telegram_user_id is already mapped to another user.
    """
    # OTP는 연동 완료 즉시 무효화하여 재사용을 방지한다
    # Nullify OTP immediately after linking to prevent replay attacks.
    try:
        db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                telegram_user_id=telegram_user_id,
                telegram_otp=None,
                telegram_otp_expires_at=None,
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError(f"telegram_user_id already mapped: {telegram_user_id}") from exc


def clear_otp(db: Session, user_id: int) -> None:
    """OTP를 무효화한다.
    Nullify the OTP fields (e.g. on timeout or explicit cancellation).
    """
    db.execute(
        update(User)
        .where(User.id == user_id)
        .values(telegram_otp=None, telegram_otp_expires_at=None)
    )
    db.commit()
