import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-tg-webhook-secret-for-tests!")

import contextlib
import logging

import pytest
import httpx
from fastapi import BackgroundTasks
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


# S1 fix: route 테스트는 TELEGRAM_WEBHOOK_SECRET 헤더를 포함해야 한다 (fail-closed 정책)
# S1 fix: route tests must supply X-Telegram-Bot-Api-Secret-Token header (fail-closed policy)
_TG_SECRET = "test-tg-webhook-secret-for-tests!"
_TG_HEADERS = {"X-Telegram-Bot-Api-Secret-Token": _TG_SECRET}


@pytest.fixture(autouse=True)
def _patch_tg_secret(monkeypatch):
    """모든 route 테스트에서 telegram settings.telegram_webhook_secret을 테스트 값으로 교체."""
    import src.webhook.providers.telegram as _tg  # pylint: disable=import-outside-toplevel
    monkeypatch.setattr(_tg.settings, "telegram_webhook_secret", _TG_SECRET)


@pytest.fixture(autouse=True)
def _authorize_gate_owner():
    """기본적으로 콜백 클릭 사용자를 repo 소유자(user_id=1)로 인가 (사이클 164 P1 #1 authz).

    handle_gate_callback 의 소유권 검증을 통과시키기 위해 user_repo.find_by_telegram_user_id 가
    id=1 사용자를 반환하도록 patch. 테스트는 mock_repo.user_id=1 + telegram_user_id 전달로 인가.
    비인가 케이스는 개별 테스트에서 이 patch 를 덮어쓴다.
    """
    with patch("src.webhook.providers.telegram.user_repo.find_by_telegram_user_id",
               return_value=MagicMock(id=1)):
        yield


@pytest.fixture(autouse=True)
def _gate_decision_claim_succeeds():
    """기본적으로 게이트 결정 claim 이 성공(first-writer)하도록 패치 (#11 리플레이 가드).

    handle_gate_callback 의 원자적 claim(gate_decision_repo.claim_decision)을 True 로 패치해
    기존 테스트의 최초-결정 정상 경로를 보존한다. 리플레이/동시패자 케이스는 개별 테스트가 False 로 덮어쓴다.
    Patch claim_decision → True by default so the first decision proceeds; replay/concurrent-loser
    cases override this (return False) in individual tests.
    """
    with patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision",
               return_value=True):
        yield


def test_approve_returns_200():
    with patch("src.webhook.providers.telegram.handle_gate_callback", new_callable=AsyncMock):
        r = client.post("/api/webhook/telegram", json=APPROVE, headers=_TG_HEADERS)
    assert r.status_code == 200

def test_reject_returns_200():
    with patch("src.webhook.providers.telegram.handle_gate_callback", new_callable=AsyncMock):
        r = client.post("/api/webhook/telegram", json=REJECT, headers=_TG_HEADERS)
    assert r.status_code == 200

def test_non_gate_returns_200():
    r = client.post("/api/webhook/telegram", json=OTHER, headers=_TG_HEADERS)
    assert r.status_code == 200

def test_no_callback_query_returns_200():
    r = client.post("/api/webhook/telegram", json={"update_id": 1}, headers=_TG_HEADERS)
    assert r.status_code == 200

def test_gate_callback_called_with_correct_args():
    with patch("src.webhook.providers.telegram.handle_gate_callback", new_callable=AsyncMock) as mock_h:
        client.post("/api/webhook/telegram", json=APPROVE, headers=_TG_HEADERS)
    mock_h.assert_called_once()
    kw = mock_h.call_args.kwargs
    assert kw["analysis_id"] == 42
    assert kw["decision"] == "approve"
    # decided_by 형식: "username(id:user_id)" — user_id(stable integer) 포함
    assert "john" in kw["decided_by"]
    assert "1" in kw["decided_by"]


def test_missing_secret_returns_401():
    """S1: TELEGRAM_WEBHOOK_SECRET 미설정(빈 값) 시 모든 요청이 401을 반환해야 한다.
    S1: Fail-closed — all requests rejected when TELEGRAM_WEBHOOK_SECRET is empty.
    """
    import src.webhook.providers.telegram as _tg  # pylint: disable=import-outside-toplevel
    original = _tg.settings.telegram_webhook_secret
    try:
        _tg.settings.telegram_webhook_secret = ""
        r = client.post("/api/webhook/telegram", json=APPROVE)
    finally:
        _tg.settings.telegram_webhook_secret = original
    assert r.status_code == 401


