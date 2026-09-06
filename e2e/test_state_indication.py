"""E2E 가드 — 상태를 «색만으로» 나르지 않는가 · 선택 상태가 실제로 «보이는가».

`tests/unit/ui/test_state_indication.py` 가 CSS 소스를 계산으로 본다면, 여기서는
브라우저가 실제로 무엇을 계산했는지를 본다 — 규칙이 «있어도» 특이도에 져서 적용되지
않으면 소스 가드는 초록이고 화면은 그대로다.

실측(수정 전, 4테마):

| 자리 | 실측 |
|---|---|
| 언어 메뉴 선택 항목 | 활성/비활성의 `color`·`background`·`font-weight`·`::after` 가 **전부 동일** |
| `.conn-dot` on/off | 색·투명도 말고 다른 차이 **0** |
| 토글 OFF | 트랙 1.00~1.07 · 테두리 1.13~1.28 · 손잡이 light 1.00 / pastel 1.04 |
| 정렬 글리프 `▲▼⇅` | 1.71~2.97 (`opacity` 가 곱해져 저자의 `opacity:1` 이 죽었다) |

🔴 이 파일은 새 파일이다 — `test_theme_mobile_guards.py` 는 이미 1200줄이 넘어,
「상태 표시」라는 다른 축을 거기 얹으면 무엇이 무엇을 지키는지 읽히지 않는다.
"""
import pytest

_THEMES = ["dark", "light", "pastel", "catppuccin"]

_CONTRAST_HELPERS = r"""
  const parse = c => { c=(c||'').trim(); if(!c) return null;
    const h=c.match(/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/);
    if (h) { let x=h[1]; if(x.length===3) x=x.split('').map(d=>d+d).join('');
      return {r:parseInt(x.slice(0,2),16), g:parseInt(x.slice(2,4),16),
              b:parseInt(x.slice(4,6),16), a:1}; }
    const m=c.match(/[-\d.]+(?:e[-+]?\d+)?/g); if(!m) return null;
    if (/^color\(/.test(c)) {
      if (!/^color\(\s*srgb[\s(]/.test(c)) return null;
      const n = /\//.test(c) && m.length>=4 ? m.slice(-4) : m.slice(-3).concat([1]);
      return {r:+n[0]*255, g:+n[1]*255, b:+n[2]*255, a:+n[3]};
    }
    return {r:+m[0],g:+m[1],b:+m[2],a:m.length>3?+m[3]:1}; };
  const over=(f,b)=>{const a=f.a+b.a*(1-f.a); if(!a) return {r:0,g:0,b:0,a:0};
    return {r:(f.r*f.a+b.r*b.a*(1-f.a))/a,g:(f.g*f.a+b.g*b.a*(1-f.a))/a,
            b:(f.b*f.a+b.b*b.a*(1-f.a))/a,a};};
  const lum=c=>{const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);};
    return 0.2126*f(c.r)+0.7152*f(c.g)+0.0722*f(c.b);};
  const ratio=(x,y)=>{const a=lum(x),b=lum(y);
    return (Math.max(a,b)+0.05)/(Math.min(a,b)+0.05);};
  const ground=n=>{let acc={r:255,g:255,b:255,a:1};const ch=[];
    for(let x=n;x;x=x.parentElement) ch.push(x);
    for(let i=ch.length-1;i>=0;i--){const cs=getComputedStyle(ch[i]);
      const c=parse(cs.backgroundColor); if(c&&c.a>0) acc=over(c,acc);
      const bi=cs.backgroundImage;
      if(bi&&bi!=='none'){(bi.match(/rgba?\([^)]+\)|#[0-9a-fA-F]{3,8}/g)||[])
        .map(parse).filter(Boolean).forEach(s=>{if(s.a>0) acc=over(s,acc);});}}
    return acc;};
"""

_NON_TEXT = 3.0


def _open_menus(page) -> None:
    page.evaluate("""() => {
        document.querySelectorAll('#themeSwitcher, #langSwitcher')
          .forEach(e => e.classList.add('open')); }""")
    page.wait_for_timeout(200)


