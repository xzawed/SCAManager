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

from types import SimpleNamespace

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
    """기본적으로 게이트 결정 claim 과 **게시 클레임**이 성공하도록 패치 (#11 · #1504 R2).

    🔴 `claim_post_attempt` 도 함께 패치한다. 그것이 게시 권한의 **단일 관문**이라
    패치하지 않으면 mock 세션의 `query()` 를 그대로 타서 시험이 다른 것을 재게 된다
    (실측: `StopIteration` — mock 의 side_effect 시퀀스가 고갈됐다).

    🔴 돌려주는 행의 `decision` 은 **직전 `claim_decision` 이 받은 값**을 반향한다.
    프로덕션은 「클레임된 결정을 게시한다」이므로 스텁도 그래야 한다 — 고정값을 쓰면
    approve/reject 를 가르는 시험이 전부 한쪽으로 쏠린다.

    리플레이/동시패자 케이스는 개별 테스트가 `claim_post_attempt → None` 으로 덮는다 —
    `claim_decision → False` 는 더 이상 리플레이를 뜻하지 않는다(게시 실패 후 재시도가 그 상태다).
    Patch both claims; the stub echoes the claimed decision because production posts that one.
    """
    seen: dict = {}

    def _claim(_db, _analysis_id, decision, _mode, decided_by=None):
        seen["decision"] = decision
        seen["decided_by"] = decided_by
        return True

    def _claim_post(_db, _analysis_id, **_kwargs):
        return SimpleNamespace(
            decision=seen.get("decision", "approve"), decided_by=seen.get("decided_by")
        )

    with patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision",
               side_effect=_claim),          patch("src.webhook.providers.telegram.gate_decision_repo.claim_post_attempt",
               side_effect=_claim_post),          patch("src.webhook.providers.telegram.gate_decision_repo.mark_posted"),          patch("src.webhook.providers.telegram.gate_decision_repo.release_post_claim"):
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
        # 🔴 리플레이는 이제 **게시 클레임 실패**로 표현한다 (#1504 R2).
        #    `claim_decision → False` 는 「이미 결정됨」일 뿐이고, 그중 게시가 실패한 행은
        #    **재시도 대상**이다. 부수효과를 가르는 관문은 `claim_post_attempt` 다.
        with patch("src.webhook.providers.telegram.gate_decision_repo.claim_post_attempt",
                   return_value=None) as mock_claim:  # 이미 게시됨 또는 게시 중
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


# --- 리플레이 **입력 클래스** — 부수효과 skip 은 옳지만 무음이면 안 된다 (#1431) ---
# 🔴 위 테스트가 `chat_id` 를 주지 않아 이 조합을 0건 남겼다. `#1412`/`#1414` 는 「게시 성공 +
#    후속 실패」를 고쳤을 뿐 **다시 누른 사람**은 여전히 아무 응답도 받지 못했다.
#    Replay input class: skipping side effects is correct, staying silent is not.


