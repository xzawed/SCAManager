"""리포 인사이트 서술은 페이지를 붙잡지 않는다 — 유료 호출은 조각 요청에서만 나간다 (원장 #1706 안 C 를 리포 인사이트에).

대시보드(#1896)와 같은 구조였다: 캐시 미스의 `GET /repos/{name}/insights` 가 Claude 응답을 기다린 뒤에야 첫 바이트를
보냈다. 이제 페이지는 유료 호출 직전에 멈추고(`status="pending"`) 자리만 그리며, 그 자리가 htmx 로
`GET /repos/{name}/insights/narrative` 를 불러 서술을 채운다. 캐시 · 부정 캐시 · 하루 한도 · 데이터 0건은 지금처럼
페이지가 바로 그린다.

여기서는 「클라이언트 팩토리가 몇 번 불렸는가」로 잰다 — 비용이 생기는 유일한 입구다(대시보드 시험과 같은 계기).
The page no longer waits for the narrative; only the fragment request makes the paid call. Counted at the client factory.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import json
import re
import uuid
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
from src.services import repo_insight_service
from src.ui.routes.repo_insights import _get_db

_TABLE_MODELS = (Analysis, ClaudeApiCall, InsightNarrativeCache, Repository, User)
if any(m.__tablename__ not in Base.metadata.tables for m in _TABLE_MODELS):
    raise RuntimeError("ORM import 소실 — 테이블 미등록 / ORM import lost, table unregistered")

_REPO = "async-owner/async-repo"
_PAGE = f"/repos/{_REPO}/insights"
_FRAGMENT = f"/repos/{_REPO}/insights/narrative"
_HX = {"HX-Request": "true"}
_TEXT = "비동기 서술: 점수가 버텼고 반복 이슈 둘이 남았다."


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _user(db, login: str) -> int:
    u = User(github_id=f"ri-{login}", github_login=login, email=f"{login}@x.com", display_name=login)
    db.add(u)
    db.commit()
    return u.id


@pytest.fixture()
def owner(db):
    """사용자 1 + 소유 리포 1 + 창 안의 분석 2건 — user_id 를 돌려준다."""
    uid = _user(db, "riowner")
    r = Repository(full_name=_REPO, user_id=uid)
    db.add(r)
    db.commit()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for i, score in enumerate((80, 85)):
        db.add(Analysis(repo_id=r.id, commit_sha=f"ria{uuid.uuid4().hex}", score=score, grade="B",
                        result={}, created_at=now - timedelta(hours=i + 1)))
    db.commit()
    return uid


@pytest.fixture()
def client_for(db):
    """로그인을 이 사용자로 묶고 라우트의 DB 의존성을 이 시험의 세션으로 바꾼 TestClient(키 있음)."""
    prev_login = app.dependency_overrides.get(require_login)
    prev_db = app.dependency_overrides.get(_get_db)

    def make(user_id: int) -> TestClient:
        current = CurrentUser(id=user_id, github_login="ri", email="ri@x.com",
                              display_name="R", plaintext_token="ghp_test")
        app.dependency_overrides[require_login] = lambda: current
        return TestClient(app, follow_redirects=False)

    app.dependency_overrides[_get_db] = lambda: db
    with patch.object(settings, "anthropic_api_key", "sk-ant-test"):
        yield make
    for dep, prev in ((require_login, prev_login), (_get_db, prev_db)):
        if prev is None:
            app.dependency_overrides.pop(dep, None)
        else:
            app.dependency_overrides[dep] = prev


class _Sdk:
    """클라이언트 팩토리 · 종료 · 비용 로그를 가로챈다 — 팩토리 호출 수가 유료 호출 수다."""

    def __init__(self, create):
        client = MagicMock()
        client.messages.create = create
        self.factory = MagicMock(return_value=client)
        self._patches = [
            patch.object(repo_insight_service, "new_async_anthropic", self.factory),
            patch.object(repo_insight_service, "aclose_anthropic_client", AsyncMock()),
            patch.object(repo_insight_service, "log_claude_api_call", MagicMock()),
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
    block.text = json.dumps({"text": text}, ensure_ascii=False)
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
    """자리 표시가 부를 주소 — `id="riNarrative"` 요소의 `hx-get`. 자리 표시가 없으면 None."""
    m = re.search(r'<div id="riNarrative"[^>]*\shx-get="([^"]+)"', html)
    return m.group(1).replace("&amp;", "&") if m else None


# ─── 페이지는 유료 호출을 하지 않는다 ─────────────────────────────────────────


def test_page_cache_miss_draws_a_placeholder_without_a_paid_call(owner, client_for):
    """캐시 미스 — 페이지는 자리(htmx 가 부를 조각 주소 · aria-busy)만 그리고 클라이언트를 만들지 않는다."""
    with _Sdk(_reply(_TEXT)) as sdk:
        page = client_for(owner).get(f"{_PAGE}?days=30")
    assert page.status_code == 200
    assert sdk.factory.call_count == 0, "페이지 요청이 유료 호출을 시작했다 — 서술을 기다리는 구조가 그대로다"
    assert _placeholder_url(page.text) == f"{_FRAGMENT}?days=30", "자리 표시가 조각 주소를 부르지 않는다"
    assert 'aria-busy="true"' in page.text
    assert _TEXT not in page.text


def test_fragment_makes_the_one_paid_call_and_draws_only_the_narrative(owner, client_for):
    """조각 요청 — 클라이언트 1번 · 서술 자리만(페이지 껍데기 없이) 그린다."""
    with _Sdk(_reply(_TEXT)) as sdk:
        frag = client_for(owner).get(f"{_FRAGMENT}?days=30", headers=_HX)
    assert frag.status_code == 200
    assert sdk.factory.call_count == 1
    assert _TEXT in frag.text
    assert re.search(r'<div id="riNarrative"[^>]*>', frag.text), "조각이 자리 표시와 같은 id 로 바꿔 끼우지 못한다"
    assert "hx-get" not in frag.text, "채운 조각이 또 조각을 부른다 — 요청이 되풀이된다"
    assert "<html" not in frag.text.lower(), "조각이 페이지 전체를 돌려준다"
    assert f"{_PAGE}?days=30&refresh=1" in frag.text, "소유 리포의 서술 카드에 새로 고침 링크가 없다"


def test_after_the_fragment_the_page_draws_the_cached_narrative_inline(owner, client_for):
    """조각이 성공을 캐시에 넣은 뒤의 페이지 — 자리 없이 서술을 바로 그리고, 유료 호출은 늘지 않는다."""
    client = client_for(owner)
    with _Sdk(_reply(_TEXT)) as sdk:
        client.get(f"{_FRAGMENT}?days=30", headers=_HX)
        page = client.get(f"{_PAGE}?days=30")
    assert sdk.factory.call_count == 1
    assert _placeholder_url(page.text) is None
    assert _TEXT in page.text


def test_a_failed_fragment_is_negatively_cached_so_the_page_does_not_loop(owner, client_for):
    """조각의 Claude 실패 — 실패 줄(새로 고침 링크)을 그리고, 이어진 페이지는 부정 캐시로 자리 없이 끝난다."""
    client = client_for(owner)
    with _Sdk(_fail()) as sdk:
        frag = client.get(f"{_FRAGMENT}?days=30", headers=_HX)
        page = client.get(f"{_PAGE}?days=30")
    assert frag.status_code == 200
    assert "ri-narrative-failed" in frag.text
    assert f"{_PAGE}?days=30&refresh=1" in frag.text, "실패 줄에 새로 고침 링크가 없다"
    assert sdk.factory.call_count == 1, "실패 뒤 페이지가 또 유료 호출을 했다"
    assert _placeholder_url(page.text) is None, "부정 캐시가 있는데 페이지가 다시 조각을 부른다 — 실패가 되풀이된다"
    assert "ri-narrative-failed" in page.text


def test_without_a_key_the_page_draws_no_placeholder(owner, client_for):
    """키가 없으면 서술 자리는 비어 있다 — 부를 조각도 유료 호출도 없다(지금과 같은 화면)."""
    with patch.object(settings, "anthropic_api_key", ""), _Sdk(_reply(_TEXT)) as sdk:
        page = client_for(owner).get(f"{_PAGE}?days=30")
    assert page.status_code == 200
    assert sdk.factory.call_count == 0
    assert _placeholder_url(page.text) is None
    assert re.search(r'<div id="riNarrative">\s*</div>', page.text), "키가 없을 때 서술 자리가 비어 있지 않다"


# ─── 조각 경로의 경계 ────────────────────────────────────────────────────────


def test_fragment_outside_htmx_redirects_to_the_page(owner, client_for):
    """주소창 · 새 탭(htmx 아님) — 맨 조각 대신 그 화면으로 303, 유료 호출 없음."""
    with _Sdk(_reply(_TEXT)) as sdk:
        resp = client_for(owner).get(f"{_FRAGMENT}?days=30")
    assert resp.status_code == 303
    assert resp.headers["location"] == f"{_PAGE}?days=30"
    assert sdk.factory.call_count == 0


@pytest.mark.parametrize(("asked", "snapped"), [(14, 30), (2, 7), (365, 90)])
def test_fragment_snaps_days_to_the_on_screen_window(owner, client_for, asked, snapped):
    """조각도 화면 기간 값으로 맞춘다 — 페이지 · 새로 고침과 같은 캐시 키를 써야 한다(회고 원장 L17 P2-7)."""
    with _Sdk(_reply(_TEXT)):
        resp = client_for(owner).get(f"{_FRAGMENT}?days={asked}")
    assert resp.headers["location"] == f"{_PAGE}?days={snapped}"


def test_page_placeholder_uses_the_snapped_window(owner, client_for):
    with _Sdk(_reply(_TEXT)):
        page = client_for(owner).get(f"{_PAGE}?days=14")
    assert _placeholder_url(page.text) == f"{_FRAGMENT}?days=30"


def test_fragment_hides_another_users_repo(owner, client_for, db):
    """남의 리포 — 페이지와 같이 404, 유료 호출 없음(유료 호출 입구의 권한 격리)."""
    stranger = _user(db, "stranger")
    with _Sdk(_reply(_TEXT)) as sdk:
        resp = client_for(stranger).get(f"{_FRAGMENT}?days=30", headers=_HX)
    assert resp.status_code == 404
    assert sdk.factory.call_count == 0


def test_fragment_requires_login():
    """미로그인 — 조각도 로그인으로 보낸다(유료 호출 입구)."""
    prev = app.dependency_overrides.pop(require_login, None)
    try:
        resp = TestClient(app, follow_redirects=False).get(f"{_FRAGMENT}?days=30", headers=_HX)
        assert resp.status_code in (302, 303, 401)
    finally:
        if prev is not None:
            app.dependency_overrides[require_login] = prev


# ─── 자리 표시의 실패 대비 ───────────────────────────────────────────────────


def _placeholder_box(page: str) -> re.Match | None:
    return re.search(r'<div id="riNarrative"[^>]*hx-get=.*?</template>', page, re.S)


def test_placeholder_carries_a_failure_state_for_network_errors(owner, client_for):
    """조각 요청 자체가 실패하면(5xx · 연결 끊김) 자리에 실패 줄을 놓는다 — 그 마크업을 `<template>` 로 미리 들고 있다."""
    with _Sdk(_reply(_TEXT)):
        page = client_for(owner).get(f"{_PAGE}?days=30").text
    box = _placeholder_box(page)
    assert box, "자리 표시 안에 실패 줄 `<template>` 이 없다"
    assert "ri-narrative-failed" in box.group(0) and f"{_PAGE}?days=30&refresh=1" in box.group(0)
    script = page[box.end():box.end() + 2000]
    assert "htmx:responseError" in script and "htmx:sendError" in script, "조각 요청 실패를 받는 리스너가 없다"


def test_unclaimed_repo_placeholder_failure_state_offers_no_refresh(owner, client_for, db):
    """소유자 없는 리포 — 자리의 실패 대비에도 새로 고침 링크가 없다(`refresh=1` 은 403 — 라우트 가드와 같은 조건)."""
    r = Repository(full_name="nobody/unclaimed", user_id=None)
    db.add(r)
    db.commit()
    db.add(Analysis(repo_id=r.id, commit_sha=f"riu{uuid.uuid4().hex}", score=70, grade="C", result={},
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)))
    db.commit()
    with _Sdk(_reply(_TEXT)) as sdk:
        page = client_for(owner).get("/repos/nobody/unclaimed/insights?days=30").text
    assert sdk.factory.call_count == 0
    box = _placeholder_box(page)
    assert box, "소유자 없는 리포의 캐시 미스도 자리를 그려야 한다"
    assert "ri-narrative-failed" in box.group(0)
    assert "refresh=1" not in box.group(0), "소유자 없는 리포의 실패 대비에 403 이 날 새로 고침 링크가 있다"
