"""AI 인사이트 생성 한도 — 기간 맞추기 · 사용자별 하루 한도 (회고 원장 L17 P2-7).

AI insight generation limits: window snapping and the per-user daily cap.

계약
- 생성 기간은 화면 값으로만 — 그 밖은 덮는 가장 작은 화면 값, 가장 큰 값보다 크면 가장 큰 값.
- 하루 한도 = 오늘(UTC) 그 사용자에게 귀속된 Claude 호출 수. 어제 호출 · 다른 사용자 · 리뷰 호출(사용자 귀속 없음)은 세지 않는다.
- 상한에 닿으면 Claude 를 부르지 않는다 — 마지막 결과(만료돼도)에 «오늘 한도» 표시, 없으면 한도 상태.
- 상한은 캐시 · 부정 캐시 **뒤** 다 — 신선한 캐시는 상한과 무관하게 그대로 준다.
Contract: on-screen windows only; the cap counts today's (UTC) calls attributed to the user; at the cap no new
call — the latest result flagged, or the limit status; a fresh cache is served regardless of the cap.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src import constants
from src.database import Base
from src.models.analysis import Analysis
from src.models.claude_api_call import ClaudeApiCall
from src.models.insight_narrative_cache import InsightNarrativeCache
from src.models.repository import Repository
from src.models.user import User
from src.repositories import insight_narrative_cache_repo
from src.services import dashboard_service, insight_cost_guard, repo_insight_service

_TABLE_MODELS = (Analysis, ClaudeApiCall, InsightNarrativeCache, Repository, User)
if any(m.__tablename__ not in Base.metadata.tables for m in _TABLE_MODELS):
    raise RuntimeError("ORM import 소실 — 테이블 미등록 / ORM import lost, table unregistered")

_CAP = 2  # 시험은 상한을 작게 — 쓰는 쪽이 `constants.X` 를 부를 때 읽는다 / small cap, read at call time
_KPI = {
    "analysis_count": 2, "avg_score": 60, "grade": "D", "score_delta": None,
    "high_security_count": 0, "top_recurring_issue": None, "top_recurring_count": 0,
}
_CARDS = {"positive_highlights": ["옛 서술"], "focus_areas": ["b"],
          "key_metrics": [{"label": "x", "value": "1", "delta": "0"}], "next_actions": ["c"]}


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def owner(db):
    u = User(github_id=f"cap-{uuid.uuid4().hex[:8]}", github_login="capper", email="c@x.com", display_name="C")
    db.add(u)
    db.commit()
    r = Repository(full_name=f"capper/r-{uuid.uuid4().hex[:6]}", user_id=u.id)
    db.add(r)
    db.commit()
    now = datetime.now(timezone.utc)
    for i, score in enumerate((80, 85)):
        db.add(Analysis(repo_id=r.id, commit_sha=f"cap{uuid.uuid4().hex}", score=score, grade="B", result={},
                        created_at=(now - timedelta(hours=i + 1)).replace(tzinfo=None)))
    db.commit()
    return u.id, r.id


@pytest.fixture()
def small_cap(monkeypatch):
    monkeypatch.setattr(constants, "INSIGHT_GENERATIONS_PER_USER_PER_DAY", _CAP)
    return _CAP


def _calls(db, *, user_id, repo_id=None, n, at=None):
    when = (at or datetime.now(timezone.utc)).replace(tzinfo=None)
    for _ in range(n):
        db.add(ClaudeApiCall(model="claude-haiku-4-5", user_id=user_id, repo_id=repo_id, created_at=when))
    db.commit()


class _Sdk:
    """클라이언트 팩토리 · 종료 · 비용 로그를 가로챈다 — 팩토리 호출 수가 «Claude 를 불렀는가» 의 증거다."""

    def __init__(self, module, reply_text: str):
        block = MagicMock()
        block.type = "text"
        block.text = reply_text
        resp = MagicMock()
        resp.content = [block]
        resp.stop_reason = "end_turn"
        resp.usage = MagicMock(input_tokens=10, output_tokens=5, cache_read_input_tokens=0,
                               cache_creation_input_tokens=0)
        client = MagicMock()
        client.messages.create = AsyncMock(return_value=resp)
        self.factory = MagicMock(return_value=client)
        self._patches = [patch.object(module, "new_async_anthropic", self.factory),
                         patch.object(module, "aclose_anthropic_client", AsyncMock()),
                         patch.object(module, "log_claude_api_call", MagicMock())]

    def __enter__(self):
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self._patches):
            p.stop()


# ─── 기간 접기 ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("asked, dashboard, repo", [
    (1, 1, 7), (2, 7, 7), (7, 7, 7), (8, 30, 30), (13, 30, 30), (30, 30, 30), (31, 90, 90), (90, 90, 90),
    (91, 90, 90), (365, 90, 90),
])
def test_windows_snap_up_to_an_on_screen_value(asked, dashboard, repo):
    assert insight_cost_guard.snap_days(asked, constants.INSIGHT_DAYS_DASHBOARD) == dashboard
    assert insight_cost_guard.snap_days(asked, constants.INSIGHT_DAYS_REPO) == repo


# ─── 하루 상한 — 무엇을 세는가 ─────────────────────────────────────────────────


def test_the_cap_counts_only_todays_calls_attributed_to_the_user(db, owner, small_cap):
    user_id, repo_id = owner
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    _calls(db, user_id=user_id, n=small_cap, at=yesterday)            # 어제 — 세지 않는다
    _calls(db, user_id=None, repo_id=repo_id, n=small_cap)            # 리뷰 호출 — 사용자 귀속 없음
    other = User(github_id=f"cap-{uuid.uuid4().hex[:8]}", github_login="o", email="o@x.com", display_name="O")
    db.add(other)
    db.commit()
    _calls(db, user_id=other.id, n=small_cap)                         # 다른 사용자
    _calls(db, user_id=user_id, n=small_cap - 1)                      # 오늘 하나 모자람
    assert not insight_cost_guard.daily_limit_reached(db, user_id=user_id)
    _calls(db, user_id=user_id, n=1)
    assert insight_cost_guard.daily_limit_reached(db, user_id=user_id)


# ─── 대시보드 서술 ─────────────────────────────────────────────────────────────


async def _dashboard(db, user_id, days=7):
    return await dashboard_service.insight_narrative(db, days=days, api_key="sk-test", user_id=user_id,
                                                     language="en")


async def test_dashboard_at_the_cap_shows_the_last_result_without_calling_claude(db, owner, small_cap):
    user_id, _ = owner
    two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
    insight_narrative_cache_repo.upsert(db, user_id=user_id, days=7, language="en",
                                        response={"status": "success", "days": 7, **_CARDS}, now=two_hours_ago)
    _calls(db, user_id=user_id, n=small_cap)
    with _Sdk(dashboard_service, json.dumps(_CARDS)) as sdk:
        out = await _dashboard(db, user_id)
    assert sdk.factory.call_count == 0, "한도인데 Claude 를 불렀다"
    assert out["status"] == "success" and out["daily_limit"] is True and out["daily_cap"] == small_cap
    assert out["positive_highlights"] == ["옛 서술"]


async def test_dashboard_at_the_cap_without_a_result_shows_the_limit(db, owner, small_cap):
    user_id, _ = owner
    _calls(db, user_id=user_id, n=small_cap)
    with _Sdk(dashboard_service, json.dumps(_CARDS)) as sdk:
        out = await _dashboard(db, user_id)
    assert sdk.factory.call_count == 0
    assert out["status"] == "daily_limit" and out["daily_cap"] == small_cap


async def test_dashboard_fresh_cache_is_served_regardless_of_the_cap(db, owner, small_cap):
    user_id, _ = owner
    insight_narrative_cache_repo.upsert(db, user_id=user_id, days=7, language="en",
                                        response={"status": "success", "days": 7, **_CARDS})
    _calls(db, user_id=user_id, n=small_cap)
    with _Sdk(dashboard_service, json.dumps(_CARDS)) as sdk:
        out = await _dashboard(db, user_id)
    assert sdk.factory.call_count == 0
    assert out["status"] == "success" and "daily_limit" not in out


async def test_dashboard_below_the_cap_generates(db, owner, small_cap):
    user_id, _ = owner
    _calls(db, user_id=user_id, n=small_cap - 1)
    with _Sdk(dashboard_service, json.dumps(_CARDS)) as sdk:
        out = await _dashboard(db, user_id)
    assert sdk.factory.call_count == 1
    assert out["status"] == "success" and "daily_limit" not in out


async def test_dashboard_generates_under_the_snapped_window(db, owner):
    """화면에 없는 기간(13)은 덮는 화면 값(30)으로 — 캐시 키도 30 이다."""
    user_id, _ = owner
    with _Sdk(dashboard_service, json.dumps(_CARDS)) as sdk:
        out = await _dashboard(db, user_id, days=13)
    assert sdk.factory.call_count == 1
    assert out["days"] == 30
    assert [row.days for row in db.query(InsightNarrativeCache).all()] == [30]


# ─── 리포 서술 ────────────────────────────────────────────────────────────────


async def _repo(db, owner_ids):
    user_id, repo_id = owner_ids
    with patch.object(repo_insight_service, "settings") as s:
        s.anthropic_api_key = "sk-ant-test"
        s.claude_insight_model = "claude-haiku-4-5"
        return await repo_insight_service.repo_insight_narrative(
            db, repo_id, 30, repo_full_name="capper/r", kpi=_KPI, recurring=[], user_id=user_id, language="en")


async def test_repo_at_the_cap_shows_the_last_result_without_calling_claude(db, owner, small_cap):
    user_id, repo_id = owner
    two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
    insight_narrative_cache_repo.upsert_repo(db, user_id=user_id, repo_id=repo_id, days=30, language="en",
                                             response={"text": "옛 진단", "status": "success"}, now=two_hours_ago)
    _calls(db, user_id=user_id, n=small_cap)
    with _Sdk(repo_insight_service, json.dumps({"text": "새 진단"})) as sdk:
        out = await _repo(db, owner)
    assert sdk.factory.call_count == 0
    assert out == {"text": "옛 진단", "status": "success", "daily_limit": True, "daily_cap": small_cap}


async def test_repo_at_the_cap_without_a_result_shows_the_limit(db, owner, small_cap):
    user_id, _ = owner
    _calls(db, user_id=user_id, n=small_cap)
    with _Sdk(repo_insight_service, json.dumps({"text": "새 진단"})) as sdk:
        out = await _repo(db, owner)
    assert sdk.factory.call_count == 0
    assert out == {"text": "", "status": "daily_limit", "daily_cap": small_cap}


async def test_repo_below_the_cap_generates(db, owner, small_cap):
    user_id, _ = owner
    _calls(db, user_id=user_id, n=small_cap - 1)
    with _Sdk(repo_insight_service, json.dumps({"text": "새 진단"})) as sdk:
        out = await _repo(db, owner)
    assert sdk.factory.call_count == 1
    assert out["status"] == "success" and "daily_limit" not in out
