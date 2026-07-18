"""railway.toml cron 무음 실패 가드 — 셸 확장 + HTTP 오류 전파 (회고 2026-07-19 P0).

P0 실측: cron 5종 전부 API 키를 **작은따옴표**로 감싸 `$INTERNAL_CRON_API_KEY` 가 셸 확장되지
않았다(리터럴 문자열이 헤더로 전송 → 401). 게다가 `curl -s` 에 `-f` 가 없어 HTTP 401 에도
exit 0 → Railway 는 성공으로 기록. **전면 실패가 무음**이었다.
P0: all 5 crons wrapped the API key in single quotes (no shell expansion → literal header → 401),
and `curl -s` without `-f` exits 0 on HTTP errors, so total failure was silent.

🔴 이 가드는 두 조건을 **독립적으로** 강제한다 — 확장(따옴표)과 전파(-f)는 별개 실패 모드다.
   따옴표만 고치면 401 이 200 이 되지만, 나중에 키가 만료돼도 다시 무음이 된다.
Both conditions are enforced independently — expansion and propagation are distinct failure modes.
Fixing quoting alone still leaves silent failure when the key later expires.
"""
import re
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_RAILWAY_TOML = _ROOT / "railway.toml"
_API_KEY_VAR = "$INTERNAL_CRON_API_KEY"


def expands_api_key(command):
    """API 키 변수가 셸 확장되는 위치에 있으면 True.

    POSIX 셸에서 작은따옴표 안의 `$VAR` 는 확장되지 않는다. 변수 앞의 작은따옴표 개수가
    홀수면 = 열린 작은따옴표 안 = 미확장.
    True when the API-key variable sits where the shell expands it. An odd number of
    preceding single quotes means it is inside an open single-quoted span (no expansion).
    """
    idx = command.find(_API_KEY_VAR)
    if idx < 0:
        return False
    return command[:idx].count("'") % 2 == 0


def fails_on_http_error(command):
    """curl 이 HTTP 4xx/5xx 에서 non-zero 로 종료하면 True (`-f` 또는 `--fail`).

    묶음 플래그(`-fsS`)도 인식한다. `--fail-with-body` 등 long 형도 허용.
    True when curl exits non-zero on HTTP errors. Recognizes bundled short flags (-fsS)
    and long forms (--fail, --fail-with-body).
    """
    if re.search(r"--fail(-with-body)?\b", command):
        return True
    # 짧은 플래그 묶음 — `-` 뒤 `--` 가 아닌 문자열에 f 포함 / bundled short flags containing f
    return any(
        "f" in token[1:]
        for token in re.findall(r"(?<!\S)-[A-Za-z]+", command)
    )


def _cron_commands():
    cfg = tomllib.loads(_RAILWAY_TOML.read_text(encoding="utf-8"))
    return [c["command"] for c in cfg.get("deploy", {}).get("cronJobs", [])]


# --- 탐지기 자체 검증 (긍정/부정 통제) ------------------------------------
# Detector self-checks — the retro's top finding was that the new guards lacked these.


def test_detects_single_quoted_key_as_unexpanded():
    """🔴 긍정 통제 — P0 원본 형태를 미확장으로 탐지해야 한다.
    Positive control: the exact P0 form must be detected as non-expanding."""
    bad = "curl -s -X POST -H 'X-API-Key: $INTERNAL_CRON_API_KEY' http://localhost:$PORT/x"
    assert expands_api_key(bad) is False


def test_double_quoted_key_expands():
    """큰따옴표 안의 변수는 확장된다."""
    good = 'curl -fsS -X POST -H "X-API-Key: $INTERNAL_CRON_API_KEY" http://localhost:$PORT/x'
    assert expands_api_key(good) is True


def test_unquoted_key_expands():
    """따옴표 없는 변수도 확장된다."""
    assert expands_api_key("curl -f -H X-API-Key:$INTERNAL_CRON_API_KEY http://x") is True


def test_missing_key_var_is_not_expanding():
    """변수 자체가 없으면 확장 아님 — 헤더 누락도 결함이다."""
    assert expands_api_key("curl -fsS http://localhost/x") is False


def test_detects_missing_fail_flag():
    """🔴 긍정 통제 — `-s` 단독(P0 원본)은 HTTP 오류를 전파하지 않는다."""
    assert fails_on_http_error("curl -s -X POST http://x") is False


def test_bundled_fail_flag_recognized():
    """묶음 플래그 `-fsS` 를 인식한다."""
    assert fails_on_http_error("curl -fsS -X POST http://x") is True


def test_long_fail_flag_recognized():
    """long 형 `--fail` 을 인식한다."""
    assert fails_on_http_error("curl --fail -s http://x") is True


def test_long_flag_with_f_letter_not_miscounted():
    """`--form` 같은 long 옵션의 f 를 `-f` 로 오인하지 않는다 (부정 통제)."""
    assert fails_on_http_error("curl -s --form a=b http://x") is False


# --- 저장소 불변식 ----------------------------------------------------------


def test_cron_jobs_exist():
    """cron 정의가 실재 — 파싱 실패로 아래 검사가 공허해지는 것을 막는다.
    Guards against a vacuous pass if parsing silently yields an empty list."""
    assert len(_cron_commands()) >= 5


@pytest.mark.parametrize("command", _cron_commands())
def test_cron_api_key_is_shell_expanded(command):
    """🔴 모든 cron 이 API 키를 셸 확장 위치에 둔다 — 작은따옴표 감싸기 = 401 전면 실패."""
    assert expands_api_key(command), (
        f"API 키가 셸 확장되지 않는다(작은따옴표 안) → 리터럴 전송 → 401:\n  {command}\n"
        "해결 / Fix: TOML 리터럴 문자열 + 셸 큰따옴표 — "
        "command = 'curl -fsS -H \"X-API-Key: $INTERNAL_CRON_API_KEY\" ...'"
    )


@pytest.mark.parametrize("command", _cron_commands())
def test_cron_propagates_http_errors(command):
    """🔴 모든 cron 이 HTTP 오류에서 non-zero 종료 — 없으면 실패가 무음으로 성공 기록된다."""
    assert fails_on_http_error(command), (
        f"curl 이 HTTP 오류를 전파하지 않는다(-f 부재) → 401/503 에도 exit 0:\n  {command}\n"
        "해결 / Fix: `-s` → `-fsS` (fail on error, silent, but show the error message)"
    )
