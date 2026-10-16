"""첫 그림 — 운영과 비슷한 지연에서도 첫 화면이 «최종 테마 · 등장 전 상태» 로 그려진다.

저장 테마 적용 · 등장 애니메이션(reveal) · 카운트업이 전부 `<body>` 맨 끝 스크립트에서 시작하면,
그 앞의 외부 스크립트(htmx · effects · Chart.js — `no-cache` 라 새로 열 때마다 서버 재검증)를
기다리는 동안 브라우저가 먼저 그린다. 실측(2026-10-16, 왕복 300ms 에뮬): 라이트 사용자에게 dark 가
1~5 프레임 보인 뒤 body 배경 전환(200ms)으로 «검은 바탕 위 흰 카드» 가 이어졌고, 테마와 상관없이
KPI 가 «73.1 → 15.5 → 다시 증가» 로 되감기고 카드가 보였다가 사라졌다.
로컬 e2e 는 지연이 0이라 이 축을 한 번도 보지 못했다 — 그래서 CDP 로 왕복을 건다.

First paint under production-like latency must already be the stored theme and the pre-entrance
state: nothing that was painted visible may be hidden again, and no visible KPI may count backwards.
"""
from __future__ import annotations

import pytest

# 이 PC → 운영(Railway) 실측: 브라우저 HTML 첫 바이트 320~500ms. 300ms 는 «낙관적인 운영» 이다.
# Measured from the dev PC to production: 320-500ms to the HTML's first byte.
_LATENCY_MS = 300

# rAF 마다 «지금 그려질 상태» 를 적는다 — 문서 생성 직후(어떤 페이지 스크립트보다 먼저) 심는다.
# Record, on every animation frame, the state that frame is about to paint.
_FRAME_LOG_JS = r"""
(() => {
  if (window.__fp) return;
  const L = window.__fp = {frames: []};
  const ids = new Map();
  const idOf = (el) => { if (!ids.has(el)) ids.set(el, ids.size); return ids.get(el); };
  const effOp = (el) => {
    let o = 1;
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity);
    return Math.round(o * 100) / 100;
  };
  const tick = () => {
    const b = document.body;
    // 🔴 body 가 생긴 순간부터 적는다 — 내용이 붙기 전 «빈 배경» 프레임도 테마 판정 대상이다
    //    (Grok `99aa48c8`: 서버가 그린 body 속성이 동기화 스크립트보다 먼저 그려질 틈).
    if (b) {
      const els = Array.from(document.querySelectorAll(
        '.card, .s-card, .kpi-card, .kpi, .repo-card, .detail-hero, .freq-row, .issue')).slice(0, 60);
      const kpis = Array.from(document.querySelectorAll('.kpi__value')).slice(0, 8);
      L.frames.push({
        t: performance.now(),
        html: document.documentElement.getAttribute('data-theme'),
        body: b.getAttribute('data-theme'),
        vis: els.filter(e => e.isConnected && e.getBoundingClientRect().height > 0)
                .map(e => [idOf(e), effOp(e), e.className && String(e.className).slice(0, 40)]),
        kpi: kpis.map(e => [idOf(e), e.textContent.trim(), effOp(e)]),
      });
    }
    if (L.frames.length < 400) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
})();
"""

