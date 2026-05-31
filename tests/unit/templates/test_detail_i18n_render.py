"""Phase 2 PR-7 회귀 가드 — repo_detail.html + analysis_detail.html 다국어 렌더링.

Phase 2 PR-7 regression guards — repo_detail + analysis_detail multilingual rendering.

검증 범위 (Coverage):
1. repo_detail.html — 헤더 / chart label / table 6 헤더 / filter 16종 / search placeholder / hook installed banner
2. repo_detail.html data-i18n-* 속성 (JS 동적 텍스트 — XSS-safe 서버 주입)
3. analysis_detail.html — title / nav prev/next / source 3종 / 등급 메시지 5종 / feedback 8 / AI 4 sections / empty 3 / breakdown 5 + headers
4. analysis_detail.html chart label/marker (tojson 안전)
5. en/ko/ja 3 언어 + locale=None default fallback
"""
from __future__ import annotations

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.i18n.filters import register_i18n_filters


def _render(template_name: str, **context) -> str:
    """Standalone Jinja2 환경 — TestClient lifespan trap 회피."""
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


# ── repo_detail.html ────────────────────────────────────────────────────────


def _repo_ctx(**overrides) -> dict:
    base = {
        "current_user": _FakeUser(),
        "repo_name": "owner/repo",
        "analyses": [
            {"id": 1, "score": 80, "grade": "B", "commit_sha": "abc1234",
             "pr_number": 1, "commit_message": "msg",
             "source": "pr", "created_at": "2026-05-01T10:00:00"},
        ],
        "chart_labels": ["2026-05-01"],
        "chart_scores": [80],
        "hook_installed": False,
        # Alembic 0032 — 월별 비용 추적
        "monthly_cost_usd": 0.0,
        "monthly_token_count": 0,
        "monthly_cost_month": "2026-05",
    }
    base.update(overrides)
    return base


def test_repo_detail_renders_korean():
    """repo_detail.html — 한국어 헤더/필터/테이블."""
    out = _render("repo_detail.html", locale="ko", **_repo_ctx())
    assert "← 목록" in out  # back
    assert "⚙️ 설정" in out  # settings_link
    assert "점수 추이" in out  # score_trend_label
    assert "분석 이력" in out  # history_title
    assert "최근 1건" in out  # history_count_recent
    assert "커밋 메시지 또는 SHA 검색…" in out  # search_placeholder
    assert ">날짜 " in out and ">커밋</th>" in out and ">PR</th>" in out
    assert ">점수 " in out and ">등급</th>" in out and ">소스</th>" in out
    assert ">전체</button>" in out  # filter_all
    assert ">오늘</button>" in out and ">금주</button>" in out
    assert ">이번달</button>" in out and ">올해</button>" in out
    assert ">직접 지정</button>" in out
    # data-i18n-* 속성
    assert 'data-i18n-filter-empty="조건에 맞는 분석 이력이 없습니다."' in out


def test_repo_detail_renders_english():
    """repo_detail.html — 영문."""
    out = _render("repo_detail.html", locale="en", **_repo_ctx())
    assert "← List" in out
    assert "⚙️ Settings" in out
    assert "Score Trend" in out
    assert "Analysis History" in out
    assert "Last 1 entries" in out
    assert "Search commit message or SHA…" in out
    assert ">Date " in out and ">Commit</th>" in out
    assert ">Score " in out and ">Grade</th>" in out and ">Source</th>" in out
    assert ">All</button>" in out
    assert ">Today</button>" in out and ">This Week</button>" in out
    assert ">Custom</button>" in out


def test_repo_detail_renders_japanese():
    """repo_detail.html — 일본어."""
    out = _render("repo_detail.html", locale="ja", **_repo_ctx())
    assert "← 一覧" in out
    assert "スコア推移" in out
    assert "分析履歴" in out
    assert "最近 1 件" in out
    assert "コミットメッセージまたはSHA検索" in out
    assert ">日付 " in out and ">コミット</th>" in out
    assert ">グレード</th>" in out and ">ソース</th>" in out
    assert ">全て</button>" in out
    assert ">今日</button>" in out and ">今週</button>" in out


