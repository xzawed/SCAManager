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
import subprocess
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
    # 11-26 세션에서 막힌 정직한 명령 — ref 이름 패턴만 받는 git 하위 명령은 파일을 읽지도 값을 내지도 않는다.
    # Denied in the 11-26 session: git subcommands that take only ref-name patterns read no file and print no value.
    "git-branch-list-glob": 'git branch --list "grok/*"',
    "git-for-each-ref-glob": "git for-each-ref --format='%(refname:short)' 'refs/heads/grok/*'",
    "git-show-ref-glob": 'git show-ref "grok/*"',
    # 패턴 자리를 엄격히 짚은 뒤에도 남아야 하는 정직한 꼴 — 출력 리디렉션 · rg · 다음 단계로 넘기기.
    # Honest shapes that must survive the stricter pattern slot: output redirects, rg, piping onward.
    "pattern-mentions-dotenv-recursive-stderr": 'grep -rn "\\.env" docs/ 2>/dev/null',
    "rg-pattern-mentions-dotenv": 'rg -n "\\.env" docs',
    "pattern-mentions-dotenv-piped": 'grep -n "\\.env" docs/a.md | head -5',
    # 따옴표를 모르는 글자 휴리스틱이 막았던 정직한 꼴(교차 검토 3차) — 패턴 속 빈 따옴표 · `'\''` 관용구 ·
    # 이스케이프한 따옴표 · `<` 로 시작하는 따옴표 안 패턴 · 깨끗한 폴더의 `{}` 검색.
    # Honest shapes a quote-blind text heuristic denied (round 3).
    "nested-empty-quotes-in-pattern": "rg 'default=\"\"' src/",
    "nested-single-quotes-in-pattern": "grep -rn \"x == ''\" src/",
    "single-quote-escape-idiom": "grep -rn 'don'\\''t' docs/",
    "escaped-quotes-in-recursive-pattern": 'grep -rn "\\"quoted\\"" docs/',
    "quoted-pattern-starting-with-redirect": "grep -n '<.env.local' docs/a.md",
    "brace-pattern-over-a-clean-folder": 'grep -rn "{}" docs/',
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
    "pipe-inside-parameter-expansion": "printenv ${UNSET:-|} grep -c SOME_KEY",
    "count-stage-with-leading-junk": "env | } grep -c SOME_KEY",
    "count-stage-reading-a-file-too": "env | grep -c SOME_KEY .env",
    # Grok 반례(따옴표 신뢰) — 큰따옴표 안 `$(…)` 의 파이프는 분할기가 못 보지만, 치환 안 글자는 따로 떼어 판정한다.
    # Grok counterexample: a pipe inside "$(…)" is invisible to the splitter, but substitution bodies are judged on their own.
    "pipe-inside-quoted-command-substitution": 'echo "$(env | grep SOME_KEY)"',
    # AntiGravity 교차 검토 반례 — 패턴 자리를 잘못 짚으면 .env 가 «패턴» 으로 빠진다: 빈 낱말 · 껍데기뿐인 패턴 ·
    # 빈 옵션 값 · 붙여 쓴 입력 리디렉션 · 명령 자리가 아닌 검색어 · 공백이나 리디렉션을 품은 옵션 값.
    # AntiGravity counterexamples: a misplaced pattern slot drops .env as "the pattern".
    "empty-pattern-then-dotenv": 'grep "" .env',
    "empty-pattern-line-numbers": "grep -n '' .env",
    "rg-empty-pattern": 'rg "" .env',
    "empty-regexp-value": 'grep -e "" .env',
    "wrapper-only-pattern": 'grep -E "()" .env',
    "empty-option-value": 'grep --label "" KEY .env',
    "rg-empty-replace-value": 'rg -r "" "API_KEY=" .env',
    "unspaced-stdin-redirect": "grep <.env KEY",
    "fd-stdin-redirect": "grep 0<.env KEY",
    "search-word-as-argument-of-git-diff": "git diff rg .env",
    "search-word-as-argument-of-cat": "cat ./rg .env",
    "search-word-as-argument-of-head": "head -n 20 grep .env",
    "search-word-then-piped-onward": "ls grep .env | xargs cat",
    "option-value-holding-a-redirect": 'grep --label "x >" KEY .env',
    "option-value-holding-an-exclude": 'grep --label "x --exclude" KEY .env',
    # 이름만 · 개수만 중화의 틈 — printenv 에 이름을 주면 «값» 한 줄만 낸다(`cut` 은 main 때부터 샜다) · 믿을 수 없는
    # 따옴표 · extglob 안의 `|` 는 파이프가 아니다. Names-only needs KEY=VALUE lines; untrusted quotes or extglob are no pipe.
    "printenv-one-value-names-only": "printenv SOME_KEY | grep -o '^[A-Za-z0-9_-]*='",
    "printenv-one-value-cut": "printenv SOME_KEY | cut -d= -f1",
    "untrusted-quotes-spoof-a-count-stage": "printenv SECRET_KEY '\\\"|wc -l|'",
    "untrusted-quotes-spoof-a-cut-stage": "printenv SECRET_KEY '\\\"|cut -d= -f1|'",
    "extglob-bar-is-not-a-pipe": "printenv SECRET_KEY @(a|wc -l|b)",
    # 내용을 안 낸다던 git 하위 명령도 stdin 을 받으면 그 줄을 낸다(Grok · AntiGravity 공통 · check-ignore 는 main 때부터).
    # "Content-free" git subcommands echo stdin lines: show-ref --exclude-existing, check-ignore --stdin -n -v.
    "show-ref-filtering-dotenv-from-stdin": "git show-ref --exclude-existing < .env",
    "check-ignore-echoing-dotenv-from-stdin": "git check-ignore --stdin -n -v < .env",
    # 빈 패턴이 빠지면 재귀 검색의 첫 대상이 «패턴» 이 된다(main 때부터) / an empty pattern shifted the first target.
    "recursive-empty-pattern-over-dotenv-folder": 'grep -rn "" . docs/',
    # AntiGravity 2차 — 붙여 쓴 입력 리디렉션 뒤 .env.* · 따옴표 앞 백슬래시(`\"`)를 / 로 바꿔 뒤집힌 따옴표 짝 ·
    # 재귀 검색의 껍데기뿐인 패턴 · 이스케이프한 `\>` 와 읽기-쓰기 `<>` 는 쓰기 리디렉션이 아니다.
    # AntiGravity round 2: unspaced `<.env.*`, quote parity flipped by `\"`, wrapper-only recursive patterns, `\>` and `<>`.
    "unspaced-stdin-redirect-dotenv-local": "grep <.env.local KEY",
    "fd-stdin-redirect-dotenv-production": "grep 0<.env.production KEY",
    "cat-unspaced-stdin-dotenv-local": "cat <.env.local",
    "show-ref-unspaced-stdin-dotenv-local": "git show-ref --exclude-existing <.env.local",
    "escaped-quotes-swallow-dotenv": 'grep -e "KEY=\\"" .env -e "SECRET=\\""',
    "recursive-escaped-quotes-swallow-target": 'grep -rn -e "KEY\\"" . -e "SECRET\\"" docs/',
    "recursive-wrapper-only-pattern": 'grep -rn -E "()" . docs/',
    "recursive-brace-pattern": 'grep -rn "{}" . docs/',
    "escaped-redirect-is-literal": "grep KEY\\> .env",
    "read-write-redirect-reads": "cat <>.env",
    # 3차(AntiGravity · Grok) — 따옴표 없는 `{}` 도 낱말 나누기에서 사라졌다 · 낱말 바로 뒤에 붙은 `<` 도 리디렉션이다.
    # Round 3: an unquoted `{}` vanished too; a `<` glued right after a word is still a redirection.
    "recursive-unquoted-brace-pattern": "grep -rn {} . docs/",
    "unspaced-redirect-after-a-word": "cat<.env.local",
    "unspaced-redirect-after-an-option": "grep -i<.env KEY",
}


