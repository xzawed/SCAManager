"""credential 훅 정밀도 — 인자 속 명령 이름 · 무해 env 이름 (원장 #1940 M06 P1-23 · P1-25).
Credential-hook precision: command names inside data arguments, and harmless env names.

회고 창의 거부 기록을 세션 기록에 대 보니 정직한 명령이 대부분이었고, 같은 꼴이 HEAD 에서도 막혔다.
- `grep -rn popd e2e` — grep 의 패턴 `popd` 를 디렉터리 되돌리기로 읽어 작업 폴더를 «모름» 으로 만들고 막았다.
- `grep -n "printenv" 시험.py` — 패턴 속 `printenv` 를 env 덤프로 읽었다.
- `env | grep -i "^PYTHON"` · `printenv PYTHONUTF8` — 무해한 이름 하나를 골라도 덤프로 막았다.
사용자 결정(11-28): «무해 이름 목록만 허용» — PYTHON* · LANG · LC_* · CLAUDE_PROJECT_* · MSYS* · TEMP/TMP · TERM · SHELL · PATH.
"""
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / ".claude" / "hooks"))
import block_credential_dump as hook  # noqa: E402


@pytest.fixture
def repo(tmp_path):
    """`.env` 꼴이 없는 작업 폴더 — e2e · tests 아래에 파이썬 파일만 / a cwd with no .env-like file."""
    for folder in ("e2e", "tests"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "test_x.py").write_text("print('popd printenv cd')\n", encoding="utf-8")
    return tmp_path


def _verdict(command, cwd, shell="bash"):
    return hook.decide_with_hint(command, str(cwd), shell)


# --- 1. 인자를 글자로만 받는 명령의 인자 속 명령 이름 -----------------------------------------------------------

@pytest.mark.parametrize("command", [
    pytest.param("grep -rn popd e2e", id="grep-pattern-popd"),
    pytest.param('grep -rn "popd" tests/ e2e/ --include=*.py | head -20', id="grep-pattern-popd-include"),
    pytest.param('grep -n "printenv" tests/test_x.py | head -20', id="grep-pattern-printenv"),
    pytest.param("echo popd; grep -rn x e2e", id="echo-popd-then-search"),
    pytest.param("echo printenv", id="echo-printenv"),
    pytest.param('grep -rn "cd" e2e', id="grep-pattern-cd"),
])
def test_a_command_name_inside_data_arguments_is_not_run(command, repo):
    """인자를 글자로만 받는 명령(grep · echo …)의 인자 속 `popd` · `printenv` · `cd` 는 실행이 아니다 — 막지 않는다."""
    assert _verdict(command, repo) is None, command


@pytest.mark.parametrize("command", [
    pytest.param("popd && grep -rn SECRET e2e", id="real-popd"),
    pytest.param('cd "$X" && grep -rn x e2e', id="cd-to-unknown"),
    pytest.param("printenv", id="printenv-alone"),
    pytest.param("sh -c printenv", id="printenv-in-shell-string"),
    pytest.param("grep -h printenv tests/test_x.py | sh", id="data-stage-piped-into-shell"),
    pytest.param("xargs printenv < tests/test_x.py", id="printenv-run-by-xargs"),
])
def test_a_command_name_that_runs_is_still_judged(command, repo):
    """🔴 대조군 — 명령 자리의 popd · 모르는 cd · printenv 와, 글자 단계의 출력을 셸이 돌리는 꼴은 그대로 막힌다."""
    assert _verdict(command, repo) is not None, command


# witness-corpus: 인자를 글자처럼 받지만 실행도 할 수 있는 명령 — 글자 단계 목록에 넣지 않았다(넣으면 구멍)
_RUNNING_DATA_COMMANDS = ["awk 'BEGIN{system(\"printenv\")}'", "sed -n 's/x/printenv/ep' notes.md",
                          "find . -exec printenv ;", "rg --pre printenv x ."]


