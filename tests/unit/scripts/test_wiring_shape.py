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

# `#1243` 이 훅 command 6종을 이 형태로 재작성했다 — 반드시 배선으로 인정돼야 한다.
# 🔴 리스트 안 암묵적 결합(`"a" "b"`)은 CodeQL `py/implicit-string-concatenation-in-list` 대상
#    ("쉼표 누락 아닌가?") — 상수로 빼고 명시적 `+` 를 쓴다.
# #1243 rewrote six hook commands into this shape. Hoisted out of the parametrize list because
# implicit concatenation there reads as a missing comma (CodeQL rule).
_PY_LAUNCHER_CALL = (
    "PY=$(command -v py >/dev/null 2>&1 && echo 'py -3' || echo python3); "
    + f"$PY {_P}"
)


# ── 양성 통제 — 실제 호출은 배선으로 인정해야 한다 ──────────────────────
# Positive control — real invocations must count as wired.

@pytest.mark.parametrize("command", [
    "python scripts/check_fake_guard.py",
    "python3 scripts/check_fake_guard.py",
    "py -3 scripts/check_fake_guard.py",
    _PY_LAUNCHER_CALL,
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


def test_project_dir_default_expansion_on_scripts_path_is_wired():
    """R67 — `${CLAUDE_PROJECT_DIR:-.}/scripts/X.py` 는 실배선이고 `echo` 는 아니다.

    기본값 전개 접두는 경로 경계 `/` 뒤에서 끝나므로 기존 `_mentions_path` 가 인정한다.
    The default-expansion prefix ends on a `/` boundary, so the existing matcher accepts it.
    """
    cmd = (
        "PY=$(command -v py >/dev/null 2>&1 && echo 'py -3' || echo python3); "
        + f"$PY ${{CLAUDE_PROJECT_DIR:-.}}/{_P}"
    )
    assert invokes(cmd, _P) is True
    assert invokes(f"echo ${{CLAUDE_PROJECT_DIR:-.}}/{_P}", _P) is False


def test_project_dir_default_expansion_on_hook_path_is_wired():
    """R67 — `${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/X.py` 도 실배선이어야 한다.

    `str.lstrip("./")` 는 `.claude` 의 점을 먹어 이 형태를 거부했다(가드 자살).
    Character-class lstrip ate the dot of `.claude` and rejected this real wiring.
    """
    cmd = (
        "PY=$(command -v py >/dev/null 2>&1 && echo 'py -3' || echo python3); "
        + f"$PY ${{CLAUDE_PROJECT_DIR:-.}}/{_HOOK}"
    )
    assert invokes(cmd, _HOOK) is True
    assert invokes(f"echo ${{CLAUDE_PROJECT_DIR:-.}}/{_HOOK}", _HOOK) is False


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


# ── 🔴 변수 해소 — `$PY` 를 리터럴로 신뢰하면 이 술어가 스스로 fail-open ────
# Variable resolution: trusting `$PY` as a literal reopens the very hole this module closes.

@pytest.mark.parametrize("command", [
    # 🔴 초판(#1248)은 `$PY`/`${PY}` 를 인터프리터 **리터럴 화이트리스트에 넣었다** — 이름만
    #    맞으면 통과했으므로 아래 세 형태가 전부 '배선' 으로 판정됐다(실측 True). 즉 `echo` 를
    #    막으려고 만든 술어가 `PY=echo` 한 줄로 우회됐다. 자기가 싸우던 클래스의 재생산이다
    #    (다각도 근본원인 분석 2026-08-01 적발 — Grok claim-review).
    # The predicate whitelisted `$PY` by NAME, so `PY=echo; $PY x.py` read as wired.
    "PY=echo; $PY scripts/check_fake_guard.py",
    "PY=cat; $PY scripts/check_fake_guard.py",
    "PY=true; ${PY} scripts/check_fake_guard.py",
    # 치환 분기 중 **하나라도** 인터프리터가 아니면 거부 (경로에 따라 무동작 가능)
    # If ANY branch of the substitution is not an interpreter, reject — it can silently no-op.
    "PY=$(echo cat || echo python3); $PY scripts/check_fake_guard.py",
    # 할당이 아예 없는 변수 = 빈 문자열로 전개 = 아무것도 실행하지 않는다
    # An unassigned variable expands to empty and runs nothing.
    "$PY scripts/check_fake_guard.py",
    # 다른 변수의 할당은 이 변수를 해소하지 못한다 / another var's assignment resolves nothing
    "OTHER=python3; $PY scripts/check_fake_guard.py",
])
def test_variable_interpreter_must_resolve_to_a_real_interpreter(command):
    assert invokes(command, _P) is False, (
        f"변수가 인터프리터로 해소되지 않는데 배선으로 오판 — fail-open 재발: {command!r}"
    )


@pytest.mark.parametrize("command", [
    # 실제 #1243 런처 형태 — 양 분기가 모두 인터프리터이므로 배선이다
    _PY_LAUNCHER_CALL,
    # 리터럴 할당 / literal assignment
    "PY=python3; $PY scripts/check_fake_guard.py",
    "PY=py; ${PY} -3 scripts/check_fake_guard.py",
])
def test_variable_resolving_to_an_interpreter_counts_as_wired(command):
    """🔴 양성 통제 — 해소 규칙이 **실제 배선을 거부**하면 가드 자살이다.

    초판 수정 중 `echo` 대상 추출 정규식이 치환의 닫는 괄호까지 삼켜 `python3)` 로 읽었고,
    그 결과 실제 `#1243` 런처가 False 로 떨어졌다. fail-closed 는 **거짓 거부**까지 정당화하지
    않는다 — 실배선 6종이 통과해야 이 술어가 저장소에서 살아남는다(정책 17 안정성 우선).
    Fail-closed must not reject the real launcher; that would be guard suicide.
    """
    assert invokes(command, _P) is True, f"실제 배선을 거부 — 가드 자살: {command!r}"


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


# ── 🔴 Grok claim-review `019fbaf8` 적발 3건 — 실측 defeat 를 고정한다 ────────
# Three defeats found by adversarial claim-review, pinned as regressions.

@pytest.mark.parametrize(("command", "desc"), [
    # 경계 없는 접미사: 배선을 **다른 파일로 갈아끼워도** 초판은 초록이었다.
    # A bare endswith let a different file satisfy the wiring assertion.
    ("python not_scripts/check_fake_guard.py", "경계 없는 접미사"),
    ("python xscripts/check_fake_guard.py", "경계 없는 접미사(구분자 없음)"),
    # 죽은 단락평가 분기: 배선을 지우지 않고 `true ||` 만 붙여 중성화하는 수법.
    # A dead short-circuit branch neutralises wiring without deleting it.
    ("true || python scripts/check_fake_guard.py", "죽은 || 분기"),
    (": || python scripts/check_fake_guard.py", "죽은 : || 분기"),
    ("false && python scripts/check_fake_guard.py", "죽은 && 분기"),
])
def test_shapes_that_do_not_actually_run_are_not_wired(command, desc):
    assert invokes(command, _P) is False, f"실행되지 않는 형태를 배선으로 오판: {desc} — {command!r}"


@pytest.mark.parametrize(("command", "desc"), [
    # 🔴 양성 통제 — 위 좁힘이 실배선을 거부하면 가드 자살이다(정책 17 안정성 우선).
    ("python path/to/scripts/check_fake_guard.py", "중첩 경로(경계 `/` 있음)"),
    ("python ./scripts/check_fake_guard.py", "`./` 접두"),
    ("false || python scripts/check_fake_guard.py", "살아있는 || 분기"),
    ("true && python scripts/check_fake_guard.py", "살아있는 && 분기"),
    # 상수가 아닌 명령의 종료 코드는 정적으로 모른다 → 죽었다고 단정하지 않는다.
    ("set -e && python scripts/check_fake_guard.py", "비상수 선행 명령"),
])
def test_narrowing_does_not_reject_genuine_invocations(command, desc):
    assert invokes(command, _P) is True, f"실배선을 거부 — 가드 자살: {desc} — {command!r}"


def test_variable_resolution_follows_shell_last_wins():
    """🔴 셸은 **마지막 할당**을 쓴다 — 초판의 '모든 할당' 규칙은 실호출을 거부했다.

    `PY=echo; PY=python3; $PY x.py` 는 셸에서 python3 이 돈다. 초판은 False 였다
    (가드 자살 방향). 반대 순서는 last-wins 로도 정확히 False 다.
    """
    assert invokes(f"PY=echo; PY=python3; $PY {_P}", _P) is True
    assert invokes(f"PY=python3; PY=echo; $PY {_P}", _P) is False