# --- #13 webhook 본문 파싱 robustness (secret 통과 후 비정형/비-dict 본문 → 500 아닌 400) ---

def test_telegram_webhook_malformed_body_returns_400():
    """#13: secret 통과 후 비정형 JSON 본문은 500 이 아니라 400 을 반환 (railway 대칭)."""
    r = client.post(
        "/api/webhook/telegram",
        content="{bad json",
        headers={**_TG_HEADERS, "Content-Type": "application/json"},
    )
    assert r.status_code == 400


def test_telegram_webhook_json_array_body_returns_400():
    """#13: 유효 JSON 이지만 비-dict(array) 본문은 payload.get 전 400 차단."""
    r = client.post("/api/webhook/telegram", json=[1, 2, 3], headers=_TG_HEADERS)
    assert r.status_code == 400


def test_telegram_webhook_json_scalar_body_returns_400():
    """#13: JSON scalar(str) 본문도 .get 부재 → isinstance 가드로 400."""
    r = client.post("/api/webhook/telegram", json="hello", headers=_TG_HEADERS)
    assert r.status_code == 400


def test_telegram_webhook_valid_dict_body_still_200():
    """#13 회귀 가드: 정상 dict 본문은 기존대로 200 유지."""
    r = client.post("/api/webhook/telegram", json={"update_id": 99}, headers=_TG_HEADERS)
    assert r.status_code == 200


# --- handle_gate_callback auto_merge 위임 테스트 (Q1 A: engine._run_auto_merge 로 자동/반자동 완전 대칭) ---

async def test_handle_gate_callback_approve_with_auto_merge():
    # approve + auto_merge=True + score>=threshold → engine._run_auto_merge 에 위임
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=85, result={"score": 85})
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [mock_analysis, mock_repo]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=True, merge_threshold=75)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision") as mock_save:
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.gate.engine._run_auto_merge", new_callable=AsyncMock) as mock_am:
                        await handle_gate_callback(analysis_id=42, decision="approve", decided_by="john", telegram_user_id="1")
                        mock_save.assert_called_once()
                        mock_am.assert_called_once()
                        args, kw = mock_am.call_args
                        # 자동 경로와 동일 시그니처: (config, github_token, repo_name, pr_number, score)
                        assert args[0] is config
                        assert args[2] == "owner/repo"
                        assert args[3] == 5
                        assert args[4] == 85
                        assert kw["analysis_id"] == 42


async def test_handle_gate_callback_skips_auto_merge_when_ai_review_truncated():
    """🔴 C22: 반자동 승인이어도 ai_review_truncated=True 면 engine._run_auto_merge 미위임.
    절단된 일부만 본 인플레 점수의 자동 머지 방지 — AutoMergeAction 가드 미러링(parity).
    """
    from src.webhook.router import handle_gate_callback
    # 90 >= threshold(75) 이나 diff 절단 마커 존재
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=90,
                              result={"score": 90, "ai_review_truncated": True})
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [mock_analysis, mock_repo]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=True, merge_threshold=75)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision"):
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.gate.engine._run_auto_merge", new_callable=AsyncMock) as mock_am:
                        await handle_gate_callback(analysis_id=42, decision="approve",
                                                   decided_by="john", telegram_user_id="1")
                        mock_am.assert_not_called()  # 절단 → 자동 머지 위임 차단


# --- P1-1 반자동 parity 핵심 테스트 (검증자 단일출처화 → result 전파) ---
# Semi-auto verifier parity: handle_gate_callback 의 반자동 auto-merge 가 engine._run_auto_merge
# 에 위임할 때 result=result_dict 를 함께 전달해야 한다 — engine 진입부의 단일출처 검증 가드
# (verifier_blocks_merge) 가 실제 diff/리뷰 요약을 판정하려면 result dict 가 필요하기 때문.
# result 누락 시 가드가 빈 dict 로 검증 → 반자동 경로만 검증 품질 저하 = parity 갭 회귀.

