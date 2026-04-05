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
    assert config.gate_mode == "disabled"
    assert config.auto_approve_threshold == 75
    assert config.auto_reject_threshold == 50
    assert config.notify_chat_id is None
    assert config.n8n_webhook_url is None


def test_repo_config_custom_values():
    config = RepoConfig(
        repo_full_name="owner/repo",
        gate_mode="auto",
        auto_approve_threshold=80,
        auto_reject_threshold=40,
        notify_chat_id="-100999",
    )
    assert config.gate_mode == "auto"
    assert config.auto_approve_threshold == 80
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
