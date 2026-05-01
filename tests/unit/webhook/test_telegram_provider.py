import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from src.main import app
from src.config_manager.manager import RepoConfigData

client = TestClient(app)

# HMAC-SHA256[:32] token for analysis_id=42, bot_token="123:ABC" — 32자 hex (128-bit)
# Telegram callback_data 64-byte 한도로 인해 32자 절단 유지 (NIST SP 800-107 충족).
# Phase H PR-5C — HMAC msg = `f"gate:{analysis_id}"` (발신측과 동일 — scope 격리)
# Computed: hmac("123:ABC", "gate:42", sha256).hexdigest()[:32]
_TOKEN_42 = "2e3450af594e60ff0c34543790c58342"
APPROVE = {"update_id": 1, "callback_query": {"id": "c1", "from": {"id": 1, "username": "john"},
            "data": f"gate:approve:42:{_TOKEN_42}", "message": {"message_id": 1, "chat": {"id": -1}}}}
REJECT = {"update_id": 2, "callback_query": {"id": "c2", "from": {"id": 1, "username": "john"},
           "data": f"gate:reject:42:{_TOKEN_42}", "message": {"message_id": 1, "chat": {"id": -1}}}}
OTHER = {"update_id": 3, "callback_query": {"id": "c3", "from": {"id": 1, "username": "john"},
          "data": "other:action", "message": {"message_id": 1, "chat": {"id": -1}}}}

def _ctx(db_mock):
    """SessionLocal() 컨텍스트 매니저 mock 헬퍼."""
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_mock)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def test_approve_returns_200():
    with patch("src.webhook.providers.telegram.handle_gate_callback", new_callable=AsyncMock):
        r = client.post("/api/webhook/telegram", json=APPROVE)
    assert r.status_code == 200

def test_reject_returns_200():
    with patch("src.webhook.providers.telegram.handle_gate_callback", new_callable=AsyncMock):
        r = client.post("/api/webhook/telegram", json=REJECT)
    assert r.status_code == 200

def test_non_gate_returns_200():
    r = client.post("/api/webhook/telegram", json=OTHER)
    assert r.status_code == 200

def test_no_callback_query_returns_200():
    r = client.post("/api/webhook/telegram", json={"update_id": 1})
    assert r.status_code == 200

def test_gate_callback_called_with_correct_args():
    with patch("src.webhook.providers.telegram.handle_gate_callback", new_callable=AsyncMock) as mock_h:
        client.post("/api/webhook/telegram", json=APPROVE)
    mock_h.assert_called_once()
    kw = mock_h.call_args.kwargs
    assert kw["analysis_id"] == 42
    assert kw["decision"] == "approve"
    # decided_by 형식: "username(id:user_id)" — user_id(stable integer) 포함
    assert "john" in kw["decided_by"]
    assert "1" in kw["decided_by"]


# --- handle_gate_callback auto_merge 테스트 (Red: handle_gate_callback에 auto_merge 로직이 없음) ---

async def test_handle_gate_callback_approve_with_auto_merge():
    # approve 결정 + auto_merge=True → merge_pr이 호출되고 log_merge_attempt(success=True) 기록
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=85,
                              result={"score": 85})
    mock_repo = MagicMock(id=1, full_name="owner/repo")
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        mock_analysis, mock_repo
    ]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=True, merge_threshold=75)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.providers.telegram.save_gate_decision"):
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.webhook.providers.telegram.merge_pr", new_callable=AsyncMock) as mock_merge:
                        with patch("src.webhook.providers.telegram.log_merge_attempt") as mock_log:
                            mock_merge.return_value = (True, None, "abc123")
                            await handle_gate_callback(analysis_id=42, decision="approve",
                                                       decided_by="john")
                            mock_merge.assert_called_once()
                            mock_log.assert_called_once()
                            _, kw = mock_log.call_args
                            assert kw["success"] is True
                            assert kw["analysis_id"] == 42


async def test_handle_gate_callback_approve_without_auto_merge():
    # approve 결정 + auto_merge=False → merge_pr이 호출되지 않는지 검증
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5)
    mock_repo = MagicMock(id=1, full_name="owner/repo")
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        mock_analysis, mock_repo
    ]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=False)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.providers.telegram.save_gate_decision"):
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.webhook.providers.telegram.merge_pr", new_callable=AsyncMock) as mock_merge:
                        await handle_gate_callback(analysis_id=42, decision="approve",
                                                   decided_by="john")
                        mock_merge.assert_not_called()