async def test_handle_gate_callback_replay_notifies_clicker():
    """#1431: claim 패자(이미 결정됨) + chat_id 있음 → 「이미 결정됨」 안내 1회.

    사용자 관점 시퀀스 — ✅ 를 눌렀는데 게시가 실패해 「미게시」를 받고, **다시 누른다**.
    그때 claim 은 이미 있으므로 False 로 떨어지는데, 여기서 무음이면 사용자는 무한 대기하고
    DB 에는 승인이 남아 있으며 GitHub 에는 리뷰가 없다.
    The clicker presses again after a not-posted notice; silence leaves them waiting forever.
    """
    from src.webhook.router import handle_gate_callback  # pylint: disable=import-outside-toplevel

    mock_db, config = _gate_callback_failure_mocks()
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
            with patch(
                "src.webhook.providers.telegram.resolve_notification_language",
                return_value="ko",
            ):
                with patch(
                    "src.webhook.providers.telegram.gate_decision_repo.claim_post_attempt",
                    return_value=None,
                ) as mock_claim:
                    with patch(
                        "src.webhook.providers.telegram.post_github_review",
                        new_callable=AsyncMock,
                    ) as mock_review:
                        with patch(
                            "src.webhook.providers.telegram._post_message_guarded",
                            new_callable=AsyncMock,
                        ) as mock_post:
                            await handle_gate_callback(
                                analysis_id=42,
                                decision="approve",
                                decided_by="john",
                                telegram_user_id="1",
                                chat_id="-100999",
                            )
    mock_claim.assert_called_once()
    mock_review.assert_not_called()      # 부수효과는 여전히 skip — 리플레이 가드 불변
    mock_post.assert_called_once()       # 🔴 그러나 무음이면 안 된다
    _bot, _chat, payload = mock_post.call_args[0]
    assert _chat == "-100999"
    assert payload.get("parse_mode") == "HTML"
    # 문구가 「미게시」 계열과 갈려야 한다 — 리뷰가 붙어 있을 수도 있으므로 단정하면 거짓이 된다.
    # The wording must differ from the not-posted family: the review may in fact be live.
    assert "이미" in payload["text"], "리플레이 안내가 「이미 결정됨」 의미를 담지 않는다"


async def test_handle_gate_callback_replay_without_chat_id_stays_silent():
    """#1431 새 입력 클래스: 리플레이 + `chat_id=None` → 발신 0건 (크래시 없이).

    🔴 이 테스트가 없으면 위 수정이 `chat_id is None` 경로에서 터진다. 콜백은 BackgroundTask 라
    예외가 나도 사용자에게 보이지 않고 조용히 사라진다 — 그래서 여기서 고정한다.
    Newly reachable class: the notify branch must not fire (or crash) without a chat_id.
    """
    from src.webhook.router import handle_gate_callback  # pylint: disable=import-outside-toplevel

    mock_db, config = _gate_callback_failure_mocks()
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
            with patch(
                "src.webhook.providers.telegram.gate_decision_repo.claim_post_attempt",
                return_value=None,
            ):
                with patch(
                    "src.webhook.providers.telegram._post_message_guarded",
                    new_callable=AsyncMock,
                ) as mock_post:
                    await handle_gate_callback(
                        analysis_id=42, decision="approve",
                        decided_by="john", telegram_user_id="1",
                    )
    mock_post.assert_not_called()


