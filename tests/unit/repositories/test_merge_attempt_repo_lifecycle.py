"""Phase 3 PR-B1 — MergeAttempt lifecycle 함수 단위 테스트.

find_latest_for_pr / mark_actually_merged / mark_disabled_externally 의
멱등 전이 가드를 검증한다 (in-memory SQLite).
"""
# pylint: disable=redefined-outer-name
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
import src.models  # noqa: F401 — 모든 모델 등록
from src.gate import _merge_attempt_states as _states
from src.models.analysis import Analysis
from src.models.merge_attempt import MergeAttempt
from src.models.repository import Repository
from src.repositories import merge_attempt_repo


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.close()
    engine.dispose()


def _seed_analysis(db, repo_name="o/r", commit_sha="abc123"):
    repo = Repository(full_name=repo_name)
    db.add(repo)
    db.commit()
    analysis = Analysis(repo_id=repo.id, commit_sha=commit_sha)
    db.add(analysis)
    db.commit()
    return analysis


def test_find_latest_for_pr_returns_none_when_no_rows(db_session):
    """PR 에 MergeAttempt 없으면 None 반환."""
    assert merge_attempt_repo.find_latest_for_pr(db_session, "o/r", 7) is None


def test_find_latest_for_pr_returns_most_recent(db_session):
    """동일 PR 의 여러 시도 중 attempted_at 가장 최근 행 반환."""
    analysis = _seed_analysis(db_session)
    older = MergeAttempt(
        analysis_id=analysis.id, repo_name="o/r", pr_number=7,
        score=80, threshold=75, success=True,
        attempted_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    newer = MergeAttempt(
        analysis_id=analysis.id, repo_name="o/r", pr_number=7,
        score=82, threshold=75, success=True,
        attempted_at=datetime(2026, 4, 29, tzinfo=timezone.utc),
    )
    db_session.add_all([older, newer])
    db_session.commit()

    found = merge_attempt_repo.find_latest_for_pr(db_session, "o/r", 7)
    assert found is not None
    assert found.score == 82  # 최신 행


def test_mark_actually_merged_transitions_pending_row(db_session):
    """state='enabled_pending_merge' 행을 'actually_merged' 로 전이."""
    analysis = _seed_analysis(db_session)
    row = MergeAttempt(
        analysis_id=analysis.id, repo_name="o/r", pr_number=7,
        score=80, threshold=75, success=True,
        state=_states.ENABLED_PENDING_MERGE,
    )
    db_session.add(row)
    db_session.commit()

    merged_at = datetime.now(timezone.utc)
    updated = merge_attempt_repo.mark_actually_merged(
        db_session, attempt_id=row.id, merged_at=merged_at,
    )
    assert updated is True
    db_session.refresh(row)
    assert row.state == _states.ACTUALLY_MERGED
    assert row.merged_at is not None


def test_mark_actually_merged_idempotent_on_already_merged(db_session):
    """이미 actually_merged 인 행 재호출 시 no-op (False 반환)."""
    analysis = _seed_analysis(db_session)
    row = MergeAttempt(
        analysis_id=analysis.id, repo_name="o/r", pr_number=7,
        score=80, threshold=75, success=True,
        state=_states.ACTUALLY_MERGED,
    )
    db_session.add(row)
    db_session.commit()

    updated = merge_attempt_repo.mark_actually_merged(
        db_session, attempt_id=row.id, merged_at=datetime.now(timezone.utc),
    )
    assert updated is False  # WHERE 절 가드로 갱신 안 됨


def test_mark_actually_merged_skips_legacy_rows(db_session):
    """state='legacy' 행은 갱신 금지 (전이 무관)."""
    analysis = _seed_analysis(db_session)
    row = MergeAttempt(
        analysis_id=analysis.id, repo_name="o/r", pr_number=7,
        score=80, threshold=75, success=True,
        state=_states.LEGACY,
    )
    db_session.add(row)
    db_session.commit()

    updated = merge_attempt_repo.mark_actually_merged(
        db_session, attempt_id=row.id, merged_at=datetime.now(timezone.utc),
    )
    assert updated is False
    db_session.refresh(row)
    assert row.state == _states.LEGACY  # 변경 없음


def test_mark_disabled_externally_transitions_pending_row(db_session):
    """state='enabled_pending_merge' 행을 'disabled_externally' 로 전이 + reason 기록."""
    analysis = _seed_analysis(db_session)
    row = MergeAttempt(
        analysis_id=analysis.id, repo_name="o/r", pr_number=7,
        score=80, threshold=75, success=True,
        state=_states.ENABLED_PENDING_MERGE,
    )
    db_session.add(row)
    db_session.commit()

    updated = merge_attempt_repo.mark_disabled_externally(
        db_session, attempt_id=row.id,
        disabled_at=datetime.now(timezone.utc),
        reason="auto_merge_disabled_by_user",
    )
    assert updated is True
    db_session.refresh(row)
    assert row.state == _states.DISABLED_EXTERNALLY
    assert row.disabled_at is not None
    assert row.failure_reason == "auto_merge_disabled_by_user"


def test_mark_disabled_externally_idempotent(db_session):
    """이미 disabled_externally 인 행은 no-op."""
    analysis = _seed_analysis(db_session)
    row = MergeAttempt(
        analysis_id=analysis.id, repo_name="o/r", pr_number=7,
        score=80, threshold=75, success=True,
        state=_states.DISABLED_EXTERNALLY,
    )
    db_session.add(row)
    db_session.commit()

    updated = merge_attempt_repo.mark_disabled_externally(
        db_session, attempt_id=row.id,
        disabled_at=datetime.now(timezone.utc),
    )
    assert updated is False


def test_create_with_state_and_enabled_at(db_session):
    """create() 의 신규 state/enabled_at 파라미터 round-trip."""
    analysis = _seed_analysis(db_session)
    enabled_at = datetime(2026, 4, 29, 12, tzinfo=timezone.utc)
    record = merge_attempt_repo.create(
        db_session,
        analysis_id=analysis.id, repo_name="o/r", pr_number=7,
        score=80, threshold=75, success=True,
        state=_states.ENABLED_PENDING_MERGE, enabled_at=enabled_at,
    )
    assert record.state == _states.ENABLED_PENDING_MERGE
    # SQLite 는 timezone naive 로 저장 — replace(tzinfo=None) 으로 비교
    # SQLite stores datetimes as naive — strip tzinfo before comparing
    assert record.enabled_at.replace(tzinfo=None) == enabled_at.replace(tzinfo=None)
    assert record.merged_at is None
    assert record.disabled_at is None


def test_create_default_state_is_legacy(db_session):
    """기존 호출처 호환 — state 미지정 시 'legacy' 기본값."""
    analysis = _seed_analysis(db_session)
    record = merge_attempt_repo.create(
        db_session,
        analysis_id=analysis.id, repo_name="o/r", pr_number=7,
        score=80, threshold=75, success=True,
    )
    assert record.state == _states.LEGACY
