"""실패한 인사이트 화면에도 새로 고침 링크 — 부정 캐시를 사용자가 넘는 유일한 길.

Failed insight screens offer Refresh — the only way a user gets past the negative cache.

실패는 잠시(부정 캐시 창) 재시도를 막는다. 링크가 성공 화면에만 있으면 사용자는 창이 끝날
때까지 같은 실패 카드만 본다. 판정은 문자열 포함이 아니라 파싱한 앵커의 **위치와 쿼리**다.
A recent failure briefly blocks retries; if Refresh exists only on success, the user is stuck on the
failure card. Assertions read parsed anchors (where they sit, what their query says), not substrings.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.auth.session import CurrentUser, require_login
from src.database import Base
from src.i18n.filters import register_i18n_filters
from src.i18n.loader import get_text
from src.main import app
from src.models.insight_narrative_cache import InsightNarrativeCache
from src.models.repository import Repository
from src.models.user import User

_FK_TARGET_MODELS = (InsightNarrativeCache, Repository, User)
if any(m.__tablename__ not in Base.metadata.tables for m in _FK_TARGET_MODELS):
    raise RuntimeError("ORM import 소실 — 테이블 미등록 / ORM import lost, table unregistered")

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class _Anchors(HTMLParser):
    """각 `<a>` 의 href · 조상 class 집합 · 링크 문구를 모은다."""

    def __init__(self):
        super().__init__()
        self.stack: list[set[str]] = []
        self.anchors: list[dict] = []
        self._open: dict | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = set((a.get("class") or "").split())
        if tag == "a":
            self._open = {"href": a.get("href") or "", "style": a.get("style") or "",
                          "cls": classes,
                          "ancestors": set().union(*self.stack) if self.stack else set(), "text": ""}
            self.anchors.append(self._open)
        if tag not in _VOID:
            self.stack.append(classes)

    def handle_endtag(self, tag):
        if tag == "a":
            self._open = None
        if tag not in _VOID and self.stack:
            self.stack.pop()

    def handle_data(self, data):
        if self._open is not None:
            self._open["text"] += data


def _anchors(html: str) -> list[dict]:
    p = _Anchors()
    p.feed(html)
    return p.anchors


def _refresh_links(html: str, path: str) -> list[dict]:
    """`path` 로 가고 쿼리에 `refresh=1` 이 있는 앵커만 — 부분문자열이 아니라 URL 파싱으로 고른다."""
    out = []
    for a in _anchors(html):
        u = urlsplit(a["href"])
        if u.path == path and parse_qs(u.query).get("refresh") == ["1"]:
            out.append({**a, "query": parse_qs(u.query)})
    return out


def _render(template_name: str, **context) -> str:
    env = Environment(loader=FileSystemLoader("src/templates"), autoescape=select_autoescape(["html", "xml"]))
    register_i18n_filters(env)
    return env.get_template(template_name).render(**context)


class _FakeUser:
    github_login = "alice"
    display_name = "Alice"
    is_telegram_connected = False
    preferred_language = "ko"


# ─── 대시보드 인사이트 ────────────────────────────────────────────────────────


def _dashboard(insight, *, locale="ko", days=7) -> str:
    return _render("dashboard.html", locale=locale, current_user=_FakeUser(), mode="insight",
                   initial_mode="insight", days=days, insight=insight)


@pytest.mark.parametrize("status", ["api_error", "parse_error"])
@pytest.mark.parametrize("locale", ["ko", "en", "ja"])
def test_dashboard_failure_card_offers_refresh(status, locale):
    html = _dashboard({"status": status}, locale=locale, days=14)
    links = _refresh_links(html, "/dashboard")
    assert len(links) == 1, f"실패 카드의 새로 고침 링크 수 {len(links)} — 1 이어야 한다"
    link = links[0]
    # 🔴 상자 «밖» — e2e(`e2e/test_theme_mobile_guards.py::_INSIGHT_STATUS_JS`)가 상자 innerText 를
    #    정본 문구와 정확히 대조한다. 링크가 안에 들어가면 4테마 전부 red 였다(독립 리뷰 실측).
    # Outside the box: the e2e contrast check compares the box innerText with the exact sentence.
    assert "dash-insight-status" not in link["ancestors"], "링크가 상태 상자 안에 있다 — 상자 글자가 정본 문구와 달라진다"
    box = re.search(r'<div class="dash-insight-status">(.*?)</div>', html, re.S)
    assert box, "실패 상태 상자가 없다"
    want = get_text("dashboard.insight.load_failed", locale, status=status)
    assert " ".join(re.sub(r"<[^>]+>", "", box.group(1)).split()) == " ".join(want.split()), (
        "상태 상자 글자가 정본 문구와 다르다")
    assert link["query"] == {"mode": ["insight"], "days": ["14"], "refresh": ["1"]}
    assert link["text"].strip() == get_text("dashboard.insight.refresh", locale)
    assert "min-height:24px" in link["style"].replace(" ", ""), "WCAG 2.5.8 24px 하한이 빠졌다"
    # 실패 문구는 그대로 / the failure sentence is unchanged
    assert status in html


def test_dashboard_success_header_still_has_exactly_one_refresh_outside_the_status_card():
    html = _dashboard({
        "status": "success", "generated_at": "2026-09-28T10:30:00Z",
        "positive_highlights": ["a"], "focus_areas": ["b"], "key_metrics": [], "next_actions": ["c"],
    })
    links = _refresh_links(html, "/dashboard")
    assert len(links) == 1
    assert "dash-insight-status" not in links[0]["ancestors"]


@pytest.mark.parametrize("status", ["no_api_key", "no_data", "disabled"])
def test_dashboard_non_failure_states_have_no_refresh(status):
    """새로 고침이 도울 수 없는 상태 — 링크를 두지 않는다(유료 호출만 부른다)."""
    assert _refresh_links(_dashboard({"status": status}), "/dashboard") == []


# ─── 리포 인사이트 — 템플릿 ───────────────────────────────────────────────────


class _FakeRepo:
    full_name = "owner/repo"
    id = 1
    user_id = 1


class _FakeUnclaimedRepo(_FakeRepo):
    user_id = None


def _repo_ctx(**overrides) -> dict:
    base = {
        "current_user": _FakeUser(), "repo": _FakeRepo(), "days": 30,
        "kpi": {"grade": "B", "avg_score": 82, "analysis_count": 5, "top_recurring_issue": "x",
                "top_recurring_count": 3, "high_security_count": 0, "score_delta": 1.5},
        "recurring_issues": [], "problem_files": [], "ai_suggestions": [], "breakdown": {"total": 0},
        "narrative": None, "narrative_failed": False,
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize("locale", ["ko", "en", "ja"])
def test_repo_failed_narrative_shows_failure_line_with_refresh(locale):
    html = _render("repo_insights.html", locale=locale, **_repo_ctx(narrative_failed=True))
    links = _refresh_links(html, "/repos/owner/repo/insights")
    assert len(links) == 1, f"실패 줄의 새로 고침 링크 수 {len(links)} — 1 이어야 한다"
    link = links[0]
    assert "ri-narrative-failed" in link["ancestors"]
    assert link["query"] == {"days": ["30"], "refresh": ["1"]}
    assert get_text("repo_insights.refresh", locale) in link["text"]
    sentence = get_text("repo_insights.narrative_failed", locale)
    assert sentence != "repo_insights.narrative_failed", "문구 키가 없다"
    assert sentence in html


def test_repo_no_failure_flag_means_no_failure_line():
    html = _render("repo_insights.html", locale="ko", **_repo_ctx())
    assert _refresh_links(html, "/repos/owner/repo/insights") == []
    assert get_text("repo_insights.narrative_failed", "ko") not in html


@pytest.mark.parametrize("narrative, failed", [
    (None, True),
    ({"text": "좋은 리포다", "status": "success"}, False),
])
def test_unclaimed_repo_offers_no_refresh_link(narrative, failed):
    """🔴 소유자 없는 리포는 `refresh=1` 이 403 이다(`src/ui/routes/repo_insights.py` 의 가드) —
    그 페이지에 새로 고침 링크를 그리면 «반드시 실패하는 링크» 다(Grok claim-review 9ea413ed 반례).
    실패 문구·서술은 그대로 두고 링크만 뺀다.
    An unclaimed repo 403s on refresh=1, so no Refresh link is drawn; the sentence/narrative stays."""
    html = _render("repo_insights.html", locale="ko",
                   **_repo_ctx(repo=_FakeUnclaimedRepo(), narrative=narrative, narrative_failed=failed))
    assert _refresh_links(html, "/repos/owner/repo/insights") == []
    if failed:
        assert get_text("repo_insights.narrative_failed", "ko") in html
    else:
        assert "좋은 리포다" in html


def test_repo_success_narrative_is_unchanged():
    html = _render("repo_insights.html", locale="ko",
                   **_repo_ctx(narrative={"text": "좋은 리포다", "status": "success"}))
    links = _refresh_links(html, "/repos/owner/repo/insights")
    assert len(links) == 1
    assert "ri-narrative-failed" not in links[0]["ancestors"]
    assert "좋은 리포다" in html
    assert get_text("repo_insights.narrative_failed", "ko") not in html


# ─── 리포 인사이트 — 라우트가 실패를 알린다 ─────────────────────────────────────


@pytest.fixture()
def route_client():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sess = Session(engine)
    u = User(github_id="rf-1", github_login="owner", email="o@x.com", display_name="O")
    sess.add(u)
    sess.commit()
    sess.add(Repository(full_name="owner/myrepo", user_id=u.id))
    sess.commit()
    current = CurrentUser(id=u.id, github_login="owner", email="o@x.com", display_name="O",
                          plaintext_token="ghp_test")
    from src.ui.routes.repo_insights import _get_db  # pylint: disable=import-outside-toplevel

    prev = app.dependency_overrides.get(require_login)
    app.dependency_overrides[require_login] = lambda: current
    app.dependency_overrides[_get_db] = lambda: sess
    try:
        yield TestClient(app)
    finally:
        if prev is None:
            app.dependency_overrides.pop(require_login, None)
        else:
            app.dependency_overrides[require_login] = prev
        app.dependency_overrides.pop(_get_db, None)
        sess.close()
        engine.dispose()


# witness-corpus: 서술 실패 부류 — 서비스 반환 status(api_error·internal_error), 형제 대시보드 실패 어휘(parse_error), 실페이지 재현에서 캐시에 실제 기록된 유형(TimeoutError·max_tokens)
_FAILED_STATUSES = ["api_error", "internal_error", "parse_error", "TimeoutError", "max_tokens"]


def _get_with_status(client, status):
    with patch("src.ui.routes.repo_insights.repo_insight_narrative",
               new=AsyncMock(return_value={"text": "", "status": status})), \
         patch("src.ui.routes.repo_insights.settings") as s:
        s.anthropic_api_key = "sk-ant-test"
        return client.get("/repos/owner/myrepo/insights?days=7", headers={"Accept-Language": "en"})


@pytest.mark.parametrize("status", _FAILED_STATUSES)
def test_route_renders_failure_line_for_any_failure_status(route_client, status):
    """정상 상태(success·no_data·disabled·no_api_key)가 아니면 전부 실패다 — 모르는 값도 조용히 사라지지 않는다.

    대시보드 템플릿의 else 분기와 같은 방향이다. Anything but the non-failure states is a failure.
    """
    resp = _get_with_status(route_client, status)
    assert resp.status_code == 200
    links = _refresh_links(resp.text, "/repos/owner/myrepo/insights")
    assert len(links) == 1 and "ri-narrative-failed" in links[0]["ancestors"]
    assert links[0]["query"] == {"days": ["7"], "refresh": ["1"]}


@pytest.mark.parametrize("status", ["no_data", "disabled", "no_api_key"])
def test_route_renders_no_failure_line_for_non_failures(route_client, status):
    resp = _get_with_status(route_client, status)
    assert resp.status_code == 200
    assert _refresh_links(resp.text, "/repos/owner/myrepo/insights") == []
