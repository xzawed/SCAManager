"""credential · 운영 접근 훅의 정밀도 — 정직한 명령은 통과, 값이 나오는 꼴은 그대로 막는다 (회고 원장 #1917 M02 P1-5).

## 이 파일이 잠그는 것

1. 실제로 막혔던 정직한 꼴(오탐)은 통과한다 — 검색 패턴 속 `\\.env` · 큰따옴표 안 `\\|` 재귀 검색(그 폴더에 .env 없음) ·
   파일 대상에 붙은 `2>/dev/null` · `env | grep -c`(개수만) · `printenv | grep -o '^[A-Z_]*='`(이름만) · `git grep` 패턴의 `\\*`.
2. 계기 뒤집기 — 같은 꼴의 위험한 짝은 그대로 막는다: `.env` 를 대상으로 한 grep · .env 가 있는 폴더의 재귀 검색 ·
   개수가 아닌 env 걸러내기 · 값을 내는 `grep -o` · `.gitignore` 를 끈 `git grep`.
3. 판정은 임시 폴더(.env 가 있는 작업 폴더)에서 잰다 — 재귀 검색 판정은 디스크의 .env 꼴 파일을 실제로 대 본다.
"""
import hashlib
import io
import json
import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / ".claude" / "hooks"))

import block_credential_dump as hook  # noqa: E402


