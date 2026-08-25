"""신규 noqa-은닉 미사용 import 가드 정합 (회고 2026-07-18 P1 테마 B — self-inflicted CodeQL py/unused-import 봉인).
New noqa-hidden unused-import guard (retro 2026-07-18 P1 theme B — seals self-inflicted CodeQL py/unused-import).

lint-changed-tests 의 flake8 F401 은 `# noqa: F401` 을 존중해 side-effect ORM import 를 pre-merge 에
못 잡는다 — CodeQL 은 별도 룰셋이라 main 전체 스캔에서만 노출(#540~545, 본 창 3회 재발). 이 가드는
PR diff 에서 **ADDED 된** `# noqa: F401`(또는 bare `# noqa`) 이 붙은 import 만 차단해 튜플-참조 패턴
(`_FK_TARGET_MODELS = (Model,)`)으로 승격을 강제한다.
flake8 respects `# noqa: F401`, so noqa-hidden side-effect imports escape to CodeQL's main full-scan.
This guard blocks only NEW noqa-hidden imports added in the diff, forcing the tuple-reference pattern.

🔴 신규 diff 한정 (정책 17 안정성) — 기존 ~115 legacy `# noqa: F401` 는 무churn (check_dual_import 선례).
Diff-scoped: legacy noqa imports untouched (no churn), mirroring check_dual_import.
"""
import re
from pathlib import Path

import yaml

from tests.unit.scripts._wiring_shape import any_invokes
from scripts.check_noqa_sideeffect import (
    find_violations,
    line_hides_f401,
    parse_added_noqa_imports,
)

_ROOT = Path(__file__).resolve().parents[3]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"


# ── 순수 함수: line_hides_f401 ───────────────────────────────────────────
# Pure function: line_hides_f401

def test_line_hides_f401_explicit_code():
    """`# noqa: F401` 은 F401 억제 → True."""
    assert line_hides_f401("from src.models.user import User  # noqa: F401") is True
    assert line_hides_f401("import src.models.repository  # noqa: F401 — 등록") is True


def test_line_hides_f401_bare_noqa():
    """bare `# noqa` 는 전체 억제(F401 포함) → True."""
    assert line_hides_f401("from src.models.user import User  # noqa") is True


def test_line_hides_f401_multi_code_list():
    """`# noqa: E402,F401` 처럼 목록에 F401 포함 → True."""
    assert line_hides_f401("import os  # noqa: E402,F401") is True


def test_line_hides_f401_space_separated_trailing_prose():
    """🔴 F401 뒤에 **공백 구분 영숫자 텍스트**가 와도 탐지 (회고 2026-07-19 P1 — 실이력 33% miss).

    결함: `_NOQA` 코드 문자 클래스에 공백이 포함돼 `F401  pylint` 를 한 덩어리로 캡처하고,
    `replace(" ","").split(",")` 가 `F401PYLINT` 로 뭉개 **False**(위반 아님)를 반환했다.
    flake8 은 코드를 `[,\\s]+` 로 분리하므로 **실제로는 F401 이 억제**된다 → 가드 통과 +
    CodeQL py/unused-import 재발. 실측: 머지 이력의 ADDED F401 라인 9건 중 3건(33%) 무음 통과.
    Defect: the codes char-class included a space, so trailing prose merged into the code token.
    flake8 splits on `[,\\s]+` and DOES suppress F401 → guard passed while CodeQL still fired.
    """
    assert line_hides_f401("import x  # noqa: F401  pylint: disable=unused-import") is True
    assert line_hides_f401("import x  # noqa: F401  C1 Phase 4 note") is True
    assert line_hides_f401("import x  # noqa: F401 registers model") is True


def test_line_hides_f401_em_dash_form_still_works():
    """em-dash 형은 기존에도 통과했다 — 회귀 방지 (우연한 성공을 고정).

    em-dash 가 문자 클래스를 종료시켜 `F401 ` 만 캡처됐다. 수정 후에도 유지돼야 한다.
    """
    assert line_hides_f401("import x  # noqa: F401 — 모듈 자동 등록  # pylint: disable=unused-import") is True


def test_line_hides_f401_other_code_only_is_false():
    """F401 없는 noqa(예: E501 단독)는 미해당 → False (오탐 차단)."""
    assert line_hides_f401("x = very_long_line  # noqa: E501") is False


def test_line_hides_f401_other_code_with_prose_is_false():
    """🔴 부정 통제 — F401 이 없으면 후행 텍스트가 있어도 False (수정이 오탐을 만들지 않는지)."""
    assert line_hides_f401("import x  # noqa: E501 long line note") is False
    assert line_hides_f401("import x  # noqa: E402 not f401 here") is False