@pytest.mark.parametrize("name", sorted(_MUST_PASS))
def test_honest_shapes_that_were_denied_now_pass(name, workdir):
    """🔴 막혔던 정직한 꼴은 통과한다(오탐 회귀 코퍼스)."""
    assert _verdict(_MUST_PASS[name], workdir) is None, (name, _verdict(_MUST_PASS[name], workdir))


@pytest.mark.parametrize("name", sorted(_MUST_BLOCK))
def test_their_dangerous_twins_are_still_denied(name, workdir):
    """대조군(뒤집기) — 같은 꼴의 위험한 짝은 그대로 막는다. «검색이면 통과» 같은 싼 완화는 여기서 걸린다."""
    assert _verdict(_MUST_BLOCK[name], workdir) is not None, name


# Bash 의 `\"` 이스케이프에 기대는 짝 — PowerShell 의 백슬래시는 이스케이프가 아니라(`"K=\"` 는 거기서 닫힌 문자열)
# 그 셸에서는 .env 가 패턴 문자열 안에 든다. Twins that rely on Bash's `\"` escape; in PowerShell `\` is literal.
_BASH_ESCAPE_ONLY = frozenset({"escaped-quotes-swallow-dotenv", "recursive-escaped-quotes-swallow-target"})


def test_the_dangerous_twins_are_denied_in_powershell_mode_too(workdir):
    """PowerShell 이 기본 셸이다 — 셸 모드(글롭 · 따옴표 해석)가 갈라도 위험한 짝은 다 막는다(AntiGravity 교차 검토).
    PowerShell is the default shell; every dangerous twin stays denied in that mode as well."""
    allowed = [name for name, command in sorted(_MUST_BLOCK.items())
               if name not in _BASH_ESCAPE_ONLY and hook.decide_with_hint(command, str(workdir), "powershell") is None]
    assert not allowed, allowed


