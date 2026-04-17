import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

# ------------------------------------------------------------------
# 공통 ai_result 픽스처 데이터
# ------------------------------------------------------------------

_AI_RESULT = {
    "commit_message_score": 15,
    "direction_score": 18,
    "test_score": 8,
    "summary": "테스트 요약",
    "suggestions": ["제안1"],
    "commit_message_feedback": "좋음",
    "code_quality_feedback": "좋음",
    "security_feedback": "없음",
    "direction_feedback": "명확함",
    "test_feedback": "테스트 있음",
    "file_feedbacks": [],
}


def _make_session_mock(db_mock):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_mock)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


# ------------------------------------------------------------------
# GET /api/hook/verify
# ------------------------------------------------------------------

def test_verify_valid_token():
    # 유효한 repo + token 조합일 때 200 {"status": "active"} 반환
    mock_db = MagicMock()
    mock_config = MagicMock()
    mock_config.hook_token = "valid-hook-token-abc"
    mock_db.query.return_value.filter.return_value.first.return_value = mock_config

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.get("/api/hook/verify", params={"repo": "owner/repo", "token": "valid-hook-token-abc"})

    assert r.status_code == 200
    assert r.json()["status"] == "active"


def test_verify_invalid_token():
    # token이 DB의 hook_token과 불일치 → 404 반환
    mock_db = MagicMock()
    mock_config = MagicMock()
    mock_config.hook_token = "correct-token"
    mock_db.query.return_value.filter.return_value.first.return_value = mock_config

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.get("/api/hook/verify", params={"repo": "owner/repo", "token": "wrong-token"})

    assert r.status_code == 404


def test_verify_unknown_repo():
    # DB에 존재하지 않는 repo → 404 반환
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.get("/api/hook/verify", params={"repo": "ghost/no-such-repo", "token": "any-token"})

    assert r.status_code == 404


# ------------------------------------------------------------------
# POST /api/hook/result
# ------------------------------------------------------------------

def test_hook_result_saves_analysis():
    # 유효한 token + ai_result JSON → Analysis 레코드가 DB에 저장됨
    mock_db = MagicMock()
    mock_config = MagicMock()
    mock_config.hook_token = "save-token"
    mock_repo = MagicMock()
    mock_repo.id = 42

    # query(RepoConfig).filter().first() → mock_config
    # query(Repository).filter().first() → mock_repo
    query_side_effects = {
        0: mock_config,  # RepoConfig 조회
        1: mock_repo,    # Repository 조회
    }
    call_count = {"n": 0}

    def _first_side_effect():
        idx = call_count["n"]
        call_count["n"] += 1
        return query_side_effects.get(idx)

    mock_db.query.return_value.filter.return_value.first.side_effect = _first_side_effect
    mock_db.query.return_value.filter_by.return_value.first.return_value = None  # no duplicate
    mock_db.add = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.refresh = MagicMock()

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.post("/api/hook/result", json={
            "repo": "owner/repo",
            "token": "save-token",
            "commit_sha": "abc123def456",
            "commit_message": "feat: 새 기능",
            "ai_result": _AI_RESULT,
        })

    assert r.status_code == 200
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


def test_hook_result_calculates_score():
    # ai_result 점수가 calculate_score에 의해 변환되어 Analysis.score에 저장됨
    mock_db = MagicMock()
    mock_config = MagicMock()
    mock_config.hook_token = "score-token"
    mock_repo = MagicMock()
    mock_repo.id = 7

    call_count = {"n": 0}

    def _first_side_effect():
        idx = call_count["n"]
        call_count["n"] += 1
        return {0: mock_config, 1: mock_repo}.get(idx)

    mock_db.query.return_value.filter.return_value.first.side_effect = _first_side_effect
    mock_db.query.return_value.filter_by.return_value.first.return_value = None  # no duplicate
    mock_db.add = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.refresh = MagicMock()

    saved_analyses = []

    def capture_add(obj):
        saved_analyses.append(obj)

    mock_db.add.side_effect = capture_add

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.post("/api/hook/result", json={
            "repo": "owner/repo",
            "token": "score-token",
            "commit_sha": "abc123score",
            "commit_message": "feat: 스코어 계산 테스트",
            "ai_result": _AI_RESULT,
        })

    assert r.status_code == 200

    # commit_message_score=15 → round(15*15/20)=11
    # direction_score=18 → round(18*25/20)=22
    # test_score=8 → round(8*15/10)=12
    # code_quality=25(no issues), security=20(no issues)
    # total = 25 + 20 + 11 + 22 + 12 = 90 → grade A
    assert len(saved_analyses) == 1
    analysis_obj = saved_analyses[0]
    assert analysis_obj.score == 90
    assert analysis_obj.grade == "A"


