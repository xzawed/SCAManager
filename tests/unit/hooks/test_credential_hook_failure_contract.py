"""credential · 운영 접근 훅이 «판정하지 못한» 호출의 처리 계약 (회고 원장 #1917 M02 P1-7).

## 이 파일이 잠그는 것

1. 배선 — Bash · PowerShell · Railway · Supabase MCP 에 걸리는 이 훅 항목은 `onFailure: "block"` 이다. 훅이 시작하지
   못하거나 · 0/2 밖의 코드로 끝나거나 · 시간을 넘기거나 · 읽을 수 없는 출력을 내면 Claude Code 가 그 호출을 막는다.
   편집 훅(`check_edit_allowed.py`)은 그대로다(사용자 결정 R31 — 알리고 통과).
2. 판정 중 예외 · 객체가 아닌 입력 = «판정 불가» — 운영 · 자격 표지가 있는 호출은 deny, 없는 호출은 막지 않고
   에이전트(additionalContext)와 사람(systemMessage)에게 판정 불가를 알린다. 훅 고장 하나로 모든 셸이 막히지 않는다.
3. 계기 뒤집기 — 같은 고장(예외)에서 표지 있는 호출 · 없는 호출을 함께 심는다. 표지 밖 목록은 witness corpus 다.
4. 판정 불가 출력에는 예외의 이름만 싣는다 — 예외 메시지는 명령 글자를 담을 수 있다.
"""
import io
import json
import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS = _ROOT / ".claude" / "settings.json"
sys.path.insert(0, str(_ROOT / ".claude" / "hooks"))

import block_credential_dump as hook  # noqa: E402

_HOOK_FILE = "block_credential_dump.py"


def _pretooluse_hooks_for(tool):
    """그 도구에 걸리는 PreToolUse 훅 객체 전부 — matcher 는 `|` 로 나눈 정규식 토큰을 통째 일치로 본다."""
    settings = json.loads(_SETTINGS.read_text(encoding="utf-8"))
    out = []
    for entry in settings.get("hooks", {}).get("PreToolUse", []):
        tokens = [t.strip() for t in entry.get("matcher", "").split("|") if t.strip()]
        if any(re.fullmatch(t, tool) for t in tokens):
            out.extend(entry.get("hooks", []))
    return out


@pytest.mark.parametrize("tool", ["Bash", "PowerShell", "mcp__railway__deploy", "mcp__claude_ai_Supabase__execute_sql"])
def test_the_credential_hook_blocks_the_call_when_it_cannot_run(tool):
    """🔴 이 훅이 걸리는 도구마다, 그 훅 항목은 `onFailure: "block"` 이다 — 훅이 판정하지 못하면 호출이 막힌다."""
    hooks = [h for h in _pretooluse_hooks_for(tool) if _HOOK_FILE in h.get("command", "")]
    assert hooks, f"{tool} 에 credential 훅이 걸리지 않는다 — 배선부터 깨졌다"
    assert all(h.get("onFailure") == "block" for h in hooks), hooks


def test_the_edit_hook_keeps_its_loud_fail_open():
    """대조군 — 편집 훅은 `onFailure` 를 두지 않는다(사용자 결정 R31: 알리고 통과). 위 단언이 «모든 훅에 block» 같은
    싼 처방으로 초록이 되지 않게 한다."""
    hooks = [h for h in _pretooluse_hooks_for("Edit") if "check_edit_allowed.py" in h.get("command", "")]
    assert hooks, "편집 훅 배선을 못 찾았다"
    assert all("onFailure" not in h for h in hooks), hooks


def _main(monkeypatch, capsys, payload_text):
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload_text))
    assert hook.main() == 0
    out = capsys.readouterr().out
    return json.loads(out) if out.strip() else None


def _bash(command):
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(_ROOT)})


def _explode(*_args, **_kwargs):
    raise TypeError("planted failure carrying the command text: secret-value-123")


def _decision(result):
    return ((result or {}).get("hookSpecificOutput") or {}).get("permissionDecision")


