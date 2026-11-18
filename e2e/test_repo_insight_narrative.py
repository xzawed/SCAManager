"""E2E — 리포 인사이트 서술 자리 → 조각 (원장 #1706 안 C 를 리포 인사이트에).

캐시 미스 — 페이지는 유료 호출을 하지 않고 자리(aria-busy · 로딩 문구)만 그린다. htmx 가
`GET /repos/{name}/insights/narrative` 로 조각을 받아 그 자리를 통째로 바꾼다. 조각 요청 자체가 실패하면(5xx · 연결
끊김) 자리가 들고 있던 실패 줄(`<template>`)로 바꾼다. Claude 호출은 `repo_insight_call_held` 가 붙잡아 두므로 자리
상태를 시간에 기대지 않고 본다.

On a cache miss the repo insights page draws a placeholder that htmx swaps for the narrative fragment,
or for the failure line when the fragment request itself fails.
"""
import pytest
from playwright.sync_api import expect

from e2e.conftest import INSIGHT_LANGUAGE, REPO_NARRATIVE_HELD_TEXT, repo_insight_call_held

_REPO = "owner/testrepo"
_PAGE = f"/repos/{_REPO}/insights?days=30"
_FRAGMENT_SUFFIX = "/insights/narrative"


def _pin_language(page, base_url):
    page.context.add_cookies([{"name": "preferred_language", "value": INSIGHT_LANGUAGE, "url": base_url}])


def test_repo_narrative_placeholder_is_swapped_for_the_fragment(seeded_page, base_url, seeded_analysis):
    """자리(aria-busy · 로딩 문구)가 먼저 보이고, 호출이 풀리면 조각의 서술 카드가 그 자리를 바꾼다 — 자리는 하나만 남는다."""
    _pin_language(seeded_page, base_url)
    with repo_insight_call_held(_REPO, days=30) as release:
        with seeded_page.expect_request(lambda r: r.url.split("?")[0].endswith(_FRAGMENT_SUFFIX)) as req:
            seeded_page.goto(f"{base_url}{_PAGE}")
        busy = seeded_page.locator('#riNarrative[aria-busy="true"] .ri-narrative-note[role="status"]')
        expect(busy).to_be_visible()
        assert req.value.headers.get("hx-request") == "true", "조각 요청이 htmx 요청이 아니다"
        assert seeded_page.locator("#riNarrative .ri-narrative-card").count() == 0, "호출이 멈춰 있는데 카드가 있다"
        release()
        expect(seeded_page.locator("#riNarrative .ri-narrative-card")).to_be_visible(timeout=15000)
    expect(seeded_page.locator("#riNarrative .ri-narrative-text")).to_have_text(REPO_NARRATIVE_HELD_TEXT)
    expect(seeded_page.locator('#riNarrative a[href*="refresh=1"]')).to_be_visible()
    assert seeded_page.locator("#riNarrative").count() == 1
    assert seeded_page.locator("#riNarrative[aria-busy], #riNarrative[hx-get]").count() == 0, (
        "바꿔 낀 뒤에도 자리 속성이 남았다 — 조각이 또 불리거나 «바쁨» 이 안 풀린다")


@pytest.mark.parametrize("failure", ["server_error", "network_error"])
def test_a_failed_repo_fragment_request_falls_back_to_the_failure_line(
        seeded_page, base_url, seeded_analysis, failure):
    """조각 요청이 5xx(`htmx:responseError`)이거나 끊기면(`htmx:sendError`) 실패 줄 · 새로 고침 링크로 바꾼다."""
    _pin_language(seeded_page, base_url)

    def _fail(route):
        if failure == "server_error":
            route.fulfill(status=500, body="boom")
        else:
            route.abort()

    pattern = f"**{_FRAGMENT_SUFFIX}?*"
    seeded_page.route(pattern, _fail)
    try:
        with repo_insight_call_held(_REPO, days=30):
            seeded_page.goto(f"{base_url}{_PAGE}")
            expect(seeded_page.locator("#riNarrative .ri-narrative-failed")).to_be_visible(timeout=15000)
    finally:
        seeded_page.unroute(pattern)
    expect(seeded_page.locator('#riNarrative a[href*="refresh=1"]')).to_be_visible()
    assert seeded_page.locator("#riNarrative").count() == 1
    assert seeded_page.locator("#riNarrative[aria-busy], #riNarrative[hx-get]").count() == 0
