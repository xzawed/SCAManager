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
import re
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.auth.session import require_login
from src.config_manager.manager import RepoConfigData
from src.main import app
from src.models.user import User as UserModel
from src.ui.routes.settings import _NOTIFY_SECRET_FIELDS

_TEST_USER = UserModel(
    id=1, github_id="12345", github_login="testuser",
    github_access_token="gho_test", email="test@example.com", display_name="Test User",
)
app.dependency_overrides[require_login] = lambda: _TEST_USER
client = TestClient(app)

# 🔴 값 목록을 **손으로 적지 않는다** — `_NOTIFY_SECRET_FIELDS` 에서 파생한다.
#
# Grok claim-review `01a02eaf` Q4 적발: 초판은 여섯 이름을 손으로 적었고, 별도 가드는
# 「`type="password"` 태그 안에 `config.` 리터럴이 있는가」라는 **형태**만 봤다. 그러면
# 아래 세 변경이 전부 통과하면서 자격증명을 다시 노출한다:
#   · `type="password"` → `type="url"` 로 바꾸고 `config.x` 직결
#   · `<input>` → `<textarea>{{ config.email_recipients }}</textarea>`
#   · `{% set u = config.x %}` 로 한 단계 우회한 뒤 `value="{{ u }}"`
# 값을 필드 목록에서 파생해 **렌더 결과에 그 값이 있는가**로 판정하면 마크업 형태와
# 무관해진다 — 위 셋 모두 red 가 된다. 새 비밀 필드도 자동으로 덮인다.
#
# Derived from the production field list and asserted against the rendered body, so the check
# is independent of markup shape (the form-based guard had three trivial bypasses).
_SECRETS = {
    name: f"LEAK-SENTINEL-{name}-{i}"
    for i, name in enumerate(_NOTIFY_SECRET_FIELDS)
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


# 🔴 새 설정 필드는 **분류를 강제**받는다 (Grok claim-review `01a02eaf` Q4 후속).
#
# 위 가드들은 "오늘 비밀인 것"만 본다. `notify_api_key` 같은 필드가 내일 추가되면
# 어떤 가드도 발동하지 않는다 — `WEBHOOK_URL_FIELDS` 에도 없고 `type="password"` 도
# 아닐 수 있기 때문이다. 아래는 **RepoConfigData 의 모든 필드**가 둘 중 하나로
# 분류돼 있기를 요구한다. 새 필드는 이 목록에 손이 닿기 전까지 red 다.
#
# 🔴 손유지가 결함이 아니라 **독립 오라클**이다 (`test_static_input_diversity.py`
#    `_tool_applies` 와 같은 논리) — 프로덕션에서 파생하면 기대값이 결함과 함께 움직인다.
_PUBLIC_CONFIG_FIELDS = frozenset({
    "repo_full_name", "pr_review_comment", "ai_review_enabled", "approve_mode",
    "approve_threshold", "reject_threshold", "auto_merge", "merge_threshold",
    "commit_comment", "create_issue", "railway_deploy_alerts",
    "auto_merge_issue_on_failure", "notification_language", "review_model",
    "disabled_tools",
})


def test_every_config_field_is_classified_public_or_secret():
    """🔴 미분류 필드가 있으면 red — 「비밀인데 아무도 안 가리는」 상태를 못 만든다."""
    from dataclasses import fields  # pylint: disable=import-outside-toplevel

    from src.config_manager.manager import RepoConfigData  # pylint: disable=import-outside-toplevel
    from src.ui.routes.settings import (  # pylint: disable=import-outside-toplevel
        _NOTIFY_SECRET_FIELDS,
    )

    declared = {f.name for f in fields(RepoConfigData)}
    classified = _PUBLIC_CONFIG_FIELDS | set(_NOTIFY_SECRET_FIELDS)

    unclassified = declared - classified
    assert not unclassified, (
        f"분류되지 않은 설정 필드: {sorted(unclassified)}.\n"
        "→ 자격증명·PII 면 src/ui/routes/settings.py 의 `_NOTIFY_SECRET_FIELDS` 에, "
        "아니면 이 파일의 `_PUBLIC_CONFIG_FIELDS` 에 넣을 것. "
        "비밀로 넣으면 위 노출 테스트가 **자동으로** 그 필드를 덮는다."
    )

    stale = classified - declared
    assert not stale, (
        f"RepoConfigData 에 없는데 분류 목록에 남은 필드: {sorted(stale)} — 목록이 낡았다"
    )


# ── 🔴 Grok claim-review `01a02eaf` Q3 — 이 패치가 만든 데이터 유실 경로 ──────────
#
# 패치 **전**: 미소유 화면이 실값을 담았으므로, 소유권 확보 후 그 폼을 저장해도 값이 보존됐다.
# 패치 **후**: 빈값을 담으므로 같은 저장이 여섯 채널을 **지운다**.
#
# 도달 경로: 인증 사용자가 미소유 리포의 설정을 연다 → 다른 탭에서 `/repos/add` 로
# 소유권 확보(문서화된 복구 절차) → 낡은 탭에서 저장 → `require_write` 통과 → 전멸.
# hx-boost(`base.html`) 히스토리 복원도 같은 스냅샷을 되살린다.
#
# 보안 수정이 **가용성 결함을 만들면 안 된다** — 화면이 값을 못 보여주면 그 폼은
# 저장 자격도 없다. 서버가 표식으로 거절한다.


def _post(user_id, extra=None):
    """settings POST — user_id 소유 상태에서 폼을 제출한다."""
    db = MagicMock()
    repo = MagicMock(id=1, full_name="owner/repo", user_id=user_id, webhook_id=None)
    db.query.return_value.filter.return_value.first.return_value = repo
    form = {"approve_mode": "disabled", "approve_threshold": "75",
            "reject_threshold": "50", "merge_threshold": "75", **(extra or {})}
    with (
        patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(db)),
        patch("src.ui.routes.settings.upsert_repo_config") as upsert,
        patch("src.ui.routes.settings.repo_config_repo.find_by_full_name",
              return_value=MagicMock(railway_webhook_token="t", railway_api_token=None)),
    ):
        resp = client.post("/repos/owner%2Frepo/settings", data=form, follow_redirects=False)
    return resp, upsert


