"""대시보드 인사이트 서술은 페이지를 붙잡지 않는다 — 유료 호출은 조각 요청에서만 나간다 (회고 원장 #1706 안 C).

운영 첫 실제 생성(11-18): 캐시 미스의 `GET /dashboard` 가 10.0 s 걸렸다(Claude 9.4 s). 페이지가 서술을 기다린 뒤에야
첫 바이트를 보냈기 때문이다. 이제 페이지는 유료 호출 직전에 멈추고(`status="pending"`) 자리만 그리며, 그 자리가 htmx 로
`GET /dashboard/insight` 를 불러 서술을 채운다. 캐시 · 부정 캐시 · 하루 한도 · 데이터 0건은 지금처럼 페이지가 바로 그린다.

여기서는 「클라이언트 팩토리가 몇 번 불렸는가」로 잰다 — 비용이 생기는 유일한 입구다(`test_insight_refresh_prg` 와 같은 계기).
The page no longer waits for the narrative; only the fragment request makes the paid call. Counted at the client factory.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import json
import re
import uuid
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.auth.session import CurrentUser, require_login
from src.config import settings
from src.database import Base
from src.main import app
from src.models.analysis import Analysis
from src.models.claude_api_call import ClaudeApiCall
from src.models.insight_narrative_cache import InsightNarrativeCache
from src.models.repository import Repository
from src.models.user import User
from src.services import dashboard_service

_TABLE_MODELS = (Analysis, ClaudeApiCall, InsightNarrativeCache, Repository, User)
if any(m.__tablename__ not in Base.metadata.tables for m in _TABLE_MODELS):
    raise RuntimeError("ORM import 소실 — 테이블 미등록 / ORM import lost, table unregistered")

_FRAGMENT = "/dashboard/insight"
_HX = {"HX-Request": "true"}
_OK_CARDS = json.dumps({
    "positive_highlights": ["비동기 잘했다"], "focus_areas": ["볼 것"],
    "key_metrics": [{"label": "평균", "value": "80", "delta": "+1"}], "next_actions": ["다음"],
})


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def owner(db):
    """사용자 1 + 소유 리포 1 + 창 안의 분석 2건 — user_id 를 돌려준다."""
    u = User(github_id="async-1", github_login="asy", email="a@x.com", display_name="A")
    db.add(u)
    db.commit()
    r = Repository(full_name="async-owner/async-repo", user_id=u.id)
    db.add(r)
    db.commit()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for i, score in enumerate((80, 85)):
        db.add(Analysis(repo_id=r.id, commit_sha=f"asy{uuid.uuid4().hex}", score=score, grade="B",
                        result={}, created_at=now - timedelta(hours=i + 1)))
    db.commit()
    return u.id


@pytest.fixture()
def client_for(db):
    """로그인을 이 사용자로 묶고 대시보드의 `SessionLocal()` 을 이 테스트의 세션으로 바꾼 TestClient."""
    prev = app.dependency_overrides.get(require_login)

    def make(user_id: int) -> TestClient:
        current = CurrentUser(id=user_id, github_login="asy", email="a@x.com",
                              display_name="A", plaintext_token="ghp_test")
        app.dependency_overrides[require_login] = lambda: current
        return TestClient(app, follow_redirects=False)

    with patch("src.ui.routes.dashboard.SessionLocal", lambda: nullcontext(db)), \
         patch.object(settings, "anthropic_api_key", "sk-ant-test"):
        yield make
    if prev is None:
        app.dependency_overrides.pop(require_login, None)
    else:
        app.dependency_overrides[require_login] = prev


class _Sdk:
    """클라이언트 팩토리 · 종료 · 비용 로그를 가로챈다 — 팩토리 호출 수가 유료 호출 수다."""

    def __init__(self, create):
        client = MagicMock()
        client.messages.create = create
        self.factory = MagicMock(return_value=client)
        self._patches = [
            patch.object(dashboard_service, "new_async_anthropic", self.factory),
            patch.object(dashboard_service, "aclose_anthropic_client", AsyncMock()),
            patch.object(dashboard_service, "log_claude_api_call", MagicMock()),
        ]

    def __enter__(self):
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self._patches):
            p.stop()


def _reply(text: str) -> AsyncMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    resp.stop_reason = "end_turn"
    resp.usage = MagicMock(input_tokens=100, output_tokens=50,
                           cache_read_input_tokens=0, cache_creation_input_tokens=0)
    return AsyncMock(return_value=resp)


def _fail() -> AsyncMock:
    return AsyncMock(side_effect=anthropic.APIConnectionError(
        message="connection failed",
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    ))


def _placeholder_url(html: str) -> str | None:
    """자리 표시가 부를 주소 — `id="dashInsight"` 요소의 `hx-get`. 자리 표시가 없으면 None."""
    m = re.search(r'<div id="dashInsight"[^>]*\shx-get="([^"]+)"', html)
    return m.group(1).replace("&amp;", "&") if m else None


# ─── 페이지는 유료 호출을 하지 않는다 ─────────────────────────────────────────


def test_page_cache_miss_draws_a_placeholder_without_a_paid_call(owner, client_for):
    """캐시 미스 — 페이지는 자리(htmx 가 부를 조각 주소 · aria-busy)만 그리고 클라이언트를 만들지 않는다."""
    with _Sdk(_reply(_OK_CARDS)) as sdk:
        page = client_for(owner).get("/dashboard?mode=insight&days=7")
    assert page.status_code == 200
    assert sdk.factory.call_count == 0, "페이지 요청이 유료 호출을 시작했다 — 서술을 기다리는 구조가 그대로다"
    assert _placeholder_url(page.text) == f"{_FRAGMENT}?days=7", "자리 표시가 조각 주소를 부르지 않는다"
    assert 'aria-busy="true"' in page.text
    assert "비동기 잘했다" not in page.text


def test_fragment_makes_the_one_paid_call_and_draws_only_the_cards(owner, client_for):
    """조각 요청 — 클라이언트 1번 · 네 카드만(페이지 껍데기 없이) 그린다."""
    with _Sdk(_reply(_OK_CARDS)) as sdk:
        frag = client_for(owner).get(f"{_FRAGMENT}?days=7", headers=_HX)
    assert frag.status_code == 200
    assert sdk.factory.call_count == 1
    assert "비동기 잘했다" in frag.text
    assert re.search(r'<div id="dashInsight"[^>]*>', frag.text), "조각이 자리 표시와 같은 id 로 바꿔 끼우지 못한다"
    assert "hx-get" not in frag.text, "채운 조각이 또 조각을 부른다 — 요청이 되풀이된다"
    assert "<html" not in frag.text.lower(), "조각이 페이지 전체를 돌려준다"


def test_after_the_fragment_the_page_draws_the_cached_cards_inline(owner, client_for):
    """조각이 성공을 캐시에 넣은 뒤의 페이지 — 자리 없이 카드를 바로 그리고, 유료 호출은 늘지 않는다."""
    client = client_for(owner)
    with _Sdk(_reply(_OK_CARDS)) as sdk:
        client.get(f"{_FRAGMENT}?days=7", headers=_HX)
        page = client.get("/dashboard?mode=insight&days=7")
    assert sdk.factory.call_count == 1
    assert _placeholder_url(page.text) is None
    assert "비동기 잘했다" in page.text


def test_a_failed_fragment_is_negatively_cached_so_the_page_does_not_loop(owner, client_for):
    """조각의 Claude 실패 — 실패 상자(새로 고침 링크)를 그리고, 이어진 페이지는 부정 캐시로 자리 없이 끝난다."""
    client = client_for(owner)
    with _Sdk(_fail()) as sdk:
        frag = client.get(f"{_FRAGMENT}?days=7", headers=_HX)
        page = client.get("/dashboard?mode=insight&days=7")
    assert frag.status_code == 200
    assert "/dashboard?mode=insight&days=7&refresh=1" in frag.text, "실패 상자에 새로 고침 링크가 없다"
    assert sdk.factory.call_count == 1, "실패 뒤 페이지가 또 유료 호출을 했다"
    assert _placeholder_url(page.text) is None, "부정 캐시가 있는데 페이지가 다시 조각을 부른다 — 실패가 되풀이된다"


# ─── 조각 경로의 경계 ────────────────────────────────────────────────────────


def test_fragment_outside_htmx_redirects_to_the_page(owner, client_for):
    """주소창 · 새 탭(htmx 아님) — 맨 조각 대신 그 화면으로 303, 유료 호출 없음."""
    with _Sdk(_reply(_OK_CARDS)) as sdk:
        resp = client_for(owner).get(f"{_FRAGMENT}?days=7")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/dashboard?mode=insight&days=7"
    assert sdk.factory.call_count == 0


@pytest.mark.parametrize(("asked", "snapped"), [(14, 30), (2, 7), (400, 90)])
def test_fragment_snaps_days_to_the_on_screen_window(owner, client_for, asked, snapped):
    """조각도 화면 기간 값으로 맞춘다 — 페이지 · 새로 고침과 같은 캐시 키를 써야 한다(회고 원장 L17 P2-7)."""
    with _Sdk(_reply(_OK_CARDS)):
        resp = client_for(owner).get(f"{_FRAGMENT}?days={min(asked, 365)}")
    assert resp.headers["location"] == f"/dashboard?mode=insight&days={snapped}"


def test_page_placeholder_uses_the_snapped_window(owner, client_for):
    with _Sdk(_reply(_OK_CARDS)):
        page = client_for(owner).get("/dashboard?mode=insight&days=14")
    assert _placeholder_url(page.text) == f"{_FRAGMENT}?days=30"


def test_fragment_requires_login():
    """미로그인 — 조각도 로그인으로 보낸다(유료 호출 입구)."""
    prev = app.dependency_overrides.pop(require_login, None)
    try:
        resp = TestClient(app, follow_redirects=False).get(f"{_FRAGMENT}?days=7", headers=_HX)
        assert resp.status_code in (302, 303, 401)
    finally:
        if prev is not None:
            app.dependency_overrides[require_login] = prev


# ─── 자리 표시의 실패 대비 ───────────────────────────────────────────────────


def test_placeholder_carries_a_failure_state_for_network_errors(owner, client_for):
    """조각 요청 자체가 실패하면(5xx · 연결 끊김) 자리에 실패 상자를 놓는다 — 그 마크업을 `<template>` 로 미리 들고 있다."""
    with _Sdk(_reply(_OK_CARDS)):
        page = client_for(owner).get("/dashboard?mode=insight&days=7").text
    box = re.search(r'<div id="dashInsight"[^>]*hx-get=.*?</template>', page, re.S)
    assert box, "자리 표시 안에 실패 상자 `<template>` 이 없다"
    assert "dash-insight-status" in box.group(0) and "refresh=1" in box.group(0)
    script = page[box.end():box.end() + 2000]
    assert "htmx:responseError" in script and "htmx:sendError" in script, "조각 요청 실패를 받는 리스너가 없다"