def test_line_hides_f401_non_import_is_false():
    """import 아닌 라인은 무관 → False (변수/표현식의 noqa 오탐 차단)."""
    assert line_hides_f401("value = compute()  # noqa: F401") is False


def test_line_hides_f401_no_noqa_is_false():
    """noqa 없는 정상 import → False (기존 F401 가드가 담당)."""
    assert line_hides_f401("from src.models.user import User") is False


# ── 순수 함수: parse_added_noqa_imports (diff ADDED 라인만) ───────────────
# Pure function: parse_added_noqa_imports

def test_parse_added_noqa_imports_added_only():
    """diff 의 ADDED(+) noqa-F401 import 만 추출 — `+++` 헤더·context·삭제(-) 제외."""
    diff = (
        "+++ b/tests/unit/x.py\n"
        "+from src.models.user import User  # noqa: F401\n"
        " from src.models.repo import Repo  # noqa: F401\n"  # context(미변경) — 제외
        "-from src.models.old import Old  # noqa: F401\n"     # 삭제 — 제외
        "+value = 1\n"                                          # ADDED 이나 import 아님 — 제외
    )
    got = parse_added_noqa_imports(diff)
    assert got == ["from src.models.user import User  # noqa: F401"]


def test_parse_added_noqa_imports_ignores_plusplus_header():
    """`+++ b/...` diff 헤더는 오탐 아님(import 아님)."""
    diff = "+++ b/tests/unit/y.py  # noqa: F401\n"
    assert parse_added_noqa_imports(diff) == []


def test_parse_added_noqa_imports_none():
    """noqa 없는 ADDED import 는 미추출 (기존 F401 가드 담당)."""
    diff = "+from src.models.user import User\n+import os\n"
    assert parse_added_noqa_imports(diff) == []


# ── find_violations (파일별) ─────────────────────────────────────────────
# find_violations per file

def test_find_violations_reports_added_noqa_import():
    diff = "+from src.models.user import User  # noqa: F401\n"
    violations = find_violations("tests/unit/x.py", diff)
    assert len(violations) == 1
    assert "User" in violations[0]


def test_find_violations_clean_when_no_added_noqa():
    diff = "+_FK_TARGET_MODELS = (User,)\n+from src.models.user import User\n"
    assert find_violations("tests/unit/x.py", diff) == []


# ── CI 배선 메타 (test_ci_dead_symbol_guard 선례 3중 봉인) ────────────────
# CI wiring meta-guards

def _lint_job_run_blocks():
    ci = yaml.safe_load(_CI.read_text(encoding="utf-8"))
    steps = ci["jobs"]["lint-changed-tests"]["steps"]
    return [s.get("run", "") for s in steps if "run" in s]


def test_ci_wires_noqa_guard_in_lint_job():
    """🔴 (R1) lint-changed-tests job 이 check_noqa_sideeffect.py 를 호출 — 타 job false-pass 차단."""
    runs = _lint_job_run_blocks()
    assert any_invokes(runs, "scripts/check_noqa_sideeffect.py"), (
        "lint-changed-tests job 에 noqa 가드 배선 누락"
    )


def test_ci_noqa_guard_passes_pr_base_sha():
    """🔴 (R2) 스크립트가 PR base SHA 를 diff base 로 전달 — 신규 diff 한정 긍정 단언."""
    runs = _lint_job_run_blocks()
    guard = next((r for r in runs if "check_noqa_sideeffect.py" in r), "")
    # 주석 제거 후 매칭 (R3: 셸 주석 decoy false-pass 봉인)
    code = "\n".join(l for l in guard.splitlines() if not l.strip().startswith("#"))
    assert "pull_request.base.sha" in code, "PR base SHA 미전달 — diff base 부정확"
    assert re.search(r"check_noqa_sideeffect\.py.*base\.sha.*HEAD", code, re.DOTALL), (
        "base..HEAD diff 범위 미전달"
    )


def test_testing_md_documents_tuple_pattern():
    """🔴 verify.md 가 side-effect-only import 에 튜플 패턴을 명시 — P1#10 안티패턴 권장 봉합."""
    rules = (_ROOT / "docs" / "workflow" / "verify.md").read_text(encoding="utf-8")
    assert "_FK_TARGET_MODELS" in rules or "_SIDE_EFFECT_MODELS" in rules, (
        "verify.md 가 side-effect-only import 튜플-참조 패턴 미문서화 — CodeQL py/unused-import 재발 근본"
    )