@pytest.mark.parametrize("boom", [
    # 🔴 **프로덕션 실경로.** `_post_message_guarded` 는 `httpx.HTTPError` 만 삼키는데
    #    (`telegram.py` 참조), 그 안의 `get_http_client()` 는 lifespan 밖에서
    #    `RuntimeError` 를 낸다(`src/shared/http_client.py:71-74`). 그 타입은 발신 가드를
    #    빠져나가 호출부 `try:` 본문으로 샌다 — 여기가 이 테스트의 진짜 근거다.
    RuntimeError("HTTP client not initialized"),
    # 방어적 2차 트리거. ⚠️ 정직 기준: 현재 `get_text` 는 누락 키에 **raise 하지 않고**
    #    키를 그대로 돌려준다(`src/i18n/loader.py`) — 즉 이 조합은 합성이다.
    #    loader 가 언젠가 raise 로 바뀌어도 거짓 알림이 나지 않도록 고정해 둔다.
    KeyError("notifier.gate.callback_already_decided"),
])
async def test_handle_gate_callback_replay_notice_failure_does_not_lie(boom):
    """#1431 자기결함 가드: 리플레이 안내 자체가 실패해도 「미게시」를 발신하면 안 된다.

    🔴 이 수정이 실제로 재생산했던 결함이다. 첫 구현의 발신은 `try:` **본문 안**에 있어,
    거기서 새는 예외가 형제 `except (…, RuntimeError, KeyError, …)` 로 떨어졌다. 그 분기는
    `review_posted=False` 라 «리뷰가 게시되지 않았습니다» 를 보내는데 — 이건 **리플레이**다.
    첫 클릭이 게시까지 성공했을 수 있으므로 그 문구는 거짓이 될 수 있다.
    `#1414` 가 고친 것과 같은 클래스다.

    The replay notice must not let its own failure fall through to the sibling except and emit
    a "not posted" claim about what is actually a replay.
    """
    from src.webhook.router import handle_gate_callback  # pylint: disable=import-outside-toplevel

    mock_db, config = _gate_callback_failure_mocks()
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
            with patch(
                "src.webhook.providers.telegram.resolve_notification_language",
                return_value="ko",
            ):
                with patch(
                    "src.webhook.providers.telegram.gate_decision_repo.claim_post_attempt",
                    return_value=None,
                ):
                    with patch(
                        "src.webhook.providers.telegram._post_message_guarded",
                        new_callable=AsyncMock,
                        side_effect=boom,
                    ) as mock_post:
                        await handle_gate_callback(
                            analysis_id=42, decision="approve", decided_by="john",
                            telegram_user_id="1", chat_id="-100999",
                        )
    sent = [c[0][2].get("text", "") for c in mock_post.call_args_list]
    assert not any("게시되지 않았습니다" in t for t in sent), (
        f"리플레이인데 「미게시」 문구를 발신했다 — 거짓 알림: {sent}"
    )
    # 🔴 「안 쟀음」과 구별 — 안내 시도 자체는 있었어야 한다(분기에 도달했다는 증거).
    # Distinguish from "never measured": the notice attempt itself must have happened.
    mock_post.assert_called_once()


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
            # 🔴 게시할 결정을 **명시**한다 — 프로덕션은 클레임된 결정을 게시하므로
            #    (#1504 R2), 클릭의 `decision` 만 주면 이 시험이 reject 를 재지 못한다.
            #    `claim_decision` 을 갈아치우면 autouse 픽스처의 반향이 끊기기 때문이다.
            with patch("src.webhook.providers.telegram.gate_decision_repo.claim_post_attempt",
                       return_value=SimpleNamespace(decision="reject", decided_by="john")),                  patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision") as mock_save:
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


# --- 갈래 A: 게이트 콜백 실패 시 Telegram 미게시 알림 (claim 유지, 스키마 변경 없음) ---
# Branch A: notify clicker when GitHub review was NOT posted (claim kept, no schema change)


def _gate_callback_failure_mocks():
    """실패 알림 테스트용 analysis/repo/db/config mock 묶음.
    Mock bundle for failure-notification tests (analysis/repo/db/config)."""
    mock_analysis = MagicMock(
        id=42, repo_id=1, pr_number=5, score=85, commit_sha="abc", result={"score": 85},
    )
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        mock_analysis, mock_repo
    ]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=False)
    return mock_db, config


async def test_handle_gate_callback_head_moved_notifies_user():
    """HeadMovedError → 미게시 알림 1회 + claim_decision 철회 없음.
    HeadMovedError → one not-posted notice; claim is NOT rolled back."""
    from src.gate.github_review import HeadMovedError  # pylint: disable=import-outside-toplevel
    from src.webhook.router import handle_gate_callback  # pylint: disable=import-outside-toplevel

    mock_db, config = _gate_callback_failure_mocks()
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch(
            "src.webhook.providers.telegram.post_github_review",
            new_callable=AsyncMock,
            side_effect=HeadMovedError("analyzed=aaa head=bbb"),
        ):
            with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                with patch(
                    "src.webhook.providers.telegram.resolve_notification_language",
                    return_value="ko",
                ):
                    with patch(
                        "src.webhook.providers.telegram.gate_decision_repo.claim_decision",
                        return_value=True,
                    ) as mock_claim:
                        with patch(
                            "src.webhook.providers.telegram._post_message_guarded",
                            new_callable=AsyncMock,
                        ) as mock_post:
                            await handle_gate_callback(
                                analysis_id=42,
                                decision="approve",
                                decided_by="john",
                                telegram_user_id="1",
                                chat_id="-100999",
                            )
    mock_claim.assert_called_once()
    mock_post.assert_called_once()
    _bot, _chat, payload = mock_post.call_args[0]
    assert _chat == "-100999"
    assert payload.get("parse_mode") == "HTML"
    assert "미게시" in payload["text"]