def test_stale_unclaimed_form_is_not_saved_even_after_the_repo_is_claimed():
    """🔴 미소유 시점에 렌더된 폼은 소유권을 얻어도 **저장되지 않는다** — 값이 지워진다.

    이 축은 「저장이 막히는가」만 본다. 「사용자가 그것을 아는가」는 아래
    `test_stale_form_redirects_with_a_visible_marker_instead_of_a_silent_409` 가 본다 —
    #1477 은 전자만 닫고 후자를 열어 뒀다(409 는 hx-boost 에서 조용하다).
    """
    _resp, upsert = _post(user_id=1, extra={"rendered_unclaimed": "1"})
    upsert.assert_not_called()


def test_a_normal_form_still_saves():
    """🔴 과잉 차단 대조군 — 표식이 없으면 정상 저장된다."""
    resp, upsert = _post(user_id=1)
    assert resp.status_code in (200, 303), f"정상 저장이 막혔다 (status={resp.status_code})"
    upsert.assert_called_once()


def test_unclaimed_page_hides_the_save_button_and_marks_itself():
    """미소유 화면은 저장 버튼을 감추고, 그래도 표식을 담는다(버튼 없이 제출될 수 있다)."""
    body = _render(user_id=None).text
    assert 'name="rendered_unclaimed"' in body, "표식이 없다 — 서버가 낡은 폼을 구별 못 한다"
    assert 'id="saveBtn"' not in body, "저장이 403 인데 버튼이 보인다"


def test_owner_page_has_the_save_button_and_no_marker():
    """대조군 — 소유자 화면은 그대로다."""
    body = _render(user_id=1).text
    assert 'id="saveBtn"' in body, "소유자 화면에서 저장 버튼이 사라졌다"
    assert 'name="rendered_unclaimed"' not in body, "소유자 폼에 표식이 붙었다 — 저장이 막힌다"