def test_hook_result_invalid_token():
    # hook_token 불일치 → 403 반환, DB에 저장 안 됨
    mock_db = MagicMock()
    mock_config = MagicMock()
    mock_config.hook_token = "correct-token"
    mock_db.query.return_value.filter.return_value.first.return_value = mock_config

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.post("/api/hook/result", json={
            "repo": "owner/repo",
            "token": "wrong-token",
            "commit_sha": "abc123",
            "commit_message": "feat: 테스트",
            "ai_result": _AI_RESULT,
        })

    assert r.status_code == 403
    mock_db.add.assert_not_called()


def test_hook_result_missing_fields():
    # 필수 필드(token) 누락 → 422 Unprocessable Entity 반환
    r = client.post("/api/hook/result", json={
        "repo": "owner/repo",
        # token 누락
        "commit_sha": "abc123",
        "commit_message": "feat: 테스트",
        "ai_result": _AI_RESULT,
    })
    assert r.status_code == 422


def test_hook_result_missing_commit_sha():
    # 필수 필드(commit_sha) 누락 → 422 반환
    r = client.post("/api/hook/result", json={
        "repo": "owner/repo",
        "token": "some-token",
        # commit_sha 누락
        "commit_message": "feat: 테스트",
        "ai_result": _AI_RESULT,
    })
    assert r.status_code == 422


def test_hook_result_missing_ai_result():
    # 필수 필드(ai_result) 누락 → 422 반환
    r = client.post("/api/hook/result", json={
        "repo": "owner/repo",
        "token": "some-token",
        "commit_sha": "abc123",
        "commit_message": "feat: 테스트",
        # ai_result 누락
    })
    assert r.status_code == 422


def test_hook_result_empty_ai_result_marks_parse_error():
    # ai_result가 빈 dict이면 status="parse_error"로 저장되어 fallback 경고 배너 표시 가능해야 함
    mock_db = MagicMock()
    mock_config = MagicMock()
    mock_config.hook_token = "empty-token"
    mock_repo = MagicMock()
    mock_repo.id = 1

    call_count = {"n": 0}

    def _first_side_effect():
        idx = call_count["n"]
        call_count["n"] += 1
        return {0: mock_config, 1: mock_repo}.get(idx)

    mock_db.query.return_value.filter.return_value.first.side_effect = _first_side_effect
    mock_db.query.return_value.filter_by.return_value.first.return_value = None
    saved = []
    mock_db.add.side_effect = lambda obj: saved.append(obj)

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.post("/api/hook/result", json={
            "repo": "owner/repo",
            "token": "empty-token",
            "commit_sha": "shaempty",
            "commit_message": "feat: empty",
            "ai_result": {},
        })

    assert r.status_code == 200
    assert len(saved) == 1
    assert saved[0].result["ai_review_status"] == "parse_error"


def test_hook_result_partial_ai_result_marks_parse_error():
    # ai_result에 score 필드 중 일부만 있으면 parse_error로 분류
    mock_db = MagicMock()
    mock_config = MagicMock()
    mock_config.hook_token = "partial-token"
    mock_repo = MagicMock()
    mock_repo.id = 2

    call_count = {"n": 0}

    def _first_side_effect():
        idx = call_count["n"]
        call_count["n"] += 1
        return {0: mock_config, 1: mock_repo}.get(idx)

    mock_db.query.return_value.filter.return_value.first.side_effect = _first_side_effect
    mock_db.query.return_value.filter_by.return_value.first.return_value = None
    saved = []
    mock_db.add.side_effect = lambda obj: saved.append(obj)

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.post("/api/hook/result", json={
            "repo": "owner/repo",
            "token": "partial-token",
            "commit_sha": "shapartial",
            "commit_message": "feat: partial",
            "ai_result": {"commit_message_score": 15},  # direction_score, test_score 누락
        })

    assert r.status_code == 200
    assert saved[0].result["ai_review_status"] == "parse_error"


