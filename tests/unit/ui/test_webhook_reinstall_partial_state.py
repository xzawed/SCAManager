"""Webhook 재설치가 **정리 실패를 성공으로 보고**하는 문제 (#1504 R1).

🔴 실측한 결함 — 부분 성공이 완전 성공으로 보인다.

`reinstall_webhook` 은 두 단계다:

1. `list_webhooks` → 기존 SCAManager 훅을 **전부 삭제**  (중복 정리)
2. `create_webhook` → 새 훅 + 새 secret 생성, DB 커밋

1단계가 **전송 오류로** 실패하면 `except` 가 로그만 남기고 그대로 2단계로 간다
(`settings.py` — "Webhook cleanup failed, proceeding with reinstall"). 결과:

- GitHub 에 훅이 **2개** 남는다 (옛 것 + 새 것)
- DB 는 **새 secret 만** 안다 → 옛 훅의 배달은 서명 검증에 실패
- 사용자에게는 `hook_ok=1` — **완전 성공으로 보인다**

즉 「중복 웹훅도 모두 정리한다」는 이 라우트의 docstring 계약이 조용히 깨지고,
그 사실이 **어디에도 표시되지 않는다.**

🔴 이 결함은 `httpx.HTTPError` 하나로도 이미 재현된다 — #1498 의 `except` 확대가
만든 것이 아니다. 확대는 도달 가능한 예외 종류만 늘렸다.

🔴 **정리 실패 시 재설치를 중단하지 않는다.** 그것이 옳은 설계다 — 훅이 하나도 없는
상태(재설치 실패)가 훅이 두 개인 상태보다 나쁘다. 고치는 것은 **보고**다:
부분 성공을 부분 성공이라고 말한다.

A cleanup failure is reported as full success (`hook_ok=1`), leaving a stale hook on GitHub
whose deliveries now fail signature verification. The fix is honest reporting, not aborting.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")

from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.auth.session import require_login  # noqa: E402
from src.main import app  # noqa: E402
from src.models.user import User as UserModel  # noqa: E402

_test_user = UserModel(
    id=1, github_id="12345", github_login="testuser",
    github_access_token="gho_test", email="test@example.com", display_name="Test User",
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _login_as_test_user():
    """require_login 을 테스트 시점에 override 하고 복원한다 (import 순서 무관 격리)."""
    prev = app.dependency_overrides.get(require_login)
    app.dependency_overrides[require_login] = lambda: _test_user
    yield
    if prev is None:
        app.dependency_overrides.pop(require_login, None)
    else:
        app.dependency_overrides[require_login] = prev


def _ctx(db_mock):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_mock)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _db():
    db = MagicMock()
    repo = MagicMock(id=1, full_name="owner/repo", user_id=1, webhook_id=999)
    db.query.return_value.filter.return_value.first.return_value = repo
    db.query.return_value.filter.return_value.all.return_value = []
    return db


def _post(*, list_side_effect=None, list_return=None):
    db = _db()
    with patch("src.ui.routes.settings.list_webhooks", new_callable=AsyncMock,
               side_effect=list_side_effect, return_value=list_return) as mock_list, \
         patch("src.ui.routes.settings.delete_webhook", new_callable=AsyncMock) as mock_del, \
         patch("src.ui.routes.settings.create_webhook",
               new_callable=AsyncMock, return_value=12345) as mock_create, \
         patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(db)):
        resp = client.post("/repos/owner%2Frepo/reinstall-webhook", follow_redirects=False)
    return resp, db, mock_list, mock_del, mock_create


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_clean_reinstall_reports_full_success():
    """대조군 — 정리가 성공하면 지금처럼 `hook_ok=1` 이다 (계약 불변)."""
    resp, db, _, mock_del, mock_create = _post(list_return=[
        {"id": 111, "config": {"url": "https://x.test/webhooks/github"}},
    ])

    assert resp.status_code == 303
    assert "webhook_ok=1" in resp.headers["location"]
    mock_del.assert_awaited_once()
    mock_create.assert_awaited_once()
    db.commit.assert_called_once()


# ─── 결함 — 정리 실패가 완전 성공으로 보고된다 ────────────────────────────────


def test_cleanup_failure_is_not_reported_as_full_success():
    """🔴 정리 실패 → 새 훅은 만들되 **완전 성공이라고 말하지 않는다**.

    지금은 `hook_ok=1` 이라 사용자가 「중복이 정리됐다」고 믿는다. 실제로는 옛 훅이
    GitHub 에 남아 있고, DB 는 새 secret 만 알아 그 훅의 배달은 전부 서명 검증에
    실패한다 — 조용한 중복 배달 + 조용한 실패다.
    """
    resp, db, _, mock_del, mock_create = _post(
        list_side_effect=httpx.ConnectError("network down"),
    )

    # 재설치 자체는 계속한다 — 훅 0개가 훅 2개보다 나쁘다.
    mock_create.assert_awaited_once()
    db.commit.assert_called_once()
    mock_del.assert_not_awaited()

    assert resp.status_code == 303
    location = resp.headers["location"]
    assert "webhook_ok=1" not in location, (
        "정리에 실패했는데 완전 성공으로 보고한다 — 옛 훅이 GitHub 에 남아 있고 "
        f"그 배달은 새 secret 으로 검증돼 전부 실패한다: {location}"
    )
    assert "webhook_partial=1" in location, (
        f"부분 성공 신호가 없다 — 사용자가 알 방법이 없다: {location}"
    )


def test_create_failure_still_reports_hook_fail():
    """대조군 — 생성 실패는 여전히 `hook_fail=1` 이다 (부분 성공과 구분).

    셋이 구분돼야 한다: 완전 성공 / **부분 성공** / 실패.
    부분 성공을 실패로 뭉뚱그리면 사용자가 훅이 없다고 오해한다.
    """
    db = _db()
    with patch("src.ui.routes.settings.list_webhooks", new_callable=AsyncMock, return_value=[]), \
         patch("src.ui.routes.settings.delete_webhook", new_callable=AsyncMock), \
         patch("src.ui.routes.settings.create_webhook", new_callable=AsyncMock,
               side_effect=httpx.ConnectError("boom")), \
         patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(db)):
        resp = client.post("/repos/owner%2Frepo/reinstall-webhook", follow_redirects=False)

    assert resp.status_code == 303
    assert "webhook_fail=1" in resp.headers["location"]
    db.commit.assert_not_called()


def test_cleanup_delete_failure_also_counts_as_partial():
    """개별 훅 **삭제**가 실패해도 부분 성공이다 — 목록 조회만의 문제가 아니다.

    `list_webhooks` 는 성공했는데 `delete_webhook` 이 실패하면 그 훅이 남는다.
    같은 결과(옛 훅 잔존)이므로 같은 신호여야 한다.
    """
    db = _db()
    with patch("src.ui.routes.settings.list_webhooks", new_callable=AsyncMock, return_value=[
                   {"id": 111, "config": {"url": "https://x.test/webhooks/github"}}]), \
         patch("src.ui.routes.settings.delete_webhook", new_callable=AsyncMock,
               side_effect=httpx.ConnectError("delete failed")), \
         patch("src.ui.routes.settings.create_webhook",
               new_callable=AsyncMock, return_value=12345), \
         patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(db)):
        resp = client.post("/repos/owner%2Frepo/reinstall-webhook", follow_redirects=False)

    assert "webhook_partial=1" in resp.headers["location"], (
        f"삭제 실패로 옛 훅이 남았는데 부분 성공 신호가 없다: {resp.headers['location']}"
    )


# ─── 선행 결함 — 두 라우트가 같은 플래그·같은 배너를 쓴다 ─────────────────────
#
# 🔴 측정 중 발견. `reinstall-hook`(CLI 훅 파일 커밋)과 `reinstall-webhook`
#    (GitHub 웹훅 재등록)이 **둘 다** `hook_ok=1` / `hook_fail=1` 로 리다이렉트하고,
#    settings 페이지에는 그 플래그를 읽는 배너가 **하나뿐**이다. 그 배너는
#    `section_cli_hook` 아래에 있고 문구가 「`.scamanager/` 파일이 Repo에 커밋됐습니다」다.
#
#    즉 **웹훅을 재설치해도 CLI 훅 파일 메시지가 뜬다.** 웹훅 재설치에는 오늘
#    올바른 피드백이 **전혀 없다.**
#
# 이 결함이 있으면 위에서 만든 `hook_partial` 도 잘못된 자리에 뜬다 — 플래그만
# 만들고 소비 지점을 안 고치면 무의미하다(정의 ≠ 배선).


def test_settings_page_accepts_the_partial_flag():
    """🔴 배선 — settings 페이지가 `hook_partial` 을 **읽어야** 한다.

    라우트가 안 받으면 쿼리는 조용히 버려지고 배너는 영영 안 뜬다.
    """
    import inspect  # noqa: PLC0415

    from src.ui.routes import settings as mod  # noqa: PLC0415

    params = inspect.signature(mod.repo_settings).parameters
    assert "webhook_partial" in params or "hook_partial" in params, (
        "settings 라우트가 부분-성공 플래그를 인자로 받지 않는다 — 리다이렉트가 "
        f"보낸 쿼리가 버려진다. 현재 인자: {sorted(params)}"
    )


def test_webhook_and_cli_hook_banners_are_not_the_same_flag():
    """🔴 웹훅 재설치와 CLI 훅 커밋이 **다른** 플래그를 쓴다.

    지금은 둘 다 `hook_ok=1` 이라, GitHub 웹훅을 재등록해도
    「`.scamanager/` 파일이 커밋됐습니다」라는 **엉뚱한 문구**가 뜬다.
    두 동작은 서로 무관하므로 신호도 분리돼야 한다.
    """
    import inspect  # noqa: PLC0415

    from src.ui.routes import settings as mod  # noqa: PLC0415

    import re  # noqa: PLC0415

    src = inspect.getsource(mod.reinstall_webhook)
    # 🔴 부분 문자열로 보면 안 된다 — `"webhook_ok=1"` 이 `"hook_ok=1"` 을 **포함**한다.
    #   경계를 둬서 CLI 훅 플래그만 정확히 찾는다(첫 판이 이 함정에 걸렸다).
    # Substring would match webhook_ok=1; anchor the boundary.
    cli_flags = re.findall(r'(?<![\w])hook_(?:ok|fail|partial)=1', src)
    assert not cli_flags, (
        "웹훅 재설치가 CLI 훅과 같은 플래그를 쓴다 — 사용자에게 "
        f"`.scamanager/ 파일이 커밋됐습니다` 라는 무관한 메시지가 뜬다: {cli_flags}"
    )
    assert "webhook_ok" in src, "웹훅 전용 성공 플래그가 없다"


def test_partial_banner_renders_in_the_github_webhook_section():
    """🔴 배선 끝단 — 부분-성공 배너가 **GitHub Webhook 섹션 안**에 렌더된다.

    플래그·라우트·i18n 이 다 있어도 템플릿이 안 읽으면 화면에 아무것도 안 뜬다.
    그리고 CLI Hook 섹션에 뜨면 엉뚱한 자리다 — 위치까지 본다.
    """
    import pathlib  # noqa: PLC0415

    root = pathlib.Path(__file__).resolve().parents[3]
    html = (root / "src" / "templates" / "settings.html").read_text(encoding="utf-8")

    gh = html.find("settings_page.inbound.section_github_webhook")
    cli = html.find("settings_page.inbound.section_cli_hook")
    assert gh != -1 and cli != -1, "섹션 라벨을 못 찾았다 — 스캐너 점검 필요"
    assert gh < cli, "GitHub Webhook 섹션이 CLI Hook 섹션보다 뒤에 있다 — 전제 변경"

    section = html[gh:cli]
    for flag in ("webhook_ok", "webhook_partial", "webhook_fail"):
        assert flag in section, (
            f"`{flag}` 배너가 GitHub Webhook 섹션 안에 없다 — 플래그가 화면에 "
            "도달하지 않거나 엉뚱한 섹션에 있다"
        )

    assert ".hook-alert.warn" in html, (
        "부분 성공용 스타일(.hook-alert.warn)이 없다 — ok/fail 중 하나로 칠하면 "
        "「다 됐다」 또는 「아무것도 안 됐다」로 오독된다"
    )


def test_partial_banner_text_exists_in_every_language():
    """i18n 3종에 세 키가 모두 있다 — 하나라도 빠지면 그 로케일에서 빈 배너가 뜬다."""
    import json  # noqa: PLC0415
    import pathlib  # noqa: PLC0415

    root = pathlib.Path(__file__).resolve().parents[3]
    missing = {}
    for lang in ("ko", "en", "ja"):
        data = json.loads(
            (root / "src" / "i18n" / "translations" / f"{lang}.json").read_text(encoding="utf-8")
        )
        inbound = data["settings_page"]["inbound"]
        absent = [
            k for k in ("webhook_ok", "webhook_partial", "webhook_fail")
            if not (inbound.get(k) or "").strip()
        ]
        if absent:
            missing[lang] = absent
    assert not missing, f"번역 누락 — 그 로케일에서 배너가 비어 보인다: {missing}"