def _reveal(page) -> None:
    """`.reveal` 을 교차관측으로 드러내고, 유한 애니메이션이 끝나기를 기다린다."""
    page.evaluate("""() => new Promise(r => {
        let y = 0;
        const step = () => { window.scrollTo(0, y); y += window.innerHeight * 0.8;
          if (y < document.body.scrollHeight + window.innerHeight) setTimeout(step, 80);
          else { window.scrollTo(0, 0); setTimeout(r, 300); } };
        step(); })""")
    page.evaluate("""() => new Promise(r => {
        const a = document.getAnimations ? document.getAnimations() : [];
        const fin = a.filter(x => { try { return x.effect &&
            (x.effect.getComputedTiming().iterations || 1) !== Infinity; }
            catch (e) { return false; } }).map(x => x.finished.catch(() => {}));
        Promise.all(fin).then(r); setTimeout(r, 2500); })""")
    page.wait_for_timeout(250)


def _theme(page, base_url, path, theme):
    page.set_viewport_size({"width": 1440, "height": 2000})
    page.goto(f"{base_url}{path}")
    page.evaluate("(t) => applyTheme(t)", theme)
    page.add_style_tag(content="*,*::before,*::after{transition:none !important}")
    page.wait_for_timeout(350)


# ── A. 메뉴 선택 상태 — «보이는가» + 보조기술에 노출되는가 ──────────────────

_MENU_JS = r"""
(sel) => [...document.querySelectorAll(sel)].map(el => {
  const cs = getComputedStyle(el);
  const after = getComputedStyle(el, '::after');
  return {active: el.classList.contains('active'),
          sig: [cs.color, cs.backgroundColor, cs.fontWeight,
                cs.textDecorationLine, after.content].join('|'),
          ariaChecked: el.getAttribute('aria-checked'),
          role: el.getAttribute('role')};
})
"""


@pytest.mark.parametrize("theme", _THEMES)
@pytest.mark.parametrize("sel", [".lang-option", ".theme-option"])
def test_menu_selection_is_visible_and_announced(seeded_page, base_url, theme, sel):
    """🔴 선택된 항목이 나머지와 «달라 보여야» 하고, `aria-checked` 로 알려져야 한다.

    실측(수정 전): `.lang-option` 은 `.active` 규칙이 **아예 없어서** 네 테마 전부
    활성/비활성의 계산 스타일이 완전히 같았다 — 색이 정보를 나르는 것조차 아니라
    아무것도 나르지 않았다(WCAG 1.3.1 / 4.1.2).
    """
    _theme(seeded_page, base_url, "/repos/owner/testrepo", theme)
    _open_menus(seeded_page)
    rows = seeded_page.evaluate(_MENU_JS, sel)

    assert len(rows) >= 3, (
        f"[{theme}] `{sel}` 를 {len(rows)}개만 찾았다 — 재지 못한 것이지 통과가 아니다")
    active = [r for r in rows if r["active"]]
    assert len(active) == 1, (
        f"[{theme}] `{sel}` 의 활성 항목이 {len(active)}개다 — 정확히 1개여야 한다")

    others = [r for r in rows if not r["active"]]
    same = [r for r in others if r["sig"] == active[0]["sig"]]
    assert not same, (
        f"[{theme}] `{sel}` 의 선택 항목이 나머지와 «똑같이» 그려진다 — "
        f"선택 상태가 화면에 전달되지 않는다.\n  활성: {active[0]['sig']}"
    )

    assert active[0]["ariaChecked"] == "true", (
        f"[{theme}] `{sel}` 의 선택 항목에 `aria-checked=\"true\"` 가 없다 "
        f"— {active[0]['ariaChecked']!r}")
    assert all(r["ariaChecked"] == "false" for r in others), (
        f"[{theme}] `{sel}` 의 비선택 항목이 `aria-checked=\"false\"` 가 아니다")
    assert all(r["role"] == "menuitemradio" for r in rows), (
        f"[{theme}] `{sel}` 의 role 이 `menuitemradio` 가 아니다 — "
        "`menuitem` 은 선택 상태를 표현할 수 없다")


def test_changing_the_theme_moves_aria_checked(seeded_page, base_url):
    """🔴 테마를 바꾸면 `aria-checked` 도 «따라와야» 한다.

    마크업에만 넣으면 첫 렌더 이후로 굳는다 — 그러면 보조기술에는 영영 옛 값이 보인다.
    """
    _theme(seeded_page, base_url, "/repos/owner/testrepo", "dark")
    _open_menus(seeded_page)
    before = seeded_page.evaluate(
        "() => [...document.querySelectorAll('.theme-option')]"
        ".map(e => e.getAttribute('aria-checked')).join(',')")
    seeded_page.evaluate("() => applyTheme('pastel')")
    seeded_page.wait_for_timeout(250)
    after = seeded_page.evaluate(
        "() => [...document.querySelectorAll('.theme-option')]"
        ".map(e => e.getAttribute('aria-checked')).join(',')")
    checked = seeded_page.evaluate(
        "() => document.querySelector('.theme-option[data-theme-target=\"pastel\"]')"
        ".getAttribute('aria-checked')")
    assert before != after, (
        f"테마를 바꿔도 `aria-checked` 가 그대로다 — {before!r}")
    assert checked == "true", f"고른 테마가 `aria-checked=\"true\"` 가 아니다 — {checked!r}"


