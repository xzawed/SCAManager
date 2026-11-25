"""공개 쓰기 전 비밀값 · 개인정보 검사 — 세션과 분리된 고정 절차 (회고 원장 #1917 M02 P2-6).

## 이 파일이 잠그는 것

1. 파일 검사 — 꼴별 개수만 찍고 하나라도 있으면 exit 1. 맞은 값은 어디에도 찍지 않는다.
2. 훅 — gh 명령이면 명령 글자 전체와 그 명령이 가리키는 본문 파일(`--body-file` · `-F` · `--notes-file` · api 의 `key=@파일` ·
   `--input`)을 재고, 꼴이 있으면 deny 한다(개수만). 경로를 못 풀거나 파일을 못 읽으면 막는다(못 재면 red).
3. 계기 뒤집기 — 같은 명령 꼴에서 깨끗한 본문은 조용하다. 꼴 밖의 값(noreply 주소 · 예시 주소 · 저장소 URL · 세션 UUID ·
   CI 경로)은 witness corpus 로 심어 «아무 주소 · 아무 경로나 막기» 같은 싼 판정이 초록이 되지 않게 한다.
4. 배선 — Bash · PowerShell 의 gh 명령에만 뜨는 두 handler(`if`)이고, 고장 나면 막는다(`onFailure: "block"`).
"""
import io
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from ruamel.yaml import YAML

import scripts.scan_publish as scan

_ROOT = Path(__file__).resolve().parents[3]

# 합성 값 — 실제 비밀값 · 실제 주소가 아니다. 모양만 맞춘다.
# Synthetic values shaped like the real thing; none of them is real.
_GH_TOKEN = "ghp_" + "Ab1" * 12
_ANTHROPIC = "sk-ant-api03-" + "Zz9" * 10
_DB_URL = "postgresql://postgres.abcdefghijkl:" + "Qx7" * 4 + "@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"
_EMAIL = "someone.private" + "@" + "mailhost.io"
_HOME = "C:" + "\\Users\\" + "alice\\AppData\\Local\\x.md"

_PLANTED = {
    "github-token": f"token {_GH_TOKEN}",
    "anthropic-key": f"key={_ANTHROPIC}",
    "db-url-with-password": _DB_URL,
    "email": f"contact {_EMAIL}",
    "local-home-path": f"see {_HOME}",
}

# witness-corpus: 꼴과 닮았지만 공개해도 되는 값 — noreply · 예시 주소, 저장소 URL, 세션 UUID, CI 경로, 이름만 쓴 변수(검사 집합 밖)
_HARMLESS = [
    "Co-Authored-By: Claude <noreply@anthropic.com>",
    "dependabot[bot]@users.noreply.github.com",
    "mail me at someone@example.com",
    "git@github.com:xzawed/SCAManager.git",
    "https://github.com/xzawed/SCAManager/pull/1926",
    "- session: 3e9108d8-0139-451d-85b8-6a3f9c1ae55e",
    "/home/runner/work/SCAManager/SCAManager/tests",
    "`SESSION_SECRET` 은 값 없이 이름만 적는다 · sk-ant- 접두만 언급",
    "D:\\Source\\SCAManager\\docs\\workflow\\verify.md",
]


@pytest.mark.parametrize("kind", sorted(_PLANTED))
def test_each_planted_shape_is_counted_under_its_kind(kind):
    """🔴 심은 꼴은 그 종류로 센다."""
    assert scan.count_kinds(_PLANTED[kind]).get(kind, 0) == 1, scan.count_kinds(_PLANTED[kind])


def test_harmless_lookalikes_count_nothing():
    """대조군(뒤집기) — 닮았지만 공개해도 되는 값은 0 이다."""
    assert {line: scan.count_kinds(line) for line in _HARMLESS if scan.count_kinds(line)} == {}


