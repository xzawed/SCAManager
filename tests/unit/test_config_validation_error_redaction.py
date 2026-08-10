"""설정 검증 실패가 자격증명을 인쇄하지 않는가 (backlog R77).

## 왜 이 축이 따로 필요한가 — 로그 필터가 **원리적으로** 닿지 못한다

`src/config.py` 는 모듈 최하단에서 `settings = Settings()` 를 실행한다. 즉 검증 실패는
**import 시점**에 일어나고, 그때는

  · `configure_logging()` 이 아직 안 불렸고(`src/main.py` 가 settings 를 먼저 import 한다),
  · 애초에 `LogRecord` 가 만들어지지 않는다(pydantic 이 예외를 던지고 파이썬이 stderr 로 인쇄).

그래서 `_RedactSecretsFilter`(계층 2)는 이 축을 **볼 수 없다**. R8 이 닫은 alembic 축
(excepthook)과도 다른 축이다 — 그쪽은 ConfigParser 보간, 이쪽은 pydantic 검증이다.

## 🔴 착수 전 반증 측정 — 원장에 적었던 처방이 틀렸다

R77 을 등재할 때 나는 *"validator 에서 값 없는 메시지로 재발생시키면 된다"* 고 적었다.
**측정해 보니 거짓이다** — pydantic v2 는 내 메시지와 **무관하게** `input_value=...` 를
덧붙인다:

    Value error, DATABASE_URL 형식이 올바르지 않습니다
      [type=value_error, input_value='postgresql://u:s3cr3tPW@[::1:5432/db', input_type=str]

그래서 통제 지점은 validator 가 아니라 **생성 지점**이다. `Settings()` 를 감싸 `ValidationError`
를 잡고, 민감 필드는 값을 빼고 나머지는 값을 남긴 메시지로 바꿔 던진다.

🔴 **`from None` 이 필수다** — `from exc` 로 체인하면 원본 `ValidationError` 가 트레이스백에
다시 인쇄돼 그대로 유출된다(실측 확인). 이 파일의 대조군이 그 축을 고정한다.
"""
from __future__ import annotations

import traceback

import pytest
from pydantic import ValidationError

import src.config as config_mod

# 🔴 모듈 속성으로 접근한다 — `tests/unit/test_config.py` 가 `importlib.reload(src.config)` 로
# 클래스 객체를 갈아끼우므로, 이 파일이 import 시점 참조를 붙들면 `isinstance` 가 **다른 클래스**를
# 비교하게 돼 조용히 실패한다(실측). 호출 시점에 모듈에서 꺼내면 항상 같은 세대를 본다.
# Resolve through the module: test_config reloads src.config, so import-time refs go stale.

_SECRET = "s3cr3tPW"   # 짧게 둔다 — 아래 주석의 절단 규칙 참조
# 닫히지 않은 `[` — 온프레미스 IPv6 지원 대상이라 현실적인 오타다. urlparse 가 ValueError 를 낸다.
_BAD_URL = f"postgresql://appuser:{_SECRET}@[::1:5432/scadb"


def _raise_validation_error() -> ValidationError:
    """실제 `Settings` 로 검증 실패를 만든다 (합성 모델이 아니라 실경로 — 불변식 2)."""
    with pytest.raises(ValidationError) as excinfo:
        config_mod.Settings(database_url=_BAD_URL, _env_file=None)
    return excinfo.value


def test_raw_pydantic_error_does_leak_the_password():
    """🔴 대조군 — 결함이 실재함을 증명한다. 이게 거짓이면 아래 봉인은 불필요해진 것이다.

    🔴 **두 축을 함께 본다 (2026-08-10 실측)**: `str(e)` 는 긴 값을 가운데를 잘라
    `'postgresql://appuser:s3c...-LEAKME@…'` 처럼 보여준다 — 즉 **길이에 따라** 노출이
    부분적일 수 있다. 반면 `e.errors()[0]["input"]` 은 **언제나 전문**이다.
    한 축만 단언하면 비밀번호 길이가 바뀌는 순간 이 대조군이 조용히 공허해진다.
    """
    exc = _raise_validation_error()
    assert _SECRET in str(exc), "짧은 비밀번호는 절단 없이 그대로 인쇄된다"
    assert _SECRET in str(exc.errors()[0].get("input")), (
        "errors()[].input 은 절단되지 않는다 — str(e) 만 가려서는 부족하다는 근거"
    )


def test_sanitized_message_hides_sensitive_values():
    """민감 필드(`*_url`·`*_secret`·`*_token`·`*_key`)는 값을 지운다."""
    message = config_mod._sanitize_validation_error(_raise_validation_error())
    assert _SECRET not in message
    assert "database_url" in message, "어느 필드가 문제인지는 남아야 고칠 수 있다"


def test_sanitized_message_keeps_non_sensitive_values():
    """🔴 과교정 대조군 — 전부 지우면 설정 오류를 아무도 못 고친다.

    민감하지 않은 필드는 입력값을 **남겨야** 진단이 된다.
    """
    with pytest.raises(ValidationError) as excinfo:
        config_mod.Settings(database_url="sqlite:///x.db", claude_review_max_tokens="abc", _env_file=None)
    message = config_mod._sanitize_validation_error(excinfo.value)
    assert "claude_review_max_tokens" in message
    assert "abc" in message, "무해한 필드의 입력값까지 지우면 진단 불가"


def test_build_settings_raises_without_the_value_anywhere_in_the_traceback():
    """🔴 배선 + `from None` 축 — **트레이스백 전문**에 값이 없어야 한다.

    `from exc` 로 체인하면 원본 ValidationError 가 traceback 에 다시 찍혀 유출된다(실측).
    문자열 단언이 아니라 실제 traceback 을 포맷해 검사한다.
    """
    try:
        config_mod.build_settings(database_url=_BAD_URL, _env_file=None)
    except config_mod.SettingsValidationError:
        formatted = traceback.format_exc()
    else:
        pytest.fail("검증 실패인데 예외가 나지 않았다")
    assert _SECRET not in formatted, (
        "트레이스백에 비밀번호가 남는다 — `from None` 이 빠졌거나 원본이 체인돼 있다"
    )
    assert "database_url" in formatted, "필드명까지 사라지면 운영자가 원인을 못 찾는다"


def test_build_settings_returns_settings_on_valid_input():
    """대조군 — 정상 입력에서는 그대로 `Settings` 를 돌려준다(래퍼가 기능을 바꾸지 않는다)."""
    built = config_mod.build_settings(database_url="sqlite:///x.db", _env_file=None)
    assert isinstance(built, config_mod.Settings)
    assert built.database_url == "sqlite:///x.db"


def test_session_secret_value_is_not_printed():
    """🔴 같은 기전으로 `SESSION_SECRET` 실값도 노출된다 — 같은 관문이 막아야 한다."""
    weak = "short-but-real-secret-x"          # 32자 미만 → validator 실패
    try:
        config_mod.build_settings(database_url="sqlite:///x.db", session_secret=weak, _env_file=None)
    except config_mod.SettingsValidationError:
        formatted = traceback.format_exc()
    else:
        pytest.fail("32자 미만 SESSION_SECRET 인데 통과했다")
    assert weak not in formatted
    assert "session_secret" in formatted
