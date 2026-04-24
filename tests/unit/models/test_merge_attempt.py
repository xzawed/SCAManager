"""MergeAttempt ORM 모델 단위 테스트 (Phase F.1).

TDD Red: src/models/merge_attempt.py 모듈은 아직 없음.
모든 auto-merge 시도를 기록하는 관측 테이블.
"""
# pylint: disable=redefined-outer-name
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.analysis import Analysis
from src.models.merge_attempt import MergeAttempt
from src.models.repository import Repository


@pytest.fixture
def db_session():
    """In-memory SQLite — SQLite 는 ForeignKey CASCADE 를 기본으로 무시하므로
    PRAGMA foreign_keys=ON 를 커넥션 이벤트로 활성화해 운영 DB 거동을 재현."""
    engine = create_engine("sqlite:///:memory:")

    # SQLite CASCADE 활성화
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_con, _):
        cursor = dbapi_con.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_cls = sessionmaker(bind=engine)
    session = session_cls()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_analysis(db_session) -> Analysis:
    repo = Repository(full_name="owner/repo")
    db_session.add(repo)
    db_session.commit()
    a = Analysis(repo_id=repo.id, commit_sha="deadbeef", score=80, grade="B", result={})
    db_session.add(a)
    db_session.commit()
    return a


def test_merge_attempt_can_be_persisted(db_session):
    """모든 필드를 round-trip 으로 영속화/재조회 — ORM 매핑 기본 검증."""
    a = _seed_analysis(db_session)
    attempt = MergeAttempt(
        analysis_id=a.id,
        repo_name="owner/repo",
        pr_number=42,
        score=80,
        threshold=75,
        success=False,
        failure_reason="branch_protection_blocked",
        detail_message="branch_protection_blocked: 머지 조건 미충족 (state=blocked)",
    )
    db_session.add(attempt)
    db_session.commit()

    found = db_session.query(MergeAttempt).filter_by(analysis_id=a.id).first()
    assert found is not None
    assert found.repo_name == "owner/repo"
    assert found.pr_number == 42
    assert found.score == 80
    assert found.threshold == 75
    assert found.success is False
    assert found.failure_reason == "branch_protection_blocked"
    assert "머지 조건 미충족" in found.detail_message
    # attempted_at 은 기본값으로 자동 채워짐
    assert isinstance(found.attempted_at, datetime)


def test_merge_attempt_cascade_delete_with_analysis(db_session):
    """Analysis 삭제 시 관련 MergeAttempt 레코드도 자동 삭제 (ondelete=CASCADE)."""
    a = _seed_analysis(db_session)
    attempt = MergeAttempt(
        analysis_id=a.id,
        repo_name="owner/repo",
        pr_number=1,
        score=70,
        threshold=75,
        success=False,
        failure_reason="unknown",
    )
    db_session.add(attempt)
    db_session.commit()
    assert db_session.query(MergeAttempt).count() == 1

    # Analysis 삭제 → CASCADE 로 MergeAttempt 도 삭제
    db_session.delete(a)
    db_session.commit()
    assert db_session.query(MergeAttempt).count() == 0


def test_merge_attempt_success_has_no_failure_reason(db_session):
    """성공 시 failure_reason/detail_message 는 None 허용 (nullable)."""
    a = _seed_analysis(db_session)
    attempt = MergeAttempt(
        analysis_id=a.id,
        repo_name="owner/repo",
        pr_number=5,
        score=92,
        threshold=75,
        success=True,
        failure_reason=None,
        detail_message=None,
    )
    db_session.add(attempt)
    db_session.commit()

    found = db_session.query(MergeAttempt).filter_by(analysis_id=a.id).first()
    assert found.success is True
    assert found.failure_reason is None
    assert found.detail_message is None


def test_merge_attempt_attempted_at_defaults_to_utc_now(db_session):
    """attempted_at 기본값은 현재 UTC 시각 — 명시적으로 주지 않아도 자동 채움."""
    a = _seed_analysis(db_session)
    before = datetime.now(timezone.utc)
    attempt = MergeAttempt(
        analysis_id=a.id,
        repo_name="owner/repo",
        pr_number=1,
        score=80,
        threshold=75,
        success=True,
    )
    db_session.add(attempt)
    db_session.commit()
    after = datetime.now(timezone.utc)

    found = db_session.query(MergeAttempt).filter_by(analysis_id=a.id).first()
    # SQLite 는 DateTime 을 naive 로 반환할 수 있으므로 tzinfo 를 붙여 비교
    attempted = found.attempted_at
    if attempted.tzinfo is None:
        attempted = attempted.replace(tzinfo=timezone.utc)
    assert before <= attempted <= after
