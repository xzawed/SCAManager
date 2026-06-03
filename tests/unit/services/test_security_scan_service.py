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


@pytest.mark.asyncio
async def test_scan_all_repos_rollback_on_repo_error(monkeypatch):
    """repo 처리 중 에러 전파 시 db.rollback() 으로 세션 오염 차단 (사이클 159 — 158 회고 P2).

    회귀 가드: outer except 에 rollback 부재 시 poisoned session 이 다음 repo 로 연쇄 실패.
    Regression guard: without rollback, a poisoned session cascades into the next repo.
    """
    monkeypatch.delenv("SECURITY_AUTO_PROCESS_DISABLED", raising=False)
    from sqlalchemy.exc import SQLAlchemyError
    fake_db = MagicMock()
    repo1 = MagicMock(full_name="a/b", id=1)
    repo2 = MagicMock(full_name="c/d", id=2)
    fake_db.query.return_value.all.return_value = [repo1, repo2]
    with patch.object(
        security_scan_service, "scan_repo_alerts",
        new=AsyncMock(side_effect=SQLAlchemyError("boom")),
    ):
        totals = await security_scan_service.scan_all_repos(fake_db)
    # 두 repo 모두 에러 → repos 카운트 증가, repo 당 rollback 1회 (총 2회)
    # Both repos error → repos counted, rollback called once per repo (2 total)
    assert totals["repos"] == 2
    assert fake_db.rollback.call_count == 2


def test_resolve_token_user_plaintext_none_falls_back_to_env(monkeypatch):
    """user.plaintext_token=None 이어도 GITHUB_TOKEN 환경변수 fallback 보장.
    Falls back to GITHUB_TOKEN env when user.plaintext_token is None, even if github_access_token exists."""
    class _U:
        # 암호화된 blob 은 있으나 복호화 결과가 None 인 경우
        # Encrypted blob exists but decryption result is None
        github_access_token = "encrypted_blob"
        plaintext_token = None
    monkeypatch.setenv("GITHUB_TOKEN", "fallback_global_pat")
    token = security_scan_service._resolve_token(_U())  # noqa: SLF001
    assert token == "fallback_global_pat"


# ── scan_repo_alerts 처리 본체 봉인 (Theme B S4) ───────────────────────────


@pytest.mark.asyncio
async def test_scan_repo_alerts_counts_and_logs_metadata():
    """code-scanning alert 1건 → counts +1 + upsert_alert_log 가 정규화 metadata 로 호출 (처리 본체 L148-170).

    kwargs 값(alert_type/alert_number/rule_id)까지 단언해 _alert_metadata 정규화 회귀도 봉인 (PR-5C 회피).
    """
    repo = MagicMock(id=7, full_name="owner/test")
    db = MagicMock()
    alert = {"number": 5, "rule": {"id": "py/test", "severity": "error"}}
    with patch.object(security_scan_service, "is_kill_switch_active", return_value=False), \
         patch.object(security_scan_service, "_resolve_token", return_value="tok"), \
         patch.object(security_scan_service, "_fetch_alerts",
                      new=AsyncMock(side_effect=[[alert], []])), \
         patch.object(security_scan_service.security_alert_log_repo, "upsert_alert_log") as mock_upsert:
        counts = await security_scan_service.scan_repo_alerts(db, repo)
    assert counts["code_scanning"] == 1
    assert counts["secret_scanning"] == 0
    assert mock_upsert.call_count == 1
    kw = mock_upsert.call_args.kwargs
    assert kw["repo_id"] == 7
    assert kw["alert_type"] == "code_scanning"
    assert kw["alert_number"] == 5
    assert kw["rule_id"] == "py/test"


@pytest.mark.asyncio
async def test_scan_repo_alerts_rollback_on_db_error():
    """upsert_alert_log 가 SQLAlchemyError 시 counts 미증가 + db.rollback 호출 (L164-169 격리)."""
    from sqlalchemy.exc import SQLAlchemyError
    repo = MagicMock(id=7, full_name="owner/test")
    db = MagicMock()
    alert = {"number": 5, "rule": {"id": "py/test", "severity": "error"}}
    with patch.object(security_scan_service, "is_kill_switch_active", return_value=False), \
         patch.object(security_scan_service, "_resolve_token", return_value="tok"), \
         patch.object(security_scan_service, "_fetch_alerts",
                      new=AsyncMock(side_effect=[[alert], []])), \
         patch.object(security_scan_service.security_alert_log_repo, "upsert_alert_log",
                      side_effect=SQLAlchemyError("boom")):
        counts = await security_scan_service.scan_repo_alerts(db, repo)
    assert counts["code_scanning"] == 0
    db.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_scan_repo_alerts_rollback_does_not_abort_secret_scanning():
    """code-scanning upsert 실패(rollback) 후에도 outer loop 가 secret-scanning 을 계속 처리.

    회귀 가드: except 절(L164-169)에 break/return 이 추가되면 secret-scanning 처리가 통째
    건너뛰어짐 — 기존 rollback 테스트는 secret=[] 라 이 동작을 구분 못 함 (사이클 158 회고 P2).
    Regression guard: a future break/return in the except block would skip secret scanning
    entirely; the prior rollback test used secret=[] so it could not distinguish this.
    """
    from sqlalchemy.exc import SQLAlchemyError
    repo = MagicMock(id=7, full_name="owner/test")
    db = MagicMock()
    code_alert = {"number": 5, "rule": {"id": "py/test", "severity": "error"}}
    secret_alert = {"number": 9, "secret_type": "github_pat"}
    with patch.object(security_scan_service, "is_kill_switch_active", return_value=False), \
         patch.object(security_scan_service, "_resolve_token", return_value="tok"), \
         patch.object(security_scan_service, "_fetch_alerts",
                      new=AsyncMock(side_effect=[[code_alert], [secret_alert]])), \
         patch.object(security_scan_service.security_alert_log_repo, "upsert_alert_log",
                      side_effect=[SQLAlchemyError("boom"), None]):
        counts = await security_scan_service.scan_repo_alerts(db, repo)
    # code-scanning upsert 실패 → counts 미증가 + rollback 1회
    # code-scanning upsert failed → count not incremented + rollback once
    assert counts["code_scanning"] == 0
    db.rollback.assert_called_once()
    # 핵심: rollback 후에도 outer loop 가 secret-scanning 을 계속 처리해 1건 집계
    # Key: after rollback, the outer loop continues to secret-scanning and counts 1
    assert counts["secret_scanning"] == 1
