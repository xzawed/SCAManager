"""회귀 가드 — repo_detail.html Script Block 2 IIFE 래핑 + var chart 선언 검증.

Regression guard — repo_detail.html Script Block 2 IIFE wrapping and var chart declaration.

버그: Script Block 2 의 bare `const` 선언이 전역 JS 스코프에 노출되어
2번째 htmx-boost 내비게이션 시 `SyntaxError: Identifier already declared` 발생.
필터/정렬/검색/슬라이더 기능이 전부 마비됨.

Bug: Bare `const` declarations in Script Block 2 were exposed at global JS scope,
causing `SyntaxError: Identifier already declared` on 2nd htmx-boost navigation
and crashing all filter/sort/search/slider functionality.

수정:
  1. Script Block 1 — `let chart` → `var chart`, `let _chartData` → `var _chartData`
  2. Script Block 2 — `(function() { ... })();` IIFE 로 래핑

Fix:
  1. Script Block 1 — `let chart` → `var chart`, `let _chartData` → `var _chartData`
  2. Script Block 2 — wrapped in `(function() { ... })();` IIFE

검증 방법:
  Jinja2 Environment 직접 사용 — FastAPI app import 없이 템플릿 소스만 검사.
  구조 검증 (IIFE 패턴 + bare let 부재) → 실제 브라우저 렌더링 없이 회귀 차단.

Verification method:
  Uses Jinja2 Environment directly — inspects template source without FastAPI app import.
  Structural checks (IIFE pattern + absent bare let) catch regressions without browser rendering.
"""
from __future__ import annotations

import re
import pathlib

import pytest
import jinja2

# 템플릿 디렉토리 — 프로젝트 루트 기준 절대 경로
# Template directory — absolute path relative to project root
_TEMPLATE_DIR = pathlib.Path(__file__).parents[3] / "src" / "templates"

# 최소 mock context — repo_detail.html 이 요구하는 변수 (Jinja2 UndefinedError 방지)
# Minimal mock context — variables required by repo_detail.html (avoids Jinja2 UndefinedError)
_MINIMAL_CONTEXT = {
    "repo_name": "owner/test-repo",
    "analyses": [],          # 빈 배열 — `| tojson` 필터로 `[]` 주입
    "chart_labels": [],
    "chart_scores": [],
    "hook_installed": False,
    "current_user": None,
    "locale": "ko",
    # repo_id 는 템플릿에서 선택적 사용 — None 허용
    "repo_id": None,
    # Alembic 0032 — 월별 비용 추적 (빈 값으로 초기화)
    "monthly_cost_usd": 0.0,
    "monthly_token_count": 0,
    "monthly_cost_month": "2026-05",
}


@pytest.fixture(scope="module")
def rendered_html() -> str:
    """repo_detail.html 을 최소 컨텍스트로 렌더링한 HTML 문자열 반환.

    Render repo_detail.html with minimal context and return the HTML string.

    FastAPI app 을 import 하지 않고 Jinja2 Environment 직접 사용.
    Uses Jinja2 Environment directly without importing the FastAPI app.

    scope="module" — 이 테스트 파일 안에서 1회만 렌더링 (성능)
    scope="module" — rendered only once per test file for efficiency.
    """
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=jinja2.select_autoescape(["html"]),
        undefined=jinja2.Undefined,    # 미정의 변수 → 빈 문자열 (UndefinedError 방지)
    )
    # i18n 필터 등록 — 템플릿이 `| i18n` / `| i18n_args` 를 사용하므로 필수
    # Register i18n filters — required because the template uses `| i18n` / `| i18n_args`
    from src.i18n.filters import register_i18n_filters
    register_i18n_filters(env)

    template = env.get_template("repo_detail.html")
    return template.render(**_MINIMAL_CONTEXT)


def _extract_script_blocks(html: str) -> list[str]:
    """HTML 에서 <script> ... </script> 블록 내용만 추출.

    Extract the inner content of each <script>...</script> block.
    """
    return re.findall(
        r"<script\b[^>]*>(.*?)</script\b[^>]*>",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )


# ─── Test 1: Script Block 2 는 IIFE 로 래핑돼야 함 ────────────────────────────