async def test_handle_gate_callback_passes_result_dict_to_engine():
    """반자동 auto-merge 위임 시 result=result_dict(analysis.result) 를 engine 에 전달한다 (P1-1 parity)."""
    from src.webhook.router import handle_gate_callback
    analysis_result = {"score": 85, "grade": "B", "ai_summary": "semi-auto-marker", "issues": []}
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=85, result=analysis_result)
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [mock_analysis, mock_repo]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=True, merge_threshold=75)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision"):
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.gate.engine._run_auto_merge", new_callable=AsyncMock) as mock_am:
                        await handle_gate_callback(analysis_id=42, decision="approve",
                                                   decided_by="john", telegram_user_id="1")
                        mock_am.assert_called_once()
                        kw = mock_am.call_args.kwargs
                        # 🔴 P1-1: result 가 keyword 인자로 전달되고 analysis.result 와 동일해야 한다.
                        # The verifier guard inside engine needs the real result to judge merge safety.
                        assert "result" in kw, "반자동 경로가 result 를 engine 에 전달하지 않음 (parity 갭)"
                        assert kw["result"] == analysis_result


# --- 🔴 analyzed SHA 결속 (반자동 경로) — 레이스 없이 재현되는 최우선 회귀 가드 ---
# handle_gate_callback 은 analysis 행을 이미 로드해 commit_sha 를 쥐고 있으면서도 이를 버리고,
# engine 이 그 시점의 PR head 를 새로 조회해 머지한다. 승인 버튼 HMAC 은 만료가 없으므로
# 사용자가 몇 시간 뒤(그 사이 여러 커밋 push 후) 버튼을 누르면 **분석된 적 없는 head** 가
# 분석 당시 점수로 머지된다 — 자동 경로와 달리 동시성 레이스조차 필요 없다.
# Semi-auto analyzed-SHA binding — the highest-value guard: it reproduces without any race.
# handle_gate_callback already loads the analysis row (holding commit_sha) and discards it, letting
# the engine re-query the PR head at merge time. The approval button's HMAC never expires, so
# clicking hours later (after further pushes) merges never-analyzed code under the old score.

async def test_handle_gate_callback_passes_analyzed_sha_to_engine():
    """반자동 승인이 engine._run_auto_merge 에 analyzed_sha=analysis.commit_sha 를 전달한다.

    값 단언 — 실제 전달된 SHA 가 분석된 커밋의 SHA 와 동일해야 한다 (호출 사실 단언 아님).
    Value assertion — the SHA actually forwarded must equal the analyzed commit's SHA.
    """
    from src.webhook.router import handle_gate_callback
    analyzed_sha = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=85,
                              commit_sha=analyzed_sha, result={"score": 85})
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [mock_analysis, mock_repo]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=True, merge_threshold=75)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision"):
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.gate.engine._run_auto_merge", new_callable=AsyncMock) as mock_am:
                        await handle_gate_callback(analysis_id=42, decision="approve",
                                                   decided_by="john", telegram_user_id="1")
                        mock_am.assert_awaited_once()
                        kw = mock_am.call_args.kwargs
                        # 🔴 analysis.commit_sha 를 버리면 engine 이 그 시점 head 를 머지한다.
                        # Dropping analysis.commit_sha lets the engine merge whatever head is current.
                        assert "analyzed_sha" in kw, \
                            "반자동 경로가 analyzed_sha 를 engine 에 전달하지 않음 — 미분석 커밋 머지 위험"
                        assert kw["analyzed_sha"] == analyzed_sha


# --- #11 리플레이 가드 테스트 (원자적 claim 패자 = 부수효과 skip) ---

async def test_handle_gate_callback_replay_claim_lost_skips_side_effects():
    """#11: claim_decision 이 False(이미 결정됨 또는 동시 리플레이 패자)면 부수효과 전부 skip.

    동일 서명 버튼 재클릭·더블클릭·Telegram 재전송으로 GitHub 리뷰 재게시·결정 뒤집기·
    auto-merge 재실행이 일어나지 않아야 한다 — first-writer-wins (원자적 claim).
    """
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=85, result={"score": 85})
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [mock_analysis, mock_repo]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=True, merge_threshold=75)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision",
                   return_value=False) as mock_claim:  # 동시/순차 리플레이 패자
            with patch("src.webhook.providers.telegram.post_github_review",
                       new_callable=AsyncMock) as mock_review:
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.gate.engine._run_auto_merge",
                               new_callable=AsyncMock) as mock_am:
                        await handle_gate_callback(analysis_id=42, decision="approve",
                                                   decided_by="john", telegram_user_id="1")
    mock_claim.assert_called_once()      # 가드가 실제로 claim 을 시도했는가
    mock_review.assert_not_called()      # GitHub 리뷰 미게시
    mock_am.assert_not_called()          # auto-merge 미재실행


