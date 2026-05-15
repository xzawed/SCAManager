"""repo_report API 엔드포인트 단위 테스트.
Unit tests for the repo_report API endpoints.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

_VALID_KEY = "test-api-key"
_AUTH = {"X-API-Key": _VALID_KEY}


@pytest.fixture(autouse=True)
def _mock_api_key(monkeypatch):
    """API 키 인증 우회 — settings 싱글톤 직접 패치.
    Bypass API key auth — patch settings singleton directly.
    """
    monkeypatch.setattr("src.api.auth.settings.api_key", _VALID_KEY)


# ── /api/repos/report ─────────────────────────────────────────────────────────

def test_list_repos_report_empty():
    """Repo 없으면 빈 목록과 summary 반환."""
    with (
        patch("src.api.repo_report.SessionLocal") as mock_sl,
        patch("src.api.repo_report.repository_repo.find_all", return_value=[]),
    ):
        mock_sl.return_value.__enter__ = lambda s: MagicMock()
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        resp = client.get("/api/repos/report", headers=_AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["repos"] == []
    assert data["summary"]["total_repos"] == 0
    assert data["summary"]["warning_count"] == 0


def test_list_repos_report_summary_grade_distribution():
    """grade_distribution 집계가 올바른지 검증."""
    repo_a = MagicMock(id=1, full_name="o/a", user_id=None)
    repo_b = MagicMock(id=2, full_name="o/b", user_id=None)

    kpi_a = {"avg_score": 90.0, "grade": "A", "score_delta": 1.0,
              "analysis_count": 5, "high_security_count": 0}
    kpi_b = {"avg_score": 45.0, "grade": "D", "score_delta": -2.0,
              "analysis_count": 3, "high_security_count": 1}

    with (
        patch("src.api.repo_report.SessionLocal"),
        patch("src.api.repo_report.repository_repo.find_all",
              return_value=[repo_a, repo_b]),
        patch("src.api.repo_report.repo_kpi", side_effect=[kpi_a, kpi_b]),
    ):
        resp = client.get("/api/repos/report", headers=_AUTH)

    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["total_repos"] == 2
    assert data["summary"]["grade_distribution"]["A"] == 1
    assert data["summary"]["grade_distribution"]["D"] == 1
    assert data["summary"]["warning_count"] == 1  # kpi_b: grade D


def test_list_repos_report_warning_from_high_security():
    """high_security_count > 0 단독으로 warning=True 트리거.
    high_security_count > 0 alone triggers warning=True.
    """
    repo_a = MagicMock(id=1, full_name="o/a", user_id=None)
    # A등급이지만 보안 HIGH 1건 — warning 트리거
    # Grade A but 1 HIGH security issue — triggers warning
    kpi_a = {"avg_score": 90.0, "grade": "A", "score_delta": 0.0,
              "analysis_count": 5, "high_security_count": 1}

    with (
        patch("src.api.repo_report.SessionLocal"),
        patch("src.api.repo_report.repository_repo.find_all", return_value=[repo_a]),
        patch("src.api.repo_report.repo_kpi", return_value=kpi_a),
    ):
        resp = client.get("/api/repos/report", headers=_AUTH)

    assert resp.status_code == 200
    data = resp.json()
    assert data["repos"][0]["warning"] is True
    assert data["summary"]["warning_count"] == 1


def test_list_repos_report_days_validation():
    """days=0 → 422."""
    resp = client.get("/api/repos/report?days=0", headers=_AUTH)
    assert resp.status_code == 422


# ── /api/repos/{name}/report ──────────────────────────────────────────────────

def test_get_repo_report_not_found():
    """존재하지 않는 repo → 404."""
    with (
        patch("src.api.repo_report.SessionLocal"),
        patch("src.api.repo_report.repository_repo.find_by_full_name",
              return_value=None),
    ):
        resp = client.get("/api/repos/owner/missing/report", headers=_AUTH)
    assert resp.status_code == 404


def test_get_repo_report_no_data():
    """분석 데이터 없는 repo → analysis_count=0, 200 응답."""
    repo = MagicMock(id=1, full_name="o/r", user_id=None)
    kpi = {"avg_score": None, "grade": "?", "score_delta": None,
           "analysis_count": 0, "top_recurring_issue": None,
           "top_recurring_count": 0, "high_security_count": 0}

    with (
        patch("src.api.repo_report.SessionLocal"),
        patch("src.api.repo_report.repository_repo.find_by_full_name",
              return_value=repo),
        patch("src.api.repo_report.repo_kpi", return_value=kpi),
        patch("src.api.repo_report.repo_recurring_issues", return_value=[]),
        patch("src.api.repo_report.repo_category_breakdown",
              return_value={"security_error": 0, "security_warning": 0,
                            "code_quality_error": 0, "code_quality_warning": 0,
                            "total": 0}),
        patch("src.api.repo_report.repo_ai_suggestions", return_value=[]),
        patch("src.api.repo_report.repo_score_trend", return_value=[]),
    ):
        resp = client.get("/api/repos/o/r/report", headers=_AUTH)

    assert resp.status_code == 200
    assert resp.json()["kpi"]["analysis_count"] == 0


def test_get_repo_report_success_schema():
    """정상 응답 스키마 필수 필드 검증."""
    repo = MagicMock(id=1, full_name="o/r", user_id=None)
    kpi = {"avg_score": 88.0, "grade": "A", "score_delta": 2.0,
           "analysis_count": 10, "top_recurring_issue": "long-line",
           "top_recurring_count": 3, "high_security_count": 0}

    with (
        patch("src.api.repo_report.SessionLocal"),
        patch("src.api.repo_report.repository_repo.find_by_full_name",
              return_value=repo),
        patch("src.api.repo_report.repo_kpi", return_value=kpi),
        patch("src.api.repo_report.repo_recurring_issues", return_value=[]),
        patch("src.api.repo_report.repo_category_breakdown",
              return_value={"security_error": 0, "security_warning": 0,
                            "code_quality_error": 0, "code_quality_warning": 0,
                            "total": 0}),
        patch("src.api.repo_report.repo_ai_suggestions", return_value=[]),
        patch("src.api.repo_report.repo_score_trend", return_value=[]),
    ):
        resp = client.get("/api/repos/o/r/report", headers=_AUTH)

    assert resp.status_code == 200
    data = resp.json()
    for key in ("repo_full_name", "days", "kpi", "recurring_issues",
                "category_breakdown", "ai_suggestions", "score_trend",
                "generated_at"):
        assert key in data, f"응답에 '{key}' 누락"


def test_get_repo_report_days_validation():
    """days=366 → 422."""
    resp = client.get("/api/repos/o/r/report?days=366", headers=_AUTH)
    assert resp.status_code == 422


def test_get_repo_report_auth_required():
    """API 키 없음 → 401 (인증 실패).
    Missing API key → 401 (authentication failure).
    """
    # settings.api_key 를 직접 mock 해야 함 — monkeypatch.setenv 는 singleton 초기화 이후라 무효
    # Must mock settings.api_key directly — monkeypatch.setenv is ineffective after singleton init
    with patch("src.api.auth.settings") as mock_settings:
        mock_settings.api_key = "real-key"
        mock_settings.app_base_url = "http://localhost"
        resp = client.get("/api/repos/o/r/report")
    assert resp.status_code == 401
