"""RepositoryRepo — Repository ORM 쿼리 단일 출처.

Note: filter() 기반 — 기존 mock 패턴 (`db.query(...).filter(...).first()`) 호환
유지. api/deps.py 의 `get_repo_or_404()` 가 404 처리를 감싸는 HTTP 레이어 헬퍼.
UI/webhook 은 본 모듈 직접 호출 (각자 에러 처리 방식 상이).
"""
from sqlalchemy.orm import Session
from src.models.repository import Repository


def find_by_full_name(db: Session, full_name: str) -> Repository | None:
    """리포 전체 이름(owner/repo)으로 조회.

    Note: filter_by() 기반 — test_pipeline.py 12곳 이상이 단일
    `.filter_by.return_value.first.side_effect` 체인으로 repo+analysis
    조회를 묶어서 mock 한다. 본 함수를 `filter` 기반으로 바꾸면 해당
    체인이 분리되어 12+ 테스트 회귀 (Phase S.1-4 + S.3-D 2회 실패로
    확정). pipeline test mock 구조 근본 재설계 (repo 조회를 본 함수
    자체 patch 로 분리) 가 선행되어야 `filter` 기반 전환 가능 — 별도
    Phase 대상.
    """
    return db.query(Repository).filter_by(full_name=full_name).first()


def find_by_id(db: Session, repo_id: int) -> Repository | None:
    """PK로 조회."""
    return db.query(Repository).filter_by(id=repo_id).first()


def save_new(db: Session, repo: Repository) -> Repository:
    """신규 리포를 저장하고 반환한다. commit은 호출자 책임."""
    db.add(repo)
    return repo