# ── B. conn-dot — 상태가 색 말고 무엇으로 갈리는가 ─────────────────────────

_CONN_JS = r"""
() => {
  const pick = st => {
    const el = document.querySelector('.conn-dot');
    if (!el) return null;
    el.classList.remove('is-on', 'is-off');
    el.classList.add(st);
    const cs = getComputedStyle(el);
    return {bg: cs.backgroundColor, opacity: cs.opacity,
            border: cs.borderTopWidth + ' ' + cs.borderTopStyle,
            radius: cs.borderRadius, w: cs.width, h: cs.height,
            aria: el.getAttribute('aria-label'), role: el.getAttribute('role')};
  };
  const el = document.querySelector('.conn-dot');
  if (!el) return null;
  const orig = el.className;
  const on = pick('is-on'), off = pick('is-off');
  el.className = orig;
  // 점은 장식이고, 상태는 바로 옆 «글자» 가 나른다
  const sib = el.nextElementSibling;
  return {on, off,
          hidden: el.getAttribute('aria-hidden'),
          siblingText: sib ? (sib.textContent || '').trim() : null,
          siblingClass: sib ? String(sib.className || '') : null};
}
"""


@pytest.mark.parametrize("theme", _THEMES)
def test_conn_dot_states_differ_by_more_than_color(seeded_page, base_url, theme):
    """🔴 채널 «설정됨/아님» 이 색 하나로만 갈리면 안 된다 (WCAG 1.4.1, Level A).

    실측(수정 전): 두 상태의 크기·모양·테두리·글자·`aria-label`·`role` 이 전부 같고
    차이는 `background` 와 `opacity` 뿐이었다.
    """
    _theme(seeded_page, base_url, "/repos/owner/testrepo/settings", theme)
    res = seeded_page.evaluate(_CONN_JS)
    assert res and res["on"] and res["off"], (
        f"[{theme}] `.conn-dot` 를 찾지 못했다 — 재지 못한 것이지 통과가 아니다")
    on, off = res["on"], res["off"]
    non_color = [k for k in ("border", "radius", "w", "h")
                 if on[k] != off[k]]
    assert non_color, (
        f"[{theme}] `.conn-dot` 의 on/off 가 색으로만 갈린다 — "
        f"on={on} off={off}")
    # 🔴 상태는 «글자» 가 나른다. 점 자신은 장식이어야 중복 낭독이 없다.
    assert res["hidden"] == "true", (
        f"[{theme}] `.conn-dot` 이 `aria-hidden` 이 아니다 — {res['hidden']!r}")
    assert res["siblingClass"] and "sr-only" in res["siblingClass"], (
        f"[{theme}] `.conn-dot` 옆에 `.sr-only` 형제가 없다 — "
        f"{res['siblingClass']!r}")
    assert res["siblingText"], (
        f"[{theme}] `.conn-dot` 옆의 `.sr-only` 가 비어 있다 — "
        "상태 글자가 렌더되지 않았다")


# ── C. 토글 OFF — 스위치가 «있다는 사실» 이 보이는가 ────────────────────────

_TOGGLE_JS = r"""
() => {
""" + _CONTRAST_HELPERS + r"""
  const sw = document.querySelector('.toggle-switch');
  if (!sw) return null;
  const input = sw.querySelector('input[type="checkbox"]');
  const track = sw.querySelector('.toggle-track');
  if (!track || !input) return null;
  const was = input.checked;
  input.checked = false;
  const t = getComputedStyle(track);
  const knob = getComputedStyle(track, '::after');
  const g = ground(sw.parentElement);
  const tc = parse(t.backgroundColor);
  const tp = tc ? over(tc, g) : g;
  const best = (colorStr, widthStr, bg) => {
    const c = parse(colorStr);
    if (!c || c.a <= 0) return 0;
    if (widthStr !== null && (parseFloat(widthStr) || 0) <= 0) return 0;
    return ratio(over(c, bg), bg);
  };
  const res = {
    track: ratio(tp, g),
    trackBorder: best(t.borderTopColor, t.borderTopWidth, g),
    knob: best(knob.backgroundColor, null, tp),
    knobBorder: best(knob.borderTopColor, knob.borderTopWidth, tp),
  };
  input.checked = was;
  res.best = Math.max(res.track, res.trackBorder, res.knob, res.knobBorder);
  return res;
}
"""