async def test_handle_gate_callback_first_decision_applies():
    """#11 정상 경로 회귀 가드: claim 성공(first-writer) → 최초 결정은 정상 적용."""
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=85, result={"score": 85})
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [mock_analysis, mock_repo]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=True, merge_threshold=75)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision",
                   return_value=True) as mock_claim:
            with patch("src.webhook.providers.telegram.post_github_review",
                       new_callable=AsyncMock) as mock_review:
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.gate.engine._run_auto_merge",
                               new_callable=AsyncMock) as mock_am:
                        await handle_gate_callback(analysis_id=42, decision="approve",
                                                   decided_by="john", telegram_user_id="1")
    mock_claim.assert_called_once()      # 결정 claim (원자적 기록)
    mock_review.assert_called_once()     # 최초 결정 — GitHub 리뷰 게시
    mock_am.assert_called_once()         # auto-merge 위임


async def test_handle_gate_callback_approve_without_auto_merge():
    # auto_merge=False → _run_auto_merge 미호출
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=85, result={"score": 85})
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [mock_analysis, mock_repo]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=False)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision") as mock_save:
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.gate.engine._run_auto_merge", new_callable=AsyncMock) as mock_am:
                        await handle_gate_callback(analysis_id=42, decision="approve", decided_by="john", telegram_user_id="1")
                        mock_save.assert_called_once()
                        mock_am.assert_not_called()


async def test_handle_gate_callback_reject_does_not_merge():
    # reject 시 auto_merge=True + 높은 score(>=threshold) 여도 머지 금지 (decision 가드 — 잠재 버그 차단)
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=90, result={"score": 90})
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [mock_analysis, mock_repo]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=True, merge_threshold=75)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision") as mock_save:
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.gate.engine._run_auto_merge", new_callable=AsyncMock) as mock_am:
                        await handle_gate_callback(analysis_id=42, decision="reject", decided_by="john", telegram_user_id="1")
                        mock_save.assert_called_once()
                        mock_am.assert_not_called()


async def test_handle_gate_callback_incomplete_static_skips_merge():
    # approve + auto_merge=True 여도 정적분석 불완전 마커 시 머지 차단 (자동 AutoMergeAction 대칭, #779/#783)
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=85,
                              result={"score": 85, "static_analysis_incomplete": True})
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [mock_analysis, mock_repo]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=True, merge_threshold=75)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision"):
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.gate.engine._run_auto_merge", new_callable=AsyncMock) as mock_am:
                        await handle_gate_callback(analysis_id=42, decision="approve", decided_by="john", telegram_user_id="1")
                        mock_am.assert_not_called()


async def test_handle_gate_callback_ai_review_failed_skips_merge():
    # approve + auto_merge=True 여도 AI 리뷰 실제 실패(api_error) 시 머지 차단 (자동 AutoMergeAction 대칭, #8)
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=85,
                              result={"score": 85, "ai_review_status": "api_error"})
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [mock_analysis, mock_repo]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=True, merge_threshold=75)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision"):
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.gate.engine._run_auto_merge", new_callable=AsyncMock) as mock_am:
                        await handle_gate_callback(analysis_id=42, decision="approve", decided_by="john", telegram_user_id="1")
                        mock_am.assert_not_called()


async def test_handle_gate_callback_ai_no_api_key_still_merges():
    # AI 의도적 미수행(no_api_key)은 실패가 아니므로 반자동 머지 보존 (회귀 가드, #8)
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=85,
                              result={"score": 85, "ai_review_status": "no_api_key"})
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [mock_analysis, mock_repo]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=True, merge_threshold=75)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision"):
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.gate.engine._run_auto_merge", new_callable=AsyncMock) as mock_am:
                        await handle_gate_callback(analysis_id=42, decision="approve", decided_by="john", telegram_user_id="1")
                        mock_am.assert_called_once()


async def test_handle_gate_callback_merge_error_does_not_propagate():
    # _run_auto_merge 가 RuntimeError 누출 시에도 콜백이 격리되어 정상 완료 (except RuntimeError 보강)
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=90, result={"score": 90})
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [mock_analysis, mock_repo]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=True, merge_threshold=75)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision"):
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.gate.engine._run_auto_merge", new_callable=AsyncMock,
                               side_effect=RuntimeError("merge boom")):
                        # 예외가 전파되지 않아야 한다 (handle_gate_callback except 격리)
                        await handle_gate_callback(analysis_id=42, decision="approve", decided_by="john", telegram_user_id="1")


