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
    command = f"gh pr create {flag} no-such-file.md --body-file - <<'EOF'\nclean body\nEOF"
    assert _hook(monkeypatch, capsys, command, tmp_path) is None


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


@pytest.mark.parametrize("template", [
    "cat {d}/note.md | gh pr create --body-file -",
    "gh issue comment 1 --body-file - < {d}/note.md",
    "gh api repos/o/r/issues/1/comments -F body=@- < {d}/note.md",
], ids=["piped-stdin", "redirected-stdin", "api-field-stdin"])
def test_a_stdin_body_is_measured_or_denied(template, tmp_path, monkeypatch, capsys):
    """🔴 본문이 stdin(`-`)이면 — `<` 로 받은 파일은 재고, 파이프처럼 모르는 곳에서 오면 못 재서 막는다(보안 검토 ①)."""
    (tmp_path / "note.md").write_text(_PLANTED["email"], encoding="utf-8")
    assert _denied(_hook(monkeypatch, capsys, template.format(d=tmp_path.as_posix()), tmp_path))


def test_a_heredoc_stdin_body_is_measured_from_the_command(tmp_path, monkeypatch, capsys):
    """대조군 — heredoc 본문은 명령 글자에 있어 잰다. 깨끗하면 통과, 꼴이 있으면 막는다."""
    clean = "gh pr create --body-file - <<'EOF'\nit's a clean body\nEOF"
    assert _hook(monkeypatch, capsys, clean, tmp_path) is None
    dirty = f"gh pr create --body-file - <<'EOF'\nsee {_HOME}\nEOF"
    assert _denied(_hook(monkeypatch, capsys, dirty, tmp_path))


@pytest.mark.parametrize("template", [
    "gh pr create -F{d}/note.md",
    "gh pr create --body-file={d}/note.md",
    "gh gist create {d}/note.md --public",
    "gh gist edit abc123 --add {d}/note.md",
], ids=["attached-short-flag", "long-flag-equals", "gist-create-positional", "gist-edit-add"])
def test_other_ways_of_naming_a_body_file_are_read(template, tmp_path, monkeypatch, capsys):
    """붙여 쓴 짧은 플래그 · `--flag=값` · gist 파일도 읽는다(보안 검토 ② ③)."""
    (tmp_path / "note.md").write_text(_PLANTED["github-token"], encoding="utf-8")
    result = _hook(monkeypatch, capsys, template.format(d=tmp_path.as_posix()), tmp_path)
    assert _denied(result) and "github-token 1" in _reason(result), result


@pytest.mark.parametrize("command", [
    'gh pr create --body "$(cat notes.md)"',
    "gh issue comment 1 -b `cat notes.md`",
    'gh api repos/o/r/issues -f body="$(cat notes.md)"',
], ids=["body-substitution", "backtick", "api-field-substitution"])
def test_a_published_value_built_by_command_substitution_is_denied(command, tmp_path, monkeypatch, capsys):
    """본문 값이 명령 치환이면 그 결과를 잴 수 없다 — 막는다(보안 검토 ②)."""
    result = _hook(monkeypatch, capsys, command, tmp_path)
    assert _denied(result) and "못" in _reason(result), result


@pytest.mark.parametrize("command, tool", [
    ('BODY=$(cat notes.md) && gh pr create --title t --body "$BODY"', "Bash"),
    ('gh pr create --title t --body "$UNSET_BODY_FOR_TEST"', "Bash"),
    ('gh issue comment 1 --body "${UNSET_BODY_FOR_TEST}"', "Bash"),
    ('B=ok; gh issue comment 1 --body "${B:-fallback}"', "Bash"),
    ('read -r B < notes.md; gh pr comment 2 --body "$B"', "Bash"),
    ('gh api repos/o/r/issues -f body="$UNSET_BODY_FOR_TEST"', "Bash"),
    ('gh gist create notes.md -d "$UNSET_BODY_FOR_TEST"', "Bash"),
    ('gh gist edit abc123 --desc "$UNSET_BODY_FOR_TEST"', "Bash"),
    ('gh pr merge 3 --squash --subject "$UNSET_BODY_FOR_TEST"', "Bash"),
    ("$b = Get-Content notes.md -Raw; gh pr create --title t --body $b", "PowerShell"),
], ids=["assigned-from-substitution", "unassigned", "braced", "parameter-expansion", "read-builtin",
        "api-field", "gist-create-description", "gist-edit-description", "merge-subject", "powershell-variable"])
