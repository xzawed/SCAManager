"""🔴 NULL-owner 저장소에 알림 채널 자격증명을 렌더하지 않는다.

🔴 Never render notification-channel credentials for an unclaimed (NULL-owner) repo.

## 왜 이것이 자격증명인가

Discord·Slack·n8n·custom webhook URL 은 **bearer 자격증명**이다 — URL 을 아는 사람은
누구나 그 채널에 게시할 수 있고, 별도 인증이 없다. `notify_chat_id` 는 Telegram 대상
식별자로, 봇이 붙어 있는 채팅에 메시지를 보낼 대상을 지정한다.

## 유출 경로 (실측)

`GET /repos/{n}/settings` 는 **읽기라 NULL-owner 저장소에 대해 모든 인증 사용자에게
열려 있다** — 의도된 설계다(`_helpers.py:78-80`, RLS 0026 이 `user_id IS NULL` 을
명시적으로 whitelist). 그런데 `settings.html` 이 다섯 필드를 `value=` 로 **실값 그대로**
렌더했다. `type="password"` 는 화면 표시만 가릴 뿐 DOM 에 평문이 들어 있고, 같은 화면의
`toggleFieldMask` 버튼(👁️)이 한 번의 클릭으로 벗긴다.

체인: 비소유자 → `GET /repos/victim/app/settings` (NULL-owner 라 통과) →
webhook URL 획득 → 피해자의 Discord·Slack 채널에 임의 게시.

## 소유 저장소는 왜 안전한가

`get_accessible_repo` 가 타인 소유 저장소를 404 로 막는다(`_helpers.py:96`). 즉
**소유권 유무로 분기하면 정확히 유출 경로만 닫히고** 소유자의 편집 흐름은 보존된다.
같은 화면 `railway_webhook_url` 이 이미 그 분기를 쓴다(`settings.py:156`) —
이 파일은 그 비대칭을 없앤다.

## 왜 '****' 마스킹이 아니라 소유권 분기인가

`railway_api_token` 은 `'****'` 마스킹을 쓴다. 그러나 그것은 **쓰기 전용 필드**라
가능한 것이다(POST 가 `'****'` 를 "변경 없음" 으로 해석). 알림 URL 은 소유자가 화면에서
읽고 고치는 값이라, 전 사용자에게 마스킹하면 편집 흐름이 깨진다.
"""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.auth.session import require_login
from src.config_manager.manager import RepoConfigData
from src.main import app
from src.models.user import User as UserModel

_TEST_USER = UserModel(
    id=1, github_id="12345", github_login="testuser",
    github_access_token="gho_test", email="test@example.com", display_name="Test User",
)
app.dependency_overrides[require_login] = lambda: _TEST_USER
client = TestClient(app)

# 🔴 각 값은 서로 **구별 가능**해야 한다 — 하나만 새도 어느 필드인지 실패 메시지가 지목한다.
_SECRETS = {
    "notify_chat_id": "-1001234567890",
    "discord_webhook_url": "https://discord.com/api/webhooks/111/aaaLEAKdiscord",
    "slack_webhook_url": "https://hooks.slack.com/services/T1/B1/aaaLEAKslack",
    "n8n_webhook_url": "https://n8n.example.com/webhook/aaaLEAKn8n",
    "custom_webhook_url": "https://example.com/hook/aaaLEAKcustom",
    # 🔴 감사 목록에 없었던 6번째 — 같은 `type="password"` 마스킹 필드이고 수신자 PII 다.
    "email_recipients": "leak-victim@example.com",
}


def _ctx(db):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _render(user_id):
    """주어진 소유자로 settings GET 을 렌더하고 응답을 반환한다."""
    db = MagicMock()
    repo = MagicMock(id=1, full_name="owner/repo", user_id=user_id, webhook_id=None)
    db.query.return_value.filter.return_value.first.return_value = repo
    config = RepoConfigData(repo_full_name="owner/repo", **_SECRETS)
    config_orm = MagicMock(railway_webhook_token=None, railway_api_token=None)
    with (
        patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(db)),
        patch("src.ui.routes.settings.get_repo_config", return_value=config),
        patch("src.ui.routes.settings.repo_config_repo.find_by_full_name",
              return_value=config_orm),
        patch("src.ui.routes.settings._detect_stale_webhook", return_value=False),
    ):
        return client.get("/repos/owner%2Frepo/settings")


def test_owner_still_sees_every_credential():
    """🔴 대조군 — 소유자에게는 전부 보여야 한다. 없으면 편집 자체가 불가능해진다.

    이 축이 없으면 "전부 마스킹" 으로 과잉 차단해도 초록이 된다.
    """
    resp = _render(user_id=1)
    assert resp.status_code == 200
    for name, value in _SECRETS.items():
        assert value in resp.text, f"소유자에게 {name} 이 보이지 않는다 — 편집 흐름이 깨졌다"