async def test_handle_gate_callback_below_threshold_still_delegates_to_engine():
    """score < merge_threshold 여도 telegram 은 _run_auto_merge 에 위임한다 (사이클 164 회고 P1 — layer 격리 봉인).

    임계 가드(score>=merge_threshold)는 engine._run_auto_merge 단일 layer(engine.py:109)가 담당하고
    telegram 위임은 무조건(approve+auto_merge+not incomplete)이다. telegram 이 임계를 잘못 추가하면
    이 테스트가 회귀를 잡는다 — 실제 머지 차단은 engine layer 테스트(tests/unit/gate/)가 봉인.
    """
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=85, result={"score": 85})
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [mock_analysis, mock_repo]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=True, merge_threshold=90)  # 85 < 90
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock):
            with patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision"):
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.gate.engine._run_auto_merge", new_callable=AsyncMock) as mock_am:
                        await handle_gate_callback(analysis_id=42, decision="approve", decided_by="john", telegram_user_id="1")
                        mock_am.assert_called_once()
                        # score 가 임계 미달이어도 그대로 engine 에 전달 — engine 이 차단 결정
                        assert mock_am.call_args.args[4] == 85


# --- handle_gate_callback authorization 테스트 (사이클 164 P1 #1 — 콜백 소유권 검증) ---

async def test_handle_gate_callback_unauthorized_non_owner_skips():
    """콜백 클릭 사용자가 repo 소유자가 아니면(user.id != repo.user_id) gate 액션 전부 미실행."""
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=85, result={"score": 85})
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)  # 소유자 user_id=1
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [mock_analysis, mock_repo]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=True, merge_threshold=75)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock) as mock_review:
            with patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision") as mock_save:
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.webhook.providers.telegram.user_repo.find_by_telegram_user_id",
                               return_value=MagicMock(id=999)):  # 비소유자(id != 1)
                        with patch("src.gate.engine._run_auto_merge", new_callable=AsyncMock) as mock_am:
                            await handle_gate_callback(analysis_id=42, decision="approve",
                                                       decided_by="attacker", telegram_user_id="999")
                            mock_review.assert_not_called()
                            mock_save.assert_not_called()
                            mock_am.assert_not_called()


async def test_handle_gate_callback_unlinked_user_skips():
    """미연동(find_by_telegram_user_id None) 또는 telegram_user_id 부재 시 gate 액션 미실행."""
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=85, result={"score": 85})
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [mock_analysis, mock_repo]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=True, merge_threshold=75)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock) as mock_review:
            with patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision") as mock_save:
                with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                    with patch("src.webhook.providers.telegram.user_repo.find_by_telegram_user_id",
                               return_value=None):  # 미연동
                        await handle_gate_callback(analysis_id=42, decision="approve",
                                                   decided_by="ghost", telegram_user_id="555")
                        mock_review.assert_not_called()
                        mock_save.assert_not_called()


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
        r = client.post("/api/webhook/telegram", json=INVALID_TOKEN_PAYLOAD, headers=_TG_HEADERS)
    assert r.status_code == 200
    mock_h.assert_not_called()


def test_malformed_callback_data_no_crash():
    # 콜백 data가 gate:로 시작하지만 파트 수가 4개 미만이면 200 반환, callback 미호출
    with patch("src.webhook.providers.telegram.handle_gate_callback", new_callable=AsyncMock) as mock_h:
        r = client.post("/api/webhook/telegram", json=BAD_PARTS_PAYLOAD, headers=_TG_HEADERS)
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


def test_secret_token_not_configured_returns_401():
    """S1: TELEGRAM_WEBHOOK_SECRET 미설정 → fail-closed, 401 반환 (인증 우회 차단).
    S1: Empty secret must return 401 — fail-closed policy prevents unauthenticated access.
    """
    with patch("src.webhook.providers.telegram.settings.telegram_webhook_secret", ""):
        with patch("src.webhook.providers.telegram.handle_gate_callback", new_callable=AsyncMock) as mock_h:
            r = client.post("/api/webhook/telegram", json=APPROVE)
    assert r.status_code == 401
    mock_h.assert_not_called()


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
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        mock_analysis, mock_repo
    ]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=False)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review",
                   new_callable=AsyncMock, side_effect=httpx.ConnectError("GitHub API down")):
            with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                # 예외가 전파되지 않아야 한다 (authz 통과 후 post_github_review 예외 경로 검증)
                # The exception must not propagate (authorized → reaches post_github_review).
                await handle_gate_callback(
                    analysis_id=42, decision="approve", decided_by="user", telegram_user_id="1",
                )


