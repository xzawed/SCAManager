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


# ── async 영역 추가 (CI fix-up — patch coverage 80%+) ──
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class _FakeResp:
    def __init__(self, status_code: int, payload=None):
        self.status_code = status_code
        self._payload = payload or []
    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_fetch_alerts_ghas_inactive_silent_skip():
    """403/404 = GHAS 비활성 — silent skip + None 반환."""
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=_FakeResp(404))
    with patch("src.services.security_scan_service.get_http_client", return_value=fake_client):
        result = await security_scan_service._fetch_alerts(  # noqa: SLF001
            "tok", "owner/test", "code-scanning",
        )
    assert result is None


@pytest.mark.asyncio
async def test_fetch_alerts_success_returns_list():
    """200 = alert list 반환."""
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=_FakeResp(200, [{"number": 1}, {"number": 2}]))
    with patch("src.services.security_scan_service.get_http_client", return_value=fake_client):
        result = await security_scan_service._fetch_alerts(  # noqa: SLF001
            "tok", "owner/test", "code-scanning",
        )
    assert result == [{"number": 1}, {"number": 2}]


@pytest.mark.asyncio
async def test_fetch_alerts_http_error_returns_none():
    """httpx.HTTPError = silent + None."""
    import httpx
    fake_client = MagicMock()
    fake_client.get = AsyncMock(side_effect=httpx.ConnectError("fail"))
    with patch("src.services.security_scan_service.get_http_client", return_value=fake_client):
        result = await security_scan_service._fetch_alerts(  # noqa: SLF001
            "tok", "owner/test", "code-scanning",
        )
    assert result is None


@pytest.mark.asyncio
async def test_scan_repo_alerts_kill_switch_skip(monkeypatch):
    """kill-switch 활성 시 즉시 skip."""
    monkeypatch.setenv("SECURITY_AUTO_PROCESS_DISABLED", "1")
    repo = MagicMock(full_name="owner/test", id=1)
    counts = await security_scan_service.scan_repo_alerts(MagicMock(), repo)
    assert counts == {"code_scanning": 0, "secret_scanning": 0, "skipped": 1}


@pytest.mark.asyncio
async def test_scan_repo_alerts_no_token_skip(monkeypatch):
    """token 없음 → skip (사용자 + 전역 모두 부재)."""
    monkeypatch.delenv("SECURITY_AUTO_PROCESS_DISABLED", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    repo = MagicMock(full_name="owner/test", id=1)
    counts = await security_scan_service.scan_repo_alerts(MagicMock(), repo, user=None)
    assert counts["skipped"] == 1


@pytest.mark.asyncio
async def test_scan_all_repos_kill_switch_sentinel(monkeypatch):
    """kill-switch 활성 시 totals.skipped = -1 sentinel + 전체 skip."""
    monkeypatch.setenv("SECURITY_AUTO_PROCESS_DISABLED", "1")
    totals = await security_scan_service.scan_all_repos(MagicMock())
    assert totals["skipped"] == -1
    assert totals["repos"] == 0


@pytest.mark.asyncio
async def test_scan_all_repos_iterates_repos(monkeypatch):
    """정상 시 모든 repo 순회 + totals 누적."""
    monkeypatch.delenv("SECURITY_AUTO_PROCESS_DISABLED", raising=False)
    fake_db = MagicMock()
    repo1 = MagicMock(full_name="a/b", id=1)
    repo2 = MagicMock(full_name="c/d", id=2)
    fake_db.query.return_value.all.return_value = [repo1, repo2]
    with patch.object(
        security_scan_service, "scan_repo_alerts",
        new=AsyncMock(return_value={"code_scanning": 1, "secret_scanning": 0, "skipped": 0}),
    ):
        totals = await security_scan_service.scan_all_repos(fake_db)
    assert totals["repos"] == 2
    assert totals["code_scanning"] == 2