async def test_handle_gate_callback_reject_does_not_merge():
    # reject 결정 시 auto_merge=True여도 score가 낮아 merge_pr이 호출되지 않는지 검증
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=0)
    mock_repo = MagicMock(id=1, full_name="owner/repo")
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        mock_analysis, mock_repo
    ]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=True)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.providers.telegram.save_gate_decision"):
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.webhook.providers.telegram.merge_pr", new_callable=AsyncMock) as mock_merge:
                        await handle_gate_callback(analysis_id=42, decision="reject",
                                                   decided_by="john")
                        mock_merge.assert_not_called()


async def test_handle_gate_callback_merge_failure_does_not_propagate():
    # merge_pr 실패(False) 시 log_merge_attempt(success=False) 기록 + 콜백 정상 완료
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=90,
                              result={"score": 90})
    mock_repo = MagicMock(id=1, full_name="owner/repo")
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        mock_analysis, mock_repo
    ]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=True, merge_threshold=75)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.providers.telegram.save_gate_decision") as mock_save:
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.webhook.providers.telegram.merge_pr", new_callable=AsyncMock) as mock_merge:
                        with patch("src.webhook.providers.telegram.log_merge_attempt") as mock_log:
                            mock_merge.return_value = (False, "forbidden: no permission", "abc123")
                            await handle_gate_callback(analysis_id=42, decision="approve",
                                                       decided_by="john")
                            mock_save.assert_called_once()
                            mock_log.assert_called_once()
                            _, kw = mock_log.call_args
                            assert kw["success"] is False
                            assert kw["reason"] == "forbidden: no permission"


# --- 추가 테스트: HMAC 검증 실패·파트 형식 오류·analysis 미존재·내부 예외 ---

INVALID_TOKEN_PAYLOAD = {
    "update_id": 9,
    "callback_query": {
        "id": "c9",
        "from": {"id": 1, "username": "attacker"},
        "data": "gate:approve:42:badtoken1234567",  # 잘못된 HMAC 토큰
        "message": {"message_id": 1, "chat": {"id": -1}}
    }
}

BAD_PARTS_PAYLOAD = {
    "update_id": 10,
    "callback_query": {
        "id": "c10",
        "from": {"id": 1, "username": "user"},
        "data": "gate:approve:only-3-parts",  # 파트 3개 (4개 미만)
        "message": {"message_id": 1, "chat": {"id": -1}}
    }
}


def test_invalid_hmac_token_does_not_call_callback():
    # HMAC 토큰이 잘못된 경우 handle_gate_callback이 호출되지 않아야 한다
    with patch("src.webhook.providers.telegram.handle_gate_callback", new_callable=AsyncMock) as mock_h:
        r = client.post("/api/webhook/telegram", json=INVALID_TOKEN_PAYLOAD)
    assert r.status_code == 200
    mock_h.assert_not_called()


def test_malformed_callback_data_no_crash():
    # 콜백 data가 gate:로 시작하지만 파트 수가 4개 미만이면 200 반환, callback 미호출
    with patch("src.webhook.providers.telegram.handle_gate_callback", new_callable=AsyncMock) as mock_h:
        r = client.post("/api/webhook/telegram", json=BAD_PARTS_PAYLOAD)
    assert r.status_code == 200
    mock_h.assert_not_called()


# --- P1-1: secret_token 헤더 검증 테스트 ---

def test_secret_token_valid_passes():
    """TELEGRAM_WEBHOOK_SECRET 설정 + 올바른 헤더 → 정상 처리."""
    with patch("src.webhook.providers.telegram.settings.telegram_webhook_secret", "mysecret"):
        with patch("src.webhook.providers.telegram.handle_gate_callback", new_callable=AsyncMock):
            r = client.post(
                "/api/webhook/telegram",
                json=APPROVE,
                headers={"X-Telegram-Bot-Api-Secret-Token": "mysecret"},
            )
    assert r.status_code == 200


