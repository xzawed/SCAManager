"""신규 이중 import 가드 정합 (회고 2026-07-03 C2 — self-inflicted CodeQL py/import-and-import-from 봉인).
New dual-import guard integrity (retro 2026-07-03 C2 — seals self-inflicted CodeQL py/import-and-import-from).

#1023(test_config.py 이중 import → CodeQL #538/#539) 같은 신규 도입만 pre-merge 차단하고,
기존 28 legacy idiom(`import X as mock` + `from X import fn`)은 무관함을 봉인한다(정책 17 안정성 우선).
Blocks only NEW dual-imports like #1023 pre-merge, leaving the 28 legacy idioms untouched.

🔴 메타테스트 3중 봉인 (test_ci_dead_symbol_guard.py 선례):
  (R1) lint-changed-tests job 영역 한정 — 다른 job 토큰 false-pass 차단.
  (R2) 스크립트 실행이 PR base SHA 를 diff base 로 전달 — 신규 diff 한정 긍정 단언.
  (R3) run: 셸 주석 제거 후 매칭 — 주석 decoy false-pass 봉인 (#936 학습).
"""
import re
from pathlib import Path

import yaml

from scripts.check_dual_import import (
    content_has_from_import,
    content_has_plain_import,
    find_violations_for_file,
    parse_added_from_modules,
    parse_added_plain_modules,
)

_ROOT = Path(__file__).resolve().parents[3]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"


# ── 순수 함수: parse_added_from_modules ──────────────────────────────────
# Pure function: parse_added_from_modules


def test_parse_added_from_modules_extracts_added_only():
    """diff -U0 의 `+from X import` 만 추출 — 문맥/삭제 라인·`+++` 헤더 제외."""
    diff = (
        "+++ b/tests/unit/test_x.py\n"
        "@@ -1,0 +2 @@\n"
        "+from src.config import Settings\n"
        " from src.other import kept\n"       # 문맥(공백) — 미추출 / context line
        "-from src.removed import gone\n"      # 삭제 — 미추출 / removed line
    )
    assert parse_added_from_modules(diff) == {"src.config"}


def test_parse_added_from_modules_ignores_plusplus_header():
    """`+++ b/...` diff 헤더는 from-import 로 오인하지 않는다."""
    diff = "+++ b/tests/from_import_named.py\n+from a.b import c\n"
    assert parse_added_from_modules(diff) == {"a.b"}


def test_parse_added_from_modules_empty_when_no_from():
    """ADDED from-import 없으면 빈 집합 (plain import 추가·문서 변경 등)."""
    assert parse_added_from_modules("+import src.config as cfg\n+# comment\n") == set()


# ── 순수 함수: content_has_plain_import ──────────────────────────────────
# Pure function: content_has_plain_import


def test_content_has_plain_import_matches_alias_and_plain():
    """`import X` 와 `import X as alias` 둘 다 매칭."""
    assert content_has_plain_import("import src.config as cfg\n", "src.config")
    assert content_has_plain_import("import src.config\n", "src.config")


def test_content_has_plain_import_no_false_match_on_from():
    """`from X import ...` 는 plain import 로 오인하지 않는다 (이중 import 성립 안 함)."""
    assert not content_has_plain_import("from src.config import Settings\n", "src.config")


def test_content_has_plain_import_no_prefix_false_match():
    """`import src.config_manager` 는 module `src.config` 로 오매칭하지 않는다 (경계)."""
    assert not content_has_plain_import("import src.config_manager as cm\n", "src.config")


# ── 순수 함수: find_violations_for_file (통합) ───────────────────────────
# Pure function: find_violations_for_file (combined)


def test_find_violations_flags_1023_pattern():
    """#1023 재현: 기존 `import src.config as cfg` + 신규 `from src.config import Settings` → 위반."""
    diff = "+++ b/tests/unit/test_config.py\n+from src.config import Settings\n"
    head = "import src.config as cfg\nfrom src.config import Settings\n\n\ndef test_x():\n    pass\n"
    assert find_violations_for_file(diff, head) == ["src.config"]


def test_find_violations_ignores_legacy_untouched():
    """기존 이중 import 파일이지만 이번 diff 에서 from-import 추가 안 하면 미검출 (legacy 무churn)."""
    diff = "+++ b/tests/unit/test_legacy.py\n+    result = do_something()\n"  # from-import 추가 없음
    head = "import src.x as mod\nfrom src.x import fn\n"  # 기존 legacy idiom
    assert find_violations_for_file(diff, head) == []


