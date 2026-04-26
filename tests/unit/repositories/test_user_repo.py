"""user_repo 단위 테스트."""
# pylint: disable=redefined-outer-name
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.user import User
from src.repositories import user_repo


@pytest.fixture
def db_session():
    """In-memory SQLite session — 각 테스트 격리.
    In-memory SQLite session isolated per test.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_cls = sessionmaker(bind=engine)
    session = session_cls()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# 기존 조회 테스트 (Existing query tests)
# ---------------------------------------------------------------------------

def test_find_by_id_returns_user(db_session):
    # PK로 사용자를 조회하면 올바른 레코드를 반환한다
    # Finding a user by PK returns the correct record.
    user = User(github_id="12345", github_login="alice", email="a@b.com", display_name="A")
    db_session.add(user)
    db_session.commit()
    found = user_repo.find_by_id(db_session, user.id)
    assert found is not None
    assert found.github_login == "alice"


def test_find_by_id_not_found(db_session):
    # 존재하지 않는 ID 조회 시 None을 반환한다
    # Returns None when ID does not exist.
    assert user_repo.find_by_id(db_session, 9999) is None


def test_find_by_github_id_returns_user(db_session):
    # GitHub ID 문자열로 사용자를 정확히 조회한다
    # Finds user by GitHub account ID string accurately.
    user = User(github_id="54321", github_login="bob", email="b@c.com", display_name="B")
    db_session.add(user)
    db_session.commit()
    found = user_repo.find_by_github_id(db_session, "54321")
    assert found is not None
    assert found.github_login == "bob"


def test_find_by_github_id_not_found(db_session):
    # 없는 GitHub ID는 None을 반환한다
    # Returns None for a non-existent GitHub ID.
    assert user_repo.find_by_github_id(db_session, "no-such-id") is None


# ---------------------------------------------------------------------------
# T2 신규 테스트 (New T2 tests for Telegram columns + helpers)
# ---------------------------------------------------------------------------

def test_user_telegram_columns_default_null(db_session):
    # User 생성 시 Telegram 관련 컬럼 3개는 모두 None이어야 한다
    # All three Telegram columns must be None on a freshly created User.
    user = User(github_id="tg_null", github_login="cain", email="c@d.com", display_name="C")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.telegram_user_id is None
    assert user.telegram_otp is None
    assert user.telegram_otp_expires_at is None


def test_find_by_otp_returns_unexpired(db_session):
    # 유효 기간 내 OTP로 find_by_otp 호출 시 해당 User를 반환한다
    # find_by_otp returns the User when OTP is still within expiry.
    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    user = User(
        github_id="tg_otp1",
        github_login="dave",
        email="d@e.com",
        display_name="D",
        telegram_otp="ABC123",
        telegram_otp_expires_at=future,
    )
    db_session.add(user)
    db_session.commit()

    found = user_repo.find_by_otp(db_session, "ABC123")
    assert found is not None
    assert found.github_login == "dave"


def test_find_by_otp_skips_expired(db_session):
    # 만료된 OTP로 find_by_otp 호출 시 None을 반환한다
    # find_by_otp returns None when the OTP has expired.
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    user = User(
        github_id="tg_otp2",
        github_login="eve",
        email="e@f.com",
        display_name="E",
        telegram_otp="EXPIRED",
        telegram_otp_expires_at=past,
    )
    db_session.add(user)
    db_session.commit()

    found = user_repo.find_by_otp(db_session, "EXPIRED")
    assert found is None


def test_set_telegram_user_id_clears_otp(db_session):
    # set_telegram_user_id 호출 후 telegram_user_id가 설정되고 OTP가 무효화된다
    # After set_telegram_user_id, telegram_user_id is stored and OTP fields are nullified.
    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    user = User(
        github_id="tg_link",
        github_login="frank",
        email="f@g.com",
        display_name="F",
        telegram_otp="LINK99",
        telegram_otp_expires_at=future,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    user_repo.set_telegram_user_id(db_session, user.id, telegram_user_id="111222333")

    db_session.refresh(user)
    assert user.telegram_user_id == "111222333"
    assert user.telegram_otp is None
    assert user.telegram_otp_expires_at is None


def test_is_telegram_connected_property(db_session):
    # telegram_user_id가 None이면 False, 값이 있으면 True를 반환한다
    # is_telegram_connected returns False when telegram_user_id is None, True otherwise.
    user = User(github_id="tg_prop", github_login="grace", email="g@h.com", display_name="G")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.is_telegram_connected is False

    user.telegram_user_id = "987654321"
    db_session.commit()
    db_session.refresh(user)

    assert user.is_telegram_connected is True


def test_clear_otp_nullifies_fields(db_session):
    """clear_otp가 OTP 있는 사용자의 otp/expires_at을 None으로 만든다.
    clear_otp nullifies telegram_otp and telegram_otp_expires_at.
    """
    # OTP가 설정된 사용자 생성
    # Create a user with an active OTP.
    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    user = User(
        github_id="tg_clear1",
        github_login="hank",
        email="h@i.com",
        display_name="H",
        telegram_otp="CLEAR01",
        telegram_otp_expires_at=future,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # clear_otp 호출 후 두 필드가 None이어야 한다
    # Both fields must be None after clear_otp.
    user_repo.clear_otp(db_session, user.id)
    db_session.refresh(user)

    assert user.telegram_otp is None
    assert user.telegram_otp_expires_at is None


def test_clear_otp_on_user_without_otp_is_noop(db_session):
    """clear_otp는 OTP가 없는 사용자에 대해 예외 없이 처리된다.
    clear_otp is a no-op when the user has no OTP.
    """
    # OTP가 없는 사용자 생성
    # Create a user with no OTP set.
    user = User(
        github_id="tg_clear2",
        github_login="iris",
        email="i@j.com",
        display_name="I",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # 예외 없이 통과해야 한다
    # Must complete without raising any exception.
    user_repo.clear_otp(db_session, user.id)
    db_session.refresh(user)

    assert user.telegram_otp is None
    assert user.telegram_otp_expires_at is None


def test_find_by_otp_returns_none_for_wrong_code(db_session):
    """만료되지 않았지만 OTP 코드가 틀리면 None을 반환한다.
    Returns None when the OTP code is incorrect even if not expired.
    """
    # 유효한 OTP를 가진 사용자 생성
    # Create a user with a valid, unexpired OTP.
    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    user = User(
        github_id="tg_wrong",
        github_login="jake",
        email="j@k.com",
        display_name="J",
        telegram_otp="CORRECT",
        telegram_otp_expires_at=future,
    )
    db_session.add(user)
    db_session.commit()

    # 다른 코드로 조회하면 None을 반환해야 한다
    # Querying with a different code must return None.
    found = user_repo.find_by_otp(db_session, "WRONGCODE")
    assert found is None