def test_a_powershell_backslash_is_never_an_escape(workdir):
    """🔴 PowerShell 에서 `\\` 는 경로 구분자다 — Bash 처럼 `\\"` 를 이스케이프로 읽으면 `"docs\\" , .env , "src\\"` 의
    따옴표 짝이 뒤집혀 .env 가 문자열 안으로 삼켜지고(구멍), 끝이 `\\` 인 폴더(`"docs\\"`)는 낱말 나누기가 깨져 막힌다
    (오탐 · AntiGravity 3차). In PowerShell a backslash is a path separator, never an escape."""
    for command in ('Get-Content "docs\\" , .env , "src\\"', 'Select-String -Path "docs\\" , ".env" , "src\\" -Pattern KEY'):
        assert hook.decide_with_hint(command, str(workdir), "powershell") is not None, command
    for command in ('rg "KEY" "docs\\"', 'cd "docs\\" ; rg KEY .'):
        assert hook.decide_with_hint(command, str(workdir), "powershell") is None, command


# witness-corpus: 덤프 뒤 «개수만 · 아무것도 안 냄» 단계 가운데 판정식(grep -c/-q/-l · wc 개수 플래그) 밖의 꼴
_UNLISTED_COUNT_ONLY_STAGES = ["awk 'END {print NR}'", "tail -n 0", "wc -l --", "wc --lines -- -"]


@pytest.mark.parametrize("stage", _UNLISTED_COUNT_ONLY_STAGES)
def test_an_unlisted_count_only_stage_does_not_neutralize_a_dump(stage, workdir):
    """🔴 목록 밖의 «개수만» 단계는 덤프를 중화하지 않는다 — 값을 안 낸다고 판정식이 확인하지 못한 꼴은 막는다
    (fail-closed · 드문 오탐). An unlisted count-only stage does not neutralize an env dump."""
    assert _verdict(f"env | {stage}", workdir) is not None


# witness-corpus: 검색 명령의 긴 옵션 가운데 카탈로그(_KNOWN_SEARCH_LONGS) 밖의 것 — 값을 받는지 모른다
_UNLISTED_SEARCH_LONGS = ["--devices skip", "--directories skip", "--exclude-from list.txt"]