async def test_handle_gate_callback_broad_exception_notifies_user():
    """broad except (HTTPError 등) → 미게시 알림 발송.
    Broad exception path also notifies the clicker that the review was not posted."""
    from src.webhook.router import handle_gate_callback  # pylint: disable=import-outside-toplevel

    mock_db, config = _gate_callback_failure_mocks()
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch(
            "src.webhook.providers.telegram.post_github_review",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("GitHub API down"),
        ):
            with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                with patch(
                    "src.webhook.providers.telegram.resolve_notification_language",
                    return_value="ko",
                ):
                    with patch(
                        "src.webhook.providers.telegram._post_message_guarded",
                        new_callable=AsyncMock,
                    ) as mock_post:
                        await handle_gate_callback(
                            analysis_id=42,
                            decision="approve",
                            decided_by="john",
                            telegram_user_id="1",
                            chat_id="-100999",
                        )
    mock_post.assert_called_once()
    payload = mock_post.call_args[0][2]
    assert "미게시" in payload["text"]


async def test_handle_gate_callback_failure_skips_notify_when_chat_id_none():
    """chat_id=None → 발신 없음, 예외 전파 없음.
    chat_id=None → no send and no raise."""
    from src.gate.github_review import HeadMovedError  # pylint: disable=import-outside-toplevel
    from src.webhook.router import handle_gate_callback  # pylint: disable=import-outside-toplevel

    mock_db, config = _gate_callback_failure_mocks()
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch(
            "src.webhook.providers.telegram.post_github_review",
            new_callable=AsyncMock,
            side_effect=HeadMovedError("head moved"),
        ):
            with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                with patch(
                    "src.webhook.providers.telegram._post_message_guarded",
                    new_callable=AsyncMock,
                ) as mock_post:
                    await handle_gate_callback(
                        analysis_id=42,
                        decision="approve",
                        decided_by="john",
                        telegram_user_id="1",
                        chat_id=None,
                    )
    mock_post.assert_not_called()


async def test_handle_gate_callback_success_does_not_send_failure_notice():
    """성공 경로 → 실패 알림 미발송 (스팸 회귀 방지).
    Success path must not send a failure notification (no spam on success)."""
    from src.webhook.router import handle_gate_callback  # pylint: disable=import-outside-toplevel

    mock_db, config = _gate_callback_failure_mocks()
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch(
            "src.webhook.providers.telegram.post_github_review",
            new_callable=AsyncMock,
        ):
            with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                with patch(
                    "src.webhook.providers.telegram._post_message_guarded",
                    new_callable=AsyncMock,
                ) as mock_post:
                    await handle_gate_callback(
                        analysis_id=42,
                        decision="approve",
                        decided_by="john",
                        telegram_user_id="1",
                        chat_id="-100999",
                    )
    mock_post.assert_not_called()


