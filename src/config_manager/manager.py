"""Repository configuration manager — get and upsert RepoConfig records."""
from dataclasses import dataclass
from sqlalchemy.orm import Session
from src.models.repo_config import RepoConfig


@dataclass
class RepoConfigData:
    """RepoConfig ORM 레코드를 Python 데이터클래스로 표현한다 (단일 출처)."""

    repo_full_name: str
    pr_review_comment: bool = True
    approve_mode: str = "disabled"
    approve_threshold: int = 75
    reject_threshold: int = 50
    notify_chat_id: str | None = None
    n8n_webhook_url: str | None = None
    discord_webhook_url: str | None = None
    slack_webhook_url: str | None = None
    custom_webhook_url: str | None = None
    email_recipients: str | None = None
    auto_merge: bool = False
    merge_threshold: int = 75


def get_repo_config(db: Session, repo_full_name: str) -> RepoConfigData:
    """DB에서 RepoConfig를 조회하여 RepoConfigData로 반환. 미존재 시 기본값 반환."""
    record = db.query(RepoConfig).filter_by(repo_full_name=repo_full_name).first()
    if record is None:
        return RepoConfigData(repo_full_name=repo_full_name)
    return RepoConfigData(
        repo_full_name=record.repo_full_name,
        pr_review_comment=record.pr_review_comment,
        approve_mode=record.approve_mode,
        approve_threshold=record.approve_threshold,
        reject_threshold=record.reject_threshold,
        notify_chat_id=record.notify_chat_id,
        n8n_webhook_url=record.n8n_webhook_url,
        discord_webhook_url=record.discord_webhook_url,
        slack_webhook_url=record.slack_webhook_url,
        custom_webhook_url=record.custom_webhook_url,
        email_recipients=record.email_recipients,
        auto_merge=record.auto_merge,
        merge_threshold=record.merge_threshold,
    )


def upsert_repo_config(db: Session, data: RepoConfigData) -> RepoConfig:
    """RepoConfig를 INSERT 또는 UPDATE(Upsert)한다.

    Raises:
        ValueError: approve_threshold < reject_threshold 인 경우
    """
    if data.approve_threshold < data.reject_threshold:
        raise ValueError(
            f"approve_threshold({data.approve_threshold})는 "
            f"reject_threshold({data.reject_threshold}) 이상이어야 합니다"
        )
    record = db.query(RepoConfig).filter_by(repo_full_name=data.repo_full_name).first()
    if record is None:
        record = RepoConfig(
            repo_full_name=data.repo_full_name,
            pr_review_comment=data.pr_review_comment,
            approve_mode=data.approve_mode,
            approve_threshold=data.approve_threshold,
            reject_threshold=data.reject_threshold,
            notify_chat_id=data.notify_chat_id,
            n8n_webhook_url=data.n8n_webhook_url,
            discord_webhook_url=data.discord_webhook_url,
            slack_webhook_url=data.slack_webhook_url,
            custom_webhook_url=data.custom_webhook_url,
            email_recipients=data.email_recipients,
            auto_merge=data.auto_merge,
            merge_threshold=data.merge_threshold,
        )
        db.add(record)
    else:
        record.pr_review_comment = data.pr_review_comment
        record.approve_mode = data.approve_mode
        record.approve_threshold = data.approve_threshold
        record.reject_threshold = data.reject_threshold
        record.notify_chat_id = data.notify_chat_id
        record.n8n_webhook_url = data.n8n_webhook_url
        record.discord_webhook_url = data.discord_webhook_url
        record.slack_webhook_url = data.slack_webhook_url
        record.custom_webhook_url = data.custom_webhook_url
        record.email_recipients = data.email_recipients
        record.auto_merge = data.auto_merge
        record.merge_threshold = data.merge_threshold
    db.commit()
    db.refresh(record)
    return record
