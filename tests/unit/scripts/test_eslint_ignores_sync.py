"""`eslint.config.mjs` ignores 동기화 + `lint-js` 공허화 가드 배선 검증 (#1227 항목 1·3).

세 축을 덮는다 (AGENTS.md 3-불변식):

  1. **fail-closed** — `ignores` 는 "`<script>` 안에 Jinja2 가 있는 템플릿" 집합과 **정확히** 같아야
     한다. 산문이 아니라 파일을 읽어 구조로 계산한다. 누락(파싱 오류 방치)도 과잉(검사 범위 임의
     축소)도 red. 실제로 `settings.html` 은 `<script>` 안 Jinja2 보간이 **17개**(전 템플릿 중 최다)
     인데도 목록 밖이라 `make lint-js` 의 유일한 error 로 남아 있었고, `|| true` 에 삼켜져 있었다.
  2. **공허화 차단** — `check_lint_js_nonvacuous.main()` 이 "0개 파일 검사"·"조용한 부분 스킵" 을
     실패로 승격하는지. 위반(경고/에러)으로는 실패하지 않아야 한다(advisory 성격 보존 — 사용자 결정).
  3. **배선** — 정의만 하고 아무 게이트에도 연결하지 않으면 dead code 다(#1145 형). `ci.yml` 과
     `Makefile` 이 **실제로 이 스크립트를 호출**하는지 YAML/recipe 구조로 확인한다(산문 언급 아님).

Covers the ignores-sync invariant, the anti-vacuity behaviour, and the wiring of both into CI and
the Makefile (#1227 items 1 and 3).
"""
import json
import pathlib
from unittest.mock import MagicMock, patch

import pytest
import yaml

from scripts.check_lint_js_nonvacuous import (
    CONFIG_PATH,
    NON_TEMPLATE_IGNORES,
    REPO_ROOT,
    TEMPLATE_DIR,
    config_ignores,
    expected_linted_templates,
    main,
    templates_with_jinja_in_script,
)

_CI_YAML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
_MAKEFILE = REPO_ROOT / "Makefile"
_SCRIPT_REF = "scripts/check_lint_js_nonvacuous.py"


def _proc(stdout: str, returncode: int = 0) -> MagicMock:
    """subprocess.run 반환값 모방 — eslint 호출 자체는 이 테스트의 관심사가 아니다."""
    mock = MagicMock()
    mock.stdout = stdout
    mock.stderr = ""
    mock.returncode = returncode
    return mock


# ── 축 1: ignores 동기화 (양방향) ─────────────────────────────────────────────

def test_ignores_exactly_matches_templates_with_jinja_in_script():
    """무시 목록 = Jinja-in-`<script>` 템플릿 집합 — 누락도 과잉도 red."""
    listed = config_ignores() - NON_TEMPLATE_IGNORES
    computed = templates_with_jinja_in_script()

    missing = computed - listed      # 파싱 불가인데 목록 밖 → eslint 가 파싱 오류를 낸다
    extra = listed - computed        # 파싱 가능한데 무시 → 근거 없는 검사 범위 축소
    assert not missing, (
        f"`<script>` 안에 Jinja2 가 있어 파싱 불가인데 ignores 에 없다: {sorted(missing)}\n"
        "→ ignores 에 추가하거나, Jinja 값을 <script> 밖(data-* 속성 등)으로 옮길 것."
    )
    assert not extra, (
        f"Jinja2 없이 파싱 가능한데 ignores 에 있다(검사 범위 임의 축소): {sorted(extra)}"
    )


def test_scanner_is_not_vacuous():
    """공허화 방지 — 대조 집합이 비면 위 테스트는 아무것도 검증하지 않는다."""
    assert len(list(TEMPLATE_DIR.glob("*.html"))) >= 5
    assert templates_with_jinja_in_script(), "Jinja-in-script 템플릿 0건 = 스캐너가 고장났다"
    assert expected_linted_templates(), "검사 대상 템플릿 0건 = 린트 범위가 비었다"


# ── 축 2: 공허화 차단 동작 ────────────────────────────────────────────────────

@pytest.mark.parametrize("stdout,label", [
    ("", "빈 stdout"),
    ("Oops! Something went wrong! :(", "비-JSON stdout (설정 부재/기동 실패)"),
    ("[]", "검사된 파일 0개"),
])
def test_main_fails_when_nothing_was_checked(stdout, label):
    """검사 범위가 비면 exit 1 — "위반 0건" 과 구별하는 것이 이 가드의 유일한 책임."""
    with patch("scripts.check_lint_js_nonvacuous._run_eslint", return_value=_proc(stdout, 2)):
        assert main() == 1, f"{label} 인데 통과했다 = 공허화 차단 실패"


