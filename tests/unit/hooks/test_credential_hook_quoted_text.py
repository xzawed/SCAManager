"""credential 훅 — 따옴표 안 글자는 펼치지 않는다 (회고 원장 R-5).

Bash 는 따옴표 안의 `*` · `?` · `[` 를 글롭으로 펼치지 않는다. 훅이 그 글자를 경로 글롭으로 보아 검색 정규식이
«.env 읽기» 로 막혔다. 고친 판정은 펼치지도 실행하지도 않는 글자 처리 명령으로 파이프라인 끝까지 이어진 단계에서만
그 글자를 글자 그대로 본다. 이 파일이 고정하는 것:

1. 오탐이던 꼴(글자 처리 명령의 따옴표 안 정규식 · 글자)이 통과한다.
2. 따옴표가 지켜 주지 못하는 읽기 — 인자를 스스로 펼치는 명령 · 뒤에서 실행하는 명령 · 따옴표 밖 글롭 · 치환 ·
   PowerShell(cmdlet 이 따옴표 안도 펼친다) — 는 그대로 막힌다.
3. 표지 규칙이 단계 · 명령 · 옵션 · 리디렉션 · 믿을 수 없는 따옴표마다 뒤집힌다(판정식 뒤집기).

Quoted glob characters are literal in Bash; the hook now reads them literally only in stages that are text
tools to the end of the pipeline. Pinned: the former false positives pass, reads the quotes cannot protect stay
denied, and the marking rule flips on every axis.
"""
# pylint: disable=protected-access
import importlib.util
from pathlib import Path

import pytest

from tests.unit.hooks.test_block_credential_dump import _decide

_HOOK = Path(__file__).resolve().parents[3] / ".claude" / "hooks" / "block_credential_dump.py"