# ── #1509: 텍스트 판정의 양방향 오류 ──────────────────────────────────────
#
# 🔴 이 가드는 diff **원문 텍스트**에 정규식을 건다(`check_noqa_sideeffect.py:28`).
#    AST 가 아니므로 「import 문처럼 보이는 줄」과 「실제 import 문」을 구조적으로
#    구분하지 못한다. 그 결과가 양방향이다 — 산문(docstring 인용)을 막고,
#    backslash continuation 의 진짜 noqa 는 놓친다. 둘 다 flake8 실물로 쟀다.
#
# 이 리포는 같은 실패를 #1501 에서 이미 겪었다: `"alias_httpx" in text` 가드가
# **그 규칙을 설명하는 docstring 자체를 막았고** AST 로 재작성했다.


def _diff_and_source(src: str) -> tuple[str, str]:
    """파일 전체가 새로 추가된 상황의 `(diff, source)` 쌍.

    🔴 AST 판정은 **소스**가 있어야 한다. diff 만 넘기면 텍스트 폴백으로 떨어져
    이 테스트들이 검사하려는 축을 지나친다(공허해진다).
    """
    lines = src.splitlines()
    header = (
        "diff --git a/tests/unit/x.py b/tests/unit/x.py\n"
        "+++ b/tests/unit/x.py\n"
        f"@@ -0,0 +1,{len(lines)} @@\n"
    )
    return header + "".join("+" + line + "\n" for line in lines), src


def test_docstring_quotation_is_not_a_violation():
    """🔴 위양성 — docstring 안에서 그 관용구를 **인용**하는 것은 위반이 아니다.

    실측(#1508): 새 가드 파일의 module docstring 이 제거 대상인 거짓 주석을 예시로
    인용했는데 게이트가 그것을 실제 코드로 잡아 CI 를 막았다. 그 줄은 실행되지 않는다.

    🔴 이것이 왜 치명적인가 — **이 가드가 막으려는 거짓을 문서화하려면 인용해야 한다.**
    인용이 불가능하면 정정 기록과 주의문을 쓸 수 없다.
    """
    src = (
        '"""세 테스트가 이런 주석을 달고 있었다:\n'
        "\n"
        "    import src.models  # noqa: F401  side-effect: populate Base.metadata\n"
        "\n"
        '그 부작용은 존재하지 않는다."""\n'
        "x = 1\n"
    )
    violations = find_violations("tests/unit/x.py", *_diff_and_source(src))
    assert not violations, (
        "docstring 안의 인용을 실제 import 로 오판했다 — 산문을 막는 가드다. "
        f"오탐: {violations}"
    )


def test_commented_out_import_is_not_a_violation():
    """위양성 — 주석 처리된 import 는 실행되지 않으므로 위반이 아니다."""
    src = "# import src.models  # noqa: F401  (예전에 이렇게 썼다)\ny = 2\n"
    violations = find_violations("tests/unit/x.py", *_diff_and_source(src))
    assert not violations, f"주석 처리된 줄을 잡았다: {violations}"


def test_parenthesized_continuation_noqa_is_not_a_violation():
    """🔴 **정정** — 괄호 여러 줄 import 의 continuation noqa 는 위반이 **아니다**.

    초안은 이 자리를 「구 가드의 미탐」이라 읽고 「잡아야 한다」고 단언했다.
    flake8 실물로 재니 틀렸다:

        from src.models import (
            Repository,  # noqa: F401
        )
        -> flake8 은 여전히 **1행에 F401 을 보고한다** (억제 안 됨)

    억제되는 것은 **1행에 붙은 noqa 뿐**이다(2·3행은 무효). 즉 이 형태는 애초에
    noqa-은닉이 아니고 `lint-changed-tests` 의 flake8 이 이미 잡는다. 이 가드가
    추가로 막으면 **중복 오탐**이다 — 구 가드가 안 잡은 것이 옳았다.
    Measured: flake8 still reports F401 on line 1, so this is not noqa-hidden at all.
    """
    src = (
        "from src.models import (" + chr(10)
        + "    Repository,  # noqa: F401" + chr(10)
        + ")" + chr(10)
    )
    violations = find_violations("tests/unit/x.py", *_diff_and_source(src))
    assert not violations, (
        "괄호 continuation 의 noqa 를 위반으로 잡았다 — flake8 은 그것을 억제하지 "
        f"않으므로 noqa-은닉이 아니다(중복 오탐): {violations}"
    )


