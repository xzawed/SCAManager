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
from src.constants import COMMIT_MSG_MAX, AI_REVIEW_MAX, TEST_COVERAGE_MAX

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


def test_verify_non_ascii_token_returns_404_not_500():
    """비-ASCII hook_token 입력이 TypeError(→500) 가 아닌 404(불일치)를 반환해야 한다 (Task 9 P1 #10).

    compare_digest(str, str) 의 비-ASCII TypeError 로 인증 엔드포인트가 500 을 내던 결함 —
    secure_str_compare(UTF-8 bytes) 로 정상 불일치(404) 처리.
    """
    mock_db = MagicMock()
    mock_config = MagicMock()
    mock_config.hook_token = "correct-token"
    mock_db.query.return_value.filter.return_value.first.return_value = mock_config

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.get("/api/hook/verify", params={"repo": "owner/repo", "token": "비ASCII토큰🔑"})

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


def test_hook_result_concurrent_insert_race_returns_duplicate_not_500():
    """동시 동일 SHA hook 이 existing 체크(L197)를 통과한 뒤 DB unique 제약(uq_analyses_repo_sha)에
    막히면, 500 대신 duplicate 응답을 반환해야 한다 (#5 멱등성 — analysis_repo.save_new race-safe).

    수정 전: db.add+db.commit() 가 IntegrityError 를 미처리로 전파 → 500.
    수정 후: save_new 가 rollback+재조회로 흡수 → (existing, created=False) → duplicate 응답.
    """
    from sqlalchemy.exc import IntegrityError
    mock_db = MagicMock()
    mock_config = MagicMock(); mock_config.hook_token = "race-token"
    mock_repo = MagicMock(); mock_repo.id = 9

    call_count = {"n": 0}

    def _first_side_effect():
        idx = call_count["n"]; call_count["n"] += 1
        return {0: mock_config, 1: mock_repo}.get(idx)

    mock_db.query.return_value.filter.return_value.first.side_effect = _first_side_effect
    # filter_by().first(): (1) L197 existing 체크 → None, (2) save_new find_by_sha(race 후) → existing
    existing = MagicMock(id=555, score=88, grade="B")
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [None, existing]
    mock_db.add = MagicMock()
    mock_db.commit = MagicMock(side_effect=IntegrityError("INSERT", {}, Exception("duplicate key")))
    mock_db.rollback = MagicMock()
    mock_db.refresh = MagicMock()

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.post("/api/hook/result", json={
            "repo": "owner/repo",
            "token": "race-token",
            "commit_sha": "raceSHA123",
            "commit_message": "feat: race",
            "ai_result": _AI_RESULT,
        })

    assert r.status_code == 200, f"동시 insert race 가 500 을 유발하면 안 됨: {r.status_code}"
    body = r.json()
    assert body["status"] == "duplicate"
    assert body["analysis_id"] == 555
    assert body["score"] == 88
    mock_db.rollback.assert_called_once()


# ------------------------------------------------------------------
# AI 점수 클램핑 회귀 가드 — CLI hook 의 raw 점수가 범위(0~MAX)를 벗어나면
# breakdown 카테고리 점수가 cap 을 초과/미만해 정합성이 깨지는 결함 방지.
# ai_review.py 의 max(0, min(MAX, ...)) 패턴을 hook.py 가 동일하게 미러하는지 검증.
# AI score clamping regression guard — out-of-range raw scores from the CLI hook
# must not push breakdown category scores past their caps (or below 0), mirroring
# the max(0, min(MAX, ...)) clamp pattern already used in ai_review.py.
# ------------------------------------------------------------------

