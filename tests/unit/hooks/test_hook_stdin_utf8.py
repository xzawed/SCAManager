"""훅은 stdin 을 바이트로 읽어 UTF-8 로 디코드한다 (원장 #1940 M06 P2-31 · P2-32).
Hooks read stdin as bytes and decode UTF-8 themselves.

하네스는 훅 입력을 UTF-8 JSON 으로 보낸다. 그런데 Windows 자식 프로세스의 `sys.stdin` 은 로캘 코덱(cp949)이라, 문자열로 읽으면
한글이 든 명령 · 경로가 다른 글자로 바뀐다 — 거부 · 감사 기록의 sha256 · 길이가 실제 명령과 달라 회고가 기록을 세션에 대지
못했고(창 거부의 26%), 경로 판정도 바뀐 글자를 본다. 형제 훅 하나(`check_memory_after_write.py`)만 고쳐져 있었다. Linux CI
에서는 원리적으로 안 드러나므로 시험은 `PYTHONIOENCODING=cp949` 로 그 상태를 만든다.
"""
import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_HOOKS = sorted((_ROOT / ".claude" / "hooks").glob("*.py"))
_CREDENTIAL = _ROOT / ".claude" / "hooks" / "block_credential_dump.py"


def _text_stdin_reads(path: Path) -> list[int]:
    """`sys.stdin.read()` · `json.load(sys.stdin)` 처럼 stdin 을 문자열로 읽는 자리(줄 번호) / text-mode stdin reads."""
    def is_sys_stdin(node):
        return (isinstance(node, ast.Attribute) and node.attr == "stdin"
                and isinstance(node.value, ast.Name) and node.value.id == "sys")
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in ("read", "readline", "readlines") and is_sys_stdin(func.value):
            found.append(node.lineno)
        if (isinstance(func, ast.Attribute) and func.attr == "load" and isinstance(func.value, ast.Name)
                and func.value.id == "json" and node.args and is_sys_stdin(node.args[0])):
            found.append(node.lineno)
    return found


def test_the_hooks_folder_is_not_empty():
    """공허화 방어 — 잴 훅이 있다."""
    assert _HOOKS


@pytest.mark.parametrize("hook", _HOOKS, ids=[p.name for p in _HOOKS])
def test_no_hook_reads_stdin_as_locale_text(hook):
    """🔴 stdin 을 문자열로 읽는 훅이 없다 — `sys.stdin.buffer.read()` 를 UTF-8 로 디코드한다."""
    assert _text_stdin_reads(hook) == [], f"{hook.name}: 로캘 코덱으로 stdin 을 읽는 줄 {_text_stdin_reads(hook)}"


def test_a_korean_command_is_recorded_with_its_real_length(tmp_path):
    """🔴 cp949 stdin 에서도 거부 기록의 길이 · sha256 이 실제 명령과 같다(한글 주석이 든 .env 읽기)."""
    import hashlib  # pylint: disable=import-outside-toplevel
    command = "cat .env  # 한글 주석 — 값은 보지 않는다"
    log = tmp_path / "denials.jsonl"
    env = {**os.environ, "PYTHONIOENCODING": "cp949", "SCAMANAGER_HOOK_LOG": str(log)}
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}, ensure_ascii=False).encode("utf-8")
    proc = subprocess.run([sys.executable, str(_CREDENTIAL)], input=payload, capture_output=True, timeout=60,
                          check=False, cwd=str(_ROOT), env=env)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert json.loads(proc.stdout.decode("utf-8"))["hookSpecificOutput"]["permissionDecision"] == "deny"
    record = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert record["len"] == len(command), record
    assert record["sha256"] == hashlib.sha256(command.encode("utf-8")).hexdigest(), "기록이 바뀐 글자를 쟀다"
