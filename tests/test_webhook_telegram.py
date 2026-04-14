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

# HMAC token for analysis_id=42, bot_token="123:ABC" (32자, SHA-256 앞 32자)
_TOKEN_42 = "d9939856ed07d33d8689614fcb1a7dff"
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
    with patch("src.webhook.router.handle_gate_callback", new_callable=AsyncMock):
        r = client.post("/api/webhook/telegram", json=APPROVE)
    assert r.status_code == 200

def test_reject_returns_200():
    with patch("src.webhook.router.handle_gate_callback", new_callable=AsyncMock):
        r = client.post("/api/webhook/telegram", json=REJECT)
    assert r.status_code == 200

def test_non_gate_returns_200():
    r = client.post("/api/webhook/telegram", json=OTHER)
    assert r.status_code == 200

def test_no_callback_query_returns_200():
    r = client.post("/api/webhook/telegram", json={"update_id": 1})
    assert r.status_code == 200

def test_gate_callback_called_with_correct_args():
    with patch("src.webhook.router.handle_gate_callback", new_callable=AsyncMock) as mock_h:
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
    # approve 결정 + auto_merge=True → merge_pr이 호출되는지 검증
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=85,
                              result={"score": 85})
    mock_repo = MagicMock(id=1, full_name="owner/repo")
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        mock_analysis, mock_repo
    ]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=True, merge_threshold=75)
    with patch("src.webhook.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.router.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.router._save_gate_decision"):
                with patch("src.webhook.router.get_repo_config", return_value=config):
                    with patch("src.webhook.router.merge_pr", new_callable=AsyncMock) as mock_merge:
                        mock_merge.return_value = True
                        await handle_gate_callback(analysis_id=42, decision="approve",
                                                   decided_by="john")
                        mock_merge.assert_called_once()


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
    with patch("src.webhook.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.router.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.router._save_gate_decision"):
                with patch("src.webhook.router.get_repo_config", return_value=config):
                    with patch("src.webhook.router.merge_pr", new_callable=AsyncMock) as mock_merge:
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
    with patch("src.webhook.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.router.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.router._save_gate_decision"):
                with patch("src.webhook.router.get_repo_config", return_value=config):
                    with patch("src.webhook.router.merge_pr", new_callable=AsyncMock) as mock_merge:
                        await handle_gate_callback(analysis_id=42, decision="reject",
                                                   decided_by="john")
                        mock_merge.assert_not_called()


async def test_handle_gate_callback_merge_failure_does_not_propagate():
    # merge_pr가 False를 반환해도 handle_gate_callback이 예외 없이 완료되는지 검증
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=90)
    mock_repo = MagicMock(id=1, full_name="owner/repo")
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        mock_analysis, mock_repo
    ]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=True)
    with patch("src.webhook.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.router.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.router._save_gate_decision") as mock_save:
                with patch("src.webhook.router.get_repo_config", return_value=config):
                    with patch("src.webhook.router.merge_pr", new_callable=AsyncMock) as mock_merge:
                        mock_merge.return_value = False
                        # 예외 없이 완료되어야 함
                        await handle_gate_callback(analysis_id=42, decision="approve",
                                                   decided_by="john")
                        # GateDecision은 merge 결과와 무관하게 저장되어야 함
                        mock_save.assert_called_once()


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
    with patch("src.webhook.router.handle_gate_callback", new_callable=AsyncMock) as mock_h:
        r = client.post("/api/webhook/telegram", json=INVALID_TOKEN_PAYLOAD)
    assert r.status_code == 200
    mock_h.assert_not_called()


def test_malformed_callback_data_no_crash():
    # 콜백 data가 gate:로 시작하지만 파트 수가 4개 미만이면 200 반환, callback 미호출
    with patch("src.webhook.router.handle_gate_callback", new_callable=AsyncMock) as mock_h:
        r = client.post("/api/webhook/telegram", json=BAD_PARTS_PAYLOAD)
    assert r.status_code == 200
    mock_h.assert_not_called()


# --- P1-1: secret_token 헤더 검증 테스트 ---

def test_secret_token_valid_passes():
    """TELEGRAM_WEBHOOK_SECRET 설정 + 올바른 헤더 → 정상 처리."""
    with patch("src.webhook.router.settings.telegram_webhook_secret", "mysecret"):
        with patch("src.webhook.router.handle_gate_callback", new_callable=AsyncMock):
            r = client.post(
                "/api/webhook/telegram",
                json=APPROVE,
                headers={"X-Telegram-Bot-Api-Secret-Token": "mysecret"},
            )
    assert r.status_code == 200


def test_secret_token_invalid_skips_callback():
    """TELEGRAM_WEBHOOK_SECRET 설정 + 잘못된 헤더 → callback 미호출."""
    with patch("src.webhook.router.settings.telegram_webhook_secret", "mysecret"):
        with patch("src.webhook.router.handle_gate_callback", new_callable=AsyncMock) as mock_h:
            r = client.post(
                "/api/webhook/telegram",
                json=APPROVE,
                headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
            )
    assert r.status_code == 200
    mock_h.assert_not_called()


def test_secret_token_not_configured_skips_check():
    """TELEGRAM_WEBHOOK_SECRET 미설정 → 헤더 없어도 정상 처리."""
    with patch("src.webhook.router.settings.telegram_webhook_secret", ""):
        with patch("src.webhook.router.handle_gate_callback", new_callable=AsyncMock) as mock_h:
            r = client.post("/api/webhook/telegram", json=APPROVE)
    assert r.status_code == 200
    mock_h.assert_called_once()


async def test_handle_gate_callback_analysis_not_found():
    # analysis DB 조회가 None 반환 시 예외 없이 정상 종료, post_github_review 미호출
    from src.webhook.router import handle_gate_callback
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = None
    with patch("src.webhook.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.router.post_github_review", new_callable=AsyncMock) as mock_review:
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
    with patch("src.webhook.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.router.post_github_review",
                   new_callable=AsyncMock, side_effect=httpx.ConnectError("GitHub API down")):
            with patch("src.webhook.router.get_repo_config", return_value=config):
                # 예외가 전파되지 않아야 한다
                await handle_gate_callback(analysis_id=42, decision="approve", decided_by="user")
