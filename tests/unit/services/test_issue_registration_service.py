# tests/unit/services/test_issue_registration_service.py
from datetime import datetime
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from src.database import Base
from src.models.issue_registration import IssueRegistration  # noqa: F401
from src.services.issue_registration_service import (
    make_ai_issue_key,
    make_static_issue_key,
    register_issue,
    get_analysis_issue_status,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


# ── key helpers ──

def test_make_ai_issue_key_is_64_chars():
    key = make_ai_issue_key("some suggestion text")
    assert len(key) == 64


def test_make_ai_issue_key_deterministic():
    assert make_ai_issue_key("text") == make_ai_issue_key("text")


def test_make_static_issue_key_excludes_line():
    k1 = make_static_issue_key("bandit", "security", "SQL injection")
    k2 = make_static_issue_key("bandit", "security", "SQL injection")
    assert k1 == k2


def test_make_static_issue_key_differs_by_tool():
    k1 = make_static_issue_key("bandit", "security", "msg")
    k2 = make_static_issue_key("pylint", "security", "msg")
    assert k1 != k2


# ── register_issue ──

@pytest.mark.asyncio
async def test_register_issue_success(db):
    with patch(
        "src.services.issue_registration_service.create_issue",
        new=AsyncMock(return_value={
            "number": 44,
            "html_url": "https://github.com/o/r/issues/44",
            "state": "open",
        }),
    ):
        result = await register_issue(
            db,
            analysis_id=1, repo_id=1,
            repo_full_name="owner/repo",
            github_token="tok",
            issue_type="ai_suggestion",
            issue_key="abc123",
            title="T", body="B", labels=["bug"],
        )
    assert result["github_issue_number"] == 44
    assert result["state"] == "open"


@pytest.mark.asyncio
async def test_register_issue_duplicate_raises_value_error(db):
    with patch(
        "src.services.issue_registration_service.create_issue",
        new=AsyncMock(return_value={
            "number": 44, "html_url": "https://github.com/o/r/issues/44", "state": "open"
        }),
    ):
        await register_issue(
            db, analysis_id=1, repo_id=1, repo_full_name="o/r",
            github_token="tok", issue_type="ai_suggestion", issue_key="dup",
            title="T", body="B", labels=[],
        )

    with pytest.raises(ValueError, match="DUPLICATE:44"):
        with patch(
            "src.services.issue_registration_service.create_issue",
            new=AsyncMock(return_value={
                "number": 99, "html_url": "https://github.com/o/r/issues/99", "state": "open"
            }),
        ):
            await register_issue(
                db, analysis_id=1, repo_id=1, repo_full_name="o/r",
                github_token="tok", issue_type="ai_suggestion", issue_key="dup",
                title="T", body="B", labels=[],
            )


# ── get_analysis_issue_status ──

@pytest.mark.asyncio
async def test_get_analysis_issue_status_empty(db):
    result = await get_analysis_issue_status(
        db, analysis_id=99, repo_full_name="o/r", github_token="tok"
    )
    assert result == []


@pytest.mark.asyncio
async def test_get_analysis_issue_status_syncs_stale(db):
    from src.repositories import issue_registration_repo
    issue_registration_repo.create(
        db, analysis_id=1, repo_id=1, issue_type="ai_suggestion",
        issue_key="k1", github_issue_number=44,
    )
    # synced_at이 None이므로 stale — GitHub API 호출 기대
    # synced_at is None so stale — expect GitHub API call
    with patch(
        "src.services.issue_registration_service.get_issue_state",
        new=AsyncMock(return_value="closed"),
    ):
        result = await get_analysis_issue_status(
            db, analysis_id=1, repo_full_name="o/r", github_token="tok"
        )
    assert result[0]["github_issue_state"] == "closed"
    assert result[0]["github_issue_number"] == 44


@pytest.mark.asyncio
async def test_get_analysis_issue_status_skips_fresh_sync(db):
    from src.repositories import issue_registration_repo
    rec = issue_registration_repo.create(
        db, analysis_id=1, repo_id=1, issue_type="ai_suggestion",
        issue_key="k2", github_issue_number=55,
    )
    # 방금 동기화된 것처럼 synced_at 설정
    # Set synced_at as if just synced
    issue_registration_repo.update_state(db, record=rec, state="open")

    with patch(
        "src.services.issue_registration_service.get_issue_state",
        new=AsyncMock(side_effect=Exception("should not be called")),
    ):
        result = await get_analysis_issue_status(
            db, analysis_id=1, repo_full_name="o/r", github_token="tok"
        )
    assert result[0]["github_issue_state"] == "open"


# ── get_repo_issue_summary (Phase 2) ──
from src.services.issue_registration_service import get_repo_issue_summary


@pytest.mark.asyncio
async def test_get_repo_issue_summary_empty(db):
    result = await get_repo_issue_summary(
        db, repo_id=99, repo_full_name="o/r", github_token="tok"
    )
    assert result == []


@pytest.mark.asyncio
async def test_get_repo_issue_summary_returns_with_registration_state(db):
    from src.repositories import issue_registration_repo
    issue_registration_repo.create(
        db, analysis_id=1, repo_id=1, issue_type="static_issue",
        issue_key="sk1", github_issue_number=55,
    )
    with patch(
        "src.services.issue_registration_service.get_issue_state",
        new=AsyncMock(return_value="open"),
    ):
        result = await get_repo_issue_summary(
            db, repo_id=1, repo_full_name="o/r", github_token="tok"
        )
    assert len(result) == 1
    assert result[0]["github_issue_number"] == 55
    assert result[0]["github_issue_state"] == "open"
    assert result[0]["issue_type"] == "static_issue"
    assert "created_at" in result[0]


# ── TOCTOU IntegrityError 핸들러 (lines 70-76) ──

@pytest.mark.asyncio
async def test_register_issue_toctou_integrity_error_raises_duplicate(db):
    # 두 번째 삽입에서 IntegrityError 발생 시 DUPLICATE:N 반환
    # IntegrityError on second insert → raises DUPLICATE:N
    from src.repositories import issue_registration_repo
    # 첫 번째 등록 성공 (issue_key="race_key", number=44)
    # First registration succeeds
    with patch(
        "src.services.issue_registration_service.create_issue",
        new=AsyncMock(return_value={
            "number": 44, "html_url": "https://github.com/o/r/issues/44", "state": "open"
        }),
    ):
        await register_issue(
            db, analysis_id=1, repo_id=1, repo_full_name="o/r",
            github_token="tok", issue_type="ai_suggestion", issue_key="race_key",
            title="T", body="B", labels=[],
        )

    # 두 번째 요청: find_by_key가 None 반환 (find → None), create 시 IntegrityError
    # Second request: find_by_key returns None but create raises IntegrityError (TOCTOU)
    original_find = issue_registration_repo.find_by_key
    call_count = {"n": 0}

    def patched_find(db_, *, repo_id, issue_key):
        call_count["n"] += 1
        # 첫 번째 find (등록 전) → None 반환 (경쟁 조건 시뮬레이션)
        # First find (before insert) → None (simulate race)
        if call_count["n"] == 1:
            return None
        # 두 번째 find (IntegrityError 후) → 기존 레코드 반환
        # Second find (after IntegrityError) → return existing record
        return original_find(db_, repo_id=repo_id, issue_key=issue_key)

    with (
        patch("src.services.issue_registration_service.create_issue",
              new=AsyncMock(return_value={
                  "number": 99, "html_url": "https://github.com/o/r/issues/99", "state": "open"
              })),
        patch.object(issue_registration_repo, "find_by_key", side_effect=patched_find),
        patch.object(issue_registration_repo, "create",
                     side_effect=IntegrityError("UNIQUE constraint failed", None, None)),
    ):
        with pytest.raises(ValueError, match="DUPLICATE:44"):
            await register_issue(
                db, analysis_id=1, repo_id=1, repo_full_name="o/r",
                github_token="tok", issue_type="ai_suggestion", issue_key="race_key",
                title="T", body="B", labels=[],
            )


# ── get_analysis_issue_status — httpx.HTTPError silent pass (lines 113-116) ──

@pytest.mark.asyncio
async def test_get_analysis_issue_status_keeps_state_on_sync_error(db):
    # 동기화 실패(httpx.HTTPError) 시 기존 상태 유지
    # Keeps existing state when sync raises httpx.HTTPError
    from src.repositories import issue_registration_repo
    issue_registration_repo.create(
        db, analysis_id=1, repo_id=1, issue_type="ai_suggestion",
        issue_key="err_key", github_issue_number=44,
    )
    with patch(
        "src.services.issue_registration_service.get_issue_state",
        new=AsyncMock(side_effect=httpx.HTTPError("timeout")),
    ):
        result = await get_analysis_issue_status(
            db, analysis_id=1, repo_full_name="o/r", github_token="tok"
        )
    # 오류 발생해도 기존 "open" 상태 그대로 반환
    # Error occurred but existing "open" state is preserved
    assert result[0]["github_issue_state"] == "open"


# ── get_repo_issue_summary — timezone 정규화 + httpx.HTTPError (lines 144, 155-158) ──

@pytest.mark.asyncio
async def test_get_repo_issue_summary_normalizes_naive_synced_at(db):
    # synced_at이 naive datetime(tzinfo=None)이고 TTL 만료된 경우 → 재동기화
    # When synced_at is a naive datetime past TTL → re-sync occurs
    from src.repositories import issue_registration_repo
    rec = issue_registration_repo.create(
        db, analysis_id=1, repo_id=1, issue_type="static_issue",
        issue_key="naive_key", github_issue_number=77,
    )
    # synced_at을 naive datetime(tzinfo 없음)으로 직접 설정 (SQLite 반환 패턴 모사)
    # Set synced_at as naive datetime (simulating SQLite return pattern)
    rec.github_issue_synced_at = datetime(2020, 1, 1, 0, 0, 0)  # 훨씬 과거, tzinfo 없음
    db.commit()

    with patch(
        "src.services.issue_registration_service.get_issue_state",
        new=AsyncMock(return_value="closed"),
    ):
        result = await get_repo_issue_summary(
            db, repo_id=1, repo_full_name="o/r", github_token="tok"
        )
    # 재동기화 후 "closed" 반환
    # After re-sync, "closed" is returned
    assert result[0]["github_issue_state"] == "closed"


@pytest.mark.asyncio
async def test_get_repo_issue_summary_keeps_state_on_sync_error(db):
    # 동기화 실패(httpx.HTTPError) 시 기존 상태 유지
    # Keeps existing state when sync raises httpx.HTTPError
    from src.repositories import issue_registration_repo
    issue_registration_repo.create(
        db, analysis_id=1, repo_id=1, issue_type="static_issue",
        issue_key="repo_err_key", github_issue_number=88,
    )
    with patch(
        "src.services.issue_registration_service.get_issue_state",
        new=AsyncMock(side_effect=httpx.HTTPError("connection error")),
    ):
        result = await get_repo_issue_summary(
            db, repo_id=1, repo_full_name="o/r", github_token="tok"
        )
    assert result[0]["github_issue_state"] == "open"
