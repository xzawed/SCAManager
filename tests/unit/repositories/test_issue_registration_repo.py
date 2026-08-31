# tests/unit/repositories/test_issue_registration_repo.py
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database import Base
from src.repositories import issue_registration_repo


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _create(db, *, issue_key="key1", repo_id=1, analysis_id=1,
            issue_type="ai_suggestion", github_issue_number=42):
    return issue_registration_repo.create(
        db,
        analysis_id=analysis_id,
        repo_id=repo_id,
        issue_type=issue_type,
        issue_key=issue_key,
        github_issue_number=github_issue_number,
    )


def test_find_by_key_returns_none_when_missing(db):
    result = issue_registration_repo.find_by_key(db, repo_id=1, issue_key="missing")
    assert result is None


def test_create_and_find_by_key(db):
    _create(db, issue_key="abc123", repo_id=1, github_issue_number=42)
    found = issue_registration_repo.find_by_key(db, repo_id=1, issue_key="abc123")
    assert found is not None
    assert found.github_issue_number == 42
    assert found.github_issue_state == "open"


def test_create_sets_created_at(db):
    rec = _create(db)
    assert rec.created_at is not None


def test_list_by_analysis_empty(db):
    result = issue_registration_repo.list_by_analysis(db, analysis_id=99)
    assert result == []


def test_list_by_analysis_returns_records(db):
    _create(db, analysis_id=1, issue_key="k1")
    _create(db, analysis_id=1, issue_key="k2")
    _create(db, analysis_id=2, issue_key="k3")
    result = issue_registration_repo.list_by_analysis(db, analysis_id=1)
    assert len(result) == 2


def test_update_state_changes_state_and_synced_at(db):
    rec = _create(db)
    issue_registration_repo.update_state(db, record=rec, state="closed")
    assert rec.github_issue_state == "closed"
    assert rec.github_issue_synced_at is not None


def test_list_by_repo_returns_newest_first(db):
    # 순서 보장을 위해 created_at 명시
    # Explicitly set created_at to guarantee ordering
    older = issue_registration_repo.create(db, repo_id=1, analysis_id=1,
        issue_type="ai_suggestion", issue_key="r1", github_issue_number=1)
    older.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db.commit()
    newer = issue_registration_repo.create(db, repo_id=1, analysis_id=1,
        issue_type="ai_suggestion", issue_key="r2", github_issue_number=2)
    newer.created_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
    db.commit()

    result = issue_registration_repo.list_by_repo(db, repo_id=1)
    assert len(result) == 2
    # 최신순 — r2(2026-01-02)가 먼저
    # Newest first — r2 (2026-01-02) comes first
    assert result[0].issue_key == "r2"
    assert result[1].issue_key == "r1"


def test_same_key_different_repo_allowed(db):
    _create(db, repo_id=1, issue_key="same")
    _create(db, repo_id=2, issue_key="same")
    assert issue_registration_repo.find_by_key(db, repo_id=1, issue_key="same") is not None
    assert issue_registration_repo.find_by_key(db, repo_id=2, issue_key="same") is not None


# ── 동기화 실패를 감추지 않는다 (#1504 R3) ──────────────────────────────────
#
# 🔴 이전에는 `except (*HTTPX_SEND_ERRORS, KeyError, ValueError): pass` 였다.
#    일시 오류(5xx·타임아웃)에는 「마지막으로 알던 상태 유지」가 맞지만, `InvalidURL` 같은
#    **영구 오류**도 같은 `pass` 로 처리돼 UI 에는 낡은 open/closed 가 성공적으로
#    동기화된 것처럼 보였다. `synced_at` 은 갱신되지 않아 TTL 마다 재시도는 하지만
#    **사용자는 그 상태가 낡았다는 사실을 알 수 없었다.**


def test_record_sync_error_keeps_the_last_known_state(db):
    """🔴 실패해도 상태와 `synced_at` 은 **그대로다** — 바뀌는 것은 실패가 보인다는 것뿐이다.

    상태를 지우면 일시 오류에서 「알던 값」까지 잃는다. 그것은 이 변경의 목적이 아니다.
    """
    rec = _create(db)
    issue_registration_repo.update_state(db, record=rec, state="closed")
    synced_before = rec.github_issue_synced_at

    issue_registration_repo.record_sync_error(db, record=rec, reason="InvalidURL")
    assert rec.github_issue_state == "closed", "실패가 마지막으로 알던 상태를 지웠다"
    assert rec.github_issue_synced_at == synced_before, (
        "실패가 `synced_at` 을 갱신했다 — TTL 재시도 주기가 밀린다"
    )
    assert rec.sync_error == "InvalidURL"


def test_a_successful_sync_clears_the_error(db):
    """🔴 성공하면 실패 표시를 **지운다** — 안 지우면 한 번 실패한 항목이 영원히 실패로 보인다."""
    rec = _create(db)
    issue_registration_repo.record_sync_error(db, record=rec, reason="ConnectError")
    assert rec.sync_error == "ConnectError"

    issue_registration_repo.update_state(db, record=rec, state="open")
    assert rec.sync_error is None, "성공했는데 실패 표시가 남았다"


def test_a_fresh_record_has_no_error(db):
    """부정 통제 — 새 행은 실패 표시가 없다. 없으면 위 두 시험이 「항상 채워짐」과 구별되지 않는다."""
    rec = _create(db)
    assert rec.sync_error is None