def test_a_published_value_from_a_variable_it_cannot_resolve_is_denied(command, tool, tmp_path, monkeypatch, capsys):
    """🔴 게시될 인라인 글(`--body` · `--title` · api 필드 · gist 설명 · 머지 제목)이 변수면, 같은 명령 안의 글자 대입으로
    풀리지 않는 한 그 값을 잴 수 없다 — 막는다. 본문 파일 경로의 변수와 같은 계약이다(못 재면 막는다).
    A published inline value that is a variable is unmeasurable unless a literal assignment in the same command resolves it.
    """
    monkeypatch.delenv("UNSET_BODY_FOR_TEST", raising=False)
    (tmp_path / "notes.md").write_text("clean", encoding="utf-8")
    result = _hook(monkeypatch, capsys, command, tmp_path, tool=tool)
    assert _denied(result) and "못" in _reason(result), result


def test_a_published_value_from_the_environment_is_not_trusted(tmp_path, monkeypatch, capsys):
    """🔴 훅의 환경은 명령이 도는 셸의 환경이 아니다(셸 프로필이 덮을 수 있다) — 게시될 글의 변수는 환경에서 풀지 않는다.
    The hook's environment is not the shell's; a published value is never resolved from it.
    """
    monkeypatch.setenv("PUB_BODY_FOR_TEST", "all clean")
    result = _hook(monkeypatch, capsys, 'gh pr comment 1 --body "$PUB_BODY_FOR_TEST"', tmp_path)
    assert _denied(result) and "못" in _reason(result), result


def test_a_published_value_from_a_literal_assignment_is_measured(tmp_path, monkeypatch, capsys):
    """대조군(뒤집기) — 같은 명령 안의 글자 대입으로 풀리는 변수는 그 값을 잰다: 깨끗하면 통과, 홈 경로가 있으면 그 꼴로 막는다.
    «변수면 무조건 막기» 는 앞쪽을, «명령 글자만 재기»(홈 경로는 명령 글자에서 세지 않는다) 는 뒤쪽을 틀린다.
    """
    assert _hook(monkeypatch, capsys, 'B="all clean"; gh pr comment 3 --body "$B"', tmp_path) is None
    result = _hook(monkeypatch, capsys, f'B="log at {_HOME}"; gh pr comment 3 --body "$B"', tmp_path)
    assert _denied(result) and "local-home-path 1" in _reason(result), result


# witness-corpus: 게시될 글이 아닌 값을 받는 gh 플래그 — 그 값이 변수여도 게시되지 않으니 막지 않는다
_NOT_PUBLISHED_FLAGS = ["--base", "--head", "-R", "--label", "--search", "--jq"]


@pytest.mark.parametrize("flag", _NOT_PUBLISHED_FLAGS)
def test_a_variable_in_a_flag_that_is_not_published_stays_silent(flag, tmp_path, monkeypatch, capsys):
    """대조군 — 게시될 글이 아닌 플래그의 변수는 재지 않는다(«`$` 가 든 gh 명령은 막기» 같은 싼 판정을 거른다)."""
    monkeypatch.delenv("UNSET_BODY_FOR_TEST", raising=False)
    command = f'gh pr create {flag} "$UNSET_BODY_FOR_TEST" --body-file - <<\'EOF\'\nclean body\nEOF'
    assert _hook(monkeypatch, capsys, command, tmp_path) is None


def test_a_dollar_that_is_not_a_variable_name_is_plain_text(tmp_path, monkeypatch, capsys):
    """대조군 — `$5` · 홀로 선 `$` 는 변수 이름이 아니다. 게시될 글에 `$` 가 들었다고 막지 않는다."""
    assert _hook(monkeypatch, capsys, 'gh pr comment 3 --body "costs $5 or 5 $ total"', tmp_path) is None


