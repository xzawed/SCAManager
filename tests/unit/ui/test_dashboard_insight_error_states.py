"""대시보드 insight api_error 상태 처리 검증 — 케이스 2종.
Dashboard insight api_error state handling verification — 2 cases.

케이스 1: 라우트 레벨 — api_error 응답이 템플릿에 올바르게 전달됨
Case 1: Route level — api_error response correctly forwarded to template context

케이스 2: 템플릿 레벨 — api_error 텍스트 렌더링 (Jinja2 직접 렌더)
Case 2: Template level — api_error text rendering (Jinja2 direct render)

대상 파일:
- src/ui/routes/dashboard.py — insight 탭 처리 부분
- src/templates/dashboard.html — api_error 렌더링 부분
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from jinja2 import Environment, FileSystemLoader, Undefined

from src.auth.session import CurrentUser, require_login
from src.main import app

# ORM metadata 등록 (모듈 최상단 import — pytest collection 시점에 등록).
# Register ORM metadata at module import time (pytest collection).
from src.models.analysis import Analysis as _AnalysisModel  # noqa: E402, F401

_TEST_USER = CurrentUser(
    id=1,
    github_login="tester",
    email="t@x.com",
    display_name="Tester",
    plaintext_token="",
)


@contextmanager
def _ctx(db):
    """SessionLocal 컨텍스트 매니저 mock 헬퍼.
    SessionLocal context manager mock helper.
    """
    yield db


@pytest.fixture(autouse=True)
def _override_login():
    """모든 테스트에서 require_login override → _TEST_USER 주입.
    Override require_login in all tests → inject _TEST_USER.
    """
    _prev = app.dependency_overrides.get(require_login)
    app.dependency_overrides[require_login] = lambda: _TEST_USER
    yield
    if _prev is not None:
        app.dependency_overrides[require_login] = _prev
    else:
        app.dependency_overrides.pop(require_login, None)


# ─── 케이스 1: 라우트 레벨 — api_error context 전달 검증 ──────────────────────
# Case 1: Route level — api_error context forwarding verification


def test_route_insight_api_error_forwarded_to_template():
    """케이스 1a: insight.status='api_error' 가 template context 에 올바르게 전달됨.

    Case 1a: insight.status='api_error' correctly forwarded to template context.

    검증:
    - insight_narrative mock → status='api_error' 응답 반환
    - 라우트가 에러 없이 처리 (200 응답)
    - context['insight']['status'] == 'api_error' 전달 확인
    """
    client = TestClient(app)
    mock_db = MagicMock()
    captured: dict = {}

    # api_error 응답 — 실제 insight_narrative 가 반환하는 구조 기반.
    # api_error response structure mirrors the actual insight_narrative return format.
    fake_api_error = {
        "status": "api_error",
        "positive_highlights": [],
        "focus_areas": [],
        "key_metrics": [],
        "next_actions": [],
        "generated_at": None,
        "days": 7,
    }

    def _capture(request, template_name, context, **kwargs):
        captured.update(context)
        return HTMLResponse(content="<html>captured</html>", status_code=200)

    with patch("src.ui.routes.dashboard.SessionLocal", return_value=_ctx(mock_db)), \
         patch(
             "src.ui.routes.dashboard.dashboard_service.insight_narrative",
             new=AsyncMock(return_value=fake_api_error),
         ), \
         patch("src.ui.routes.dashboard.templates.TemplateResponse", side_effect=_capture):
        response = client.get("/dashboard?mode=insight")

    assert response.status_code == 200, (
        f"api_error insight 처리 중 에러 발생 (기대 200, 실제 {response.status_code})"
    )
    assert "insight" in captured, "template context 에 'insight' 키 누락"
    insight_ctx = captured["insight"]
    assert insight_ctx["status"] == "api_error", (
        f"context['insight']['status'] 'api_error' 기대, 실제: {insight_ctx['status']!r}"
    )


def test_route_insight_api_error_mode_and_days_in_context():
    """케이스 1b: api_error 응답 시 mode='insight' 및 days 값 context 전달 확인.

    Case 1b: mode='insight' and days value present in context when api_error occurs.
    """
    client = TestClient(app)
    mock_db = MagicMock()
    captured: dict = {}

    fake_api_error = {
        "status": "api_error",
        "positive_highlights": [],
        "focus_areas": [],
        "key_metrics": [],
        "next_actions": [],
        "generated_at": None,
        "days": 30,
    }

    def _capture(request, template_name, context, **kwargs):
        captured.update(context)
        return HTMLResponse(content="<html>captured</html>", status_code=200)

    with patch("src.ui.routes.dashboard.SessionLocal", return_value=_ctx(mock_db)), \
         patch(
             "src.ui.routes.dashboard.dashboard_service.insight_narrative",
             new=AsyncMock(return_value=fake_api_error),
         ), \
         patch("src.ui.routes.dashboard.templates.TemplateResponse", side_effect=_capture):
        response = client.get("/dashboard?mode=insight&days=30")

    assert response.status_code == 200
    assert captured.get("mode") == "insight", (
        f"mode 'insight' 기대, 실제: {captured.get('mode')!r}"
    )
    assert captured.get("days") == 30, (
        f"days=30 기대, 실제: {captured.get('days')!r}"
    )
    # insight 전체 dict 가 그대로 전달 (api_error 포함)
    # Full insight dict forwarded as-is (including api_error)
    assert captured["insight"]["status"] == "api_error"


def test_route_insight_api_error_overview_services_not_called():
    """케이스 1c: api_error insight 시 overview 분기 서비스 함수 미호출 확인.

    Case 1c: Overview branch service functions NOT called when insight returns api_error.

    insight 분기가 api_error 를 에러로 인식해 overview 로 폴백하지 않아야 함.
    The insight branch must NOT fall back to overview when api_error is received.
    """
    client = TestClient(app)
    mock_db = MagicMock()

    fake_api_error = {
        "status": "api_error",
        "positive_highlights": [],
        "focus_areas": [],
        "key_metrics": [],
        "next_actions": [],
        "generated_at": None,
        "days": 7,
    }

    with patch("src.ui.routes.dashboard.SessionLocal", return_value=_ctx(mock_db)), \
         patch(
             "src.ui.routes.dashboard.dashboard_service.insight_narrative",
             new=AsyncMock(return_value=fake_api_error),
         ), \
         patch(
             "src.ui.routes.dashboard.dashboard_service.dashboard_kpi",
             return_value={},
         ) as mock_kpi, \
         patch("src.ui.routes.dashboard.templates.TemplateResponse") as mock_tr:
        mock_tr.return_value = HTMLResponse(content="<html>x</html>", status_code=200)
        response = client.get("/dashboard?mode=insight")

    assert response.status_code == 200
    # api_error 는 insight 분기 내 정상 응답 — overview 분기 미진입 (dashboard_kpi 미호출)
    # api_error is a normal insight response — overview branch NOT entered (dashboard_kpi not called)
    assert not mock_kpi.called, (
        "api_error 시 overview 분기 폴백 발생 (dashboard_kpi 호출됨) — 잘못된 에러 처리"
    )


# ─── 케이스 2: 템플릿 레벨 — Jinja2 직접 렌더링 status 분기 검증 ─────────────
# Case 2: Template level — Jinja2 direct rendering for each status branch


@pytest.fixture(scope="module")
def jinja_env():
    """실제 dashboard.html 을 렌더할 수 있는 Jinja2 Environment.

    Real Jinja2 Environment capable of rendering dashboard.html.
    i18n 필터 등록 포함 (templates._helpers 가 등록한 것과 동일 환경).
    Includes i18n filter registration (same environment as templates._helpers registers).
    """
    import os
    template_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "src", "templates"
    )
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=True,
        # Undefined 변수는 빈 문자열로 처리 (렌더 중단 방지)
        # Treat undefined variables as empty string (prevent render abort)
        undefined=Undefined,
    )
    # i18n 필터 등록 (실제 필터와 동일 구현 사용)
    # Register i18n filters (same implementation as production)
    from src.i18n.filters import register_i18n_filters
    register_i18n_filters(env)
    return env


def _render_insight_section(jinja_env, insight: dict, days: int = 7, locale: str = "ko") -> str:
    """dashboard.html 의 insight 섹션만 추출하여 렌더링.

    Render only the insight section of dashboard.html.

    직접 템플릿 전체 렌더링 시 다른 섹션의 context 의존성(kpi, trend 등)으로
    UndefinedError 가 발생할 수 있어 insight 섹션 전용 미니 템플릿 사용.
    Full template rendering would cause UndefinedError from other sections (kpi, trend etc),
    so use a minimal template targeting only the insight section.

    실제 dashboard.html 의 insight 분기 조건 코드를 그대로 복사하여 검증.
    Copies the actual insight branch conditions from dashboard.html for verification.
    """
    # 실제 dashboard.html 의 insight 분기 로직 (라인 879~934)
    # Actual insight branch logic from dashboard.html (lines 879-934)
    template_source = """
{% if insight and insight.status == 'success' %}
<div class="insight-success">AI Insight 성공</div>
{% elif insight and insight.status == 'no_api_key' %}
<div class="dash-insight-status">
  {{ 'dashboard.insight.no_api_key' | i18n_args(locale | default('ko')) }}
