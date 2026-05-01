"""RepositoryRepo — Repository ORM 쿼리 단일 출처.

Note: filter() 기반 — 기존 mock 패턴 (`db.query(...).filter(...).first()`) 호환
유지. api/deps.py 의 `get_repo_or_404()` 가 404 처리를 감싸는 HTTP 레이어 헬퍼.
UI/webhook 은 본 모듈 직접 호출 (각자 에러 처리 방식 상이).
"""
from sqlalchemy.orm import Session, joinedload
from src.models.repository import Repository


def find_all(db: Session) -> list[Repository]:
    """모든 Repository 레코드를 반환한다.
    Return all Repository records.
    """
    return db.query(Repository).all()


def find_by_full_name(db: Session, full_name: str) -> Repository | None:
    """리포 전체 이름(owner/repo)으로 조회.

    Note: Phase S.4 (test_pipeline.py mock 재설계) 완료 이후 `filter()` 기반으로
    전환됨. 과거 `filter_by` 는 `test_pipeline.py` 의 `filter_by.return_value
    .first.side_effect` 단일 체인 mock 과 결합되어 있어 내부 구현 변경이
    12+ 회귀를 유발했다. 현재 테스트는 `repository_repo.find_by_full_name`
    자체를 직접 patch 하므로 내부 ORM 구현과 독립적이다.
    """
    return db.query(Repository).filter(Repository.full_name == full_name).first()


def find_by_full_name_with_owner(db: Session, full_name: str) -> Repository | None:
    """리포 + owner 를 단일 SELECT 로 eager-load (Phase H PR-3B — opt-in).

    `repo.owner.plaintext_token` 을 참조하는 호출처(pipeline, webhook providers
    등) 전용. lazy-load 시 호출당 추가 SELECT 1회 (N+1). joinedload 로 단일
    JOIN — Railway PG 기준 5-15ms 절약.

    **현재 상태 (PR-3B)**: 함수 추가 후 호출처 마이그레이션은 보류.
    `find_by_full_name` 의 mock 체인 (`db.query.return_value.filter.return_value
    .first`) 이 70+ 테스트에서 사용 중이라 호출처 변경 시 대규모 회귀 발생.
    Phase S.4 (test_pipeline.py mock 재설계) 와 동일 트랩.

    **마이그레이션 방법**: 호출처 1곳씩 옮기면서 해당 테스트의 mock 체인을
    `db.query.return_value.options.return_value.filter.return_value.first` 로
    갱신 — 별도 PR (PR-3B-2) 로 점진 진행.

    Currently available but un-adopted to avoid breaking 70+ mock chains
    (Phase S.4 lesson). Migrate callsites one-by-one in a follow-up PR,
    updating each test's mock chain to include `.options.return_value`.
    """
    return (
        db.query(Repository)
        .options(joinedload(Repository.owner))
        .filter(Repository.full_name == full_name)
        .first()
    )


def find_by_id(db: Session, repo_id: int) -> Repository | None:
    """PK로 조회."""
    return db.query(Repository).filter_by(id=repo_id).first()


def save_new(db: Session, repo: Repository) -> Repository:
    """신규 리포를 저장하고 반환한다. commit은 호출자 책임."""
    db.add(repo)
    return repo