# --- Phase F.2 관측 테스트 — Q1 A 이후 engine._run_auto_merge 로 이관됨 ---
# 반자동 merge 시도의 log_merge_attempt 관측은 이제 engine._run_auto_merge 내부에서
# 수행된다(자동/반자동 단일 출처). 해당 동작은 tests/unit/gate/ 의 engine 테스트가 커버하고,
# 위 위임 테스트(test_handle_gate_callback_*)가 telegram → engine 위임을 검증한다.
# The semi-auto merge_attempt observation now lives in engine._run_auto_merge (single source);
# engine tests cover it, and the delegation tests above verify telegram hands off to engine.


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
                r = client.post("/api/webhook/telegram", json=payload, headers=_TG_HEADERS)
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
            r = client.post("/api/webhook/telegram", json=APPROVE, headers=_TG_HEADERS)
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
            r = client.post("/api/webhook/telegram", json=cmd_payload, headers=_TG_HEADERS)
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
    r = client.post("/api/webhook/telegram", json={"update_id": 1, "unknown_key": "value"},
                    headers=_TG_HEADERS)
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
    import src.webhook.providers.telegram as _tg  # pylint: disable=import-outside-toplevel

    bot_token = "123:ABC"  # conftest 환경변수와 일치
    analysis_id = 99
    sender_token = _gate_callback_token(bot_token, analysis_id)

    # 수신측은 settings.telegram_bot_token 사용 — patch 로 주입
    with patch("src.webhook.providers.telegram.settings") as mock_settings:
        mock_settings.telegram_bot_token = bot_token
        callback_data = f"gate:approve:{analysis_id}:{sender_token}"
        parsed = _tg._parse_gate_callback(callback_data)

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
        import src.webhook.providers.telegram as _tg  # pylint: disable=import-outside-toplevel
        parsed = _tg._parse_gate_callback(f"gate:approve:42:{legacy_token}")

    assert parsed is None, "구 패턴 토큰은 거부되어야 함 (Critical C10 가드)"


def test_cmd_scope_token_does_not_validate_as_gate():
    """cmd 도메인 토큰을 gate 콜백에 재사용 시도 → 거부 (cross-replay 차단)."""
    from src.gate.telegram_gate import _make_callback_token  # pylint: disable=import-outside-toplevel
    bot_token = "123:ABC"
    cmd_token = _make_callback_token(bot_token, "cmd", 42)

    with patch("src.webhook.providers.telegram.settings") as mock_settings:
        mock_settings.telegram_bot_token = bot_token
        import src.webhook.providers.telegram as _tg  # pylint: disable=import-outside-toplevel
        parsed = _tg._parse_gate_callback(f"gate:approve:42:{cmd_token}")

    assert parsed is None, "cmd 도메인 토큰을 gate 로 재사용 시도 차단 필요"


# --- handle_gate_callback pr_number=None 가드 (B1) ---

async def test_handle_gate_callback_skips_when_pr_number_is_none():
    """pr_number=None인 Analysis(push 이벤트)가 연결된 경우 gate action을 건너뛰어야 한다.
    Gate action must be skipped when the linked Analysis has pr_number=None (push event).
    """
    from src.webhook.router import handle_gate_callback  # pylint: disable=import-outside-toplevel
    # push Analysis — pr_number 없음
    mock_analysis = MagicMock(id=55, repo_id=1, pr_number=None, result={"score": 80})
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        mock_analysis, mock_repo
    ]
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.post_github_review",
                   new_callable=AsyncMock) as mock_review:
            with patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision") as mock_save:
                await handle_gate_callback(analysis_id=55, decision="approve", decided_by="john", telegram_user_id="1")
    # pr_number=None → post_github_review·gate_decision_repo.claim_decision 모두 호출되지 않아야 한다
    mock_review.assert_not_called()
    mock_save.assert_not_called()


