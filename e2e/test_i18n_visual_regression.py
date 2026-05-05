"""Phase 5 PR-16 — i18n E2E 시각 회귀 가드 (3 언어 × 주요 페이지).

Phase 5 PR-16 — i18n E2E visual regression guards (3 languages × main pages).

검증 범위 (Coverage):
1. 3 언어 (en/ko/ja) × 4 주요 페이지 (login/overview/dashboard/settings) 렌더링
2. preferred_language Cookie 설정 시 LocaleMiddleware 가 해당 언어 적용
3. 언어별 핵심 텍스트 (header/title/nav) 표시 검증
4. Cookie 미설정 시 default locale ('en') fallback 검증
5. base.html nav 메뉴 (Overview/Dashboard/Logout) 다국어 적용 검증

본 가이드는 정책 11 페어 (UI/시각 변경 PR 8 조합 시각 체크리스트 의무) 자동화 보조 가드.
사용자 시각 검증 책임은 보존 — 본 가드는 정적 text + nav structure 회귀 차단만.

This guard supports Policy 11 (8-combination visual checklist obligation for UI changes) but
DOES NOT replace user manual visual verification — only prevents text/structure regression.
"""
import pytest


# ── 언어별 키 텍스트 매트릭스 (anchor texts for visual regression) ───────────


_I18N_ANCHORS = {
    "en": {
        "nav_overview": "Overview",
        "nav_dashboard": "Dashboard",
        "nav_logout": "Logout",
        "login_subtitle": "Claude reviews your PR",
        "login_button": "Sign in with GitHub",
        "overview_title": "Today's Analyses",
        "overview_title_empty": "Repository Status",
        "dashboard_title": "Dashboard",
        "settings_save": "Save settings",
        "settings_page_title": "Repository Settings",
    },
    "ko": {
        "nav_overview": "개요",
        "nav_dashboard": "대시보드",
        "nav_logout": "로그아웃",
        "login_subtitle": "PR이 들어오면 Claude가 검토",
        "login_button": "GitHub로 로그인",
        "overview_title": "오늘의 분석",
        "overview_title_empty": "리포지토리 현황",
        "dashboard_title": "대시보드",
        "settings_save": "설정 저장",
        "settings_page_title": "리포지토리 설정",
    },
    "ja": {
        "nav_overview": "概要",
        "nav_dashboard": "ダッシュボード",
        "nav_logout": "ログアウト",
        "login_subtitle": "PRが入ってきたらClaude",
        "login_button": "GitHubでログイン",
        "overview_title": "本日の分析",
        "overview_title_empty": "リポジトリ状況",
        "dashboard_title": "ダッシュボード",
        "settings_save": "設定を保存",
        "settings_page_title": "リポジトリ設定",
    },
}


def _set_locale_cookie(page, base_url: str, locale: str) -> None:
    """preferred_language Cookie 설정 — LocaleMiddleware 가 Layer 1 (Cookie) 우선 감지.

    Set preferred_language cookie — LocaleMiddleware Layer 1 takes priority.
    """
    page.context.add_cookies([{
        "name": "preferred_language",
        "value": locale,
        "url": base_url,
    }])


# ── /login (비로그인 진입 페이지) ──────────────────────────────────────────


@pytest.mark.parametrize("locale", ["en", "ko", "ja"])
def test_login_page_i18n_render(page, base_url, locale):
    """/login 페이지 — 3 언어 (en/ko/ja) 텍스트 렌더링 검증.

    /login is unauthenticated, so Cookie-based locale must be respected.
    """
    _set_locale_cookie(page, base_url, locale)
    page.goto(f"{base_url}/login")
    body = page.content()

    anchors = _I18N_ANCHORS[locale]
    assert anchors["login_subtitle"] in body, (
        f"login subtitle missing for locale={locale}"
    )
    assert anchors["login_button"] in body, (
        f"login button missing for locale={locale}"
    )

    # HTML lang attribute 동적 검증
    html_tag_re = page.locator("html")
    actual_lang = html_tag_re.get_attribute("lang")
    assert actual_lang == locale, (
        f"<html lang='{actual_lang}'> doesn't match expected '{locale}'"
    )


# ── / (overview — 로그인 후) ──────────────────────────────────────────────