def test_repo_detail_hook_installed_banner_korean():
    """repo_detail.html hook_installed=True 배너 — 한국어."""
    out = _render("repo_detail.html", locale="ko", **_repo_ctx(hook_installed=True))
    assert "CLI 코드리뷰 훅이 설정됐습니다!" in out
    assert "로컬 리포에서 아래 명령어를 실행하면" in out


def test_repo_detail_chart_label_renders_korean():
    """repo_detail.html chart label JS (tojson 안전) — 한국어."""
    out = _render("repo_detail.html", locale="ko", **_repo_ctx())
    # tojson 은 한국어를 \uXXXX escape 또는 그대로 유지 (ensure_ascii=False)
    assert ('label: "\\uc810\\uc218"' in out) or ('label: "점수"' in out)


def test_repo_detail_chart_label_renders_english():
    """repo_detail.html chart label — 영문."""
    out = _render("repo_detail.html", locale="en", **_repo_ctx())
    assert 'label: "Score"' in out


# ── analysis_detail.html ────────────────────────────────────────────────────


def _analysis_ctx(**overrides) -> dict:
    base = {
        "current_user": _FakeUser(),
        "repo_name": "owner/repo",
        "analysis": {
            "id": 42,
            "commit_sha": "abc1234",
            "commit_message": "fix: bug",
            "pr_number": 7,
            "score": 80,
            "grade": "B",
            "result": {
                "ai_review_status": "success",
                "breakdown": {"code_quality": 20, "security": 18, "commit_message": 12,
                              "ai_review": 20, "test_coverage": 10},
                "ai_summary": "Good code",
                "ai_suggestions": ["Improve tests"],
                "issues": [{"tool": "pylint", "severity": "warning", "line": 10, "message": "test"}],
            },
            "source": "pr",
            "created_at": "2026-05-01T10:00:00",
        },
        "trend_data": [
            {"id": 41, "score": 75, "label": "05/01"},
            {"id": 42, "score": 80, "label": "05/02"},
        ],
        "prev_id": 41,
        "next_id": None,
        "user_feedback": {"thumbs": None, "comment": None, "updated_at": None},
    }
    base.update(overrides)
    return base


def test_analysis_detail_renders_korean():
    """analysis_detail.html — 한국어 핵심 텍스트."""
    out = _render("analysis_detail.html", locale="ko", **_analysis_ctx())
    assert "분석 #42" in out  # title + nav_label
    assert "← 이력" in out  # back
    assert "◀ 이전" in out  # prev (active)
    assert "다음 ▶" in out  # next (disabled)
    assert "📝 커밋 메시지" in out
    assert "/100" in out
    assert "등급 B" in out
    assert "견고한 PR이에요" in out  # score 80 → good
    # feedback
    assert "이 점수가 맞다고 생각하시나요?" in out
    assert "맞음</span>" in out and "아님</span>" in out
    # trend section
    assert "📈 점수 추이 (최근 2건)" in out
    # AI sections
    assert "🤖 AI 요약" in out
    assert "💡 개선 제안" in out
    assert "📊 점수 상세" in out
    assert "🔍 정적 분석 이슈 (1건)" in out
    # source
    assert "🔀 PR" in out


def test_analysis_detail_renders_english():
    """analysis_detail.html — 영문."""
    out = _render("analysis_detail.html", locale="en", **_analysis_ctx())
    assert "Analysis #42" in out
    assert "← History" in out
    assert "◀ Previous" in out
    assert "Next ▶" in out
    assert "📝 Commit Message" in out
    assert "Grade B" in out
    assert "Solid PR" in out
    assert "Do you think this score is accurate?" in out
    assert "Accurate</span>" in out and "Inaccurate</span>" in out
    assert "📈 Score Trend (last 2 entries)" in out
    assert "🤖 AI Summary" in out
    assert "💡 Suggestions" in out
    assert "📊 Score Breakdown" in out
    assert "🔍 Static Analysis Issues (1)" in out
    assert "Code Quality" in out  # breakdown labels
    assert "Implementation Direction" in out


