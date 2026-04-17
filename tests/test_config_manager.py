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
    """인메모리 SQLite 세션 — 각 테스트마다 독립 DB."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# 기존 동작 유지 테스트
# ---------------------------------------------------------------------------

def test_get_repo_config_returns_default_when_not_found(db):
    """존재하지 않는 repo 조회 시 기본값 RepoConfigData가 반환된다."""
    config = get_repo_config(db, "owner/nonexistent")
    assert config.repo_full_name == "owner/nonexistent"
    # 기존 필드 — approve_mode로 rename 후에도 기본값은 "disabled"
    assert config.approve_mode == "disabled"
    assert config.approve_threshold == 75
    assert config.reject_threshold == 50
    assert config.notify_chat_id is None


def test_upsert_creates_new_config(db):
    """신규 RepoConfig가 DB에 생성되어야 한다."""
    data = RepoConfigData(
        repo_full_name="owner/repo",
        approve_mode="auto",
        approve_threshold=80,
        reject_threshold=45,
    )
    record = upsert_repo_config(db, data)
    assert record.id is not None
    assert record.approve_mode == "auto"
    assert record.approve_threshold == 80


def test_upsert_updates_existing_config(db):
    """기존 RepoConfig가 업데이트되고 중복 생성되지 않아야 한다."""
    upsert_repo_config(db, RepoConfigData(repo_full_name="owner/repo", approve_mode="auto"))
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo",
        approve_mode="semi-auto",
        approve_threshold=90,
    ))
    assert record.approve_mode == "semi-auto"
    assert record.approve_threshold == 90
    assert db.query(RepoConfig).filter_by(repo_full_name="owner/repo").count() == 1


def test_get_repo_config_returns_existing(db):
    """저장된 RepoConfig가 올바르게 조회된다."""
    upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo",
        approve_mode="auto",
        notify_chat_id="-100999",
    ))
    config = get_repo_config(db, "owner/repo")
    assert config.approve_mode == "auto"
    assert config.notify_chat_id == "-100999"


# ---------------------------------------------------------------------------
# 신규 필드 기본값 테스트 (Red: pr_review_comment, merge_threshold 미존재)
# ---------------------------------------------------------------------------

def test_repo_config_data_new_fields_defaults():
    """RepoConfigData에 신규 필드가 있고 기본값이 올바른지 검증한다."""
    # pr_review_comment 기본값은 True
    config = RepoConfigData(repo_full_name="owner/repo")
    assert config.pr_review_comment is True
    # merge_threshold 기본값은 75
    assert config.merge_threshold == 75
    # approve_mode 기본값은 "disabled" (gate_mode rename)
    assert config.approve_mode == "disabled"
    # approve_threshold 기본값은 75 (auto_approve_threshold rename)
    assert config.approve_threshold == 75
    # reject_threshold 기본값은 50 (auto_reject_threshold rename)
    assert config.reject_threshold == 50


def test_get_repo_config_default_pr_review_comment_is_true(db):
    """존재하지 않는 repo 조회 시 pr_review_comment 기본값이 True인지 검증한다."""
    config = get_repo_config(db, "owner/new-repo")
    assert config.pr_review_comment is True


def test_get_repo_config_default_merge_threshold_is_75(db):
    """존재하지 않는 repo 조회 시 merge_threshold 기본값이 75인지 검증한다."""
    config = get_repo_config(db, "owner/new-repo-2")
    assert config.merge_threshold == 75


def test_get_repo_config_default_auto_merge_is_false(db):
    """존재하지 않는 repo 조회 시 auto_merge 기본값이 False인지 검증한다."""
    config = get_repo_config(db, "owner/nonexistent-auto-merge")
    assert config.auto_merge is False


# ---------------------------------------------------------------------------
# 신규 필드 저장/조회 테스트 (Red: DB 컬럼 미존재)
# ---------------------------------------------------------------------------

def test_get_repo_config_returns_new_fields(db):
    """get_repo_config()가 신규 필드(pr_review_comment, merge_threshold)를 포함한다."""
    upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo",
        approve_mode="auto",
        pr_review_comment=False,
        merge_threshold=80,
    ))
    config = get_repo_config(db, "owner/repo")
    assert config.pr_review_comment is False
    assert config.merge_threshold == 80


def test_upsert_repo_config_with_pr_review_comment_false(db):
    """pr_review_comment=False로 upsert 시 DB에 올바르게 저장된다."""
    data = RepoConfigData(
        repo_full_name="owner/repo-noreview",
        approve_mode="auto",
        pr_review_comment=False,
    )
    record = upsert_repo_config(db, data)
    assert record.pr_review_comment is False


def test_upsert_repo_config_with_merge_threshold(db):
    """merge_threshold 값이 지정되면 DB에 올바르게 저장된다."""
    data = RepoConfigData(
        repo_full_name="owner/repo-mergethresh",
        approve_mode="auto",
        auto_merge=True,
        merge_threshold=85,
    )
    record = upsert_repo_config(db, data)
    assert record.merge_threshold == 85


def test_upsert_updates_pr_review_comment(db):
    """pr_review_comment를 True → False로 업데이트 시 DB에 반영된다."""
    upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-toggle",
        approve_mode="auto",
        pr_review_comment=True,
    ))
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-toggle",
        approve_mode="auto",
        pr_review_comment=False,
    ))
    assert record.pr_review_comment is False
    assert db.query(RepoConfig).filter_by(repo_full_name="owner/repo-toggle").count() == 1


def test_upsert_updates_merge_threshold(db):
    """merge_threshold를 75 → 90으로 업데이트 시 DB에 반영된다."""
    upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-thresh",
        approve_mode="auto",
        merge_threshold=75,
    ))
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-thresh",
        approve_mode="auto",
        merge_threshold=90,
    ))
    assert record.merge_threshold == 90
    assert db.query(RepoConfig).filter_by(repo_full_name="owner/repo-thresh").count() == 1


# ---------------------------------------------------------------------------
# auto_merge 기존 테스트 — approve_mode 필드명 기준으로 유지
# ---------------------------------------------------------------------------

def test_upsert_creates_config_with_auto_merge_true(db):
    """auto_merge=True로 RepoConfig 생성 시 DB에 올바르게 저장된다."""
    data = RepoConfigData(
        repo_full_name="owner/repo-merge",
        approve_mode="auto",
        auto_merge=True,
    )
    record = upsert_repo_config(db, data)
    assert record.auto_merge is True


def test_upsert_updates_auto_merge_flag(db):
    """auto_merge를 False → True로 업데이트 시 DB에 반영된다."""
    upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-flag",
        approve_mode="auto",
        auto_merge=False,
    ))
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-flag",
        approve_mode="auto",
        auto_merge=True,
    ))
    assert record.auto_merge is True
    assert db.query(RepoConfig).filter_by(repo_full_name="owner/repo-flag").count() == 1


# ---------------------------------------------------------------------------
# Phase 3-A: RepoConfigData 신규 4필드 기본값 (Red)
# ---------------------------------------------------------------------------

def test_repo_config_data_push_commit_comment_default():
    """RepoConfigData.push_commit_comment 기본값은 True여야 한다."""
    data = RepoConfigData(repo_full_name="owner/repo")
    assert data.push_commit_comment is True


def test_repo_config_data_regression_alert_default():
    """RepoConfigData.regression_alert 기본값은 True여야 한다."""
    data = RepoConfigData(repo_full_name="owner/repo")
    assert data.regression_alert is True


def test_repo_config_data_regression_drop_threshold_default():
    """RepoConfigData.regression_drop_threshold 기본값은 15여야 한다."""
    data = RepoConfigData(repo_full_name="owner/repo")
    assert data.regression_drop_threshold == 15


def test_repo_config_data_block_threshold_default():
    """RepoConfigData.block_threshold 기본값은 None이어야 한다."""
    data = RepoConfigData(repo_full_name="owner/repo")
    assert data.block_threshold is None


def test_get_repo_config_returns_phase3a_defaults(db):
    """존재하지 않는 repo 조회 시 Phase 3-A 신규 필드가 기본값으로 반환된다."""
    config = get_repo_config(db, "owner/phase3a-new")
    assert config.push_commit_comment is True
    assert config.regression_alert is True
    assert config.regression_drop_threshold == 15
    assert config.block_threshold is None


# ---------------------------------------------------------------------------
# Phase 3-A: upsert 신규 필드 저장/업데이트 (Red)
# ---------------------------------------------------------------------------

def test_upsert_creates_with_push_commit_comment_false(db):
    """push_commit_comment=False로 upsert 시 DB에 저장된다."""
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-push-off",
        push_commit_comment=False,
    ))
    assert record.push_commit_comment is False


def test_upsert_creates_with_regression_alert_false(db):
    """regression_alert=False로 upsert 시 DB에 저장된다."""
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-reg-off",
        regression_alert=False,
    ))
    assert record.regression_alert is False


def test_upsert_creates_with_regression_drop_threshold(db):
    """regression_drop_threshold 커스텀 값이 DB에 저장된다."""
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-drop",
        regression_drop_threshold=25,
    ))
    assert record.regression_drop_threshold == 25


def test_upsert_creates_with_block_threshold(db):
    """block_threshold 커스텀 값이 DB에 저장된다."""
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-block",
        block_threshold=40,
    ))
    assert record.block_threshold == 40


def test_upsert_updates_push_commit_comment(db):
    """push_commit_comment를 True → False로 업데이트 시 DB에 반영된다."""
    upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-toggle-push",
        push_commit_comment=True,
    ))
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-toggle-push",
        push_commit_comment=False,
    ))
    assert record.push_commit_comment is False
    assert db.query(RepoConfig).filter_by(repo_full_name="owner/repo-toggle-push").count() == 1


def test_upsert_updates_regression_fields(db):
    """regression_alert / regression_drop_threshold / block_threshold 업데이트."""
    upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-reg",
        regression_alert=True,
        regression_drop_threshold=15,
        block_threshold=None,
    ))
    record = upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-reg",
        regression_alert=False,
        regression_drop_threshold=30,
        block_threshold=55,
    ))
    assert record.regression_alert is False
    assert record.regression_drop_threshold == 30
    assert record.block_threshold == 55
    assert db.query(RepoConfig).filter_by(repo_full_name="owner/repo-reg").count() == 1


def test_get_repo_config_returns_phase3a_saved_values(db):
    """저장된 Phase 3-A 필드가 get_repo_config로 조회되어야 한다."""
    upsert_repo_config(db, RepoConfigData(
        repo_full_name="owner/repo-saved",
        push_commit_comment=False,
        regression_alert=False,
        regression_drop_threshold=20,
        block_threshold=45,
    ))
    config = get_repo_config(db, "owner/repo-saved")
    assert config.push_commit_comment is False
    assert config.regression_alert is False
    assert config.regression_drop_threshold == 20
    assert config.block_threshold == 45