def test_arguments_after_a_heredoc_marker_on_the_same_line_are_judged(tmp_path, monkeypatch, capsys):
    """🔴 heredoc 여는 줄의 나머지(`<<'EOF' --title …`)도 gh 의 인자다 — 본문과 함께 걷어 내면 그 글을 재지 못한다.
    Words after the heredoc operator on the same line are still gh arguments.
    """
    monkeypatch.delenv("UNSET_BODY_FOR_TEST", raising=False)
    tail_var = "gh pr create --body-file - <<'EOF' --title \"$UNSET_BODY_FOR_TEST\"\nclean body\nEOF"
    result = _hook(monkeypatch, capsys, tail_var, tmp_path)
    assert _denied(result) and "못" in _reason(result), result
    tail_home = f"gh pr create --body-file - <<'EOF' --title \"see {_HOME}\"\nclean body\nEOF"
    result = _hook(monkeypatch, capsys, tail_home, tmp_path)
    assert _denied(result) and "local-home-path 1" in _reason(result), result
    assert _hook(monkeypatch, capsys, "gh pr create --body-file - <<'EOF' --title ok\nclean body\nEOF", tmp_path) is None


@pytest.mark.parametrize("word, denied, why", [
    ('"$UNSET_BODY_FOR_TEST"', True, "못"),
    (f'"see {_HOME}"', True, "local-home-path 1"),
    ('"all clean"', False, ""),
    ("'literal $UNSET_BODY_FOR_TEST'", False, ""),
], ids=["variable", "home-path", "clean", "single-quoted-literal"])
def test_a_here_string_body_is_measured(word, denied, why, tmp_path, monkeypatch, capsys):
    """🔴 here-string(`<<< 낱말`)은 heredoc 이 아니다 — 그 낱말이 본문이다. 작은따옴표면 펼치지 않는다(글자 그대로)."""
    monkeypatch.delenv("UNSET_BODY_FOR_TEST", raising=False)
    result = _hook(monkeypatch, capsys, f"gh pr comment 1 --body-file - <<< {word}", tmp_path)
    assert _denied(result) is denied and why in (_reason(result) if result else ""), result


@pytest.mark.parametrize("body, prefix, denied", [
    ("notes: $(cat notes.md)", "", True),
    ("hi $UNSET_BODY_FOR_TEST", "", True),
    ("hi `cat notes.md`", "", True),
    ("hi $B", "B=ok; ", False),
    ("plain text, costs $5", "", False),
], ids=["command-substitution", "unset-variable", "backtick", "literal-assignment", "no-reference"])
def test_an_unquoted_heredoc_body_is_judged_after_expansion(body, prefix, denied, tmp_path, monkeypatch, capsys):
    """🔴 따옴표 없는 끝 표시(`<<EOF`)의 본문은 bash 가 펼친다 — 펼친 값을 못 재면 막는다. 인라인 글과 같은 규칙이다."""
    monkeypatch.delenv("UNSET_BODY_FOR_TEST", raising=False)
    (tmp_path / "notes.md").write_text("clean", encoding="utf-8")
    result = _hook(monkeypatch, capsys, f"{prefix}gh pr create --title t --body-file - <<EOF\n{body}\nEOF", tmp_path)
    assert _denied(result) is denied, result


def test_a_cat_heredoc_piped_into_gh_is_measured(tmp_path, monkeypatch, capsys):
    """파이프 앞 단계가 heredoc 하나만 받는 `cat` 이면 stdin 은 그 heredoc 본문이다 — 깨끗하면 통과, 꼴이 있으면 막는다.
    앞 단계에 다른 인자가 붙으면(`cat <<EOF 파일`) 본문이 어디서 오는지 모르니 막는다.
    """
    clean = "cat <<'EOF' | gh pr create --title t --body-file -\nclean body\nEOF"
    assert _hook(monkeypatch, capsys, clean, tmp_path) is None
    dirty = f"cat <<'EOF' | gh pr create --title t --body-file -\nsee {_HOME}\nEOF"
    result = _hook(monkeypatch, capsys, dirty, tmp_path)
    assert _denied(result) and "local-home-path 1" in _reason(result), result
    (tmp_path / "notes.md").write_text("clean", encoding="utf-8")
    mixed = "cat <<'EOF' notes.md | gh pr create --title t --body-file -\nclean body\nEOF"
    assert _denied(_hook(monkeypatch, capsys, mixed, tmp_path))


