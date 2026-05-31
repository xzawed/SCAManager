"""사이클 147 Sprint 2 — repo_insights.html render-parity 가드 (회고 P1-4).

Cycle 147 Sprint 2 — repo_insights.html render-parity guards (retro P1-4).

배경 (Background):
사이클 146 신규 테스트(test_i18n_common_repo_insights.py)는 JSON 키 존재만 검증.
템플릿이 오타 키를 호출하면 raw 'repo_insights.<key>' 가 노출되나 키 존재 테스트는
통과하는 사각 존재. 사이클 144 #696 render-parity 패턴을 사이클 146 키에 적용.

검증 방식 (Approach):
실제 Jinja2 환경 + register_i18n_filters 로 repo_insights.html(base.html 상속)을
렌더 → 번역 텍스트가 출력에 포함되는지 assert. 오타 키면 raw 키가 노출되어 실패.
조건부 카드(recurring/category/problem/ai)는 context override 로 활성화.
"""
from __future__ import annotations

import re

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.i18n.filters import register_i18n_filters


def _render(template_name: str, **context) -> str:
    env = Environment(
        loader=FileSystemLoader("src/templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    register_i18n_filters(env)
    return env.get_template(template_name).render(**context)


class _FakeUser:
    github_login = "alice"
    display_name = "Alice"
    is_telegram_connected = False
    preferred_language = "ko"


class _FakeRepo:
    full_name = "owner/repo"
    id = 1


def _kpi(**overrides) -> dict:
    base = {
        "grade": "B",
        "avg_score": 82,
        "analysis_count": 5,
        "top_recurring_issue": "unused import",
        "top_recurring_count": 3,
        "high_security_count": 2,
        "score_delta": 1.5,
    }
    base.update(overrides)
    return base


def _ri_ctx(**overrides) -> dict:
    """모든 조건부 카드를 활성화한 fully-populated context.

    Fully-populated context activating every conditional card.
    조건부 블록(recurring/category/problem/ai 카드)을 모두 켜서
    해당 카드의 i18n 키가 렌더되도록 함.
    """
    base = {
        "current_user": _FakeUser(),
        "repo": _FakeRepo(),
        "days": 30,
        "kpi": _kpi(),
        "recurring_issues": [
            {"message": "unused import x", "tool": "pylint", "count": 3, "severity": "warning"},
        ],
        "problem_files": [{"path": "a.py", "count": 2}],
        "ai_suggestions": [{"text": "use caching", "count": 2}],
        "breakdown": {"total": 5},
        "narrative": {"text": "코드 품질이 양호합니다."},
        # locale 은 _render(locale=...) 로 전달 — 중복 방지
        # locale is passed via _render(locale=...) to avoid duplicate kwarg
    }
    base.update(overrides)
    return base


def _ri_ctx_empty(**overrides) -> dict:
    """empty-state context — 분석 0건 경로 (empty_no_data 블록 활성화)."""
    base = _ri_ctx(
        kpi=_kpi(analysis_count=0, avg_score=None, top_recurring_issue=None,
                 top_recurring_count=0, high_security_count=0, score_delta=None),
        recurring_issues=[],
        problem_files=[],
        ai_suggestions=[],
        breakdown={"total": 0},
        narrative=None,
    )
    base.update(overrides)
    return base


# ── 한국어 render ────────────────────────────────────────────────────────────


def test_repo_insights_renders_korean_kpi_labels():
    """KPI 4 카드 라벨 + period_basis 한국어 렌더 (오타 키면 raw 키 노출 → 실패)."""
    out = _render("repo_insights.html", locale="ko", **_ri_ctx())
    assert "평균 점수" in out  # kpi_avg_score
    assert "총 분석수" in out  # kpi_total_analyses
    assert "최다 반복 이슈" in out  # kpi_top_recurring
    assert "보안 HIGH" in out  # kpi_security_high
    assert "최근 30일" in out  # recent_days (days=30 placeholder)
    assert "분석 5건 기준" in out  # period_basis (count placeholder)


def test_repo_insights_renders_korean_card_titles():
    """반복/카테고리/문제파일/AI제안 카드 제목 + 테이블 헤더 한국어 렌더."""
    out = _render("repo_insights.html", locale="ko", **_ri_ctx())
    assert "반복 이슈 랭킹" in out  # recurring_ranking_title
    assert "카테고리 비율" in out  # category_ratio_title
    assert "문제 파일 TOP" in out  # problem_files_title
    assert "AI 제안 모음" in out  # ai_suggestions_title
    assert "AI 종합 진단" in out  # narrative_title
    # 테이블 헤더 / table headers
    assert "이슈 메시지" in out  # th_message
    assert "도구" in out  # th_tool
    assert "횟수" in out  # th_count
    assert "전체 5건" in out  # total_items (count placeholder)


def test_repo_insights_renders_korean_empty_state():
    """분석 0건 시 empty_no_data + hint 한국어 렌더 (empty-state 경로)."""
    out = _render("repo_insights.html", locale="ko", **_ri_ctx_empty())
    assert "최근 30일 내 분석 데이터가 없습니다." in out  # empty_no_data
    assert "GitHub Push 또는 PR 이벤트 발생 후 다시 확인하세요." in out  # empty_no_data_hint


# ── 영어 render ──────────────────────────────────────────────────────────────


def test_repo_insights_renders_english_kpi_labels():
    out = _render("repo_insights.html", locale="en", **_ri_ctx())
    assert "Avg score" in out  # kpi_avg_score
    assert "Last 30 days" in out  # recent_days
    assert "Recurring Issue Ranking" in out  # recurring_ranking_title


def test_repo_insights_renders_english_card_titles():
    out = _render("repo_insights.html", locale="en", **_ri_ctx())
    assert "Recurring Issue Ranking" in out
    assert "AI Suggestions" in out  # ai_suggestions_title (영어 라벨 — JSON 단일 출처)


# ── 테마 키 커버 (base.html 상속) ───────────────────────────────────────────


def test_repo_insights_renders_common_theme_labels():
    """base.html 상속 — common.theme 라벨 렌더 (테마 키 사각 차단).

    Inherits base.html — renders common.theme labels (theme key coverage).
    """
    out_ko = _render("repo_insights.html", locale="ko", **_ri_ctx())
    assert "다크 오로라" in out_ko  # common.theme.dark_label
    out_en = _render("repo_insights.html", locale="en", **_ri_ctx())
    assert "Dark Aurora" in out_en


# ── raw 키 누출 회귀 가드 ────────────────────────────────────────────────────


def _ri_key_leaks(out: str) -> list[str]:
    """raw 'repo_insights.<i18n_key>' 누출 추출 — 정적 자원 파일명/속성명 제외.

    Extracts raw 'repo_insights.<i18n_key>' leaks, excluding static asset filenames/attr names.
    제외 대상: data-i18n-* 속성명, repo_insights.css/.js 정적 자원 링크.
    """
    # data-i18n-* 속성명(data-i18n-chart-sec-err 등)은 키가 아니므로 제거
    # Strip data-i18n-* attribute names (not keys) before scanning
    stripped = re.sub(r'data-i18n[\w-]*="[^"]*"', "", out)
    # repo_insights.css / repo_insights.js 정적 자원 파일명은 i18n 키 아님 → 제외
    # repo_insights.css / .js are static asset filenames, not i18n keys → exclude
    return re.findall(r"repo_insights\.(?!css\b|js\b)[a-z_]+", stripped)


def test_repo_insights_no_raw_key_leak_populated():
    """fully-populated 렌더에 raw 'repo_insights.<key>' 미노출 (오타 키 탐지)."""
    leaks = _ri_key_leaks(_render("repo_insights.html", locale="ko", **_ri_ctx()))
    assert not leaks, f"raw repo_insights 키 노출: {leaks}"


def test_repo_insights_no_raw_key_leak_empty():
    """empty-state 렌더에도 raw 'repo_insights.<key>' 미노출."""
    leaks = _ri_key_leaks(_render("repo_insights.html", locale="en", **_ri_ctx_empty()))
    assert not leaks, f"raw repo_insights 키 노출: {leaks}"
