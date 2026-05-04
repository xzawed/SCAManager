"""Cycle 73 F1 — security_scan_service 단위 테스트 (kill-switch + GHAS graceful + token resolve)."""
from __future__ import annotations

from src.services import security_scan_service


def test_is_kill_switch_active_default_false(monkeypatch):
    """default = OFF — kill-switch 환경변수 부재 시 False."""
    monkeypatch.delenv("SECURITY_AUTO_PROCESS_DISABLED", raising=False)
    assert security_scan_service.is_kill_switch_active() is False


def test_is_kill_switch_active_true_on_set(monkeypatch):
    """SECURITY_AUTO_PROCESS_DISABLED=1 시 True."""
    monkeypatch.setenv("SECURITY_AUTO_PROCESS_DISABLED", "1")
    assert security_scan_service.is_kill_switch_active() is True


def test_is_kill_switch_active_false_on_other_value(monkeypatch):
    """0 또는 빈 문자열 시 False — 명시 '1' 만 활성."""
    monkeypatch.setenv("SECURITY_AUTO_PROCESS_DISABLED", "0")
    assert security_scan_service.is_kill_switch_active() is False
    monkeypatch.setenv("SECURITY_AUTO_PROCESS_DISABLED", "")
    assert security_scan_service.is_kill_switch_active() is False


def test_resolve_token_user_first(monkeypatch):
    """사용자 토큰 우선 — User.plaintext_token 사용."""
    class _U:
        github_access_token = "encrypted_value"
        plaintext_token = "user_pat_xxx"
    token = security_scan_service._resolve_token(_U())  # noqa: SLF001
    assert token == "user_pat_xxx"


def test_resolve_token_global_fallback(monkeypatch):
    """user 부재 시 GITHUB_TOKEN 환경변수 fallback."""
    monkeypatch.setenv("GITHUB_TOKEN", "global_pat_yyy")
    token = security_scan_service._resolve_token(None)  # noqa: SLF001
    assert token == "global_pat_yyy"


def test_resolve_token_none_when_both_missing(monkeypatch):
    """user + 환경변수 모두 부재 시 None — 호출 측에서 skip."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    token = security_scan_service._resolve_token(None)  # noqa: SLF001
    assert token is None


def test_alert_metadata_code_scanning():
    """code-scanning alert payload → alert_type/number/severity/rule_id 정규화."""
    alert = {
        "number": 42,
        "rule": {"id": "py/unused-import", "severity": "note"},
    }
    meta = security_scan_service._alert_metadata(alert, "code-scanning")  # noqa: SLF001
    assert meta["alert_type"] == "code_scanning"
    assert meta["alert_number"] == 42
    assert meta["severity"] == "note"
    assert meta["rule_id"] == "py/unused-import"


def test_alert_metadata_secret_scanning():
    """secret-scanning alert payload → severity = high 일관 + rule_id = secret_type."""
    alert = {"number": 7, "secret_type": "telegram_bot_token"}
    meta = security_scan_service._alert_metadata(alert, "secret-scanning")  # noqa: SLF001
    assert meta["alert_type"] == "secret_scanning"
    assert meta["severity"] == "high"
    assert meta["rule_id"] == "telegram_bot_token"
