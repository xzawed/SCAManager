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


def test_repo_config_defaults_commit_comment_false():
    """신규 필드 commit_comment의 기본값은 False (Push 이벤트에서 자동 발송 안 함)."""
    config = RepoConfig(repo_full_name="owner/repo")
    assert config.commit_comment is False


def test_repo_config_defaults_create_issue_false():
    """신규 필드 create_issue의 기본값은 False (명시적 opt-in)."""
    config = RepoConfig(repo_full_name="owner/repo")
    assert config.create_issue is False


def test_repo_config_custom_commit_comment_and_create_issue():
    config = RepoConfig(
        repo_full_name="owner/repo",
        commit_comment=True,
        create_issue=True,
    )
    assert config.commit_comment is True
    assert config.create_issue is True