async def test_handle_gate_callback_failure_notice_omits_exception_text():
    """발신 텍스트에 예외 문자열 부재 — httpx URL 에 bot token 이 실림.
    Sent text must not contain the exception string (httpx embeds bot token in URL)."""
    from src.webhook.router import handle_gate_callback  # pylint: disable=import-outside-toplevel

    secret_exc = "Client error '401' for url 'https://api.telegram.org/botSECRET_TOKEN/sendMessage'"
    mock_db, config = _gate_callback_failure_mocks()
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch(
            "src.webhook.providers.telegram.post_github_review",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError(secret_exc),
        ):
            with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                with patch(
                    "src.webhook.providers.telegram.resolve_notification_language",
                    return_value="ko",
                ):
                    with patch(
                        "src.webhook.providers.telegram._post_message_guarded",
                        new_callable=AsyncMock,
                    ) as mock_post:
                        await handle_gate_callback(
                            analysis_id=42,
                            decision="approve",
                            decided_by="john",
                            telegram_user_id="1",
                            chat_id="-100999",
                        )
    mock_post.assert_called_once()
    sent_text = mock_post.call_args[0][2]["text"]
    assert secret_exc not in sent_text
    assert "SECRET_TOKEN" not in sent_text
    assert "미게시" in sent_text


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


# ──────────────────────────────────────────────────────────────────────────────
# 배선 — dispatcher 가 실제로 `chat_id` 를 넘기는가 (3-불변식 ③: 정의 ≠ 배선)
#
# 🔴 위 실패-알림 테스트들은 `handle_gate_callback` 을 **직접** 호출한다. 그래서
# dispatcher(`telegram_webhook`)에서 `chat_id=chat_id` 한 줄을 지워도 전부 초록이다 —
# 알림 기능은 코드에 존재하지만 운영에서는 `chat_id=None` 이라 **한 번도 발화하지 않는다**.
# 이 축은 라우트를 실제로 태워서만 잴 수 있다.
# The failure-notice tests call the handler directly, so dropping `chat_id=chat_id` at the
# dispatcher would keep them green while production silently always passes None.
# ──────────────────────────────────────────────────────────────────────────────


def test_dispatcher_passes_chat_id_from_callback_message():
    """🔴 라우트가 `callback_query.message.chat.id` 를 핸들러까지 전달한다."""
    with patch("src.webhook.providers.telegram.handle_gate_callback",
               new_callable=AsyncMock) as mock_gate:
        r = client.post("/api/webhook/telegram", json=APPROVE, headers=_TG_HEADERS)
    assert r.status_code == 200
    mock_gate.assert_called_once()
    kwargs = mock_gate.call_args.kwargs
    assert "chat_id" in kwargs, (
        "dispatcher 가 chat_id 를 안 넘긴다 — 실패 알림이 운영에서 영원히 skip 된다"
    )
    expected = str(APPROVE["callback_query"]["message"]["chat"]["id"])
    assert kwargs["chat_id"] == expected, (
        f"chat_id 가 payload 와 다르다: {kwargs['chat_id']!r} != {expected!r}"
    )


def test_dispatcher_passes_none_when_chat_is_absent():
    """chat 이 없는 페이로드면 None — 크래시 없이 알림만 skip 된다."""
    payload = {
        "update_id": 4242,
        "callback_query": {
            "id": "c4242",
            "from": {"id": 1, "username": "john"},
            "data": f"gate:approve:42:{_TOKEN_42}",
        },
    }
    with patch("src.webhook.providers.telegram.handle_gate_callback",
               new_callable=AsyncMock) as mock_gate:
        r = client.post("/api/webhook/telegram", json=payload, headers=_TG_HEADERS)
    assert r.status_code == 200
    mock_gate.assert_called_once()
    assert mock_gate.call_args.kwargs.get("chat_id") is None


