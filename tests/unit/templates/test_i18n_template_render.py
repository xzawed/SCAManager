"""Phase 2 PR-5 회귀 가드 — base.html / add_repo.html / overview.html 다국어 렌더링 검증.

Phase 2 PR-5 regression guards — multilingual rendering for base/add_repo/overview templates.
login.html 은 사이클 117 에서 삭제됨 (standalone landing.html 로 통합).
login.html deleted in cycle 117 (merged into standalone landing.html).

검증 범위 (Coverage):
1. add_repo.html — page_title / subtitle / label_select / submit / data-i18n-* 속성 en/ko/ja
2. overview.html (with repos) — greeting / title / repo_count / table headers en/ko/ja
3. overview.html (empty) — title_empty / tutorial 3 step en/ko/ja
4. base.html nav — header.overview / header.dashboard / common.menu_aria / common.logout en/ko/ja
5. locale 미주입 (None) → default 'ko' fallback
"""
from __future__ import annotations

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.i18n.filters import register_i18n_filters


def _render(template_name: str, **context) -> str:
    """Standalone Jinja2 환경에서 템플릿 렌더 — TestClient lifespan trap 회피.

    Standalone Jinja2 environment for template rendering — avoids TestClient lifespan trap
    (memory: feedback-testclient-lifespan-trap.md). Jinja2 i18n 필터만 검증.
    """
    env = Environment(
        loader=FileSystemLoader("src/templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    register_i18n_filters(env)
    tmpl = env.get_template(template_name)
    return tmpl.render(**context)


# ── add_repo.html ───────────────────────────────────────────────────────────


def test_add_repo_html_renders_korean_keys():
    """add_repo.html — 한국어 핵심 키 + data-i18n 속성 검증."""
    out = _render("add_repo.html", locale="ko")
    assert "리포 추가 — SCAManager" in out  # title block
    assert "리포지토리 추가" in out  # page_title
    assert "← 돌아가기" in out  # back
    assert "GitHub 리포지토리" in out  # label_select
    assert "Webhook 생성 + 리포 추가" in out  # submit
    # data-i18n-* 속성 (JS 동적 텍스트 서버측 주입)
    assert 'data-i18n-placeholder="리포를 선택하세요"' in out
    assert 'data-i18n-no-repos-option="추가 가능한 리포가 없습니다"' in out
    assert "data-i18n-loaded-template=" in out  # 템플릿 형식만 확인 (count placeholder)


def test_add_repo_html_renders_english_keys():
    """add_repo.html — 영문 키 + data-i18n 속성 검증."""
    out = _render("add_repo.html", locale="en")
    assert "Add Repository — SCAManager" in out
    assert "Webhook will be auto-created" in out
    assert "Sign in with GitHub" not in out  # login 키 격리
    assert 'data-i18n-placeholder="Select a repository"' in out


def test_add_repo_html_renders_japanese_keys():
    """add_repo.html — 일본어 키 검증."""
    out = _render("add_repo.html", locale="ja")
    assert "リポ追加 — SCAManager" in out
    assert "リポジトリ追加" in out
    assert "← 戻る" in out
    assert "Webhook生成 + リポ追加" in out


# ── overview.html (with repos) ──────────────────────────────────────────────


class _FakeUser:
    display_name = "Alice"
    github_login = "alice"


def test_overview_html_with_repos_renders_korean():
    """overview.html (리포 ≥ 1) — 한국어 greeting + table header + repo_count."""
    repos = [{"full_name": "owner/repo", "analysis_count": 5, "avg_score": 80, "avg_grade": "B"}]
    out = _render(
        "overview.html",
        locale="ko",
        current_user=_FakeUser(),
        repos=repos,
        calibration={},
    )
    assert "안녕하세요, Alice님" in out  # greeting
    assert "오늘의 분석" in out  # title (with repos)
    assert "1개 리포" in out  # repo_count
    assert "리포지토리</th>" in out  # table.repository
    assert "분석</th>" in out  # table.analysis
    assert "평균 점수</th>" in out  # table.avg_score
    assert "등급</th>" in out  # table.grade
    assert "5회</span>" in out  # analysis_count_unit


def test_overview_html_with_repos_renders_english():
    """overview.html (리포 ≥ 1) — 영문 greeting + table header + repo_count."""
    repos = [{"full_name": "owner/repo", "analysis_count": 5, "avg_score": 80, "avg_grade": "B"}]
    out = _render(
        "overview.html",
        locale="en",
        current_user=_FakeUser(),
        repos=repos,
        calibration={},
    )
    assert "Hello, Alice" in out
    assert "Today&#39;s Analyses" in out  # apostrophe escaped
    assert "1 repos" in out
    assert "Repository</th>" in out
    assert "Average Score</th>" in out
    assert "5 runs</span>" in out


def test_overview_html_with_repos_renders_japanese():
    """overview.html (리포 ≥ 1) — 일본어 greeting + table header + repo_count."""
    repos = [{"full_name": "owner/repo", "analysis_count": 5, "avg_score": 80, "avg_grade": "B"}]
    out = _render(
        "overview.html",
        locale="ja",
        current_user=_FakeUser(),
        repos=repos,
        calibration={},
    )
    assert "こんにちは、Aliceさん" in out
    assert "本日の分析" in out
    assert "1個のリポ" in out
    assert "リポジトリ</th>" in out
    assert "平均スコア</th>" in out
    assert "5回</span>" in out


# ── overview.html (empty — tutorial) ────────────────────────────────────────


def test_overview_html_empty_renders_korean_tutorial():
    """overview.html (리포 0) — 한국어 tutorial 3 step + tip 검증."""
    out = _render(
        "overview.html",
        locale="ko",
        current_user=_FakeUser(),
        repos=[],
        calibration={},
    )
    assert "리포지토리 현황" in out  # title_empty
    assert "3단계로 시작하기" in out  # tutorial.title
    assert "GitHub 리포 선택" in out  # step1_title
    assert "기본 설정 (Simple 모드)" in out  # step2_title
    assert "첫 Push 또는 PR" in out  # step3_title
    assert "🚀 빠른 설정 프리셋" in out  # step2_desc_preset
    assert "팁" in out  # tip_label


def test_overview_html_empty_renders_english_tutorial():
    """overview.html (리포 0) — 영문 tutorial 3 step + tip 검증."""
    out = _render(
        "overview.html",
        locale="en",
        current_user=_FakeUser(),
        repos=[],
        calibration={},
    )
    assert "Repository Status" in out  # title_empty
    assert "Get Started in 3 Steps" in out
    assert "Select GitHub Repo" in out
    assert "Initial Setup (Simple Mode)" in out
    assert "First Push or PR" in out
    assert "Quick Setup Presets" in out
    assert "Tip" in out


def test_overview_html_empty_renders_japanese_tutorial():
    """overview.html (리포 0) — 일본어 tutorial 3 step + tip 검증."""
    out = _render(
        "overview.html",
        locale="ja",
        current_user=_FakeUser(),
        repos=[],
        calibration={},
    )
    assert "リポジトリ状況" in out
    assert "3ステップで始める" in out
    assert "GitHubリポを選択" in out
    assert "初期設定 (Simpleモード)" in out
    assert "最初のPushまたはPR" in out
    assert "ヒント" in out


# ── base.html nav (via overview.html which extends base) ────────────────────


def test_base_nav_renders_korean_via_overview():
    """base.html nav — 한국어 (overview.html extends base + locale=ko 시)."""
    repos = [{"full_name": "owner/repo", "analysis_count": 1, "avg_score": 50, "avg_grade": "D"}]
    out = _render("overview.html", locale="ko", current_user=_FakeUser(), repos=repos, calibration={})
    assert ">개요</a>" in out  # header.overview
    assert ">대시보드</a>" in out  # header.dashboard
    assert ">로그아웃</button>" in out  # common.logout
    assert 'aria-label="메뉴 열기"' in out  # common.menu_aria
    assert '<html lang="ko"' in out  # HTML lang dynamic (data-* attrs also present)


def test_base_nav_renders_english_via_overview():
    """base.html nav — 영문 (overview.html extends base + locale=en 시)."""
    repos = [{"full_name": "owner/repo", "analysis_count": 1, "avg_score": 50, "avg_grade": "D"}]
    out = _render("overview.html", locale="en", current_user=_FakeUser(), repos=repos, calibration={})
    assert ">Overview</a>" in out
    assert ">Dashboard</a>" in out
    assert ">Logout</button>" in out
    assert 'aria-label="Open menu"' in out
    assert '<html lang="en"' in out


def test_base_nav_renders_japanese_via_overview():
    """base.html nav — 일본어 (overview.html extends base + locale=ja 시)."""
    repos = [{"full_name": "owner/repo", "analysis_count": 1, "avg_score": 50, "avg_grade": "D"}]
    out = _render("overview.html", locale="ja", current_user=_FakeUser(), repos=repos, calibration={})
    assert ">概要</a>" in out
    assert ">ダッシュボード</a>" in out
    assert ">ログアウト</button>" in out
    assert 'aria-label="メニューを開く"' in out
    assert '<html lang="ja"' in out


# ── locale 미주입 fallback ──────────────────────────────────────────────────


def test_overview_html_locale_none_defaults_to_ko():
    """overview.html — locale 미주입 시 'ko' default fallback (Jinja default 필터)."""
    out = _render("overview.html", current_user=_FakeUser(), repos=[], calibration={})
    assert "리포지토리 현황" in out
    assert '<html lang="ko"' in out


def test_add_repo_html_locale_none_defaults_to_ko():
    """add_repo.html — locale 미주입 시 'ko' default fallback."""
    out = _render("add_repo.html")
    assert "리포 추가 — SCAManager" in out
    assert "리포지토리 추가" in out
