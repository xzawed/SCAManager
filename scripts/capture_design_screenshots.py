#!/usr/bin/env python3
"""
현재 서비스 12페이지 × 4테마 스크린샷 자동 캡처 (Claude Design 브리프용).
Auto-captures 12 pages × 4 themes for Claude Design brief package.

사전 조건 / Prerequisites:
  1. make run  (로컬 서버 실행 중 / local server running)
  2. 브라우저에서 로그인 후 session 쿠키 값 복사
     Copy session cookie value from browser DevTools after login

사용법 / Usage:
  python scripts/capture_design_screenshots.py --session-cookie "<value>" --repo-id 1 --analysis-id 1

출력 / Output:
  docs/design/brief/screenshots/{dark,light,pastel,catppuccin}/{page}.png
"""
import argparse
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "design" / "brief" / "screenshots"
BASE_URL = "http://localhost:8000"
THEMES = ["dark", "light", "pastel", "catppuccin"]

# 인증 불필요 페이지 / Public pages (no auth)
PAGES_PUBLIC = [
    ("landing", "/"),
]

# 인증 필요 페이지 / Auth-required pages
PAGES_AUTH = [
    ("overview", "/overview"),
    ("dashboard", "/dashboard"),
    ("add_repo", "/repos/add"),
    ("settings", "/settings"),
]

# 데이터 의존 페이지 (repo_id / analysis_id 필요) / Data-dependent pages
PAGES_DATA = [
    ("repo_detail", "/repos/{repo_id}"),
    ("repo_insights", "/repos/{repo_id}/insights"),
    ("analysis_detail", "/repos/{repo_id}/analysis/{analysis_id}"),
]

# 어드민 페이지 / Admin pages
PAGES_ADMIN = [
    ("admin_operations", "/admin/operations"),
    ("admin_rls_audit", "/admin/rls-audit"),
    ("admin_tenants", "/admin/tenants"),
]

# 모바일 캡처 대상 페이지 / Pages to also capture at mobile width
MOBILE_PAGES = {"dashboard", "analysis_detail", "repo_detail", "settings"}


async def _set_theme(page, theme: str) -> None:
    """JS로 data-theme 속성 변경 후 트랜지션 대기 / Switch theme via JS and wait for transition."""
    await page.evaluate("(t) => document.body.setAttribute('data-theme', t)", theme)
    await page.wait_for_timeout(350)  # 테마 트랜지션 안정 대기 / wait for CSS transition


async def _capture(page, name: str, theme: str, suffix: str = "") -> None:
    """스크린샷 저장 / Save screenshot."""
    filename = f"{name}{suffix}.png"
    path = OUTPUT_DIR / theme / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(path), full_page=True)
    print(f"  📸  {theme}/{filename}")


async def _capture_all_themes(page, name: str, suffix: str = "") -> None:
    """현재 페이지를 4테마 모두 캡처 / Capture current page in all 4 themes."""
    # landing 은 always-dark — dark 테마만 캡처
    # landing is always-dark — capture dark theme only
    themes = ["dark"] if name == "landing" else THEMES
    for theme in themes:
        await _set_theme(page, theme)
        await _capture(page, name, theme, suffix)


async def _make_context(browser, viewport: dict, session_cookie: str):
    """세션 쿠키 포함 컨텍스트 생성 / Create browser context with optional session cookie."""
    ctx = await browser.new_context(viewport=viewport)
    if session_cookie:
        await ctx.add_cookies([{
            "name": "session",
            "value": session_cookie,
            "domain": "localhost",
            "path": "/",
            "sameSite": "Lax",
        }])
    return ctx


