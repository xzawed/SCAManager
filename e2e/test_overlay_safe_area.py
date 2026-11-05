"""띄워 둔 fixed 요소(토스트 · 오류 배너)는 노치 · 홈 표시줄의 안전 영역 안에 칠해진다.

CDP 로 네 쪽 inset 을 심고 `env()` 로 다시 읽어 확인한 뒤, 각 요소를 앱이 띄우는 길로 띄워 상자가 안전
영역 안인지 잰다. inset 은 각 요소의 기본 거리(16~24px)보다 크게 심는다 — 작으면 inset 을 안 써도 안쪽에
들어와 공허한 초록이다. 단위 쪽(`tests/unit/ui/test_fixed_overlay_safe_area.py`)은 CSS 선언을 보고,
여기서는 브라우저가 그 선언으로 실제로 어디에 그렸는가를 본다.
Floating fixed overlays must render inside the safe area once insets are planted through CDP.
"""
from __future__ import annotations

import pytest

from e2e.test_theme_mobile_guards import _STATE_OPENERS

_INSET = 40
# 선택자 → (경로, 여는 JS(없으면 경로가 띄운다), 붙어 있는 가장자리)
# selector → (path, opener JS or None when the path itself shows it, anchored edges)
_SIGNED_IN = {
    "#issueToast": ("/repos/owner%2Ftestrepo/analyses/__ID__", _STATE_OPENERS["#issueToast"][1],
                    ("bottom", "right")),
    "#errorToast": ("/repos/add", _STATE_OPENERS[".toast"][1], ("top",)),
    "#saveToast": ("/repos/owner%2Ftestrepo/settings?saved=1", None, ("top",)),
}

_BOX_JS = """async sel => {
    const frame = () => new Promise(r => requestAnimationFrame(() => r()));
    await frame(); await frame();
    const env = side => {
        const probe = document.createElement('div');
        probe.style.cssText = `position:absolute;height:0;width:env(safe-area-inset-${side}, 0px)`;
        document.body.appendChild(probe);
        const w = probe.getBoundingClientRect().width;
        probe.remove();
        return w;
    };
    const el = document.querySelector(sel);
    if (!el) return {error: sel + ' 가 없다'};
    // 문서의 애니메이션이 다 끝난 자리를 잰다 — 토스트는 사용자 동작 뒤(진입 애니메이션이 끝난 뒤)에 뜬다.
    // 진입 애니메이션이 도는 동안은 `.container` 의 transform 이 fixed 의 기준이라, 끝내지 않고 재면 그 순간을 잰다.
    // Measure once every animation has finished: overlays appear after a user action, past the page entry.
    for (const a of document.getAnimations()) { try { a.finish(); } catch (e) { /* 무한 반복은 건너뛴다 */ } }
    await frame();
    const r = el.getBoundingClientRect(), doc = document.documentElement;
    return {inset: {top: env('top'), right: env('right'), bottom: env('bottom'), left: env('left')},
            box: {top: r.top, right: r.right, bottom: r.bottom, left: r.left, w: r.width, h: r.height},
            vw: doc.clientWidth, vh: doc.clientHeight, shown: el.checkVisibility()};
}"""


# fixed 의 기준을 화면에서 빼앗는 조상 속성 — 하나라도 있으면 그 조상이 기준 상자가 된다.
# Ancestor properties that make the ancestor, not the viewport, the containing block of a fixed element.
_CONTAINING_BLOCK_JS = """async () => {
    const frame = () => new Promise(r => requestAnimationFrame(() => r()));
    for (const a of document.getAnimations()) { try { a.finish(); } catch (e) { /* 무한 반복은 건너뛴다 */ } }
    await frame(); await frame();
    const takes = s => {
        const hit = [];
        for (const k of ['transform', 'translate', 'rotate', 'scale', 'perspective', 'filter', 'backdropFilter'])
            if (s[k] && s[k] !== 'none') hit.push(`${k}: ${s[k]}`);
        if (/transform|perspective|filter/.test(s.willChange)) hit.push(`will-change: ${s.willChange}`);
        if (/paint|layout|strict|content/.test(s.contain)) hit.push(`contain: ${s.contain}`);
        if (/size/.test(s.containerType)) hit.push(`container-type: ${s.containerType}`);
        return hit;
    };
    const name = el => el.id ? '#' + el.id : el.tagName.toLowerCase() + '.' + String(el.className).split(' ')[0];
    const fixed = [...document.querySelectorAll('body *')].filter(el => getComputedStyle(el).position === 'fixed');
    const captured = [];
    for (const el of fixed) {
        for (let a = el.parentElement; a && a !== document.documentElement; a = a.parentElement) {
            const hit = takes(getComputedStyle(a));
            if (hit.length) { captured.push(`${name(el)} ← ${name(a)} (${hit.join(' · ')})`); break; }
        }
    }
    return {fixed: fixed.map(name), captured};
}"""

