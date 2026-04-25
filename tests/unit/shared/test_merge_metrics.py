"""merge_metrics — auto-merge 시도 기록 + 구조화 로깅 (Phase F.1).

TDD Red: src/shared/merge_metrics.py 모듈은 아직 없음.

- parse_reason_tag: 정규 태그 추출 (":" 구분자 기반).
- log_merge_attempt: MergeAttempt DB 기록 + INFO 구조화 로그.
- DB 실패는 WARNING 로그 + None 반환 — 파이프라인 중단 금지.
"""
# pylint: disable=redefined-outer-name
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

import logging
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.analysis import Analysis
from src.models.merge_attempt import MergeAttempt
from src.models.repository import Repository
from src.shared import merge_metrics


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_cls = sessionmaker(bind=engine)
    session = session_cls()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def seeded_analysis(db_session):
    """테스트용 Analysis — merge_attempt FK 참조용."""
    repo = Repository(full_name="owner/repo")
    db_session.add(repo)
    db_session.commit()
    a = Analysis(repo_id=repo.id, commit_sha="abc", score=80, grade="B", result={})
    db_session.add(a)
    db_session.commit()
    return a


# ---------------------------------------------------------------------------
# parse_reason_tag
# ---------------------------------------------------------------------------


def test_parse_reason_tag_none():
    """None 입력은 None 반환."""
    assert merge_metrics.parse_reason_tag(None) is None


def test_parse_reason_tag_with_colon():
    """'tag: detail' 형식 → tag 부분만 추출."""
    assert (
        merge_metrics.parse_reason_tag(
            "branch_protection_blocked: 머지 조건 미충족 (state=blocked)"
        )
        == "branch_protection_blocked"
    )
    assert (
        merge_metrics.parse_reason_tag("permission_denied: Resource not accessible")
        == "permission_denied"
    )


def test_parse_reason_tag_without_colon():
    """':' 없는 문자열은 전체를 태그로 취급."""
    assert merge_metrics.parse_reason_tag("just_a_tag") == "just_a_tag"
    assert merge_metrics.parse_reason_tag("unknown") == "unknown"


def test_parse_reason_tag_empty_string():
    """빈 문자열은 None 로 정규화 (정규 태그로 인정 안 함)."""
    assert merge_metrics.parse_reason_tag("") is None


# ---------------------------------------------------------------------------
# log_merge_attempt — 성공/실패 경로
# ---------------------------------------------------------------------------


def test_log_merge_attempt_on_success_stores_none_reason(db_session, seeded_analysis):
    """success=True 시 failure_reason 과 detail_message 는 None 으로 저장."""
    rec = merge_metrics.log_merge_attempt(
        db_session,
        analysis_id=seeded_analysis.id,
        repo_name="owner/repo",
        pr_number=1,
        score=90,
        threshold=75,
        success=True,
        reason=None,
    )
    assert rec is not None
    assert rec.success is True
    assert rec.failure_reason is None
    assert rec.detail_message is None
    # DB 에 실제로 INSERT
    assert db_session.query(MergeAttempt).count() == 1


def test_log_merge_attempt_on_failure_extracts_tag(db_session, seeded_analysis):
    """failure 경로: reason 문자열에서 정규 태그만 failure_reason 에, 전체는 detail_message 에."""
    full_reason = "permission_denied: Resource not accessible by integration"
    rec = merge_metrics.log_merge_attempt(
        db_session,
        analysis_id=seeded_analysis.id,
        repo_name="owner/repo",
        pr_number=3,
        score=80,
        threshold=75,
        success=False,
        reason=full_reason,
    )
    assert rec is not None
    assert rec.success is False
    assert rec.failure_reason == "permission_denied"
    assert rec.detail_message == full_reason


def test_log_merge_attempt_on_failure_without_reason(db_session, seeded_analysis):
    """success=False + reason=None — failure_reason/detail_message 모두 None 허용."""
    rec = merge_metrics.log_merge_attempt(
        db_session,
        analysis_id=seeded_analysis.id,
        repo_name="owner/repo",
        pr_number=4,
        score=70,
        threshold=75,
        success=False,
        reason=None,
    )
    assert rec is not None
    assert rec.success is False
    assert rec.failure_reason is None
    assert rec.detail_message is None


# ---------------------------------------------------------------------------
# 구조화 로그 — caplog 에 extra 필드 검증
# ---------------------------------------------------------------------------


