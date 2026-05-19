"""회귀 가드 — analysis_detail.html 두 버그 수정 검증.

Regression guard — analysis_detail.html two bug fixes.

버그 1: Chart backgroundColor 무효 CSS
  `backgroundColor: accent + '22'` where `accent = 'rgb(R,G,B)'` (from --accent-rgb)
  → `'rgb(R,G,B)22'` = INVALID CSS → Chart.js fallback `rgba(0,0,0,0.1)` → 차트 영역 검정
  수정: `accentRgb ? ('rgba(' + accentRgb + ', 0.13)') : (accent + '22')`

Bug 1: Chart backgroundColor invalid CSS
  `accent + '22'` when `accent = 'rgb(R,G,B)'` → `'rgb(R,G,B)22'` INVALID CSS
  → Chart.js fallback rgba(0,0,0,0.1) → chart fill area appears BLACK
  Fix: conditionally use rgba() when accentRgb is available

버그 2: 피드백 버튼 핸들러 누적 (IIFE 패턴)
  htmx-boost 재방문 시 `(function() { btns.forEach(addEventListener...) })()` IIFE 가
  재실행 → 동일 버튼에 클릭 핸들러 중복 등록 → 클릭 시 API 다중 호출
  수정: named function `_initFeedback()` + `feedbackInit` 가드 + remove-before-add 패턴

Bug 2: Feedback button handler accumulation (IIFE pattern)
  On htmx-boost re-navigation, the IIFE re-runs, adding duplicate click handlers
  to the same buttons → multiple API calls per click
  Fix: named function `_initFeedback()` + `feedbackInit` guard + remove-before-add

검증 방법:
  Jinja2 Environment 직접 사용 — FastAPI app import 없이 템플릿 소스 구조 검사.
  케이스 A: trend_data ≥ 2 (차트 렌더링) / 케이스 B: trend_data = 1 (차트 비렌더링)
  / 케이스 C: trend_data 없음.

Verification method:
  Jinja2 Environment directly — template structure inspection without FastAPI import.
  Case A: trend_data ≥ 2 (chart renders) / Case B: trend_data = 1 (chart skipped)
  / Case C: no trend_data.
"""
from __future__ import annotations

import re
import pathlib
from types import SimpleNamespace

import pytest
import jinja2

_TEMPLATE_DIR = pathlib.Path(__file__).parents[3] / "src" / "templates"

# 최소 analysis 객체 — SimpleNamespace 로 속성 접근 가능
# Minimal analysis object — attribute access via SimpleNamespace
_ANALYSIS = SimpleNamespace(
    id=42,
    score=82,
    grade="B",
    commit_sha="abc1234567890",
    pr_number=7,
    commit_message="test: add regression guard",
    result={
        "summary": "Test summary text",
        "ai_review": None,
        "ai_review_status": "success",
        "ai_suggestions": [],
        "issues": [],
        "file_feedbacks": [],
    },
    created_at="2026-05-20T10:00:00",
    repo_id=1,
    thumbs=None,
)

# 케이스 A 컨텍스트 — trend_data ≥ 2 → 차트 블록 렌더링됨
# Case A context — trend_data ≥ 2 → chart block rendered
_CTX_WITH_TREND = {
    "analysis": _ANALYSIS,
    "repo_name": "owner/test-repo",
    "current_user": None,
    "locale": "ko",
    "user_feedback": None,
    "trend_data": [
        {"id": 41, "score": 78, "label": "05/19"},
        {"id": 42, "score": 82, "label": "05/20"},
    ],
    "prev_id": 41,
    "next_id": None,
}

# 케이스 B 컨텍스트 — trend_data = 1 → 차트 블록 생략 (|length > 1 조건 불충족)
# Case B context — trend_data = 1 → chart block skipped (|length > 1 condition fails)
_CTX_ONE_TREND = {
    **_CTX_WITH_TREND,
    "trend_data": [{"id": 42, "score": 82, "label": "05/20"}],
}

# 케이스 C 컨텍스트 — trend_data 미정의 → 차트 블록 생략
# Case C context — trend_data undefined → chart block skipped
_CTX_NO_TREND = {
    k: v for k, v in _CTX_WITH_TREND.items() if k != "trend_data"
}