@pytest.mark.parametrize("option", _UNLISTED_SEARCH_LONGS)
def test_an_unknown_long_option_keeps_the_pattern_as_a_path(option, workdir):
    """🔴 모르는 긴 옵션이 있으면 어느 낱말이 패턴인지 모른다 — 패턴의 `\\.env` 도 경로로 보고 막는다(fail-closed)."""
    assert _verdict(f'grep {option} -n "\\.env" docs/a.md', workdir) is not None


# witness-corpus: 출력 리디렉션 문법 가운데 판정식(_OUTPUT_REDIRECT) 밖의 꼴 — 검색 대상에서 걷어 내지 못한다
_UNLISTED_OUTPUT_REDIRECTS = [">| out.txt", "2>&-"]


@pytest.mark.parametrize("redirect", _UNLISTED_OUTPUT_REDIRECTS)
def test_an_unlisted_output_redirect_fails_closed(redirect, workdir):
    """대조군 — 판정식이 모르는 리디렉션은 걷지 않아 막는 쪽으로 간다(.env 없는 폴더라도 · 드문 오탐)."""
    assert _verdict(f"grep -rn foo docs/ {redirect}", workdir) is not None


# witness-corpus: 파이프처럼 보이지만 파이프가 아닌 `|` 가운데 판정식(`${` · `$'`) 밖의 꼴 — 산술 OR
_UNLISTED_NON_PIPE_BARS = ["$((1|2))", "$((0|1))"]


@pytest.mark.parametrize("bar", _UNLISTED_NON_PIPE_BARS)
def test_a_bar_inside_arithmetic_does_not_neutralize_a_dump(bar, workdir):
    """🔴 산술 안의 `|` 는 파이프가 아니다 — 그 뒤를 «개수만» 단계로 읽어 덤프를 중화하지 않는다(단계 통째 일치가 막는다)."""
    assert _verdict(f"printenv {bar} grep -c SOME_KEY", workdir) is not None


# witness-corpus: ref 이름만 다루는 git 하위 명령 가운데 목록 밖 — ls-remote(`--upload-pack` 이 명령을 돌린다) · describe
_UNLISTED_GIT_REF_COMMANDS = ['ls-remote origin "grok/*"', 'describe --all "grok/*"']


@pytest.mark.parametrize("command", _UNLISTED_GIT_REF_COMMANDS)
def test_an_unlisted_git_subcommand_with_a_glob_stays_denied(command, workdir):
    """대조군(뒤집기) — 목록에 넣은 ref 명령(branch · for-each-ref · show-ref)만 풀린다. 목록 밖은 글롭이 있으면 그대로 막는다
    («git 이면 통과» 같은 싼 완화를 거른다)."""
    assert _verdict(f"git {command}", workdir) is not None


def test_a_file_reading_option_of_a_ref_command_is_still_denied(workdir):
    """대조군 — ref 명령이라도 파일을 읽는 옵션은 그대로 막는다(`git tag -F .env` 는 .env 를 태그 메시지로 읽는다)."""
    assert _verdict("git tag -a v9 -F .env", workdir) is not None


def _git_repo(path, ignored):
    """임시 git 저장소 — .gitignore 에 `ignored` 이름들 / a scratch repository ignoring the given names."""
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    (path / ".gitignore").write_text("".join(f"{name}\n" for name in ignored), encoding="utf-8")