def test_first_line_noqa_of_a_multiline_import_is_a_violation():
    """반대 축 — **1행**에 붙은 noqa 는 실제로 F401 을 억제하므로 위반이다.

    실측: `from src.models import (  # noqa: F401` 은 flake8 이 보고하지 않는다.
    """
    src = (
        "from src.models import (  # noqa: F401" + chr(10)
        + "    Repository," + chr(10)
        + ")" + chr(10)
    )
    violations = find_violations("tests/unit/x.py", *_diff_and_source(src))
    assert violations, "1행 noqa 는 flake8 이 억제하므로 반드시 잡아야 한다"


def test_backslash_continuation_noqa_is_a_violation():
    """backslash continuation 의 noqa 는 flake8 이 **억제한다** — 그래서 잡아야 한다.

    괄호와 정반대다(실측). 이 비대칭이 `import_line_numbers` 가 span 전체가 아니라
    `lineno` + backslash 줄만 넣는 이유다.
    """
    backslash = chr(92)
    src = "import os, " + backslash + chr(10) + "    sys  # noqa: F401" + chr(10)
    violations = find_violations("tests/unit/x.py", *_diff_and_source(src))
    assert violations, "backslash continuation 의 noqa 를 놓쳤다 — flake8 은 억제한다"


def test_headerless_diff_does_not_silently_pass():
    """🔴 fail-open 바닥 — hunk 헤더가 없는 diff 를 조용히 「위반 0건」으로 만들지 않는다.

    AST 판정은 ADDED 라인의 **새 파일 줄번호**를 hunk 헤더에서 얻는다. 헤더가 없으면
    대조할 좌표가 없는데, 그 라인을 그냥 버리면 **입력을 못 읽었을 때 초록**이 된다.
    `git diff -U0` 은 항상 헤더를 내지만, 가드에서 「조용한 0」은 두면 안 되는 형태다
    (형제 가드들의 fail-closed 규율과 같은 축).
    """
    src = "from src.models.user import User  # noqa: F401\n"
    headerless = "+from src.models.user import User  # noqa: F401\n"

    violations = find_violations("tests/unit/x.py", headerless, src)
    assert violations, (
        "hunk 헤더 없는 diff 가 조용히 통과했다 — 좌표를 못 얻으면 텍스트 판정으로 "
        "넘겨야 한다(fail-closed)"
    )


def test_hunk_arithmetic_across_diff_shapes():
    """계기 자기검증 — 줄번호 산술이 git 이 실제로 내놓는 형태들에서 맞는가.

    틀리면 ADDED 라인이 **엉뚱한 AST 구간**에 대조돼 양방향으로 오판한다.
    """
    from scripts.check_noqa_sideeffect import added_lines_with_numbers  # noqa: PLC0415

    # 쉼표 없는 헤더
    assert added_lines_with_numbers("@@ -1 +1 @@\n+aaa\n") == [(1, "aaa")]
    # 여러 hunk — 각 헤더에서 다시 시작
    assert added_lines_with_numbers(
        "@@ -0,0 +3,1 @@\n+aaa\n@@ -5,0 +10,2 @@\n+bbb\n+ccc\n"
    ) == [(3, "aaa"), (10, "bbb"), (11, "ccc")]
    # 삭제 라인은 새 파일 줄번호를 소비하지 않는다
    assert added_lines_with_numbers("@@ -3,1 +3,2 @@\n-old\n+new1\n+new2\n") == [
        (3, "new1"), (4, "new2")
    ]
    # `+++` 파일 헤더는 ADDED 가 아니다
    assert added_lines_with_numbers("+++ b/tests/x.py\n@@ -0,0 +7,1 @@\n+aaa\n") == [(7, "aaa")]