# ---------------------------------------------------------------------------
# 무가드 백그라운드 태스크 → uvicorn 토큰 트레이스백 (2026-07-19 P0 후속)
#
# 🔴 사고 경로: `_handle_message` 는 `background_tasks.add_task(telegram_post_message, ...)`
# 를 **아무 가드 없이** 등록한다. Telegram API 가 401/400/5xx 를 돌려주면 httpx 예외가
# 백그라운드 태스크 → ASGI 밖으로 탈출하고, uvicorn 이 `Exception in ASGI application` 을
# exc_info 와 함께 로깅한다. httpx 예외 메시지에는 요청 URL 이 통째로 박혀 있으므로
# (`... for url 'https://api.telegram.org/bot<토큰>/sendMessage'`) **봇 토큰이 운영 로그에
# 평문으로 남는다**. uvicorn 로거는 propagate=False 라 앱의 root 리댁션 필터도 지나치지 않는다.
# An unguarded background task lets httpx's exception escape to uvicorn, which logs it with
# exc_info — and the httpx message embeds the full token URL.
#
# 🔴 형제 호출처는 전부 가드돼 있다 — `gate/actions/approve.py` · `services/cron_service.py` ·
# `services/merge_retry_service.py` 가 모두 `except httpx.HTTPError` 로 감싼다. 이 한 곳만
# 비대칭으로 빠져 있었다(only-one-side-unguarded).
#
# 🔴 산문 grep 금지 — 아래는 **실제로 태스크를 실행**해 예외 전파 여부를 관측한다.
# No source-grep assertions: the queued task is actually executed and observed.
# ---------------------------------------------------------------------------

_FAKE_TG_TOKEN = "123456:FAKE_TOKEN_FOR_TEST"
_FAKE_TG_URL = f"https://api.telegram.org/bot{_FAKE_TG_TOKEN}/sendMessage"
_MESSAGE_UPDATE = {
    "update_id": 9,
    "message": {"message_id": 1, "text": "/start",
                "from": {"id": 1, "username": "john"}, "chat": {"id": -100123}},
}


def _failing_post_mock():
    """Telegram API 401 을 재현하는 mock — 예외 문자열에 토큰 URL 이 박혀 있다(httpx 실제 형태).
    Reproduces a Telegram 401; the exception string embeds the token URL exactly like httpx.
    """
    return AsyncMock(side_effect=httpx.HTTPError(
        f"Client error '401 Unauthorized' for url '{_FAKE_TG_URL}'"
    ))


@contextlib.contextmanager
def _queued_reply_task(post_mock):
    """`_handle_message` 로 응답 전송 태스크를 실제 큐에 넣고, **태스크 실행 시점까지** patch 를 유지한다.
    Queue the reply task via _handle_message and keep the patches active *through task execution*.

    🔴 patch 를 태스크 실행까지 유지해야 하는 이유: 가드 래퍼는 `telegram_post_message` 를
    **실행 시점에** 모듈 전역에서 해석한다. 큐 등록 직후 patch 를 풀면 래퍼가 **실제 함수**를
    호출해 http_client 로 나가버리고, 테스트는 가드가 아니라 네트워크 계층에서 실패한다
    (실측 확인 — 이 함수가 contextmanager 인 이유다).
    The guard wrapper resolves telegram_post_message from module globals at *call* time, so
    releasing the patch after queueing would let the real function run and fail in the HTTP layer
    instead of exercising the guard (measured — hence the contextmanager).
    """
    import src.webhook.providers.telegram as _tg  # pylint: disable=import-outside-toplevel

    bg = BackgroundTasks()
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(MagicMock())), \
         patch("src.webhook.providers.telegram.handle_message_command", return_value="hi"), \
         patch("src.webhook.providers.telegram.telegram_post_message", post_mock):
        result = _tg._handle_message(_MESSAGE_UPDATE, bg, _FAKE_TG_TOKEN)  # pylint: disable=protected-access
        assert result == {"status": "ok"}
        assert bg.tasks, "응답 전송 태스크가 큐에 등록되지 않았다 — 가드 검증 불가(테스트 전제 붕괴)"
        yield bg


