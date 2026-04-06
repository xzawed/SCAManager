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


# --- auto_merge 필드 테스트 (Red: RepoConfigData와 RepoConfig에 auto_merge가 아직 없음) ---

def test_get_repo_config_default_auto_merge_is_false(db):
    # 존재하지 않는 repo 조회 시 auto_merge 기본값이 False인지 검증
    config = get_repo_config(db, "owner/nonexistent-auto-merge")
    assert config.auto_merge is False


def test_upsert_creates_config_with_auto_merge_true(db):
    # auto_merge=True로 RepoConfig 생성 시 DB에 올바르게 저장되는지 검증
    data = RepoConfigData(repo_full_name="owner/repo-merge", gate_mode="auto",
                          auto_merge=True)
    record = upsert_repo_config(db, data)
    assert record.auto_merge is True


def test_upsert_updates_auto_merge_flag(db):
    # auto_merge를 False → True로 업데이트 시 DB에 반영되는지 검증
    upsert_repo_config(db, RepoConfigData(repo_full_name="owner/repo-flag",
                                           gate_mode="auto", auto_merge=False))
    record = upsert_repo_config(db, RepoConfigData(repo_full_name="owner/repo-flag",
                                                    gate_mode="auto", auto_merge=True))
    assert record.auto_merge is True
    assert db.query(RepoConfig).filter_by(repo_full_name="owner/repo-flag").count() == 1
