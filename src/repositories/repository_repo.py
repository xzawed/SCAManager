"""RepositoryRepo — Repository ORM 쿼리 단일 출처.

Note: filter() 기반 — 기존 mock 패턴 (`db.query(...).filter(...).first()`) 호환
유지. api/deps.py 의 `get_repo_or_404()` 가 404 처리를 감싸는 HTTP 레이어 헬퍼.
UI/webhook 은 본 모듈 직접 호출 (각자 에러 처리 방식 상이).
"""
from sqlalchemy.orm import Session
from src.models.repository import Repository


def find_by_full_name(db: Session, full_name: str) -> Repository | None:
    """리포 전체 이름(owner/repo)으로 조회.

    Note: Phase S.4 (test_pipeline.py mock 재설계) 완료 이후 `filter()` 기반으로
    전환됨. 과거 `filter_by` 는 `test_pipeline.py` 의 `filter_by.return_value
    .first.side_effect` 단일 체인 mock 과 결합되어 있어 내부 구현 변경이
    12+ 회귀를 유발했다. 현재 테스트는 `repository_repo.find_by_full_name`
    자체를 직접 patch 하므로 내부 ORM 구현과 독립적이다.
    """
    return db.query(Repository).filter(Repository.full_name == full_name).first()


def find_by_id(db: Session, repo_id: int) -> Repository | None:
    """PK로 조회."""
    return db.query(Repository).filter_by(id=repo_id).first()


def save_new(db: Session, repo: Repository) -> Repository:
    """신규 리포를 저장하고 반환한다. commit은 호출자 책임."""
    db.add(repo)
    return repo