def test_the_file_check_prints_counts_only_and_fails(tmp_path):
    """파일 검사 — 꼴별 개수를 찍고 exit 1. 맞은 값은 출력 어디에도 없다. 깨끗한 파일은 exit 0."""
    dirty, clean = tmp_path / "dirty.md", tmp_path / "clean.md"
    dirty.write_text("\n".join(_PLANTED.values()), encoding="utf-8")
    clean.write_text("\n".join(_HARMLESS), encoding="utf-8")
    run = lambda p: subprocess.run([sys.executable, str(_ROOT / "scripts" / "scan_publish.py"), str(p)],  # noqa: E731
                                   capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
    bad = run(dirty)
    assert bad.returncode == 1, bad.stdout + bad.stderr
    assert all(f"{kind} 1" in bad.stdout for kind in _PLANTED), bad.stdout
    leaked = [v for v in (_GH_TOKEN, _ANTHROPIC, _DB_URL, _EMAIL, _HOME) if v in bad.stdout + bad.stderr]
    assert leaked == [], "검사 출력에 맞은 값이 실렸다"
    good = run(clean)
    assert good.returncode == 0, good.stdout + good.stderr


def _hook(monkeypatch, capsys, command, cwd, tool="Bash"):
    payload = {"tool_name": tool, "tool_input": {"command": command}, "cwd": str(cwd)}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert scan.main(["--hook"]) == 0
    out = capsys.readouterr().out
    return json.loads(out) if out.strip() else None


def _denied(result):
    return ((result or {}).get("hookSpecificOutput") or {}).get("permissionDecision") == "deny"


def _reason(result):
    return result["hookSpecificOutput"]["permissionDecisionReason"]


def test_a_body_file_with_a_secret_is_denied_with_counts_only(tmp_path, monkeypatch, capsys):
    """🔴 본문 파일에 꼴이 있으면 막는다 — 사유에는 종류 · 개수만, 값은 없다."""
    body = tmp_path / "pr.md"
    body.write_text(f"# 본문\n{_PLANTED['github-token']}\n", encoding="utf-8")
    result = _hook(monkeypatch, capsys, f'gh pr create --title t --body-file "{body.as_posix()}"', tmp_path)
    assert _denied(result), result
    assert "github-token 1" in _reason(result) and _GH_TOKEN not in json.dumps(result), result


def test_a_clean_body_file_passes_silently(tmp_path, monkeypatch, capsys):
    """대조군(뒤집기) — 같은 명령 꼴에서 본문이 깨끗하면 아무것도 내지 않는다."""
    body = tmp_path / "pr.md"
    body.write_text("\n".join(_HARMLESS), encoding="utf-8")
    assert _hook(monkeypatch, capsys, f'gh pr create --title t --body-file "{body.as_posix()}"', tmp_path) is None


@pytest.mark.parametrize("template", [
    'cd "{d}" && gh issue comment 1917 --body-file note.md',
    'S="{d}"; gh issue edit 1917 --body-file "$S/note.md"',
    'gh pr edit 5 -F {d}/note.md',
    'gh release create v1 --notes-file {d}/note.md',
    'gh api repos/o/r/issues/1/comments -F body=@{d}/note.md',
    'gh api repos/o/r/pulls/2 -X PATCH --input {d}/note.md',
], ids=["cd-then-relative", "same-command-variable", "short-flag", "release-notes", "api-field-file", "api-input"])
def test_every_way_of_pointing_at_a_body_file_is_read(template, tmp_path, monkeypatch, capsys):
    """본문 파일을 가리키는 꼴마다 그 파일을 읽는다 — 복합 명령 · 같은 명령 안의 변수 · 짧은 플래그 · api 필드."""
    (tmp_path / "note.md").write_text(_PLANTED["email"], encoding="utf-8")
    result = _hook(monkeypatch, capsys, template.format(d=tmp_path.as_posix()), _ROOT)
    assert _denied(result) and "email 1" in _reason(result), result


# witness-corpus: 본문 파일이 아닌 값을 받는 gh 플래그 — 이 값은 파일로 읽지 않는다(본문 파일 플래그 집합 밖)
_NOT_BODY_FLAGS = ["--title", "-t", "--base", "-R", "--label", "--json"]


@pytest.mark.parametrize("flag", _NOT_BODY_FLAGS)
def test_non_body_flags_are_not_read_as_files(flag, tmp_path, monkeypatch, capsys):
    """대조군 — 본문 파일이 아닌 플래그의 값은 파일로 읽지 않는다(읽으려 들면 «못 읽었다» 로 막혔을 것이다)."""
    assert _hook(monkeypatch, capsys, f"gh pr create {flag} no-such-file.md --body-file -", tmp_path) is None


def test_an_inline_body_is_scanned_from_the_command_text(tmp_path, monkeypatch, capsys):
    """인라인 본문(`--body`) · heredoc 은 명령 글자 자체에 있다 — 그것도 잰다."""
    result = _hook(monkeypatch, capsys, f'gh pr comment 7 --body "see {_DB_URL}"', tmp_path)
    assert _denied(result) and "db-url-with-password 1" in _reason(result), result


@pytest.mark.parametrize("command", [
    "gh pr create --body-file no-such-file.md",
    'gh issue comment 1 --body-file "$UNDEFINED_VAR_FOR_TEST/x.md"',
    'gh pr create --body-file "$(mktemp)"',
], ids=["missing-file", "unresolved-variable", "command-substitution"])
def test_a_body_file_that_cannot_be_read_is_denied(command, tmp_path, monkeypatch, capsys):
    """🔴 못 재면 막는다 — 없는 파일 · 풀지 못한 변수 · 명령 치환 경로."""
    monkeypatch.delenv("UNDEFINED_VAR_FOR_TEST", raising=False)
    result = _hook(monkeypatch, capsys, command, tmp_path)
    assert _denied(result) and "못" in _reason(result), result


def test_powershell_commands_are_checked_too(tmp_path, monkeypatch, capsys):
    """PowerShell 도구의 gh 명령도 같은 판정이다(역슬래시 경로)."""
    body = tmp_path / "pr.md"
    body.write_text(_PLANTED["anthropic-key"], encoding="utf-8")
    result = _hook(monkeypatch, capsys, f'gh pr create --body-file "{body}"', tmp_path, tool="PowerShell")
    assert _denied(result) and "anthropic-key 1" in _reason(result), result


def test_non_gh_commands_and_reads_stay_silent(tmp_path, monkeypatch, capsys):
    """대조군 — gh 가 아닌 명령 · 꼴 없는 gh 읽기는 조용하다(`if` 가 못 거른 경우에도)."""
    assert _hook(monkeypatch, capsys, "git status --short && npm ci", tmp_path) is None
    assert _hook(monkeypatch, capsys, "gh pr view 1926 --json state --jq .state", tmp_path) is None


def test_unreadable_hook_input_is_denied(monkeypatch, capsys):
    """입력을 못 읽으면(이 훅은 gh 명령에만 뜬다) 판정 불가로 막는다."""
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    assert scan.main(["--hook"]) == 0
    assert _denied(json.loads(capsys.readouterr().out))


def test_the_db_url_shape_is_the_same_expression_as_the_commit_hook():
    """DB 주소 꼴은 커밋 훅(`check-db-url-in-diff`)과 같은 식이다 — 두 벌이 갈라지면 한쪽만 고쳐진다."""
    config = YAML(typ="safe", pure=True).load((_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    entries = [h["entry"] for repo in config["repos"] for h in repo.get("hooks", []) if h.get("id") == "check-db-url-in-diff"]
    assert entries == [scan._KINDS["db-url-with-password"]], "커밋 훅과 게시 전 검사의 DB 주소 식이 갈라졌다"


def _publish_handlers():
    settings = json.loads((_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    return [h for entry in settings["hooks"]["PreToolUse"] for h in entry.get("hooks", [])
            if "scripts/scan_publish.py" in h.get("command", "")]


def test_the_hook_is_wired_for_gh_on_both_shells_and_blocks_on_failure():
    """🔴 배선 — Bash · PowerShell 의 gh 명령에만 뜨는 두 handler, 고장 나면 막는다."""
    handlers = _publish_handlers()
    assert sorted(h.get("if") for h in handlers) == ["Bash(gh *)", "PowerShell(gh *)"], handlers
    assert all(h.get("onFailure") == "block" and re.search(r"scan_publish\.py --hook$", h["command"]) for h in handlers)
