"""user_repo 단위 테스트."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.user import User
from src.repositories import user_repo


@pytest.fixture
def db_session():
    """In-memory SQLite session — 각 테스트 격리."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_cls = sessionmaker(bind=engine)
    session = session_cls()
    try:
        yield session
    finally:
        session.close()


def test_find_by_id_returns_user(db_session):
    user = User(github_id="12345", github_login="alice", email="a@b.com", display_name="A")
    db_session.add(user)
    db_session.commit()
    found = user_repo.find_by_id(db_session, user.id)
    assert found is not None
    assert found.github_login == "alice"


def test_find_by_id_not_found(db_session):
    assert user_repo.find_by_id(db_session, 9999) is None


def test_find_by_github_id_returns_user(db_session):
    user = User(github_id="54321", github_login="bob", email="b@c.com", display_name="B")
    db_session.add(user)
    db_session.commit()
    found = user_repo.find_by_github_id(db_session, "54321")
    assert found is not None
    assert found.github_login == "bob"


def test_find_by_github_id_not_found(db_session):
    assert user_repo.find_by_github_id(db_session, "no-such-id") is None
