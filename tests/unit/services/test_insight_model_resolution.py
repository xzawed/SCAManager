"""리포 인사이트의 모델 선택이 카탈로그 해석을 거친다 — create 와 비용 행이 같은 판 (Issue #1905 ①a Task 4).

Repo insight model selection goes through the catalog resolver; the create call and the cost row use the same model.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models.analysis import Analysis
from src.models.claude_api_call import ClaudeApiCall
from src.models.insight_narrative_cache import InsightNarrativeCache
from src.models.repository import Repository
from src.models.user import User
from src.services import repo_insight_service
from src.shared import model_catalog as mc

_TABLE_MODELS = (Analysis, ClaudeApiCall, InsightNarrativeCache, Repository, User)
if any(m.__tablename__ not in Base.metadata.tables for m in _TABLE_MODELS):
    raise RuntimeError("side-effect ORM import 소실 — 테이블 미등록 / ORM import lost, table unregistered")

_KPI = {
    "analysis_count": 2, "avg_score": 60, "grade": "D", "score_delta": None,
    "high_security_count": 0, "top_recurring_issue": None, "top_recurring_count": 0,
}


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def owner(db):
    user = User(github_id=f"mr-{uuid.uuid4().hex[:8]}", github_login="resolver", email="r@x.com", display_name="R")
    db.add(user)
    db.commit()
    repo = Repository(full_name=f"resolver/r-{uuid.uuid4().hex[:6]}", user_id=user.id)
    db.add(repo)
    db.commit()
    now = datetime.now(timezone.utc)
    for hours, score in ((1, 80), (2, 85)):
        db.add(Analysis(repo_id=repo.id, commit_sha=f"mr{uuid.uuid4().hex}", score=score, grade="B", result={},
                        created_at=(now - timedelta(hours=hours)).replace(tzinfo=None)))
    db.commit()
    return user.id, repo.id


async def test_repo_insight_calls_resolved_model(db, owner):
    user_id, repo_id = owner
    mc.set_verified("haiku", "claude-haiku-5-5")
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps({"text": "진단"})
    response = MagicMock()
    response.content = [block]
    response.stop_reason = "end_turn"
    response.usage = MagicMock(input_tokens=10, output_tokens=5, cache_read_input_tokens=0,
                               cache_creation_input_tokens=0)
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=response)
    with patch.object(repo_insight_service, "new_async_anthropic", MagicMock(return_value=client)), \
         patch.object(repo_insight_service, "aclose_anthropic_client", AsyncMock()), \
         patch.object(repo_insight_service, "log_claude_api_call", MagicMock()) as cost_row, \
         patch.object(repo_insight_service, "settings") as s:
        s.anthropic_api_key = "sk-ant-test"
        s.claude_insight_model = "auto:haiku"
        out = await repo_insight_service.repo_insight_narrative(
            db, repo_id, 30, repo_full_name="resolver/r", kpi=_KPI, recurring=[], user_id=user_id, language="en")
    assert out["status"] == "success"
    assert client.messages.create.await_args.kwargs["model"] == "claude-haiku-5-5"
    assert cost_row.call_args.kwargs["model"] == "claude-haiku-5-5"
