"""신규 dead-code(호출자 0 공개 함수) 가드 정합 (회고 2026-07-18 P1#9/14/15 — declared-but-unwired 봉인).
New dead-code (zero-caller public function) guard (retro 2026-07-18 P1#9/14/15 — declared-but-unwired).

#1060 `find_orphaned` 가 호출자 0 dead code 로 13 PR 생존(전 스위트 green + 5+1 + opus whole-branch
모두 미검출, #1073 이 뒤늦게 배선). service 함수 mutation-green 이 route/caller 배선을 못 잡는다.
이 가드는 PR diff 에서 **ADDED** 된 src/repositories·src/services 의 공개 함수가 src/ 어디서도
AST 참조되지 않으면 차단(의도적 미배선은 `# unwired-ok:` 마커로 예외).
#1060's find_orphaned survived 13 PRs as zero-caller dead code (all gates green). This guard blocks NEW
public repository/service functions with no in-src AST reference (intentional staging via `# unwired-ok:`).

🔴 AST 참조 카운트 = docstring/주석 멘션 제외(grep 은 자기 docstring 멘션에 false-negative).
AST reference counting excludes docstring/comment mentions (grep false-negatives on self-mentions).
"""
import re
from pathlib import Path

import yaml

from scripts.check_dead_code import (
    count_ast_references,
    parse_added_public_defs,
    parse_unwired_ok_names,
)

_ROOT = Path(__file__).resolve().parents[3]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"


# ── parse_added_public_defs ──────────────────────────────────────────────
def test_parses_added_public_def():
    diff = "+def find_orphaned(db, *, older_than_minutes):\n"
    assert parse_added_public_defs(diff) == {"find_orphaned"}


def test_parses_added_async_def():
    diff = "+async def fetch_all(db):\n"
    assert parse_added_public_defs(diff) == {"fetch_all"}


def test_parses_indented_method():
    """클래스 메서드(들여쓰기)도 ADDED def 로 추출."""
    diff = "+    def compute_scores(self):\n"
    assert parse_added_public_defs(diff) == {"compute_scores"}


def test_excludes_private_and_dunder():
    """`_private`·`__dunder__` 는 제외 — 암묵/내부 호출 가능성(오탐 차단)."""
    diff = "+def _helper(x):\n+def __init__(self):\n+def public_api(x):\n"
    assert parse_added_public_defs(diff) == {"public_api"}


def test_excludes_context_and_deleted_and_header():
    """context( )·삭제(-)·`+++` 헤더 라인은 def 추출 대상 아님."""
    diff = (
        "+++ b/src/services/x.py\n"
        " def context_only(db):\n"   # 미변경 context — 제외
        "-def removed(db):\n"        # 삭제 — 제외
        "+def added(db):\n"
    )
    assert parse_added_public_defs(diff) == {"added"}


# ── parse_unwired_ok_names ───────────────────────────────────────────────
def test_parses_unwired_ok_marker():
    diff = "+# unwired-ok: find_orphaned (후속 #1073 에서 배선)\n"
    assert "find_orphaned" in parse_unwired_ok_names(diff)


def test_unwired_ok_trailing_comment():
    diff = "+def stage_only(db):  # unwired-ok: stage_only (예정)\n"
    assert "stage_only" in parse_unwired_ok_names(diff)


def test_no_unwired_ok():
    assert parse_unwired_ok_names("+def foo(db):\n") == set()


# ── count_ast_references (핵심: docstring/주석 제외) ──────────────────────
def test_counts_bare_call():
    assert count_ast_references("find_orphaned", "x = find_orphaned(db)\n") == 1


def test_counts_attribute_call():
    """모듈 정규화 호출(repo.find_orphaned) = Attribute 참조."""
    assert count_ast_references("find_orphaned", "repo.find_orphaned(db)\n") == 1


def test_def_only_is_zero_references():
    """정의만 있고 참조 없음 → 0 (def 이름은 참조 아님)."""
    src = "def find_orphaned(db):\n    return 1\n"
    assert count_ast_references("find_orphaned", src) == 0


def test_docstring_mention_is_not_a_reference():
    """🔴 docstring 멘션은 참조 아님 — grep false-negative 봉인(find_orphaned 자기 docstring)."""
    src = '''def find_orphaned(db):
    """find_orphaned 는 흔적을 표면화한다 (find_orphaned 참조)."""
    return 1
'''
    assert count_ast_references("find_orphaned", src) == 0


def test_comment_mention_is_not_a_reference():
    src = "# find_orphaned 배선 예정\nx = 1\n"
    assert count_ast_references("find_orphaned", src) == 0


def test_syntax_error_source_returns_zero():
    """파싱 불가 소스는 0 참조(크래시 금지)."""
    assert count_ast_references("foo", "def broken(:\n") == 0


# ── CI 배선 메타 (test_ci_dead_symbol_guard 선례 3중 봉인) ────────────────
def _lint_job_run_blocks():
    ci = yaml.safe_load(_CI.read_text(encoding="utf-8"))
    steps = ci["jobs"]["lint-changed-tests"]["steps"]
    return [s.get("run", "") for s in steps if "run" in s]


def test_ci_wires_dead_code_guard():
    """🔴 (R1) lint-changed-tests job 이 check_dead_code.py 를 호출 — 타 job false-pass 차단."""
    assert any("check_dead_code.py" in r for r in _lint_job_run_blocks()), (
        "lint-changed-tests job 에 dead-code 가드 배선 누락"
    )


def test_ci_dead_code_guard_passes_pr_base_sha():
    """🔴 (R2·R3) PR base SHA 를 diff base 로 전달 (주석 decoy 제거 후 매칭)."""
    guard = next((r for r in _lint_job_run_blocks() if "check_dead_code.py" in r), "")
    code = "\n".join(l for l in guard.splitlines() if not l.strip().startswith("#"))
    assert re.search(r"check_dead_code\.py.*base\.sha.*HEAD", code, re.DOTALL), (
        "base..HEAD diff 범위 미전달"
    )
