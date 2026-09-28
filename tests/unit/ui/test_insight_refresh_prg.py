"""인사이트 새로 고침은 Post/Redirect/Get 이다 — `?refresh=1` 은 캐시만 지우고 303 으로 떠난다.

Insight Refresh is Post/Redirect/Get: `?refresh=1` only invalidates the cache and leaves with a 303.

수정 전(#1716 리뷰 실측): 새로 고침 링크의 주소가 `refresh=1` 을 그대로 달고 있어, 결과 화면에서
F5 를 누를 때마다 캐시를 지우고 유료 ~45 s 호출을 또 시작했다(부정 캐시 120 s 도 우회).
여기서는 「클라이언트 팩토리가 몇 번 불렸는가」로 잰다 — 비용이 생기는 유일한 입구다.
Before the fix, the Refresh URL kept `refresh=1`, so every F5 on the result deleted the cache and
started another paid ~45 s call (bypassing the 120 s negative cache). These tests count client
factory calls, the single entry point where cost starts.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import json
import uuid
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qsl, unquote, urlsplit

import anthropic
import httpx
import pytest
from fastapi import Request
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
from src.repositories import insight_narrative_cache_repo
from src.services import dashboard_service, repo_insight_service
from src.ui._helpers import redirect_without_refresh
from src.ui.routes.repo_insights import _get_db

# KPI 비용 집계가 claude_api_calls 를 읽는다 — 단독 실행에서도 테이블이 있도록 등록을 확인한다.
# The KPI cost aggregate reads claude_api_calls; assert registration so a lone run has the table.
_TABLE_MODELS = (Analysis, ClaudeApiCall, InsightNarrativeCache, Repository, User)
if any(m.__tablename__ not in Base.metadata.tables for m in _TABLE_MODELS):
    raise RuntimeError("ORM import 소실 — 테이블 미등록 / ORM import lost, table unregistered")

_REPO = "prg-owner/prg-repo"
_OK_CARDS = json.dumps({
    "positive_highlights": ["잘했다"], "focus_areas": ["볼 것"],
    "key_metrics": [{"label": "평균", "value": "80", "delta": "+1"}], "next_actions": ["다음"],
})


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
    """사용자 1 + 소유 리포 1 + 창 안의 분석 2건 — (user_id, repo_id) 를 돌려준다."""
    u = User(github_id="prg-1", github_login="prg", email="p@x.com", display_name="P")
    db.add(u)
    db.commit()
    r = Repository(full_name=_REPO, user_id=u.id)
    db.add(r)
    db.commit()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for i, score in enumerate((80, 85)):
        db.add(Analysis(repo_id=r.id, commit_sha=f"prg{uuid.uuid4().hex}", score=score, grade="B",
                        result={}, created_at=now - timedelta(hours=i + 1)))
    db.commit()
    return u.id, r.id


@pytest.fixture()
def client_for(db):
    """로그인·세션을 이 테스트의 DB 로 묶은 TestClient 를 만든다 — 끝나면 override 를 되돌린다."""
    prev_login = app.dependency_overrides.get(require_login)
    prev_db = app.dependency_overrides.get(_get_db)

    def make(user_id: int, *, follow_redirects: bool = True) -> TestClient:
        current = CurrentUser(id=user_id, github_login="prg", email="p@x.com",
                              display_name="P", plaintext_token="ghp_test")
        app.dependency_overrides[require_login] = lambda: current
        app.dependency_overrides[_get_db] = lambda: db
        return TestClient(app, follow_redirects=follow_redirects)

    # 대시보드는 의존성이 아니라 `SessionLocal()` 을 직접 연다 — 같은 세션을 닫지 않고 건넨다.
    # The dashboard opens `SessionLocal()` directly; hand it the same session without closing it.
    with patch("src.ui.routes.dashboard.SessionLocal", lambda: nullcontext(db)), \
         patch.object(settings, "anthropic_api_key", "sk-ant-test"):
        yield make
    for dep, prev in ((require_login, prev_login), (_get_db, prev_db)):
        if prev is None:
            app.dependency_overrides.pop(dep, None)
        else:
            app.dependency_overrides[dep] = prev


class _Sdk:
    """두 서비스의 클라이언트 팩토리·종료·비용 로그를 가로챈다 — 호출 수가 증거다."""

    def __init__(self, create):
        client = MagicMock()
        client.messages.create = create
        self.factory = MagicMock(return_value=client)
        self._patches = [
            p for m in (dashboard_service, repo_insight_service) for p in (
                patch.object(m, "new_async_anthropic", self.factory),
                patch.object(m, "aclose_anthropic_client", AsyncMock()),
                patch.object(m, "log_claude_api_call", MagicMock()),
            )
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


_PAGES = {
    # 페이지 → (새로 고침 주소, 성공 응답 본문)
    # page → (refresh URL, success reply body)
    "dashboard": ("/dashboard?mode=insight&days=7&refresh=1", _OK_CARDS),
    "repo": (f"/repos/{_REPO}/insights?days=30&refresh=1", json.dumps({"text": "진단 서술"})),
}


def _query(url: str) -> list[tuple[str, str]]:
    return parse_qsl(urlsplit(url).query, keep_blank_values=True)


# ─── F5 는 유료 호출을 되풀이하지 않는다 ─────────────────────────────────────


@pytest.mark.parametrize("outcome", ["success", "api_error"])
@pytest.mark.parametrize("page", sorted(_PAGES))
def test_reload_after_refresh_makes_no_second_client(owner, client_for, page, outcome):
    """새로 고침 → 도착한 주소에서 F5 — 성공이면 캐시가, 실패면 부정 캐시가 받아 클라이언트는 한 번뿐이다."""
    user_id, _ = owner
    refresh_url, ok_body = _PAGES[page]
    create = _reply(ok_body) if outcome == "success" else _fail()
    client = client_for(user_id)
    with _Sdk(create) as sdk:
        first = client.get(refresh_url)
        assert first.status_code == 200
        assert sdk.factory.call_count == 1, "새로 고침이 서술을 한 번 새로 만들지 않았다"

        reload_ = client.get(str(first.url))  # F5 = 주소창의 주소를 다시 GET / F5 re-GETs the address bar

    assert reload_.status_code == 200
    assert sdk.factory.call_count == 1, (
        f"새로 고침 뒤 F5 가 유료 호출을 또 시작했다 — 도착 주소 {first.url}")
    assert "refresh" not in dict(_query(str(first.url))), f"도착 주소에 refresh 가 남았다: {first.url}"


# ─── 303 의 모양 ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("path, want_path, want_query", [
    # refresh 가 가운데 · 알 수 없는 인자 · 빈 값 — 나머지는 순서까지 그대로
    # refresh in the middle, an unknown param, a blank value: the rest keep their order
    ("/dashboard?days=14&refresh=1&mode=insight&x=a%20b&y=",
     "/dashboard", [("days", "14"), ("mode", "insight"), ("x", "a b"), ("y", "")]),
    ("/dashboard?mode=insight&refresh=2", "/dashboard", [("mode", "insight")]),
    # 남은 키가 알파벳순이 아니다 — 정렬해 버리는 구현을 잡는다(독립 리뷰 R4c 생존)
    # Remaining keys out of alphabetical order, so a sorting implementation is caught
    ("/dashboard?mode=insight&refresh=1&days=14", "/dashboard", [("mode", "insight"), ("days", "14")]),
    # 같은 키가 둘이어도 모두 뺀다 — 목적지에 refresh 가 남으면 되돌아온다
    # Drop every refresh key; one left behind would bounce back
    ("/dashboard?refresh=1&mode=insight&refresh=1", "/dashboard", [("mode", "insight")]),
    (f"/repos/{_REPO}/insights?days=14&refresh=1", f"/repos/{_REPO}/insights", [("days", "14")]),
    (f"/repos/{_REPO}/insights?refresh=1", f"/repos/{_REPO}/insights", []),
    ("/repos/prg-owner%2Fprg-repo/insights?refresh=1&days=7", f"/repos/{_REPO}/insights",
     [("days", "7")]),
])
def test_refresh_invalidates_then_redirects_303_without_refresh(
        db, owner, client_for, path, want_path, want_query):
    """새로 고침 요청은 캐시만 지우고 Claude 는 부르지 않은 채 `refresh` 를 뺀 같은 주소로 303 이다."""
    user_id, repo_id = owner
    # 두 언어로 캐시를 심는다 — 새로 고침은 언어와 무관하게 그 창의 서술을 버린다.
    # Seed two languages; Refresh drops the window's narrative regardless of language.
    q = dict(_query(path))
    days = int(q.get("days", 7 if path.startswith("/dashboard") else 30))
    for lang in ("en", "ko"):
        if path.startswith("/dashboard"):
            insight_narrative_cache_repo.upsert(
                db, user_id=user_id, days=days, language=lang, response={"status": "success"})
        else:
            insight_narrative_cache_repo.upsert_repo(
                db, user_id=user_id, repo_id=repo_id, days=days, language=lang,
                response={"text": "t", "status": "success"})
    assert db.query(InsightNarrativeCache).count() == 2  # 심은 것이 실제로 있다 / the plant exists

    client = client_for(user_id, follow_redirects=False)
    with _Sdk(_fail()) as sdk:
        r = client.get(path)
        assert r.status_code == 303, f"{path} → {r.status_code}"
        loc = r.headers["location"]
        assert urlsplit(loc).path == want_path
        assert _query(loc) == want_query
        assert sdk.factory.call_count == 0, "리다이렉트하는 요청이 Claude 를 불렀다"
        db.expire_all()
        assert db.query(InsightNarrativeCache).count() == 0, "새로 고침이 캐시를 지우지 않았다"

        # 목적지는 다시 리다이렉트하지 않는다 — 고리가 없다.
        # The destination does not redirect again: no loop.
        landed = client.get(loc)
    assert landed.status_code == 200, f"{loc} → {landed.status_code}"


@pytest.mark.parametrize("raw_path", [b"/repos/o/a%3Fb/insights", b"/repos/o/a%23b/insights",
                                      b"/repos/o/a%25b/insights"])
def test_redirect_points_at_the_same_path_when_it_holds_reserved_characters(raw_path):
    """경로에 인코딩된 `?`·`#`·`%` 가 있어도 Location 은 같은 경로다 — 디코드된 채 붙이면 `?` 뒤가 쿼리가 된다.
    (Grok 1422c56b 반례: `/repos/foo%3Fbar/insights?refresh=1` → `Location: /repos/foo?bar/insights`)"""
    path = unquote(raw_path.decode())
    request = Request({"type": "http", "method": "GET", "path": path, "raw_path": raw_path,
                       "query_string": b"days=7&refresh=1", "headers": []})
    loc = urlsplit(redirect_without_refresh(request).headers["location"])
    assert unquote(loc.path) == path, f"{raw_path!r} → {loc.geturl()}"
    assert parse_qsl(loc.query, keep_blank_values=True) == [("days", "7")]


@pytest.mark.parametrize("path", [
    "/dashboard?mode=insight&days=7&refresh=0",
    "/dashboard?mode=insight&days=7",
    # 마지막 mode 가 이긴다 — insight 가 아닌 대시보드에서 refresh 는 원래 아무 일도 하지 않는다(Grok 1422c56b)
    # The last mode wins; outside insight mode refresh never did anything on the dashboard
    "/dashboard?mode=insight&days=7&refresh=1&mode=overview",
    f"/repos/{_REPO}/insights?days=30&refresh=0",
    f"/repos/{_REPO}/insights?days=30",
])
def test_no_refresh_does_not_redirect(db, owner, client_for, path):
    """🔴 반드시 무시돼야 하는 쪽 — `refresh` 가 없거나 0 이거나 insight 모드가 아니면 리다이렉트도 무효화도 없다."""
    user_id, repo_id = owner
    days = 7 if path.startswith("/dashboard") else 30
    if path.startswith("/dashboard"):
        seeded = insight_narrative_cache_repo.upsert(
            db, user_id=user_id, days=days, language="en", response={"status": "success"})
    else:
        seeded = insight_narrative_cache_repo.upsert_repo(
            db, user_id=user_id, repo_id=repo_id, days=days, language="en",
            response={"text": "t", "status": "success"})
    seeded_id = seeded.id
    client = client_for(user_id, follow_redirects=False)
    with _Sdk(_fail()):
        r = client.get(path)
    assert r.status_code == 200, f"{path} → {r.status_code}"
    db.expire_all()
    assert db.get(InsightNarrativeCache, seeded_id) is not None, "새로 고침이 아닌 조회가 캐시를 지웠다"


# ─── 기존 가드는 리다이렉트보다 앞이다 ───────────────────────────────────────


@pytest.mark.parametrize("which, status", [("unclaimed", 403), ("unknown", 404), ("others", 404)])
def test_repo_guards_answer_before_any_redirect(db, owner, client_for, which, status):
    """소유자 없는 리포 403 · 없는 리포/남의 리포 404 가 먼저다 — 303 도, 캐시 삭제도 없다."""
    user_id, _ = owner
    other = User(github_id="prg-2", github_login="other", email="o@x.com", display_name="O")
    db.add(other)
    db.commit()
    names = {"unclaimed": "prg-owner/unclaimed", "unknown": "prg-owner/nope",
             "others": "prg-other/theirs"}
    owners = {"unclaimed": None, "others": other.id}
    if which in owners:
        r = Repository(full_name=names[which], user_id=owners[which])
        db.add(r)
        db.commit()
        # 이 사용자가 그 리포를 읽을 때 쌓인 캐시 — 거절된 새로 고침이 지우면 안 된다.
        # Cache this user built while reading the repo; a refused refresh must not delete it.
        insight_narrative_cache_repo.upsert_repo(
            db, user_id=user_id, repo_id=r.id, days=30, language="en",
            response={"text": "t", "status": "success"})
    before = db.query(InsightNarrativeCache).count()

    client = client_for(user_id, follow_redirects=False)
    with _Sdk(_fail()) as sdk:
        resp = client.get(f"/repos/{names[which]}/insights?days=30&refresh=1")
    assert resp.status_code == status
    assert sdk.factory.call_count == 0
    db.expire_all()
    assert db.query(InsightNarrativeCache).count() == before
