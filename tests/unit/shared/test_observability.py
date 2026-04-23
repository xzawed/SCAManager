"""observability — Sentry SDK 초기화 테스트 (Phase E.2a, TDD Red).

`src/shared/observability.py` 모듈은 아직 없으므로 import 자체가 실패해야 정상 (Red).
"""
import os
from unittest.mock import MagicMock, patch

# conftest.py 가 실행되기 전에 필수 env var 주입 (안전장치)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

import logging

import pytest

# sentry-sdk 가 설치된 환경에서만 실행 (로컬 devcontainer DNS 제약 시 skip)
pytest.importorskip("sentry_sdk", reason="sentry-sdk not installed (CI/prod 에서만 실행)")

from src.shared import observability  # noqa: E402


def _make_settings(
    *,
    sentry_dsn: str = "",
    sentry_environment: str = "production",
    sentry_traces_sample_rate: float = 0.1,
) -> MagicMock:
    """테스트용 settings mock 생성."""
    mock = MagicMock()
    mock.sentry_dsn = sentry_dsn
    mock.sentry_environment = sentry_environment
    mock.sentry_traces_sample_rate = sentry_traces_sample_rate
    return mock


def test_init_sentry_returns_false_when_dsn_empty():
    # DSN 이 빈 문자열이면 init 을 호출하지 않고 False 반환
    with patch("src.shared.observability.settings", _make_settings(sentry_dsn="")), \
         patch("src.shared.observability.sentry_sdk.init") as mock_init:
        result = observability.init_sentry()
        assert result is False
        mock_init.assert_not_called()


def test_init_sentry_returns_true_when_dsn_set():
    # DSN 이 설정되면 sentry_sdk.init 호출 + True 반환
    with patch(
        "src.shared.observability.settings",
        _make_settings(sentry_dsn="https://abc@o1.ingest.sentry.io/123"),
    ), patch("src.shared.observability.sentry_sdk.init") as mock_init:
        result = observability.init_sentry()
        assert result is True
        mock_init.assert_called_once()


def test_init_sentry_passes_dsn_to_sdk():
    # init 호출 시 dsn 파라미터에 사용자 DSN 이 그대로 전달됨
    dsn = "https://abc@o1.ingest.sentry.io/123"
    with patch(
        "src.shared.observability.settings",
        _make_settings(sentry_dsn=dsn),
    ), patch("src.shared.observability.sentry_sdk.init") as mock_init:
        observability.init_sentry()
        kwargs = mock_init.call_args.kwargs
        assert kwargs.get("dsn") == dsn


def test_init_sentry_uses_environment_from_settings():
    # sentry_environment="staging" 이면 init 에 environment="staging" 전달
    with patch(
        "src.shared.observability.settings",
        _make_settings(
            sentry_dsn="https://abc@o1.ingest.sentry.io/123",
            sentry_environment="staging",
        ),
    ), patch("src.shared.observability.sentry_sdk.init") as mock_init:
        observability.init_sentry()
        kwargs = mock_init.call_args.kwargs
        assert kwargs.get("environment") == "staging"


def test_init_sentry_uses_default_sample_rate():
    # traces_sample_rate 기본값(0.1)이 init 에 전달됨
    with patch(
        "src.shared.observability.settings",
        _make_settings(
            sentry_dsn="https://abc@o1.ingest.sentry.io/123",
            sentry_traces_sample_rate=0.1,
        ),
    ), patch("src.shared.observability.sentry_sdk.init") as mock_init:
        observability.init_sentry()
        kwargs = mock_init.call_args.kwargs
        assert kwargs.get("traces_sample_rate") == 0.1


def test_init_sentry_includes_fastapi_integration():
    # integrations 리스트에 FastApiIntegration 인스턴스가 포함됨
    from sentry_sdk.integrations.fastapi import FastApiIntegration

    with patch(
        "src.shared.observability.settings",
        _make_settings(sentry_dsn="https://abc@o1.ingest.sentry.io/123"),
    ), patch("src.shared.observability.sentry_sdk.init") as mock_init:
        observability.init_sentry()
        kwargs = mock_init.call_args.kwargs
        integrations = kwargs.get("integrations") or []
        assert any(isinstance(i, FastApiIntegration) for i in integrations)


def test_init_sentry_returns_false_on_sdk_exception():
    # sentry_sdk.init 이 예외를 던지면 False 반환 + 예외 전파 안 함
    with patch(
        "src.shared.observability.settings",
        _make_settings(sentry_dsn="https://invalid-dsn"),
    ), patch(
        "src.shared.observability.sentry_sdk.init",
        side_effect=Exception("Invalid DSN format"),
    ):
        result = observability.init_sentry()
        assert result is False


def test_init_sentry_logs_disabled_message(caplog):
    # DSN 빈 경우 "disabled" 문자열이 INFO 로그에 기록됨
    with patch("src.shared.observability.settings", _make_settings(sentry_dsn="")), \
         patch("src.shared.observability.sentry_sdk.init"):
        with caplog.at_level(logging.INFO, logger="src.shared.observability"):
            observability.init_sentry()
    messages = " ".join(rec.getMessage() for rec in caplog.records).lower()
    assert "disabled" in messages


def test_init_sentry_logs_enabled_message(caplog):
    # DSN 설정 시 "initialized" 문자열이 INFO 로그에 기록됨
    with patch(
        "src.shared.observability.settings",
        _make_settings(
            sentry_dsn="https://abc@o1.ingest.sentry.io/123",
            sentry_environment="production",
        ),
    ), patch("src.shared.observability.sentry_sdk.init"):
        with caplog.at_level(logging.INFO, logger="src.shared.observability"):
            observability.init_sentry()
    messages = " ".join(rec.getMessage() for rec in caplog.records).lower()
    assert "initialized" in messages
