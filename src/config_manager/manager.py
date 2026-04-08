from dataclasses import dataclass
from sqlalchemy.orm import Session
from src.models.repo_config import RepoConfig


@dataclass
class RepoConfigData:
    repo_full_name: str
    gate_mode: str = "disabled"
    auto_approve_threshold: int = 75
    auto_reject_threshold: int = 50
    notify_chat_id: str | None = None
    n8n_webhook_url: str | None = None
    discord_webhook_url: str | None = None
    slack_webhook_url: str | None = None
    custom_webhook_url: str | None = None
    email_recipients: str | None = None
    auto_merge: bool = False


def get_repo_config(db: Session, repo_full_name: str) -> RepoConfigData:
    record = db.query(RepoConfig).filter_by(repo_full_name=repo_full_name).first()
    if record is None:
        return RepoConfigData(repo_full_name=repo_full_name)
    return RepoConfigData(
        repo_full_name=record.repo_full_name,
        gate_mode=record.gate_mode,
        auto_approve_threshold=record.auto_approve_threshold,
        auto_reject_threshold=record.auto_reject_threshold,
        notify_chat_id=record.notify_chat_id,
        n8n_webhook_url=record.n8n_webhook_url,
        discord_webhook_url=record.discord_webhook_url,
        slack_webhook_url=record.slack_webhook_url,
        custom_webhook_url=record.custom_webhook_url,
        email_recipients=record.email_recipients,
        auto_merge=record.auto_merge,
    )


def upsert_repo_config(db: Session, data: RepoConfigData) -> RepoConfig:
    record = db.query(RepoConfig).filter_by(repo_full_name=data.repo_full_name).first()
    if record is None:
        record = RepoConfig(
            repo_full_name=data.repo_full_name,
            gate_mode=data.gate_mode,
            auto_approve_threshold=data.auto_approve_threshold,
            auto_reject_threshold=data.auto_reject_threshold,
            notify_chat_id=data.notify_chat_id,
            n8n_webhook_url=data.n8n_webhook_url,
            discord_webhook_url=data.discord_webhook_url,
            slack_webhook_url=data.slack_webhook_url,
            custom_webhook_url=data.custom_webhook_url,
            email_recipients=data.email_recipients,
            auto_merge=data.auto_merge,
        )
        db.add(record)
    else:
        record.gate_mode = data.gate_mode
        record.auto_approve_threshold = data.auto_approve_threshold
        record.auto_reject_threshold = data.auto_reject_threshold
        record.notify_chat_id = data.notify_chat_id
        record.n8n_webhook_url = data.n8n_webhook_url
        record.discord_webhook_url = data.discord_webhook_url
        record.slack_webhook_url = data.slack_webhook_url
        record.custom_webhook_url = data.custom_webhook_url
        record.email_recipients = data.email_recipients
        record.auto_merge = data.auto_merge
    db.commit()
    db.refresh(record)
    return record