def test_fallback_is_degraded_not_stricter():
    """🔴 폴백이 「더 엄격」이 아님을 **고정한다** — 초안 주석의 거짓 주장을 재발 방지.

    처음에는 「텍스트 폴백은 덜 정확하지만 더 엄격하다(fail-closed)」고 적었다.
    실측하니 **양방향으로 열화**였다: 산문을 오탐하고 continuation 을 미탐한다.
    이 테스트가 red 가 되면 그 관계가 바뀐 것이니 docstring 을 다시 재라.
    """
    def _both(src: str) -> tuple[int, int]:
        lines = src.splitlines()
        diff = f"@@ -0,0 +1,{len(lines)} @@\n" + "".join("+" + l + "\n" for l in lines)
        return len(find_violations("x.py", diff, src)), len(parse_added_noqa_imports(diff))

    # 텍스트가 **놓치는** 자리 — backslash continuation (폴백이 더 느슨)
    ast_n, txt_n = _both("import os, " + chr(92) + chr(10) + "    sys  # noqa: F401" + chr(10))
    assert (ast_n, txt_n) == (1, 0), (
        f"backslash continuation 축이 바뀌었다 — AST={ast_n} 텍스트={txt_n}"
    )

    # 텍스트가 **오탐하는** 자리 — docstring 인용 (폴백이 더 엄격)
    ast_n, txt_n = _both('"""예시:' + chr(10) + chr(10)
                         + "    import src.models  # noqa: F401" + chr(10) + chr(10)
                         + '"""' + chr(10) + "x = 1" + chr(10))
    assert (ast_n, txt_n) == (0, 1), (
        f"산문 축이 바뀌었다 — AST={ast_n} 텍스트={txt_n}"
    )


def test_ast_path_does_not_regress_normal_import_forms():
    """회귀 방지 — 텍스트가 잡던 정상 형태를 AST 도 전부 잡는다.

    판정기를 바꾸며 **막으려던 것을 놓치면** 이 PR 은 가드를 약화한 것이다.
    """
    def _ast(src: str) -> int:
        lines = src.splitlines()
        diff = f"@@ -0,0 +1,{len(lines)} @@\n" + "".join("+" + l + "\n" for l in lines)
        return len(find_violations("x.py", diff, src))

    forms = {
        "module level": "import src.models.user  # noqa: F401\n",
        "from import": "from src.models.user import User  # noqa: F401\n",
        "TYPE_CHECKING": (
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    from src.models.user import User  # noqa: F401\n"
        ),
        "function scope": "def f():\n    from src.models.user import User  # noqa: F401\n",
        "try/except": (
            "try:\n"
            "    import src.models.user  # noqa: F401\n"
            "except ImportError:\n"
            "    pass\n"
        ),
        "bare noqa": "import src.models.user  # noqa\n",
    }
    missed = [name for name, src in forms.items() if _ast(src) == 0]
    assert not missed, f"AST 판정이 놓친 형태 — 가드 약화: {missed}"


def test_changed_files_query_disables_quotepath(monkeypatch):
    """🔴 비-ASCII 파일명이 **조용히 가드 밖으로 빠지는** 선행 결함을 막는다.

    git 은 기본값 `core.quotepath=true` 로 비-ASCII 경로를 따옴표+8진 이스케이프로
    내놓는다. 그 문자열은 `.py` 가 아니라 `.py"` 로 끝나 `_changed_test_files` 의
    `endswith(".py")` 필터에 걸러진다 — **한글 이름의 테스트 파일이 통째로 무검사**다.

    실측(이 PR): 한글 이름 파일에 noqa import 를 심었을 때
      · 플래그 없음 → 대상 목록 `[]`, EXIT=0 (조용히 통과)
      · 플래그 있음 → 대상 목록에 포함, EXIT=1 (잡힘)

    🔴 **실제 인자를 본다 — 소스 텍스트가 아니라.** 첫 판은 `inspect.getsource` 에
    문자열이 있는지만 봤는데, 바로 위 **주석에 같은 문자열이 있어** 플래그를 지워도
    통과했다(뮤테이션으로 확인). 공허한 가드였다.
    Asserts the actual argv, not the source text: a first version matched the explanatory
    comment and stayed green when the flag was deleted.
    """
    from scripts import check_noqa_sideeffect as mod  # noqa: PLC0415

    seen = []

    def _fake_git(args):
        seen.append(list(args))
        return ""

    monkeypatch.setattr(mod, "_git", _fake_git)
    mod._changed_test_files("BASE", "HEAD")  # pylint: disable=protected-access

    assert seen, "git 호출이 없었다 — 계기 고장"
    argv = seen[0]
    assert "-c" in argv and "core.quotepath=false" in argv, (
        "_changed_test_files 가 core.quotepath 를 끄지 않는다 — 비-ASCII 경로가 "
        f"따옴표로 감싸져 `.py` 필터에 걸러지고 그 파일은 무검사로 통과한다. argv={argv}"
    )
    # `-c` 바로 뒤에 와야 git 이 설정으로 받는다 (순서가 틀리면 무동작)
    assert argv[argv.index("-c") + 1] == "core.quotepath=false", (
        f"`-c` 다음 인자가 설정값이 아니다 — git 이 무시한다. argv={argv}"
    )
