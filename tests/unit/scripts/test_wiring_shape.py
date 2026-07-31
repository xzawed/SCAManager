"""배선 판정 술어 `tests/unit/scripts/_wiring_shape.py` 의 계약 — **호출 형태**를 강제하는가.

## 왜 만드나 (2026-07-31 Grok claim-review + 뮤테이션 실측)

배선 가드 10곳이 전부 `"<경로>" in <명령>` **substring** 으로 배선을 판정했다. 그래서 명령을
`echo scripts/check_x.py` 로 바꿔 **실행만 제거**해도 경로 문자열이 남아 전부 초록이었다.
실측(격리 worktree, `assert mutated != orig` 증명, `tests/unit/scripts`+`tests/unit/hooks`
498건 전체 실행): 뮤테이션 12건 중 **11건이 GREEN**(단 한 건도 red 로 전환되지 않음).

AGENTS.md 불변식 1 은 이 형태를 명시적으로 금지한다 — *"substring/`X in source` 검사 금지.
산문이 통과시킬 수 있으면 그 가드는 fail-open 이다."* 가드들이 자신이 강제하려던 규칙을 범했다.

🔴 이 파일은 **부정 통제가 본체**다. 실제 배선을 인정하는 것(양성)보다, **실행되지 않는
데코이를 거부하는 것**(음성)이 이 술어의 존재 이유다.

Contract for the wiring predicate: an invocation must actually run the script. The prior
substring form let `echo scripts/check_x.py` pass — 11 of 12 real-path mutations stayed green.
"""
import pytest

from tests.unit.scripts._wiring_shape import any_invokes, invokes, surface_invokes

_P = "scripts/check_fake_guard.py"
_HOOK = ".claude/hooks/fake_hook.py"


# ── 양성 통제 — 실제 호출은 배선으로 인정해야 한다 ──────────────────────
# Positive control — real invocations must count as wired.

@pytest.mark.parametrize("command", [
    "python scripts/check_fake_guard.py",
    "python3 scripts/check_fake_guard.py",
    "py -3 scripts/check_fake_guard.py",
    # PR #1243 이 훅 command 6종을 이 형태로 재작성했다 — 반드시 배선으로 인정돼야 한다.
    # #1243 rewrote six hook commands into this shape; it must still count as wired.
    "PY=$(command -v py >/dev/null 2>&1 && echo 'py -3' || echo python3); "
    "$PY scripts/check_fake_guard.py",
    # 인자·리다이렉트가 붙어도 호출은 호출 / arguments and redirects don't change the verdict
    'python scripts/check_fake_guard.py "${{ github.event.pull_request.base.sha }}" HEAD',
    "python scripts/check_fake_guard.py 2>&1",
    # 복합 명령의 뒷 세그먼트 / later segment of a compound command
    "set -e && python scripts/check_fake_guard.py",
    # 인라인 주석이 붙어도 앞의 실제 호출은 남는다 / inline comment must not erase the call
    "python scripts/check_fake_guard.py  # 실행",
])
def test_real_invocation_counts_as_wired(command):
    assert invokes(command, _P) is True, f"실제 호출을 배선으로 못 잡았다: {command!r}"


def test_hook_path_invocation_counts():
    assert invokes(f"python {_HOOK}", _HOOK) is True


# ── 🔴 부정 통제 — 실행하지 않는 데코이는 거부해야 한다 (이 파일의 본체) ──
# Negative control — non-executing decoys must be rejected. This is the point of the module.

@pytest.mark.parametrize("command", [
    # 🔴 실측 뮤테이션 GROK-20260731-1/2/3/4/5/6/7 이 정확히 이 형태로 11건 통과했다.
    # The exact shape that let 11 measured mutations stay green.
    "echo scripts/check_fake_guard.py",
    "echo 'skipping scripts/check_fake_guard.py'",
    'echo "would run scripts/check_fake_guard.py"',
    "true  # scripts/check_fake_guard.py",
    ":  scripts/check_fake_guard.py",
    "cat scripts/check_fake_guard.py",
    "ls -l scripts/check_fake_guard.py",
    "printf 'scripts/check_fake_guard.py'",
    # 실행자 오타 — 조용히 아무것도 실행하지 않는다 / typo'd interpreter runs nothing
    "pythn scripts/check_fake_guard.py",
    # 언급만 / mere mention
    "# python scripts/check_fake_guard.py",
    "name: scripts/check_fake_guard.py 는 중요하다",
    "",
])
def test_non_executing_decoy_is_not_wired(command):
    assert invokes(command, _P) is False, (
        f"실행하지 않는 데코이를 배선으로 오판 — fail-open 재발: {command!r}"
    )