def test_hook_result_complete_ai_result_marks_success():
    # 모든 score 필드가 있는 정상 ai_result는 status="success"로 저장
    mock_db = MagicMock()
    mock_config = MagicMock()
    mock_config.hook_token = "ok-token"
    mock_repo = MagicMock()
    mock_repo.id = 3

    call_count = {"n": 0}

    def _first_side_effect():
        idx = call_count["n"]
        call_count["n"] += 1
        return {0: mock_config, 1: mock_repo}.get(idx)

    mock_db.query.return_value.filter.return_value.first.side_effect = _first_side_effect
    mock_db.query.return_value.filter_by.return_value.first.return_value = None
    saved = []
    mock_db.add.side_effect = lambda obj: saved.append(obj)

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.post("/api/hook/result", json={
            "repo": "owner/repo",
            "token": "ok-token",
            "commit_sha": "shaok",
            "commit_message": "feat: ok",
            "ai_result": _AI_RESULT,
        })

    assert r.status_code == 200
    assert saved[0].result["ai_review_status"] == "success"


def test_hook_result_unknown_repo_returns_404():
    # hook_token은 맞지만 Repository 레코드가 없을 때 → 404 반환
    mock_db = MagicMock()
    mock_config = MagicMock()
    mock_config.hook_token = "known-token"

    call_count = {"n": 0}

    def _first_side_effect():
        idx = call_count["n"]
        call_count["n"] += 1
        return {0: mock_config, 1: None}.get(idx)  # Repository = None

    mock_db.query.return_value.filter.return_value.first.side_effect = _first_side_effect

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.post("/api/hook/result", json={
            "repo": "owner/ghost-repo",
            "token": "known-token",
            "commit_sha": "abc123",
            "commit_message": "feat: 테스트",
            "ai_result": _AI_RESULT,
        })

    assert r.status_code == 404
    mock_db.add.assert_not_called()


# ------------------------------------------------------------------
# Phase 3-C: block_threshold 기반 차단 판정
# ------------------------------------------------------------------

_LOW_AI_RESULT = {
    # AI가 명시적으로 아주 낮은 점수를 부여한 경우를 가정
    "commit_message_score": 1,
    "direction_score": 1,
    "test_score": 0,
    "summary": "매우 낮은 품질",
    "suggestions": [],
    "commit_message_feedback": "",
    "code_quality_feedback": "",
    "security_feedback": "",
    "direction_feedback": "",
    "test_feedback": "",
    "file_feedbacks": [],
}


def _build_hook_post_mocks(hook_token: str, block_threshold, repo_id: int = 99):
    """POST /api/hook/result 호출을 위한 mock_db + config 세팅 공통 헬퍼.

    RepoConfig.block_threshold를 명시적으로 설정해야 함 (MagicMock 기본 속성 금지).
    """
    mock_db = MagicMock()
    mock_config = MagicMock()
    mock_config.hook_token = hook_token
    mock_config.block_threshold = block_threshold
    mock_repo = MagicMock()
    mock_repo.id = repo_id

    call_count = {"n": 0}

    def _first_side_effect():
        idx = call_count["n"]
        call_count["n"] += 1
        return {0: mock_config, 1: mock_repo}.get(idx)

    mock_db.query.return_value.filter.return_value.first.side_effect = _first_side_effect
    mock_db.query.return_value.filter_by.return_value.first.return_value = None
    saved = []
    mock_db.add.side_effect = lambda obj: saved.append(obj)

    # refresh 호출 후 analysis.id 속성이 할당되도록 simulate
    def _refresh(obj):
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = 12345
    mock_db.refresh.side_effect = _refresh

    return mock_db, saved


