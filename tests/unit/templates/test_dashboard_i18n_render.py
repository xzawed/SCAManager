"""Phase 2 PR-6 회귀 가드 — dashboard.html 다국어 렌더링 검증.

Phase 2 PR-6 regression guards — dashboard.html multilingual rendering.

검증 범위 (Coverage):
1. dashboard.html title + subtitle + nav (mode + range) en/ko/ja
2. KPI 5 카드 (avg_score / analysis_count / high_security / active_repos / auto_merge_success)
3. mode=overview branch (KPI + trend + frequent_issues + feedback CTA)
4. mode=insight branch (✨/🔍/📊/💬 4 카드 + refresh + status fallback)
5. mode=security branch (kill-switch / empty / processed/pending/classification/recent_pending / load_failed)
6. mode=usage branch (empty / 4 cards / SaaS info / load_failed)
7. Chart.js trend label (i18n + tojson 안전)
8. locale 미주입 default 'ko' fallback
"""
from __future__ import annotations

from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.i18n.filters import register_i18n_filters


def _render(template_name: str, **context) -> str:
    """Standalone Jinja2 환경에서 템플릿 렌더 — TestClient lifespan trap 회피."""
    env = Environment(
        loader=FileSystemLoader("src/templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    register_i18n_filters(env)
    tmpl = env.get_template(template_name)
    return tmpl.render(**context)


class _FakeUser:
    github_login = "alice"
    display_name = "Alice"


def _kpi_dict() -> dict:
    """Common KPI fixture — overview mode 렌더 의존. C1 Phase 4 — monthly_cost 6번째 카드 포함."""
    return {
        "avg_score": {"value": 75, "grade": "B", "delta": 3},
        "analysis_count": {"value": 12, "delta": 2},
        "high_security_issues": {"value": 0, "delta": -1},
        "active_repos": {"value": 3, "total": 5, "delta": 0},
        "monthly_cost": {"value": 0.0123, "delta": -0.002, "by_model": {"sonnet": 0.0123, "haiku": 0.0, "opus": 0.0, "other": 0.0}},
    }


def _auto_merge_dict() -> dict:
    return {
        "value": 50,
        "delta": 10,
        "success_count": 5,
        "total_attempts": 10,
        "final_success_rate_pct": 80,
        "final_success_prs": 4,
        "distinct_prs": 5,
    }


# ── overview mode ───────────────────────────────────────────────────────────


def test_dashboard_overview_renders_korean_kpi_titles():
    """dashboard mode=overview — 한국어 KPI 5 카드 + nav + section titles."""
    out = _render(
        "dashboard.html",
        locale="ko",
        current_user=_FakeUser(),
        mode="overview",
        initial_mode="overview",
        days=7,
        kpi=_kpi_dict(),
        trend=[{"date": "2026-05-01", "avg_score": 75}],
        frequent_issues=[],
        auto_merge=_auto_merge_dict(),
        merge_failures=[],
        feedback={"show_cta": False, "count": 0},
    )
    # KPI 6 카드 라벨 (C1 Phase 4 — monthly_cost 추가)
    assert "평균 점수" in out
    assert "분석 건수" in out
    assert "보안 이슈 (HIGH)" in out
    assert "활성 리포" in out
    assert "자동 머지 성공률 (PR 기준)" in out
    assert "이번 달 AI 비용" in out
    assert "$0.0123" in out
    assert "vs 직전 30일" in out
    # Section
    assert "점수 추세 (7일)" in out
    assert "자주 발생 이슈 (최근 7일)" in out
    # Nav
    assert ">📊 개요</a>" in out
    assert ">💬 인사이트</a>" in out
    assert ">🛡️ 보안</a>" in out
    assert ">📈 사용량</a>" in out
    assert "대시보드 · SCAManager" in out  # title block
    assert "우리 코드는 어떻게 흘러가고 있나요" in out  # subtitle


def test_dashboard_overview_renders_english_kpi_titles():
    """dashboard mode=overview — 영문 KPI 5 + nav + sections."""
    out = _render(
        "dashboard.html",
        locale="en",
        current_user=_FakeUser(),
        mode="overview",
        initial_mode="overview",
        days=7,
        kpi=_kpi_dict(),
        trend=[],
        frequent_issues=[],
        auto_merge=_auto_merge_dict(),
        merge_failures=[],
        feedback={"show_cta": False, "count": 0},
    )
    assert "Average Score" in out
    assert "Analyses" in out
    assert "Security Issues (HIGH)" in out
    assert "Active Repos" in out
    assert "Auto-Merge Success Rate (PR-based)" in out
    assert "AI cost (30d)" in out
    assert "$0.0123" in out
    assert "Score Trend (7d)" in out
    assert "No analysis data in the last 7 days." in out
    assert ">📊 Overview</a>" in out
    assert ">💬 Insight</a>" in out
    assert ">🛡️ Security</a>" in out
    assert ">📈 Usage</a>" in out
    assert "Dashboard · SCAManager" in out


def test_dashboard_overview_renders_japanese_kpi_titles():
    """dashboard mode=overview — 일본어 KPI 5 + nav."""
    out = _render(
        "dashboard.html",
        locale="ja",
        current_user=_FakeUser(),
        mode="overview",
        initial_mode="overview",
        days=30,
        kpi=_kpi_dict(),
        trend=[{"date": "2026-05-01", "avg_score": 80}],
        frequent_issues=[{"message": "issue", "tool": "pylint", "language": "python", "category": "code_quality", "count": 3}],
        auto_merge=_auto_merge_dict(),
        merge_failures=[],
        feedback={"show_cta": False, "count": 0},
    )
    assert "平均スコア" in out
    assert "分析数" in out
    assert "セキュリティ問題 (HIGH)" in out
    assert "アクティブなリポ" in out
    assert "自動マージ成功率 (PR基準)" in out
    assert "今月のAIコスト" in out
    assert "$0.0123" in out
    assert "スコアトレンド (30日)" in out
    assert "頻発する問題 (最近 30 日)" in out
    assert ">📊 概要</a>" in out
    assert ">💬 インサイト</a>" in out
    assert ">🛡️ セキュリティ</a>" in out
    assert ">📈 使用量</a>" in out
    assert "ダッシュボード · SCAManager" in out


def test_dashboard_overview_feedback_cta_renders_korean():
    """feedback CTA banner — 한국어 (count=0)."""
    out = _render(
        "dashboard.html",
        locale="ko",
        current_user=_FakeUser(),
        mode="overview",
        initial_mode="overview",
        days=7,
        kpi=_kpi_dict(),
        trend=[],
        frequent_issues=[],
        auto_merge=_auto_merge_dict(),
        merge_failures=[],
        feedback={"show_cta": True, "count": 0, "recent_analysis": None},
    )
    assert "AI 점수에 피드백을 남겨주세요" in out
    assert "분석 결과 페이지의 👍 / 👎 버튼" in out


def test_dashboard_overview_feedback_cta_renders_english_with_count():
    """feedback CTA — 영문 + count > 0."""
    out = _render(
        "dashboard.html",
        locale="en",
        current_user=_FakeUser(),
        mode="overview",
        initial_mode="overview",
        days=7,
        kpi=_kpi_dict(),
        trend=[],
        frequent_issues=[],
        auto_merge=_auto_merge_dict(),
        merge_failures=[],
        feedback={
            "show_cta": True,
            "count": 5,
            "recent_analysis": {"id": 1, "repo_full_name": "owner/repo"},
        },
    )
    assert "Please give feedback on AI scores" in out
    assert "5 feedback items so far" in out
    assert "View recent analysis" in out


# ── insight mode ────────────────────────────────────────────────────────────


def test_dashboard_insight_success_renders_korean():
    """insight 4 카드 (success status) — 한국어."""
    out = _render(
        "dashboard.html",
        locale="ko",
        current_user=_FakeUser(),
        mode="insight",
        initial_mode="insight",
        days=7,
        insight={
            "status": "success",
            "generated_at": "2026-05-05T10:30:00",
            "positive_highlights": ["좋은 점 1"],
            "focus_areas": ["주의 1"],
            "key_metrics": [{"label": "점수", "value": 75, "delta": "+3"}],
            "next_actions": ["다음 행동"],
        },
    )
    assert "✨ 잘한 것" in out
    assert "🔍 신경 쓸 것" in out
    assert "📊 숫자" in out
    assert "💬 다음" in out
    assert "🔄 새로 고침" in out
    assert "cache 생성 시각" in out  # generated_at tooltip


def test_dashboard_insight_no_api_key_renders_english():
    """insight no_api_key fallback — 영문."""
    out = _render(
        "dashboard.html",
        locale="en",
        current_user=_FakeUser(),
        mode="insight",
        initial_mode="insight",
        days=7,
        insight={"status": "no_api_key"},
    )
    assert "ANTHROPIC_API_KEY not set" in out
    assert "Insight mode requires AI analysis" in out


def test_dashboard_insight_no_data_renders_japanese():
    """insight no_data fallback — 일본어 + days 변수 치환."""
    out = _render(
        "dashboard.html",
        locale="ja",
        current_user=_FakeUser(),
        mode="insight",
        initial_mode="insight",
        days=30,
        insight={"status": "no_data"},
    )
    assert "最近 30 日の分析データが不足しています" in out


def test_dashboard_insight_success_renders_japanese():
    """insight 4 카드 — 일본어."""
    out = _render(
        "dashboard.html",
        locale="ja",
        current_user=_FakeUser(),
        mode="insight",
        initial_mode="insight",
        days=7,
        insight={
            "status": "success",
            "generated_at": "2026-05-05T10:30:00",
            "positive_highlights": ["良い点"],
            "focus_areas": ["注意"],
            "key_metrics": [],
            "next_actions": ["次"],
        },
    )
    assert "✨ よかったこと" in out
    assert "🔍 注力すべき点" in out
    assert "📊 数値" in out
    assert "💬 次" in out
    assert "🔄 更新" in out


# ── security mode ──────────────────────────────────────────────────────────


def test_dashboard_security_kill_switch_renders_korean():
    """security mode kill-switch active — 한국어."""
    out = _render(
        "dashboard.html",
        locale="ko",
        current_user=_FakeUser(),
        mode="security",
        initial_mode="security",
        days=7,
        security={"kill_switch_active": True},
    )
    assert "Security 자동 처리 비활성화" in out


def test_dashboard_security_empty_renders_english():
    """security mode total_alerts=0 empty state — 영문."""
    out = _render(
        "dashboard.html",
        locale="en",
        current_user=_FakeUser(),
        mode="security",
        initial_mode="security",
        days=7,
        security={"kill_switch_active": False, "total_alerts": 0},
    )
    assert "No alerts pending review" in out
    assert "View directly on GitHub Security tab" in out


def test_dashboard_security_cards_render_japanese():
    """security 4 카드 (pending + processed + classification + recent_pending) — 일본어."""
    out = _render(
        "dashboard.html",
        locale="ja",
        current_user=_FakeUser(),
        mode="security",
        initial_mode="security",
        days=7,
        security={
            "kill_switch_active": False,
            "total_alerts": 5,
            "processed_count": 2,
            "pending_count": 3,
            "classification": {"true_positive": 2, "false_positive": 1},
            "recent_pending": [
                {"alert_number": 1, "severity": "HIGH", "alert_type": "code", "rule_id": "py/test", "ai_classification": "true"}
            ],
        },
    )
    assert "✨ 処理済み" in out
    assert "🔍 新規 pending" in out
    assert "📊 分類分布" in out
    assert "💬 最近 pending (Top 5)" in out


# ── usage mode ─────────────────────────────────────────────────────────────


def test_dashboard_usage_empty_renders_korean():
    """usage mode repo_count=0 empty state — 한국어."""
    out = _render(
        "dashboard.html",
        locale="ko",
        current_user=_FakeUser(),
        mode="usage",
        initial_mode="usage",
        days=7,
        usage={"repo_count": 0},
    )
    assert "등록된 리포지토리가 없습니다" in out


def test_dashboard_usage_cards_render_english():
    """usage 4 카드 + SaaS info — 영문 + days 변수 치환."""
    out = _render(
        "dashboard.html",
        locale="en",
        current_user=_FakeUser(),
        mode="usage",
        initial_mode="usage",
        days=30,
        usage={
            "repo_count": 5,
            "total_analyses": 100,
            "last_analysis_at": datetime(2026, 5, 5, 10, 30),
            "recent_analyses": 12,
            "avg_score": 80,
            "days": 30,
        },
    )
    assert "📁 Your Repos" in out
    assert "📊 Total Analyses" in out
    assert "🕒 Last 30 days" in out
    assert "⭐ Average Score" in out
    assert "Last 30 days average" in out
    assert "💡 SaaS Phase 1 Info" in out
    assert "your data only" in out


def test_dashboard_usage_cards_render_japanese():
    """usage 4 카드 — 일본어 + days 변수 치환."""
    out = _render(
        "dashboard.html",
        locale="ja",
        current_user=_FakeUser(),
        mode="usage",
        initial_mode="usage",
        days=7,
        usage={
            "repo_count": 5,
            "total_analyses": 100,
            "last_analysis_at": None,
            "recent_analyses": 12,
            "avg_score": None,
            "days": 7,
        },
    )
    assert "📁 本人のリポ" in out
    assert "🕒 最近 7 日" in out
    assert "⭐ 平均スコア" in out


# ── Chart.js label ─────────────────────────────────────────────────────────


def test_dashboard_chart_label_renders_korean():
    """Chart.js trend label JS 블록 — 한국어."""
    out = _render(
        "dashboard.html",
        locale="ko",
        current_user=_FakeUser(),
        mode="overview",
        initial_mode="overview",
        days=7,
        kpi=_kpi_dict(),
        trend=[{"date": "2026-05-01", "avg_score": 75}],
        frequent_issues=[],
        auto_merge=_auto_merge_dict(),
        merge_failures=[],
        feedback={"show_cta": False, "count": 0},
    )
    # Chart.js label 은 tojson 안전 (스크립트 블록)
    assert 'label: "\\ud3c9\\uade0 \\uc810\\uc218"' in out or 'label: "평균 점수"' in out


def test_dashboard_chart_label_renders_english():
    """Chart.js trend label JS 블록 — 영문."""
    out = _render(
        "dashboard.html",
        locale="en",
        current_user=_FakeUser(),
        mode="overview",
        initial_mode="overview",
        days=7,
        kpi=_kpi_dict(),
        trend=[{"date": "2026-05-01", "avg_score": 75}],
        frequent_issues=[],
        auto_merge=_auto_merge_dict(),
        merge_failures=[],
        feedback={"show_cta": False, "count": 0},
    )
    assert 'label: "Average Score"' in out


# ── locale fallback ─────────────────────────────────────────────────────────


def test_dashboard_locale_none_defaults_to_ko():
    """dashboard.html — locale 미주입 시 default 'ko'."""
    out = _render(
        "dashboard.html",
        current_user=_FakeUser(),
        mode="overview",
        initial_mode="overview",
        days=7,
        kpi=_kpi_dict(),
        trend=[],
        frequent_issues=[],
        auto_merge=_auto_merge_dict(),
        merge_failures=[],
        feedback={"show_cta": False, "count": 0},
    )
    assert "평균 점수" in out
    assert "대시보드 · SCAManager" in out


# ── repos mode — 점수추이 차트 Chart.js 로드 (렌더 기반 회귀 가드) ──────────────
# ── repos mode — score-trend chart Chart.js load (render-based regression guard) ──
#
# 🔴 repos 모드 점수추이 차트(repoTrendChart) 공백 회귀 봉인 (#921 후속, 2026-06-17).
# vendor `chart.umd.min.js` <script> 로드 조건이 overview `trend` 만 검사하던 탓에 repos 모드는
# Chart.js 가 로드조차 안 돼(scriptCount=0) 차트가 영구 공백이었다. E2E 는 CI 미실행이라
# 이 렌더 단위 테스트가 fast-CI 의 1차 봉인이다 (Codex mutual 검증 보강 제안).


def _repos_context(score_trend):
    """repos 모드 dashboard.html 렌더 컨텍스트 — route(_build_repo_summary + repo_report_data) shape 미러."""
    return dict(
        current_user=_FakeUser(),
        locale="ko",
        mode="repos",
        initial_mode="repos",
        days=30,
        selected_repo="owner/testrepo",
        summary={
            "repos": [{"repo_id": 1, "full_name": "owner/testrepo", "avg_score": 80,
                       "grade": "B", "score_delta": 0, "warning": False}],
            "summary": {"total_repos": 1, "avg_score": 80,
                        "grade_distribution": {"A": 0, "B": 1, "C": 0, "D": 0, "F": 0},
                        "warning_count": 0},
            "warning_repos": [],
        },
        repo_report={
            "repo_full_name": "owner/testrepo",
            "kpi": {"avg_score": 80, "grade": "B", "score_delta": 0,
                    "high_security_count": 0, "analysis_count": 2},
            "recurring_issues": [],
            "category_breakdown": {"security_error": 0, "security_warning": 0,
                                   "code_quality_error": 0, "code_quality_warning": 0},
            "ai_suggestions": [],
            "score_trend": score_trend,
        },
    )


def test_dashboard_repos_mode_loads_chartjs_when_trend_present():
    """repos 모드 + score_trend>1 → Chart.js vendor <script> + repoTrendChart 렌더.

    🔴 회귀(#921 후속): 이전 로드 조건(`mode != 'insight' and trend`)은 repos 모드에서 `trend` 가
    비어 Chart.js 미로드 → repoTrendChart 영구 공백. _show_repos_trend OR 분기로 봉인.
    """
    out = _render("dashboard.html", **_repos_context(
        [{"date": "2026-06-14", "avg_score": 70}, {"date": "2026-06-17", "avg_score": 90}]))
    assert "/static/vendor/chart.umd.min.js" in out, (
        "repos 모드 + score_trend>1 인데 Chart.js vendor <script> 미로드 → 점수추이 차트 영구 공백"
    )
    assert 'id="repoTrendChart"' in out
    # onload 가 _reposChartReady 를 호출해야 async 로드 후 재빌드됨
    assert "if(document._reposChartReady)document._reposChartReady()" in out


def test_dashboard_repos_mode_no_chartjs_when_single_trend_point():
    """repos 모드 + score_trend 1개 → 차트 미렌더 → Chart.js 미로드 (로드 조건 정밀성).

    `score_trend | length > 1` 경계 — 1개면 repoTrendChart 도, vendor <script> 도 렌더 안 함.
    off-by-one(>0 등)으로 조건이 느슨해지는 회귀를 차단한다.
    """
    out = _render("dashboard.html", **_repos_context([{"date": "2026-06-17", "avg_score": 90}]))
    assert 'id="repoTrendChart"' not in out, "score_trend 1개면 트렌드 차트 미렌더여야 함"
    assert "/static/vendor/chart.umd.min.js" not in out, (
        "차트가 없는데 Chart.js 로드 → 로드 조건이 너무 느슨함(off-by-one 회귀)"
    )
