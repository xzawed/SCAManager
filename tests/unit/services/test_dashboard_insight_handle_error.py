"""_handle_insight_error 헬퍼 단위 테스트.
Unit tests for the _handle_insight_error helper extracted from insight_narrative.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


def _make_db():
    return MagicMock()


def _now():
    return datetime(2026, 5, 30, 12, 0, 0, tzinfo=timezone.utc)


def test_handle_insight_error_with_user_id_records_error():
    """user_id가 있으면 cache_repo.record_error가 호출되어야 한다.
    record_error must be called when user_id is provided.
    """
    from src.services.dashboard_service import _handle_insight_error  # pylint: disable=import-outside-toplevel

    mock_db = _make_db()
    with patch("src.services.dashboard_service.insight_narrative_cache_repo") as mock_repo:
        result = _handle_insight_error(
            mock_db,
            user_id=42,
            days=7,
            language="en",
            error_type="no_data",
            now=_now(),
        )

    mock_repo.record_error.assert_called_once_with(
        mock_db, user_id=42, days=7, language="en", error_type="no_data", now=_now(),
    )
    assert result["status"] == "no_data"
    assert result["days"] == 7


def test_handle_insight_error_without_user_id_skips_cache():
    """user_id=None이면 cache_repo.record_error가 호출되지 않아야 한다.
    record_error must NOT be called when user_id is None.
    """
    from src.services.dashboard_service import _handle_insight_error  # pylint: disable=import-outside-toplevel

    mock_db = _make_db()
    with patch("src.services.dashboard_service.insight_narrative_cache_repo") as mock_repo:
        result = _handle_insight_error(
            mock_db,
            user_id=None,
            days=7,
            language="ko",
            error_type="api_error",
            now=_now(),
        )

    mock_repo.record_error.assert_not_called()
    assert result["status"] == "api_error"


def test_handle_insight_error_returns_correct_status_for_each_error_type():
    """각 error_type에 맞는 status를 가진 응답을 반환해야 한다.
    Must return response with matching status for each error_type.
    """
    from src.services.dashboard_service import _handle_insight_error  # pylint: disable=import-outside-toplevel

    mock_db = _make_db()
    for error_type in ("no_data", "api_error", "parse_error"):
        with patch("src.services.dashboard_service.insight_narrative_cache_repo"):
            result = _handle_insight_error(
                mock_db, user_id=None, days=7, language="en",
                error_type=error_type, now=_now(),
            )
        assert result["status"] == error_type, f"expected {error_type}, got {result['status']}"