def test_find_violations_ignores_added_from_without_coexisting_import():
    """신규 from-import 만 있고 plain import 공존 안 하면 이중 import 아님 → 미검출."""
    diff = "+++ b/tests/unit/test_x.py\n+from src.config import Settings\n"
    head = "from src.config import Settings\n"
    assert find_violations_for_file(diff, head) == []


# ── 🔴 역방향 (2026-07-23 회고 P1-A) — #1196 자초 CodeQL #560 재현 봉인 ────
# Reverse direction — seals the #1196 self-inflicted CodeQL #560 blind spot


def test_parse_added_plain_modules_extracts_plain_and_alias():
    """ADDED `+import X` / `+import X as Y` 에서 모듈명 추출 — `+from ...` 은 미추출."""
    diff = (
        "+++ b/tests/unit/api/test_hook.py\n"
        "+import src.api.hook as _hook_module\n"   # #1196 실제 라인 / actual #1196 line
        "+import src.config\n"
        "+from src.other import kept\n"            # from-import — 이 함수 대상 아님
        " import src.context as ctx\n"            # 문맥(공백) — 미추출
    )
    assert parse_added_plain_modules(diff) == {"src.api.hook", "src.config"}


def test_content_has_from_import_matches_and_no_false_on_plain():
    """`from X import ...` 존재 검출 + `import X`(plain)은 오검출 안 함."""
    assert content_has_from_import("from src.api.hook import _coerce_raw_score\n", "src.api.hook")
    assert content_has_from_import("    from src.x import y  # 함수-local\n", "src.x")  # 들여쓰기
    assert not content_has_from_import("import src.api.hook as h\n", "src.api.hook")


def test_find_violations_flags_1196_reverse_direction():
    """🔴 #1196 재현: 기존 `from src.api.hook import _coerce_raw_score`(함수-local) + 신규
    top-level `import src.api.hook as _hook_module` → 역방향 이중 import 위반 검출.
    이 방향이 단방향 가드의 사각이었고 CodeQL #560 을 자초했다(회고 P1-A).
    """
    diff = "+++ b/tests/unit/api/test_hook.py\n+import src.api.hook as _hook_module\n"
    head = (
        "import src.api.hook as _hook_module\n"
        "def test_x():\n"
        "    from src.api.hook import _coerce_raw_score\n"  # 함수-local from-import (실제 #1196)
        "    return _coerce_raw_score\n"
    )
    assert find_violations_for_file(diff, head) == ["src.api.hook"]


def test_find_violations_reverse_ignored_without_coexisting_from():
    """신규 plain import 만 있고 from-import 공존 안 하면 미검출 (역방향 부정통제)."""
    diff = "+++ b/tests/unit/test_x.py\n+import src.foo as f\n"
    head = "import src.foo as f\nx = 1\n"
    assert find_violations_for_file(diff, head) == []


# ── CI 배선 메타테스트 (self-inflicted CodeQL 재발 방지 실효) ─────────────
# CI wiring meta-test (ensures the guard actually runs in CI)


def _lint_job() -> dict:
    """ci.yml 에서 lint-changed-tests job 만 추출 (R1 — 다른 job 토큰 false-pass 차단)."""
    data = yaml.safe_load(_CI.read_text(encoding="utf-8"))
    job = data["jobs"].get("lint-changed-tests")
    assert job is not None, "lint-changed-tests job 부재"
    return job


def _lint_run_code() -> str:
    """lint job 의 run: 스크립트만 합치고 셸 주석 제거 (R3/#936 — 주석 decoy false-pass 봉인)."""
    job = _lint_job()
    runs = "\n".join(
        s["run"] for s in job.get("steps", []) if isinstance(s, dict) and "run" in s
    )
    return re.sub(r"(?m)(?:^|\s)#.*$", "", runs)


def test_ci_wires_dual_import_guard():
    """lint-changed-tests job 이 check_dual_import.py 를 실제 실행한다 (주석 제외)."""
    code = _lint_run_code()
    assert "scripts/check_dual_import.py" in code, "check_dual_import.py 가 CI 에서 미실행 (가드 무력)"


def test_ci_dual_import_guard_is_pr_diff_scoped():
    """가드가 PR base SHA 를 diff base 로 전달 — 신규 diff 한정(R2), 전체 스캔 아님."""
    code = _lint_run_code()
    assert re.search(
        r"check_dual_import\.py[^\n]*pull_request\.base\.sha", code
    ), "dual-import 가드가 PR base SHA(신규 diff 한정) 미전달 — legacy churn 위험"