def test_rg_reads_a_dotenv_that_git_does_not_ignore(tmp_path):
    """🔴 rg 는 숨김 · .gitignore 파일을 건너뛸 뿐이다 — 무시되지 않은 prod.env 는 기본값으로도 읽는다(Grok 반례
    `rg -e .env -e SYNTHETIC .`). 무시 여부는 가정하지 않고 git 에 묻는다.
    rg skips only hidden and ignored files; an unignored prod.env is read by default, so ask git."""
    _git_repo(tmp_path, [".env"])
    (tmp_path / ".env").write_text("SYNTHETIC_KEY=x\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "prod.env").write_text("SYNTHETIC_KEY=x\n", encoding="utf-8")
    for command in ("rg -e .env -e SYNTHETIC .", "rg SYNTHETIC ."):
        assert _verdict(command, tmp_path) is not None, command
    # 대조군 — git 이 무시하는 파일은 rg 도 건너뛴다 / control: files git ignores are skipped
    (tmp_path / ".gitignore").write_text(".env\nprod.env\n", encoding="utf-8")
    assert _verdict("rg SYNTHETIC .", tmp_path) is None


def test_rg_hidden_reads_only_the_dotenv_files_git_does_not_ignore(tmp_path):
    """--hidden 은 숨김 파일을 열 뿐 .gitignore 는 지킨다 — 무시된 .env 는 통과(이 리포의 꼴), 무시되지 않은
    .env.production 은 막는다. --hidden still honours .gitignore."""
    _git_repo(tmp_path, [".env"])
    (tmp_path / ".env").write_text("SYNTHETIC_KEY=x\n", encoding="utf-8")
    assert _verdict("rg --hidden SYNTHETIC .", tmp_path) is None
    (tmp_path / ".env.production").write_text("SYNTHETIC_KEY=x\n", encoding="utf-8")
    assert _verdict("rg --hidden SYNTHETIC .", tmp_path) is not None


def test_rg_reads_inside_an_ignored_folder_it_is_pointed_at(tmp_path):
    """🔴 rg 는 이름을 준 폴더 안을 그 폴더가 gitignore 돼 있어도 읽는다 — git 은 그 안의 파일을 «무시됨» 으로 답하므로
    대상 폴더 자체가 무시되면 git 의 답을 믿지 않는다(AntiGravity 2차). 대조군: 저장소 루트의 `rg KEY .` 은 무시된
    폴더로 내려가지 않는다. rg searches inside an ignored folder it is pointed at, though git reports its files ignored."""
    _git_repo(tmp_path, ["secrets/"])
    (tmp_path / "secrets").mkdir()
    (tmp_path / "secrets" / "prod.env").write_text("SYNTHETIC_KEY=x\n", encoding="utf-8")
    assert _verdict("rg SYNTHETIC secrets", tmp_path) is not None
    assert _verdict("rg SYNTHETIC .", tmp_path / "secrets") is not None
    assert _verdict("rg SYNTHETIC .", tmp_path) is None


def test_rg_outside_a_git_repository_honours_no_gitignore(tmp_path, monkeypatch):
    """저장소 밖의 rg 는 .gitignore 를 보지 않는다 — 거기 적혀 있어도 prod.env 를 읽는다(막는 쪽). 위 폴더가 우연히
    저장소여도 시험이 흔들리지 않게 git 이 tmp_path 위로 올라가지 못하게 한다.
    Outside a repository rg ignores .gitignore, so a listed prod.env is still read."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    (tmp_path / ".gitignore").write_text("prod.env\n", encoding="utf-8")
    (tmp_path / "prod.env").write_text("SYNTHETIC_KEY=x\n", encoding="utf-8")
    assert _verdict("rg SYNTHETIC .", tmp_path) is not None


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


def test_a_production_denial_record_keeps_no_command_word(tmp_path, monkeypatch, capsys):
    """🔴 운영 거부 사유는 명령 낱말(하위 명령 자리에 온 값 · 둘째 낱말)을 품는다 — 기록에는 정적인 범주만 남긴다
    (AntiGravity 반례: `railway --token 값 status` 의 값이 사유째 기록됐다). 안내문(에이전트에게 보이는 사유)은 그대로다.
    Production reasons embed command words; the record keeps only the static category."""
    log = tmp_path / "denials.jsonl"
    monkeypatch.setenv("SCAMANAGER_HOOK_LOG", str(log))
    for command in ("railway --token SYNTHETIC_MARKER_123 status", "railway service --token SYNTHETIC_MARKER_123 list",
                    "railway domain SYNTHETIC_MARKER_123"):
        out = _run_main(monkeypatch, capsys, {"tool_name": "Bash", "tool_input": {"command": command}})
        assert '"permissionDecision": "deny"' in out, command
    records = _records(log)
    assert [r["kind"] for r in records] == ["production"] * 3, records
    assert all(r["reason"] for r in records), records
    assert "synthetic_marker_123" not in log.read_text(encoding="utf-8").lower(), "명령 낱말이 기록에 남았다"


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
