"""C1 Phase 3 T3.3 — insight_narrative user_id 귀속 스레딩 단위 테스트.

`insight_narrative` 가 보유한 user_id 가 `_call_insight_claude_api` 를 거쳐
`log_claude_api_call` 성공/에러 양 경로에 그대로 전달되는지 검증한다
(비용 귀속, T3.1 영속화 후속).

Unit tests for insight_narrative's user_id attribution threading (C1 Phase 3 T3.3).
Verifies user_id flows through `_call_insight_claude_api` into both the success and
error paths of `log_claude_api_call` (cost attribution, follow-up to T3.1 persistence).
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database import Base
from src.models.analysis import Analysis  # noqa: F401  (Base.metadata 등록)
from src.models.repository import Repository  # noqa: F401
from src.models.user import User  # noqa: F401


@pytest.fixture()
def db():
    """모든 ORM 테이블이 생성된 in-memory SQLite 세션."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def seeded_repo(db):
    """analysis_count > 0 조건 충족용 user + repo + Analysis 2건 seed."""
    import uuid  # pylint: disable=import-outside-toplevel
    from datetime import datetime, timedelta, timezone  # pylint: disable=import-outside-toplevel

    user = User(github_id=101, github_login="u3-3", email="u33@x.com", display_name="U33")
    db.add(user)
    db.commit()
    db.refresh(user)
    repo = Repository(full_name="u33/repo", user_id=user.id)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    now = datetime.now(timezone.utc)
    for i in range(2):
        db.add(Analysis(
            repo_id=repo.id, commit_sha=f"sha-{uuid.uuid4().hex}",
            score=80, grade="B", result={}, created_at=now - timedelta(hours=i + 1),
        ))
    db.commit()
    return repo


async def test_insight_narrative_passes_user_id_to_log_on_success(db, seeded_repo):
    """성공 응답 시 log_claude_api_call 에 user_id 가 전달된다.
    user_id is forwarded to log_claude_api_call on the success path."""
    response_obj = MagicMock()
    response_obj.content = [MagicMock(text=json.dumps({
        "positive_highlights": [], "focus_areas": [], "key_metrics": [], "next_actions": [],
    }))]
    response_obj.usage = MagicMock(
        input_tokens=50, output_tokens=20,
        cache_read_input_tokens=0, cache_creation_input_tokens=0,
    )
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=response_obj)

    with patch("src.services.dashboard_service.anthropic.AsyncAnthropic", return_value=fake_client), \
         patch("src.services.dashboard_service.log_claude_api_call") as mock_log:
        from src.services.dashboard_service import insight_narrative  # noqa: PLC0415

        await insight_narrative(db, days=7, api_key="sk-test", user_id=seeded_repo.user_id)

    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs.get("user_id") == seeded_repo.user_id


async def test_insight_narrative_passes_user_id_to_log_on_error(db, seeded_repo):
    """예외 발생 시에도 log_claude_api_call 에 user_id 가 전달된다.
    user_id is forwarded to log_claude_api_call even on the error path."""
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(side_effect=RuntimeError("boom"))

    with patch("src.services.dashboard_service.anthropic.AsyncAnthropic", return_value=fake_client), \
         patch("src.services.dashboard_service.log_claude_api_call") as mock_log:
        from src.services.dashboard_service import insight_narrative  # noqa: PLC0415

        await insight_narrative(db, days=7, api_key="sk-test", user_id=seeded_repo.user_id)

    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs.get("user_id") == seeded_repo.user_id


async def test_insight_narrative_defaults_user_id_to_none(db, seeded_repo):
    """user_id 미전달 시 log_claude_api_call 에 None 이 전달된다 (회귀 가드).
    Without an explicit user_id, log_claude_api_call receives None (regression guard)."""
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(side_effect=RuntimeError("boom"))

    with patch("src.services.dashboard_service.anthropic.AsyncAnthropic", return_value=fake_client), \
         patch("src.services.dashboard_service.log_claude_api_call") as mock_log:
        from src.services.dashboard_service import insight_narrative  # noqa: PLC0415

        await insight_narrative(db, days=7, api_key="sk-test")

    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs.get("user_id") is None