# 판정 불가여도 막아야 할 호출 — 운영 · 자격 표지가 있다.
# Calls that must still be denied when the verdict fails: they carry a production/credential marker.
_MARKED = [
    "railway logs --deployment",
    "cat .env",
    "psql -c 'select 1'",
    'py -3 scripts/observe_db.py "SELECT 1"',
    "echo $DATABASE_URL",
    "env | sort",
    "Get-ChildItem Env:",
    "gh auth token",
]

# witness-corpus: 판정이 예외로 끝나도 막지 않아야 할 흔한 명령 — 운영 · 자격 표지 글자가 없다(표지 집합 밖의 값)
_UNMARKED = [
    "git status --short",
    "py -3 -m pytest tests/unit -q",
    "npm ci --no-audit",
    "ls -la docs/workflow",
    "gh pr checks 1924",
]


@pytest.mark.parametrize("command", _MARKED)
def test_a_marked_call_is_denied_when_the_verdict_raises(command, monkeypatch, capsys):
    """🔴 판정이 예외로 끝나면 표지 있는 호출은 막는다 — 고장 난 판정이 운영 · 자격 접근을 통과시키지 않는다."""
    monkeypatch.setattr(hook, "decide_with_hint", _explode)
    result = _main(monkeypatch, capsys, _bash(command))
    assert _decision(result) == "deny", result
    reason = result["hookSpecificOutput"]["permissionDecisionReason"]
    assert reason.startswith("[판정 불가]") and "TypeError" in reason, reason
    assert "secret-value-123" not in reason, "예외 메시지(명령 글자를 담을 수 있다)가 출력에 실렸다"


@pytest.mark.parametrize("command", _UNMARKED)
def test_an_unmarked_call_passes_with_a_notice_when_the_verdict_raises(command, monkeypatch, capsys):
    """대조군(뒤집기) — 같은 고장에서 표지 없는 호출은 막지 않는다. 대신 판정 불가를 에이전트 · 사람에게 알린다."""
    monkeypatch.setattr(hook, "decide_with_hint", _explode)
    result = _main(monkeypatch, capsys, _bash(command))
    assert result is not None, "판정 불가가 조용히 지나갔다"
    spec = result["hookSpecificOutput"]
    assert "permissionDecision" not in spec, spec
    assert spec["additionalContext"] == result["systemMessage"], result
    assert "판정하지 못했다" in spec["additionalContext"] and "TypeError" in spec["additionalContext"], spec
    assert "secret-value-123" not in spec["additionalContext"], spec


def test_a_production_mcp_call_is_denied_when_its_verdict_raises(monkeypatch, capsys):
    """MCP 갈래도 같다 — 운영 MCP 판정이 예외로 끝나면 그 도구 이름이 표지다."""
    monkeypatch.setattr(hook, "decide_mcp_production_access", _explode)
    payload = json.dumps({"tool_name": "mcp__railway__deploy", "tool_input": {"service": "web"}})
    assert _decision(_main(monkeypatch, capsys, payload)) == "deny"


@pytest.mark.parametrize(("payload_text", "decision"), [
    ('["railway", "up"]', "deny"),
    ('"cat .env"', "deny"),
    ("[1, 2, 3]", None),
    ("null", None),
    ("[" * 100_000, None),
    ('["railway", ' + "[" * 100_000, "deny"),
], ids=["list-marked", "string-marked", "list-plain", "null", "deep-nesting", "deep-nesting-marked"])
def test_a_payload_that_is_not_an_object_is_unjudged(payload_text, decision, monkeypatch, capsys):
    """🔴 JSON 이지만 객체가 아닌 입력은 판정 불가다 — 예전처럼 속성 오류로 죽지 않고, 표지로 가른다."""
    result = _main(monkeypatch, capsys, payload_text)
    assert result is not None, "판정 불가가 조용히 지나갔다"
    assert _decision(result) == decision, result


def test_a_normal_verdict_is_unchanged(monkeypatch, capsys):
    """대조군 — 판정이 정상으로 끝나면 예전 출력 그대로다(표지 판정은 판정 불가일 때만 쓴다)."""
    assert _main(monkeypatch, capsys, _bash("git status --short")) is None
    assert _decision(_main(monkeypatch, capsys, _bash("cat .env"))) == "deny"
