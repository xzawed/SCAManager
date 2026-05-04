"""feature_kill_switch — 환경변수 기반 기능 비활성화 helper 회귀 가드.

Cycle 78 PR 1 — NEW-P0-2 (5+1 cross-verify 결과 — kill-switch helper 모듈 신설).
"""
from __future__ import annotations

import pytest

from src.shared.feature_kill_switch import is_disabled


class TestIsDisabled:
    """is_disabled — `<FEATURE>_DISABLED` 환경변수 truthy 검사."""

    def test_unset_returns_false(self, monkeypatch):
        monkeypatch.delenv("FEATURE_X_DISABLED", raising=False)
        assert is_disabled("FEATURE_X") is False

    def test_one_returns_true(self, monkeypatch):
        monkeypatch.setenv("FEATURE_X_DISABLED", "1")
        assert is_disabled("FEATURE_X") is True

    def test_true_lowercase_returns_true(self, monkeypatch):
        monkeypatch.setenv("FEATURE_X_DISABLED", "true")
        assert is_disabled("FEATURE_X") is True

    def test_true_uppercase_returns_true(self, monkeypatch):
        monkeypatch.setenv("FEATURE_X_DISABLED", "TRUE")
        assert is_disabled("FEATURE_X") is True

    def test_yes_returns_true(self, monkeypatch):
        monkeypatch.setenv("FEATURE_X_DISABLED", "yes")
        assert is_disabled("FEATURE_X") is True

    def test_zero_returns_false(self, monkeypatch):
        monkeypatch.setenv("FEATURE_X_DISABLED", "0")
        assert is_disabled("FEATURE_X") is False

    def test_false_returns_false(self, monkeypatch):
        monkeypatch.setenv("FEATURE_X_DISABLED", "false")
        assert is_disabled("FEATURE_X") is False

    def test_blank_returns_false(self, monkeypatch):
        monkeypatch.setenv("FEATURE_X_DISABLED", "")
        assert is_disabled("FEATURE_X") is False

    def test_whitespace_returns_false(self, monkeypatch):
        monkeypatch.setenv("FEATURE_X_DISABLED", "   ")
        assert is_disabled("FEATURE_X") is False

    def test_one_with_whitespace_returns_true(self, monkeypatch):
        monkeypatch.setenv("FEATURE_X_DISABLED", "  1  ")
        assert is_disabled("FEATURE_X") is True

    @pytest.mark.parametrize("feature_name", [
        "SECURITY_AUTO_PROCESS",
        "SCAMANAGER_SELF_ANALYSIS",
        "TELEGRAM_INTERACTIVE",
        "SAAS_MULTITENANT",
        "OPERATIONS_DASHBOARD",
        "MOBILE_PWA",
        "SECURITY_CLASSIFY",
    ])
    def test_real_feature_names_use_correct_env_pattern(self, monkeypatch, feature_name):
        """실제 사용처 환경변수명이 `<FEATURE>_DISABLED` 패턴 정합."""
        env_name = f"{feature_name}_DISABLED"
        monkeypatch.setenv(env_name, "1")
        assert is_disabled(feature_name) is True
        monkeypatch.delenv(env_name)
        assert is_disabled(feature_name) is False
