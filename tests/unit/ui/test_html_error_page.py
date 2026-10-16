"""브라우저 화면 요청의 404·403 은 오류 «화면» 이다 — API·비브라우저는 JSON 그대로 (2026-10-16 렌더링 검수).

## 무엇이 문제였나

없는 리포·분석 주소(삭제된 리포 · 알림 속 옛 링크 · 남의 리포)로 가면 브라우저에
`{"detail":"Repository not found"}` 원문이 그대로 보였다. FastAPI 기본 처리기가 HTML 화면
요청에도 JSON 을 줬기 때문이다.

## 이 시험이 지키는 것 (사용자 결정 «브라우저 요청만 오류 화면»)

- GET · 화면 경로 · `Accept` 에 `text/html` → 오류 화면(상태 코드는 그대로 404·403).
- `/api/…` 같은 비화면 경로, `Accept: */*`(CLI·API 클라이언트·TestClient 기본) → 종전 JSON.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.auth.session import CurrentUser, get_current_user, require_login
from src.main import app

_BROWSER = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
_USER = CurrentUser(id=1, github_login="testuser", email="t@example.com", display_name="Test User",
                    plaintext_token="")


@pytest.fixture
def client():
    saved = {k: app.dependency_overrides.get(k) for k in (require_login, get_current_user)}
    app.dependency_overrides[require_login] = lambda: _USER
    app.dependency_overrides[get_current_user] = lambda: _USER
    try:
        yield TestClient(app)
    finally:
        for key, prev in saved.items():
            if prev is None:
                app.dependency_overrides.pop(key, None)
            else:
                app.dependency_overrides[key] = prev


def _no_repo_db():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def test_a_browser_gets_an_error_page_for_a_missing_repo(client):
    """🔴 브라우저 화면 요청의 404 는 nav 가 있는 오류 화면이다 — JSON 원문이 아니다."""
    with patch("src.ui.routes.detail.SessionLocal", return_value=_no_repo_db()):
        r = client.get("/repos/nope%2Frepo", headers={**_BROWSER, "Accept-Language": "ko-KR"})
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("text/html"), r.headers["content-type"]
    assert '"detail"' not in r.text, "브라우저에 JSON 원문이 그대로 나갔다"
    assert "<nav" in r.text and 'class="error-page' in r.text, "base 를 상속한 오류 화면이 아니다"
    assert "페이지를 찾을 수 없습니다" in r.text
    assert 'href="/"' in r.text, "개요로 돌아가는 길이 없다"


def test_an_api_client_still_gets_json_for_the_same_page(client):
    """대조군 — 같은 화면 주소라도 `Accept: */*`(CLI·API 클라이언트)면 종전 JSON 이다."""
    with patch("src.ui.routes.detail.SessionLocal", return_value=_no_repo_db()):
        r = client.get("/repos/nope%2Frepo")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json"), r.headers["content-type"]
    assert "detail" in r.json()


def test_api_paths_stay_json_even_for_a_browser(client):
    """🔴 `/api/…` 는 브라우저가 열어도 JSON — 화면 처리기는 화면 경로에만 걸린다."""
    r = client.get("/api/no-such-endpoint", headers=_BROWSER)
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json"), r.headers["content-type"]


def test_an_unknown_page_is_an_error_page_in_the_viewer_language(client):
    """라우트가 없는 화면 주소도 오류 화면이고, 문구는 요청 언어를 따른다."""
    r = client.get("/no-such-page", headers={**_BROWSER, "Accept-Language": "ja-JP"})
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("text/html")
    assert "ページが見つかりません" in r.text
    assert 'lang="ja"' in r.text


_CHROME_NAV = ("text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
               "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7")
_FIREFOX_NAV = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

# witness-corpus: 운영 HTTP 로그(2026-10-09~16)에 실제로 찍힌 4xx 요청과 실제 클라이언트 기본 Accept 머리
_REAL_REQUESTS = [
    # (메서드, 경로, Accept, 오류 화면이어야 하는가) — 경로·메서드는 운영 로그, Accept 는 각 클라이언트 기본값.
    ("GET", "/.env", "*/*", False),                 # curl/8.5.0 스캐너
    ("GET", "/config.json", "*/*", False),          # curl/8.5.0 스캐너
    ("GET", "/v1/models", "*/*", False),            # curl/8.5.0
    ("GET", "/api/config", "*/*", False),           # curl/8.5.0 — /api 는 브라우저형이어도 JSON
    ("GET", "/api/config", _CHROME_NAV, False),
    ("HEAD", "/", _CHROME_NAV, False),              # 업타임 봇 HEAD / → 405 는 화면 대상이 아니다
    ("GET", "/robots.txt", _FIREFOX_NAV, True),     # 크롤러가 브라우저형 Accept 로 열면 화면 404
    ("GET", "/repos/gone%2Frepo", _CHROME_NAV, True),
    ("GET", "/repos/gone%2Frepo", "application/json", False),
]


@pytest.mark.parametrize(("method", "path", "accept", "page"), _REAL_REQUESTS)
def test_real_requests_get_the_right_kind_of_error(client, method, path, accept, page):
    """🔴 실제로 들어온 요청 모양 그대로 — 화면 404 는 브라우저 탐색에만, 나머지는 종전 응답이다."""
    with patch("src.ui.routes.detail.SessionLocal", return_value=_no_repo_db()):
        r = client.request(method, path, headers={"Accept": accept})
    is_page = r.headers.get("content-type", "").startswith("text/html") and 'class="error-page' in r.text
    assert is_page is page, f"{method} {path} Accept={accept[:30]!r} → {r.status_code} {r.headers.get('content-type')}"
    if page:
        assert r.status_code == 404


def test_non_get_requests_keep_the_default_response(client):
    """대조군 — 화면이 아닌 메서드(POST 등)의 오류는 오류 화면으로 바꾸지 않는다."""
    r = client.post("/no-such-page", headers=_BROWSER)
    assert not r.headers["content-type"].startswith("text/html"), r.headers["content-type"]
