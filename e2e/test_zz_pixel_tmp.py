"""TEMPORARY pixel-truth contrast sweep — not committed.

🔴 배경을 «계산» 하지 않는다. 글자를 전부 투명하게 만든 뒤 화면을 한 장 찍으면 그 그림이
곧 «칠해진 배경» 이다. 조상 사슬을 걷는 합성기는 형제가 칠한 층(aurora/orb glow)을
구조적으로 보지 못했고, 실측 96건 중 25건이 최대 59/255 만큼 틀렸다.
"""
import io
import json
import os
import pathlib

import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "_tmg", str(pathlib.Path(__file__).with_name("test_theme_mobile_guards.py")))
_tmg = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_tmg)
_PARSE_COLOR_JS = _tmg._PARSE_COLOR_JS

OUT = os.environ.get("SWEEP_OUT", "pixel.json")

# 글자만 지운다. 그라디언트 글자는 배경이 글자 모양으로 클립돼 칠해지므로 그 배경도 끈다.
# 🔴 «글자만» 지운다. 여기에 `animation: none` 을 넣었더니 orb 애니메이션까지 꺼져
#    글자-있는 그림과 없는 그림 사이에 배경이 «움직였고», 그 이동분이 글리프 마스크로
#    잡혔다(실측: 12px 숫자 하나에 글리프 픽셀 164개, 다른 테마는 31개).
_HIDE_TEXT_CSS = """
*, *::before, *::after {
  color: transparent !important;
  -webkit-text-fill-color: transparent !important;
  text-shadow: none !important;
}
"""

# 요소별 «글자색 + 상자». 배경은 안 잰다 — 그림에서 읽는다.
_COLLECT_JS = "() => {\n" + _PARSE_COLOR_JS + r"""
  const opacityFrom = n => { let a=1;
    for(let x=n;x;x=x.parentElement){ const o=parseFloat(getComputedStyle(x).opacity);
      if(!isNaN(o)) a*=o; }
    return a; };
  const stops = bi => (bi.match(/rgba?\([^)]+\)/g)||[]).map(parse).filter(Boolean);
  const path = n => { const p=[]; for(let x=n;x&&x.tagName;x=x.parentElement){
    p.unshift(x.tagName.toLowerCase()+(x.className&&typeof x.className==='string'
      ? '.'+x.className.trim().split(/\s+/).join('.') : '')); if(p.length>=3) break; }
    return p.join(' > '); };
  const out=[];
  const push = (el, fillRaw, own, pseudo) => {
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    if (r.width<1 || r.height<1) return;
    if (r.y < 0 || r.x < 0) return;
    const oa = opacityFrom(el);
    if (oa <= 0.005) return;
    const fill = parse(fillRaw);
    if (!fill) return;
    const clip = (cs.backgroundClip||'')+(cs.webkitBackgroundClip||'');
    const gradText = fill.a===0 && cs.backgroundImage!=='none' && clip.includes('text');
    let fgs, kind;
    if (gradText) {
      const g = stops(cs.backgroundImage);
      if (!g.length) return;
      fgs = g.map(s => [s.r, s.g, s.b, (s.a===0?1:s.a)*oa]); kind='gradient-text';
    } else {
      if (fill.a === 0) return;
      fgs = [[fill.r, fill.g, fill.b, fill.a*oa]]; kind='solid';
    }
    const size = parseFloat(cs.fontSize), weight = parseInt(cs.fontWeight,10)||400;
    // 🔴 요소 상자가 아니라 «이 글자» 의 줄 상자를 쓴다. 상자를 쓰면 자식 요소의
    //    글자까지 마스크에 들어와 남의 글자 아래 배경을 이 요소 색으로 판정한다.
    //    Use the text node's own line boxes: an element box also contains its children's glyphs.
    let rects = [];
    if (!pseudo) {
      for (const n of el.childNodes) {
        if (n.nodeType!==3 || !n.textContent.trim()) continue;
        const rg = document.createRange(); rg.selectNodeContents(n);
        for (const b of rg.getClientRects())
          if (b.width>=1 && b.height>=1) rects.push([Math.round(b.x),Math.round(b.y),Math.round(b.width),Math.round(b.height)]);
      }
    }
    if (!rects.length) rects = [[Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]];
    out.push({sel: path(el)+(pseudo||''),
              cls: (typeof el.className==='string'?el.className:''), tag: el.tagName,
              text: own.slice(0,40), size, weight,
              large: size>=24 || (size>=18.5 && weight>=700),
              pseudo: pseudo||'', kind, opacity: +oa.toFixed(3), fgs,
              word: /[\p{L}\p{N}]/u.test(own), colorRaw: fillRaw,
              disabled: !!(el.closest('[disabled],:disabled,[aria-disabled="true"],.disabled')),
              rects: rects});
  };
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el);
    if (cs.visibility==='hidden' || cs.display==='none') continue;
    const own = Array.from(el.childNodes)
      .filter(n=>n.nodeType===3 && n.textContent.trim()).map(n=>n.textContent.trim()).join(' ');
    if (own) push(el, cs.webkitTextFillColor || cs.color, own, '');
    const tag = el.tagName;
    if (tag==='INPUT' || tag==='TEXTAREA' || tag==='SELECT') {
      const val = (el.value||'').trim();
      if (val) push(el, cs.color, val, '::value');
      const ph = (el.placeholder||'').trim();
      if (ph) push(el, getComputedStyle(el,'::placeholder').color || cs.color, ph, '::placeholder');
    }
    for (const pe of ['::before','::after']) {
      const pcs = getComputedStyle(el, pe);
      const c = pcs.content;
      if (!c || c==='none' || c==='normal' || c==='""') continue;
      const txt = c.replace(/^["']|["']$/g,'').trim();
      if (txt) push(el, pcs.color || cs.color, txt, pe);
    }
  }
  return out;
}
"""