def _post_hook_capturing(ai_result: dict) -> list:
    """주어진 ai_result 로 /api/hook/result 를 호출하고 저장된 Analysis 객체 목록을 반환.
    Call /api/hook/result with the given ai_result and return captured Analysis objects."""
    mock_db = MagicMock()
    mock_config = MagicMock()
    mock_config.hook_token = "clamp-token"
    mock_repo = MagicMock()
    mock_repo.id = 99

    call_count = {"n": 0}

    def _first_side_effect():
        idx = call_count["n"]
        call_count["n"] += 1
        return {0: mock_config, 1: mock_repo}.get(idx)

    mock_db.query.return_value.filter.return_value.first.side_effect = _first_side_effect
    mock_db.query.return_value.filter_by.return_value.first.return_value = None  # no duplicate
    saved: list = []
    mock_db.add.side_effect = lambda obj: saved.append(obj)

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.post("/api/hook/result", json={
            "repo": "owner/repo",
            "token": "clamp-token",
            "commit_sha": "shaclamp",
            "commit_message": "feat: clamp",
            "ai_result": ai_result,
        })
    assert r.status_code == 200
    return saved


def test_hook_result_clamps_overrange_scores():
    # 범위 초과 raw 점수(commit=999/direction=50/test=99, 모든 키 존재 → success)는
    # 상한(20/20/10)으로 클램프되어 breakdown 카테고리 점수가 cap 을 넘지 않는다.
    saved = _post_hook_capturing({
        **_AI_RESULT,
        "commit_message_score": 999,
        "direction_score": 50,
        "test_score": 99,
    })
    assert len(saved) == 1
    breakdown = saved[0].result["breakdown"]
    # 클램프 후 raw 20/20/10 → 스케일 결과가 정확히 각 cap 과 동일
    # After clamp raw 20/20/10 → scaled exactly to each cap
    assert breakdown["commit_message"] == COMMIT_MSG_MAX
    assert breakdown["ai_review"] == AI_REVIEW_MAX
    assert breakdown["test_coverage"] == TEST_COVERAGE_MAX


def test_hook_result_negative_scores_clamped_to_zero():
    # 음수 raw 점수는 하한 0 으로 클램프되어 breakdown 카테고리 점수가 음수가 되지 않는다.
    # Negative raw scores clamp to a 0 floor so breakdown categories never go negative.
    saved = _post_hook_capturing({
        **_AI_RESULT,
        "commit_message_score": -5,
        "direction_score": -1,
        "test_score": -3,
    })
    assert len(saved) == 1
    breakdown = saved[0].result["breakdown"]
    assert breakdown["commit_message"] == 0
    assert breakdown["ai_review"] == 0
    assert breakdown["test_coverage"] == 0


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
# T-1: Bearer 헤더 인증 3시나리오 회귀 가드 (사이클 113 P0-A)
# T-1: Bearer header auth 3-scenario regression guard (Cycle 113 P0-A)
# ------------------------------------------------------------------

def test_verify_with_bearer_header_only():
    """Authorization: Bearer 헤더만으로 verify 성공 → 200 {"status": "active"}.
    Verify succeeds with only an Authorization: Bearer header — returns 200 {"status": "active"}.

    사이클 113 P0-A 회귀 가드: hook.py 가 Authorization 헤더에서 bearer_token을 파싱 후
    effective_token으로 사용하는지 검증한다.
    Cycle 113 P0-A regression guard: verifies hook.py parses bearer_token from
    Authorization header and uses it as effective_token.
    """
    mock_db = MagicMock()
    mock_config = MagicMock()
    mock_config.hook_token = "bearer-only-token"
    mock_db.query.return_value.filter.return_value.first.return_value = mock_config

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        with patch("src.api.hook.repo_config_repo.find_by_full_name", return_value=mock_config):
            r = client.get(
                "/api/hook/verify",
                params={"repo": "owner/repo"},
                headers={"Authorization": "Bearer bearer-only-token"},
            )

    assert r.status_code == 200
    assert r.json()["status"] == "active"


def test_verify_bearer_takes_priority_over_query_param():
    """Bearer와 ?token= 동시 존재 시 Bearer가 우선 처리되어 올바른 token으로 인증된다.
    When both Bearer header and ?token= query param are present, Bearer takes priority.

    사이클 113 P0-A 회귀 가드: effective_token = bearer_token or token 우선순위 검증.
    Cycle 113 P0-A regression guard: verifies effective_token = bearer_token or token priority.
    """
    mock_db = MagicMock()
    mock_config = MagicMock()
    # hook_token이 Bearer 값과 일치 → Bearer 우선 사용 시 200
    # hook_token matches Bearer value → 200 when Bearer takes priority
    mock_config.hook_token = "correct-bearer-token"

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        with patch("src.api.hook.repo_config_repo.find_by_full_name", return_value=mock_config):
            r = client.get(
                "/api/hook/verify",
                params={"repo": "owner/repo", "token": "wrong-query-token"},
                headers={"Authorization": "Bearer correct-bearer-token"},
            )

    # Bearer 값이 hook_token과 일치하므로 200 반환 (query param 무시)
    # Bearer matches hook_token → 200 (query param ignored)
    assert r.status_code == 200
    assert r.json()["status"] == "active"