def _make_env() -> jinja2.Environment:
    """i18n 필터 등록된 Jinja2 Environment 반환.

    Return a Jinja2 Environment with i18n filters registered.
    """
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=jinja2.select_autoescape(["html"]),
        undefined=jinja2.Undefined,
    )
    from src.i18n.filters import register_i18n_filters
    register_i18n_filters(env)
    return env


@pytest.fixture(scope="module")
def env() -> jinja2.Environment:
    return _make_env()


@pytest.fixture(scope="module")
def html_with_trend(env: jinja2.Environment) -> str:
    """케이스 A — trend_data ≥ 2, 차트 렌더링됨.

    Case A — trend_data ≥ 2, chart block rendered.
    """
    return env.get_template("analysis_detail.html").render(**_CTX_WITH_TREND)


@pytest.fixture(scope="module")
def html_one_trend(env: jinja2.Environment) -> str:
    """케이스 B — trend_data = 1, 차트 블록 생략.

    Case B — trend_data = 1, chart block skipped.
    """
    return env.get_template("analysis_detail.html").render(**_CTX_ONE_TREND)


@pytest.fixture(scope="module")
def html_no_trend(env: jinja2.Environment) -> str:
    """케이스 C — trend_data 미정의, 차트 블록 생략.

    Case C — trend_data undefined, chart block skipped.
    """
    return env.get_template("analysis_detail.html").render(**_CTX_NO_TREND)


def _script_blocks(html: str) -> list[str]:
    """<script> 블록 내용 추출 / Extract <script> block contents."""
    return re.findall(
        r"<script\b[^>]*>(.*?)</script\b[^>]*>",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )


# ─── Bug 1 회귀 가드: chart backgroundColor ────────────────────────────────────

class TestChartBackgroundColor:
    """Bug 1: accent + '22' 무효 CSS 패턴 → rgba() 조건부 패턴으로 교체.

    Bug 1: accent + '22' invalid CSS → replaced with conditional rgba() pattern.
    """

    def test_case_a_invalid_css_pattern_absent(self, html_with_trend: str):
        """케이스 A (차트 렌더링): 조건 없는 bare `backgroundColor: accent + '22'` 패턴이 없어야 함.

        Case A (chart rendered): bare `backgroundColor: accent + '22'` (without ternary) must NOT appear.

        Before fix (INVALID):
          `backgroundColor: accent + '22',`
          → when accent = 'rgb(R,G,B)' (from --accent-rgb): produces 'rgb(R,G,B)22' invalid CSS

        After fix (VALID):
          `backgroundColor: accentRgb ? ('rgba(' + accentRgb + ', 0.13)') : (accent + '22'),`
          → ternary guard: fallback '(accent + "22")' still literal in source but
            accentRgb path always taken (--accent-rgb is defined in all themes).
        """
        # OLD バグパターン: ternary なしの bare backgroundColor 行全体を検索
        # OLD bug pattern: search for the exact bare backgroundColor line without ternary
        assert not re.search(
            r"backgroundColor\s*:\s*accent\s*\+\s*['\"]22['\"],",
            html_with_trend,
        ), (
            "Bug 1 회귀: `backgroundColor: accent + '22'` bare 패턴이 analysis_detail.html 에 남아 있음. "
            "--accent-rgb 가 정의된 테마에서 'rgb(R,G,B)22' 무효 CSS → 차트 검정 배경 재발. "
            "수정: `accentRgb ? ('rgba(' + accentRgb + ', 0.13)') : (accent + '22')` 패턴 유지."
        )

    def test_case_a_rgba_condition_present_in_chart_block(self, html_with_trend: str):
        """케이스 A: 차트 스크립트 블록에 accentRgb 조건부 rgba() 패턴이 있어야 함.

        Case A: chart script block must contain the conditional rgba() pattern.
        """
        blocks = _script_blocks(html_with_trend)
        trend_blocks = [b for b in blocks if "TREND" in b or "trendChart" in b]
        assert trend_blocks, "TREND 또는 trendChart 를 포함하는 <script> 블록을 찾을 수 없음."

        chart_block = trend_blocks[0]
        assert re.search(
            r"accentRgb\s*\?\s*\(['\"]rgba\(",
            chart_block,
        ), (
            "차트 블록에 `accentRgb ? ('rgba(...` 패턴이 없음 — Bug 1 수정이 되돌아갔을 수 있음. "
            f"블록 앞 300자:\n{chart_block[:300]}"
        )

    def test_case_a_rgba_uses_correct_alpha(self, html_with_trend: str):
        """케이스 A: rgba 알파값이 0.13 (0x22/0xFF ≈ 0.133) 이어야 함.

        Case A: rgba alpha value must be 0.13 (approximation of 0x22/0xFF).
        """
        assert "rgba(' + accentRgb + ', 0.13)" in html_with_trend, (
            "chart backgroundColor rgba 알파값이 0.13 이 아님 — "
            "원래 0x22 불투명도(13%)와 다를 수 있음."
        )

    def test_case_b_no_chart_block_renders(self, html_one_trend: str):
        """케이스 B (trend_data=1): 차트 블록이 렌더링되지 않아야 함.

        Case B (trend_data=1): chart block must NOT be rendered.
        """
        assert "trendChart" not in html_one_trend, (
            "trend_data 가 1개일 때 차트 블록이 렌더링됨 — "
            "`trend_data|length > 1` 조건이 제대로 동작하지 않음."
        )

    def test_case_c_no_chart_block_renders(self, html_no_trend: str):
        """케이스 C (trend_data 없음): 차트 블록이 렌더링되지 않아야 함.

        Case C (trend_data undefined): chart block must NOT be rendered.
        """
        assert "trendChart" not in html_no_trend, (
            "trend_data 미정의 시 차트 블록이 렌더링됨 — "
            "`trend_data is defined` 조건이 제대로 동작하지 않음."
        )

    def test_case_b_invalid_pattern_absent(self, html_one_trend: str):
        """케이스 B: 차트 미렌더링 시에도 bare backgroundColor 버그 패턴이 없어야 함.

        Case B: even without chart, bare backgroundColor bug pattern must not appear.
        """
        assert not re.search(
            r"backgroundColor\s*:\s*accent\s*\+\s*['\"]22['\"],",
            html_one_trend,
        ), (
            "케이스 B 에서 bare `backgroundColor: accent + '22'` 패턴 잔존 — 예기치 않은 위치 있음."
        )