@pytest.mark.parametrize("theme", _THEMES)
def test_toggle_off_state_is_visible(seeded_page, base_url, theme):
    """🔴 꺼진 스위치도 카드 위에서 보여야 한다 (WCAG 1.4.11).

    실측(수정 전): 트랙 1.00~1.07 · 테두리 1.13~1.28, light·pastel 은 흰 손잡이가
    흰 트랙 위라 1.00 / 1.04 — 스위치가 «있다는 사실» 조차 전달되지 않았다.
    """
    _theme(seeded_page, base_url, "/repos/owner/testrepo/settings", theme)
    res = seeded_page.evaluate(_TOGGLE_JS)
    assert res, f"[{theme}] `.toggle-switch` 를 찾지 못했다 — 재지 못한 것이지 통과가 아니다"
    assert res["best"] >= _NON_TEXT, (
        f"[{theme}] 꺼진 스위치가 안 보인다 — 트랙 {res['track']:.2f} · "
        f"트랙테두리 {res['trackBorder']:.2f} · 손잡이 {res['knob']:.2f} · "
        f"손잡이테두리 {res['knobBorder']:.2f} (최댓값 {res['best']:.2f} < {_NON_TEXT})"
    )


# ── C-2. 토글 포커스 — 입력이 0×0 이라 «계산» 으로는 통과처럼 보인다 ────────

def _clip_bytes(page, sel: str) -> bytes:
    r = page.evaluate(
        "(s) => { const b = document.querySelector(s).getBoundingClientRect();"
        " return {x: b.left - 16, y: b.top - 16, width: b.width + 32,"
        "         height: b.height + 32}; }", sel)
    return page.screenshot(clip=r)


def test_toggle_focus_actually_paints(seeded_page, base_url):
    """🔴 토글에 포커스가 가면 «픽셀이 바뀌어야» 한다 (WCAG 2.4.7, AA).

    실측(수정 전): `document.activeElement` 가 그 입력이고 `:focus-visible` 도 참인데
    **0px** 이 바뀌었다 — 같은 자리에 빨강 링을 강제하면 618px 이 바뀌므로 계기 문제가
    아니다. 입력이 `width:0;height:0;opacity:0` 이라 일반 `input:focus` 규칙의 글로가
    그릴 자리가 없다. 링을 «보이는 형제» 트랙에 걸어 0 → 362px.

    🔴 이 축은 계산으로 못 잡는다. `getComputedStyle(input)` 은 box-shadow 를 «갖고
    있다» 고 답하고, e2e 포커스 감사는 6px 미만 요소를 아예 건너뛴다.
    """
    page = seeded_page
    page.set_viewport_size({"width": 1440, "height": 2400})
    page.goto(f"{base_url}/repos/owner/testrepo/settings")
    page.evaluate("() => { document.body.setAttribute('data-settings-mode','advanced');"
                  " document.querySelectorAll('.is-hidden')"
                  ".forEach(e => e.classList.remove('is-hidden')); }")
    page.add_style_tag(content="*,*::before,*::after{transition:none !important}"
                               ".atmosphere__orb{display:none !important}")
    page.wait_for_timeout(700)
    sel = ".toggle-switch .toggle-track"
    visible = page.evaluate(
        "(s) => { const e = document.querySelector(s); if (!e) return false;"
        " e.scrollIntoView({block: 'center'});"
        " const b = e.getBoundingClientRect();"
        " return b.width >= 6 && b.height >= 6 && b.top >= 0"
        "        && b.bottom <= window.innerHeight; }", sel)
    assert visible, "토글 트랙을 화면 안에서 찾지 못했다 — 재지 못한 것이지 통과가 아니다"
    page.wait_for_timeout(300)

    base = _clip_bytes(page, sel)
    # 🔴 자기검사 — 계기가 링을 «볼 수 있는가». 0 이면 앱이 아니라 계기가 고장난 것이다.
    handle = page.add_style_tag(
        content=f"{sel}{{outline:3px solid #ff0000 !important;outline-offset:2px !important}}")
    page.wait_for_timeout(300)
    assert _clip_bytes(page, sel) != base, (
        "자기검사 실패 — 트랙에 빨강 링을 강제해도 픽셀이 안 바뀐다. 계기가 고장났다")
    page.evaluate("(el) => el.remove()", handle)
    page.wait_for_timeout(300)
    base = _clip_bytes(page, sel)

    page.keyboard.press("Tab")          # 키보드 양태를 세운다
    page.evaluate("() => document.querySelector("
                  "'.toggle-switch input[type=checkbox]').focus()")
    page.wait_for_timeout(350)
    focused = page.evaluate(
        "() => document.querySelector('.toggle-switch input[type=checkbox]')"
        ".matches(':focus-visible')")
    assert focused, "토글 입력이 `:focus-visible` 이 아니다 — 이 시험의 전제가 깨졌다"
    assert _clip_bytes(page, sel) != base, (
        "토글에 포커스가 가도 «픽셀이 하나도» 바뀌지 않는다 — 표시가 없다 "
        "(WCAG 2.4.7 Level AA). 입력이 0×0 이므로 링은 보이는 형제에 걸어야 한다"
    )