async def test_notice_does_not_claim_not_posted_when_the_review_did_land():
    """🔴 리뷰 게시가 **성공한 뒤** auto-merge 가 터지면 «게시되지 않았습니다» 는 거짓이다.

    ## 실측 사고 (`#1412` fcad25ca 가 그 상태로 머지됐다)

    `post_github_review` 성공 → `_run_auto_merge` 예외 → 같은 broad except 로 낙하 →
    `callback_failed`(«리뷰가 게시되지 않았습니다») 발신. 그런데 리뷰는 **GitHub 에 붙어 있다**.

    그 거짓말의 대가:
      (a) 사용자가 다시 누른다 → `already decided — skipping replay` 로 무시된다
      (b) GitHub 에서 수동 승인한다 → **중복 리뷰**

    게이트가 조용한 것보다 **틀린 말을 하는 것이 나쁘다** — 조용하면 확인하러 가지만,
    틀린 말은 사용자를 잘못된 행동으로 이끈다.
    A post-success + auto-merge-failure must not tell the user the review was not posted.
    """
    from src.webhook.router import handle_gate_callback  # pylint: disable=import-outside-toplevel

    mock_db, config = _gate_callback_failure_mocks()
    config.auto_merge = True  # auto-merge 경로를 태워야 그 예외가 난다
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch(
            "src.webhook.providers.telegram.post_github_review", new_callable=AsyncMock
        ) as mock_review:  # 🔴 성공한다
            with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                with patch(
                    "src.webhook.providers.telegram.resolve_notification_language",
                    return_value="ko",
                ):
                    with patch(
                        "src.webhook.providers.telegram.gate_decision_repo.claim_decision",
                        return_value=True,
                    ):
                        with patch(
                            "src.gate.engine._run_auto_merge",
                            new_callable=AsyncMock,
                            side_effect=RuntimeError("merge queue exploded"),
                        ):
                            with patch(
                                "src.webhook.providers.telegram._post_message_guarded",
                                new_callable=AsyncMock,
                            ) as mock_post:
                                await handle_gate_callback(
                                    analysis_id=42,
                                    decision="approve",
                                    decided_by="john",
                                    telegram_user_id="1",
                                    chat_id="-100999",
                                )

    mock_review.assert_awaited_once(), "전제 붕괴 — 리뷰 게시가 호출되지 않았다"
    mock_post.assert_called_once()
    text = mock_post.call_args[0][2]["text"]
    assert "미게시" not in text, (
        f"리뷰가 실제로 게시됐는데 «미게시» 라고 알렸다 — 사용자가 중복 리뷰를 만든다:\n{text}"
    )
    assert "게시" in text, f"게시 사실을 언급하지 않는다: {text}"


async def test_not_posted_notice_still_says_not_posted_when_the_review_failed():
    """대칭 — 게시 자체가 실패했으면 «미게시» 가 맞다 (위 수정이 이 축을 끄지 않았는지)."""
    from src.webhook.router import handle_gate_callback  # pylint: disable=import-outside-toplevel

    mock_db, config = _gate_callback_failure_mocks()
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)):
        with patch(
            "src.webhook.providers.telegram.post_github_review",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("GitHub API down"),
        ):
            with patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
                with patch(
                    "src.webhook.providers.telegram.resolve_notification_language",
                    return_value="ko",
                ):
                    with patch(
                        "src.webhook.providers.telegram.gate_decision_repo.claim_decision",
                        return_value=True,
                    ):
                        with patch(
                            "src.webhook.providers.telegram._post_message_guarded",
                            new_callable=AsyncMock,
                        ) as mock_post:
                            await handle_gate_callback(
                                analysis_id=42, decision="approve", decided_by="john",
                                telegram_user_id="1", chat_id="-100999",
                            )
    assert "미게시" in mock_post.call_args[0][2]["text"]


# ── 게시 실패 뒤 재클릭이 **재시도된다** (#1504 R2) ───────────────────────────
#
# 🔴 이것이 `#1504` R2 가 고치려던 것이다. 이전에는 `claim_decision` 이 False 를 돌리면
#    무조건 리플레이로 막혀, 전송 오류로 리뷰가 안 붙은 결정은 **자동 복구 수단이 없었다**
#    (새 푸시로 새 analysis_id 를 만드는 것이 유일한 우회였다).
#
# 🔴 위 리플레이 시험들과 **짝**이다. 그쪽은 `claim_post_attempt → None`(이미 게시됨)이고
#    이쪽은 행을 돌려준다(미게시). 둘이 함께 있어야 「관문이 실제로 가른다」가 성립한다 —
#    한쪽만 두면 「항상 막는다」 또는 「항상 통과」와 구별되지 않는다.


