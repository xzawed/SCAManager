"""repo_config_repo 단위 테스트."""
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
from src.models.repo_config import RepoConfig
from src.models.repository import Repository
from src.repositories import repo_config_repo


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_cls = sessionmaker(bind=engine)
    session = session_cls()
    try:
        yield session
    finally:
        session.close()


def _seed(db_session, full_name="owner/repo", railway_token=None):
    cfg = RepoConfig(
        repo_full_name=full_name,
        railway_webhook_token=railway_token,
    )
    db_session.add(cfg)
    db_session.commit()
    return cfg


def test_find_by_full_name(db_session):
    cfg = _seed(db_session)
    found = repo_config_repo.find_by_full_name(db_session, "owner/repo")
    assert found is not None and found.id == cfg.id


def test_find_by_full_name_not_found(db_session):
    assert repo_config_repo.find_by_full_name(db_session, "none/repo") is None


def test_find_by_railway_webhook_token(db_session):
    cfg = _seed(db_session, railway_token="tok-abc-xyz")
    found = repo_config_repo.find_by_railway_webhook_token(db_session, "tok-abc-xyz")
    assert found is not None and found.id == cfg.id


def test_delete_by_full_name_returns_row_count(db_session):
    _seed(db_session)
    deleted = repo_config_repo.delete_by_full_name(db_session, "owner/repo")
    db_session.commit()
    assert deleted == 1
    assert repo_config_repo.find_by_full_name(db_session, "owner/repo") is None
