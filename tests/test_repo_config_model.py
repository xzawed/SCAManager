import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from src.models.repo_config import RepoConfig
from src.models.gate_decision import GateDecision


def test_repo_config_defaults():
    config = RepoConfig(repo_full_name="owner/repo")
    assert config.approve_mode == "disabled"
    assert config.approve_threshold == 75
    assert config.reject_threshold == 50
    assert config.pr_review_comment is True
    assert config.merge_threshold == 75
    assert config.notify_chat_id is None
    assert config.n8n_webhook_url is None


def test_repo_config_custom_values():
    config = RepoConfig(
        repo_full_name="owner/repo",
        approve_mode="auto",
        approve_threshold=80,
        reject_threshold=40,
        pr_review_comment=False,
        merge_threshold=60,
        notify_chat_id="-100999",
    )
    assert config.approve_mode == "auto"
    assert config.approve_threshold == 80
    assert config.pr_review_comment is False
    assert config.merge_threshold == 60
    assert config.notify_chat_id == "-100999"


def test_gate_decision_fields():
    decision = GateDecision(analysis_id=1, decision="approve", mode="auto")
    assert decision.analysis_id == 1
    assert decision.decision == "approve"
    assert decision.mode == "auto"
    assert decision.decided_by is None


def test_gate_decision_manual_with_user():
    decision = GateDecision(analysis_id=5, decision="reject", mode="manual", decided_by="john")
    assert decision.decided_by == "john"


# ---------------------------------------------------------------------------
# Phase 3-A: RepoConfig ORM 신규 4필드 기본값 (Red)
# ---------------------------------------------------------------------------

def test_repo_config_push_commit_comment_default_true():
    """push_commit_comment 기본값은 True여야 한다."""
    config = RepoConfig(repo_full_name="owner/repo-new")
    assert config.push_commit_comment is True


def test_repo_config_regression_alert_default_true():
    """regression_alert 기본값은 True여야 한다."""
    config = RepoConfig(repo_full_name="owner/repo-new")
    assert config.regression_alert is True


def test_repo_config_regression_drop_threshold_default_15():
    """regression_drop_threshold 기본값은 15점이어야 한다."""
    config = RepoConfig(repo_full_name="owner/repo-new")
    assert config.regression_drop_threshold == 15


def test_repo_config_block_threshold_default_none():
    """block_threshold 기본값은 None (nullable)이어야 한다."""
    config = RepoConfig(repo_full_name="owner/repo-new")
    assert config.block_threshold is None


def test_repo_config_phase3a_custom_values():
    """Phase 3-A 신규 필드를 커스텀 값으로 생성할 수 있어야 한다."""
    config = RepoConfig(
        repo_full_name="owner/repo-custom",
        push_commit_comment=False,
        regression_alert=False,
        regression_drop_threshold=20,
        block_threshold=60,
    )
    assert config.push_commit_comment is False
    assert config.regression_alert is False
    assert config.regression_drop_threshold == 20
    assert config.block_threshold == 60