def test_a_quoted_heredoc_body_is_literal(tmp_path, monkeypatch, capsys):
    """대조군(뒤집기) — 끝 표시에 따옴표가 있으면 bash 는 본문을 펼치지 않는다. 같은 본문이 `<<EOF` 에서는 막히고 여기선 통과한다."""
    monkeypatch.delenv("UNSET_BODY_FOR_TEST", raising=False)
    for quote in ("'", '"'):
        command = f"gh pr create --title t --body-file - <<{quote}EOF{quote}\nhi $UNSET_BODY_FOR_TEST and $(not run)\nEOF"
        assert _hook(monkeypatch, capsys, command, tmp_path) is None, quote


@pytest.mark.parametrize("command", [
    "gh pr create --title t --body-file - <<\\EOF\nbody\nEOF",
    "gh pr create --title t --body-file - <<'END-OF'\nbody\nEND-OF",
], ids=["backslash-delimiter", "dashed-delimiter"])
def test_a_heredoc_the_scanner_cannot_parse_is_denied(command, tmp_path, monkeypatch, capsys):
    """🔴 이 검사가 끝 표시를 못 읽는 heredoc 이 본문(stdin)이면 그 본문을 잰 적이 없다 — 막는다(못 재면 red)."""
    result = _hook(monkeypatch, capsys, command, tmp_path)
    assert _denied(result) and "못" in _reason(result), result


def test_only_assignments_before_the_gh_call_count(tmp_path, monkeypatch, capsys):
    """변수는 gh 호출 **앞**의 대입으로만 푼다 — 뒤의 대입이 다른 파일을 가리켜도 앞 값을 쓴다(보안 검토 ④)."""
    (tmp_path / "dirty").mkdir()
    (tmp_path / "clean").mkdir()
    (tmp_path / "dirty" / "n.md").write_text(_PLANTED["email"], encoding="utf-8")
    (tmp_path / "clean" / "n.md").write_text("ok", encoding="utf-8")
    command = f'S="{(tmp_path / "dirty").as_posix()}"; gh pr create --body-file "$S/n.md"; S="{(tmp_path / "clean").as_posix()}"'
    assert _denied(_hook(monkeypatch, capsys, command, tmp_path))


def test_a_home_path_in_an_inline_body_is_caught(tmp_path, monkeypatch, capsys):
    """인라인 본문 · 제목 안의 홈 경로는 잡는다 — 명령의 파일 인자로 쓴 경로만 빼고(보안 검토 ⑤)."""
    result = _hook(monkeypatch, capsys, f'gh pr comment 3 --body "log at {_HOME}"', tmp_path)
    assert _denied(result) and "local-home-path 1" in _reason(result), result


def test_a_mailto_address_is_caught_but_url_credentials_are_not_double_counted():
    """`mailto:` 주소도 사람 주소다. DB 주소의 `비밀번호@호스트` 는 이메일로 다시 세지 않는다(보안 검토 ⑥)."""
    assert scan.count_kinds(f"write mailto:{_EMAIL}") == {"email": 1}
    assert scan.count_kinds(_DB_URL) == {"db-url-with-password": 1}


@pytest.mark.parametrize("prefix", ["pushd {d} && ", "Set-Location {d}; ", "(cd {d} && true); ", "cd - && "],
                         ids=["pushd", "set-location", "subshell-cd", "cd-dash"])
def test_a_relative_body_path_after_an_unmodelled_directory_change_is_denied(prefix, tmp_path, monkeypatch, capsys):
    """디렉터리를 모르는 방법으로 바꿨으면 상대 경로는 못 잰다 — 막고 절대 경로를 요구한다(보안 검토 ⑦)."""
    (tmp_path / "note.md").write_text("clean", encoding="utf-8")
    command = prefix.format(d=tmp_path.as_posix()) + "gh pr create --body-file note.md"
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
