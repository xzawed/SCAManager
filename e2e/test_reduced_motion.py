"""E2E 가드 — «동작 줄이기» 를 켠 사용자에게 화면이 실제로 멈추는가 (prefers-reduced-motion).

모션 감소의 유일한 관측이 `"prefers-reduced-motion" in css` 부분문자열이었다(#1746 K15 P1-58) —
규칙이 «적혀 있는지» 만 보고, 그 규칙이 화면에 «닿는지» 는 아무도 재지 않았다. 그래서 랜딩이
`base.html` 을 상속하지 않아 전역 리셋이 닿지 않는 것(P1-57)도 초록이었다.
여기서는 브라우저가 계산한 타이밍을 읽는다 — `document.getAnimations()` 의 `getComputedTiming()`.

실측(수정 전, reduce):

| 화면 | 남아 움직이던 것 |
|---|---|
| 랜딩 `/` | 전체화면 고정 그라데이션 `meshShift` 14초 무한(확대·회전) · 배지 점 `pulse` 무한 · 미리보기 줄 `reviewReveal` |
"""
import pytest

_ANIM_JS = r"""() => document.getAnimations().map(a => {
  const e = a.effect, t = e ? e.getComputedTiming() : {};
  const tg = e && e.target;
  const cls = tg && typeof tg.className === 'string' && tg.className.trim()
    ? '.' + tg.className.trim().split(/\s+/)[0] : '';
  return {name: a.animationName || a.transitionProperty || a.constructor.name,
          state: a.playState,
          iterations: t.iterations === Infinity ? 'inf' : t.iterations,
          duration: typeof t.duration === 'number' ? t.duration : 0,
          target: tg ? ((tg.id ? '#' + tg.id : '') || cls || tg.tagName.toLowerCase()) : '',
          pseudo: (e && e.pseudoElement) || ''};
})"""

# 모션 감소에서 남으면 안 되는 것 = 끝없이 되풀이하거나, 한 번이라도 1ms 를 넘게 움직이는 애니메이션.
#   전역 리셋은 지속을 0.01ms 로 줄이지만, 반복 횟수까지 1 로 묶지 않으면 무한 애니메이션이
#   0.01ms 주기로 계속 돌아 프레임마다 다른 지점이 칠해진다(깜빡임) — 그래서 무한은 길이와 무관하게 red.
# What must not survive reduce: an infinite animation (any duration) or one that moves for over 1ms.
_MAX_MS = 1.0


def _moving(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["state"] == "running"
            and (r["iterations"] == "inf" or r["duration"] > _MAX_MS)]


def _measure(page, url: str, motion: str) -> list[dict]:
    page.emulate_media(reduced_motion=motion)
    resp = page.goto(url)
    assert resp is not None and resp.status == 200, f"{url} status={resp and resp.status}"
    page.wait_for_timeout(600)
    return page.evaluate(_ANIM_JS)


def _assert_reduced(page, url: str) -> None:
    # 🔴 대조군 — «감소 안 함» 에서 움직이는 것이 하나도 없으면, 아래 «감소» 의 0건은 계기가 눈먼
    #    것과 구별되지 않는다. 두 레이아웃 모두 무한 `orb-drift`(`.atmosphere__orb`)를 가진다.
    plain = _moving(_measure(page, url, "no-preference"))
    assert plain, f"{url}: 감소를 끄고도 움직이는 애니메이션을 하나도 못 봤다 — 계기가 눈멀었다"
    left = _moving(_measure(page, url, "reduce"))
    assert not left, (
        f"{url}: 모션 감소를 켰는데 {len(left)}건이 계속 움직인다:\n  "
        + "\n  ".join(f"{r['name']} on {r['target']}{r['pseudo']} "
                      f"iterations={r['iterations']} duration={r['duration']}ms" for r in left[:8]))