# ── 🔴 409 는 hx-boost 에서 **조용하다** (Grok claim-review `01a02ecb` F1(d) 잔여) ────
#
# #1477 은 낡은 폼을 409 로 막았다. 데이터는 안전하지만 **사용자에게 아무것도 안 보인다**:
# htmx 1.9.12 는 `200 <= status < 400` 만 swap 하고, 이 리포에는 `htmx:responseError`
# 핸들러가 **0건**이다(실측). 그래서 저장 버튼을 눌러도 화면이 그대로다 — 사용자는
# 저장이 됐다고 믿는다. 「조용한 실패」는 이 리포가 반복해서 닫아 온 형태다.
#
# 이 리포의 사용자 피드백 관용구는 **303 리다이렉트 + 쿼리 파라미터 배너**다
# (`?saved=1` · `?save_error=1`, `settings.html` 의 `save-toast`). 같은 길로 보낸다:
# 저장하지 않고 리다이렉트하면 (a) hx-boost 가 새 본문을 swap 하고 (b) 토스트가 보이며
# (c) 그 화면에는 **소유권 확보 후의 실값**이 들어 있어 바로 다시 저장할 수 있다.


def test_stale_form_redirects_with_a_visible_marker_instead_of_a_silent_409():
    """🔴 낡은 폼 제출은 **보이는** 피드백으로 끝난다 — 조용한 409 가 아니다."""
    resp, upsert = _post(user_id=1, extra={"rendered_unclaimed": "1"})
    assert resp.status_code == 303, (
        f"303 리다이렉트가 아니다 (status={resp.status_code}). "
        "409 는 hx-boost 가 swap 하지 않아 사용자에게 아무것도 보이지 않는다."
    )
    location = resp.headers.get("location", "")
    assert "stale_form=1" in location, f"리다이렉트에 표식이 없다: {location!r}"
    upsert.assert_not_called()


def test_the_stale_banner_actually_renders_and_is_translated():
    """🔴 파라미터만 붙이고 배너가 없으면 여전히 조용하다."""
    from src.i18n.loader import get_text  # pylint: disable=import-outside-toplevel

    db = MagicMock()
    repo = MagicMock(id=1, full_name="owner/repo", user_id=1, webhook_id=None)
    db.query.return_value.filter.return_value.first.return_value = repo
    config = RepoConfigData(repo_full_name="owner/repo", **_SECRETS)
    with (
        patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(db)),
        patch("src.ui.routes.settings.get_repo_config", return_value=config),
        patch("src.ui.routes.settings.repo_config_repo.find_by_full_name",
              return_value=MagicMock(railway_webhook_token=None, railway_api_token=None)),
        patch("src.ui.routes.settings._detect_stale_webhook", return_value=False),
    ):
        body = client.get("/repos/owner%2Frepo/settings?stale_form=1").text

    assert "stale_unclaimed_form" not in body, "i18n 키 원문이 노출됐다 (3 로케일 미등재)"
    # 🔴 로케일을 **렌더 결과에서 파생**한다 — 한국어로 못박으면 기본 로케일이 en 인
    #    테스트 클라이언트에서 오탐이 난다(실측). 페이지가 무엇으로 그려졌는지 물어본다.
    lang = re.search(r'<html lang="([a-z-]+)"', body)
    assert lang, "렌더된 로케일을 읽을 수 없다"
    expected = get_text("errors.stale_unclaimed_form", lang.group(1))
    fragment = expected.split(".")[0][:24]
    assert fragment in body, (
        f"낡은 폼 안내가 렌더되지 않았다 (로케일={lang.group(1)}, 조각={fragment!r})"
    )
    # 🔴 **토스트가 아니라 배너**여야 한다. `save-toast` 는 3초 뒤 사라지는데
    #    이 문구는 조치 안내 3문장이라 그 안에 안 읽힌다(실측: 캡처에 안 잡혔다).
    assert 'id="staleFormBanner"' in body, "지속 배너가 아니다 — 토스트는 3초 뒤 사라진다"
    assert 'role="alert"' in body, "스크린리더에 알림으로 전달되지 않는다"
    for loc in ("ko", "en", "ja"):
        text = get_text("errors.stale_unclaimed_form", loc)
        assert text and "stale_unclaimed_form" not in text, f"{loc} 번역 누락"


