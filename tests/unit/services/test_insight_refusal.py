"""인사이트 두 호출이 공용 도우미를 거친다 — 거절 · Haiku→Sonnet · 기한 라벨 · 부정 캐시 (Issue #1905 ①b).

Both insight calls go through the shared helper: refusals, Haiku-to-Sonnet, the deadline label and the
negative cache. 응답은 SDK 의 실제 타입(Message)이다 — 거절 응답은 본문이 비어 있다.
Responses are real SDK Message objects; a refusal comes back with no content.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anthropic.types import Message
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models.analysis import Analysis
from src.models.claude_api_call import ClaudeApiCall
from src.models.insight_narrative_cache import InsightNarrativeCache
from src.models.repository import Repository
from src.models.user import User
from src.services import dashboard_service, repo_insight_service

_TABLE_MODELS = (Analysis, ClaudeApiCall, InsightNarrativeCache, Repository, User)
if any(m.__tablename__ not in Base.metadata.tables for m in _TABLE_MODELS):
    raise RuntimeError("side-effect ORM import 소실 — 테이블 미등록 / ORM import lost, table unregistered")

_KPI = {
    "analysis_count": 2, "avg_score": 60, "grade": "D", "score_delta": None,
    "high_security_count": 0, "top_recurring_issue": None, "top_recurring_count": 0,
}


def _message(*, model: str, stop_reason: str = "end_turn", text: str | None = '{"text": "ok"}') -> Message:
    return Message.model_validate({
        "id": "msg", "type": "message", "role": "assistant", "model": model,
        "content": [{"type": "text", "text": text}] if text is not None else [],
        "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 12, "output_tokens": 5, "cache_read_input_tokens": 0,
                  "cache_creation_input_tokens": 0},
    })


def _client(*responses) -> MagicMock:
    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=list(responses))
    return client


def _rows(cost_row) -> list[tuple]:
    return [(c.kwargs["model"], c.kwargs["status"], c.kwargs.get("error_type", "")) for c in cost_row.call_args_list]


def _refused(model: str) -> Message:
    return _message(model=model, stop_reason="refusal", text=None)


async def test_dashboard_insight_whole_chain_refusal_returns_no_text():
    client = _client(_refused("claude-haiku-4-5"), _refused("claude-sonnet-5"))
    with patch.object(dashboard_service, "log_claude_api_call") as cost_row:
        text = await dashboard_service._call_insight_claude_api(  # pylint: disable=protected-access
            client, "claude-haiku-4-5", "prompt", user_id=3)
    assert text is None
    assert _rows(cost_row) == [("claude-haiku-4-5", "refused", ""), ("claude-sonnet-5", "refused", "")]
    assert {c.kwargs["user_id"] for c in cost_row.call_args_list} == {3}


async def test_dashboard_haiku_refusal_is_answered_by_sonnet():
    client = _client(_refused("claude-haiku-4-5"), _message(model="claude-sonnet-5", text='{"focus_areas": []}'))
    with patch.object(dashboard_service, "log_claude_api_call") as cost_row:
        text = await dashboard_service._call_insight_claude_api(  # pylint: disable=protected-access
            client, "claude-haiku-4-5", "prompt", user_id=3)
    assert text == '{"focus_areas": []}'
    assert _rows(cost_row) == [("claude-haiku-4-5", "refused", ""), ("claude-sonnet-5", "success", "")]


async def test_dashboard_insight_deadline_row_keeps_the_timeout_label(monkeypatch):
    # 페이지 기한은 호출부의 것이다 — 기한에 걸린 호출의 행은 예전처럼 TimeoutError 로 하나
    # The page deadline belongs to the caller; the call it cut off still gets one TimeoutError row.
    monkeypatch.setattr(dashboard_service, "ANTHROPIC_PAGE_DEADLINE_SECONDS", 0.05)

    async def _hang(**_kwargs):
        await asyncio.Event().wait()

    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=_hang)
    with patch.object(dashboard_service, "log_claude_api_call") as cost_row:
        text = await dashboard_service._call_insight_claude_api(  # pylint: disable=protected-access
            client, "claude-haiku-4-5", "prompt", user_id=3)
    assert text is None
    assert _rows(cost_row) == [("claude-haiku-4-5", "error", "TimeoutError")]
    assert cost_row.call_args.kwargs["duration_ms"] >= 40


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def owner(db):  # pylint: disable=redefined-outer-name
    user = User(github_id=f"rf-{uuid.uuid4().hex[:8]}", github_login="refusal", email="rf@x.com", display_name="R")
    db.add(user)
    db.commit()
    repo = Repository(full_name=f"refusal/r-{uuid.uuid4().hex[:6]}", user_id=user.id)
    db.add(repo)
    db.commit()
    now = datetime.now(timezone.utc)
    for hours, score in ((1, 80), (2, 85)):
        db.add(Analysis(repo_id=repo.id, commit_sha=f"rf{uuid.uuid4().hex}", score=score, grade="B", result={},
                        created_at=(now - timedelta(hours=hours)).replace(tzinfo=None)))
    db.commit()
    return user.id, repo.id


async def _repo_narrative(db, owner, client, *, attribution=None):  # pylint: disable=redefined-outer-name
    user_id, repo_id = owner
    factory = MagicMock(return_value=client)
    with patch.object(repo_insight_service, "new_async_anthropic", factory), \
         patch.object(repo_insight_service, "aclose_anthropic_client", AsyncMock()), \
         patch.object(repo_insight_service, "log_claude_api_call", MagicMock()) as cost_row:
        out = await repo_insight_service.repo_insight_narrative(
            db, repo_id, 30, repo_full_name="refusal/r", kpi=_KPI, recurring=[], user_id=user_id, language="en")
    if attribution is not None:
        attribution.extend((c.kwargs["repo_id"], c.kwargs["user_id"]) for c in cost_row.call_args_list)
    return out, _rows(cost_row), factory.call_count


async def test_repo_insight_refusal_is_api_error_and_the_next_call_short_circuits(db, owner, monkeypatch):  # pylint: disable=redefined-outer-name
    # 거절도 벤더 쪽 실패다 — api_error 로 답하고, 부정 캐시가 다음 호출에서 같은 status 로 되살린다
    # A refusal is a vendor-side failure: api_error now, and the negative cache brings back the same status.
    monkeypatch.setattr(repo_insight_service.settings, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(repo_insight_service.settings, "claude_insight_model", "claude-haiku-4-5")
    attribution: list = []
    out, rows, _ = await _repo_narrative(db, owner, _client(_refused("claude-haiku-4-5"),
                                                            _refused("claude-sonnet-5")), attribution=attribution)
    assert out == {"text": "", "status": "api_error"}
    assert rows == [("claude-haiku-4-5", "refused", ""), ("claude-sonnet-5", "refused", "")]
    # 도우미가 쓴 행(앞 거절)도 리포 · 사용자에 귀속된다 / helper-written rows keep the repo and user attribution
    assert attribution == [(owner[1], owner[0])] * 2
    again, rows_again, calls = await _repo_narrative(db, owner, _client())
    assert (again, rows_again, calls) == ({"text": "", "status": "api_error"}, [], 0)


async def test_repo_haiku_refusal_is_answered_by_sonnet(db, owner, monkeypatch):  # pylint: disable=redefined-outer-name
    monkeypatch.setattr(repo_insight_service.settings, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(repo_insight_service.settings, "claude_insight_model", "claude-haiku-4-5")
    out, rows, _ = await _repo_narrative(db, owner, _client(_refused("claude-haiku-4-5"),
                                                            _message(model="claude-sonnet-5", text='{"text": "진단"}')))
    assert out == {"text": "진단", "status": "success"}
    assert rows == [("claude-haiku-4-5", "refused", ""), ("claude-sonnet-5", "success", "")]


async def test_repo_refusal_with_a_failing_negative_cache_write_keeps_one_row_per_attempt(db, owner, monkeypatch):  # pylint: disable=redefined-outer-name
    # 거절 행을 쓴 뒤 부정 캐시 기록이 실패해도 except 가 같은 응답의 행을 또 쓰지 않는다
    # When the negative-cache write fails after the refused row, the except path does not write that response again.
    monkeypatch.setattr(repo_insight_service.settings, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(repo_insight_service.settings, "claude_insight_model", "claude-haiku-4-5")
    monkeypatch.setattr(repo_insight_service, "_record_narrative_error",
                        MagicMock(side_effect=[RuntimeError("cache write failed"), None]))
    out, rows, _ = await _repo_narrative(db, owner, _client(_refused("claude-haiku-4-5"),
                                                            _refused("claude-sonnet-5")))
    assert rows == [("claude-haiku-4-5", "refused", ""), ("claude-sonnet-5", "refused", "")]
    assert out["status"] == "internal_error"
