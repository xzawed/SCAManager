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
    all_templates,
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


@pytest.fixture
def eslint_installed(tmp_path):
    """`main()` 동작 테스트를 **조달 축과 분리**한다 — 설치 상태를 명시적으로 고정.

    🔴 이 픽스처가 없으면 테스트가 `node_modules` 존재 여부에 암묵적으로 의존한다. 실제로 CI 의
    `test-and-analyze` job 은 `npm ci` 를 돌리지 않아 eslint 가 없고, 그 결과 조달 실패(exit 1)가
    advisory 축 단언(exit 0 기대)을 깨뜨렸다(#1229 CI 실측). 로컬은 `npm install` 을 한 상태라
    통과해 **환경에 따라 결과가 갈리는** 테스트였다.
    🔴 Without this the tests implicitly depend on node_modules being present. CI's test-and-analyze
    job does not run `npm ci`, so the procurement failure (exit 1) broke the advisory assertion
    (expects exit 0) — a test whose result varied by environment.
    """
    fake = tmp_path / "eslint.js"
    fake.write_text("", encoding="utf-8")
    with patch("scripts.check_lint_js_nonvacuous.ESLINT_JS", fake):
        yield


# ── 축 1: ignores 동기화 (양방향) ─────────────────────────────────────────────

def test_ignores_exactly_matches_templates_with_jinja_in_script():
    """[보조] 설정의 첫 `ignores` 배열 ↔ Jinja-in-`<script>` 집합 대조 — 오프라인 조기 피드백.

    🔴 **이 테스트는 봉인이 아니다.** `config_ignores()` 는 설정 문법의 일부(첫 배열)만 읽으므로
    두 번째 config 객체·`files:` 축소 등으로 우회된다(Grok claim-review 적발). 실제 커버리지
    봉인은 `main()` 의 역산(`test_main_fails_on_unjustified_exclusion`)이 담당한다.
    🔴 NOT a seal — it reads only part of the config syntax; the real seal is main()'s derivation.
    """
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


def test_template_scan_is_recursive(tmp_path):
    """하위 디렉토리 템플릿도 스캔 대상 — eslint CLI 가 `src/templates/**/*.html`(재귀)이므로.

    🔴 얕은 `glob("*.html")` 을 쓰면 중첩 템플릿이 `all_templates()` 에도
    `templates_with_jinja_in_script()` 에도 들어오지 않아 **두 봉인을 동시에 우회**한다
    (Grok claim-review 적발: 린트되든 무시되든 아무 검사도 받지 않는다).
    현재 리포에는 중첩 템플릿이 없어 **실제 파일로는 이 회귀가 드러나지 않으므로** 픽스처로
    고정한다 — 없으면 `rglob`→`glob` 회귀가 뮤테이션에서도 살아남는다(실측).
    🔴 A shallow glob leaves nested templates out of BOTH sets, bypassing both seals. The repo has
    no nested templates today, so this regression is invisible without a fixture (measured).
    """
    (tmp_path / "top.html").write_text("<script>var a = 1;</script>", encoding="utf-8")
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "deep.html").write_text("<script>var b = 1;</script>", encoding="utf-8")

    with patch("scripts.check_lint_js_nonvacuous.TEMPLATE_DIR", tmp_path), \
         patch("scripts.check_lint_js_nonvacuous.REPO_ROOT", tmp_path):
        found = all_templates()
    assert "sub/deep.html" in found, f"중첩 템플릿이 스캔에서 빠졌다: {sorted(found)}"
    assert "top.html" in found


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
def test_main_fails_when_nothing_was_checked(stdout, label, eslint_installed):
    """검사 범위가 비면 exit 1 — "위반 0건" 과 구별하는 것이 이 가드의 유일한 책임."""
    with patch("scripts.check_lint_js_nonvacuous._run_eslint", return_value=_proc(stdout, 2)):
        assert main() == 1, f"{label} 인데 통과했다 = 공허화 차단 실패"