def test_secret_token_invalid_returns_401():
    """TELEGRAM_WEBHOOK_SECRET 설정 + 잘못된 헤더 → 401 반환, callback 미호출."""
    with patch("src.webhook.providers.telegram.settings.telegram_webhook_secret", "mysecret"):
        with patch("src.webhook.providers.telegram.handle_gate_callback", new_callable=AsyncMock) as mock_h:
            r = client.post(
                "/api/webhook/telegram",
                json=APPROVE,
                headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
            )
    assert r.status_code == 401
    mock_h.assert_not_called()


def test_secret_token_not_configured_skips_check():
    """TELEGRAM_WEBHOOK_SECRET 미설정 → 헤더 없어도 정상 처리."""
    with patch("src.webhook.providers.telegram.settings.telegram_webhook_secret", ""):
        with patch("src.webhook.providers.telegram.handle_gate_callback", new_callable=AsyncMock) as mock_h:
            r = client.post("/api/webhook/telegram", json=APPROVE)
    assert r.status_code == 200
    mock_h.assert_called_once()


async def test_handle_gate_callback_analysis_not_found():
    # analysis DB 조회가 None 반환 시 예외 없이 정상 종료, post_github_review 미호출
    from src.webhook.router import handle_gate_callback
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = None
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock) as mock_review:
            await handle_gate_callback(analysis_id=999, decision="approve", decided_by="user")
            mock_review.assert_not_called()


async def test_handle_gate_callback_exception_does_not_propagate():
    # post_github_review가 예외를 던져도 handle_gate_callback이 정상 종료되어야 한다
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, result={"score": 85})
    mock_repo = MagicMock(id=1, full_name="owner/repo")
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        mock_analysis, mock_repo
    ]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=False)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review",
                   new_callable=AsyncMock, side_effect=httpx.ConnectError("GitHub API down")):
            with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                # 예외가 전파되지 않아야 한다
                # The exception must not propagate.
                await handle_gate_callback(analysis_id=42, decision="approve", decided_by="user")


# --- Phase F.2: log_merge_attempt 관측 테스트 ---

async def test_log_merge_attempt_called_on_auto_merge_success():
    """반자동 merge 성공 시 log_merge_attempt(success=True) 가 호출된다."""
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=7, score=80,
                              result={"score": 80})
    mock_repo = MagicMock(id=1, full_name="org/myrepo")
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        mock_analysis, mock_repo
    ]
    config = RepoConfigData(repo_full_name="org/myrepo", auto_merge=True, merge_threshold=70)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.providers.telegram.save_gate_decision"):
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.webhook.providers.telegram.merge_pr",
                               new_callable=AsyncMock, return_value=(True, None, "abc123")):
                        with patch("src.webhook.providers.telegram.log_merge_attempt") as mock_log:
                            await handle_gate_callback(
                                analysis_id=42, decision="approve", decided_by="alice"
                            )
    mock_log.assert_called_once()
    _, kw = mock_log.call_args
    assert kw["success"] is True
    assert kw["analysis_id"] == 42
    assert kw["repo_name"] == "org/myrepo"
    assert kw["pr_number"] == 7
    assert kw["score"] == 80
    assert kw["threshold"] == 70


async def test_log_merge_attempt_called_on_auto_merge_failure():
    """반자동 merge 실패 시 log_merge_attempt(success=False, reason=...) 가 호출된다."""
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=55, repo_id=2, pr_number=9, score=85,
                              result={"score": 85})
    mock_repo = MagicMock(id=2, full_name="org/protected")
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        mock_analysis, mock_repo
    ]
    config = RepoConfigData(repo_full_name="org/protected", auto_merge=True, merge_threshold=80)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.providers.telegram.save_gate_decision"):
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.webhook.providers.telegram.merge_pr",
                               new_callable=AsyncMock,
                               return_value=(False, "branch_protection_blocked: required status check", "abc123")):
                        with patch("src.webhook.providers.telegram.log_merge_attempt") as mock_log:
                            await handle_gate_callback(
                                analysis_id=55, decision="approve", decided_by="bob"
                            )
    mock_log.assert_called_once()
    _, kw = mock_log.call_args
    assert kw["success"] is False
    assert kw["reason"] == "branch_protection_blocked: required status check"


