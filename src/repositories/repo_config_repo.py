"""RepoConfigRepo — RepoConfig ORM 쿼리 단일 출처 (순수 조회·삭제).

도메인 로직(`_config_field_names()` 기반 dynamic upsert) 은
`src/config_manager/manager.py` 에 그대로 유지. 본 모듈은 raw
ORM 조회·삭제만 담당한다.

Note: RepoConfig 는 repo_full_name (String) 만 가지고 Repository FK
가 없다. 따라서 식별은 full_name 기반으로 통일.
"""
from sqlalchemy.orm import Session

from src.models.repo_config import RepoConfig


def find_by_full_name(db: Session, full_name: str) -> RepoConfig | None:
    """리포 full_name (owner/repo) 으로 조회."""
    return db.query(RepoConfig).filter(RepoConfig.repo_full_name == full_name).first()


def find_by_full_names(db: Session, full_names: list[str]) -> dict[str, RepoConfig]:
    """다건 full_name 을 단일 IN 쿼리로 조회 → {full_name: RepoConfig} 매핑.
    Batch-fetch multiple full_names in a single IN query → {full_name: RepoConfig} map.

    루프 내 per-repo 조회(N+1)를 단일 쿼리로 대체할 때 사용 (cron 등).
    Used to replace per-repo lookups in a loop (N+1) with one query (e.g. cron).
    빈 리스트면 쿼리 없이 빈 dict 반환.
    Returns an empty dict without querying when the list is empty.
    """
    if not full_names:
        return {}
    rows = (
        db.query(RepoConfig)
        .filter(RepoConfig.repo_full_name.in_(full_names))
        .all()
    )
    return {row.repo_full_name: row for row in rows}


def find_by_railway_webhook_token(db: Session, token: str) -> RepoConfig | None:
    """Railway webhook 토큰으로 조회 (POST /webhooks/railway/{token})."""
    return db.query(RepoConfig).filter(
        RepoConfig.railway_webhook_token == token
    ).first()


def delete_by_full_name(db: Session, full_name: str) -> int:
    """full_name 기반 삭제. 삭제된 행 수 반환. 호출자가 commit."""
    return db.query(RepoConfig).filter(
        RepoConfig.repo_full_name == full_name
    ).delete(synchronize_session=False)