def _lum(c):
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])


def _ratio(a, b):
    la, lb = _lum(a), _lum(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def _over(fg, bg):
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3))


def _score_pairs(rows, pairs):
    """🔴 글자-있는 그림과 «같은 위상» 의 글자-없는 그림을 짝지어 마스크를 만든다.

    이전 판은 위상 0 의 글자 그림 하나를 다른 위상의 배경 그림들과 비교했다. 그러면
    orb 가 움직인 자리가 전부 «글리프» 로 잡힌다 — 실측에서 12px 숫자 하나의 글리프
    픽셀이 164개(정상 31개)로 부풀고 배경을 엉뚱한 곳에서 읽었다.
    """
    import numpy as np  # noqa: PLC0415
    masks, bares = [], []
    for img_text, img_bare in pairs:
        A = np.asarray(img_text, dtype=np.int16)
        B = np.asarray(img_bare, dtype=np.int16)
        # 🔴 문턱이 높으면 «대비가 낮아서 잘 안 보이는 글자» 가 마스크에서 빠진다 —
        #    바로 그 글자를 찾으려고 재는 것이므로 fail-open 이다. 8 로 낮춘다.
        masks.append(np.abs(A - B).sum(axis=2) >= 8)
        bares.append(np.asarray(img_bare, dtype=np.uint8))
    H, W = masks[0].shape
    out, unmeasurable = [], 0
    for r in rows:
        boxes = []
        for x, y, w, h in r["rects"]:
            x0, y0 = max(0, x), max(0, y)
            x1, y1 = min(W, x + max(1, w)), min(H, y + max(1, h))
            if x1 > x0 and y1 > y0:
                boxes.append((x0, y0, x1, y1))
        if not boxes:
            continue
        worst, worst_bg, phase, gpx = None, None, -1, 0
        for pi, (mask, bare) in enumerate(zip(masks, bares)):
            px_list, n = [], 0
            for (x0, y0, x1, y1) in boxes:
                sub = mask[y0:y1, x0:x1]
                if not sub.any():
                    continue
                n += int(sub.sum())
                px_list.append(bare[y0:y1, x0:x1][sub].reshape(-1, 3))
            if not px_list:
                continue
            gpx = max(gpx, n)
            px = np.concatenate(px_list, axis=0)
            uniq, counts = np.unique(px, axis=0, return_counts=True)
            keep = uniq[counts / counts.sum() >= 0.02]
            if len(keep) == 0:
                keep = uniq[counts.argmax():counts.argmax() + 1]
            for bg in keep:
                bg = tuple(int(v) for v in bg)
                for fg in r["fgs"]:
                    v = _ratio(_over(fg, bg), bg)
                    if worst is None or v < worst:
                        worst, worst_bg, phase = v, bg, pi
        if worst is None:
            unmeasurable += 1
            continue
        need = 3.0 if r["large"] else 4.5
        out.append({**{k: r[k] for k in
                       ("sel", "cls", "tag", "text", "size", "weight", "large",
                        "pseudo", "kind", "opacity", "word", "colorRaw", "disabled")},
                    "need": need, "ratio": round(worst, 2),
                    "bg": f"rgb({worst_bg[0]},{worst_bg[1]},{worst_bg[2]})",
                    "phase": phase, "glyphpx": gpx})
    return out, unmeasurable