async def test_log_merge_attempt_exception_does_not_abort_callback():
    """log_merge_attempt 예외 시 WARNING 로그만 남기고 콜백은 정상 완료된다."""
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=77, repo_id=3, pr_number=11, score=90,
                              result={"score": 90})
    mock_repo = MagicMock(id=3, full_name="org/repo3")
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        mock_analysis, mock_repo
    ]
    config = RepoConfigData(repo_full_name="org/repo3", auto_merge=True, merge_threshold=80)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.providers.telegram.save_gate_decision"):
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.webhook.providers.telegram.merge_pr",
                               new_callable=AsyncMock, return_value=(True, None, "abc123")):
                        with patch("src.webhook.providers.telegram.log_merge_attempt",
                                   side_effect=RuntimeError("DB connection lost")):
                            # 예외가 전파되지 않아야 한다 (nested try/except 격리)
                            await handle_gate_callback(
                                analysis_id=77, decision="approve", decided_by="carol"
                            )


# ---------------------------------------------------------------------------
# Phase 10 T6: message.text 처리 + cmd: callback 위임 테스트
# Phase 10 T6: message.text handling + cmd: callback dispatch tests
# ---------------------------------------------------------------------------

def test_message_text_routes_to_commands_handler():
    """message.text가 있으면 handle_message_command가 호출된다.
    message.text payload routes to handle_message_command.
    """
    # 실제 DB 세션을 mock SessionLocal로 대체한다
    # Replace real DB session with mock SessionLocal
    mock_db = MagicMock()
    payload = {
        "message": {
            "text": "/stats owner/repo",
            "from": {"id": 123},
            "chat": {"id": 456},
        }
    }
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch(
            "src.webhook.providers.telegram.handle_message_command",
            return_value="응답 텍스트",
        ) as mock_cmd:
            with patch(
                "src.webhook.providers.telegram.telegram_post_message",
                new_callable=AsyncMock,
            ):
                r = client.post("/api/webhook/telegram", json=payload)
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    # handle_message_command가 sender_id="123", text="/stats owner/repo" 로 호출됐는지 확인
    # handle_message_command must be called with sender_id="123" and correct text
    mock_cmd.assert_called_once()
    _, kw = mock_cmd.call_args
    assert kw["telegram_user_id"] == "123"
    assert kw["text"] == "/stats owner/repo"


def test_callback_query_gate_prefix_unchanged():
    """gate: callback은 기존 gate 처리 로직으로 간다.
    gate: callbacks are handled by the existing gate logic.
    """
    # gate: 콜백은 parse_cmd_callback을 거치지 않고 handle_gate_callback으로 라우팅돼야 한다
    # gate: callbacks must route to handle_gate_callback, not parse_cmd_callback
    with patch("src.webhook.providers.telegram.handle_gate_callback",
               new_callable=AsyncMock) as mock_gate:
        with patch("src.webhook.providers.telegram.parse_cmd_callback") as mock_cmd:
            r = client.post("/api/webhook/telegram", json=APPROVE)
    assert r.status_code == 200
    mock_gate.assert_called_once()
    # parse_cmd_callback은 gate: 접두사 데이터로 호출되지 않아야 한다
    # parse_cmd_callback must NOT be called for gate: prefixed data
    mock_cmd.assert_not_called()


def test_callback_query_cmd_prefix_dispatched():
    """cmd: callback은 parse_cmd_callback으로 위임된다.
    cmd: callbacks are dispatched to parse_cmd_callback.
    """
    # cmd: 접두사 콜백이 들어올 때 parse_cmd_callback이 호출되고 handle_gate_callback은 호출 안됨
    # When cmd: prefixed callback arrives, parse_cmd_callback is called, gate_callback is not
    cmd_payload = {
        "update_id": 99,
        "callback_query": {
            "id": "c99",
            "from": {"id": 7, "username": "testuser"},
            "data": "cmd:stats:42:abc123",
            "message": {"message_id": 1, "chat": {"id": -1}},
        },
    }
    with patch("src.webhook.providers.telegram.parse_cmd_callback",
               return_value=None) as mock_cmd:
        with patch("src.webhook.providers.telegram.handle_gate_callback",
                   new_callable=AsyncMock) as mock_gate:
            r = client.post("/api/webhook/telegram", json=cmd_payload)
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    # parse_cmd_callback이 cmd: 데이터로 호출됐는지 확인
    # parse_cmd_callback must be called with the cmd: data string
    mock_cmd.assert_called_once_with("cmd:stats:42:abc123")
    # gate 콜백은 호출되지 않아야 한다
    # Gate callback must not be triggered
    mock_gate.assert_not_called()