def test_repo_detail_script_block2_iife_wrapped(rendered_html: str):
    """Script Block 2 (`ALL_ANALYSES` 포함) 가 IIFE 패턴으로 래핑됐는지 검증.

    Verify that Script Block 2 (containing `ALL_ANALYSES`) is wrapped in an IIFE.

    수정 전 상태 (실패 케이스):
    <script>
    const ALL_ANALYSES = ...;    ← bare top-level const — SyntaxError on 2nd visit

    수정 후 상태 (통과 케이스):
    <script>
    (function() {
    const ALL_ANALYSES = ...;    ← scoped inside IIFE
    })();
    </script>

    Before fix (failure case):
    `ALL_ANALYSES` is a bare top-level const — SyntaxError: Identifier already declared
    on 2nd htmx-boost navigation.

    After fix (pass case):
    `ALL_ANALYSES` is declared inside an IIFE — scoped, no redeclaration error.
    """
    blocks = _extract_script_blocks(rendered_html)

    # ALL_ANALYSES 를 포함한 블록 찾기
    # Find the script block that contains ALL_ANALYSES
    block2_candidates = [b for b in blocks if "ALL_ANALYSES" in b]
    assert block2_candidates, (
        "ALL_ANALYSES 를 포함하는 <script> 블록을 찾지 못함 — "
        "repo_detail.html 구조가 예상과 다름"
    )

    block2 = block2_candidates[0]

    # IIFE 시작 패턴 — `(function()` 또는 `(() =>` 형식 모두 허용
    # IIFE start pattern — allow both `(function()` and `(() =>` forms
    has_iife_open = bool(
        re.search(r"\(\s*function\s*\(", block2)
        or re.search(r"\(\s*\(\s*\)\s*=>", block2)
    )
    assert has_iife_open, (
        "Script Block 2 가 IIFE 로 시작하지 않음 — htmx-boost 2번째 방문 시 "
        "SyntaxError 회귀 위험. `(function() {` 또는 `(() => {` 패턴 누락."
        "\n실제 블록 앞 200자:\n" + block2[:200]
    )

    # IIFE 닫기 패턴 — `})();` 또는 `})()`
    # IIFE closing pattern — `})();` or `})()`
    has_iife_close = bool(re.search(r"\}\s*\)\s*\(\s*\)\s*;?", block2))
    assert has_iife_close, (
        "Script Block 2 가 IIFE 닫기 패턴으로 끝나지 않음 — `})();` 누락."
        "\n실제 블록 뒤 200자:\n" + block2[-200:]
    )

    # ALL_ANALYSES 가 IIFE 내부에 있는지 위치 검증 (여는 IIFE 이후에 위치해야 함)
    # Verify ALL_ANALYSES is positioned after the IIFE opening (i.e., inside the IIFE)
    iife_open_match = re.search(r"\(\s*function\s*\(", block2)
    all_analyses_pos = block2.find("ALL_ANALYSES")
    assert iife_open_match and all_analyses_pos > iife_open_match.start(), (
        "ALL_ANALYSES 선언이 IIFE 시작보다 앞에 위치함 — IIFE 스코프 밖에 있을 수 있음."
    )


# ─── Test 2: Script Block 1 에 bare `let chart` / `let _chartData` 없어야 함 ──

def test_repo_detail_no_bare_let_chart(rendered_html: str):
    """Script Block 1 에 bare `let chart` 또는 `let _chartData` 선언이 없어야 함.

    Script Block 1 must not contain bare `let chart` or `let _chartData` declarations.

    수정 전 상태 (실패 케이스):
      let chart;
      let _chartData = [];
    → htmx-boost 2번째 방문 시 `SyntaxError: Identifier 'chart' already declared`

    수정 후 상태 (통과 케이스):
      var chart;
      var _chartData = [];
    → `var` 는 재선언이 허용되므로 htmx-boost 재방문 시에도 안전

    Before fix (failure case):
      `let chart` / `let _chartData` → SyntaxError on 2nd htmx-boost visit

    After fix (pass case):
      `var chart` / `var _chartData` → var redeclaration is harmless
    """
    blocks = _extract_script_blocks(rendered_html)

    # ALL_ANALYSES 가 없는 블록들만 검사 (Script Block 1 대상)
    # Inspect blocks that do NOT contain ALL_ANALYSES (these are Script Block 1 candidates)
    block1_candidates = [b for b in blocks if "ALL_ANALYSES" not in b]

    # `let chart` bare 선언 패턴 — 줄 시작 또는 공백 후 `let chart` (세미콜론 또는 줄 끝)
    # Pattern for bare `let chart` — at line start or after whitespace
    bare_let_chart_pattern = re.compile(r"^\s*let\s+chart\s*[;=\n]", re.MULTILINE)
    bare_let_chart_data_pattern = re.compile(r"^\s*let\s+_chartData\s*[;=\n]", re.MULTILINE)

    for block in block1_candidates:
        match_chart = bare_let_chart_pattern.search(block)
        assert not match_chart, (
            "Script Block 에 bare `let chart` 선언 발견 — "
            "htmx-boost 2번째 방문 시 SyntaxError 회귀 위험. "
            "`var chart` 로 변경 필요."
            f"\n일치 문맥: {block[max(0, match_chart.start()-30):match_chart.end()+30]!r}"
        )

        match_chart_data = bare_let_chart_data_pattern.search(block)
        assert not match_chart_data, (
            "Script Block 에 bare `let _chartData` 선언 발견 — "
            "htmx-boost 2번째 방문 시 SyntaxError 회귀 위험. "
            "`var _chartData` 로 변경 필요."
            f"\n일치 문맥: {block[max(0, match_chart_data.start()-30):match_chart_data.end()+30]!r}"
        )


# ─── Test 3: `var chart` 와 `var _chartData` 가 실제로 존재해야 함 ─────────────

def test_repo_detail_var_chart_and_chart_data_present(rendered_html: str):
    """Script Block 1 에 `var chart` 와 `var _chartData` 선언이 존재해야 함.

    Script Block 1 must contain `var chart` and `var _chartData` declarations.

    단순 삭제로 우회하는 회귀를 차단 — 선언 존재 + var 키워드 사용 동시 검증.
    Guards against regressions where declarations are simply removed.
    Both existence and use of `var` are checked simultaneously.
    """
    # ALL_ANALYSES 포함 여부로 구분하지 않고 전체 HTML 검색
    # Search the full rendered HTML (not per-block) for simplicity
    assert re.search(r"\bvar\s+chart\b", rendered_html), (
        "렌더링된 HTML 에 `var chart` 선언 없음 — "
        "Script Block 1 의 `let chart` → `var chart` 수정이 되돌아갔을 수 있음."
    )
    assert re.search(r"\bvar\s+_chartData\b", rendered_html), (
        "렌더링된 HTML 에 `var _chartData` 선언 없음 — "
        "Script Block 1 의 `let _chartData` → `var _chartData` 수정이 되돌아갔을 수 있음."
    )