# 본문 안에 fixed 요소가 있는 화면 — 이슈 모달은 열어서 잰다(닫히면 display: none 이라 안 잡힌다).
# Screens with fixed elements inside the page body; the issue modal is measured open.
_BODY_OVERLAYS = {
    "/repos/owner%2Ftestrepo/analyses/__ID__": (_STATE_OPENERS["#issueModalOverlay"][1],
                                                ("#issueModalOverlay", "#issueToast")),
    "/repos/add": (None, ("#errorToast",)),
    "/repos/owner%2Ftestrepo/settings?saved=1": (None, ("#saveToast",)),
}


@pytest.mark.parametrize("path", sorted(_BODY_OVERLAYS))
def test_fixed_elements_are_positioned_against_the_viewport(seeded_page, base_url, seeded_analysis, path):
    """🔴 fixed 요소는 화면을 기준으로 그려진다 — 조상의 transform 등이 기준을 빼앗으면 모달이 본문 상자의
    한가운데(긴 페이지면 화면 밖)에, 토스트가 본문 끝에 그려진다. 진입 애니메이션이 끝난 뒤에 잰다."""
    opener, expected = _BODY_OVERLAYS[path]
    seeded_page.set_viewport_size({"width": 390, "height": 844})
    seeded_page.goto(f"{base_url}{path.replace('__ID__', str(seeded_analysis))}")
    if opener:
        seeded_page.evaluate(opener)
    res = seeded_page.evaluate(_CONTAINING_BLOCK_JS)
    missing = [sel for sel in expected if sel not in res["fixed"]]
    assert not missing, f"{path}: fixed 로 잡히지 않은 요소 {missing} (잡힌 것 {res['fixed']}) — 재지 못했다"
    assert not res["captured"], f"{path}: 화면이 아니라 조상을 기준으로 그려지는 fixed 요소:\n  " + "\n  ".join(
        res["captured"])


def _plant_insets(page) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    cdp = page.context.new_cdp_session(page)
    cdp.send("Emulation.setSafeAreaInsetsOverride",
             {"insets": {"top": _INSET, "right": _INSET, "bottom": _INSET, "left": _INSET}})


def _assert_inside(res: dict, selector: str, edges: tuple[str, ...]) -> None:
    assert not res.get("error"), res["error"]
    want = {side: _INSET for side in ("top", "right", "bottom", "left")}
    assert res["inset"] == want, f"inset {want} 을 심었는데 env() 가 {res['inset']} — 못 심었다(공허)"
    box = res["box"]
    assert res["shown"] and box["w"] > 0 and box["h"] > 0, f"{selector} 가 안 떴다({res}) — 재지 못했다"
    limits = {"top": (box["top"], ">=", _INSET), "left": (box["left"], ">=", _INSET),
              "bottom": (box["bottom"], "<=", res["vh"] - _INSET),
              "right": (box["right"], "<=", res["vw"] - _INSET)}
    outside = [f"{side}: {at:.1f}px (안전 영역 경계 {edge}px)" for side in edges
               for at, op, edge in [limits[side]]
               if (op == ">=" and at < edge - 0.5) or (op == "<=" and at > edge + 0.5)]
    assert not outside, f"{selector} 가 inset {_INSET}px 안전 영역 밖에 그려진다 — " + " · ".join(outside)


@pytest.mark.parametrize("selector", sorted(_SIGNED_IN))
def test_floating_overlay_stays_inside_the_safe_area(seeded_page, base_url, seeded_analysis, selector):
    """🔴 이슈 생성 토스트 · 등록 오류 토스트 · 저장 토스트 — 붙어 있는 가장자리의 inset 만큼 물러나 그린다."""
    path, opener, edges = _SIGNED_IN[selector]
    _plant_insets(seeded_page)
    seeded_page.goto(f"{base_url}{path.replace('__ID__', str(seeded_analysis))}")
    if opener:
        seeded_page.evaluate(opener)
    _assert_inside(seeded_page.evaluate(_BOX_JS, selector), selector, edges)


def test_landing_error_banner_stays_inside_the_safe_area(anonymous_page, base_url):
    """🔴 랜딩의 로그인 오류 배너 — 위는 이미 inset 을 쓴다. 좌우 16px 여백도 가로 모드 노치를 피해야 한다."""
    _plant_insets(anonymous_page)
    anonymous_page.goto(f"{base_url}/?error=oauth_failed")
    _assert_inside(anonymous_page.evaluate(_BOX_JS, "#authErrorBanner"), "#authErrorBanner",
                   ("top", "left", "right"))
