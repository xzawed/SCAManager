"""Phase 2 PR-5 회귀 가드 — base.html / login.html / add_repo.html / overview.html 다국어 렌더링 검증.

Phase 2 PR-5 regression guards — multilingual rendering for base/login/add_repo/overview templates.

검증 범위 (Coverage):
1. login.html — 5 i18n 키 (title_prefix / title / subtitle / github_login / footer) en/ko/ja
2. add_repo.html — page_title / subtitle / label_select / submit / data-i18n-* 속성 en/ko/ja
3. overview.html (with repos) — greeting / title / repo_count / table headers en/ko/ja
4. overview.html (empty) — title_empty / tutorial 3 step en/ko/ja
5. base.html nav — header.overview / header.dashboard / common.menu_aria / common.logout en/ko/ja
6. locale 미주입 (None) → default 'ko' fallback
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


# ── login.html ──────────────────────────────────────────────────────────────


def test_login_html_renders_korean_keys():
    """login.html — 한국어 5 키 렌더 검증."""
    out = _render("login.html", locale="ko")
    assert "로그인 — SCAManager" in out  # title block
    assert "PR이 들어오면 Claude가 검토하고" in out  # subtitle
    assert "GitHub로 로그인" in out  # github_login
    assert "GitHub OAuth로 안전하게 인증합니다" in out  # footer


def test_login_html_renders_english_keys():
    """login.html — 영문 5 키 렌더 검증."""
    out = _render("login.html", locale="en")
    assert "Login — SCAManager" in out
    assert "Claude reviews your PR" in out
    assert "Sign in with GitHub" in out
    assert "Secure authentication with GitHub OAuth" in out


def test_login_html_renders_japanese_keys():
    """login.html — 일본어 5 키 렌더 검증."""
    out = _render("login.html", locale="ja")
    assert "ログイン — SCAManager" in out
    assert "PRが入ってきたらClaudeがレビュー" in out
    assert "GitHubでログイン" in out
    assert "GitHub OAuthで安全に認証します" in out


def test_login_html_default_locale_fallback_to_ko():
    """login.html — locale 미주입 시 default 'ko' fallback (Jinja default 필터)."""
    out = _render("login.html")  # locale=None
    assert "로그인 — SCAManager" in out
    assert "GitHub로 로그인" in out


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


# ── base.html nav (via login.html which extends base) ───────────────────────


def test_base_nav_renders_korean_via_login():
    """base.html nav — 한국어 (login.html extends base + locale=ko 시)."""
    # login 페이지는 비로그인 상태이므로 nav 미노출 — overview 경유 검증
    repos = [{"full_name": "owner/repo", "analysis_count": 1, "avg_score": 50, "avg_grade": "D"}]
    out = _render("overview.html", locale="ko", current_user=_FakeUser(), repos=repos, calibration={})
    assert ">개요</a>" in out  # header.overview
    assert ">대시보드</a>" in out  # header.dashboard
    assert ">로그아웃</button>" in out  # common.logout
    assert 'aria-label="메뉴 열기"' in out  # common.menu_aria
    assert '<html lang="ko">' in out  # HTML lang dynamic


def test_base_nav_renders_english_via_overview():
    """base.html nav — 영문 (overview.html extends base + locale=en 시)."""
    repos = [{"full_name": "owner/repo", "analysis_count": 1, "avg_score": 50, "avg_grade": "D"}]
    out = _render("overview.html", locale="en", current_user=_FakeUser(), repos=repos, calibration={})
    assert ">Overview</a>" in out
    assert ">Dashboard</a>" in out
    assert ">Logout</button>" in out
    assert 'aria-label="Open menu"' in out
    assert '<html lang="en">' in out


def test_base_nav_renders_japanese_via_overview():
    """base.html nav — 일본어 (overview.html extends base + locale=ja 시)."""
    repos = [{"full_name": "owner/repo", "analysis_count": 1, "avg_score": 50, "avg_grade": "D"}]
    out = _render("overview.html", locale="ja", current_user=_FakeUser(), repos=repos, calibration={})
    assert ">概要</a>" in out
    assert ">ダッシュボード</a>" in out
    assert ">ログアウト</button>" in out
    assert 'aria-label="メニューを開く"' in out
    assert '<html lang="ja">' in out


# ── locale 미주입 fallback ──────────────────────────────────────────────────


def test_overview_html_locale_none_defaults_to_ko():
    """overview.html — locale 미주입 시 'ko' default fallback (Jinja default 필터)."""
    out = _render("overview.html", current_user=_FakeUser(), repos=[], calibration={})
    assert "리포지토리 현황" in out
    assert '<html lang="ko">' in out


def test_add_repo_html_locale_none_defaults_to_ko():
    """add_repo.html — locale 미주입 시 'ko' default fallback."""
    out = _render("add_repo.html")
    assert "리포 추가 — SCAManager" in out
    assert "리포지토리 추가" in out
