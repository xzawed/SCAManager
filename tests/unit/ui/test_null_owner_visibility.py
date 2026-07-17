"""NULL-owner 저장소 가시화 — 생성 시 경고 로그 + 개요 배너.

Surface unclaimed (NULL-owner) repositories — creation warning + overview banner.

## 왜 필요한가

`#1062` 는 NULL-owner 저장소의 **쓰기를 차단**했지만 **모집단이 줄지는 않는다** —
`worker/pipeline.py::_ensure_repo` 가 미등록 저장소 웹훅마다 계속 만들고,
`models/repository.py` 의 `ondelete="SET NULL"` 로 계정 삭제 시에도 생긴다.

차단만 하고 알리지 않으면 운영자는 **설정을 저장하려다 403 을 만나고 나서야** 이 상태를
알게 된다. 그 시점엔 원인(웹훅으로 자동 생성됨)도, 해결책(`/repos/add` 재등록)도 모른다.

**막지 않고 탐지 가능하게 만든다** — `#1060`(analysis_attempts) 과 같은 철학.
"""
import logging
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.auth.session import get_current_user, require_login
from src.main import app
from src.models.user import User as UserModel

_TEST_USER = UserModel(
    id=1, github_id="12345", github_login="testuser",
    github_access_token="gho_test", email="test@example.com", display_name="Test User",
)
app.dependency_overrides[require_login] = lambda: _TEST_USER
app.dependency_overrides[get_current_user] = lambda: _TEST_USER
client = TestClient(app)


def _ctx(db):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


# ---------------------------------------------------------------------------
# 1. 생성 시점 경고 로그 — 운영자가 Railway 로그에서 즉시 발견
# ---------------------------------------------------------------------------

def test_ensure_repo_warns_when_creating_null_owner_repo(caplog):
    """🔴 미등록 저장소 웹훅으로 NULL-owner 가 생성되면 WARNING + 조치 안내를 남긴다.

    이 로그가 없으면 운영자는 저장소가 소유자 없이 생겼다는 사실 자체를 모른다.
    """
    from src.worker import pipeline  # pylint: disable=import-outside-toplevel

    db = MagicMock()
    # find_by_full_name → None (미등록) 이어야 생성 분기로 간다
    with (
        patch("src.worker.pipeline.repository_repo.find_by_full_name", return_value=None),
        patch("src.worker.pipeline.repository_repo.save_new") as mock_save,
        patch("src.worker.pipeline.analysis_repo.find_by_sha", return_value=None),
        caplog.at_level(logging.WARNING, logger="src.worker"),
    ):
        mock_save.return_value = MagicMock(id=1, full_name="owner/unregistered", user_id=None)
        pipeline._ensure_repo(db, "owner/unregistered", "abc1234")  # pylint: disable=protected-access

    # getMessage() 가 args 보간을 표준 방식으로 처리한다 (수동 % 포맷은 placeholder 수 불일치 시 깨짐)
    # getMessage() interpolates args the standard way (manual % breaks on placeholder mismatch)
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "owner/unregistered" in joined, "경고에 저장소 이름이 없으면 어느 것인지 알 수 없다"
    assert "/repos/add" in joined, "조치 방법(재등록 경로)이 없으면 운영자가 무엇을 해야 할지 모른다"


def test_ensure_repo_does_not_warn_for_existing_repo(caplog):
    """이미 등록된 저장소는 경고하지 않는다 — 정상 경로 노이즈 0."""
    from src.worker import pipeline  # pylint: disable=import-outside-toplevel

    db = MagicMock()
    existing = MagicMock(id=1, full_name="owner/registered", user_id=1, owner=None)
    with (
        patch("src.worker.pipeline.repository_repo.find_by_full_name", return_value=existing),
        patch("src.worker.pipeline.analysis_repo.find_by_sha", return_value=None),
        caplog.at_level(logging.WARNING, logger="src.worker"),
    ):
        pipeline._ensure_repo(db, "owner/registered", "abc1234")  # pylint: disable=protected-access

    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "/repos/add" not in joined, "정상 저장소에 소유권 경고가 뜨면 노이즈다"


# ---------------------------------------------------------------------------
# 2. 개요 배너 — 운영자가 UI 에서 인지
# ---------------------------------------------------------------------------

def _render_overview(repo_user_ids):
    """주어진 user_id 목록으로 개요를 렌더한다."""
    db = MagicMock()
    repos = [
        MagicMock(id=i + 1, full_name=f"owner/r{i}", user_id=uid)
        for i, uid in enumerate(repo_user_ids)
    ]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = repos
    db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
    with (
        patch("src.ui.routes.overview.SessionLocal", return_value=_ctx(db)),
        # 실제 반환 타입은 dict[str, dict] — [] 로 두면 템플릿이 .values() 에서 죽는다
        # Real return type is dict[str, dict]; [] would break the template's .values()
        patch("src.ui.routes.overview.analysis_feedback_repo"
              ".get_calibration_by_score_range", return_value={}),
    ):
        return client.get("/")


def test_overview_shows_banner_when_unclaimed_repos_exist():
    """🔴 NULL-owner 저장소가 있으면 개요에 안내 배너가 뜬다."""
    resp = _render_overview([1, None, 1])
    assert resp.status_code == 200
    assert "overview.unclaimed" not in resp.text, "i18n 키 원문 노출 (3 로케일 미등재)"

    from src.i18n.loader import get_text  # pylint: disable=import-outside-toplevel
    # 특수문자 없는 식별 조각 — Jinja2 autoescape 가 따옴표를 바꾸므로 전문 비교 불가
    hint = get_text("overview.unclaimed_banner", "en")
    assert hint != "overview.unclaimed_banner", "i18n 키 미등재"
    assert "no registered owner" in resp.text, "unclaimed 배너가 렌더되지 않았다"


def test_overview_no_banner_when_all_repos_claimed():
    """모든 저장소에 소유자가 있으면 배너를 띄우지 않는다 — 노이즈 0."""
    resp = _render_overview([1, 1])
    assert resp.status_code == 200
    assert "no registered owner" not in resp.text, "정상 상태에 경고 배너가 뜨면 노이즈다"


def test_overview_banner_reports_accurate_count():
    """배너 카운트는 실제 NULL-owner 개수와 일치한다."""
    resp = _render_overview([1, None, None, 1, None])
    assert resp.status_code == 200
    assert "3" in resp.text, "NULL-owner 3개인데 카운트가 안 보인다"
