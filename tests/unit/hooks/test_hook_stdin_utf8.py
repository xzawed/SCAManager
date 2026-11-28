"""훅은 stdin 을 바이트로 읽어 UTF-8 로 디코드한다 (원장 #1940 M06 P2-31 · P2-32).
Hooks read stdin as bytes and decode UTF-8 themselves.

하네스는 훅 입력을 UTF-8 JSON 으로 보낸다. 그런데 Windows 자식 프로세스의 `sys.stdin` 은 로캘 코덱(cp949 + surrogateescape)이라,
문자열로 읽으면 한글이 든 명령 · 경로가 다른 글자로 바뀐다. 거부 · 감사 기록의 sha256 · 길이가 실제 명령과 달라졌고(창 거부의 26%),
더 나쁘게는 한글 바로 뒤 ASCII 한 글자가 cp949 두 바이트 글자에 먹혀 게시 전 검사가 한글에 붙은 토큰 · DB 주소를 놓쳤다
(실측: «각» 뒤의 GitHub 토큰 — UTF-8 로 읽으면 막고, 실훅 조건이면 통과). Linux CI 에서는 원리적으로 안 드러나므로 시험은
`PYTHONIOENCODING=cp949:surrogateescape` 로 그 상태를 만든다.
"""
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.unit.scripts.test_scan_publish import _DB_URL, _GH_TOKEN

_ROOT = Path(__file__).resolve().parents[3]
_CREDENTIAL = _ROOT / ".claude" / "hooks" / "block_credential_dump.py"
_PUBLISH_SCAN = _ROOT / "scripts" / "scan_publish.py"
_REAL_HOOK_STDIN = "cp949:surrogateescape"


def _hook_entry_scripts() -> list[Path]:
    """settings.json 의 훅 명령이 돌리는 리포 안 파이썬 파일 — 새 훅을 등록하면 이 시험이 저절로 그것도 잰다."""
    settings = json.loads((_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    found = set()
    for entries in settings.get("hooks", {}).values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                for match in re.finditer(r"(?<![\w.-])((?:\.claude|scripts)/[\w./-]+\.py)\b", hook.get("command", "")):
                    path = _ROOT / match.group(1)
                    if path.is_file():
                        found.add(path)
    return sorted(found)


_ENTRY_SCRIPTS = _hook_entry_scripts()


def _text_stdin_reads_in(source: str) -> list[int]:
    """stdin 을 로캘 글자로 읽는 자리(줄 번호) — `sys.stdin.read*()` · `json.load(sys.stdin)` · `for … in sys.stdin` · `input()` ·
    `fileinput.input()`. / Text-mode stdin reads in `source`."""
    def is_sys_stdin(node):
        return (isinstance(node, ast.Attribute) and node.attr == "stdin"
                and isinstance(node.value, ast.Name) and node.value.id == "sys")
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.For, ast.comprehension)) and is_sys_stdin(node.iter):
            found.append(getattr(node, "lineno", getattr(node.iter, "lineno", 0)))
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in ("read", "readline", "readlines") and is_sys_stdin(func.value):
            found.append(node.lineno)
        if (isinstance(func, ast.Attribute) and func.attr == "load" and isinstance(func.value, ast.Name)
                and func.value.id == "json" and node.args and is_sys_stdin(node.args[0])):
            found.append(node.lineno)
        if isinstance(func, ast.Name) and func.id == "input":
            found.append(node.lineno)
        if (isinstance(func, ast.Attribute) and func.attr == "input" and isinstance(func.value, ast.Name)
                and func.value.id == "fileinput"):
            found.append(node.lineno)
    return found


def _text_stdin_reads(path: Path) -> list[int]:
    return _text_stdin_reads_in(path.read_text(encoding="utf-8"))


# witness-corpus: stdin 을 로캘 글자로 읽는 다른 꼴 — 줄 단위 순회 · input() · fileinput (read 계열 메서드 이름 밖)
_OTHER_TEXT_READS = ["for line in sys.stdin:\n    pass\n", "name = input()\n",
                     "import fileinput\nfor line in fileinput.input():\n    pass\n",
                     "lines = [line for line in sys.stdin]\n"]


@pytest.mark.parametrize("source", _OTHER_TEXT_READS)
def test_other_text_mode_stdin_reads_are_caught(source):
    """🔴 메서드 이름 목록 밖의 글자 읽기도 잡는다 — 훅이 이 꼴로 바꿔도 가드가 초록으로 지나치지 않게."""
    assert _text_stdin_reads_in(source), source