def test_other_script_invocation_does_not_count():
    """다른 스크립트를 실행하는 명령은 이 스크립트의 배선이 아니다."""
    assert invokes("python scripts/check_other.py", _P) is False


def test_unparseable_command_is_not_wired():
    """🔴 파싱 실패는 fail-closed — '모르겠으면 배선 아님'."""
    assert invokes('python "unbalanced scripts/check_fake_guard.py', _P) is False


# ── any_invokes — 목록 판정 ──────────────────────────────────────────────

def test_any_invokes_true_when_one_real_call():
    cmds = ["echo scripts/check_fake_guard.py", "python scripts/check_fake_guard.py"]
    assert any_invokes(cmds, _P) is True


def test_any_invokes_false_when_all_decoys():
    cmds = ["echo scripts/check_fake_guard.py", "true  # scripts/check_fake_guard.py"]
    assert any_invokes(cmds, _P) is False


def test_any_invokes_false_on_empty():
    """대조군 — 빈 목록은 배선 아님(공허 통과 차단)."""
    assert any_invokes([], _P) is False


# ── surface_invokes — 원시 표면 텍스트(YAML/JSON) 판정 ───────────────────

def test_surface_yaml_run_block_is_wired():
    text = "jobs:\n  x:\n    steps:\n      - run: python scripts/check_fake_guard.py\n"
    assert surface_invokes(text, _P) is True


def test_surface_precommit_entry_is_wired():
    text = "  - id: fake\n    entry: python scripts/check_fake_guard.py\n"
    assert surface_invokes(text, _P) is True


def test_surface_multiline_run_block_is_wired():
    text = "      - run: |\n          set -e\n          python scripts/check_fake_guard.py\n"
    assert surface_invokes(text, _P) is True


def test_surface_backslash_continuation_is_wired():
    """🔴 백슬래시 줄 연결 — `codeql.yml` 의 **실제** 배선 형태.

    초판은 이 형태에서 고립된 `\\` 때문에 `shlex` 가 ValueError 를 냈고, fail-closed 규칙에 걸려
    **실배선을 미배선으로 오판**했다(가드 자살). 술어를 켜자마자 드러난 회귀라 여기 고정한다.
    The real wiring shape in codeql.yml; a dangling escape once made the predicate reject it.
    """
    text = (
        "      - name: gate\n"
        "        run: |\n"
        "          python scripts/check_fake_guard.py \\\n"
        '            "${{ github.repository }}" \\\n'
        '            "${{ github.event.pull_request.number }}"\n'
    )
    assert surface_invokes(text, _P) is True


def test_surface_json_command_is_wired():
    text = '{"hooks": {"SessionStart": [{"hooks": [{"command": "python scripts/check_fake_guard.py"}]}]}}'
    assert surface_invokes(text, _P) is True


def test_surface_json_py_launcher_command_is_wired():
    """🔴 #1243 이 도입한 `PY=$(...)` 형태가 JSON 안에서도 인정돼야 한다."""
    text = (
        '{"hooks": {"SessionStart": [{"hooks": [{"command": '
        '"PY=$(command -v py >/dev/null 2>&1 && echo \'py -3\' || echo python3); '
        '$PY scripts/check_fake_guard.py"}]}]}}'
    )
    assert surface_invokes(text, _P) is True


@pytest.mark.parametrize("text", [
    # 🔴 뮤테이션 실측 형태 / the measured mutation shapes
    "      - run: echo scripts/check_fake_guard.py\n",
    '{"hooks": [{"command": "echo \'skipping scripts/check_fake_guard.py\'"}]}',
    "      # TODO: wire scripts/check_fake_guard.py 나중에\n",
    "      - name: scripts/check_fake_guard.py 를 실행하는 스텝(설명뿐)\n",
    "",
])
def test_surface_decoy_is_not_wired(text):
    assert surface_invokes(text, _P) is False, f"표면 데코이를 배선으로 오판: {text!r}"


# ── 자가 검증 — 이 술어 자신이 공허하지 않은지 ──────────────────────────
# Self-check — is this predicate itself non-vacuous?

def test_predicate_is_not_constant():
    """🔴 술어가 상수가 아님을 실증 — 항상 True/False 면 아무것도 판정하지 않는다."""
    assert invokes("python scripts/check_fake_guard.py", _P) is True
    assert invokes("echo scripts/check_fake_guard.py", _P) is False