async def test_a_decision_whose_post_failed_is_retried_on_the_next_click():
    """🔴 결정은 기록됐는데 게시가 실패한 행은 다시 누르면 **게시된다**."""
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=85, result={"score": 85})
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [mock_analysis, mock_repo]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=False, merge_threshold=75)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision",
               return_value=False), \
         patch("src.webhook.providers.telegram.gate_decision_repo.claim_post_attempt",
               return_value=SimpleNamespace(decision="approve", decided_by="john")), \
         patch("src.webhook.providers.telegram.gate_decision_repo.mark_posted") as mock_mark, \
         patch("src.webhook.providers.telegram.post_github_review",
               new_callable=AsyncMock) as mock_review, \
         patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
        await handle_gate_callback(analysis_id=42, decision="approve",
                                   decided_by="john", telegram_user_id="1")
    mock_review.assert_called_once()   # 🔴 이전에는 여기가 0회였다 — 재시도 불가
    mock_mark.assert_called_once()     # 성공했으면 못 박는다


async def test_the_retry_posts_the_claimed_decision_not_the_new_click():
    """🔴 재시도는 **클레임된 결정**을 게시한다 — approve→reject 뒤집기를 되살리지 않는다.

    HMAC 은 `gate:{analysis_id}` 만 서명하므로 같은 버튼으로 다른 결정을 보낼 수 있다.
    재시도가 새 클릭의 결정을 따르면 `claim_decision` 이 막던 뒤집기가 그대로 돌아온다.
    """
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=85, result={"score": 85})
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [mock_analysis, mock_repo]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=False, merge_threshold=75)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.webhook.providers.telegram.gate_decision_repo.claim_decision",
               return_value=False), \
         patch("src.webhook.providers.telegram.gate_decision_repo.claim_post_attempt",
               return_value=SimpleNamespace(decision="approve", decided_by="john")), \
         patch("src.webhook.providers.telegram.gate_decision_repo.mark_posted"), \
         patch("src.webhook.providers.telegram.post_github_review",
               new_callable=AsyncMock) as mock_review, \
         patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
        # 클릭은 reject 인데 클레임된 결정은 approve 다.
        await handle_gate_callback(analysis_id=42, decision="reject",
                                   decided_by="mallory", telegram_user_id="1")
    assert mock_review.call_args.args[3] == "approve", (
        f"재시도가 새 클릭의 결정을 게시했다 — 뒤집기가 되살아났다: {mock_review.call_args.args}"
    )


async def test_a_failed_post_releases_the_lease_so_the_next_click_can_retry():
    """🔴 알려진 실패는 리스를 푼다 — 사람을 리스 길이만큼 기다리게 하지 않는다."""
    from src.webhook.router import handle_gate_callback
    mock_analysis = MagicMock(id=42, repo_id=1, pr_number=5, score=85, result={"score": 85})
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=1)
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [mock_analysis, mock_repo]
    config = RepoConfigData(repo_full_name="owner/repo", auto_merge=False, merge_threshold=75)
    with patch("src.webhook.providers.telegram.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.webhook.providers.telegram.gate_decision_repo.claim_post_attempt",
               return_value=SimpleNamespace(decision="approve", decided_by="john")), \
         patch("src.webhook.providers.telegram.gate_decision_repo.release_post_claim") as mock_rel, \
         patch("src.webhook.providers.telegram.post_github_review",
               new_callable=AsyncMock, side_effect=ValueError("transport")), \
         patch("src.webhook.providers.telegram.get_repo_config", return_value=config):
        await handle_gate_callback(analysis_id=42, decision="approve",
                                   decided_by="john", telegram_user_id="1")
    mock_rel.assert_called_once()
