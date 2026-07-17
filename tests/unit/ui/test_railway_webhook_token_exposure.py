"""🔴 railway_webhook_token 노출 차단 — NULL-owner 저장소에서 살아있는 토큰 평문 렌더 금지.

🔴 Block railway_webhook_token exposure — never render the live token for unclaimed repos.

## 왜 이 가드가 별도로 필요한가

`POST /webhooks/railway/{token}` (`src/webhook/providers/railway.py:30`) 은 **세션이 없다** —
인증이 URL path 의 토큰을 DB 에서 조회하는 방식(`find_by_railway_webhook_token` +
`secure_str_compare`, `:51-55`)이라 **NULL-owner 쓰기 차단(`require_write=True`) 가드가
물리적으로 붙지 않는다**. GitHub webhook 의 HMAC 서명과 성격이 전혀 다르다.

따라서 유일한 방어는 **토큰이 새어나가는 지점을 막는 것**이다. 그 지점은 하나뿐이다:
`GET /repos/{n}/settings` 는 **읽기라 NULL-owner 에게도 열려 있고**(의도된 설계),
`settings.py` 가 살아있는 토큰으로 URL 을 조립해 템플릿이 `value=` 로 평문 렌더했다.
(같은 화면의 `railway_api_token` 은 `'****'` 로 마스킹되는데 **비대칭**이었다.)

체인: 비소유자 → `GET /repos/victim/app/settings` (NULL-owner 라 통과) → 토큰 획득 →
`POST /webhooks/railway/{token}` → 세션 없음 → `railway.py:66-70` 이 NULL-owner 라 else 분기 →
**서버 전역 `settings.github_token`** 으로 피해자 저장소에 GitHub Issue 생성.

## 소유 저장소는 왜 안전한가

`get_accessible_repo` 가 타인 소유 저장소를 404 로 막으므로, 소유자 본인만 자기 토큰을 본다.
즉 **소유권 유무로 분기하면 정확히 유출 경로만 닫힌다** — 정상 셋업 흐름(토큰 복사해 Railway 에
붙여넣기)은 그대로 보존된다.
"""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.auth.session import require_login
from src.main import app
from src.models.user import User as UserModel

# test_router.py 와 동일 관용구 — require_login 은 UserModel 을 반환한다.
# Same idiom as test_router.py — require_login returns a UserModel.
_TEST_USER = UserModel(
    id=1, github_id="12345", github_login="testuser",
    github_access_token="gho_test", email="test@example.com", display_name="Test User",
)
app.dependency_overrides[require_login] = lambda: _TEST_USER
client = TestClient(app)

_LIVE_TOKEN = "deadbeefcafe1234deadbeefcafe1234"  # nosec B105 — 테스트 픽스처


def _ctx(db):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _db_with(user_id):
    """user_id 소유의 repo + 살아있는 railway_webhook_token 을 가진 config."""
    db = MagicMock()
    repo = MagicMock(id=1, full_name="owner/repo", user_id=user_id, webhook_id=None)
    db.query.return_value.filter.return_value.first.return_value = repo
    return db


def _render(user_id):
    """settings GET 을 렌더하고 응답 본문을 반환한다."""
    db = _db_with(user_id)
    config_orm = MagicMock(
        railway_webhook_token=_LIVE_TOKEN,
        railway_api_token=None,
    )
    with (
        patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(db)),
        patch("src.ui.routes.settings.repo_config_repo.find_by_full_name",
              return_value=config_orm),
        patch("src.ui.routes.settings._detect_stale_webhook", return_value=False),
    ):
        return client.get("/repos/owner%2Frepo/settings")


def test_owner_still_sees_live_webhook_url():
    """🔴 소유자는 토큰을 그대로 본다 — 정상 셋업 흐름 비회귀.

    이 테스트가 없으면 "전부 마스킹" 으로 과잉 차단해 Railway 연동 자체가 불가능해진다.
    """
    resp = _render(user_id=1)
    assert resp.status_code == 200
    assert _LIVE_TOKEN in resp.text, "소유자에게는 webhook URL 이 보여야 한다 (셋업에 필요)"


def test_null_owner_repo_never_renders_live_token():
    """🔴 NULL-owner 저장소에서는 살아있는 토큰이 응답 어디에도 없어야 한다.

    조회는 허용(설계)되지만 **시크릿은 읽기 표면에 포함되지 않는다**.
    """
    resp = _render(user_id=None)
    assert resp.status_code == 200, "조회 자체는 현행 유지 — 403 이 아니다"
    assert _LIVE_TOKEN not in resp.text, (
        "NULL-owner 저장소에 살아있는 railway webhook 토큰이 노출됐다 — "
        "비소유자가 이 토큰으로 세션 없는 POST /webhooks/railway/{token} 에 도달한다"
    )


def test_null_owner_repo_shows_unclaimed_hint_not_pending():
    """NULL-owner 에겐 '미설정(pending)' 이 아니라 '소유권 확보 필요' 로 안내한다.

    토큰이 실제로는 **설정되어 있으므로** pending 문구는 거짓이다 — 사용자가 재설정을
    시도하게 만들어 혼란을 부른다.
    """
    resp = _render(user_id=None)
    body = resp.text
    assert "railway_webhook_unclaimed" not in body, "i18n 키 원문이 노출됐다 (3 로케일 미등재)"

    from src.i18n.loader import get_text  # pylint: disable=import-outside-toplevel
    unclaimed = get_text("settings_page.inbound.railway_webhook_unclaimed", "en")
    pending = get_text("settings_page.inbound.railway_webhook_pending", "en")
    assert unclaimed != pending, "unclaimed 문구가 pending 과 같으면 안내가 거짓이 된다"

    # 🔴 Jinja2 autoescape 가 따옴표를 &#39; 로 바꾸므로 전문 비교는 못 한다 —
    # 특수문자 없는 식별 조각으로 대조한다 (escape 방식 변경에 취약하지 않도록).
    # 🔴 Jinja2 autoescape rewrites quotes, so compare a distinctive quote-free fragment.
    assert "has no registered owner" in body, "unclaimed 안내가 렌더되지 않았다"
    assert pending not in body, "pending 분기로 샜다 — 설정된 상태를 '미설정' 이라 안내하면 거짓"