_PATHS = [("overview", "/"), ("dashboard", "/dashboard"),
          ("dash_security", "/dashboard?mode=security"), ("dash_usage", "/dashboard?mode=usage"),
          ("dash_insight", "/dashboard?mode=insight"), ("dash_repos", "/dashboard?mode=repos"),
          ("repo_detail", "/repos/owner/testrepo"), ("repo_settings", "/repos/owner/testrepo/settings"),
          ("repo_insights", "/repos/owner/testrepo/insights"), ("add_repo", "/repos/add")]
_THEMES = ["dark", "light", "pastel", "catppuccin"]

# orb 주기는 38·48·56초 alternate — 두 배 구간을 고르게 훑는다.
_PHASES_MS = [0, 19000, 38000, 57000, 76000]


def _cell(page, url, theme):
    from PIL import Image  # noqa: PLC0415
    page.goto(url)
    page.evaluate("(t) => applyTheme(t)", theme)
    page.add_style_tag(content=(
        "*,*::before,*::after{transition:none !important}"
        "*:not(.atmosphere__orb),*::before,*::after{animation:none !important}"))
    page.wait_for_timeout(450)
    page.evaluate("() => document.getAnimations().forEach(a => a.pause())")
    # 🔴 `disabled` 는 «문서에 넣은 뒤» 세팅해야 한다. 삽입 전에 세우면 무시돼
    #    글자 숨김 CSS 가 수집 중에 살아 있고, 그러면 모든 글자가 투명이라
    #    단색 요소가 전부 걸러진다(실측: 22행 → 1행).
    page.evaluate("""(css) => { const st = document.createElement('style');
        st.id = 'hide-text-probe'; st.textContent = css;
        document.head.appendChild(st); st.disabled = true; }""", _HIDE_TEXT_CSS)
    page.evaluate("""() => { for (const el of document.querySelectorAll('body *')) {
        const cs = getComputedStyle(el);
        const clip=(cs.backgroundClip||'')+(cs.webkitBackgroundClip||'');
        if (clip.includes('text')) el.dataset.clipText = '1'; } }""")
    page.wait_for_timeout(150)
    rows = page.evaluate(_COLLECT_JS)
    pairs = []
    for t in _PHASES_MS:
        page.evaluate("(t) => document.getAnimations().forEach(a => { try { a.currentTime = t; } catch(e){} })", t)
        page.wait_for_timeout(120)
        a = Image.open(io.BytesIO(page.screenshot(full_page=False))).convert("RGB")
        page.evaluate("""() => { document.getElementById('hide-text-probe').disabled = false;
            document.querySelectorAll('[data-clip-text]').forEach(
              e => e.style.setProperty('background-image','none','important')); }""")
        page.wait_for_timeout(90)
        b = Image.open(io.BytesIO(page.screenshot(full_page=False))).convert("RGB")
        page.evaluate("""() => { document.getElementById('hide-text-probe').disabled = true;
            document.querySelectorAll('[data-clip-text]').forEach(
              e => e.style.removeProperty('background-image')); }""")
        page.wait_for_timeout(60)
        pairs.append((a, b))
    rows, unmeasurable = _score_pairs(rows, pairs)
    return {"rows": rows, "unmeasurable": unmeasurable}


def test_pixel_sweep(seeded_page, base_url, seeded_analysis):
    results = {}
    seeded_page.set_viewport_size({"width": 1440, "height": 900})
    paths = list(_PATHS) + [("analysis_detail",
                             f"/repos/owner/testrepo/analyses/{seeded_analysis}")]
    thin = []
    for name, path in paths:
        for theme in _THEMES:
            cell = _cell(seeded_page, f"{base_url}{path}", theme)
            results[f"{name}|{theme}"] = cell
            if len(cell["rows"]) < 15:
                thin.append(f'{name}|{theme}={len(cell["rows"])}')
    total = sum(len(v["rows"]) for v in results.values())
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)
    # 🔴 수집이 얇으면 «통과» 가 아니라 red 다 — 화면이 숨겨진 채로 잰 것이다.
    assert not thin, f"행이 너무 적게 수집된 셀: {thin}"
    assert total >= 1200, f"총 수집 {total} — 이전 실측 1520 대비 급감, 재지 못한 것이다"