def test_a_normal_settings_page_has_no_stale_banner():
    """대조군 — 파라미터가 없으면 배너도 없다(항상 뜨면 문구가 무의미해진다)."""
    body = _render(user_id=1).text
    from src.i18n.loader import get_text  # pylint: disable=import-outside-toplevel
    lang = re.search(r'<html lang="([a-z-]+)"', body)
    assert lang, "렌더된 로케일을 읽을 수 없다"
    fragment = get_text("errors.stale_unclaimed_form", lang.group(1)).split(".")[0][:24]
    assert fragment not in body, "정상 화면에 낡은 폼 배너가 떴다"


def test_the_stale_redirect_precedes_every_write():
    """🔴 순서 불변식 — 리다이렉트가 **모든 쓰기보다 앞**이어야 한다.

    이 분기의 존재 이유는 「낡은 폼이 자격증명을 빈값으로 덮어쓰지 못하게」다. 한 줄만
    아래로 내려가도 그 목적이 사라지는데, 값은 그대로라 어떤 테스트도 안 깨진다.
    AST 로 줄 순서를 직접 잰다.
    """
    import ast  # pylint: disable=import-outside-toplevel
    from pathlib import Path  # pylint: disable=import-outside-toplevel

    root = Path(__file__).resolve().parents[3]
    tree = ast.parse((root / "src" / "ui" / "routes" / "settings.py").read_text(encoding="utf-8"))
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "update_repo_settings"
    )
    redirects = [
        n.lineno for n in ast.walk(fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "RedirectResponse"
    ]
    writes = [
        n.lineno for n in ast.walk(fn)
        if isinstance(n, ast.Call)
        and (getattr(n.func, "id", None) in ("upsert_repo_config", "encrypt_token")
             or getattr(n.func, "attr", None) == "commit")
    ]
    assert redirects, "리다이렉트를 못 찾았다 — 이 가드가 공허하다"
    assert writes, "쓰기 호출을 못 찾았다 — 이 가드가 공허하다"
    assert min(redirects) < min(writes), (
        f"낡은 폼 리다이렉트({min(redirects)}행)가 첫 쓰기({min(writes)}행)보다 뒤에 있다 — "
        "그 사이에서 자격증명이 빈값으로 덮어써진다."
    )


def test_the_redirect_url_is_built_from_the_validated_repo_not_the_path_param():
    """🔴 리다이렉트 URL 은 **DB 가 돌려준 이름**으로 만든다 (CodeQL py/url-redirection).

    경로 인자를 그대로 끼우면 검증 전 사용자 입력이 리다이렉트 URL 에 실린다.
    같은 파일의 다른 리다이렉트들이 이미 `quote(repo.full_name, safe="")` 를 쓴다 —
    이 분기만 예외로 두지 않는다.
    """
    import ast  # pylint: disable=import-outside-toplevel
    from pathlib import Path  # pylint: disable=import-outside-toplevel

    root = Path(__file__).resolve().parents[3]
    src = (root / "src" / "ui" / "routes" / "settings.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "update_repo_settings"
    )
    # stale 분기의 f-string 이 `repo_name` 을 직접 쓰지 않는지 — 이름으로 확인한다.
    stale = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.If) and any(
            isinstance(c, ast.Constant) and c.value == "rendered_unclaimed"
            for c in ast.walk(n.test)
        )
    ]
    assert len(stale) == 1, f"낡은 폼 분기를 찾지 못했다 ({len(stale)}개)"
    names = {n.id for n in ast.walk(stale[0]) if isinstance(n, ast.Name)}
    assert "safe_name" in names, "검증·인코딩된 이름을 쓰지 않는다"
    assert "repo_name" not in names, (
        "리다이렉트가 경로 인자 `repo_name` 을 직접 쓴다 — "
        '`quote(repo.full_name, safe="")` 로 만들 것.'
    )