def test_verify_no_token_returns_401():
    """Authorization 헤더도 ?token= 쿼리도 없으면 401 반환.
    Returns 401 when neither Authorization header nor ?token= query param is present.

    사이클 113 P0-A 회귀 가드: effective_token이 None이면 HTTPException(401) 발화 검증.
    Cycle 113 P0-A regression guard: verifies HTTPException(401) raised when effective_token is None.
    """
    mock_db = MagicMock()

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.get(
            "/api/hook/verify",
            params={"repo": "owner/repo"},
            # Authorization 헤더 없음, token 쿼리 없음
            # No Authorization header, no token query param
        )

    assert r.status_code == 401


# ------------------------------------------------------------------
# 비숫자 점수 필드 방어 회귀 가드 — CLI hook 의 점수 필드가 비숫자 타입
# ("abc"/None/list 등)으로 오염돼도 int() ValueError/TypeError 가 500 으로
# 새지 않고, default 폴백 + ai_review_status="parse_error" 분류로 graceful
# 하게 처리되어 200 을 반환하는지 검증한다 (정합성 감사 area=gate P2).
# Non-numeric score field defense regression guard — a CLI hook score field
# polluted with a non-numeric type ("abc"/None/list) must NOT leak an int()
# ValueError/TypeError as a 500. Instead it should fall back to defaults,
# classify ai_review_status="parse_error", and still return 200 (integrity
# audit area=gate P2).
# ------------------------------------------------------------------

def _post_hook_non_numeric(ai_result: dict):
    """주어진 (비정상 가능) ai_result 로 /api/hook/result 를 호출하고 (response, saved) 반환.
    Call /api/hook/result with the given (possibly malformed) ai_result and
    return (response, saved) — status 단언을 호출자에게 맡겨 Red(500) 신호를 보존한다.

    참고: _post_hook_capturing 헬퍼는 내부에서 status_code == 200 을 단언하므로,
    현재 500 동작을 그 assert 가 가려 버린다. 따라서 여기서는 직접 client.post 후
    status 단언을 호출자에게 위임한다 (test_hook_result_partial_ai_result_marks_parse_error
    의 mock 설정을 정확히 미러).
    Note: _post_hook_capturing asserts status == 200 internally, which would mask
    the current 500. So this helper leaves the status assertion to the caller,
    mirroring the mock setup of test_hook_result_partial_ai_result_marks_parse_error.
    """
    mock_db = MagicMock()
    mock_config = MagicMock()
    mock_config.hook_token = "coerce-token"
    mock_repo = MagicMock()
    mock_repo.id = 77

    call_count = {"n": 0}

    def _first_side_effect():
        idx = call_count["n"]
        call_count["n"] += 1
        return {0: mock_config, 1: mock_repo}.get(idx)

    mock_db.query.return_value.filter.return_value.first.side_effect = _first_side_effect
    mock_db.query.return_value.filter_by.return_value.first.return_value = None  # no duplicate
    saved: list = []
    mock_db.add.side_effect = lambda obj: saved.append(obj)

    with patch("src.api.hook.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.post("/api/hook/result", json={
            "repo": "owner/repo",
            "token": "coerce-token",
            "commit_sha": "shacoerce",
            "commit_message": "feat: coerce",
            "ai_result": ai_result,
        })
    return r, saved