def test_a_bytes_read_is_not_a_text_read():
    """대조군 — `sys.stdin.buffer.read()` 를 UTF-8 로 디코드하는 관용구는 글자 읽기가 아니다."""
    assert _text_stdin_reads_in('raw = getattr(sys.stdin, "buffer", sys.stdin).read()\n') == []


def _run_hook(script: Path, payload: dict, env_extra: dict) -> subprocess.CompletedProcess:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    env = {**os.environ, "PYTHONIOENCODING": _REAL_HOOK_STDIN, **env_extra}
    return subprocess.run([sys.executable, str(script), *(["--hook"] if script == _PUBLISH_SCAN else [])], input=data,
                          capture_output=True, timeout=60, check=False, cwd=str(_ROOT), env=env)


def _absorbing_syllable(value: str) -> str:
    """cp949 + surrogateescape 로 읽으면 `value` 의 첫 글자를 먹는 한글 음절 / a syllable that swallows value's first char."""
    for code in range(0xAC00, 0xD7A4):
        if value not in (chr(code) + value).encode("utf-8").decode("cp949", "surrogateescape"):
            return chr(code)
    raise AssertionError("먹는 음절이 없다 — 시험 전제가 깨졌다")


def test_the_entry_scripts_include_the_hooks_and_the_publish_scan():
    """공허화 방어 — 잴 훅이 있고, 게시 전 검사(scripts/)도 settings 에서 끌어온다."""
    assert _ENTRY_SCRIPTS and _PUBLISH_SCAN in _ENTRY_SCRIPTS and _CREDENTIAL in _ENTRY_SCRIPTS


@pytest.mark.parametrize("script", _ENTRY_SCRIPTS, ids=[p.name for p in _ENTRY_SCRIPTS])
def test_no_hook_reads_stdin_as_locale_text(script):
    """🔴 settings 가 돌리는 훅 어느 것도 stdin 을 문자열로 읽지 않는다 — `sys.stdin.buffer.read()` 를 UTF-8 로 디코드한다."""
    assert _text_stdin_reads(script) == [], f"{script.name}: 로캘 코덱으로 stdin 을 읽는 줄 {_text_stdin_reads(script)}"


@pytest.mark.parametrize("value", [pytest.param(_GH_TOKEN, id="github-token"), pytest.param(_DB_URL, id="db-url")])
def test_the_publish_scan_sees_a_secret_glued_to_korean(value, tmp_path):
    """🔴 실훅 조건(cp949 stdin)에서도 한글 바로 뒤에 붙은 토큰 · DB 주소를 막는다 — 로캘로 읽으면 첫 글자가 먹혀 통과했다."""
    syllable = _absorbing_syllable(value)
    command = f"gh issue comment 1 --body '{syllable}{value}'"
    proc = _run_hook(_PUBLISH_SCAN, {"tool_name": "Bash", "tool_input": {"command": command}},
                     {"SCAMANAGER_HOOK_LOG": str(tmp_path / "denials.jsonl")})
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert '"deny"' in proc.stdout.decode("utf-8"), f"«{syllable}» 뒤의 값을 놓쳤다"


@pytest.mark.parametrize("script", [_CREDENTIAL, _PUBLISH_SCAN], ids=["credential", "publish-scan"])
def test_a_korean_command_is_recorded_with_its_real_length(script, tmp_path):
    """🔴 cp949 stdin 에서도 거부 기록의 길이 · sha256 이 실제 명령과 같다(두 막는 훅이 같은 기록 파일을 쓴다)."""
    command = ("cat .env  # 한글 주석 — 값은 보지 않는다" if script == _CREDENTIAL
               else f"gh issue comment 1 --body '한글 본문 {_GH_TOKEN}'")
    log = tmp_path / "denials.jsonl"
    proc = _run_hook(script, {"tool_name": "Bash", "tool_input": {"command": command}}, {"SCAMANAGER_HOOK_LOG": str(log)})
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert json.loads(proc.stdout.decode("utf-8"))["hookSpecificOutput"]["permissionDecision"] == "deny"
    record = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert record["len"] == len(command), record
    assert record["sha256"] == hashlib.sha256(command.encode("utf-8")).hexdigest(), "기록이 바뀐 글자를 쟀다"
