"""SessionStart 훅 배선 가드 — 카운터 2종이 기계적으로 실행되는지 (회고 2026-07-19 P0/P1).

회고 확정: #1080 카덴스 카운터와 #1084 owed 원장이 **집행면에 배선되지 않아** 실행이 여전히
인지 의존이었다. 기존 배선 테스트는 `assert "check_retro_cadence.py" in CLAUDE.md` 즉 **산문
문자열 존재**만 단언해 그 문서-only 상태를 정답으로 고정하고 있었다("공허 단언" 확정 지적).
Retro: the counters were wired to no enforcement surface, so execution stayed cognition-dependent.
The prior guard asserted only that a prose string existed in CLAUDE.md, pinning the doc-only state.

🔴 이 가드는 산문이 아니라 **실행 기전**(.claude/settings.json 의 SessionStart 훅 엔트리)을 단언한다.
   settings.json 이 곧 실행 주체이므로, 여기의 배선을 단언하는 것은 실행을 단언하는 것과 같다.
This asserts the execution mechanism itself — settings.json IS what runs the scripts, so asserting
its wiring is asserting execution (unlike asserting prose in a markdown file).
"""
import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _ROOT / ".claude" / "settings.json"

# 세션 시작 시 기계 실행돼야 하는 카운터 — 스크립트 경로로 식별.
# Counters that must run mechanically at session start, identified by script path.
_REQUIRED = ("scripts/check_retro_cadence.py", "scripts/check_owed_verification.py")


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
    """🔴 카운터가 SessionStart 훅에 배선 — 문서 안내가 아니라 기계 실행."""
    commands = session_start_commands(_settings())
    assert any(script in c for c in commands), (
        f"{script} 가 SessionStart 훅에 미배선 — 실행이 인지 의존으로 회귀한다.\n"
        f"현재 배선: {commands}\n"
        "해결 / Fix: .claude/settings.json 의 hooks.SessionStart 항목에 command 추가."
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
