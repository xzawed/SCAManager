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
    # 🔴 `try/except/else + pytest.fail` 을 쓰지 않는다 — CodeQL 이 `pytest.fail` 을 `NoReturn`
    #    으로 모델링하지 않아 `formatted` 를 미할당 가능으로 보고 `py/uninitialized-local-variable`
    #    을 낸다(testing.md 가 기록한 함정 · 이 파일 초판이 실제로 3건 발화시켰다).
    #    `pytest.raises` 는 예외 부재를 스스로 실패시키므로 else 분기 자체가 불필요하다.
    with pytest.raises(config_mod.SettingsValidationError) as excinfo:
        config_mod.build_settings(database_url=_BAD_URL, _env_file=None)
    formatted = "".join(traceback.format_exception(excinfo.value))
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
    with pytest.raises(config_mod.SettingsValidationError) as excinfo:
        config_mod.build_settings(database_url="sqlite:///x.db", session_secret=weak,
                                  _env_file=None)
    formatted = "".join(traceback.format_exception(excinfo.value))
    assert weak not in formatted
    assert "session_secret" in formatted


# ── 모델 레벨 검증 실패 (Grok claim-review 019fed 가 BROKEN 으로 반증한 축) ──────
#
# 🔴 **내 1차 수정이 원래 결함보다 나빴다.** `model_validator(mode="after")` 실패는
# `loc=()` 라 `"(root)"` 로 정규화되는데, 그건 이름 힌트에 안 걸려 **비민감**으로 분류됐고,
# 비민감 분기는 `err["input"]` 을 그대로 인쇄한다. 그런데 모델 레벨 오류의 `input` 은
# **모델 전체 dict** 다 — 즉 `telegram_bot_token`·`anthropic_api_key`·`session_secret` 이
# 한꺼번에 찍힌다(실측). 필드 하나를 가리려다 전부를 흘리는 형태였다.
#
# 규칙: **`input` 이 매핑이거나 loc 이 모델 전체를 가리키면 값은 절대 인쇄하지 않는다.**


def test_model_level_validation_failure_does_not_dump_every_secret():
    """🔴 모델 레벨 실패에서 형제 필드의 시크릿이 새지 않는가 (실경로 · 실제 시크릿 값)."""
    with pytest.raises(config_mod.SettingsValidationError) as excinfo:
        config_mod.build_settings(
            _env_file=None,
            database_url="sqlite:///x.db",
            telegram_bot_token="LEAKTOKEN",
            telegram_chat_id="1",
            anthropic_api_key="LEAKKEY",
            session_secret="S" * 40,
            merge_retry_max_backoff_seconds=1,
            merge_retry_initial_backoff_seconds=60,
        )
    formatted = "".join(traceback.format_exception(excinfo.value))
    assert "LEAKTOKEN" not in formatted, "모델 레벨 오류가 형제 필드 시크릿을 통째로 인쇄한다"
    assert "LEAKKEY" not in formatted
    assert "merge_retry" in formatted, "무엇이 문제인지는 남아야 한다"


def test_optional_str_credential_is_still_treated_as_sensitive():
    """🔴 `str | None` 로 선언된 자격증명 필드가 비민감으로 새지 않는가.

    타입 판정을 `annotation is not str` 로만 하면 Optional 계열이 전부 빠져나간다.
    """
    for name in ("github_token", "openai_api_key", "smtp_pass", "smtp_user"):
        assert config_mod._is_sensitive_field(name), f"{name} 이 비민감으로 분류됐다"


def test_root_loc_is_classified_sensitive():
    """🔴 축 1 을 **따로** 관측한다 — 통합 테스트만으로는 어느 방어가 잡았는지 알 수 없다.

    `_sanitize_validation_error` 에는 방어가 둘이다: (a) `(root)` loc 을 민감으로 보는 규칙과
    (b) `input` 이 매핑이면 인쇄하지 않는 규칙. 통합 테스트는 **둘 중 하나만 살아도** 통과하므로,
    한쪽이 죽어도 초록이다. 그래서 (a)를 직접 단언한다.

    🔴 **(b)는 현재 도달하지 않는다** — `(root)` 규칙이 먼저 이겨 민감 분기로 가기 때문이다.
    지우지 않고 두는 이유는 *비-root loc 에 매핑 input 이 실리는* 미래 형태의 backstop 이기
    때문이고, **지금 테스트로 관측되지 않는다는 사실을 여기 적어 둔다**(guards.md — 관측되지
    않는 중복을 검증된 것으로 오인하지 않기 위해).
    """
    assert config_mod._is_sensitive_field("(root)")
    assert config_mod._is_sensitive_field("")


# ── 기동 실패 메시지의 **실용성** (사용자 지시 2026-08-10) ────────────────────
#
# 🔴 1차 설계는 민감 필드의 값을 **통째로** 지웠다. 그건 안전하지만 진단을 망친다:
# `database_url` 이 왜 틀렸는지(호스트 오타? 포트? 스킴?) 알 수 없어 운영자가 손댈 곳을
# 못 찾는다. 사용자 지시 — *"기동 실패가 후속작업이나 품질에 악영향을 준다면 개선하라"*.
#
# 개선: 필드 종류를 나눈다.
#   · URL 계열   → **자격증명만 마스킹**하고 나머지는 보여준다(이미 검증된 `_redact` 재사용)
#   · 불투명 시크릿 → 값 대신 **길이**만 (빈 값 vs 오타를 구분하게 해 준다)
#   · 그 외      → 값 그대로
# 이러면 R77 의 실제 트리거(`[::1:5432` 처럼 닫히지 않은 대괄호)가 **눈에 보인다**.


def test_url_field_shows_everything_except_the_credential():
    """🔴 URL 은 통째로 지우지 않는다 — 문제 지점이 보여야 고칠 수 있다."""
    message = config_mod._sanitize_validation_error(_raise_validation_error())
    assert _SECRET not in message, "비밀번호는 여전히 가려져야 한다"
    assert "appuser" in message, "사용자명은 진단에 필요하다"
    assert "[::1:5432" in message, "🔴 실제 결함(닫히지 않은 대괄호)이 보여야 한다"
    assert "***" in message, "가려진 자리는 표시돼야 한다"


def test_opaque_secret_shows_length_not_value():
    """불투명 시크릿은 값 대신 길이 — 빈 값 오설정과 오타를 구분하게 해 준다."""
    weak = "short-but-real-secret-x"
    try:
        config_mod.build_settings(database_url="sqlite:///x.db", session_secret=weak,
                                  _env_file=None)
    except config_mod.SettingsValidationError as exc:
        message = str(exc)
    else:
        pytest.fail("32자 미만인데 통과했다")
    assert weak not in message
    assert str(len(weak)) in message, "길이조차 없으면 빈 값인지 오타인지 구분 불가"


def test_non_credential_url_field_is_shown_intact():
    """🔴 `app_base_url` 은 자격증명이 아니다 — 가리면 순손실이다."""
    shown = config_mod._render_error_value("app_base_url", "https://example.up.railway.app")
    assert shown == "https://example.up.railway.app"