def test_unknown_payload_returns_ok():
    """message도 callback_query도 없으면 {"status": "ok"} 반환.
    Payloads without message or callback_query return {"status": "ok"}.
    """
    # 알 수 없는 형식의 페이로드 — 두 키 모두 없음
    # Unknown payload format — neither key is present
    r = client.post("/api/webhook/telegram", json={"update_id": 1, "unknown_key": "value"})
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Phase H PR-5C — sender ↔ receiver HMAC PARITY 회귀 가드
# 12-에이전트 감사 Critical C10 — 이전에는 발신측 (gate.telegram_gate) 의
# `f"gate:{id}"` 와 수신측의 `str(id)` 가 달라 모든 semi-auto 콜백이 401.
# 본 테스트는 두 토큰이 정확히 동일함을 영구 가드.
# ---------------------------------------------------------------------------


def test_sender_receiver_hmac_token_parity():
    """발신측 _gate_callback_token() 이 만든 토큰을 수신측이 검증 통과해야 한다."""
    from src.gate.telegram_gate import _gate_callback_token  # pylint: disable=import-outside-toplevel
    from src.webhook.providers.telegram import _parse_gate_callback  # pylint: disable=import-outside-toplevel

    bot_token = "123:ABC"  # conftest 환경변수와 일치
    analysis_id = 99
    sender_token = _gate_callback_token(bot_token, analysis_id)

    # 수신측은 settings.telegram_bot_token 사용 — patch 로 주입
    with patch("src.webhook.providers.telegram.settings") as mock_settings:
        mock_settings.telegram_bot_token = bot_token
        callback_data = f"gate:approve:{analysis_id}:{sender_token}"
        parsed = _parse_gate_callback(callback_data)

    assert parsed is not None, (
        "PARITY 위반: 발신측 토큰이 수신측 검증을 통과해야 함 — "
        "HMAC msg 형식이 양쪽 동일해야 한다"
    )
    decision, parsed_id, parsed_token = parsed
    assert decision == "approve"
    assert parsed_id == analysis_id
    assert parsed_token == sender_token


def test_receiver_rejects_legacy_str_id_token():
    """레거시 패턴 (HMAC msg = str(id)) 토큰은 수신 거부 — 보안 가드."""
    import hashlib  # pylint: disable=import-outside-toplevel
    import hmac as _hmac  # pylint: disable=import-outside-toplevel
    bot_token = "123:ABC"
    legacy_token = _hmac.new(
        bot_token.encode(), b"42", digestmod=hashlib.sha256,
    ).hexdigest()[:32]

    with patch("src.webhook.providers.telegram.settings") as mock_settings:
        mock_settings.telegram_bot_token = bot_token
        from src.webhook.providers.telegram import _parse_gate_callback  # pylint: disable=import-outside-toplevel
        parsed = _parse_gate_callback(f"gate:approve:42:{legacy_token}")

    assert parsed is None, "구 패턴 토큰은 거부되어야 함 (Critical C10 가드)"


def test_cmd_scope_token_does_not_validate_as_gate():
    """cmd 도메인 토큰을 gate 콜백에 재사용 시도 → 거부 (cross-replay 차단)."""
    from src.gate.telegram_gate import _make_callback_token  # pylint: disable=import-outside-toplevel
    bot_token = "123:ABC"
    cmd_token = _make_callback_token(bot_token, "cmd", 42)

    with patch("src.webhook.providers.telegram.settings") as mock_settings:
        mock_settings.telegram_bot_token = bot_token
        from src.webhook.providers.telegram import _parse_gate_callback  # pylint: disable=import-outside-toplevel
        parsed = _parse_gate_callback(f"gate:approve:42:{cmd_token}")

    assert parsed is None, "cmd 도메인 토큰을 gate 로 재사용 시도 차단 필요"
