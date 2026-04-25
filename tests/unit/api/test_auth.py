"""tests/test_api_auth.py — API 키 인증 의존성(_check_api_key) 단위 테스트.

P0-1 보안 수정 대상:
  - 타이밍 공격 방지: hmac.compare_digest 사용 여부
  - API_KEY 미설정(빈 문자열) 시 open access 동작 유지
  - API_KEY 미설정 시 logger.warning 경고 출력

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
# 테스트 4: API_KEY 미설정(빈 문자열)이면 키 없어도 200 (기존 동작 유지)
# Test 4: API_KEY not set (empty string) → 200 even without a key (preserve existing behaviour).
# ---------------------------------------------------------------------------

def test_api_key_empty_string_allows_access(monkeypatch):
    # settings.api_key = "" 환경에서 헤더 없어도 통과 → 200 (open access)
    monkeypatch.setattr("src.api.auth.settings.api_key", "")
    r = client.get("/protected")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# 테스트 5: 타이밍 공격 안전성 — hmac.compare_digest 호출 여부 직접 검증
# 현재 코드(!=)는 hmac.compare_digest를 import/호출하지 않으므로 FAIL(Red).
# ---------------------------------------------------------------------------

def test_api_key_uses_safe_comparison(monkeypatch):
    # _check_api_key 내부에서 hmac.compare_digest가 호출되는지 확인.
    # 현재 코드(!=)는 hmac을 import하지 않으므로 이 테스트는 FAIL해야 함(Red).
    # patch 전략: hmac 모듈 자체를 src.api.auth 네임스페이스에 주입 후 compare_digest 감시.
    import hmac as _hmac
    mock_hmac = MagicMock(wraps=_hmac)
    mock_hmac.compare_digest = MagicMock(return_value=True)
    monkeypatch.setattr("src.api.auth.settings.api_key", _TEST_KEY)
    # src.api.auth 모듈에 hmac 심기 (현재 코드엔 없으므로 setattr로 삽입)
    import src.api.auth as _auth_mod
    monkeypatch.setattr(_auth_mod, "hmac", mock_hmac, raising=False)
    r = client.get("/protected", headers={"X-API-Key": _TEST_KEY})
    # hmac.compare_digest가 실제로 한 번 이상 호출됐어야 함
    mock_hmac.compare_digest.assert_called()
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# 테스트 6 (보조): API_KEY 미설정 시 어떤 키를 보내도 200 (open access)
# ---------------------------------------------------------------------------

def test_api_key_empty_string_ignores_provided_key(monkeypatch):
    # settings.api_key = "" 환경에서는 아무 키를 보내도 통과
    monkeypatch.setattr("src.api.auth.settings.api_key", "")
    r = client.get("/protected", headers={"X-API-Key": "any-random-key"})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# 테스트 7: API_KEY 미설정 시 logger.warning 호출 여부
# 현재 코드에는 logger가 없으므로 FAIL(Red).
# ---------------------------------------------------------------------------

def test_api_key_empty_logs_warning(monkeypatch):
    # settings.api_key = "" 환경에서 요청 시 logger.warning이 호출돼야 함.
    # 현재 코드에 logger가 없으므로 이 테스트는 FAIL해야 함(Red).
    import src.api.auth as _auth_mod
    monkeypatch.setattr("src.api.auth.settings.api_key", "")
    mock_logger = MagicMock()
    monkeypatch.setattr(_auth_mod, "logger", mock_logger, raising=False)
    client.get("/protected")
    mock_logger.warning.assert_called()