async def test_message_reply_background_task_does_not_propagate_http_error():
    """🔴 핵심 — `telegram_post_message` 가 HTTPError 를 던져도 백그라운드 태스크 밖으로 새지 않는다.

    예외가 전파되면 uvicorn 이 exc_info 로 받아 적고, httpx 메시지에 박힌 토큰 URL 이 운영
    로그에 평문으로 남는다. 형제 호출처와 동일하게 좁게 흡수해야 한다.
    A propagated exception reaches uvicorn's exc_info logging, which prints the token-bearing URL.
    """
    post_mock = _failing_post_mock()

    with _queued_reply_task(post_mock) as bg:
        # 🔴 실제 실행 — 여기서 예외가 새면 운영에서 uvicorn 이 토큰 트레이스백을 남긴다.
        # Actually run it: an escape here is exactly the production leak.
        await bg()

    # 흡수하되 **전송 자체는 시도**해야 한다 — 가드가 발신을 통째로 없애면 기능 회귀다.
    # Swallow, but still attempt the send: a guard that drops the send is a functional regression.
    post_mock.assert_awaited_once()


async def test_message_reply_guard_does_not_log_bot_token(caplog):
    """🔴 흡수하면서 토큰을 로깅하지 않는다 — 예외 **타입명만** 남긴다.

    가드를 달면서 `logger.exception(...)` 이나 `%s` 로 예외 객체를 찍으면 사고가 그대로
    재현된다(httpx 예외 문자열 = 토큰 URL 포함). 관측은 유지하되 페이로드는 버려야 한다.
    Guarding with logger.exception / %s on the exception object reproduces the leak verbatim,
    because the httpx message *is* the token URL.

    🔴 **`caplog.text` 만으로는 이 계약을 검증할 수 없다 (뮤테이션 실측으로 확인)**:
    `logger.exception` 으로 바꿔도 `caplog.text` 에는 토큰이 안 나타난다 — `logging_config` 의
    리댁션 필터가 root 핸들러(캡처 핸들러보다 **앞선** 순서)에서 `record.exc_text` 를 **제자리
    변형**하기 때문이다. 즉 계층 2 가 계층을 가려 테스트가 spurious-pass 한다. 따라서
    `record.exc_info` 자체를 단언해 **호출처가 트레이스백을 만들지 않는 것**을 직접 잠근다.
    🔴 caplog.text alone cannot verify this (measured via mutation): swapping in logger.exception
    still shows no token, because the redaction filter mutates record.exc_text in place on an
    earlier root handler. Layer 2 masks the defect, so we assert on record.exc_info directly.
    """
    caplog.set_level(logging.WARNING)

    with _queued_reply_task(_failing_post_mock()) as bg:
        await bg()

    text = caplog.text
    assert "FAKE_TOKEN_FOR_TEST" not in text, (
        f"🔴 봇 토큰이 가드의 로그에 평문으로 남았다 — 예외 객체/메시지를 그대로 찍고 있다.\n"
        f"로그: {text!r}"
    )
    assert _FAKE_TG_URL not in text, (
        f"🔴 토큰이 박힌 요청 URL 전문이 로그에 남았다.\n로그: {text!r}"
    )
    assert "HTTPError" in text, (
        f"실패가 전혀 관측되지 않는다 — 좁게 흡수하되 `type(exc).__name__` 은 남겨야 "
        f"운영에서 Telegram 전송 실패를 인지할 수 있다(silent swallow 금지).\n로그: {text!r}"
    )

    assert caplog.records, "가드가 아무것도 로깅하지 않았다 — silent swallow"
    for record in caplog.records:
        # 🔴 리댁션 필터의 in-place 변형에 영향받지 않는 축 — 호출처가 exc_info 를 붙였는지.
        # Immune to the filter's in-place mutation: did the call site attach exc_info at all?
        assert record.exc_info is None, (
            "🔴 가드가 `logger.exception`/`exc_info=True` 로 트레이스백을 남겼다. 트레이스백에는 "
            "토큰 URL 이 통째로 들어가며, 지금은 리댁션 필터(계층 2)가 우연히 가려 줄 뿐이다 — "
            "신규 시크릿 URL 형태나 필터 미적용 핸들러에서는 그대로 유출된다. "
            "`type(exc).__name__` 만 로깅할 것."
        )
        assert "FAKE_TOKEN_FOR_TEST" not in record.getMessage(), (
            f"🔴 원본 레코드 메시지에 토큰이 들어 있다 — 필터가 가려 주기 전 단계에서 이미 "
            f"유출됐다.\n메시지: {record.getMessage()!r}"
        )