# ── D. 정렬 방향 글리프 — 실제로 «칠해지는» 값으로 잰다 ────────────────────

_SORT_JS = r"""
() => {
""" + _CONTRAST_HELPERS + r"""
  const out = [];
  document.querySelectorAll('.sort-icon').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return;
    const ps = getComputedStyle(el, '::after');
    const content = ps.content;
    if (!content || content === 'none' || content === 'normal') return;
    // 🔴 opacity 는 곱해진다 — 의사요소와 조상 사슬을 «다» 곱해야 실제 값이다.
    let op = parseFloat(ps.opacity); if (isNaN(op)) op = 1;
    for (let x = el; x; x = x.parentElement) {
      const o = parseFloat(getComputedStyle(x).opacity); if (!isNaN(o)) op *= o; }
    const fg = parse(ps.color); if (!fg) return;
    const g = ground(el);
    out.push({content, opacity: +op.toFixed(3),
              ratio: +ratio(over({...fg, a: fg.a * op}, g), g).toFixed(2),
              th: (el.parentElement ? el.parentElement.className : '')});
  });
  return out;
}
"""


@pytest.mark.parametrize("theme", _THEMES)
def test_sort_direction_glyph_meets_non_text_contrast(seeded_page, base_url, theme):
    """🔴 정렬 방향은 «상태» 다 — 그 글리프가 3:1 을 넘어야 한다.

    실측(수정 전): 1.71~2.97. 원인은 `.sort-icon { opacity: .5 }` 가
    `::after { opacity: 1 }` 과 **곱해져** 저자의 되돌림이 작동하지 않은 것.
    """
    _theme(seeded_page, base_url, "/repos/owner/testrepo", theme)
    # 🔴 표는 `.reveal` 안에 있다 — 드러내지 않으면 조상 opacity 가 0 이라
    #    「전부 1.00」 이라는 무의미한 값이 나온다(실측으로 한 번 그랬다).
    _reveal(seeded_page)
    rows = seeded_page.evaluate(_SORT_JS)
    # 현재 정렬 가능한 열은 2개(`created_at`·`score`). 하나라도 줄면 이 축이 조용히
    # 좁아진 것이므로 red 로 알린다.
    assert len(rows) >= 2, (
        f"[{theme}] 정렬 글리프를 {len(rows)}개만 찾았다 — 재지 못한 것이지 통과가 아니다")
    faded = [r for r in rows if r["opacity"] < 0.5]
    assert not faded, (
        f"[{theme}] 정렬 글리프가 opacity {faded[0]['opacity']} 로 잡혔다 — "
        "`.reveal` 이 드러나지 않은 채로 잰 것이다(재지 못한 것이지 통과가 아니다)")
    bad = [r for r in rows if r["ratio"] < _NON_TEXT]
    assert not bad, (
        f"[{theme}] 정렬 방향 글리프 {len(bad)}건이 3:1 미만 (관측 {len(rows)}건):\n  "
        + "\n  ".join(f"{r['content']} ratio={r['ratio']} opacity={r['opacity']} "
                      f"th={r['th'][:30]!r}" for r in bad[:6])
    )
