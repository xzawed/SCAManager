# tests/unit/services/test_issue_registration_service.py
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
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
    rec = issue_registration_repo.create(
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
