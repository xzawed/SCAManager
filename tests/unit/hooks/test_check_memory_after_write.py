"""메모리를 고친 순간 역방향 가드를 보이는 PostToolUse 훅 — #1746 K18 P2-32.

역방향 축은 세션 시작과 리포 커밋에서만 돌아, 메모리만 고친 순간(결함이 생기는 순간)에는 조용했다.
The reverse memory axis ran only at session start and on repo commits; this hook runs it right after a memory write.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_HOOK = _ROOT / ".claude" / "hooks" / "check_memory_after_write.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_memory_after_write", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load()


def _memory(tmp_path: Path, body: str) -> Path:
    d = tmp_path / "memory"
    d.mkdir()
    (d / "MEMORY.md").write_text(body, encoding="utf-8")
    return d


def _run(monkeypatch, capsys, memory_dir: Path, path: str) -> str:
    monkeypatch.setenv("CLAUDE_PROJECT_MEMORY_DIR", str(memory_dir))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_name": "Write",
                                                              "tool_input": {"file_path": path}})))
    assert hook.main() == 0
    return capsys.readouterr().out


def test_a_dead_coordinate_written_into_memory_is_reported_at_once(tmp_path, monkeypatch, capsys):
    """🔴 메모리에 죽은 좌표를 쓴 «그 순간» 보인다 — 사람에게(systemMessage)도, 쓴 쪽에게(additionalContext)도.

    계기 뒤집기 — 같은 메모리 상태라도 메모리 밖(리포 파일)을 쓴 때는 조용하다.
    """
    mem = _memory(tmp_path, "- 진입점 = `docs/gone-for-good.md`\n")
    payload = json.loads(_run(monkeypatch, capsys, mem, str(mem / "MEMORY.md")))
    assert "docs/gone-for-good.md" in payload["systemMessage"], payload
    assert payload["hookSpecificOutput"]["additionalContext"] == payload["systemMessage"], payload
    assert _run(monkeypatch, capsys, mem, str(_ROOT / "README.md")) == "", "메모리 밖 쓰기까지 판정했다"


def test_a_clean_memory_write_stays_silent(tmp_path, monkeypatch, capsys):
    """대조군 — 살아 있는 좌표만 있으면 아무 말도 하지 않는다(매 쓰기마다 떠들면 경고가 죽는다)."""
    mem = _memory(tmp_path, "- 진입점 = `docs/STATE.md`\n")
    assert _run(monkeypatch, capsys, mem, str(mem / "MEMORY.md")) == ""


@pytest.mark.parametrize("raw", ["", "not json", "[]", '{"tool_input": "x"}', '{"tool_input": {"file_path": 3}}'])
def test_unreadable_input_is_ignored(raw, monkeypatch, capsys):
    """무엇을 썼는지 모르면 조용히 넘어간다 — 훅이 쓰기 도구 전체를 시끄럽게 만들면 안 된다."""
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


def test_the_hook_is_wired_after_every_write_tool():
    """정의 ≠ 배선 — PostToolUse 의 Write · Edit · MultiEdit 에 이 훅이 걸려 있어야 한다."""
    cfg = json.loads((_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    matchers = [e.get("matcher", "") for e in cfg["hooks"]["PostToolUse"]
                for h in e.get("hooks", []) if "check_memory_after_write.py" in h.get("command", "")]
    assert matchers, "PostToolUse 에 메모리 쓰기 훅이 걸려 있지 않다 — 정의만 있고 아무 데서도 안 돈다"
    assert all({"Write", "Edit", "MultiEdit"} <= set(m.split("|")) for m in matchers), matchers
