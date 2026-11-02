"""Dashboard repos 모드 단위 테스트.
Unit tests for the Dashboard repos mode branch.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.ui.routes.dashboard import _VALID_MODES, _build_repo_summary

client = TestClient(__import__("src.main", fromlist=["app"]).app)


@contextmanager
def _ctx(db):
    """SessionLocal 컨텍스트 매니저 mock 헬퍼.
    Mock context manager helper for SessionLocal.
    """
    yield db


def test_repos_mode_in_valid_modes():
    """'repos'가 _VALID_MODES에 포함되어야 한다."""
    assert "repos" in _VALID_MODES


def test_build_repo_summary_empty():
    """Repo 없을 때 요약 반환."""
    db = MagicMock()
    with patch("src.ui.routes.dashboard.repository_repo.find_all_by_user",
               return_value=[]):
        result = _build_repo_summary(db, user_id=1, days=30)
    assert result["repos"] == []
    assert result["summary"]["total_repos"] == 0
    assert result["summary"]["warning_count"] == 0


def test_build_repo_summary_grade_distribution():
    """등급 분포 집계 검증."""
    repo_a = MagicMock(id=1, full_name="o/a", user_id=1)
    repo_b = MagicMock(id=2, full_name="o/b", user_id=None)
    kpi_a = {"avg_score": 90.0, "grade": "A", "score_delta": 1.0,
              "analysis_count": 5, "high_security_count": 0}
    kpi_b = {"avg_score": 40.0, "grade": "F", "score_delta": -5.0,
              "analysis_count": 2, "high_security_count": 2}

    db = MagicMock()
    with (
        patch("src.ui.routes.dashboard.repository_repo.find_all_by_user",
              return_value=[repo_a, repo_b]),
        patch("src.ui.routes.dashboard.repo_kpi", side_effect=[kpi_a, kpi_b]),
    ):
        result = _build_repo_summary(db, user_id=1, days=30)

    assert result["summary"]["grade_distribution"]["A"] == 1
    assert result["summary"]["grade_distribution"]["F"] == 1
    assert result["summary"]["warning_count"] == 1  # repo_b (grade F)
    assert len(result["warning_repos"]) == 1
    assert result["warning_repos"][0]["full_name"] == "o/b"


def test_repos_mode_no_repo_selected():
    """repos 모드 진입 — repo 미선택 시 200 응답."""
    from src.auth.session import require_login, CurrentUser
    from src.main import app

    fake_user = CurrentUser(
        id=1,
        github_login="testuser",
        email="test@example.com",
        display_name="Test User",
        plaintext_token="",
    )
    mock_db = MagicMock()
    # _build_repo_summary 를 mock 하여 실제 DB 접근 방지
    # Mock _build_repo_summary to avoid real DB access
    fake_summary = {
        "repos": [],
        "summary": {"total_repos": 0, "avg_score": None,
                    "grade_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0},
                    "warning_count": 0},
        "warning_repos": [],
    }

    _saved = dict(app.dependency_overrides)
    app.dependency_overrides[require_login] = lambda: fake_user
    try:
        with (
            patch("src.ui.routes.dashboard.SessionLocal", return_value=_ctx(mock_db)),
            patch("src.ui.routes.dashboard._build_repo_summary", return_value=fake_summary),
        ):
            # 🔴 모듈 최상위의 `client` 를 쓰지 않는다. 그것은 **임포트 때의** app 을
            #    감싸는데, 이 테스트는 **호출 때의** app 에 override 를 건다.
            #    `tests/unit/test_main.py` 가 `importlib.reload(main_mod)` 로 app 객체를
            #    갈아치우므로 둘이 다른 인스턴스가 되고, override 가 닿지 않아 실제
            #    `require_login` 이 돌아 404 가 난다.
            #    같은 객체로 클라이언트를 만들어 그 틈을 없앤다.
            # The module-level client wraps the app captured at import; a reload elsewhere
            # swaps `src.main.app`, so the override lands on a different instance.
            resp = TestClient(app).get("/dashboard?mode=repos")
        assert resp.status_code in (200, 307)  # 307 = 로그인 리다이렉트 허용
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(_saved)


def test_repos_mode_in_valid_modes_endpoint():
    """repos가 유효 모드로 처리됨 (invalid 모드 fallback 되지 않음)."""
    assert "repos" in _VALID_MODES
    invalid = "nonexistent"
    assert invalid not in _VALID_MODES


def test_repos_report_marks_issue_basis_when_window_exceeds_30():
    """repos 레포트 — 분석 45건이면 라우트가 `issue_basis`=30 을 넘겨 «최근 30건» 표기가 렌더된다.
    The repos report route passes issue_basis=30 for 45 analyses and the note renders.
    """
    from src.auth.session import require_login, CurrentUser
    from src.main import app

    fake_user = CurrentUser(id=1, github_login="testuser", email="test@example.com",
                            display_name="Test User", plaintext_token="")
    fake_summary = {
        "repos": [], "summary": {"total_repos": 0, "avg_score": None,
                                 "grade_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0},
                                 "warning_count": 0},
        "warning_repos": [],
    }
    kpi = {"avg_score": 80.0, "grade": "B", "score_delta": None, "analysis_count": 45,
           "high_security_count": 0, "top_recurring_issue": None, "top_recurring_count": 0}
    breakdown = {"security_error": 0, "security_warning": 0, "code_quality_error": 0,
                 "code_quality_warning": 0, "total": 0}
    _saved = dict(app.dependency_overrides)
    app.dependency_overrides[require_login] = lambda: fake_user
    try:
        with (
            patch("src.ui.routes.dashboard.SessionLocal", return_value=_ctx(MagicMock())),
            patch("src.ui.routes.dashboard._build_repo_summary", return_value=fake_summary),
            patch("src.ui.routes.dashboard.repository_repo.find_by_full_name",
                  return_value=MagicMock(id=7, full_name="o/r", user_id=1)),
            patch("src.ui.routes.dashboard.repo_kpi", return_value=kpi),
            patch("src.ui.routes.dashboard.repo_recurring_issues", return_value=[]),
            patch("src.ui.routes.dashboard.repo_category_breakdown", return_value=breakdown),
            patch("src.ui.routes.dashboard.repo_ai_suggestions", return_value=[]),
            patch("src.ui.routes.dashboard.repo_score_trend", return_value=[]),
        ):
            resp = TestClient(app).get("/dashboard?mode=repos&repo=o/r", headers={"Accept-Language": "ko"})
        assert resp.status_code == 200
        assert "이슈 집계는 최근 분석 30건 기준" in resp.text
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(_saved)


def _render_repos_report(trend_unverified: int, locale: str = "ko") -> str:
    """repos 레포트를 렌더한다 — 추세 점 2개(차트 구역이 그려지는 최소)와 주어진 미검증 수로.
    Render the repos report with a two-point trend (the chart section's minimum) and the given count.
    """
    from src.auth.session import require_login, CurrentUser
    from src.main import app

    fake_user = CurrentUser(id=1, github_login="testuser", email="test@example.com",
                            display_name="Test User", plaintext_token="")
    fake_summary = {
        "repos": [], "summary": {"total_repos": 0, "avg_score": None,
                                 "grade_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0},
                                 "warning_count": 0},
        "warning_repos": [],
    }
    kpi = {"avg_score": None, "grade": "?", "score_delta": None, "analysis_count": 4,
           "high_security_count": 0, "top_recurring_issue": None, "top_recurring_count": 0}
    breakdown = {"security_error": 0, "security_warning": 0, "code_quality_error": 0,
                 "code_quality_warning": 0, "total": 0}
    trend = [{"date": "2026-10-19", "avg_score": 70.0, "count": 2},
             {"date": "2026-10-20", "avg_score": 72.0, "count": 2}]
    _saved = dict(app.dependency_overrides)
    app.dependency_overrides[require_login] = lambda: fake_user
    try:
        with (
            patch("src.ui.routes.dashboard.SessionLocal", return_value=_ctx(MagicMock())),
            patch("src.ui.routes.dashboard._build_repo_summary", return_value=fake_summary),
            patch("src.ui.routes.dashboard.repository_repo.find_by_full_name",
                  return_value=MagicMock(id=7, full_name="o/r", user_id=1)),
            patch("src.ui.routes.dashboard.repo_kpi", return_value=kpi),
            patch("src.ui.routes.dashboard.repo_recurring_issues", return_value=[]),
            patch("src.ui.routes.dashboard.repo_category_breakdown", return_value=breakdown),
            patch("src.ui.routes.dashboard.repo_ai_suggestions", return_value=[]),
            patch("src.ui.routes.dashboard.repo_score_trend", return_value=trend),
            # create=True — 되돌린 코드에 이름이 없어도 패치가 «오류» 가 아니라 단언에서 빨갛게 한다.
            # create=True so reverted code fails the assertion instead of erroring in patch().
            patch("src.ui.routes.dashboard.repo_trend_unverified_count",
                  return_value=trend_unverified, create=True),
        ):
            resp = TestClient(app).get("/dashboard?mode=repos&repo=o/r",
                                       headers={"Accept-Language": locale})
        assert resp.status_code == 200
        return resp.text
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(_saved)


def _trend_notes(html: str) -> list[str]:
    """`repos-trend-note` 문단의 글자 — 요소 단위로 읽는다(부분문자열 판정 금지).
    Text of each repos-trend-note paragraph, read per element.
    """
    import re  # noqa: PLC0415

    return [re.sub(r"\s+", " ", m).strip()
            for m in re.findall(r'<p class="repos-trend-note">(.*?)</p>', html, re.S)]


def test_repos_report_notes_unverified_scores_inside_the_trend():
    """추세가 미검증 점수까지 평균하면 차트 아래에 그 수를 적는다 — 리포 표의 평균·등급은 검증만 쓴다.
    When the trend averages unverified scores, the report states how many under the chart.
    """
    from src.i18n.loader import get_text

    for locale in ("ko", "en", "ja"):
        html = _render_repos_report(3, locale)
        assert 'id="repoTrendChart"' in html, "추세 구역이 안 그려졌다 — 표기를 잴 자리가 없다"
        assert _trend_notes(html) == [
            get_text("dashboard.trend_includes_unverified", locale, count=3)], locale


def test_repos_report_has_no_unverified_note_when_the_trend_is_all_verified():
    """미검증이 0 이면 표기가 없다 — 같은 화면(추세 구역은 그려짐)이 대조군이다.
    No note at zero; the same page with the trend section drawn is the control.
    """
    html = _render_repos_report(0)
    assert 'id="repoTrendChart"' in html, "추세 구역이 안 그려졌다 — 「없음」을 잴 수 없다"
    assert _trend_notes(html) == []