def test_analysis_detail_renders_japanese():
    """analysis_detail.html — 일본어."""
    out = _render("analysis_detail.html", locale="ja", **_analysis_ctx())
    assert "分析 #42" in out
    assert "← 履歴" in out
    assert "◀ 前へ" in out
    assert "次へ ▶" in out
    assert "📝 コミットメッセージ" in out
    assert "グレード B" in out
    assert "堅実な PR です" in out
    assert "このスコアは正しいと思いますか?" in out
    assert "正しい</span>" in out and "違う</span>" in out
    assert "📈 スコア推移 (最近 2 件)" in out
    assert "🤖 AI 要約" in out
    assert "💡 改善提案" in out
    assert "📊 スコア詳細" in out
    assert "🔍 静的解析の問題 (1件)" in out


def test_analysis_detail_score_messages_5_bands():
    """analysis_detail.html score message 5 분기 (90+/75+/60+/45+/<45) — 한국어."""
    for score, expected_msg in [
        (95, "모범적이에요"),
        (80, "견고한 PR이에요"),
        (65, "양호하지만 개선 여지가 있어요"),
        (50, "살펴볼 부분이 있어요"),
        (30, "꼭 확인이 필요해요"),
    ]:
        ctx = _analysis_ctx()
        ctx["analysis"] = {**ctx["analysis"], "score": score}
        out = _render("analysis_detail.html", locale="ko", **ctx)
        assert expected_msg in out, f"score={score} expected '{expected_msg}'"


def test_analysis_detail_ai_defaults_banner_korean():
    """analysis_detail.html ai_review_status != success → 경고 배너 — 한국어 5 분기."""
    for status, msg_part in [
        ("no_api_key", "ANTHROPIC_API_KEY가 설정되지 않아"),
        ("api_error", "AI API 호출에 실패하여"),
        ("empty_diff", "분석 가능한 코드 변경사항이 없어"),
        ("parse_error", "AI 응답 파싱에 실패하여"),
        ("other_status", "AI 리뷰를 수행하지 못해"),
    ]:
        ctx = _analysis_ctx()
        ctx["analysis"] = {**ctx["analysis"], "result": {"ai_review_status": status, "breakdown": {}}}
        out = _render("analysis_detail.html", locale="ko", **ctx)
        assert "AI 리뷰 기본값 적용" in out
        assert msg_part in out, f"status={status} expected '{msg_part}'"


def test_analysis_detail_empty_states_renders_japanese():
    """analysis_detail.html empty 상태 3 분기 — 일본어."""
    # legacy (result=None + score=None)
    ctx_legacy = _analysis_ctx()
    ctx_legacy["analysis"] = {**ctx_legacy["analysis"], "result": None, "score": None}
    out = _render("analysis_detail.html", locale="ja", **ctx_legacy)
    assert "この分析には詳細データがありません" in out
    assert "(AI レビュー導入前の分析記録)" in out

    # no_result (result=None + score=N)
    ctx_no = _analysis_ctx()
    ctx_no["analysis"] = {**ctx_no["analysis"], "result": None, "score": 50}
    out2 = _render("analysis_detail.html", locale="ja", **ctx_no)
    assert "分析結果データがありません" in out2

    # ai_no_data (result={} but no AI fields)
    ctx_empty = _analysis_ctx()
    ctx_empty["analysis"] = {**ctx_empty["analysis"], "result": {"ai_review_status": "success"}}
    out3 = _render("analysis_detail.html", locale="ja", **ctx_empty)
    assert "AI レビューデータがありません" in out3


def test_analysis_detail_chart_tooltip_localizable():
    """analysis_detail.html chart tooltip i18n + tojson 안전 (한국어)."""
    out = _render("analysis_detail.html", locale="ko", **_analysis_ctx())
    # trend_chart_score_prefix = "점수: " / current_marker = " ★ 현재"
    assert ('"\\uc810\\uc218: "' in out or '"점수: "' in out)