def test_main_fails_when_every_template_is_ignored():
    """전 템플릿이 `ignores` 로 빠져 검사 대상이 0이어도 exit 1.

    🔴 이 축은 아래 부분-스킵 검사가 **덮지 못한다** — 기대 집합까지 비면 차집합이 공집합이라
    그 단언은 통과해버린다. 즉 `if not results` 분기를 독립적으로 고정하는 유일한 테스트다.
    (뮤테이션으로 발견: 이 테스트가 없을 때 `if not results` 를 제거해도 스위트가 green 이었다.)
    """
    with patch("scripts.check_lint_js_nonvacuous._run_eslint", return_value=_proc("[]")), \
         patch("scripts.check_lint_js_nonvacuous.expected_linted_templates", return_value=set()):
        assert main() == 1


def test_main_fails_on_silent_partial_skip():
    """검사돼야 할 템플릿이 결과에서 빠지면 exit 1 (조용한 부분 스킵)."""
    expected = sorted(expected_linted_templates())
    # 기대 집합이 2개 이상일 때만 의미 있는 단언 (1개면 부분 스킵이 성립하지 않는다)
    assert len(expected) > 1
    payload = json.dumps([{
        "filePath": str(REPO_ROOT / expected[0]), "messages": [],
        "errorCount": 0, "warningCount": 0,
    }])
    with patch("scripts.check_lint_js_nonvacuous._run_eslint", return_value=_proc(payload)):
        assert main() == 1


def test_main_stays_advisory_on_violations():
    """위반이 있어도 exit 0 — 사용자 결정(2026-07-29): 위반은 advisory, 공허화만 fail-closed."""
    payload = json.dumps([
        {
            "filePath": str(REPO_ROOT / rel),
            "messages": [{"ruleId": "no-undef", "severity": 2,
                          "message": "x is not defined", "line": 1}],
            "errorCount": 1, "warningCount": 0,
        }
        for rel in sorted(expected_linted_templates())
    ])
    with patch("scripts.check_lint_js_nonvacuous._run_eslint", return_value=_proc(payload, 1)):
        assert main() == 0, "위반으로 실패하면 advisory 계약 위반"


def test_main_fails_fast_when_eslint_not_installed():
    """미설치는 '위반 0건' 이 아니라 **조달 실패** — 실행을 시도하기 전에 exit 1.

    🔴 `_run_eslint` 가 **호출되지 않았음**까지 단언한다. 종료 코드만 보면 이 분기를 지워도
    (없는 경로로 node 를 띄웠다가 비-JSON stdout 으로) 여전히 1이라 테스트가 통과해버려,
    "미설치를 명확히 보고한다" 는 계약이 조용히 사라진다 (뮤테이션으로 발견).
    """
    with patch("scripts.check_lint_js_nonvacuous.ESLINT_JS",
               pathlib.Path("/nonexistent/eslint.js")), \
         patch("scripts.check_lint_js_nonvacuous._run_eslint") as run:
        assert main() == 1
        run.assert_not_called()


# ── 축 3: 배선 (정의 ≠ 배선) ──────────────────────────────────────────────────

def test_ci_workflow_actually_runs_the_script():
    """`ci.yml` 의 어떤 job step 이 **실제로** 이 스크립트를 실행하는지 YAML 구조로 확인한다.

    산문 grep 이 아니라 `jobs.*.steps[].run` 을 파싱한다 — 주석에만 언급되고 실행되지 않는
    상태를 통과시키지 않기 위해서다(#1145 형 배선 누락).
    """
    workflow = yaml.safe_load(_CI_YAML.read_text(encoding="utf-8"))
    run_commands = [
        step.get("run", "")
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
    ]
    assert any(_SCRIPT_REF in cmd for cmd in run_commands), (
        f"{_SCRIPT_REF} 를 실행하는 CI step 이 없다 — 가드가 배선되지 않았다"
    )


def test_makefile_lint_js_target_runs_the_script():
    """`make lint-js` 가 스크립트를 호출하고, 실패를 삼키는 `|| true` 가 없어야 한다."""
    lines = _MAKEFILE.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("lint-js:"))
    body = []
    for line in lines[start + 1:]:
        if not line.startswith("\t"):
            break
        body.append(line)
    recipe = "\n".join(body)
    assert _SCRIPT_REF in recipe, f"make lint-js 가 {_SCRIPT_REF} 를 호출하지 않는다:\n{recipe}"
    assert "|| true" not in recipe, (
        "make lint-js 에 `|| true` 가 남아 있다 — 공허화 차단이 다시 삼켜진다"
    )


def test_guard_target_paths_exist():
    """가드가 읽는 실경로가 실제로 존재해야 한다 (경로 오타 = 조용한 무력화)."""
    assert CONFIG_PATH.is_file()
    assert _CI_YAML.is_file()
    assert _MAKEFILE.is_file()
    assert (REPO_ROOT / _SCRIPT_REF).is_file()
