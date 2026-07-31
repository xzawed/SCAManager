"""훅 명령의 **인터프리터가 실제로 Python 을 실행하는가** — exit 49 회귀 차단.

## 사고 (2026-07-31 회고 P0-5 · P0-7)

`#1243` 이 고친 창 최대 P0: Claude Code 훅 6종이 bare `python` 으로 배선돼 있었고, Windows 에서
`python` 은 **Microsoft Store 스텁**이라 아무것도 실행하지 않고 **exit 49** 를 낸다. 보안 훅
`block_credential_dump` 를 포함한 6종이 **한 번도 실행된 적이 없었다**.

`#1243` 은 command 를 `PY=$(command -v py …); $PY` 폴백으로 고쳤으나 **회귀 가드를 0건 동반**했다
(정책 4 정면 위반). 실측: `settings.json` 을 bare `python` 으로 되돌리는 뮤테이션에서 배선 가드
16건이 **전부 green**. 즉 봉인했다고 선언한 결함이 언제든 무음 회귀 가능했다.

## 이 파일이 닫는 축 (그리고 닫지 못하는 축)

- ✅ **인터프리터 생존** — 명령의 인터프리터 부분이 실제로 Python 을 돌리는가(exit 49 차단).
- ❌ 훅 본문의 정확성 · 조건부 skip · Claude Code 가 실제로 이 명령을 호출하는가.

🔴 `_wiring_shape` 술어(#1248)는 **명령 형태**만 본다 — `python X` 는 형태상 정당하므로
bare `python` 회귀를 구별하지 못한다. 그 축을 여기서 **실행 관측**으로 닫는다.

Probes that each hook command's interpreter can actually run Python. The wiring predicate only
checks command *shape*, so a revert to bare `python` (a Store stub returning 49) looks valid to it.
"""
import json
import shutil
import subprocess  # nosec B404
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _ROOT / ".claude" / "settings.json"

# 훅 명령은 POSIX 셸 문법(`$(...)`·`;`·`||`)을 쓰므로 셸을 통해 평가해야 한다.
# Hook commands use POSIX shell syntax, so they must be evaluated through a shell.
_SHELL = shutil.which("sh") or shutil.which("bash")

_MARKER = "HOOK_INTERPRETER_ALIVE"


def hook_commands() -> list[tuple[str, str]]:
    """settings.json 의 모든 훅 (이벤트, 명령) — 세 이벤트 전부.
    Every (event, command) pair registered under any hook event."""
    settings = json.loads(_SETTINGS.read_text(encoding="utf-8"))
    out = []
    for event, groups in settings.get("hooks", {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                cmd = hook.get("command", "")
                if cmd:
                    out.append((event, cmd))
    return out


def interpreter_prefix(command: str) -> str:
    """명령에서 **스크립트 경로 앞부분**(= 인터프리터 호출)을 떼어낸다.

    `PY=$(…); $PY scripts/x.py` → `PY=$(…); $PY`
    스크립트 경로를 못 찾으면 빈 문자열(호출자가 실패로 처리).
    Strip everything from the script path onward, leaving the interpreter invocation.
    """
    for token in command.split():
        if token.endswith(".py"):
            return command[: command.index(token)].rstrip()
    return ""


def _probe(prefix: str) -> subprocess.CompletedProcess:
    """인터프리터 접두사로 사소한 파이썬 한 줄을 실행해 본다."""
    script = f'{prefix} -c "print(\'{_MARKER}\')"'
    return subprocess.run(  # nosec B603
        [_SHELL, "-c", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=60, check=False, cwd=str(_ROOT),
    )


# ── 탐지기 자체 검증 (긍정/부정 통제) ────────────────────────────────────
# Detector self-check — the point of these is that the probe is not vacuous.


def test_prefix_extraction_strips_the_script_path():
    """🔴 긍정 통제 — 추출기가 인터프리터 부분만 정확히 떼어낸다."""
    cmd = "PY=$(command -v py >/dev/null 2>&1 && echo 'py -3' || echo python3); $PY scripts/x.py"
    assert interpreter_prefix(cmd) == (
        "PY=$(command -v py >/dev/null 2>&1 && echo 'py -3' || echo python3); $PY"
    )


def test_prefix_extraction_reports_nothing_when_no_script():
    """🔴 부정 통제 — 스크립트 경로가 없으면 빈 문자열(아래 단언이 fail 해야 한다)."""
    assert interpreter_prefix("echo hello") == ""


@pytest.mark.skipif(_SHELL is None, reason="POSIX 셸 부재 — 훅 자체가 실행 불가한 환경")
def test_probe_detects_a_dead_interpreter():
    """🔴 **프로브가 공허하지 않은지** — 죽은 인터프리터를 실제로 잡는가.

    이 단언이 없으면 아래 실행 테스트가 "무엇을 해도 통과" 일 수 있다. 존재하지 않는 실행 파일로
    프로브해 non-zero 를 확인한다.
    A dead interpreter must fail the probe; otherwise the liveness assertions below prove nothing.
    """
    result = _probe("definitely_not_a_real_python_zzz")
    assert result.returncode != 0
    assert _MARKER not in result.stdout


# ── 저장소 불변식 ────────────────────────────────────────────────────────


def test_settings_declares_hooks():
    """대조군 — 훅이 하나도 없으면 아래 parametrize 가 공허하다."""
    assert len(hook_commands()) >= 4, f"훅 탐색이 {len(hook_commands())}개 — 전제 붕괴"


@pytest.mark.skipif(_SHELL is None, reason="POSIX 셸 부재 — 훅 자체가 실행 불가한 환경")
@pytest.mark.parametrize(("event", "command"), hook_commands())
def test_hook_interpreter_actually_runs_python(event, command):
    """🔴 훅 명령의 인터프리터가 **실제로 Python 을 실행**해야 한다.

    bare `python` 으로 되돌리면 Windows 에서 Store 스텁이 **exit 49** 를 내고 훅 6종이
    조용히 죽는다(2026-07-31 회고 P0-5·P0-7 의 원인). 형태 검사로는 구별할 수 없어
    여기서 실행으로 관측한다.
    Reverting to bare `python` yields a Store stub (exit 49) on Windows; shape checks can't see it.
    """
    prefix = interpreter_prefix(command)
    assert prefix, f"[{event}] 명령에서 스크립트 경로를 못 찾았다: {command!r}"

    result = _probe(prefix)
    assert result.returncode == 0 and _MARKER in result.stdout, (
        f"[{event}] 훅의 인터프리터가 Python 을 실행하지 못한다 — 이 훅은 무동작이다.\n"
        f"  명령 / command   : {command}\n"
        f"  인터프리터 / prefix: {prefix}\n"
        f"  exit={result.returncode} stdout={result.stdout.strip()!r} "
        f"stderr={result.stderr.strip()[:200]!r}\n"
        "  🔴 exit 49 = Windows Microsoft Store 스텁(아무것도 실행하지 않음).\n"
        "  해결 / Fix: `PY=$(command -v py >/dev/null 2>&1 && echo 'py -3' || echo python3); $PY` 형태 사용."
    )
