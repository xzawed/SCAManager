"""tests/test_api_auth.py — API 키 인증 의존성(_check_api_key) 단위 테스트.

보안 수정 대상:
  - 타이밍 공격 방지: secure_str_compare(hmac.compare_digest) 사용 여부
  - 🔴 API_KEY 미설정 시 **기본 fail-closed(503)** — 명시적 API_AUTH_DISABLED=1 opt-out 시에만 통과
    (감사 ①: 이전엔 http/빈 APP_BASE_URL 이면 무인증 통과 → 오설정 cross-tenant 노출 위험)
  - API_AUTH_DISABLED=1 통과 시 logger.warning 경고 출력

테스트 대상 엔드포인트: 미니멀 FastAPI 앱 + GET /protected
  → require_api_key 의존성만 격리 테스트
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")

from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.auth import require_api_key

# 격리된 미니멀 앱 — src.main 전체 import 없이 require_api_key만 테스트
_app = FastAPI()


@_app.get("/protected", dependencies=[require_api_key])
def _protected():
    return {"data": "ok"}


client = TestClient(_app, raise_server_exceptions=False)

_TEST_KEY = "s3cr3t-k3y"


# ---------------------------------------------------------------------------
# 테스트 1: 올바른 API 키로 요청 시 200 반환
# Test 1: correct API key → 200 response.
# ---------------------------------------------------------------------------

def test_api_key_valid_passes(monkeypatch):
    # settings.api_key = TEST_KEY 환경에서 동일 키 헤더 전송 → 200
    monkeypatch.setattr("src.api.auth.settings.api_key", _TEST_KEY)
    r = client.get("/protected", headers={"X-API-Key": _TEST_KEY})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# 테스트 2: 잘못된 API 키로 요청 시 401 반환
# Test 2: wrong API key → 401 response.
# ---------------------------------------------------------------------------

def test_api_key_invalid_returns_401(monkeypatch):
    # settings.api_key = TEST_KEY 환경에서 틀린 키 전송 → 401
    monkeypatch.setattr("src.api.auth.settings.api_key", _TEST_KEY)
    r = client.get("/protected", headers={"X-API-Key": "wrong-key"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid or missing API key"


# ---------------------------------------------------------------------------
# 테스트 3: API_KEY 설정됐는데 헤더 없으면 401
# Test 3: API_KEY configured but header absent → 401.
# ---------------------------------------------------------------------------

def test_api_key_missing_when_required_returns_401(monkeypatch):
    # settings.api_key = TEST_KEY 환경에서 X-API-Key 헤더 없이 요청 → 401
    monkeypatch.setattr("src.api.auth.settings.api_key", _TEST_KEY)
    r = client.get("/protected")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# 테스트 4 (감사 ① — fail-closed 기본): API_KEY 미설정 + API_AUTH_DISABLED 미설정 → 503
# Test 4 (audit ① — fail-closed default): API_KEY unset + API_AUTH_DISABLED unset → 503.
# ---------------------------------------------------------------------------

def test_api_key_empty_default_fail_closed_503(monkeypatch):
    # settings.api_key = "" + api_auth_disabled=False → 모든 요청 차단(503) — 명시적 opt-out 없으면 안전
    monkeypatch.setattr("src.api.auth.settings.api_key", "")
    monkeypatch.setattr("src.api.auth.settings.api_auth_disabled", False)
    r = client.get("/protected")
    assert r.status_code == 503


def test_api_key_empty_fail_closed_regardless_of_base_url(monkeypatch):
    # 🔴 감사 ① 회귀 가드: 이전엔 http/빈 APP_BASE_URL 이면 무인증 통과(fail-open).
    # 이제 app_base_url 값과 무관하게 api_auth_disabled=False 면 503 (http 오판 노출 차단).
    monkeypatch.setattr("src.api.auth.settings.api_key", "")
    monkeypatch.setattr("src.api.auth.settings.api_auth_disabled", False)
    for base_url in ("http://localhost:8000", "https://scamanager.example.com", ""):
        monkeypatch.setattr("src.api.auth.settings.app_base_url", base_url)
        assert client.get("/protected").status_code == 503


# ---------------------------------------------------------------------------
# 테스트 5: 타이밍 공격 안전성 — secure_str_compare 호출 여부 직접 검증
# ---------------------------------------------------------------------------

def test_api_key_uses_safe_comparison(monkeypatch):
    # _check_api_key 내부에서 timing-safe 비교(secure_str_compare)가 호출되는지 확인.
    # Task 9 P1 #9/#10: hmac.compare_digest 직접 호출 → secure_str_compare 단일 헬퍼로 통일
    # (내부 UTF-8 bytes compare_digest — 비-ASCII TypeError 방지 + timing-safe).
    mock_cmp = MagicMock(return_value=True)
    monkeypatch.setattr("src.api.auth.settings.api_key", _TEST_KEY)
    monkeypatch.setattr("src.api.auth.secure_str_compare", mock_cmp)
    r = client.get("/protected", headers={"X-API-Key": _TEST_KEY})
    # secure_str_compare 가 실제로 한 번 이상 호출됐어야 함 (timing-safe 비교 사용)
    mock_cmp.assert_called()
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# 테스트 6 (fail-closed): API_KEY 미설정 + opt-out 없음 → 키를 보내도 503
# Test 6 (fail-closed): API_KEY unset + no opt-out → 503 even with a provided key.
# ---------------------------------------------------------------------------

def test_api_key_empty_default_ignores_provided_key_503(monkeypatch):
    monkeypatch.setattr("src.api.auth.settings.api_key", "")
    monkeypatch.setattr("src.api.auth.settings.api_auth_disabled", False)
    r = client.get("/protected", headers={"X-API-Key": "any-random-key"})
    assert r.status_code == 503


# ---------------------------------------------------------------------------
# 테스트 7 (명시 opt-out): API_AUTH_DISABLED=1 → 키 없어도 200 + 경고
# Test 7 (explicit opt-out): API_AUTH_DISABLED=1 → keyless 200 + warning.
# ---------------------------------------------------------------------------

def test_api_auth_disabled_allows_access(monkeypatch):
    # 명시적 개발 opt-out — api_key 미설정이라도 통과(개발 편의)
    monkeypatch.setattr("src.api.auth.settings.api_key", "")
    monkeypatch.setattr("src.api.auth.settings.api_auth_disabled", True)
    r = client.get("/protected")
    assert r.status_code == 200


def test_api_auth_disabled_logs_warning(monkeypatch):
    # API_AUTH_DISABLED=1 통과 시 logger.warning(무인증 경고) 호출돼야 함
    # 🔴 모듈은 파일 상단에서 from-import 로 이미 들어옴 — 모듈 객체 별칭 import 를 추가하지 않고
    # string-path 패치로 통일해 CodeQL py/import-and-import-from(#520) 이중 import 를 회피.
    monkeypatch.setattr("src.api.auth.settings.api_key", "")
    monkeypatch.setattr("src.api.auth.settings.api_auth_disabled", True)
    mock_logger = MagicMock()
    monkeypatch.setattr("src.api.auth.logger", mock_logger, raising=False)
    client.get("/protected")
    mock_logger.warning.assert_called()


# ---------------------------------------------------------------------------
# 테스트 8: API_KEY 설정 시 api_auth_disabled 무관 — 키 검증 경로 우선 (opt-out 우회 불가)
# Test 8: with API_KEY set, api_auth_disabled is irrelevant — key validation path wins.
# ---------------------------------------------------------------------------

def test_api_key_set_overrides_disabled_flag(monkeypatch):
    # api_key 설정 + api_auth_disabled=True 라도 잘못된 키는 401 (opt-out 으로 우회 불가)
    monkeypatch.setattr("src.api.auth.settings.api_key", _TEST_KEY)
    monkeypatch.setattr("src.api.auth.settings.api_auth_disabled", True)
    r = client.get("/protected", headers={"X-API-Key": "wrong-key"})
    assert r.status_code == 401
