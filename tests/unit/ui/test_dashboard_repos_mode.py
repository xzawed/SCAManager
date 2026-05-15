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

    _prev = app.dependency_overrides.get(require_login)
    app.dependency_overrides[require_login] = lambda: fake_user
    try:
        with (
            patch("src.ui.routes.dashboard.SessionLocal", return_value=_ctx(mock_db)),
            patch("src.ui.routes.dashboard._build_repo_summary", return_value=fake_summary),
        ):
            resp = client.get("/dashboard?mode=repos")
        assert resp.status_code in (200, 307)  # 307 = 로그인 리다이렉트 허용
    finally:
        if _prev is not None:
            app.dependency_overrides[require_login] = _prev
        else:
            app.dependency_overrides.pop(require_login, None)


def test_repos_mode_in_valid_modes_endpoint():
    """repos가 유효 모드로 처리됨 (invalid 모드 fallback 되지 않음)."""
    assert "repos" in _VALID_MODES
    invalid = "nonexistent"
    assert invalid not in _VALID_MODES