@pytest.fixture
def workdir(tmp_path):
    """작업 폴더 — 루트에 .env(합성 값), docs/ 와 src/ 에는 .env 가 없다."""
    (tmp_path / ".env").write_text("SYNTHETIC_KEY=not-a-real-value\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("text\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    return tmp_path


def _verdict(command, cwd):
    return hook.decide_with_hint(command, str(cwd), "bash")


# 회고 창 · 11-25 세션에서 실제로 막힌 정직한 명령의 꼴 — 값이 나올 길이 없다.
# Honest shapes that were really denied; none of them can print a value.
_MUST_PASS = {
    "pattern-mentions-dotenv": 'grep -n "\\.env" docs/a.md',
    "quoted-alternation-recursive": 'grep -rn "foo\\|bar" docs/',
    "stderr-redirect-on-file-target": 'grep -rn -E "a|b" src/a.py 2>/dev/null | head -8',
    "env-count-only": 'env | grep -c -E "^PY"',
    "env-line-count": "env | wc -l",
    "printenv-names-only": "printenv | grep -o '^[A-Z_]*='",
    "git-grep-escaped-glob-pattern": 'git grep -n -E "req\\*|\\.claude/\\*\\*" -- docs/',
    "git-grep-escaped-glob-pattern-piped": 'git grep -n -E "req\\*|\\.claude/\\*\\*" -- docs/ src/ | head',
}

# 같은 꼴의 위험한 짝 — 값이 나온다(또는 나올 수 있다).
# The dangerous twins of the same shapes: a value is (or may be) printed.
_MUST_BLOCK = {
    "grep-targets-dotenv": "grep -n KEY .env",
    "recursive-over-folder-with-dotenv": "grep -rn KEY . 2>/dev/null",
    "quoted-alternation-recursive-over-dotenv-folder": 'grep -rn "foo\\|bar" .',
    "env-filtered-not-counted": "env | grep KEY",
    "printenv-values-via-grep-o": "printenv | grep -o 'TOKEN=.*'",
    "git-grep-without-gitignore": "git grep --no-index KEY",
    "safe-dotenv-command-piped-onward": "ls .env | xargs cat",
    "end-of-options-makes-dotenv-a-file": "grep -- -e .env",
    "wc-reading-stdin-as-file-names": "env | wc --files0-from=-",
    # 커밋 보안 검토(자동)가 짚은 반례 — 글자 모임 범위가 `=` 를 품음 · 줄인 긴 옵션 · 이스케이프한 파이프.
    # Counterexamples from the automated commit review: a class range spanning `=`, abbreviated long options, an escaped pipe.
    "names-only-class-range-spans-equals": "printenv | grep -o '^[0-z]*='",
    "names-only-without-trailing-equals": "printenv | grep -o '^[0-z]*'",
    "abbreviated-regexp-attached": "grep --regex=KEY .env",
    "abbreviated-regexp-separate": "grep --reg KEY .env",
    "unknown-long-option-keeps-positionals": "grep --some-new-flag KEY .env",
    "escaped-pipe-is-not-a-pipe": "printenv \\| grep -c SOME_KEY",
}


@pytest.mark.parametrize("name", sorted(_MUST_PASS))
def test_honest_shapes_that_were_denied_now_pass(name, workdir):
    """🔴 막혔던 정직한 꼴은 통과한다(오탐 회귀 코퍼스)."""
    assert _verdict(_MUST_PASS[name], workdir) is None, (name, _verdict(_MUST_PASS[name], workdir))


@pytest.mark.parametrize("name", sorted(_MUST_BLOCK))
def test_their_dangerous_twins_are_still_denied(name, workdir):
    """대조군(뒤집기) — 같은 꼴의 위험한 짝은 그대로 막는다. «검색이면 통과» 같은 싼 완화는 여기서 걸린다."""
    assert _verdict(_MUST_BLOCK[name], workdir) is not None, name


def _run_main(monkeypatch, capsys, payload):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert hook.main() == 0
    return capsys.readouterr().out


def _records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def test_every_denial_leaves_a_value_free_record(tmp_path, monkeypatch, capsys):
    """🔴 거부마다 기록 한 줄 — 시각 · 종류 · 사유 · 명령 sha256 · 길이만. 명령 글자 · 값은 남기지 않는다(회고가 정밀도를 센다)."""
    log = tmp_path / "denials.jsonl"
    monkeypatch.setenv("SCAMANAGER_HOOK_LOG", str(log))
    secret_looking = "grep -n SYNTHETIC_MARKER_123 .env"
    _run_main(monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": secret_looking}})
    _run_main(monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": "railway up"}})
    _run_main(monkeypatch, capsys, {"tool_name": "mcp__railway__deploy", "tool_input": {}})
    records = _records(log)
    assert [r["kind"] for r in records] == ["credential", "production", "production"], records
    first = records[0]
    assert set(first) == {"ts", "kind", "reason", "sha256", "len"}, first
    assert first["sha256"] == hashlib.sha256(secret_looking.encode("utf-8")).hexdigest()
    assert first["len"] == len(secret_looking)
    assert "SYNTHETIC_MARKER_123" not in log.read_text(encoding="utf-8"), "명령 글자가 기록에 남았다"


def test_a_pass_leaves_no_record_and_a_broken_log_never_changes_the_verdict(tmp_path, monkeypatch, capsys):
    """대조군 — 통과는 기록하지 않는다. 기록을 못 써도(폴더 자리에 파일) 판정은 그대로 deny 다."""
    log = tmp_path / "denials.jsonl"
    monkeypatch.setenv("SCAMANAGER_HOOK_LOG", str(log))
    assert _run_main(monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": "git status"}}) == ""
    assert not log.exists()
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("SCAMANAGER_HOOK_LOG", str(blocker / "denials.jsonl"))
    out = _run_main(monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": "cat .env"}})
    assert '"permissionDecision": "deny"' in out, out


def test_the_suite_never_writes_the_real_denial_log():
    """🔴 시험은 실제 홈의 거부 기록을 건드리지 않는다 — 회고가 그 파일로 정밀도를 센다(conftest 가 임시 자리로 돌린다)."""
    log = os.environ.get("SCAMANAGER_HOOK_LOG", "")
    real = os.path.join(os.path.expanduser("~"), ".scamanager")
    assert log and not os.path.abspath(log).startswith(os.path.abspath(real)), log


def test_a_mention_only_production_word_in_a_search_pattern_passes():
    """대조군 — 검색 패턴 속 `railway ssh` 는 명령 자리가 아니다(이미 통과 · 회귀 잠금). 진짜 호출은 막는다."""
    assert hook.decide_production_access('grep -n "railway ssh" docs/a.md') is None
    assert hook.decide_production_access("railway ssh") is not None