# 그려진 프레임만 판정한다(첫 콘텐츠 그림 이전 프레임은 화면에 나오지 않는다).
# Judge only frames at or after first contentful paint.
_VERDICT_JS = r"""
(theme) => {
  const fcpEntry = performance.getEntriesByName('first-contentful-paint')[0];
  if (!fcpEntry) return {error: 'first-contentful-paint 가 없다 — 그려진 프레임을 고를 수 없다'};
  const fcp = fcpEntry.startTime;
  const all = (window.__fp || {frames: []}).frames;
  const frames = all.filter(f => f.t >= fcp - 20);
  if (!frames.length) return {error: '첫 콘텐츠 그림 이후 프레임이 0개 — 관측 실패'};
  // 테마는 body 가 생긴 «모든» 프레임에서 본다. body 에 속성이 없으면 html 의 토큰을 상속한다.
  // Theme is judged on every frame since <body> exists; a body without the attribute inherits <html>.
  const wrongTheme = all.filter(f => f.html !== theme || (f.body || f.html) !== theme)
                        .map(f => [Math.round(f.t), f.html, f.body]);
  const seenVisible = new Map(), unpainted = [];
  for (const f of frames) {
    for (const [id, op, cls] of f.vis) {
      if (op >= 0.5 && !seenVisible.has(id)) seenVisible.set(id, [Math.round(f.t), cls]);
      else if (op < 0.05 && seenVisible.has(id)) {
        unpainted.push({cls, visible_at: seenVisible.get(id)[0], hidden_at: Math.round(f.t)});
        seenVisible.delete(id);
      }
    }
  }
  const lastVisible = new Map(), rewound = [];
  for (const f of frames) {
    for (const [id, text, op] of f.kpi) {
      const m = text.match(/-?\d+(?:\.\d+)?/);
      if (!m || op < 0.5) continue;
      const v = parseFloat(m[0]);
      if (lastVisible.has(id) && v < lastVisible.get(id) - 0.001)
        rewound.push({from: lastVisible.get(id), to: v, at: Math.round(f.t)});
      lastVisible.set(id, v);
    }
  }
  const last = frames[frames.length - 1];
  return {frames: frames.length, wrong_theme: wrongTheme.slice(0, 5), wrong_theme_n: wrongTheme.length,
          unpainted: unpainted.slice(0, 5), unpainted_n: unpainted.length,
          rewound: rewound.slice(0, 5), rewound_n: rewound.length,
          visible_at_end: last.vis.filter(v => v[1] >= 0.5).length};
}
"""


def _paths(analysis_id: int) -> list[str]:
    # 차트가 있는 화면(Chart.js 205KB 가 테마 스크립트 앞을 막는다) + 없는 화면 + 설정.
    # Chart pages (Chart.js blocks before the theme script), a chart-less page and settings.
    return ["/dashboard", "/repos/owner/testrepo",
            f"/repos/owner/testrepo/analyses/{analysis_id}",
            "/repos/owner/testrepo/settings", "/"]


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_first_paint_is_the_stored_theme_and_never_unpaints(browser_instance, live_server,
                                                             seeded_analysis, theme):
    """🔴 그려진 첫 프레임부터 저장 테마이고, 한 번 보인 카드는 다시 숨지 않고, 보이는 KPI 는 줄지 않는다.

    The first painted frame already uses the stored theme; nothing painted visible is hidden
    again; no visible KPI counts backwards.
    """
    problems: list[str] = []
    for path in _paths(seeded_analysis):
        ctx = browser_instance.new_context(base_url=live_server, viewport={"width": 1440, "height": 900})
        try:
            ctx.add_init_script(script=f"try{{localStorage.setItem('sca-theme','{theme}')}}catch(e){{}}")
            ctx.add_init_script(script=_FRAME_LOG_JS)
            page = ctx.new_page()
            cdp = ctx.new_cdp_session(page)
            cdp.send("Network.enable")
            cdp.send("Network.emulateNetworkConditions", {
                "offline": False, "latency": _LATENCY_MS,
                "downloadThroughput": 2_500_000, "uploadThroughput": 1_250_000})
            page.goto(path, wait_until="load", timeout=60000)
            page.wait_for_timeout(2500)
            res = page.evaluate(_VERDICT_JS, theme)
        finally:
            ctx.close()
        # 못 재면 초록이 아니라 red — 관측 0 은 «통과» 가 아니다.
        # Unmeasurable is red, not green.
        assert not res.get("error"), f"{path}: {res.get('error')}"
        assert res["visible_at_end"] > 0, (
            f"{path}: 끝까지 보이는 카드가 0개 — 감시 선택자가 화면과 어긋났다(공허한 초록)")
        if res["wrong_theme_n"]:
            problems.append(f"[{theme}] {path}: 저장 테마가 아닌 프레임 {res['wrong_theme_n']}개 "
                            f"(t, html, body) {res['wrong_theme']}")
        if res["unpainted_n"]:
            problems.append(f"[{theme}] {path}: 보였다가 다시 숨은 요소 {res['unpainted_n']}개 {res['unpainted']}")
        if res["rewound_n"]:
            problems.append(f"[{theme}] {path}: 보이는 KPI 가 되감김 {res['rewound_n']}회 {res['rewound']}")
    assert not problems, "첫 그림이 최종 상태가 아니다:\n  " + "\n  ".join(problems)


