"""SessionStart 훅 배선 가드 — 남은 카운터가 기계적으로 실행되는지.

🔴 이 가드는 산문이 아니라 **실행 기전**(.claude/settings.json 의 SessionStart 훅 엔트리)을 단언한다.

🔴 **단, "settings.json 에 적혀 있다 = 실행된다" 는 아니다** (2026-07-31 정정). 초판은 정확히 그
   추론을 했고, 그래서 command 를 `echo '...'` 로 바꿔도 통과했다 — 파일만 옮긴 산문 grep 이었다.
   지금은 `tests/unit/scripts/_wiring_shape` 가 **명령어가 인터프리터인지** 구조 판정한다.
   여전히 잡지 못하는 것: 인터프리터가 그 환경에 실제로 존재하는지(런타임 사실).
This asserts the execution mechanism, but "present in settings.json" is NOT "executed" — the first
version made that inference and an `echo` decoy passed. It still cannot prove the interpreter exists.
"""
import json
from pathlib import Path

import pytest

from tests.unit.scripts._wiring_shape import any_invokes

_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _ROOT / ".claude" / "settings.json"

# 세션 시작 시 기계 실행돼야 하는 카운터 — 스크립트 경로로 식별.
# Counters that must run mechanically at session start, identified by script path.
_REQUIRED = (
    "scripts/check_main_red.py",
    "scripts/check_precommit_installed.py",
)


def _settings():
    return json.loads(_SETTINGS.read_text(encoding="utf-8"))


def session_start_commands(settings):
    """SessionStart 훅에 등록된 command 문자열 전부.
    Every command string registered under the SessionStart hook."""
    out = []
    for entry in settings.get("hooks", {}).get("SessionStart", []):
        for hook in entry.get("hooks", []):
            cmd = hook.get("command", "")
            if hook.get("args"):
                cmd = f"{cmd} {' '.join(hook['args'])}"
            out.append(cmd)
    return out


# --- 탐지기 자체 검증 (긍정/부정 통제) ------------------------------------


def test_extractor_finds_commands():
    """🔴 긍정 통제 — 추출기가 실제로 command 를 찾는다."""
    fake = {"hooks": {"SessionStart": [{"matcher": "startup", "hooks": [
        {"type": "command", "command": "python x.py"}]}]}}
    assert session_start_commands(fake) == ["python x.py"]


def test_extractor_handles_args_form():
    """`args` 분리 형식도 한 문자열로 합쳐 인식 (스키마 변형 대응)."""
    fake = {"hooks": {"SessionStart": [{"matcher": "startup", "hooks": [
        {"type": "command", "command": "python", "args": ["scripts/a.py"]}]}]}}
    assert session_start_commands(fake) == ["python scripts/a.py"]


def test_extractor_empty_when_no_session_start():
    """🔴 부정 통제 — SessionStart 미배선이면 빈 목록(=아래 불변식이 fail 해야 함)."""
    assert session_start_commands({"hooks": {"PreToolUse": []}}) == []


# --- 저장소 불변식 ----------------------------------------------------------


def test_settings_json_is_valid():
    """settings.json 이 유효한 JSON — 깨지면 모든 훅이 조용히 죽는다."""
    assert isinstance(_settings(), dict)


@pytest.mark.parametrize("script", _REQUIRED)
def test_counter_wired_to_session_start(script):
    """🔴 카운터가 SessionStart 훅에서 **실제로 실행**되는가 — 경로 문자열 존재가 아니라.

    🔴 2026-07-31 봉인: 이전 판은 `any(script in c for c in commands)` substring 이라,
    command 를 `echo 'skipping scripts/check_main_red.py'` 로 중성화해도 통과했다
    (실측 뮤테이션 GROK-20260731-1 — 지정 경로 498건 전부 green, red 0). 즉 이 파일의
    docstring 이 주장한 "실행 기전 단언" 은 **CLAUDE.md 의 산문 grep 을 settings.json 의 산문
    grep 으로 옮긴 것**에 불과했다. 판정을 `_wiring_shape.any_invokes` 로 넘긴다.
    Was a substring test: neutering the command into an `echo` kept all 498 tests green.
    """
    commands = session_start_commands(_settings())
    assert any_invokes(commands, script), (
        f"{script} 가 SessionStart 훅에서 실행되지 않는다 — 실행이 인지 의존으로 회귀한다.\n"
        f"현재 배선: {commands}\n"
        "해결 / Fix: .claude/settings.json 의 hooks.SessionStart 에 **인터프리터 호출** 추가\n"
        "  (예: `python scripts/x.py` — 경로만 언급하는 echo/주석은 배선이 아니다)."
    )


def test_session_start_matcher_covers_startup():
    """새 세션(startup)에서 반드시 발화 — resume 만 걸면 신규 세션이 누락된다."""
    entries = _settings().get("hooks", {}).get("SessionStart", [])
    assert any("startup" in e.get("matcher", "") for e in entries), (
        "SessionStart matcher 에 startup 없음 — 신규 세션에서 카운터가 안 돈다"
    )


def test_wired_scripts_exist_on_disk():
    """배선된 스크립트가 실재 — 경로 오타 시 훅이 무음 실패한다.

    #1094 형('가드가 무력한데 green') 차단: 배선 문자열만 맞고 파일이 없으면 실행은 0 이다.
    """
    for script in _REQUIRED:
        assert (_ROOT / script).is_file(), f"배선된 스크립트 부재: {script}"