def test_hook_result_block_false_when_threshold_none():
    # block_threshold가 None(opt-in 미설정) → 응답 block=False, block_threshold=None
    mock_db, _ = _build_hook_post_mocks("tok-none", block_threshold=None)

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.post("/api/hook/result", json={
            "repo": "owner/repo",
            "token": "tok-none",
            "commit_sha": "sha_block_none",
            "commit_message": "feat: no threshold",
            "ai_result": _AI_RESULT,
        })

    assert r.status_code == 200
    body = r.json()
    assert body["block"] is False
    assert body["block_threshold"] is None


def test_hook_result_block_true_when_score_below_threshold():
    # block_threshold=95, 저점수 AI result → 계산 점수가 95 미만이므로 block=True
    mock_db, saved = _build_hook_post_mocks("tok-low", block_threshold=95)

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.post("/api/hook/result", json={
            "repo": "owner/repo",
            "token": "tok-low",
            "commit_sha": "sha_block_true",
            "commit_message": "feat: low score",
            "ai_result": _LOW_AI_RESULT,
        })

    assert r.status_code == 200
    body = r.json()
    assert saved[0].score < 95  # sanity — 낮은 AI result 로 실제 점수가 낮음
    assert body["block"] is True
    assert body["block_threshold"] == 95


def test_hook_result_block_false_when_score_meets_threshold():
    # block_threshold=60, 고점수(_AI_RESULT=90점) → score >= threshold → block=False
    mock_db, saved = _build_hook_post_mocks("tok-hi", block_threshold=60)

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.post("/api/hook/result", json={
            "repo": "owner/repo",
            "token": "tok-hi",
            "commit_sha": "sha_block_false",
            "commit_message": "feat: high score",
            "ai_result": _AI_RESULT,
        })

    assert r.status_code == 200
    body = r.json()
    assert saved[0].score >= 60
    assert body["block"] is False
    assert body["block_threshold"] == 60


def test_hook_result_block_false_when_score_exactly_threshold():
    # block_threshold == score(90) 인 경계값 — `<` 비교이므로 block=False 이어야 함
    mock_db, saved = _build_hook_post_mocks("tok-eq", block_threshold=90)

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.post("/api/hook/result", json={
            "repo": "owner/repo",
            "token": "tok-eq",
            "commit_sha": "sha_block_eq",
            "commit_message": "feat: edge threshold",
            "ai_result": _AI_RESULT,
        })

    assert r.status_code == 200
    body = r.json()
    assert saved[0].score == 90  # _AI_RESULT → 90
    assert body["block"] is False
    assert body["block_threshold"] == 90


def test_hook_result_duplicate_also_returns_block():
    # 기존 Analysis 가 존재(duplicate)해도 응답에 block / block_threshold 필드가 포함되고,
    # 기존 레코드 score 기준으로 block_threshold 판정을 수행해야 함
    mock_db = MagicMock()
    mock_config = MagicMock()
    mock_config.hook_token = "tok-dup"
    mock_config.block_threshold = 80  # 기존 score=50 → block=True 기대
    mock_repo = MagicMock()
    mock_repo.id = 55

    call_count = {"n": 0}

    def _first_side_effect():
        idx = call_count["n"]
        call_count["n"] += 1
        return {0: mock_config, 1: mock_repo}.get(idx)

    mock_db.query.return_value.filter.return_value.first.side_effect = _first_side_effect

    # 기존 Analysis 존재 → score=50
    existing = MagicMock()
    existing.id = 777
    existing.score = 50
    existing.grade = "D"
    mock_db.query.return_value.filter_by.return_value.first.return_value = existing

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.post("/api/hook/result", json={
            "repo": "owner/repo",
            "token": "tok-dup",
            "commit_sha": "sha_dup",
            "commit_message": "feat: duplicate",
            "ai_result": _AI_RESULT,
        })

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "duplicate"
    assert body["score"] == 50
    assert body["analysis_id"] == 777
    assert body["block"] is True
    assert body["block_threshold"] == 80
    mock_db.add.assert_not_called()
