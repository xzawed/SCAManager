"""훅 밖 실행 경로 2꼴 — Monitor 도구 · AntiGravity 위임 (원장 #1940 «정할 것» 7 · 11-28 사용자 «둘 다 막기»).
Two execution paths that bypassed the hooks: the Monitor tool and AntiGravity delegation (ledger #1940 item 7).

- Monitor 는 셸 명령(`command`)을 받아 돌리지만 credential · 운영 판정 훅과 게시 전 검사의 matcher 밖이었다 — Bash 와 같은
  판정을 받는다(WebSocket 꼴은 명령이 없어 판정할 것이 없다).
- AntiGravity 위임(delegate_to_antigravity · start_ag_task · ag_session)은 agy 셸을 훅 밖에서 돌린다 — 계획 모드
  (`agyMode: "plan"`)이고 권한 건너뛰기가 아닐 때만 통과한다. agy 설정을 바꾸는 관리 동작(MCP 등록 · 동기화 · 원격 데몬 ·
  갱신)도 막는다. 상태 · 결과 · 산출물 읽기와 되돌리기 · 취소는 둔다.

훅은 배선된 방식대로 subprocess 로 돌린다 — 함수만 재면 main() 이 그 함수를 부르지 않아도 초록이다(«거짓 집행자»).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.unit.hooks.test_block_credential_dump import pretooluse_commands_for

_ROOT = Path(__file__).resolve().parents[3]
_HOOK = _ROOT / ".claude" / "hooks" / "block_credential_dump.py"
_SCAN = _ROOT / "scripts" / "scan_publish.py"
_SETTINGS = _ROOT / ".claude" / "settings.json"
_AG = "mcp__plugin_antigravity-delegate_antigravity-delegate__"


def _decision(script, payload, *args):
    """훅 하나를 배선대로 돌려 (permissionDecision 또는 None) / run one hook as wired."""
    proc = subprocess.run([sys.executable, str(script), *args], input=json.dumps(payload).encode("utf-8"),
                          capture_output=True, timeout=60, check=False, cwd=str(_ROOT))
    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out else None


def _monitor(command):
    return {"tool_name": "Monitor", "tool_input": {"command": command, "description": "watch", "timeout_ms": 60000}}


def _settings():
    return json.loads(_SETTINGS.read_text(encoding="utf-8"))


# --- 1. 배선 — 두 도구가 판정 훅에 닿는다 ------------------------------------------------------------


def test_the_credential_hook_is_wired_for_monitor_and_antigravity():
    """🔴 matcher 가 Monitor 와 AntiGravity 위임 도구를 덮는다 — 판정이 맞아도 배선이 없으면 실행 횟수 0 이다."""
    for tool in ("Monitor", _AG + "delegate_to_antigravity", _AG + "start_ag_task", _AG + "ag_session",
                 _AG + "ag_cli_admin"):
        commands = pretooluse_commands_for(_settings(), tool)
        assert any("block_credential_dump.py" in c for c in commands), f"{tool} 에 credential 훅 배선이 없다: {commands}"


def test_the_publish_scan_is_wired_for_monitor():
    """Monitor 로 도는 gh 도 공개 쓰기다 — 게시 전 검사가 Monitor 에도 붙는다. 거름(`if`) 없는 그 handler 는 Monitor 전용
    항목에만 있어야 한다 — 공용 항목에 두면 모든 셸 · MCP 호출마다 프로세스가 하나 더 뜬다."""
    commands = pretooluse_commands_for(_settings(), "Monitor")
    assert any("scan_publish.py --hook" in c for c in commands), commands
    unfiltered = [entry["matcher"] for entry in _settings()["hooks"]["PreToolUse"] for h in entry.get("hooks", [])
                  if "scan_publish.py" in h.get("command", "") and not h.get("if")]
    assert unfiltered == ["Monitor"], unfiltered


# --- 2. Monitor — Bash 와 같은 판정 ------------------------------------------------------------------

_MONITOR_DENIED = [
    pytest.param("cat .env", id="dotenv-read"),
    pytest.param("tail -f .env.local", id="dotenv-tail"),
    pytest.param("while true; do printenv; sleep 30; done", id="env-dump-loop"),
    pytest.param("railway variables --set A=1", id="production-variable-write"),
]
_MONITOR_ALLOWED = [
    pytest.param("until test -f build.log; do sleep 2; done", id="wait-for-file"),
    pytest.param("tail -f app.log | grep --line-buffered ERROR", id="log-tail"),
    pytest.param("gh pr checks 1942 --json name,bucket", id="gh-read"),
]


@pytest.mark.parametrize("command", _MONITOR_DENIED)
def test_monitor_gets_the_bash_verdict(command):
    """🔴 Monitor 의 셸 명령도 credential · 운영 판정을 받는다 — 같은 명령을 Bash 로 치면 막히는 꼴이다."""
    assert _decision(_HOOK, {"tool_name": "Bash", "tool_input": {"command": command}}) == "deny", "대조군(Bash)이 안 막혔다"
    assert _decision(_HOOK, _monitor(command)) == "deny", f"Monitor 로는 통과했다: {command!r}"


@pytest.mark.parametrize("command", _MONITOR_ALLOWED)
def test_monitor_keeps_honest_watches(command):
    """대조군 — 정직한 감시 명령은 Monitor 에서도 통과한다."""
    assert _decision(_HOOK, _monitor(command)) is None, command


def test_a_websocket_monitor_has_nothing_to_judge():
    """WebSocket 꼴(명령 없음)은 셸을 돌리지 않는다 — 통과."""
    payload = {"tool_name": "Monitor", "tool_input": {"ws": {"url": "wss://example.com/events"}, "description": "x",
                                                         "timeout_ms": 60000}}
    assert _decision(_HOOK, payload) is None


def test_the_publish_scan_judges_a_monitor_gh_post(tmp_path):
    """🔴 Monitor 로 올리는 gh 공개 쓰기도 본문을 잰다 — 꼴이 든 본문 파일은 막고, gh 가 없는 감시는 조용하다."""
    body = tmp_path / "body.md"
    body.write_text("contact " + "someone.private" + "@" + "mailhost.io\n", encoding="utf-8")
    posting = _monitor(f"gh issue comment 1 --body-file {body.as_posix()}")
    assert _decision(_SCAN, posting, "--hook") == "deny"
    # gh 가 없는 감시는 글자에 주소 꼴이 있어도 게시가 아니다 — 거름이 없으면 막혔다(뒤집기 대조군)
    watch = _monitor("tail -f app.log | grep --line-buffered " + "someone.private" + "@" + "mailhost.io")
    assert _decision(_SCAN, watch, "--hook") is None


# --- 3. AntiGravity — 계획 모드만 ---------------------------------------------------------------------

_RUNNERS = ("delegate_to_antigravity", "start_ag_task")
_BASE_INPUT = {"title": "claim review", "instructions": "Review the diff and list counterexamples."}


@pytest.mark.parametrize("tool", _RUNNERS)
def test_an_antigravity_run_in_plan_mode_passes(tool):
    assert _decision(_HOOK, {"tool_name": _AG + tool, "tool_input": {**_BASE_INPUT, "agyMode": "plan"}}) is None


@pytest.mark.parametrize("tool", _RUNNERS)
@pytest.mark.parametrize("extra", [
    pytest.param({}, id="mode-missing"),
    pytest.param({"agyMode": "auto"}, id="auto"),
    pytest.param({"agyMode": "accept-edits"}, id="accept-edits"),
    pytest.param({"agyMode": "plan", "dangerouslySkipPermissions": True}, id="plan-but-skip-permissions"),
    pytest.param({"agyMode": "Plan"}, id="mode-case-differs"),
])
def test_an_antigravity_run_outside_plan_mode_is_denied(tool, extra):
    """🔴 계획 모드가 아니거나 권한 건너뛰기면 막는다 — 모르는 값 · 빠진 값도 막는 쪽이다."""
    assert _decision(_HOOK, {"tool_name": _AG + tool, "tool_input": {**_BASE_INPUT, **extra}}) == "deny", extra


@pytest.mark.parametrize(("tool_input", "expected"), [
    pytest.param({"action": "start", "prompt": "x", "agyMode": "plan"}, None, id="session-start-plan"),
    pytest.param({"action": "send", "sessionId": "s1", "prompt": "x", "agyMode": "plan"}, None, id="session-send-plan"),
    pytest.param({"action": "start", "prompt": "x"}, "deny", id="session-start-default-mode"),
    pytest.param({"action": "send", "sessionId": "s1", "prompt": "x"}, "deny", id="session-send-without-mode"),
    pytest.param({"action": "list"}, None, id="session-list"),
    pytest.param({"action": "close", "sessionId": "s1"}, None, id="session-close"),
])
def test_an_antigravity_session_follows_the_same_rule(tool_input, expected):
    assert _decision(_HOOK, {"tool_name": _AG + "ag_session", "tool_input": tool_input}) == expected, tool_input


@pytest.mark.parametrize(("action", "expected"), [
    pytest.param("mcp_list", None, id="list"),
    pytest.param("remote_status", None, id="remote-status"),
    pytest.param("changelog", None, id="changelog"),
    pytest.param("mcp_add", "deny", id="mcp-add"),
    pytest.param("mcp_sync_from_claude", "deny", id="mcp-sync"),
    pytest.param("remote_start", "deny", id="remote-start"),
    pytest.param("update", "deny", id="update"),
    pytest.param("brand_new_action", "deny", id="unknown-action"),
])
def test_antigravity_admin_actions_that_change_agy_are_denied(action, expected):
    """agy 설정 · 데몬 · 바이너리를 바꾸는 관리 동작은 막고 읽기만 둔다 — 모르는 동작은 막는 쪽이다."""
    assert _decision(_HOOK, {"tool_name": _AG + "ag_cli_admin", "tool_input": {"action": action}}) == expected


# witness-corpus: 셸을 돌리지 않는 AntiGravity 도구 — 결과 · 상태 · 산출물 읽기와 취소 · 되돌리기 · 로그인(실행 도구 목록 밖)
_AG_QUIET_TOOLS = ["get_ag_job", "cancel_ag_job", "list_ag_artifacts", "list_ag_capabilities", "check_ag_environment",
                   "get_ag_usage", "ag_auth", "rollback_ag_task"]


@pytest.mark.parametrize("tool", _AG_QUIET_TOOLS)
def test_antigravity_status_tools_pass(tool):
    assert _decision(_HOOK, {"tool_name": _AG + tool, "tool_input": {}}) is None


# witness-corpus: AntiGravity 가 앞으로 도구로 낼 수 있는 기능 — 플러그인 스킬의 기능명(swarm · goal · boost · browser)에서 왔다(허용 목록 밖)
_AG_FUTURE_TOOLS = ["ag_swarm", "ag_goal", "ag_boost", "ag_browser"]


@pytest.mark.parametrize("tool", _AG_FUTURE_TOOLS)
def test_an_unknown_antigravity_tool_is_denied(tool):
    """🔴 플러그인이 새 도구를 더하면 셸을 도는지 모른다 — 계획 모드 인자가 있어도 막는 쪽이다(허용 목록이 닫혀 있다)."""
    assert _decision(_HOOK, {"tool_name": _AG + tool, "tool_input": {"agyMode": "plan"}}) == "deny"


def test_another_plugin_server_is_not_judged_here():
    """대조군 — AntiGravity 가 아닌 MCP 서버는 이 판정의 대상이 아니다(운영 MCP 판정만 그대로)."""
    assert _decision(_HOOK, {"tool_name": "mcp__claude_ai_Notion__notion-search", "tool_input": {}}) is None