def test_landing_stops_moving_when_reduced_motion_is_requested(anonymous_page, base_url):
    """🔴 랜딩은 `base.html` 을 상속하지 않는다 — 전역 리셋이 거기에도 닿아야 한다(P1-57)."""
    _assert_reduced(anonymous_page, f"{base_url}/")
    assert anonymous_page.locator(".landing-bg").count() == 1, (
        "랜딩이 아닌 화면을 쟀다 — `anonymous_page` 가 로그인 상태로 렌더됐다")


@pytest.mark.parametrize("path", [
    "/dashboard",
    "/repos/owner%2Ftestrepo",
    "/repos/owner%2Ftestrepo/insights",
    "/repos/owner%2Ftestrepo/settings",
    "/repos/owner%2Ftestrepo/analyses/__ID__",
])
def test_app_pages_stop_moving_when_reduced_motion_is_requested(seeded_page, base_url, seeded_analysis, path):
    """앱 화면(`base.html` 상속) — 같은 계약을 화면마다 잰다. 리포 인사이트가 종전 부분문자열
    가드(`tests/integration/test_repo_insights_css.py`)가 지키던 자리다."""
    _assert_reduced(seeded_page, f"{base_url}{path.replace('__ID__', str(seeded_analysis))}")


# 페이지 넘김 스크롤은 스크립트가 `scrollIntoView` 에 고르는 것이라 CSS 리셋이 닿지 않는다 — 따로 잰다.
#   클릭과 같은 동기 구간에서 머리 위치를 읽는다: 즉시 스크롤은 그 자리에서 도착하고, smooth 는 다음
#   프레임부터 움직여 아직 출발 전이다. 2 → 1 로 넘긴다 — 1 → 2 는 행이 줄어 문서가 짧아지고, 잘린
#   스크롤이 «도착» 처럼 보일 수 있다.
# The page-flip scroll is chosen by script, out of the CSS reset's reach; read it in the click's task.
_PAGE_FLIP_JS = r"""() => {
  const head = document.querySelector('.history-header');
  const one = Array.from(document.querySelectorAll('#pagination .page-btn'))
    .find(b => b.textContent.trim() === '1');
  if (!head || !one) return null;
  window.scrollBy(0, head.getBoundingClientRect().top + 100);
  const before = head.getBoundingClientRect().top;
  one.click();
  return {before: before, after: head.getBoundingClientRect().top};
}"""


def _flip_to_first_page(page, url: str, motion: str) -> dict:
    page.emulate_media(reduced_motion=motion)
    page.goto(url)
    page.locator("#pagination").get_by_role("button", name="2", exact=True).click()
    page.wait_for_timeout(800)
    got = page.evaluate(_PAGE_FLIP_JS)
    assert got is not None, f"{motion}: 기록 머리나 1페이지 버튼이 없다 — 시드가 2페이지를 못 만든다"
    # 🔴 머리가 화면 위에 있어야 «스크롤했는가» 를 잴 수 있다 — 아니면 둘 다 초록이다.
    assert got["before"] < -50, f"{motion}: 머리를 화면 위로 못 올렸다 {got} — 계기가 눈멀었다"
    return got


def test_history_page_flip_scrolls_at_once_when_reduced_motion_is_requested(seeded_page, base_url,
                                                                           paginated_history):
    """리포 상세 분석 이력의 페이지 넘김 — 모션 감소면 스크롤이 애니메이션 없이 그 자리에서 끝난다."""
    seeded_page.set_viewport_size({"width": 1280, "height": 240})
    url = f"{base_url}/repos/owner%2Ftestrepo"
    plain = _flip_to_first_page(seeded_page, url, "no-preference")
    # 대조군 — 감소를 끄면 smooth 라 같은 구간에서는 아직 출발 전이어야 한다. 이미 도착했다면 이 계기는
    #   smooth 와 즉시를 가르지 못한다.
    assert plain["after"] < -50, f"감소 안 함인데 클릭과 같은 구간에서 이미 도착했다 {plain} — 계기가 smooth 를 못 가른다"
    calm = _flip_to_first_page(seeded_page, url, "reduce")
    assert calm["after"] >= -1, f"모션 감소인데 페이지 넘김 스크롤이 그 자리에서 끝나지 않았다(smooth) {calm}"