def test_hook_result_non_numeric_score_returns_parse_error_not_500():
    # 점수 필드 중 하나가 비숫자 문자열("abc")이면 int() ValueError 가 500 으로 새면 안 되고,
    # default 폴백 + ai_review_status="parse_error" 로 graceful 처리되어 200 을 반환해야 한다.
    # When one score field is a non-numeric string ("abc"), the int() ValueError must
    # not leak as a 500; it must fall back to defaults, mark ai_review_status="parse_error",
    # and return 200.
    r, saved = _post_hook_non_numeric({**_AI_RESULT, "commit_message_score": "abc"})

    # 핵심 단언: 현재 구현은 int("abc") → ValueError → 500 (= Red). 가드 추가 후 200.
    # Core assertion: current impl raises ValueError → 500 (= Red). After the guard, 200.
    assert r.status_code == 200
    # 비숫자 점수는 parse_error 로 분류되어 fallback 경고 배너가 노출 가능해야 한다.
    # A non-numeric score must be classified as parse_error so the fallback banner can show.
    assert len(saved) == 1
    assert saved[0].result["ai_review_status"] == "parse_error"
    # 오염된 필드가 default 로 폴백돼 breakdown 카테고리 점수가 정상 범위(0~cap)여야 한다.
    # The polluted field falls back to a default so the breakdown category stays in range (0~cap).
    breakdown = saved[0].result["breakdown"]
    assert 0 <= breakdown["commit_message"] <= COMMIT_MSG_MAX
    assert 0 <= breakdown["ai_review"] <= AI_REVIEW_MAX
    assert 0 <= breakdown["test_coverage"] <= TEST_COVERAGE_MAX


def test_hook_result_none_score_value_returns_parse_error():
    # 점수 필드 값이 None 이면 int(None) → TypeError 가 500 으로 새면 안 되고,
    # default 폴백 + ai_review_status="parse_error" 로 graceful 처리되어 200 을 반환해야 한다.
    # When a score field value is None, int(None) raises TypeError which must not leak as a 500;
    # it must fall back to defaults, mark ai_review_status="parse_error", and return 200.
    r, saved = _post_hook_non_numeric({**_AI_RESULT, "test_score": None})

    # 핵심 단언: 현재 구현은 int(None) → TypeError → 500 (= Red). 가드 추가 후 200.
    # Core assertion: current impl raises TypeError → 500 (= Red). After the guard, 200.
    assert r.status_code == 200
    assert len(saved) == 1
    assert saved[0].result["ai_review_status"] == "parse_error"
    breakdown = saved[0].result["breakdown"]
    assert 0 <= breakdown["test_coverage"] <= TEST_COVERAGE_MAX


def test_coerce_raw_score_absorbs_infinity_overflow():
    # int(float('inf')) → OverflowError. 운영에서 JSON 비표준 리터럴 Infinity 는 json.loads 가
    # float('inf') 로 파싱하므로 핸들러가 이를 만난다 (적대적 self-verify 발견). _coerce_raw_score 가
    # OverflowError 를 흡수해 default 폴백 + ok=False 를 반환해야 한다 (parse_error 분류 → 200).
    # 헬퍼를 직접 단위 검증한다 — TestClient json= 직렬화는 inf 를 환경에 따라 거부하므로
    # (CI httpx: "Out of range float values are not JSON compliant") HTTP 경로 테스트는 fragile.
    # int(float('inf')) raises OverflowError. In production json.loads parses the non-standard literal
    # Infinity to float('inf'), so the handler hits it (found by adversarial self-verify). _coerce_raw_score
    # must absorb the OverflowError → default fallback + ok=False (parse_error → 200). Verified at the helper
    # level directly — TestClient json= serialization rejects inf env-dependently, so an HTTP-path test is fragile.
    from src.api.hook import _coerce_raw_score  # pylint: disable=import-outside-toplevel
    assert _coerce_raw_score(float("inf"), 20, 17) == (17, False)
    assert _coerce_raw_score(float("-inf"), 10, 7) == (7, False)
    # NaN 은 int(float('nan')) → ValueError 로 흡수됨 (기존 except 로 안전) / NaN absorbed via ValueError
    assert _coerce_raw_score(float("nan"), 20, 17) == (17, False)
    # 정상 정수·숫자문자열은 ok=True 로 통과 (동등성) / valid int & numeric string stay ok=True
    assert _coerce_raw_score(18, 20, 17) == (18, True)
    assert _coerce_raw_score("15", 20, 17) == (15, True)
