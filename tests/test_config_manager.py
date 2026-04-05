import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database import Base
from src.models.repo_config import RepoConfig
from src.models.gate_decision import GateDecision
from src.config_manager.manager import get_repo_config, upsert_repo_config, RepoConfigData


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_get_repo_config_returns_default_when_not_found(db):
    config = get_repo_config(db, "owner/nonexistent")
    assert config.repo_full_name == "owner/nonexistent"
    assert config.gate_mode == "disabled"
    assert config.auto_approve_threshold == 75
    assert config.auto_reject_threshold == 50
    assert config.notify_chat_id is None


def test_upsert_creates_new_config(db):
    data = RepoConfigData(repo_full_name="owner/repo", gate_mode="auto",
                          auto_approve_threshold=80, auto_reject_threshold=45)
    record = upsert_repo_config(db, data)
    assert record.id is not None
    assert record.gate_mode == "auto"
    assert record.auto_approve_threshold == 80


def test_upsert_updates_existing_config(db):
    upsert_repo_config(db, RepoConfigData(repo_full_name="owner/repo", gate_mode="auto"))
    record = upsert_repo_config(db, RepoConfigData(repo_full_name="owner/repo",
                                                    gate_mode="semi-auto",
                                                    auto_approve_threshold=90))
    assert record.gate_mode == "semi-auto"
    assert record.auto_approve_threshold == 90
    assert db.query(RepoConfig).filter_by(repo_full_name="owner/repo").count() == 1


def test_get_repo_config_returns_existing(db):
    upsert_repo_config(db, RepoConfigData(repo_full_name="owner/repo", gate_mode="auto",
                                           notify_chat_id="-100999"))
    config = get_repo_config(db, "owner/repo")
    assert config.gate_mode == "auto"
    assert config.notify_chat_id == "-100999"
