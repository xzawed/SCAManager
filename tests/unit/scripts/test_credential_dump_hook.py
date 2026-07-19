"""credential 값 stdout 덤프 차단 훅 — 배선 + 판정 가드 (회고 2026-07-19 P0).

사고: 2026-07-19 세션에서 변수 **이름만** 확인할 의도로 아래를 실행했으나, `CRON` 패턴이
값까지 매칭해 credential 이 평문으로 대화 기록에 남았다.
Incident: a name-only lookup matched a value too, leaking a credential into the transcript.

    railway variables --service SCAManager --kv | grep -iE "...|CRON"

2차 회고(168 에이전트)가 P0 로 확정한 것은 유출 자체가 아니라 **재발 방지책이 산문뿐**이라는
점이다 — owed 원장 표 셀 + 로컬 메모리. "credential 유출 벡터(Bash stdout)에 훅 커버리지 0",
"인지 의존 산문 5회차, 자기 진단 1커밋 후 재생산".
The retro's P0 was not the leak but that the only mitigation was prose: zero hook coverage on the
Bash-stdout exfiltration vector, the 5th consecutive cognition-dependent mitigation.

🔴 그래서 이 가드는 산문을 읽지 않는다. (1) `.claude/settings.json` 을 **JSON 으로 파싱**해
   PreToolUse/Bash 배선을 단언하고, (2) 훅을 **subprocess 로 실제 실행**해 stdin→stdout 판정을
   확인한다. 문서 문자열 grep 은 #1094 형('가드가 무력한데 green')을 재생산하므로 금지.
This asserts the execution mechanism: settings.json wiring parsed as JSON, plus a real subprocess
run of the hook. Asserting prose would reproduce the very defect the retro flagged.

🔴 이 파일의 명령 상수는 **명령 문자열일 뿐 실제 키 값을 담지 않는다**. 상수명도 중립 명명
   (`_CMD_*`) 을 쓴다 — #1109 에서 테스트 상수명이 CodeQL `py/clear-text-logging-sensitive-data`
   alert 2건을 자초한 전례.
Command constants hold commands only, never real key material; neutral `_CMD_*` naming avoids the
self-inflicted CodeQL alerts of #1109.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _ROOT / ".claude" / "settings.json"
_HOOK = _ROOT / ".claude" / "hooks" / "block_credential_dump.py"

# 훅이 배선돼야 하는 도구 — Bash stdout 이 유출 벡터.
# The tool the hook must gate; Bash stdout is the exfiltration vector.
_TOOL = "Bash"

# --- 명령 상수 (실제 키 값 없음 — 명령 문자열만) ------------------------------

# 🔴 실제 사고 명령 원문. `CRON` 이 이름뿐 아니라 값까지 매칭한 그 형태.
# The verbatim incident command: `CRON` matched values, not just names.
_CMD_INCIDENT = (
    'railway variables --service SCAManager --kv '
    '| grep -iE "SCHEDULER|ENVIRONMENT|LOG_LEVEL|CRON"'
)

# 안전 관용구 — 이름만 추출한 뒤 필터. 훅이 이걸 막으면 사용자가 훅을 끄게 된다.
# The safe idiom; blocking it would push the operator to disable the hook.
_CMD_NAMES_ONLY = "railway variables --kv | cut -d= -f1 | grep -i CRON"


def _payload(command, tool_name=_TOOL):
    return json.dumps({"tool_name": tool_name, "tool_input": {"command": command}})


def _run_hook(command, tool_name=_TOOL):
    """훅을 배선된 방식대로 실제 실행 — import 우회 없이 stdin/stdout 계약 확인.

    Run the hook exactly as wired (subprocess + stdin JSON), not via import.
    """
    assert _HOOK.is_file(), (
        f"훅 파일 부재: {_HOOK.relative_to(_ROOT)}\n"
        "해결 / Fix: PreToolUse(Bash) 훅을 신설하라. 배선 문자열만 맞고 파일이 없으면 "
        "실행 횟수는 0 이다(#1094 형 'green 인데 무력')."
    )
    return subprocess.run(
        [sys.executable, str(_HOOK)],
        input=_payload(command, tool_name).encode("utf-8"),
        capture_output=True,
        timeout=20,
        check=False,
        cwd=str(_ROOT),
    )


def _decide(command, tool_name=_TOOL):
    """(permissionDecision, reason) 반환. 통과(무출력)면 (None, "").

    Returns the decision pair; (None, "") means the hook stayed silent = allow.
    """
    proc = _run_hook(command, tool_name)
    stdout = proc.stdout.decode("utf-8", errors="replace").strip()
    stderr = proc.stderr.decode("utf-8", errors="replace").strip()
    # 훅은 무슨 일이 있어도 exit 0 — 비정상 종료는 harness 를 막거나 무음 실패한다.
    # The hook must always exit 0; a crash either blocks the harness or fails silently.
    assert proc.returncode == 0, (
        f"훅이 exit {proc.returncode} 로 종료 — 항상 exit 0 이어야 한다.\n"
        f"stderr: {stderr}"
    )
    if not stdout:
        return None, ""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"훅 stdout 이 JSON 이 아니다 — harness 가 판정을 읽지 못한다.\n"
            f"stdout: {stdout!r}"
        ) from exc
    spec = data.get("hookSpecificOutput", {})
    assert spec.get("hookEventName") == "PreToolUse", (
        f"hookEventName 이 'PreToolUse' 가 아니다 — 판정이 무시된다. 실제: {spec!r}"
    )
    return spec.get("permissionDecision"), spec.get("permissionDecisionReason", "")


# --- 1·3. 차단 대상 (credential 값이 stdout 으로 나오는 명령) -----------------

_BLOCKED = [
    # 🔴 실제 사고 명령 — 이 한 줄이 이 PR 의 존재 이유.
    pytest.param(_CMD_INCIDENT, id="incident-railway-variables-grep"),
    pytest.param("railway variables --service SCAManager --kv", id="railway-variables-kv"),
    pytest.param("railway variables", id="railway-variables-bare"),
    pytest.param("printenv", id="printenv-bare"),
    pytest.param("printenv | sort", id="printenv-piped"),
    pytest.param("cat .env", id="cat-dotenv"),
    pytest.param("cat D:/Source/SCAManager/.env", id="cat-dotenv-abspath"),
    pytest.param("type .env", id="type-dotenv-windows"),
]


@pytest.mark.parametrize("command", _BLOCKED)
def test_credential_dump_is_denied(command):
    """🔴 credential 값을 stdout 으로 쏟는 명령은 deny — 사고 명령 원문 포함."""
    decision, _ = _decide(command)
    assert decision == "deny", (
        f"차단되지 않음: {command!r}\n"
        "이 명령은 credential 값을 대화 기록에 평문으로 남긴다(2026-07-19 사고 재현).\n"
        "해결 / Fix: .claude/hooks/block_credential_dump.py 의 차단 패턴에 추가."
    )


# --- 2·4·5. 통과 대상 (false-positive 방어) -----------------------------------

_ALLOWED = [
    # 안전 관용구 3변형 — 이름만 추출. 막히면 훅이 곧 비활성화된다.
    pytest.param(_CMD_NAMES_ONLY, id="safe-idiom-cut-d-eq"),
    pytest.param("railway variables --kv | cut -d'=' -f1", id="safe-idiom-cut-quoted-single"),
    pytest.param('railway variables --kv | cut -d"=" -f1', id="safe-idiom-cut-quoted-double"),
    pytest.param("printenv | cut -d= -f1", id="safe-idiom-printenv-names"),
    # 쓰기 작업 — 값을 넣는 것이지 꺼내는 것이 아니다.
    pytest.param("railway variables --set FOO=bar", id="write-set"),
    pytest.param("railway variables --set SCHEDULER_ENABLED=1", id="write-set-scheduler"),
    # 🔴 소스에서 CRON 을 grep 하는 정상 작업 — 이게 막히면 일상 작업이 마비된다.
    pytest.param('grep -rn "CRON" src/', id="grep-source-cron"),
    pytest.param('grep -rniE "SCHEDULER|CRON" src/', id="grep-source-alternation"),
    # 무관 명령 일반.
    pytest.param("git status", id="git-status"),
    pytest.param("pytest tests/unit", id="pytest-unit"),
    pytest.param("railway logs", id="railway-logs"),
    pytest.param("railway status", id="railway-status"),
    pytest.param("cat README.md", id="cat-readme"),
    pytest.param("ls -la .claude/hooks/", id="ls-hooks"),
    # ⚠️ 사양 판단: `.env.example` 은 저장소에 커밋된 값 없는 템플릿이고
    # CLAUDE.md 핵심 명령(`cp .env.example .env`)에 등장한다 → 통과 대상으로 본다.
    # Spec call: .env.example is a committed, value-free template — allow it.
    pytest.param("cat .env.example", id="cat-dotenv-example"),
]


@pytest.mark.parametrize("command", _ALLOWED)
def test_benign_command_is_not_denied(command):
    """정상 명령은 통과 — 특히 소스 grep 과 이름만 추출 관용구(과잉 차단 봉인)."""
    decision, reason = _decide(command)
    assert decision != "deny", (
        f"오탐 차단: {command!r} 는 credential 값을 노출하지 않는다.\n"
        f"훅 사유: {reason}\n"
        "해결 / Fix: 허용 예외(cut -d= -f1 / --set / 비대상 명령)를 넓혀라."
    )


# --- 6. 비-Bash 도구는 무조건 통과 -------------------------------------------


@pytest.mark.parametrize("tool_name", ["Read", "Edit", "Write", "Grep", "Glob"])
def test_non_bash_tool_always_passes(tool_name):
    """Bash 외 도구는 판정 대상 아님 — 오작동 시 전 도구가 마비된다."""
    decision, _ = _decide(_CMD_INCIDENT, tool_name=tool_name)
    assert decision != "deny", (
        f"{tool_name} 도구가 차단됐다 — 이 훅은 Bash stdout 만 대상으로 한다."
    )


# --- 7. 차단 메시지 유용성 ----------------------------------------------------


def test_deny_reason_teaches_the_safe_idiom():
    """🔴 deny 사유가 안전 대안을 제시 — 대안 없는 차단은 우회를 부른다."""
    decision, reason = _decide(_CMD_INCIDENT)
    assert decision == "deny"
    assert "cut -d= -f1" in reason, (
        "차단 사유에 안전 관용구(`cut -d= -f1`)가 없다.\n"
        f"현재 사유: {reason}\n"
        "대안을 알려주지 않는 차단은 사용자가 훅을 끄게 만든다."
    )


def test_deny_output_is_ascii_safe():
    """훅 stdout 이 ASCII — Windows cp949 콘솔에서 UnicodeEncodeError 로 무음 실패 방지.

    선례: `check_edit_allowed.py` 가 `ensure_ascii=True` 를 쓰는 이유, bilingual 훅 cp949 버그.
    """
    proc = _run_hook(_CMD_INCIDENT)
    try:
        proc.stdout.decode("ascii")
    except UnicodeDecodeError as exc:
        raise AssertionError(
            "훅 stdout 에 non-ASCII 바이트 — cp949 콘솔에서 훅이 죽어 무음 통과한다.\n"
            "해결 / Fix: json.dumps(..., ensure_ascii=True)."
        ) from exc


def test_malformed_stdin_does_not_crash():
    """깨진 stdin 에도 exit 0 — 훅이 죽으면 모든 Bash 호출이 막히거나 무음 통과한다."""
    proc = subprocess.run(
        [sys.executable, str(_HOOK)],
        input=b"not json at all",
        capture_output=True,
        timeout=20,
        check=False,
        cwd=str(_ROOT),
    )
    assert proc.returncode == 0, (
        f"깨진 stdin 에 exit {proc.returncode} — 훅은 항상 exit 0 이어야 한다."
    )


# --- 8. 배선 단언 (JSON 파싱 — 산문 grep 금지) --------------------------------


def _settings():
    return json.loads(_SETTINGS.read_text(encoding="utf-8"))


def pretooluse_commands_for(settings, tool):
    """지정 도구에 매칭되는 PreToolUse 훅 command 전부.

    matcher 는 `Write|Edit|MultiEdit` 같은 정규식 alternation 이므로 토큰 분해 후 대조.
    Matchers are regex alternations, so split on `|` before comparing.
    """
    out = []
    for entry in settings.get("hooks", {}).get("PreToolUse", []):
        tokens = [t.strip() for t in entry.get("matcher", "").split("|")]
        if tool not in tokens:
            continue
        for hook in entry.get("hooks", []):
            cmd = hook.get("command", "")
            if hook.get("args"):
                cmd = f"{cmd} {' '.join(hook['args'])}"
            out.append(cmd)
    return out


def test_extractor_finds_bash_group():
    """🔴 긍정 통제 — 추출기가 Bash 그룹의 command 를 실제로 찾는다."""
    fake = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
        {"type": "command", "command": "python x.py"}]}]}}
    assert pretooluse_commands_for(fake, "Bash") == ["python x.py"]


def test_extractor_handles_alternation_and_args():
    """alternation matcher + `args` 분리 형식도 인식 (스키마 변형 대응)."""
    fake = {"hooks": {"PreToolUse": [{"matcher": "Bash|BashOutput", "hooks": [
        {"type": "command", "command": "python", "args": [".claude/hooks/h.py"]}]}]}}
    assert pretooluse_commands_for(fake, "Bash") == ["python .claude/hooks/h.py"]


def test_extractor_ignores_other_tool_groups():
    """🔴 부정 통제 — Write/Edit 그룹은 Bash 로 집계되지 않는다(공허 통과 차단)."""
    fake = {"hooks": {"PreToolUse": [{"matcher": "Write|Edit", "hooks": [
        {"type": "command", "command": "python other.py"}]}]}}
    assert pretooluse_commands_for(fake, "Bash") == []


def test_settings_json_is_valid():
    """settings.json 이 유효한 JSON — 깨지면 모든 훅이 조용히 죽는다."""
    assert isinstance(_settings(), dict)


def test_hook_wired_to_pretooluse_bash():
    """🔴 훅이 PreToolUse/Bash 에 배선 — 산문 안내가 아니라 기계 집행면."""
    commands = pretooluse_commands_for(_settings(), _TOOL)
    assert any("block_credential_dump.py" in c for c in commands), (
        "block_credential_dump.py 가 PreToolUse(Bash) 에 미배선 — 차단이 인지 의존으로 회귀한다.\n"
        f"현재 Bash 배선: {commands}\n"
        "해결 / Fix: .claude/settings.json 의 hooks.PreToolUse 에 matcher 'Bash' 그룹 추가."
    )


def test_wired_hook_exists_on_disk():
    """배선된 훅이 실재 — 경로 오타 시 훅이 무음 실패한다(#1094 형 차단)."""
    assert _HOOK.is_file(), f"배선된 훅 파일 부재: {_HOOK.relative_to(_ROOT)}"


def test_existing_edit_hooks_survive():
    """기존 Write/Edit 훅 배선이 유지 — Bash 그룹 추가가 기존 보호를 덮어쓰지 않는다."""
    commands = pretooluse_commands_for(_settings(), "Write")
    assert any("check_edit_allowed.py" in c for c in commands), (
        "check_edit_allowed.py 배선이 사라졌다 — 모바일 환경 보호가 무력화된다."
    )