async def _capture_desktop(browser, repo_id: int, analysis_id: int, session_cookie: str) -> None:
    """데스크탑(1440px) 전체 페이지 캡처 / Capture all pages at desktop width (1440px)."""
    ctx = await _make_context(browser, {"width": 1440, "height": 900}, session_cookie)
    try:
        page = await ctx.new_page()

        # 공개 페이지 / Public pages
        for name, path in PAGES_PUBLIC:
            await page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
            await _capture_all_themes(page, name)

        # 인증 페이지 / Auth-required pages
        for name, path in PAGES_AUTH:
            resp = await page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
            if resp and resp.url.endswith("/") and name != "overview":
                print(f"  ⚠️  {name}: 인증 실패 — session-cookie 를 확인하세요")
                continue
            await _capture_all_themes(page, name)

        # 데이터 의존 페이지 / Data-dependent pages
        for name, path_tmpl in PAGES_DATA:
            path = path_tmpl.format(repo_id=repo_id, analysis_id=analysis_id)
            resp = await page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
            if resp and resp.status == 404:
                print(f"  ⚠️  {name}: 404 — --repo-id / --analysis-id 를 확인하세요")
                continue
            await _capture_all_themes(page, name)

        # 어드민 페이지 / Admin pages
        for name, path in PAGES_ADMIN:
            resp = await page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
            if resp and resp.status in (403, 404):
                print(f"  ⚠️  {name}: {resp.status} — 어드민 계정인지 확인하세요")
                continue
            await _capture_all_themes(page, name)
    finally:
        await ctx.close()


async def _capture_mobile(browser, repo_id: int, analysis_id: int, session_cookie: str) -> None:
    """모바일(390px) 주요 페이지 캡처 / Capture key pages at mobile width (390px)."""
    ctx = await _make_context(browser, {"width": 390, "height": 844}, session_cookie)
    try:
        page = await ctx.new_page()

        all_pages = PAGES_PUBLIC + PAGES_AUTH + PAGES_DATA + PAGES_ADMIN
        for name, path_tmpl in all_pages:
            if name not in MOBILE_PAGES:
                continue
            path = path_tmpl.format(repo_id=repo_id, analysis_id=analysis_id)
            await page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
            await _capture_all_themes(page, name, suffix="-mobile")
    finally:
        await ctx.close()


def _make_stdout_safe():
    """Windows cp949 stdout 에서 이모지/한글 출력 크래시 방지 — UTF-8 재구성(errors=replace).
    Guard against the cp949 emoji/Korean print crash on Windows (UTF-8, replace on miss).

    🔴 standalone 실행(`python scripts/x.py`)이라 공유 헬퍼를 import 할 수 없다 — scripts/ 에
    패키지 초기화가 없어 sys.path 조작이 필요해지므로, 검증된 관용구를 각 스크립트에
    복제한다(정책 16 최소 추상화). 누락 방지는 회귀 가드가 담당:
    `tests/unit/scripts/test_stdout_encoding_guard.py`.
    Scripts run standalone, so the idiom is duplicated rather than imported; a regression guard
    asserts no script is left unguarded.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / stream without reconfigure


async def main(args: argparse.Namespace) -> None:
    """CLI 진입점 — 데스크탑·모바일 캡처 순서대로 실행 / CLI entry point: desktop then mobile."""
    _make_stdout_safe()
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # ── 데스크탑 (1440px) 캡처 ──────────────────────────────────────────
        # Desktop (1440px) capture
        await _capture_desktop(browser, args.repo_id, args.analysis_id, args.session_cookie)

        # ── 모바일 (390px) 캡처 — 주요 페이지만 ────────────────────────────
        # Mobile (390px) capture — key pages only
        await _capture_mobile(browser, args.repo_id, args.analysis_id, args.session_cookie)

        await browser.close()

    total = sum(1 for _ in OUTPUT_DIR.rglob("*.png"))
    print(f"\n✅  캡처 완료 — 총 {total}장 → {OUTPUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SCAManager design screenshots")
    parser.add_argument("--session-cookie", default="", help="session cookie value")
    parser.add_argument("--repo-id", type=int, default=1, help="existing repo ID")
    parser.add_argument("--analysis-id", type=int, default=1, help="existing analysis ID")
    asyncio.run(main(parser.parse_args()))