@pytest.mark.parametrize("command", _RUNNING_DATA_COMMANDS)
def test_data_looking_commands_that_can_run_their_arguments_are_not_exempt(command, repo):
    """🔴 awk · sed(e) · find -exec · rg --pre 는 인자를 실행한다 — 인자 속 printenv 를 그대로 막는다."""
    assert _verdict(command, repo) is not None, command


# --- 2. 무해 env 이름(사용자 결정 11-28) ------------------------------------------------------------------------

@pytest.mark.parametrize("command", [
    pytest.param('env | grep -i "^PYTHON"', id="env-grep-python-prefix"),
    pytest.param("env | grep '^LANG='", id="env-grep-exact-lang"),
    pytest.param("env | grep -e '^PYTHON' -e '^LC_'", id="env-grep-two-prefixes"),
    pytest.param("env | grep -E '^CLAUDE_PROJECT_MEMORY_DIR='", id="env-grep-claude-project"),
    pytest.param("printenv PYTHONUTF8", id="printenv-python"),
    pytest.param("printenv LANG TERM", id="printenv-two-exact"),
    pytest.param("command printenv MSYS_NO_PATHCONV", id="printenv-msys-with-prefix"),
])
def test_a_harmless_env_name_may_be_read(command, repo):
    """무해 이름 목록(PYTHON* · LANG · LC_* · CLAUDE_PROJECT_* · MSYS* · TEMP/TMP · TERM · SHELL · PATH)만 정확히 고르면 통과."""
    assert _verdict(command, repo) is None, command


# witness-corpus: 무해 목록 밖의 이름 · 목록 이름을 넓게 고르는 꼴 — 값이 비밀일 수 있다
_NOT_HARMLESS_READS = ["printenv GH_TOKEN", "printenv DATABASE_URL", "env | grep '^GIT_'",
                       "env | grep -i 'railway'", "printenv RAILWAY_API_TOKEN"]


@pytest.mark.parametrize("command", _NOT_HARMLESS_READS)
def test_an_env_name_outside_the_list_is_still_a_dump(command, repo):
    """🔴 목록 밖 이름은 그대로 덤프다(GIT_* 도 — 토큰을 담는 변수가 있다)."""
    assert _verdict(command, repo) is not None, command


@pytest.mark.parametrize("command", [
    pytest.param("env | grep '^LANG'", id="exact-name-without-equals-also-picks-LANGUAGE"),
    pytest.param("env | grep -i CLAUDE_PROJECT_MEMORY_DIR", id="unanchored-matches-values-too"),
    pytest.param("env | grep -E '^PYTHON|TOKEN'", id="alternation"),
    pytest.param("env | grep -v '^PYTHON'", id="inverted"),
    pytest.param("env | grep -A2 '^PYTHON'", id="context-lines"),
    pytest.param("env | grep '^PYTHON' notes.md", id="file-argument"),
    pytest.param("env | grep '^PYTHON' '^LC_'", id="second-word-is-a-file-not-a-pattern"),
    pytest.param("printenv PYTHONUTF8 GH_TOKEN", id="one-name-outside-the-list"),
    pytest.param("railway variables --kv | grep '^PYTHON'", id="railway-service-variables"),
    # Grok(642a337b) 반례 — 실측으로 막힘을 단언한다 / Grok's counterexamples, asserted blocked
    pytest.param("echo >(printenv SECRET)", id="printenv-in-process-substitution-of-a-data-stage"),
    pytest.param("env | grep -E '^PYTHON|.*'", id="alternation-widening-to-everything"),
    pytest.param("env | grep -E '^PYTHON|.*' < .env", id="alternation-over-dotenv"),
    pytest.param("env | grep '^PYTHON' -e '.*'", id="plain-word-beside-e-pattern"),
    pytest.param("env | tee /dev/stderr | grep '^PYTHON'", id="grep-not-the-very-next-stage"),
])
def test_a_wide_or_bent_selection_is_still_a_dump(command, repo):
    """🔴 줄 머리에 고정하지 않은 · 여러 갈래 · 뒤집기 · 앞뒤 줄 · 파일 인자 · 목록 밖 이름이 섞인 고르기와 railway 변수는 덤프다."""
    assert _verdict(command, repo) is not None, command