def _payload(rels, *, violation=False):
    """주어진 상대경로들을 eslint JSON 결과 형태로 만든다."""
    msg = [{"ruleId": "no-undef", "severity": 2, "message": "x is not defined", "line": 1}]
    return json.dumps([
        {
            "filePath": str(REPO_ROOT / rel),
            "messages": msg if violation else [],
            "errorCount": 1 if violation else 0, "warningCount": 0,
        }
        for rel in sorted(rels)
    ])


def test_main_fails_when_disk_scan_is_empty(eslint_installed):
    """디스크 템플릿 집합이 비면 exit 1 — 대조 집합이 비면 모든 차집합 단언이 **공허하게 참**이다.

    🔴 Grok claim-review 적발: 이전 판은 `missing = expected - linted` 만 봐서, expected 가
    비면 어떤 결과든 통과했다(`∅ - X = ∅`). 즉 "검사 범위가 통째로 사라진" 최악의 경우가
    가장 조용히 통과하는 구조였다.
    🔴 Caught by Grok claim-review: with an empty reference set every set-difference is vacuously
    true, so total coverage collapse was the quietest pass.
    """
    # 🔴 두 집합을 **함께** 비운다 — 실제 붕괴(TEMPLATE_DIR 경로 오타)에서는 디스크 스캔에
    # 의존하는 두 집합이 동시에 비고, 그때 비로소 모든 차집합이 공허해진다. 한쪽만 비우면
    # 다른 봉인이 우연히 잡아 이 분기를 고정하지 못한다(뮤테이션으로 발견).
    # 🔴 Empty BOTH sets: a real collapse empties both at once, which is exactly when every
    # set-difference goes vacuous. Emptying one lets the other seal catch it by luck.
    with patch("scripts.check_lint_js_nonvacuous._run_eslint",
               return_value=_proc(_payload(["src/templates/whatever.html"]))), \
         patch("scripts.check_lint_js_nonvacuous.all_templates", return_value=set()), \
         patch("scripts.check_lint_js_nonvacuous.templates_with_jinja_in_script",
               return_value=set()):
        assert main() == 1


def test_main_fails_on_unjustified_exclusion(eslint_installed):
    """정당한 근거(`<script>` 내 Jinja2) 없이 린트에서 빠진 템플릿이 있으면 exit 1.

    🔴 이것이 진짜 봉인이다 — 무시 집합을 **설정 파싱이 아니라 eslint 실제 결과에서 역산**한다.
    따라서 두 번째 `ignores` 배열·작은따옴표·`files:` 축소·`globalIgnores()` 등 설정 문법을
    어떻게 바꾸든 린트 결과가 달라져 여기서 잡힌다(전 판은 이 전부가 green 이었다).
    🔴 The real seal: the ignored set is derived from eslint's actual output, so any config-syntax
    bypass changes that output and fails here.
    """
    linted = sorted(expected_linted_templates())
    assert len(linted) > 1, "대조가 성립하려면 린트 대상이 2개 이상이어야 한다"
    with patch("scripts.check_lint_js_nonvacuous._run_eslint",
               return_value=_proc(_payload(linted[1:]))):        # 첫 파일이 근거 없이 빠졌다
        assert main() == 1


def test_main_fails_when_unparseable_template_is_linted(eslint_installed):
    """Jinja2 로 파싱 불가한 템플릿이 무시되지 않고 린트되면 exit 1 (반대 방향)."""
    justified = templates_with_jinja_in_script()
    assert justified, "대조 집합이 비면 이 테스트는 공허하다"
    with patch("scripts.check_lint_js_nonvacuous._run_eslint",
               return_value=_proc(_payload(all_templates()))):   # 무시돼야 할 것까지 전부 린트됨
        assert main() == 1


def test_main_stays_advisory_on_violations(eslint_installed):
    """위반이 있어도 exit 0 — 사용자 결정(2026-07-29): 위반은 advisory, 공허화만 fail-closed."""
    with patch("scripts.check_lint_js_nonvacuous._run_eslint",
               return_value=_proc(_payload(expected_linted_templates(), violation=True), 1)):
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
