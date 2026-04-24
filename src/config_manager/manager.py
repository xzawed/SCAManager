"""Repository configuration manager — get and upsert RepoConfig records."""
from dataclasses import dataclass, fields
from sqlalchemy.orm import Session
from src.models.repo_config import RepoConfig


@dataclass
class RepoConfigData:  # pylint: disable=too-many-instance-attributes
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
    commit_comment: bool = False
    create_issue: bool = False
    railway_deploy_alerts: bool = False
    auto_merge_issue_on_failure: bool = False


def _config_field_names() -> list[str]:
    """RepoConfigData의 필드명 목록 (repo_full_name 제외). 새 채널은 RepoConfigData에만 추가."""
    return [f.name for f in fields(RepoConfigData) if f.name != "repo_full_name"]


def get_repo_config(db: Session, repo_full_name: str) -> RepoConfigData:
    """DB에서 RepoConfig를 조회하여 RepoConfigData로 반환. 미존재 시 기본값 반환."""
    record = db.query(RepoConfig).filter_by(repo_full_name=repo_full_name).first()
    if record is None:
        return RepoConfigData(repo_full_name=repo_full_name)
    kwargs = {name: getattr(record, name) for name in _config_field_names()}
    return RepoConfigData(repo_full_name=record.repo_full_name, **kwargs)


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
    field_names = _config_field_names()
    record = db.query(RepoConfig).filter_by(repo_full_name=data.repo_full_name).first()
    if record is None:
        kwargs = {name: getattr(data, name) for name in field_names}
        record = RepoConfig(repo_full_name=data.repo_full_name, **kwargs)
        db.add(record)
    else:
        for name in field_names:
            setattr(record, name, getattr(data, name))
    db.commit()
    db.refresh(record)
    return record
