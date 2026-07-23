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
    def __init__(self, status_code: int, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or []
        self.headers = headers or {}
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
async def test_fetch_alerts_403_rate_limit_logs_warning_not_ghas_skip(caplog):
    """🔴 403 rate-limit(X-RateLimit-Remaining=0)은 GHAS 비활성 silent skip 이 아니라 WARNING (종합감사 P2).
    스캔 미수행을 '0 alerts' 로 오인하지 않게 표면화한다.
    """
    import logging as _logging
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=_FakeResp(403, headers={"X-RateLimit-Remaining": "0"}))
    with patch("src.services.security_scan_service.get_http_client", return_value=fake_client):
        with caplog.at_level(_logging.WARNING, logger="src.services.security_scan_service"):
            result = await security_scan_service._fetch_alerts(  # noqa: SLF001
                "tok", "owner/test", "code-scanning",
            )
    assert result is None
    logged = "\n".join(r.message for r in caplog.records)
    assert "rate-limit" in logged.lower(), f"rate-limit 경고 미표면화: {logged!r}"
    assert "비활성" not in logged, "rate-limit 을 GHAS 비활성으로 오분류"


@pytest.mark.asyncio
async def test_fetch_alerts_403_without_ratelimit_is_ghas_skip(caplog):
    """403 (rate-limit 신호 없음) = GHAS 비활성 info skip (WARNING 아님)."""
    import logging as _logging
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=_FakeResp(403))  # no rate-limit headers
    with patch("src.services.security_scan_service.get_http_client", return_value=fake_client):
        with caplog.at_level(_logging.WARNING, logger="src.services.security_scan_service"):
            result = await security_scan_service._fetch_alerts(  # noqa: SLF001
                "tok", "owner/test", "code-scanning",
            )
    assert result is None
    # WARNING 레벨엔 rate-limit 경고 없어야(=info skip)
    assert not any("rate-limit" in r.message.lower() for r in caplog.records)


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


@pytest.mark.asyncio
async def test_scan_all_repos_resolves_owner_token(monkeypatch):
    """🔴 P1-4 (Grok REAL): scan_all_repos 가 repo 소유자를 resolve 해 scan_repo_alerts(user=owner)
    로 전달 — 소유자 private 리포가 전역 토큰만으로 403 silent skip 되지 않도록(정책 14).

    값 단언: mock 호출 사실이 아니라 실제 전달된 user 가 resolve 된 owner.
    """
    monkeypatch.delenv("SECURITY_AUTO_PROCESS_DISABLED", raising=False)
    fake_db = MagicMock()
    owner = MagicMock(id=5)
    repo = MagicMock(full_name="owner/private", id=1, user_id=5)
    fake_db.query.return_value.all.return_value = [repo]
    with patch.object(security_scan_service.user_repo, "find_by_id", return_value=owner) as mock_find, \
         patch.object(
             security_scan_service, "scan_repo_alerts",
             new=AsyncMock(return_value={"code_scanning": 0, "secret_scanning": 0, "skipped": 0}),
         ) as mock_scan:
        await security_scan_service.scan_all_repos(fake_db)
    mock_find.assert_called_once_with(fake_db, 5)
    assert mock_scan.await_args.kwargs["user"] is owner


@pytest.mark.asyncio
async def test_scan_all_repos_null_owner_passes_user_none(monkeypatch):
    """소유자 없는(user_id=None) legacy 리포는 owner resolve 없이 user=None (전역 토큰 fallback)."""
    monkeypatch.delenv("SECURITY_AUTO_PROCESS_DISABLED", raising=False)
    fake_db = MagicMock()
    repo = MagicMock(full_name="legacy/repo", id=1, user_id=None)
    fake_db.query.return_value.all.return_value = [repo]
    with patch.object(security_scan_service.user_repo, "find_by_id") as mock_find, \
         patch.object(
             security_scan_service, "scan_repo_alerts",
             new=AsyncMock(return_value={"code_scanning": 0, "secret_scanning": 0, "skipped": 0}),
         ) as mock_scan:
        await security_scan_service.scan_all_repos(fake_db)
    mock_find.assert_not_called()
    assert mock_scan.await_args.kwargs["user"] is None


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


@pytest.mark.asyncio
async def test_scan_repo_alerts_fetches_kinds_concurrently():
    """code/secret scanning 2종 fetch 가 asyncio.gather 로 병렬 실행됨을 검증.
    Verifies code/secret scanning fetches run concurrently via asyncio.gather.

    회귀 가드: 직렬 await 로 되돌리면 max 동시성이 1 로 떨어져 실패.
    Regression guard: reverting to serial awaits drops max concurrency to 1 and fails.
    """
    import asyncio
    repo = MagicMock(id=7, full_name="owner/test")
    db = MagicMock()
    concurrency = {"cur": 0, "max": 0}

    async def fake_fetch(_token, _full_name, _kind):
        concurrency["cur"] += 1
        concurrency["max"] = max(concurrency["max"], concurrency["cur"])
        await asyncio.sleep(0.02)  # 다른 코루틴이 동시 진입할 윈도우 / window for concurrent entry
        concurrency["cur"] -= 1
        return []

    with patch.object(security_scan_service, "is_kill_switch_active", return_value=False), \
         patch.object(security_scan_service, "_resolve_token", return_value="tok"), \
         patch.object(security_scan_service, "_fetch_alerts", new=fake_fetch):
        await security_scan_service.scan_repo_alerts(db, repo)

    # gather 병렬이면 두 fetch 가 동시에 진입 → max 동시성 2
    # With gather, both fetches enter concurrently → max concurrency 2
    assert concurrency["max"] == 2
