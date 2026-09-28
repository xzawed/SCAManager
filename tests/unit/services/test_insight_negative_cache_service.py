"""페이지 내러티브 부정 캐시 — 창 안의 재조회는 Anthropic 클라이언트를 만들지 않는다.

Page narrative negative cache — a reload inside the window never constructs an Anthropic client.

실측(수정 전): 45 s 기한에 걸린 뒤 새로 고침 8번 = 유료 시도 8번. 실패 행이 태어날 때 만료라
성공 캐시 조회로는 막히지 않았다. 여기서는 「클라이언트 팩토리가 불렸는가」로 잰다 — 비용이
생기는 유일한 입구다.
Measured before the fix: 8 reloads after a 45 s deadline miss = 8 paid attempts. The client
factory is the single entry point where cost starts, so that is what these tests count.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import httpx
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
from src.repositories import insight_narrative_cache_repo
from src.services import dashboard_service, repo_insight_service

# KPI 비용 집계가 claude_api_calls 를 읽는다 — 단독 실행에서도 테이블이 있도록 등록을 확인한다.
# The KPI cost aggregate reads claude_api_calls; assert registration so a lone run has the table.
_TABLE_MODELS = (ClaudeApiCall, InsightNarrativeCache, Repository, User)
if any(m.__tablename__ not in Base.metadata.tables for m in _TABLE_MODELS):
    raise RuntimeError("ORM import 소실 — 테이블 미등록 / ORM import lost, table unregistered")

_KPI = {
    "analysis_count": 2, "avg_score": 60, "grade": "D", "score_delta": None,
    "high_security_count": 0, "top_recurring_issue": None, "top_recurring_count": 0,
}
_NO_DATA_KPI = {**_KPI, "analysis_count": 0}


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def owner(db):
    """사용자 1 + 소유 리포 1 — (user_id, repo_id) 를 돌려준다."""
    u = User(github_id="negcache-1", github_login="negcache", email="n@x.com", display_name="N")
    db.add(u)
    db.commit()
    r = Repository(full_name=f"negcache/r-{uuid.uuid4().hex[:6]}", user_id=u.id)
    db.add(r)
    db.commit()
    return u.id, r.id


@pytest.fixture()
def t0():
    return datetime.now(timezone.utc)


def _seed_analyses(db, repo_id, t0):
    for i, score in enumerate((80, 85)):
        db.add(Analysis(repo_id=repo_id, commit_sha=f"neg{uuid.uuid4().hex}", score=score, grade="B",
                        result={}, created_at=(t0 - timedelta(hours=i + 1)).replace(tzinfo=None)))
    db.commit()


def _text_response(text: str, *, stop_reason: str = "end_turn") -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    resp.stop_reason = stop_reason
    resp.usage = MagicMock(input_tokens=100, output_tokens=50,
                           cache_read_input_tokens=0, cache_creation_input_tokens=0)
    return resp


def _connection_error() -> Exception:
    return anthropic.APIConnectionError(
        message="connection failed",
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )


class _Sdk:
    """클라이언트 팩토리·종료·비용 로그를 한 번에 가로챈다 — 호출 수가 증거다."""

    def __init__(self, module, create):
        self.module = module
        client = MagicMock()
        client.messages.create = create
        self.factory = MagicMock(return_value=client)
        self.log = MagicMock()
        self._patches = [
            patch.object(module, "new_async_anthropic", self.factory),
            patch.object(module, "aclose_anthropic_client", AsyncMock()),
            patch.object(module, "log_claude_api_call", self.log),
        ]

    def __enter__(self):
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self._patches):
            p.stop()


# ─── 대시보드 ─────────────────────────────────────────────────────────────────

_DASH_FAILURES = {
    "api_error": lambda: AsyncMock(side_effect=_connection_error()),
    "parse_error": lambda: AsyncMock(return_value=_text_response("JSON 아님 {{{")),
}


async def _dash(db, user_id, *, now, refresh=False):
    return await dashboard_service.insight_narrative(
        db, days=7, now=now, api_key="sk-test", user_id=user_id, refresh=refresh, language="en",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", sorted(_DASH_FAILURES))
async def test_dashboard_reload_inside_ttl_makes_no_client(db, owner, t0, status):
    user_id, repo_id = owner
    _seed_analyses(db, repo_id, t0)
    with _Sdk(dashboard_service, _DASH_FAILURES[status]()) as sdk, \
         patch.object(dashboard_service, "dashboard_kpi", wraps=dashboard_service.dashboard_kpi) as kpi, \
         patch.object(insight_narrative_cache_repo, "record_error",
                      wraps=insight_narrative_cache_repo.record_error) as rec:
        first = await _dash(db, user_id, now=t0)
        assert first["status"] == status
        assert sdk.factory.call_count == 1 and sdk.log.call_count == 1 and kpi.call_count == 1

        second = await _dash(db, user_id, now=t0 + timedelta(seconds=10))

    assert second["status"] == status
    assert sdk.factory.call_count == 1, "창 안의 재조회가 Anthropic 클라이언트를 또 만들었다"
    assert sdk.log.call_count == 1, "호출하지 않았는데 비용 행을 남겼다"
    assert kpi.call_count == 1, "단락은 KPI 집계보다 앞서야 한다"
    assert rec.call_count == 1, "단락이 실패를 또 기록했다"
    assert db.query(InsightNarrativeCache).one().error_count == 1
    assert second["positive_highlights"] == [] and second["days"] == 7


@pytest.mark.asyncio
async def test_dashboard_refresh_bypasses_the_negative_cache(db, owner, t0):
    user_id, repo_id = owner
    _seed_analyses(db, repo_id, t0)
    with _Sdk(dashboard_service, _DASH_FAILURES["api_error"]()) as sdk:
        await _dash(db, user_id, now=t0)
        again = await _dash(db, user_id, now=t0 + timedelta(seconds=10), refresh=True)
    assert again["status"] == "api_error"
    assert sdk.factory.call_count == 2


@pytest.mark.asyncio
async def test_dashboard_calls_again_after_the_ttl(db, owner, t0):
    user_id, repo_id = owner
    _seed_analyses(db, repo_id, t0)
    with _Sdk(dashboard_service, _DASH_FAILURES["api_error"]()) as sdk:
        await _dash(db, user_id, now=t0)
        await _dash(db, user_id, now=t0 + timedelta(seconds=121))
    assert sdk.factory.call_count == 2


@pytest.mark.asyncio
async def test_dashboard_no_data_does_not_short_circuit(db, owner, t0):
    """`no_data` 뒤 데이터가 생기면 창 안이라도 바로 부른다."""
    user_id, repo_id = owner
    with _Sdk(dashboard_service, _DASH_FAILURES["api_error"]()) as sdk:
        first = await _dash(db, user_id, now=t0)
        assert first["status"] == "no_data" and sdk.factory.call_count == 0
        _seed_analyses(db, repo_id, t0)
        second = await _dash(db, user_id, now=t0 + timedelta(seconds=10))
    assert sdk.factory.call_count == 1
    assert second["status"] == "api_error"


@pytest.mark.asyncio
async def test_dashboard_recorded_class_name_is_reported_as_api_error(db, owner, t0):
    """대시보드 키에 status 가 아닌 값이 있어도 응답 status 계약(api_error/parse_error) 밖으로 새지 않는다."""
    user_id, repo_id = owner
    _seed_analyses(db, repo_id, t0)
    insight_narrative_cache_repo.record_error(
        db, user_id=user_id, days=7, language="en", error_type="APITimeoutError", now=t0,
    )
    with _Sdk(dashboard_service, _DASH_FAILURES["api_error"]()) as sdk:
        out = await _dash(db, user_id, now=t0 + timedelta(seconds=5))
    assert out["status"] == "api_error"
    assert sdk.factory.call_count == 0


# ─── 리포 ─────────────────────────────────────────────────────────────────────

_REPO_FAILURES = {
    "api_error": lambda: AsyncMock(side_effect=_connection_error()),
    "internal_error": lambda: AsyncMock(return_value=_text_response("JSON 아님 {{{")),
}


async def _repo(db, owner, *, now, refresh=False, kpi=None):
    user_id, repo_id = owner
    with patch.object(repo_insight_service, "settings") as s:
        s.anthropic_api_key = "sk-ant-test"
        s.claude_insight_model = "claude-haiku-4-5"
        return await repo_insight_service.repo_insight_narrative(
            db, repo_id, 30, repo_full_name="negcache/r", kpi=kpi or _KPI, recurring=[],
            now=now, refresh=refresh, user_id=user_id, language="en",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", sorted(_REPO_FAILURES))
async def test_repo_reload_inside_ttl_makes_no_client(db, owner, t0, status):
    with _Sdk(repo_insight_service, _REPO_FAILURES[status]()) as sdk, \
         patch.object(insight_narrative_cache_repo, "record_error_repo",
                      wraps=insight_narrative_cache_repo.record_error_repo) as rec:
        first = await _repo(db, owner, now=t0)
        assert first == {"text": "", "status": status}
        assert sdk.factory.call_count == 1 and sdk.log.call_count == 1

        second = await _repo(db, owner, now=t0 + timedelta(seconds=10))

    assert second == {"text": "", "status": status}
    assert sdk.factory.call_count == 1, "창 안의 재조회가 Anthropic 클라이언트를 또 만들었다"
    assert sdk.log.call_count == 1, "호출하지 않았는데 비용 행을 남겼다"
    assert rec.call_count == 1, "단락이 실패를 또 기록했다"


@pytest.mark.asyncio
async def test_repo_refresh_bypasses_the_negative_cache(db, owner, t0):
    with _Sdk(repo_insight_service, _REPO_FAILURES["api_error"]()) as sdk:
        await _repo(db, owner, now=t0)
        await _repo(db, owner, now=t0 + timedelta(seconds=10), refresh=True)
    assert sdk.factory.call_count == 2


@pytest.mark.asyncio
async def test_repo_calls_again_after_the_ttl(db, owner, t0):
    with _Sdk(repo_insight_service, _REPO_FAILURES["api_error"]()) as sdk:
        await _repo(db, owner, now=t0)
        await _repo(db, owner, now=t0 + timedelta(seconds=121))
    assert sdk.factory.call_count == 2


@pytest.mark.asyncio
async def test_repo_no_data_does_not_short_circuit(db, owner, t0):
    with _Sdk(repo_insight_service, _REPO_FAILURES["api_error"]()) as sdk:
        first = await _repo(db, owner, now=t0, kpi=_NO_DATA_KPI)
        assert first["status"] == "no_data" and sdk.factory.call_count == 0
        second = await _repo(db, owner, now=t0 + timedelta(seconds=10))
    assert sdk.factory.call_count == 1
    assert second["status"] == "api_error"


@pytest.mark.asyncio
@pytest.mark.parametrize("recorded, status", [
    ("TimeoutError", "api_error"),        # 페이지 기한 초과로 기록된 것 / recorded page-deadline miss
    ("APITimeoutError", "api_error"),
    ("RateLimitError", "api_error"),
    ("max_tokens", "internal_error"),
    ("JSONDecodeError", "internal_error"),
])
async def test_repo_short_circuit_maps_the_recorded_class(db, owner, t0, recorded, status):
    user_id, repo_id = owner
    insight_narrative_cache_repo.record_error_repo(
        db, user_id=user_id, repo_id=repo_id, days=30, language="en", error_type=recorded, now=t0,
    )
    with _Sdk(repo_insight_service, _REPO_FAILURES["api_error"]()) as sdk:
        out = await _repo(db, owner, now=t0 + timedelta(seconds=5))
    assert out == {"text": "", "status": status}
    assert sdk.factory.call_count == 0


@pytest.mark.parametrize("recorded, status", [
    ("TimeoutError", "api_error"),
    ("APIError", "api_error"),
    ("APIConnectionError", "api_error"),
    ("APITimeoutError", "api_error"),
    ("RateLimitError", "api_error"),            # 'API' 접두 없는 벤더 / vendor without an API prefix
    ("InternalServerError", "api_error"),
    ("JSONDecodeError", "internal_error"),      # 'Error' 로 끝나도 우리 쪽 / ends in Error, still ours
    ("AttributeError", "internal_error"),
    ("RuntimeError", "internal_error"),
    ("max_tokens", "internal_error"),
    ("AnthropicError", "internal_error"),       # SDK 루트는 APIError 하위가 아니다 / SDK root, not APIError
    ("Anthropic", "internal_error"),            # 모듈의 클래스지만 예외가 아니다 / a class, not an exception
    ("types", "internal_error"),                # 모듈의 비-클래스 속성 / non-class module attribute
    ("", "internal_error"),
])
def test_recorded_error_status_mapping(recorded, status):
    """#1458 의 벤더/우리 구분을 기록된 클래스명으로 되살린다 — 이름 모양이 아니라 클래스 계보로."""
    assert repo_insight_service._status_for_recorded_error(recorded) == status  # pylint: disable=protected-access