@pytest.mark.parametrize("locale", ["en", "ko", "ja"])
def test_overview_page_i18n_render(page, base_url, locale):
    """/ overview 페이지 — 3 언어 nav + title 렌더링 검증."""
    _set_locale_cookie(page, base_url, locale)
    page.goto(f"{base_url}/")
    body = page.content()

    anchors = _I18N_ANCHORS[locale]
    # base.html nav 검증
    assert anchors["nav_overview"] in body, (
        f"nav 'Overview' missing for locale={locale}"
    )
    assert anchors["nav_dashboard"] in body, (
        f"nav 'Dashboard' missing for locale={locale}"
    )
    assert anchors["nav_logout"] in body, (
        f"nav 'Logout' missing for locale={locale}"
    )

    # overview title — 리포 0 vs ≥1 분기 모두 포괄
    assert (
        anchors["overview_title"] in body
        or anchors["overview_title_empty"] in body
    ), f"overview title missing for locale={locale}"


# ── /dashboard ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("locale", ["en", "ko", "ja"])
def test_dashboard_page_i18n_render(page, base_url, locale):
    """/dashboard 페이지 — 3 언어 title + nav 렌더링 검증."""
    _set_locale_cookie(page, base_url, locale)
    page.goto(f"{base_url}/dashboard")
    body = page.content()

    anchors = _I18N_ANCHORS[locale]
    assert anchors["dashboard_title"] in body, (
        f"dashboard title missing for locale={locale}"
    )
    assert anchors["nav_overview"] in body
    assert anchors["nav_dashboard"] in body


# ── /repos/{name}/settings (settings 페이지 — repo 시드 의무) ─────────────


@pytest.mark.parametrize("locale", ["en", "ko", "ja"])
def test_settings_page_i18n_render(seeded_page, base_url, locale):
    """/repos/{owner}/{repo}/settings 페이지 — 3 언어 title + save button 검증.

    seeded_page fixture = repo 시드 + 신규 page (격리 context). Cookie 는 본 함수에서 추가.
    seeded_page fixture seeds owner/testrepo + a fresh page; we add the cookie locally.
    """
    seeded_page.context.add_cookies([{
        "name": "preferred_language",
        "value": locale,
        "url": base_url,
    }])
    seeded_page.goto(f"{base_url}/repos/owner/testrepo/settings")
    body = seeded_page.content()

    anchors = _I18N_ANCHORS[locale]
    # 페이지 헤더 (`리포지토리 설정` 등)
    assert anchors["settings_page_title"] in body, (
        f"settings page title missing for locale={locale}"
    )
    # 저장 버튼 — 페이지 하단 의무 노출
    assert anchors["settings_save"] in body, (
        f"settings save button missing for locale={locale}"
    )


# ── default locale fallback (Cookie 미설정) ────────────────────────────────


def test_no_cookie_falls_to_default_locale(page, base_url):
    """Cookie 미설정 시 settings.default_locale ('en') fallback 검증."""
    # Cookie 미설정 — 기존 컨텍스트 cookies 모두 삭제
    page.context.clear_cookies()
    page.goto(f"{base_url}/login")
    body = page.content()

    # default = 'en'
    anchors_en = _I18N_ANCHORS["en"]
    assert anchors_en["login_subtitle"] in body, (
        "default locale fallback failed — expected English subtitle"
    )

    actual_lang = page.locator("html").get_attribute("lang")
    assert actual_lang == "en", f"expected default lang='en', got '{actual_lang}'"


# ── 언어 전환 일관성 (Cookie 변경 시 즉시 반영) ─────────────────────────


def test_locale_switch_via_cookie_takes_effect(page, base_url):
    """preferred_language Cookie 변경 시 다음 요청에서 즉시 다른 언어 표시."""
    # 1차: en
    _set_locale_cookie(page, base_url, "en")
    page.goto(f"{base_url}/login")
    assert "Sign in with GitHub" in page.content()

    # 2차: ko 로 전환
    page.context.clear_cookies()
    _set_locale_cookie(page, base_url, "ko")
    page.goto(f"{base_url}/login")
    assert "GitHub로 로그인" in page.content()

    # 3차: ja 로 전환
    page.context.clear_cookies()
    _set_locale_cookie(page, base_url, "ja")
    page.goto(f"{base_url}/login")
    assert "GitHubでログイン" in page.content()