# hx-boost 이동 — 새 본문이 정착하기 전 프레임도 «등장 전» 이어야 한다.
# hx-boost navigation: frames before the new body settles must also be in the pre-entrance state.
_ARM_JS = r"""() => {
  const L = window.__bf = {frames: []};
  const ids = new Map(); const idOf = (el) => { if (!ids.has(el)) ids.set(el, ids.size); return ids.get(el); };
  const effOp = (el) => { let o = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity); return Math.round(o * 100) / 100; };
  const tick = () => {
    L.frames.push({t: performance.now(), path: location.pathname,
      vis: Array.from(document.querySelectorAll('.card, .s-card, .kpi-card, .kpi, .repo-card, .detail-hero, .freq-row, .issue'))
        .slice(0, 60).filter(e => e.isConnected && e.getBoundingClientRect().height > 0).map(e => [idOf(e), effOp(e)]),
      kpi: Array.from(document.querySelectorAll('.kpi__value')).slice(0, 8).map(e => [idOf(e), e.textContent.trim(), effOp(e)])});
    if (L.frames.length < 300) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}"""

_BOOST_JS = r"""(url) => new Promise((resolve) => {
  const done = () => { document.removeEventListener('htmx:afterSettle', done); resolve(true); };
  document.addEventListener('htmx:afterSettle', done);
  const a = document.createElement('a'); a.href = url; a.textContent = 'go'; document.body.appendChild(a);
  htmx.process(a); a.click(); setTimeout(() => resolve(false), 15000);
})"""

_BOOST_VERDICT_JS = r"""(want) => {
  const fr = window.__bf.frames.filter(f => f.path === want);
  const seen = new Set(), unpainted = [];
  for (const f of fr) for (const [id, op] of f.vis) {
    if (op >= 0.5) seen.add(id); else if (op < 0.05 && seen.has(id)) { unpainted.push(Math.round(f.t)); seen.delete(id); }
  }
  const last = new Map(), rewound = [];
  for (const f of fr) for (const [id, text, op] of f.kpi) {
    const m = text.match(/-?\d+(?:\.\d+)?/); if (!m || op < 0.5) continue;
    const v = parseFloat(m[0]); if (last.has(id) && v < last.get(id) - 0.001) rewound.push([last.get(id), v]);
    last.set(id, v);
  }
  const end = fr.length ? fr[fr.length - 1].vis.filter(v => v[1] >= 0.5).length : 0;
  return {frames: fr.length, unpainted, rewound, visible_at_end: end};
}"""


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_boosted_navigation_never_rewinds_or_unpaints(browser_instance, live_server, seeded_analysis, theme):
    """🔴 hx-boost 로 대시보드에 들어갈 때 KPI 가 «최종값 → 0» 으로 되감기거나 보인 카드가 숨지 않는다.

    실측(수정 전): `/` → `/dashboard` 6회 중 5회 KPI «85 → 14» — 새 본문이 정착(settle 20ms) 전 한
    프레임 그대로 그려진 뒤 effects.js 가 0 으로 되돌렸다. 확률적이라 세 번 연달아 잰다.
    """
    problems = []
    for rep in range(3):
        ctx = browser_instance.new_context(base_url=live_server, viewport={"width": 1440, "height": 900})
        try:
            ctx.add_init_script(script=f"try{{localStorage.setItem('sca-theme','{theme}')}}catch(e){{}}")
            page = ctx.new_page()
            page.goto("/", wait_until="load")
            page.wait_for_timeout(1200)
            page.evaluate(_ARM_JS)
            settled = page.evaluate(_BOOST_JS, "/dashboard")
            page.wait_for_timeout(2500)
            res = page.evaluate(_BOOST_VERDICT_JS, "/dashboard")
        finally:
            ctx.close()
        assert settled, f"[{theme}] 대시보드로의 hx-boost 이동이 정착하지 않았다"
        assert res["frames"] and res["visible_at_end"] > 0, f"[{theme}] 이동 뒤 프레임·보이는 카드가 없다 {res}"
        if res["unpainted"] or res["rewound"]:
            problems.append(f"[{theme}] #{rep}: 숨음 {res['unpainted'][:3]} · KPI 되감김 {res['rewound'][:3]}")
    assert not problems, "hx-boost 이동 직후 그림이 최종 상태가 아니다:\n  " + "\n  ".join(problems)