def test_null_owner_repo_leaks_no_notification_credential():
    """🔴 NULL-owner 저장소에서는 다섯 값 중 **어느 것도** 응답에 없어야 한다."""
    resp = _render(user_id=None)
    assert resp.status_code == 200, "조회 자체는 현행 유지 — 403 이 아니다"
    leaked = [name for name, value in _SECRETS.items() if value in resp.text]
    assert not leaked, (
        f"NULL-owner 저장소에 알림 자격증명이 노출됐다: {leaked}. "
        "비소유자가 이 URL 로 피해자의 채널에 임의 게시할 수 있다"
    )


def test_null_owner_page_still_renders_the_form():
    """과잉 차단 대조군 — 값만 비우고 **필드 자체는 남는다**.

    폼이 통째로 사라지면 소유권을 확보한 뒤에도 화면이 달라 보여 혼란스럽다.
    """
    resp = _render(user_id=None)
    for name in _SECRETS:
        assert f'name="{name}"' in resp.text, f"{name} 입력 필드가 사라졌다 — 값만 비워야 한다"


# ── 구조 가드 — 다음에 추가되는 비밀 필드도 잡는다 ─────────────────────────────
#
# 위 세 축은 **오늘 아는 6개 필드**만 본다. 7번째가 추가되면 조용히 통과한다.
# 아래 둘은 그 드리프트를 잡는다. `email_recipients` 가 정확히 그 사례였다 —
# 감사 목록에 없었고, 값 단위 테스트만 있었다면 지금도 새고 있었을 것이다.


def test_every_write_validated_webhook_url_is_read_redacted():
    """🔴 쓰기에서 SSRF 검증하는 URL 은 읽기에서도 가려져야 한다.

    두 목록이 따로 늙으면 「저장 시엔 자격증명 취급, 렌더 시엔 평문」인 필드가 생긴다.
    """
    from src.ui.routes.settings import (  # pylint: disable=import-outside-toplevel
        _NOTIFY_SECRET_FIELDS, WEBHOOK_URL_FIELDS,
    )
    assert WEBHOOK_URL_FIELDS, "검증 대상이 비었다 — 이 가드가 공허하다"
    missing = set(WEBHOOK_URL_FIELDS) - set(_NOTIFY_SECRET_FIELDS)
    assert not missing, (
        f"쓰기에서 검증하지만 읽기에서 가리지 않는 webhook 필드: {sorted(missing)}"
    )


def test_no_password_input_renders_config_directly():
    """🔴 템플릿 축 — `type="password"` 필드가 `config.<x>` 를 직접 렌더하면 안 된다.

    비밀 값은 `secrets` dict 를 거쳐야 한다(`renderable_secrets` 가 소유권으로 분기하는
    유일한 자리). 이 단언은 **새 필드를 `config.` 로 붙이는 순간** red 가 된다 —
    필드 이름을 여기 나열하지 않으므로 목록이 낡지 않는다.

    연결 상태 점(`conn-dot`)의 `{% if config.x %}` 는 input 태그 밖이라 걸리지 않는다.
    """
    import re  # pylint: disable=import-outside-toplevel
    from pathlib import Path  # pylint: disable=import-outside-toplevel

    tpl = (Path(__file__).resolve().parents[3] / "src" / "templates" / "settings.html")
    html = tpl.read_text(encoding="utf-8")
    inputs = re.findall(r"<input\b[^>]*>", html, re.DOTALL)
    assert inputs, "input 태그를 하나도 못 찾았다 — 이 가드가 공허하다"

    password_inputs = [t for t in inputs if 'type="password"' in t]
    assert password_inputs, "password 입력이 0개 — 파싱이 깨졌거나 필드가 사라졌다"

    offenders = [t for t in password_inputs if "config." in t]
    assert not offenders, (
        "비밀 입력이 config 를 직접 렌더한다 — 소유권 분기를 우회한다:\n"
        + "\n".join(t[:160] for t in offenders)
    )


def test_unclaimed_hint_is_shown_and_translated():
    """값을 비웠으면 **이유를 말한다** — 점은 켜져 있는데 값만 비면 '미설정' 으로 오독된다."""
    from src.i18n.loader import get_text  # pylint: disable=import-outside-toplevel

    body = _render(user_id=None).text
    assert "unclaimed_hidden" not in body, "i18n 키 원문이 노출됐다 (3 로케일 미등재)"
    assert "has no registered owner" in body, "미등록 안내가 렌더되지 않았다"
    for loc in ("ko", "en", "ja"):
        text = get_text("settings_page.notify.unclaimed_hidden", loc)
        assert text and "unclaimed_hidden" not in text, f"{loc} 번역 누락"


def test_owner_does_not_see_the_unclaimed_hint():
    """대조군 — 소유자 화면에는 그 안내가 없다(항상 표시하면 문구가 무의미해진다)."""
    assert "has no registered owner" not in _render(user_id=1).text