def _load_hook():
    spec = importlib.util.spec_from_file_location("block_credential_dump_for_quoted_tests", _HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MOD = _load_hook()


@pytest.fixture(name="env_dir")
def _env_dir(tmp_path):
    """점 파일 .env · 점 없는 prod.env · 보통 파일 — 맨 `*` 도 `.e*` 도 .env 꼴을 집는 폴더(예전 판정이면 막힌다).
    A folder where both a bare `*` and `.e*` hit a .env-like file."""
    for name in (".env", "prod.env", "notes.txt"):
        (tmp_path / name).write_text("PLANT=1\n", encoding="utf-8")
    return tmp_path


# 1. 오탐이던 꼴 — 이 폴더에서 예전 판정은 모두 «.env 읽기» 로 막았다.
_NOW_ALLOWED = [
    pytest.param(r"grep -n 'foo\|bar\*\*' notes.txt", id="grep-alternation-and-escaped-stars"),
    pytest.param(r'grep -nE "(a|b)\*\*" notes.txt', id="grep-double-quoted"),
    pytest.param(r"grep -n 'x\*' notes.txt | head -5", id="grep-into-head"),
    pytest.param(r"grep -o 'a\*' notes.txt | sort | uniq -c", id="grep-sort-uniq"),
    pytest.param(r"git log --oneline | grep 'fix\*'", id="text-tool-as-the-last-stage"),
    pytest.param(r"cd . && grep -n 'a\*\*' notes.txt", id="after-cd"),
    pytest.param(r"LC_ALL=C grep -n 'x\*' notes.txt 2>/dev/null", id="assignment-and-null-redirect"),
    pytest.param("echo '*'", id="echo-quoted-star"),
]

# 2. 따옴표가 지켜 주지 못하는 읽기 — 그대로 막는다.
_STILL_DENIED = [
    pytest.param("Bash", "cat '.env'", id="quoted-literal-path"),
    pytest.param("Bash", 'grep KEY ".env"', id="double-quoted-literal-path"),
    pytest.param("Bash", "cat .e*", id="unquoted-glob"),
    pytest.param("Bash", 'cat ".e"*', id="glob-outside-the-quotes"),
    pytest.param("Bash", "cat *.env", id="unquoted-name-glob"),
    pytest.param("Bash", "find . -name '.e*' -exec cat {} +", id="find-expands-its-own-pattern"),
    pytest.param("Bash", "find . -iname '.E*' -print0 | xargs -0 cat", id="find-into-xargs"),
    pytest.param("Bash", "git grep --no-index KEY -- '.e*'", id="git-pathspec"),
    pytest.param("Bash", "tar -cf - --wildcards '.e*' | tar -xOf -", id="tar-wildcards"),
    pytest.param("Bash", "echo '.e*' | xargs sh -c 'cat $0'", id="text-tool-feeding-a-shell"),
    pytest.param("Bash", "grep -l KEY '.e*' | sh", id="grep-feeding-a-shell"),
    pytest.param("Bash", 'echo "$(cat .e*)"', id="substitution-inside-quotes"),
    pytest.param("Bash", "rg -uu KEY -g '.e*'", id="rg-include-glob"),
    pytest.param("Bash", "grep -r KEY --include='.e*' .", id="grep-include-glob"),
    pytest.param("PowerShell", "Get-Content '.e*'", id="powershell-cmdlet-expands-quoted"),
    pytest.param("PowerShell", 'Get-Content ".e*"', id="powershell-double-quoted"),
]


@pytest.mark.parametrize("command", _NOW_ALLOWED)
def test_quoted_text_in_text_tools_is_not_a_glob(env_dir, command):
    """오탐이던 꼴이 통과한다 / the former false positives pass."""
    decision, reason = _decide(command, cwd=env_dir)
    assert decision != "deny", f"따옴표 안 글자를 경로 글롭으로 읽어 막았다: {command!r}\n{reason}"


@pytest.mark.parametrize(("tool", "command"), _STILL_DENIED)
def test_reads_the_quotes_do_not_protect_are_still_denied(env_dir, tool, command):
    """🔴 따옴표가 지켜 주지 못하는 읽기는 그대로 막힌다 / reads the quotes cannot protect stay denied."""
    decision, _ = _decide(command, tool_name=tool, cwd=env_dir)
    assert decision == "deny", f"막아야 할 꼴이 통과했다({tool}): {command!r}"


# 3. 표지 규칙 — 같은 따옴표 글자가 축마다 표지되거나 안 된다. 두 결과가 다 심겨 있다.
_MARK_RULES = [
    pytest.param("grep 'a*' f", True, id="text-tool"),
    pytest.param("grep 'a*' f | head -1", True, id="text-tools-to-the-end"),
    pytest.param("git log | grep 'a*'", True, id="an-earlier-stage-does-not-matter"),
    pytest.param("grep 'a*' f 2>/dev/null >&2", True, id="null-and-fd-redirects"),
    pytest.param("X='a*' grep k f", True, id="leading-assignment"),
    pytest.param("grep 'a*' f | xargs cat", False, id="a-later-stage-runs-things"),
    pytest.param("find . -name 'a*'", False, id="command-expands-its-arguments"),
    pytest.param("grep 'a*' f > out", False, id="output-to-a-file"),
    pytest.param("printf -v x '%s' 'a*'", False, id="printf-assigns-a-variable"),
    pytest.param("sort --compress-program=gzip 'a*'", False, id="sort-runs-a-program"),
    pytest.param("X='a*'", False, id="assignment-only"),
    pytest.param("'grep' 'a*' f", False, id="quoted-command-name"),
    pytest.param("grep 'a*' \"$(cat f)\"", False, id="substitution-untrusted"),
    pytest.param("grep 'a*' f # note", False, id="comment-untrusted"),
    pytest.param("grep 'a*", False, id="unclosed-quote"),
]


@pytest.mark.parametrize(("command", "marked"), _MARK_RULES)
def test_the_mark_rule_flips_on_each_axis(monkeypatch, command, marked):
    """🔴 표지는 글자 처리 단계 · 믿을 수 있는 따옴표에만 — 축마다 두 결과가 다 나온다."""
    monkeypatch.setitem(_MOD._CONTEXT, "shell", "bash")
    assert (_MOD._mark_quoted_literals(command) != command) is marked, command


def test_only_quoted_glob_characters_are_marked(monkeypatch):
    """따옴표 밖 글롭과 따옴표 밖 이스케이프는 예전처럼 글롭이다 — 따옴표 안 글자만 표지된다."""
    monkeypatch.setitem(_MOD._CONTEXT, "shell", "bash")
    star, query = _MOD._GLOB_SENTINELS["*"], _MOD._GLOB_SENTINELS["?"]
    out = _MOD._mark_quoted_literals(r"grep 'a*' b* \* \"c?\" d")
    assert (out.count(star), out.count(query)) == (1, 0), out
    out = _MOD._mark_quoted_literals("grep \"c?\" 'a[1]' f")
    assert (out.count(query), out.count(_MOD._GLOB_SENTINELS["["])) == (1, 1), out


def test_a_marked_glob_is_read_as_a_literal_name():
    """경로 후보는 표지를 글자 그대로의 패턴으로 읽는다 — 글롭이었다면 .env 를 집는 자리다."""
    star = _MOD._GLOB_SENTINELS["*"]
    assert _MOD._path_tokens(f"grep k .e{star}") == ["grep", "k", ".e[*]"]


def test_powershell_is_never_marked(monkeypatch):
    """PowerShell 은 cmdlet 이 따옴표 안 와일드카드도 펼친다 — 표지하지 않는다."""
    monkeypatch.setitem(_MOD._CONTEXT, "shell", "powershell")
    assert _MOD._mark_quoted_literals("grep 'a*' f") == "grep 'a*' f"