# ─── Bug 2 회귀 가드: 피드백 버튼 핸들러 누적 ──────────────────────────────────

class TestFeedbackButtonHandler:
    """Bug 2: 피드백 IIFE → named function + remove-before-add 패턴 전환.

    Bug 2: Feedback IIFE → named function + remove-before-add pattern.
    """

    def test_feedback_iife_pattern_absent(self, html_with_trend: str):
        """피드백 블록에 익명 IIFE `(function()` 패턴이 없어야 함.

        Feedback block must NOT contain anonymous IIFE `(function()` pattern.

        Before fix: `(function() { ... btns.forEach(btn => btn.addEventListener...) })();`
        After fix:  named function `_initFeedback()` with feedbackInit guard.

        Note: 차트 블록의 `(function()` IIFE 는 허용 — 피드백 블록 한정 검사.
        Note: `(function()` in chart block is allowed — only feedback-specific check here.
        """
        blocks = _script_blocks(html_with_trend)
        # 피드백 관련 스크립트 블록 찾기 — feedbackCard 또는 fb-btn 참조
        # Find feedback-related blocks — those referencing feedbackCard or fb-btn
        fb_blocks = [b for b in blocks if "feedbackCard" in b or "fb-btn" in b]
        assert fb_blocks, "feedbackCard 또는 fb-btn 을 포함하는 <script> 블록을 찾을 수 없음."

        fb_block = fb_blocks[0]
        # 피드백 블록 안에 익명 IIFE 가 없어야 함
        # Feedback block must not start with anonymous IIFE
        has_anonymous_iife = bool(
            re.search(r"^\s*\(\s*function\s*\(\s*\)\s*\{", fb_block, re.MULTILINE)
        )
        assert not has_anonymous_iife, (
            "피드백 스크립트 블록이 익명 IIFE `(function() {` 로 시작함 — "
            "htmx-boost 재방문 시 핸들러 중복 등록 회귀. "
            "named function `_initFeedback()` + remove-before-add 패턴 유지 필요."
            f"\n블록 앞 200자:\n{fb_block[:200]}"
        )

    def test_named_function_init_feedback_present(self, html_with_trend: str):
        """named function `_initFeedback` 가 피드백 블록에 있어야 함.

        Named function `_initFeedback` must be present in feedback block.
        """
        assert "_initFeedback" in html_with_trend, (
            "피드백 블록에 `_initFeedback` named function 이 없음 — "
            "Bug 2 수정이 되돌아갔을 수 있음."
        )

    def test_remove_before_add_handler_present(self, html_with_trend: str):
        """document._adFeedbackHandler remove-before-add 패턴이 있어야 함.

        `document._adFeedbackHandler` remove-before-add pattern must be present.
        """
        assert "document._adFeedbackHandler" in html_with_trend, (
            "`document._adFeedbackHandler` 패턴이 없음 — "
            "htmx 이벤트 리스너 remove-before-add 패턴 누락."
        )
        assert "removeEventListener('htmx:afterSettle', document._adFeedbackHandler)" in html_with_trend, (
            "htmx:afterSettle remove 패턴 없음 — stale closure 위험."
        )
        assert "removeEventListener('htmx:historyRestore', document._adFeedbackHandler)" in html_with_trend, (
            "htmx:historyRestore remove 패턴 없음 — 뒤로가기 재방문 시 핸들러 누적 위험."
        )

    def test_feedback_init_guard_present(self, html_with_trend: str):
        """feedbackInit guard 가 피드백 블록에 있어야 함.

        `feedbackInit` guard must be present in feedback block.

        이 가드가 없으면 `htmx:afterSettle` 이 비내비게이션 요청에도 발화할 때
        동일 DOM 에 버튼 핸들러가 중복 등록됨.

        Without this guard, `htmx:afterSettle` firing for non-navigation requests
        would add duplicate button handlers to the same DOM nodes.
        """
        assert "feedbackInit" in html_with_trend, (
            "피드백 블록에 `feedbackInit` guard 가 없음 — "
            "동일 DOM 재방문 시 핸들러 중복 등록 방지 누락."
        )

    def test_feedback_handler_registered_for_htmx_events(self, html_with_trend: str):
        """htmx:afterSettle 과 htmx:historyRestore 에 핸들러 등록이 있어야 함.

        Handler must be registered for htmx:afterSettle and htmx:historyRestore.
        """
        assert "addEventListener('htmx:afterSettle', document._adFeedbackHandler)" in html_with_trend, (
            "htmx:afterSettle 이벤트 등록 없음 — htmx 내비게이션 시 피드백 버튼 미작동."
        )
        assert "addEventListener('htmx:historyRestore', document._adFeedbackHandler)" in html_with_trend, (
            "htmx:historyRestore 이벤트 등록 없음 — 뒤로가기 시 피드백 버튼 미작동."
        )

    def test_case_b_feedback_card_still_renders(self, html_one_trend: str):
        """케이스 B: 차트 없어도 피드백 카드는 렌더링되어야 함.

        Case B: feedback card must render even without chart.
        """
        assert "feedbackCard" in html_one_trend, (
            "케이스 B 에서 피드백 카드가 렌더링되지 않음 — "
            "피드백 기능이 trend_data 에 의존적으로 잘못 조건화됐을 수 있음."
        )
        assert "_initFeedback" in html_one_trend, (
            "케이스 B 에서 _initFeedback 함수가 없음 — 피드백 초기화 로직 누락."
        )

    def test_case_c_feedback_card_still_renders(self, html_no_trend: str):
        """케이스 C: trend_data 없어도 피드백 카드 렌더링 및 핸들러 등록.

        Case C: feedback card and handler must render without trend_data.
        """
        assert "feedbackCard" in html_no_trend, (
            "케이스 C 에서 피드백 카드가 렌더링되지 않음."
        )
        assert "_initFeedback" in html_no_trend, (
            "케이스 C 에서 _initFeedback 함수가 없음."
        )