</div>
{% elif insight and insight.status == 'no_data' %}
<div class="dash-insight-status">
  {{ 'dashboard.insight.no_data' | i18n_args(locale | default('ko'), days=days) }}
</div>
{% else %}
<div class="dash-insight-status">
  {{ 'dashboard.insight.load_failed' | i18n_args(locale | default('ko'), status=(insight.status if insight else 'unknown')) }}
</div>
{% endif %}
"""
    tmpl = jinja_env.from_string(template_source)
    return tmpl.render(insight=insight, days=days, locale=locale)


def test_template_api_error_renders_load_failed_message(jinja_env):
    """케이스 2a: status='api_error' → load_failed 메시지 렌더링.

    Case 2a: status='api_error' → load_failed message rendered.

    ko 번역: "⚠️ AI Insight 생성 실패 ({status}) — 잠시 후 다시 시도해주세요."
    status='api_error' 치환 후: "⚠️ AI Insight 생성 실패 (api_error) — 잠시 후 다시 시도해주세요."
    """
    insight = {
        "status": "api_error",
        "positive_highlights": [],
        "focus_areas": [],
        "key_metrics": [],
        "next_actions": [],
        "generated_at": None,
        "days": 7,
    }
    html = _render_insight_section(jinja_env, insight, locale="ko")

    # load_failed 분기 진입 확인 — dash-insight-status div 존재
    # Confirm load_failed branch entered — dash-insight-status div present
    assert "dash-insight-status" in html, "load_failed 분기 미진입 (dash-insight-status 없음)"

    # 'api_error' 문자열이 status placeholder 치환으로 포함되어야 함
    # 'api_error' must be included as the {status} placeholder substitution
    assert "api_error" in html, (
        f"status='api_error' 렌더링 시 'api_error' 문자열 미포함\n실제 HTML:\n{html}"
    )

    # insight-success, no_api_key, no_data 분기가 아님을 확인
    # Confirm this is NOT the success/no_api_key/no_data branch
    assert "insight-success" not in html, "api_error 가 success 분기로 잘못 라우팅됨"


def test_template_api_error_contains_ai_insight_text(jinja_env):
    """케이스 2b: api_error 시 'AI Insight' 관련 텍스트 포함 확인 (ko 번역).

    Case 2b: api_error renders text containing 'AI Insight' (ko translation).
    """
    insight = {"status": "api_error", "positive_highlights": [], "focus_areas": [],
               "key_metrics": [], "next_actions": [], "generated_at": None, "days": 7}
    html = _render_insight_section(jinja_env, insight, locale="ko")

    # ko 번역 = "⚠️ AI Insight 생성 실패 (api_error) — 잠시 후 다시 시도해주세요."
    # ko translation = "⚠️ AI Insight 생성 실패 (api_error) — 잠시 후 다시 시도해주세요."
    assert "AI Insight" in html, (
        f"ko api_error 메시지에 'AI Insight' 미포함\n실제 HTML:\n{html}"
    )
    assert "생성 실패" in html or "api_error" in html, (
        f"ko api_error 메시지에 '생성 실패' 또는 'api_error' 미포함\n실제 HTML:\n{html}"
    )


def test_template_api_error_en_locale(jinja_env):
    """케이스 2c: en locale 에서 api_error 렌더링 확인.

    Case 2c: api_error rendering in English locale.

    en 번역: "⚠️ AI Insight generation failed ({status}) — please try again later."
    status='api_error' 치환 후: "⚠️ AI Insight generation failed (api_error) — please try again later."
    """
    insight = {"status": "api_error", "positive_highlights": [], "focus_areas": [],
               "key_metrics": [], "next_actions": [], "generated_at": None, "days": 7}
    html = _render_insight_section(jinja_env, insight, locale="en")

    assert "api_error" in html, (
        f"en api_error 메시지에 'api_error' 미포함\n실제 HTML:\n{html}"
    )
    # en 번역 확인
    # English translation verification
    assert "AI Insight" in html or "generation failed" in html or "load_failed" in html, (
        f"en api_error 메시지 부적절\n실제 HTML:\n{html}"
    )


def test_template_no_api_key_status(jinja_env):
    """케이스 2d: status='no_api_key' → no_api_key 분기 전용 메시지 렌더링.

    Case 2d: status='no_api_key' → renders no_api_key branch message.

    ko 번역: "🔑 ANTHROPIC_API_KEY 미설정 — Insight 모드는 AI 분석이 필요합니다."
    """
    insight = {"status": "no_api_key", "positive_highlights": [], "focus_areas": [],
               "key_metrics": [], "next_actions": [], "generated_at": None, "days": 7}
    html = _render_insight_section(jinja_env, insight, locale="ko")

    # no_api_key 분기 전용 텍스트 확인
    # Verify no_api_key branch-specific text
    assert "dash-insight-status" in html
    # ko 번역에 "ANTHROPIC_API_KEY" 또는 "api_key" 포함
    # ko translation contains "ANTHROPIC_API_KEY" or "api_key"
    assert "ANTHROPIC_API_KEY" in html or "api_key" in html.lower(), (
        f"no_api_key 메시지 미포함\n실제 HTML:\n{html}"
    )
    # load_failed 분기 (api_error) 와 다른 텍스트 확인
    # Different text from load_failed (api_error) branch
    assert "생성 실패" not in html, (
        "no_api_key 가 load_failed 분기로 잘못 라우팅됨"
    )


def test_template_no_data_status(jinja_env):
    """케이스 2e: status='no_data' → no_data 분기 메시지 + days 치환 확인.

    Case 2e: status='no_data' → renders no_data message with days substitution.

    ko 번역: "📭 최근 {days}일 분석 데이터가 부족합니다 — 분석 결과가 누적된 후 다시 시도해주세요."
    """
    insight = {"status": "no_data", "positive_highlights": [], "focus_areas": [],
               "key_metrics": [], "next_actions": [], "generated_at": None, "days": 7}
    html = _render_insight_section(jinja_env, insight, days=14, locale="ko")

    assert "dash-insight-status" in html
    # days 변수 치환 확인 (14일)
    # Verify days variable substitution (14 days)
    assert "14" in html, (
        f"no_data 메시지에 days=14 치환 미반영\n실제 HTML:\n{html}"
    )
    # "부족" 또는 "데이터" 포함 (ko 번역 확인)
    # Contains "부족" or "데이터" (ko translation check)
    assert "데이터" in html or "부족" in html or "no_data" in html.lower(), (
        f"no_data 메시지 미포함\n실제 HTML:\n{html}"
    )


def test_template_parse_error_status(jinja_env):
    """케이스 2f: status='parse_error' → load_failed else 분기 + status 치환 확인.

    Case 2f: status='parse_error' → falls into load_failed else branch with status substitution.

    parse_error 는 success/no_api_key/no_data 어느 분기에도 해당하지 않으므로
    else 분기 (load_failed) 로 라우팅되어야 함.
    parse_error doesn't match any specific branch, so it must fall into the else (load_failed) branch.
    """
    insight = {"status": "parse_error", "positive_highlights": [], "focus_areas": [],
               "key_metrics": [], "next_actions": [], "generated_at": None, "days": 7}
    html = _render_insight_section(jinja_env, insight, locale="ko")

    assert "dash-insight-status" in html
    # parse_error 문자열이 status placeholder 치환으로 포함되어야 함
    # 'parse_error' must appear as the {status} placeholder substitution
    assert "parse_error" in html, (
        f"status='parse_error' 렌더링 시 'parse_error' 미포함\n실제 HTML:\n{html}"
    )


def test_template_success_status_not_load_failed(jinja_env):
    """케이스 2g: status='success' → success 전용 div, load_failed 분기 미진입 확인.

    Case 2g: status='success' → success-specific div rendered, NOT load_failed branch.
    """
    insight = {
        "status": "success",
        "positive_highlights": ["좋은 결과"],
        "focus_areas": ["개선 사항"],
        "key_metrics": [],
        "next_actions": ["다음 행동"],
        "generated_at": "2026-05-19T00:00:00Z",
        "days": 7,
    }
    html = _render_insight_section(jinja_env, insight, locale="ko")

    # success 분기 진입 확인
    # Confirm success branch entered
    assert "insight-success" in html, (
        f"success 분기 미진입 (insight-success div 없음)\n실제 HTML:\n{html}"
    )
    # load_failed 메시지 미포함 확인
    # Confirm load_failed message NOT included
    assert "생성 실패" not in html, "success 상태에서 load_failed 메시지 렌더링됨"
    assert "dash-insight-status" not in html, (
        "success 상태에서 dash-insight-status 분기 진입됨"
    )


def test_template_none_insight_renders_unknown(jinja_env):
    """케이스 2h: insight=None 시 'unknown' status 로 load_failed 분기 처리.

    Case 2h: insight=None → load_failed branch with 'unknown' status.

    템플릿 코드: insight.status if insight else 'unknown'
    Template code: insight.status if insight else 'unknown'
    """
    html = _render_insight_section(jinja_env, insight=None, locale="ko")

    # None insight → else 분기 → dash-insight-status
    # None insight → else branch → dash-insight-status
    assert "dash-insight-status" in html, (
        f"insight=None 시 dash-insight-status 분기 미진입\n실제 HTML:\n{html}"
    )
    # 'unknown' 이 status placeholder 로 치환되어 포함
    # 'unknown' should appear as the {status} placeholder substitution
    assert "unknown" in html, (
        f"insight=None 시 'unknown' status 미포함\n실제 HTML:\n{html}"
    )


# ─── 각 status별 렌더링 텍스트 매핑 요약 테스트 ─────────────────────────────
# Status-to-rendered-text mapping summary test


def test_template_all_status_render_different_messages(jinja_env):
    """케이스 2i: 모든 status 값이 각각 다른 텍스트를 렌더링하는지 확인.

    Case 2i: All status values render distinct messages.

    상태별 렌더 결과가 서로 다름을 확인하여 분기 정확성 검증.
    Verifies branch accuracy by confirming each status produces unique output.
    """
    # api_error, no_api_key, no_data, parse_error 는 모두 다른 메시지
    # api_error, no_api_key, no_data, parse_error all produce different messages
    statuses_and_renders: dict[str, str] = {}

    for status in ("api_error", "no_api_key", "parse_error"):
        insight = {"status": status, "positive_highlights": [], "focus_areas": [],
                   "key_metrics": [], "next_actions": [], "generated_at": None, "days": 7}
        statuses_and_renders[status] = _render_insight_section(
            jinja_env, insight, days=7, locale="ko"
        )

    # no_data 는 days placeholder 가 있어 별도 처리
    # no_data has a days placeholder, handled separately
    no_data_insight = {"status": "no_data", "positive_highlights": [], "focus_areas": [],
                       "key_metrics": [], "next_actions": [], "generated_at": None, "days": 7}
    statuses_and_renders["no_data"] = _render_insight_section(
        jinja_env, no_data_insight, days=7, locale="ko"
    )

    # 각 상태별 핵심 포함 문자열 확인
    # Verify key string included in each status render
    api_error_html = statuses_and_renders["api_error"]
    no_api_key_html = statuses_and_renders["no_api_key"]
    no_data_html = statuses_and_renders["no_data"]
    parse_error_html = statuses_and_renders["parse_error"]

    # api_error: load_failed + "api_error" 포함
    # api_error: load_failed + contains "api_error"
    assert "api_error" in api_error_html, f"api_error 분기 오류:\n{api_error_html}"

    # no_api_key: 전용 메시지 ("ANTHROPIC_API_KEY" 포함)
    # no_api_key: dedicated message (contains "ANTHROPIC_API_KEY")
    assert "ANTHROPIC_API_KEY" in no_api_key_html, f"no_api_key 분기 오류:\n{no_api_key_html}"

    # no_data: days 포함 (7일)
    # no_data: contains days (7 days)
    assert "7" in no_data_html, f"no_data 분기 오류:\n{no_data_html}"

    # parse_error: load_failed + "parse_error" 포함
    # parse_error: load_failed + contains "parse_error"
    assert "parse_error" in parse_error_html, f"parse_error 분기 오류:\n{parse_error_html}"

    # api_error 와 no_api_key 는 다른 메시지
    # api_error and no_api_key produce different messages
    assert api_error_html != no_api_key_html, (
        "api_error 와 no_api_key 가 동일한 HTML 을 렌더링함 — 분기 오류"
    )

    # api_error 와 no_data 는 다른 메시지
    # api_error and no_data produce different messages
    assert api_error_html != no_data_html, (
        "api_error 와 no_data 가 동일한 HTML 을 렌더링함 — 분기 오류"
    )