def test_analysis_detail_chart_tooltip_english():
    """analysis_detail.html chart tooltip — 영문."""
    out = _render("analysis_detail.html", locale="en", **_analysis_ctx())
    assert '"Score: "' in out
    assert '" \\u2605 Current"' in out or '" ★ Current"' in out


# ── locale fallback ─────────────────────────────────────────────────────────


def test_repo_detail_locale_none_defaults_to_ko():
    """repo_detail.html — locale 미주입 시 default 'ko'."""
    out = _render("repo_detail.html", **_repo_ctx())
    assert "← 목록" in out  # back ko default
    assert "분석 이력" in out


def test_analysis_detail_locale_none_defaults_to_ko():
    """analysis_detail.html — locale 미주입 시 default 'ko'."""
    out = _render("analysis_detail.html", **_analysis_ctx())
    assert "← 이력" in out  # back ko default
    assert "분석 #42" in out


# ---------------------------------------------------------------------------
# 사이클 143/144 i18n 렌더 정합 가드 (회고 P1-4)
# 키 존재가 아닌 실제 렌더 결과에 번역 텍스트가 나타나는지 검증 —
# 템플릿이 오타 키 호출 시 raw 키 노출을 검출.
# Render-parity guard: verifies translated text appears in rendered output,
# catching template typo-key calls that key-existence tests miss.
# ---------------------------------------------------------------------------


def test_repo_detail_cycle143_korean_strings_render():
    """repo_detail.html ko — 사이클 143 신규 번역 텍스트 렌더 검증."""
    out = _render("repo_detail.html", locale="ko", **_repo_ctx())
    assert "최근 점수:" in out  # recent_score
    assert "이번 달 AI 리뷰 예상 비용" in out  # cost.title
    assert "한 달 전체" in out  # cost.period ({month} 보간 후 Tier A 수정값)
    assert "반복 이슈" in out  # issue_mgmt.title (🔁 반복 이슈 — Issue 등록 관리)


def test_repo_detail_cycle143_english_strings_render():
    """repo_detail.html en — 사이클 143 신규 번역 텍스트 렌더 검증."""
    out = _render("repo_detail.html", locale="en", **_repo_ctx())
    assert "Recent Score:" in out  # recent_score
    assert "Estimated AI Review Cost This Month" in out  # cost.title


def test_repo_detail_history_empty_renders_when_no_analyses():
    """repo_detail.html — analyses 비어있을 때 history_empty 빈 상태 렌더."""
    out = _render("repo_detail.html", locale="ko", **_repo_ctx(analyses=[]))
    assert "분석 이력이 없습니다" in out  # history_empty


def test_repo_detail_cycle144_bulk_register_renders():
    """repo_detail.html ko — 사이클 144 일괄 등록 버튼 정적 렌더 (count=0)."""
    out = _render("repo_detail.html", locale="ko", **_repo_ctx())
    # 템플릿이 count=0 으로 i18n_args 호출 → {count}건 보간 검증
    assert "선택 항목 일괄 Issue 등록 (0건)" in out  # issue_mgmt.bulk_register


def test_analysis_detail_cycle144_issue_panel_korean_renders():
    """analysis_detail.html ko — 사이클 144 Issue 패널 번역 텍스트 렌더."""
    out = _render("analysis_detail.html", locale="ko", **_analysis_ctx())
    assert "GitHub Issue 등록" in out  # issue_panel.panel_title (📋 GitHub Issue 등록)
    assert "GitHub Issue 생성" in out  # issue_panel.modal_title (📝 GitHub Issue 생성)


def test_analysis_detail_cycle144_issue_panel_english_renders():
    """analysis_detail.html en — 사이클 144 Issue 패널 번역 텍스트 렌더."""
    out = _render("analysis_detail.html", locale="en", **_analysis_ctx())
    assert "GitHub Issue Registration" in out  # issue_panel.panel_title
    assert "Create GitHub Issue" in out  # issue_panel.modal_title


def test_analysis_detail_cycle143_issue_form_renders():
    """analysis_detail.html ko — 사이클 143 issue_form 라벨 렌더."""
    out = _render("analysis_detail.html", locale="ko", **_analysis_ctx())
    assert "제목" in out  # issue_form.title