def test_log_merge_attempt_emits_structured_log(
    db_session, seeded_analysis, caplog,
):
    """INFO 로그에 'merge_attempt' 식별자 + extra 필드 포함."""
    with caplog.at_level(logging.INFO, logger="src.shared.merge_metrics"):
        merge_metrics.log_merge_attempt(
            db_session,
            analysis_id=seeded_analysis.id,
            repo_name="owner/repo",
            pr_number=7,
            score=85,
            threshold=75,
            success=False,
            reason="branch_protection_blocked: 머지 조건 미충족",
        )

    assert len(caplog.records) >= 1
    record = caplog.records[-1]
    msg = record.getMessage()
    assert "merge_attempt" in msg
    # extra 필드 — structured log shipper 가 파싱할 수 있어야 함
    assert getattr(record, "merge_result", None) in ("success", "failure")
    # 실패 경로 — failure 라벨
    assert getattr(record, "merge_result", None) == "failure"
    assert getattr(record, "failure_reason", None) == "branch_protection_blocked"
    assert getattr(record, "score", None) == 85
    assert getattr(record, "threshold", None) == 75
    assert getattr(record, "repo_name", None) == "owner/repo"
    assert getattr(record, "pr_number", None) == 7


def test_log_merge_attempt_success_has_merge_result_success(
    db_session, seeded_analysis, caplog,
):
    """success=True 시 extra merge_result='success', failure_reason 은 None/미설정."""
    with caplog.at_level(logging.INFO, logger="src.shared.merge_metrics"):
        merge_metrics.log_merge_attempt(
            db_session,
            analysis_id=seeded_analysis.id,
            repo_name="owner/repo",
            pr_number=2,
            score=90,
            threshold=75,
            success=True,
            reason=None,
        )
    record = caplog.records[-1]
    assert getattr(record, "merge_result", None) == "success"
    # 성공 시 failure_reason 은 None
    assert getattr(record, "failure_reason", "<missing>") in (None, "<missing>")


# ---------------------------------------------------------------------------
# DB 오류 내성 — commit 예외 시 None 반환 + WARNING 로그
# ---------------------------------------------------------------------------


def test_log_merge_attempt_db_failure_returns_none_and_warns(caplog):
    """db.commit() 이 예외 발생 시 None 반환 + WARNING 로그 (파이프라인 비중단)."""
    mock_db = MagicMock()
    mock_db.commit.side_effect = RuntimeError("DB down")

    with caplog.at_level(logging.WARNING, logger="src.shared.merge_metrics"):
        rec = merge_metrics.log_merge_attempt(
            mock_db,
            analysis_id=1,
            repo_name="owner/repo",
            pr_number=1,
            score=80,
            threshold=75,
            success=False,
            reason="unknown",
        )

    assert rec is None
    # WARNING 레벨의 로그가 최소 1건 기록되어야 함
    # At least one WARNING-level log entry must be recorded.
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) >= 1


def test_log_merge_attempt_db_failure_calls_rollback():
    """commit() 실패 시 rollback() 호출 — 세션 invalid 상태 방지.

    SQLAlchemy 는 commit 실패 후 rollback 하지 않으면 동일 세션의 후속 쿼리가
    PendingRollbackError 로 실패한다. Phase F.1 검토 Blocker 사항.
    """
    mock_db = MagicMock()
    mock_db.commit.side_effect = RuntimeError("DB down")

    merge_metrics.log_merge_attempt(
        mock_db,
        analysis_id=1,
        repo_name="owner/repo",
        pr_number=1,
        score=80,
        threshold=75,
        success=False,
        reason="unknown",
    )
    mock_db.rollback.assert_called_once()


def test_log_merge_attempt_rollback_failure_also_does_not_crash():
    """rollback() 자체가 예외를 던져도 log_merge_attempt 는 None 반환 (방어적)."""
    mock_db = MagicMock()
    mock_db.commit.side_effect = RuntimeError("DB down")
    mock_db.rollback.side_effect = RuntimeError("rollback also broken")

    rec = merge_metrics.log_merge_attempt(
        mock_db,
        analysis_id=1,
        repo_name="owner/repo",
        pr_number=1,
        score=80,
        threshold=75,
        success=False,
        reason="unknown",
    )
    assert rec is None
