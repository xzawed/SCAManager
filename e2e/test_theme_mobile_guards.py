"""E2E 회귀 가드 — catppuccin 토큰 누락 + WCAG 2.5.5 모바일 클릭 영역.

7-에이전트 정합성 검증 (2026-05-02) P1 #5 후속.
도입 배경:
  - cleanup PR #169 — catppuccin(구 claude-dark) 테마가 settings 페이지 토큰 8종 (`--save-btn-bg`,
    `--grad-gate/merge/notify/hook`, `--title-gradient`, `--btn-gate-active-*`,
    `--hint-*`, `--hook-btn-*`) 미정의로 카드 헤더가 흰색/투명 깨졌던 사고.
  - UI 감사 Step A — WCAG 2.5.5 Target Size — 모바일 (≤768px) 인터랙티브 요소
    `.btn`/`.btn--sm`/`.nav-hamburger`/`.nav-logout-btn` min-height ≥40~44px 의무.
  - 2026-05-11 UI 리디자인: claude-dark → catppuccin, glass → pastel 로 테마 명칭 변경.

본 테스트는 두 영역의 회귀를 e2e 레벨에서 차단한다.
"""
# E2E regression guards — catppuccin token regression + WCAG 2.5.5 mobile click area.

import pytest


# ── A. catppuccin 토큰 회귀 가드 (cleanup PR #169 사고 차단) ─────────────────


def _set_catppuccin(page) -> None:
    """헬퍼 — catppuccin 테마로 전환 후 적용 확인.

    드롭다운 → catppuccin 옵션 클릭 → body[data-theme=catppuccin] 단언.
    (2026-05-11 UI 리디자인 전 이름: claude-dark)
    """
    # Helper — switch to catppuccin theme and assert it applied (formerly claude-dark).
    page.click("#themeToggle")
    page.wait_for_selector(".theme-switcher.open", timeout=2000)
    # 🔴 항목 속성은 `data-theme-target` (#639) — 적용된 테마를 읽는 body[data-theme] 와 별개 축
    # Entry attribute is `data-theme-target` (#639); the applied theme is body[data-theme].
    page.click('.theme-option[data-theme-target="catppuccin"]')
    assert page.get_attribute("body", "data-theme") == "catppuccin"


def test_catppuccin_settings_tokens_defined(seeded_page, base_url):
    """catppuccin 테마에서 settings 페이지의 8 토큰 모두 정의되어 있어야 한다.

    회귀 사례: cleanup PR #169 이전 settings 페이지가 catppuccin(구 claude-dark) 토큰 미정의로
    `var(--save-btn-bg)` 등이 invalid → 카드 헤더 흰색 / 저장 버튼 투명 깨짐.
    """
    # Regression guard: cleanup PR #169 — catppuccin settings tokens were missing,
    # causing card headers / save button to render blank.
    seeded_page.goto(f"{base_url}/repos/owner/testrepo/settings")
    _set_catppuccin(seeded_page)

    # 토큰이 모두 정의되어 있어야 함 (빈 문자열이면 미정의 = invalid var())
    # All tokens must be defined (empty value = undefined = invalid).
    #
    # 🔴 이 목록은 «settings 가 실제로 읽는» 토큰만 담는다. `--save-btn-bg` 는 소비자가
    #    0곳인데 이 단언이 존재를 계약으로 붙들고 있어서 죽은 채로 남아 있었다(#1639 W19).
    #    되살리면 `tests/unit/ui/test_no_dead_design_tokens.py` 가 red 가 된다.
    #    같은 축의 단위 시험 3건을 고쳤는데 이 e2e 만 남아 CI 에서 red 가 났다 —
    #    「존재를 요구하는 계약」은 단위와 e2e **두 곳**에 흩어져 있다.
    required = [
        "--grad-gate",
        "--grad-merge",
        "--grad-notify",
        "--grad-hook",
        "--title-gradient",
        "--hint-bg",
        "--hook-btn-bg",
    ]
    # catppuccin 토큰은 body[data-theme="catppuccin"] 스코프 → document.body 에서 조회
    # catppuccin tokens scoped to body[data-theme=catppuccin] — query document.body.
    for token in required:
        value = seeded_page.evaluate(
            f"getComputedStyle(document.body).getPropertyValue('{token}').trim()"
        )
        assert value, f"catppuccin 테마에 {token} 미정의 (settings 페이지 깨짐 위험)"


def test_catppuccin_dashboard_renders_without_token_failure(page, base_url):
    """catppuccin 테마 적용 후 dashboard 페이지가 정상 렌더되고 body 배경이 투명이 아니어야 한다.

    회귀 사례: --bg-app 등 핵심 토큰 미정의 시 body 배경이 transparent → 시각 깨짐.
    """
    # Regression guard: missing --bg-app etc. would render body bg transparent.
    page.goto(f"{base_url}/dashboard")
    _set_catppuccin(page)

    # body 배경이 transparent / rgba(0,0,0,0) 가 아니어야 함
    # body bg must not be transparent / rgba(0,0,0,0).
    bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
    assert bg not in ("rgba(0, 0, 0, 0)", "transparent"), (
        f"catppuccin dashboard body 배경 투명 — 토큰 누락 의심: {bg}"
    )


def test_catppuccin_grade_aliases_defined(page, base_url):
    """catppuccin 테마에서 등급 색 alias (--grade-a/b/c/d/f) 가 모두 정의되어 있어야 한다.

    회귀 사례: 등급 색 미정의 시 overview 카드의 등급 뱃지가 색상 없이 렌더.
    """
    # Regression guard: missing --grade-* aliases would render overview grade badges colorless.
    page.goto(base_url)
    _set_catppuccin(page)

    # 등급 alias 도 body[data-theme="catppuccin"] 스코프
    # Grade aliases scoped to body[data-theme=catppuccin] too.
    for grade in ["a", "b", "c", "d", "f"]:
        token = f"--grade-{grade}"
        value = page.evaluate(
            f"getComputedStyle(document.body).getPropertyValue('{token}').trim()"
        )
        assert value, f"catppuccin 테마에 {token} 미정의"


# ── B. WCAG 2.5.5 모바일 클릭 영역 회귀 가드 (UI 감사 Step A) ─────────────────

_MOBILE_VIEWPORT = {"width": 375, "height": 812}  # iPhone X/11/12/13 sm
_DESKTOP_VIEWPORT = {"width": 1024, "height": 768}


def _min_height_px(page, selector: str) -> float:
    """헬퍼 — 셀렉터의 computed min-height 를 px 단위 float 반환.

    미존재 셀렉터 / 'auto'·'normal' 등 비px 값 = 둘 다 fail-fast (silent skip·0.0 금지, 사이클 158 회고 P2).
    """
    # Helper — return computed min-height in px; missing selector OR non-px value → fail-fast (no silent 0.0).
    # Playwright page.evaluate 는 단일 expression 또는 arrow function 만 허용
    # Playwright page.evaluate accepts a single expression OR an arrow function.
    raw = page.evaluate(
        f"() => {{"
        f"  const el = document.querySelector({selector!r});"
        f"  if (!el) return null;"
        f"  return getComputedStyle(el).minHeight;"
        f"}}"
    )
    if raw is None:
        # fail-fast — 셀렉터 미존재 = 페이지 구조 회귀 (silent skip 금지, 사이클 157 #9).
        # docstring 의 fail-fast 의도 정합. 호출처(.btn--sm) 는 overview 에 정적 존재 보장(L178).
        # Missing selector = structural regression — fail rather than silently skip.
        pytest.fail(f"셀렉터 '{selector}' 미존재 — 페이지 구조 회귀 (fail-fast)")
    if not raw.endswith("px"):
        # 비px(auto/normal) = WCAG 타깃 CSS 룰 미적용 회귀 — silent 0.0 대신 raw 값과 함께 fail-fast.
        # Non-px (auto/normal) = CSS rule not applied (regression) — fail-fast with raw value.
        pytest.fail(f"셀렉터 '{selector}' min-height='{raw}' (비px) — CSS 룰 미적용 회귀 (fail-fast)")
    return float(raw[:-2])


def _measure_injected_btn_min_height(page, btn_class: str) -> float:
    """헬퍼 — `<a class="{btn_class}">` 를 nav 외부에 동적 주입해 computed min-height 측정.

    overview 페이지가 `.btn--sm` 만 가지므로 정적 셀렉터로는 base `.btn` 규칙 측정 불가.
    DOM 주입 방식이 매체 쿼리 + 클래스 룰을 모두 적용한 결과를 안정적으로 노출한다.
    비px 값 = .btn CSS 룰 미적용 회귀 → fail-fast (silent 0.0 금지 — `_min_height_px` 와 일관, #740).
    """
    # Helper — inject a stub <a> with the desired class to measure CSS @media + class rule output.
    raw = page.evaluate(
        "(cls) => {"
        "  const el = document.createElement('a');"
        "  el.className = cls;"
        "  el.href = '#';"
        "  el.textContent = 'probe';"
        "  document.body.appendChild(el);"
        "  const h = getComputedStyle(el).minHeight;"
        "  el.remove();"
        "  return h;"
        "}",
        btn_class,
    )
    if not raw or not raw.endswith("px"):
        # 주입 요소 min-height 가 비px = .btn CSS 룰 미적용 회귀 — silent 0.0 대신 fail-fast (#740 일관).
        # Injected element non-px min-height = .btn CSS rule not applied — fail-fast (consistent with #740).
        pytest.fail(f"주입 '{btn_class}' min-height='{raw}' (비px) — .btn CSS 룰 미적용 회귀 (fail-fast)")
    return float(raw[:-2])


def test_mobile_btn_min_height_44(page, base_url):
    """모바일 viewport (375px) 에서 .btn 의 min-height 가 44px 이상이어야 한다 (WCAG 2.5.5).

    회귀 사례: @media (max-width: 768px) 분기에서 .btn min-height: 44px 누락 시
    iOS 사용자 클릭 영역 작아 mis-tap 빈발.
    """
    # WCAG 2.5.5 Target Size — .btn must be ≥44px on mobile.
    page.set_viewport_size(_MOBILE_VIEWPORT)
    page.goto(base_url)
    height = _measure_injected_btn_min_height(page, "btn btn-primary")
    assert height >= 44, f"모바일 .btn min-height = {height}px (≥44px 필요 — WCAG 2.5.5)"


def test_mobile_btn_sm_min_height_40(page, base_url):
    """모바일 viewport 에서 .btn--sm 의 min-height 가 40px 이상이어야 한다.

    .btn--sm 은 보조 액션 — WCAG 권장 최소(40px) 적용.
    """
    # WCAG 2.5.5 — .btn--sm minimum 40px on mobile (reduced for secondary actions).
    page.set_viewport_size(_MOBILE_VIEWPORT)
    page.goto(base_url)
    # overview 의 실제 .btn--sm 셀렉터 사용 — 정적 존재 보장
    # Use real .btn--sm selector on overview — guaranteed to exist.
    height = _min_height_px(page, "a.btn--sm")
    assert height >= 40, f"모바일 .btn--sm min-height = {height}px (≥40px 필요)"


def test_mobile_nav_hamburger_44x44(page, base_url):
    """모바일 viewport 에서 .nav-hamburger 가 ≥44x44 영역이어야 한다.

    회귀 사례: nav 햄버거 버튼이 모바일에서 24x24 정도면 mis-tap 빈발.
    """
    # WCAG 2.5.5 — .nav-hamburger must be ≥44x44 on mobile.
    page.set_viewport_size(_MOBILE_VIEWPORT)
    page.goto(base_url)
    raw_height = page.evaluate(
        "() => {"
        "  const el = document.querySelector('.nav-hamburger');"
        "  if (!el) return null;"
        "  const cs = getComputedStyle(el);"
        "  return [cs.minWidth, cs.minHeight];"
        "}"
    )
    if raw_height is None:
        # fail-fast — .nav-hamburger 는 e2e conftest 가 current_user 를 override(get_current_user)하므로
        # 항상 렌더(base.html:635 `{% if current_user %}`). 미존재 = 진짜 회귀 (사이클 157 #9).
        # The e2e conftest overrides get_current_user, so .nav-hamburger always renders; absence = regression.
        pytest.fail(".nav-hamburger 셀렉터 미존재 — current_user 인증 시 항상 렌더 (fail-fast)")
    min_w_str, min_h_str = raw_height
    assert min_w_str.endswith("px") and min_h_str.endswith("px"), (
        f".nav-hamburger min-w/h px 단위 아님 — minWidth={min_w_str}, minHeight={min_h_str}"
    )
    min_w, min_h = float(min_w_str[:-2]), float(min_h_str[:-2])
    assert min_w >= 44, f".nav-hamburger min-width = {min_w}px (≥44px 필요)"
    assert min_h >= 44, f".nav-hamburger min-height = {min_h}px (≥44px 필요)"


def test_desktop_btn_no_mobile_min_height(page, base_url):
    """데스크탑 viewport (1024px) 에서 .btn min-height 가 44px 미만이어야 한다.

    회귀 가드: 모바일 분기 (@media max-width: 768px) 가 데스크탑에 누수되지 않는지 확인.
    @media 가 잘못 작성되어 데스크탑에도 44px 가 적용되면 데스크탑 UI 가 어색해짐.
    """
    # Regression guard: ensure mobile @media rules don't leak into desktop viewport.
    page.set_viewport_size(_DESKTOP_VIEWPORT)
    page.goto(base_url)
    # DOM 주입 .btn 으로 데스크탑 분기에서 min-height 가 44px 미만임을 확인
    # Use DOM-injected .btn to verify desktop has no mobile-only min-height.
    height = _measure_injected_btn_min_height(page, "btn btn-primary")
    assert height < 44, (
        f"데스크탑 .btn min-height = {height}px — 모바일 분기 누수 의심"
        " (@media max-width:768px 가 데스크탑 적용 중)"
    )


# ── D. UI 감사 후속 — 가로 넘침 · accent 대비 · 테마 속성 일치 ─────────────
# UI audit follow-up: horizontal overflow, on-accent contrast, theme attribute agreement.

_NARROW_VIEWPORTS = [(320, 640), (375, 667)]

# 🔴 색 파서를 따로 둔다 — `color-mix()` 는 `color(srgb r g b)` 로 직렬화되고 그 성분은
#    0~1 실수다. `rgb()` 의 0~255 와 같은 자로 읽으면 거의 «검정» 으로 재서, 실제로는
#    통과하는 색을 미달로, 미달인 색을 통과로 보고할 수 있다. 이 리포는
#    `settings.html::--text-desc` 가 `color-mix` 를 쓴다.
# color-mix() serializes as `color(srgb r g b)` whose components are 0..1, not 0..255.
_PARSE_COLOR_JS = r"""
  const parse = c => { c=(c||'').trim(); if(!c) return null;
  // 토큰 값(`getPropertyValue`)은 저자가 쓴 «16진» 그대로 온다 — computed 색만 다루면
  // 토큰과 대조할 수 없다. 실제로 이 갈래가 없어 관측 0건이 났었다.
  // Token values come back as authored hex; without this branch nothing matches.
  const h=c.match(/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/);
  if (h) { let x=h[1]; if(x.length===3) x=x.split('').map(d=>d+d).join('');
    return {r:parseInt(x.slice(0,2),16), g:parseInt(x.slice(2,4),16),
            b:parseInt(x.slice(4,6),16), a:1}; }
  const m=c.match(/[-\d.]+(?:e[-+]?\d+)?/g); if(!m) return null;
  if (/^color\(/.test(c)) {
    if (!/^color\(\s*srgb[\s(]/.test(c)) return null;   // display-p3 등은 못 잰다 → null
    const n = /\//.test(c) && m.length>=4 ? m.slice(-4) : m.slice(-3).concat([1]);
    return {r:+n[0]*255, g:+n[1]*255, b:+n[2]*255, a:+n[3]};
  }
  return {r:+m[0],g:+m[1],b:+m[2],a:m.length>3?+m[3]:1}; };
"""

# 대비 계산 — 알파를 조상 위로 합성한 «칠해지는» 색으로 잰다.
# Contrast helper: composite alpha up the ancestor chain to the painted color.
_CONTRAST_JS = r"""
(sel) => {
""" + _PARSE_COLOR_JS + r"""
  const el = document.querySelector(sel);
  if (!el) return {found: false};
  const over = (f,b) => { const a=f.a+b.a*(1-f.a); if(!a) return {r:0,g:0,b:0,a:0};
    return {r:(f.r*f.a+b.r*b.a*(1-f.a))/a, g:(f.g*f.a+b.g*b.a*(1-f.a))/a,
            b:(f.b*f.a+b.b*b.a*(1-f.a))/a, a}; };
  const paintedBg = n => { let acc={r:255,g:255,b:255,a:1}; const chain=[];
    for(let x=n;x;x=x.parentElement) chain.push(x);
    for(let i=chain.length-1;i>=0;i--){ const cs=getComputedStyle(chain[i]);
      const c=parse(cs.backgroundColor); if(c&&c.a>0) acc=over(c,acc);
      const bi=cs.backgroundImage;
      if(bi&&bi!=='none'){ const g=(bi.match(/rgba?\([^)]+\)/g)||[]).map(parse).filter(Boolean);
        if(g.length) acc=over({...g[0],a:1},acc); }        // 그라디언트 첫 정지점으로 근사
    } return acc; };
  const lum = c => { const f=v=>{v/=255; return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);};
    return 0.2126*f(c.r)+0.7152*f(c.g)+0.0722*f(c.b); };
  const cs = getComputedStyle(el);
  const bg = paintedBg(el);
  const fg = over(parse(cs.webkitTextFillColor || cs.color), bg);
  const l1 = lum(fg), l2 = lum(bg);
  return {found: true, ratio: (Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05),
          size: parseFloat(cs.fontSize), color: cs.color,
          // 🔴 이 계기는 background-color 만 읽는다. 그라디언트가 칠해지면 잰 값이
          //    실제와 다르므로, 조용한 초록 대신 그 사실을 돌려보내 red 로 만든다.
          // This instrument reads background-color only; report a painted gradient so the
          // test fails loudly instead of passing on a number it cannot compute.
          bgImage: (cs.backgroundImage || 'none')};
}
"""


@pytest.mark.parametrize("width,height", _NARROW_VIEWPORTS)
@pytest.mark.parametrize("path", ["/", "/dashboard"])
def test_no_horizontal_overflow_on_narrow_viewports(page, base_url, width, height, path):
    """🔴 좁은 화면에서 문서가 가로로 스크롤되면 안 된다.

    실측(수정 전): 화면과 무관하게 `scrollWidth = 409px` 로 고정돼 375px 에서 34px,
    320px 에서 89px 이 잘렸다. 원인은 `flex-wrap: nowrap` 인 nav 행의 min-content 폭.
    기존 모바일 가드는 버튼 높이만 재고 **문서 넘침을 재지 않아** 이 결함을 못 봤다.

    🔴 두 경로를 다 본다. `/` 만 보면 nav 만 덮고, 대시보드 계열의 두 번째 원인
    (세그먼트 토글 `.dash-mode-toggle`, 실측 폭 362px)은 회귀해도 초록이다 —
    가드를 만든 직후 실제로 그랬다.
    Both paths: `/` alone covers only the nav and leaves the dashboard's segmented
    toggle — the second, independent cause — silently unguarded.
    """
    page.set_viewport_size({"width": width, "height": height})
    page.goto(f"{base_url}{path}")
    page.wait_for_timeout(400)
    over = page.evaluate(
        "() => document.documentElement.scrollWidth"
        " - document.documentElement.clientWidth")
    assert over <= 1, (
        f"{path} 가 {width}px 에서 {over}px 가로로 넘친다 — "
        "화면 밖으로 밀린 내용이 생긴다"
    )


@pytest.mark.parametrize("theme", ["dark", "light", "pastel", "catppuccin"])
def test_primary_button_label_meets_aa(page, base_url, theme):
    """🔴 채워진 기본 버튼의 «라벨» 이 네 테마 모두에서 AA(4.5:1)를 넘어야 한다.

    실측(수정 전): `base.html` 이 `color: #fff` 를 하드코딩해 `components.css` 의
    `var(--accent-text-on)` 을 덮었다 — dark 3.45 · catppuccin 2.03.
    catppuccin 은 토큰에 이미 어두운 글자색이 있었는데도 적용되지 않았다.
    버튼 «면» 은 3:1 이면 되지만 라벨은 본문 텍스트라 4.5 가 적용된다.
    """
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(base_url)
    page.evaluate("(t) => applyTheme(t)", theme)
    page.wait_for_timeout(250)
    page.evaluate("""
      () => { const b = document.createElement('button');
              b.className = 'btn btn-primary'; b.id = 'aa-probe';
              b.textContent = 'Save settings';
              document.querySelector('.container, body').appendChild(b); }
    """)
    page.wait_for_timeout(150)
    res = page.evaluate(_CONTRAST_JS, "#aa-probe")
    assert res["found"], "주입한 .btn-primary 를 찾지 못했다"
    # 🔴 계기의 사각지대를 red 로 바꾼다 — 그라디언트가 칠해지면 아래 비율은 거짓이다.
    assert res["bgImage"] == "none", (
        f"[{theme}] 버튼이 그라디언트({res['bgImage'][:48]})로 칠해진다 — "
        "이 시험은 단색만 계산하므로 비율을 신뢰할 수 없다. 계기를 먼저 고칠 것"
    )
    assert res["ratio"] >= 4.5, (
        f"[{theme}] 기본 버튼 라벨 대비 {res['ratio']:.2f} "
        f"({res['size']:.0f}px, color={res['color']}) — 4.5 필요"
    )


def test_html_and_body_theme_attributes_agree(page, base_url):
    """🔴 저장된 테마로 자연스럽게 로드했을 때 html 과 body 의 data-theme 이 같아야 한다.

    실측(수정 전): `tweaks.js` 가 DOMContentLoaded 에서 뒤늦게 `html[data-theme]` 를
    자기 기본값 dark 로 덮어, `sca-theme=light` 인데도 html=dark · body=light 로 갈렸다.
    🔴 이 축은 «프로브가 applyTheme() 를 직접 부르면» 가려진다 — 부르지 않고 잰다.
    Load naturally (never call applyTheme here) or the defect is masked.
    """
    page.goto(base_url)
    page.evaluate("() => localStorage.setItem('sca-theme', 'light')")
    page.goto(base_url)
    page.wait_for_timeout(700)
    pair = page.evaluate("""
      () => ({html: document.documentElement.getAttribute('data-theme'),
              body: document.body.getAttribute('data-theme')})
    """)
    assert pair["html"] == pair["body"], (
        f"html={pair['html']} · body={pair['body']} 로 갈렸다 — "
        "테마를 늦게 덮어쓰는 코드가 있다"
    )
    assert pair["body"] == "light", f"저장된 테마가 반영되지 않았다: {pair}"


@pytest.mark.parametrize("mode", ["overview", "insight", "security", "usage"])
def test_active_mode_segment_is_visible_on_narrow(page, base_url, mode):
    """🔴 좁은 화면에서 «지금 보고 있는» 모드 세그먼트가 토글 안에 보여야 한다.

    세그먼트 토글을 `overflow-x: auto` 로 만들어 문서 넘침을 없앤 뒤 생긴 2차 결함:
    스크롤 위치가 0 이라 뒤쪽 모드(security·usage)를 열면 활성 항목이 잘려 보이지 않았다
    (실측 320px: security 32px · usage 117px 만큼 오른쪽으로 벗어남).
    「어느 모드인지」를 알려주는 유일한 표시라 안 보이면 길을 잃는다.
    After making the toggle scrollable, the active segment for later modes sat outside
    the visible strip — the only indicator of the current mode.
    """
    page.set_viewport_size({"width": 320, "height": 640})
    page.goto(f"{base_url}/dashboard?mode={mode}")
    page.wait_for_timeout(600)
    res = page.evaluate("""
      () => {
        const t = document.querySelector('.dash-mode-toggle');
        if (!t) return {skip: true};
        const a = t.querySelector('a.active');
        if (!a) return {skip: true};
        const tr = t.getBoundingClientRect(), ar = a.getBoundingClientRect();
        return {skip: false, text: (a.textContent || '').trim(),
                offRight: Math.round(ar.right - tr.right),
                offLeft: Math.round(tr.left - ar.left)};
      }
    """)
    if res.get("skip"):
        pytest.fail("활성 세그먼트를 찾지 못했다 — 이 시험의 전제가 깨졌다")
    assert res["offRight"] <= 1 and res["offLeft"] <= 1, (
        f"[{mode}] 활성 세그먼트 '{res['text']}' 가 토글 밖으로 나갔다 "
        f"(오른쪽 {res['offRight']}px · 왼쪽 {res['offLeft']}px)"
    )


# ── E. 보조·3차 글자색이 «칠해지는» 바탕에서 AA 를 넘는가 (#1609 가 미룬 일) ────────
# Secondary/faint text tokens must clear AA against the color actually painted behind them.

# 🔴 선택자 목록을 쓰지 않는다 — 목록은 늙고, 새로 생긴 사용처를 못 본다.
#    대신 «그 테마에서 --text-2/--text-3 이 실제로 해석된 값» 과 같은 색으로 칠해진
#    글자를 런타임에 골라낸다. 토큰을 새로 쓰는 화면이 생기면 자동으로 범위에 들어온다.
# No selector list: elements are selected at runtime by matching the theme's resolved
# --text-2 / --text-3 values, so new usages are covered automatically.
_TOKEN_TEXT_AUDIT_JS = r"""
() => {
""" + _PARSE_COLOR_JS + r"""
  const over = (f,b) => { const a=f.a+b.a*(1-f.a); if(!a) return {r:0,g:0,b:0,a:0};
    return {r:(f.r*f.a+b.r*b.a*(1-f.a))/a, g:(f.g*f.a+b.g*b.a*(1-f.a))/a,
            b:(f.b*f.a+b.b*b.a*(1-f.a))/a, a}; };
  const stops = bi => (bi.match(/rgba?\([^)]+\)/g)||[]).map(parse).filter(Boolean);
  // 조상 그라디언트는 stop 마다 바탕 후보를 만든다 — 글자가 어느 지점에 앉을지 모른다.
  const paintedBgs = n => { let accs=[{r:255,g:255,b:255,a:1}];
    const chain=[]; for(let x=n;x;x=x.parentElement) chain.push(x);
    for(let i=chain.length-1;i>=0;i--){ const cs=getComputedStyle(chain[i]);
      const bc=parse(cs.backgroundColor); if(bc&&bc.a>0) accs=accs.map(a=>over(bc,a));
      const bi=cs.backgroundImage;
      const clip=(cs.backgroundClip||'')+(cs.webkitBackgroundClip||'');
      if(bi&&bi!=='none'&&!clip.includes('text')){ const g=stops(bi);
        if(g.length) accs=accs.flatMap(a=>g.map(s=>over(s,a))); }
      if(accs.length>24) accs=accs.slice(0,24);
    } return accs; };
  const lum = c => { const f=v=>{v/=255; return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);};
    return 0.2126*f(c.r)+0.7152*f(c.g)+0.0722*f(c.b); };
  const ratio = (a,b) => { const l1=lum(a), l2=lum(b);
    return (Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05); };

  // 🔴 조상 `opacity` 를 곱한다. 이 가드는 `opacity===0` 만 걸렀고 0<o<1 을 무시해
  //    `opacity:.8` 로 흐려진 글자를 «실제보다 진하게» 재고 있었다(실측 4.31 을 5.4 로).
  //    Ancestor opacity was ignored, so dimmed text measured stronger than it renders.
  const opacityFrom = n => { let a=1;
    for(let x=n;x;x=x.parentElement){ const o=parseFloat(getComputedStyle(x).opacity);
      if(!isNaN(o)) a*=o; }
    return a; };
  const bodyCs = getComputedStyle(document.body);
  const want = {};
  // 🔴 관측 대상 토큰 이름은 «한 곳» 에만 둔다. 아래 `seen` 을 따로 리터럴로 적었더니
  //    이 목록을 바꾼 파생 가드에서 `seen[name]` 이 undefined 가 됐다(합계가 NaN).
  //    Keep the token list in one place; a duplicated `seen` literal went stale immediately.
  for (const name of ['--text-2','--text-3']) {
    const c = parse(bodyCs.getPropertyValue(name));
    if (!c) return {error: `${name} 을 읽지 못했다: ${bodyCs.getPropertyValue(name)}`};
    want[name] = c;
  }
  const same = (a,b) => Math.round(a.r)===Math.round(b.r)
                     && Math.round(a.g)===Math.round(b.g)
                     && Math.round(a.b)===Math.round(b.b);

  const bad = [], seen = {};
  for (const name of Object.keys(want)) seen[name] = 0;   // 목록은 위 한 곳에서만 온다
  for (const el of document.querySelectorAll('body *')) {
    const own = Array.from(el.childNodes)
      .filter(n=>n.nodeType===3 && n.textContent.trim()).map(n=>n.textContent.trim()).join(' ');
    if (!own) continue;
    // 이모지·기호만인 요소는 자기 색으로 그려진다 — 1.4.3 대상이 아니다.
    if (!/[\p{L}\p{N}]/u.test(own)) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility==='hidden' || cs.display==='none' || +cs.opacity===0) continue;
    const r = el.getBoundingClientRect();
    if (r.width<1 || r.height<1) continue;
    const fg = parse(cs.webkitTextFillColor || cs.color);
    if (!fg || fg.a===0) continue;
    const token = Object.keys(want).find(k => same(fg, want[k]));
    if (!token) continue;
    const oa = opacityFrom(el);
    if (oa <= 0.005) continue;
    fg.a *= oa;
    seen[token]++;
    const size = parseFloat(cs.fontSize), weight = parseInt(cs.fontWeight,10)||400;
    // WCAG 1.4.3 large text = 18pt(24px), or 14pt(18.5px) bold.
    const need = (size>=24 || (size>=18.5 && weight>=700)) ? 3 : 4.5;
    let worst = Infinity, worstBg = null;
    for (const b of paintedBgs(el)) {
      const v = ratio(over(fg,b), b);
      if (v < worst) { worst = v; worstBg = b; }
    }
    if (worst < need) bad.push({token, ratio: +worst.toFixed(2), need, size,
      text: own.slice(0,40), cls: (typeof el.className==='string'?el.className:''),
      bg: `rgb(${Math.round(worstBg.r)},${Math.round(worstBg.g)},${Math.round(worstBg.b)})`});
  }
  return {bad, seen};
}
"""

# 두 토큰이 실제로 쓰이는 화면들. 각각이 서로 다른 바탕(카드·표·nav 알약·KPI)을 만든다.
# 🔴 대시보드는 «한 화면» 이 아니다 — `?mode=` 마다 다른 DOM 이다. 실측(400조합)에서
#    기본 모드 외 4개는 이 목록에 없어 «한 번도» 대비 관측을 받지 않았다.
#    그런데 라우트 커버리지 가드는 초록이었다: `/dashboard` 가 라우트로는 덮였고,
#    타깃 크기 축이 넣은 `?mode=` 리터럴까지 합쳐 세었기 때문이다.
#    `tests/unit/ui/test_a11y_route_coverage.py::test_the_contrast_sweep_opens_every_dashboard_mode`
#    가 이 목록을 템플릿의 분기와 대조한다 — 새 모드가 생기면 red 다.
_TOKEN_TEXT_PATHS = ["/", "/dashboard", "/repos/owner/testrepo", "/repos/owner/testrepo/insights",
                     "/repos/add",
                     "/dashboard?mode=insight", "/dashboard?mode=security",
                     "/dashboard?mode=usage", "/dashboard?mode=repos"]


def _settle_animations(page) -> None:
    """🔴 «끝난 화면» 을 잰다 — 등장 애니메이션이 도는 중에 재면 `opacity` 가 0.9x 라
    실제보다 흐리게 나온다(실측 `.reveal` 0.936 → 거짓 미달 1.97).
    무한 반복(배경 orb)은 영영 안 끝나므로 제외한다.
    Measure the settled frame: entrance animations mid-flight report a dimmer opacity.
    """
    page.evaluate("""() => Promise.all(document.getAnimations()
        .filter(a => { try { return a.effect.getTiming().iterations !== Infinity; }
                       catch (e) { return false; } })
        .map(a => a.finished.catch(() => {})))""")


def _reveal_all(page) -> None:
    """🔴 화면 «전체» 를 드러낸 뒤 잰다 — 안 그러면 첫 화면 아래는 관측되지 않는다.

    `base.html::_revealIO` 가 `.card`·`.s-card`·`.kpi-card`·`.reveal` 에 `.reveal` 을 붙이고,
    `.visible` 은 **뷰포트에 들어올 때만** 붙인다. `.reveal { opacity: 0 }` 이므로 스크롤하지
    않으면 첫 화면 아래 글자는 전부 `opacity:0` 이고, 대비 감사는 그것을 「보이지 않음」으로
    걸러 «안 쟀는데 통과» 를 만든다.

    🔴 `_settle_animations` 로는 못 고친다. `.visible` 이 붙기 «전» 에는 Animation 객체가
    아예 없어서 기다릴 대상이 0개다 — 그 헬퍼는 이 경우 no-op 다.

    실측(2026-09-09, 400조합): 스크롤을 넣자 관측 글자가 늘고 invisible 로 걸린 수가
    5212 → 2281 로 줄었다. 그리고 결론이 «양방향» 으로 바뀌었다 — 페이드 도중에 재던
    `.mono` 2.52 는 정착값 7.05 로 사라졌고(거짓), 첫 화면 아래 있던 `.field-tag`
    pastel 2.79 같은 진짜 미달이 새로 드러났다.

    Scroll first: reveal-on-intersect content is invisible (and unmeasurable) until it enters
    the viewport, and `_settle_animations` cannot help because no Animation exists yet.
    """
    page.evaluate("""async () => {
        const step = Math.max(200, Math.floor(window.innerHeight * 0.8));
        for (let y = 0; y < document.body.scrollHeight; y += step) {
            window.scrollTo(0, y);
            await new Promise(r => setTimeout(r, 110));
        }
        window.scrollTo(0, 0);
        await new Promise(r => setTimeout(r, 110));
        // 🔴 훑기만으로는 «문서 끝 40px 안» 에 있는 요소가 영영 안 드러난다 —
        //    관찰자의 `rootMargin: 0 0 -40px 0` 때문에 최대 스크롤에서도 교차하지 않는다.
        //    실측: 같은 코드가 로컬은 초록, CI 는 `.reveal 1/7` red 였다(폰트 높이 차이로
        //    경계에 걸린다). 남은 것은 «하나씩» 화면 가운데로 끌어와 확실히 드러낸다.
        const stuck = Array.from(document.querySelectorAll('.reveal')).filter(e => {
            const r = e.getBoundingClientRect();
            return r.width > 0 && r.height > 0
                   && parseFloat(getComputedStyle(e).opacity) < 0.99; });
        for (const el of stuck) {
            el.scrollIntoView({block: 'center'});
            await new Promise(r => setTimeout(r, 90));
        }
        window.scrollTo(0, 0);
        await new Promise(r => setTimeout(r, 110));
    }""")
    _settle_animations(page)


def unrevealed_counts(page) -> dict:
    """`.reveal` 중 아직 안 드러난 것을 **두 부류로 나눠** 센다.

    - `stuck`: 화면에 자리를 차지하는데도 `opacity < 0.99` — 스윕이 «놓친» 것이다.
    - `hiddenByMode`: 상자가 0인 것(모드 토글의 `display:none` 등). 이건 스윕 잘못이
      아니라 «다른 상태에서 재야 할» 표면이다(설정 advanced 등).

    🔴 둘을 합쳐 세면 고칠 수 없는 수가 섞여 시험이 영영 red 이거나, 반대로 뭉뚱그려
    통과시키게 된다. 나눠 세고 각각 다른 곳에서 책임진다.
    """
    return page.evaluate("""() => {
        const out = {stuck: 0, hiddenByMode: 0, total: 0};
        for (const e of document.querySelectorAll('.reveal')) {
            out.total++;
            if (parseFloat(getComputedStyle(e).opacity) >= 0.99) continue;
            const r = e.getBoundingClientRect();
            if (r.width < 1 || r.height < 1) out.hiddenByMode++;
            else out.stuck++;
        }
        return out;
    }""")


@pytest.mark.parametrize("theme", ["dark", "light", "pastel", "catppuccin"])
@pytest.mark.parametrize("path", _TOKEN_TEXT_PATHS)
def test_token_text_meets_aa_against_painted_background(seeded_page, base_url, theme, path):
    """🔴 `--text-2`·`--text-3` 로 칠해진 글자는 «실제로 칠해진» 바탕에서 AA 를 넘어야 한다.

    실측(수정 전, 10화면 x 4테마): `--text-3` 을 쓰는 글자 59건 중 dark·light·pastel 은
    59건 전부, catppuccin 은 48건이 미달이었다(최저 2.40 — pastel body 그라디언트의
    어두운 stop 위).

    🔴 단위 가드(`tests/unit/ui/test_secondary_text_contrast.py`)는 `tokens.css` 의
    표면 토큰만 본다. 그것만으로는 «컴포넌트가 자기 워시를 깔고 그 위에 글자를 얹는» 경우를
    못 본다 — 실제로 nav 의 두 버튼이 그래서 토큰을 올린 뒤에도 4.44 로 남아 있었고,
    이 시험만이 그것을 잡았다. 두 가드는 서로를 대신하지 못한다.
    The unit guard only sees surface tokens; components that paint their own wash under the
    text are invisible to it. Two nav buttons did exactly that and only this test caught them.
    """
    _assert_token_text_aa(seeded_page, base_url, theme, path)


def _assert_token_text_aa(page, base_url, theme, path, viewport=None, prepare=None):
    """한 화면·한 테마에서 토큰 글자의 AA 를 잰다 — 세 시험이 공유한다.

    🔴 화면 목록이 parametrize 상수인 시험과, 화면 경로가 **픽스처에서 와야 하는** 시험
    (분석 상세는 `seeded_analysis` 의 id 가 필요하다)이 같은 측정을 써야 한다. 본문을
    복사하면 한쪽만 고쳐지는 순간 두 화면의 판정이 갈린다.

    🔴 `viewport` 를 «인자» 로 연 이유 — 이 헬퍼가 뷰포트를 데스크탑으로 하드코딩하고
    있어서, 호출자가 모바일 크기를 넣어도 덮였다. 그래서 모바일에만 존재하는 표면
    (`.nav-links.open` 오버레이)의 글자 대비는 원리적으로 **한 번도** 관측되지 않았다.
    기본값은 그대로 데스크탑이라 기존 두 시험의 판정은 바뀌지 않는다.

    `prepare` 는 테마 적용 «후» · 측정 «전» 에 부르는 훅이다(예: 햄버거 열기).

    The viewport was hardcoded to desktop, so mobile-only surfaces were never observed.
    """
    page.set_viewport_size(viewport or {"width": 1440, "height": 900})
    page.goto(f"{base_url}{path}")
    page.evaluate("(t) => applyTheme(t)", theme)
    # 🔴 테마 전환에 transition 이 걸려 있다 — 끄지 않으면 «중간색» 을 잰다(전 테마의
    #    글자색 위에 다음 테마의 바탕이 겹친 값이 나온다).
    page.add_style_tag(content="*,*::before,*::after{transition:none !important}")
    page.wait_for_timeout(400)
    _reveal_all(page)
    if prepare is not None:
        prepare(page)
    res = page.evaluate(_TOKEN_TEXT_AUDIT_JS)

    assert not res.get("error"), res.get("error")
    seen = res["seen"]
    # 🔴 아무것도 못 골랐으면 «통과» 가 아니라 red 다 — 토큰 이름이 바뀌었거나
    #    테마가 적용되지 않은 것이고, 그때 이 시험은 아무 것도 재지 않는다.
    assert seen["--text-2"] + seen["--text-3"] > 0, (
        f"[{theme}] {path} 에서 --text-2/--text-3 로 칠해진 글자를 하나도 찾지 못했다 — "
        "재지 못한 것이지 통과한 것이 아니다"
    )
    bad = res["bad"]
    assert not bad, (
        f"[{theme}] {path} — 토큰 글자 {len(bad)}건이 AA 미달 "
        f"(관측 {seen['--text-2']}+{seen['--text-3']}건):\n  "
        + "\n  ".join(
            f"{b['token']} {b['ratio']} < {b['need']} @{b['size']:.0f}px "
            f"bg={b['bg']} cls={b['cls']!r} {b['text']!r}"
            for b in bad[:12]
        )
    )


@pytest.mark.parametrize("theme", ["dark", "light", "pastel", "catppuccin"])
def test_token_text_meets_aa_on_the_analysis_detail_screen(
        seeded_page, base_url, seeded_analysis, theme):
    """🔴 분석 상세는 경로에 id 가 들어가 parametrize 상수로 못 적어 스윕 밖이었다.

    그 결과 이 화면은 픽셀 접근성 관측을 **한 번도** 받지 않았고, 실제로 심각도 칩이
    리터럴 hex 라 24조합 중 16건이 AA 미달인 채로 남아 있었다(#1633 에서 고쳤다).
    「목록에 못 적는 화면」이 조용히 빠지는 것이 이 스윕의 구조적 구멍이었다.

    The analysis-detail path needs a fixture-provided id, so it could not be a parametrize
    constant — and that is exactly why it was never swept.
    """
    _assert_token_text_aa(seeded_page, base_url, theme,
                          f"/repos/owner%2Ftestrepo/analyses/{seeded_analysis}")


# 오버레이가 «실제로» 열렸고 그 안의 글자가 감사 대상 토큰으로 칠해졌는지 세는 계기.
# 0 이면 위 감사는 오버레이를 한 글자도 보지 못한 것이고, 그때 초록은 「통과」가 아니다.
_OVERLAY_OBSERVED_JS = r"""
() => {
  const box = document.querySelector('.nav-links');
  if (!box) return {error: '.nav-links 미존재'};
  const cs = getComputedStyle(box);
  if (!box.classList.contains('open')) return {error: '햄버거를 눌렀는데 .open 이 없다'};
  if (cs.display === 'none') return {error: '.open 인데 display:none — 오버레이가 안 보인다'};
  // 🔴 토큰 «원시값»(hex)과 computed `color`(rgb 형식)를 문자열로 견주면 언제나 다르다.
  //    그 비교는 항상 0 을 돌려주고, 그러면 이 계기는 「못 쟀다」를 「없다」로 바꾼다.
  //    브라우저에게 var() 를 «해석시켜» 같은 표기로 만든 뒤 견준다.
  const probe = document.createElement('span');
  probe.style.color = 'var(--text-2)';
  document.body.appendChild(probe);
  const want = getComputedStyle(probe).color;
  probe.remove();
  const links = Array.from(box.querySelectorAll('a.nav-link'));
  const painted = links.filter(a => getComputedStyle(a).color === want);
  const r = box.getBoundingClientRect();
  return {links: links.length, painted: painted.length,
          width: Math.round(r.width), height: Math.round(r.height),
          position: cs.position};
}
"""


def _open_mobile_nav(page) -> None:
    """햄버거를 눌러 `.nav-links.open` 오버레이를 띄운다."""
    page.click(".nav-hamburger")
    page.wait_for_selector(".nav-links.open", state="visible", timeout=5000)
    _settle_animations(page)


def _assert_overlay_was_measured(page) -> None:
    """🔴 측정이 «끝난 뒤» 상태로 오버레이가 실제 대상이었는지 되짚는다.

    이 확인을 여는 쪽(`_open_mobile_nav`)에 두었더니, 호출부에서 `prepare=` 를 지우는
    뮤테이션이 **초록으로 남았다** — 검사가 열기와 함께 사라져 오버레이를 한 번도 열지
    않은 채 통과했다. 검사는 지워지는 쪽이 아니라 «남는 쪽» 에 둔다.

    Keeping this inside the opener made a `prepare=`-removal mutation survive green.
    """
    res = page.evaluate(_OVERLAY_OBSERVED_JS)
    assert not res.get("error"), (
        f"{res['error']} — 오버레이를 열지 않은 채 AA 감사가 통과했다(측정 대상 밖)")
    # 「열었다」가 아니라 「감사가 볼 글자가 있다」를 잰다. 오버레이가 열려도 그 안의
    # 글자가 --text-2 가 아니면 AA 감사는 이 면을 한 글자도 재지 않는다.
    assert res["painted"] > 0, (
        f"오버레이가 열렸으나 --text-2 로 칠해진 링크가 0개다 "
        f"(링크 {res['links']}개, {res['width']}x{res['height']}, {res['position']}) — "
        "재지 못한 것이지 통과한 것이 아니다")
    assert res["position"] == "fixed", (
        f"오버레이가 fixed 가 아니다({res['position']}) — 모바일 @media 가 안 걸렸다")


@pytest.mark.parametrize("theme", ["dark", "light", "pastel", "catppuccin"])
def test_token_text_meets_aa_in_the_mobile_nav_overlay(seeded_page, base_url, theme):
    """🔴 모바일에만 «존재하는» 표면 — 데스크탑 스윕은 이 면을 볼 수 없다.

    `@media (max-width: 768px)` 에서 `.nav-links` 는 `display:none` 이 되고, 햄버거를
    누른 `.open` 상태에서만 `position:fixed` 오버레이로 나타난다. 그 오버레이는
    `background: var(--bg-nav)` — **알파 0.72~0.82 의 반투명** 면이다. 1440 에서는 이
    요소가 아예 다른 레이아웃(가로 flex 바)이라, 지금까지의 AA 스윕은 이 면의 글자
    대비를 «한 번도» 관측하지 못했다.

    헬퍼가 뷰포트를 데스크탑으로 하드코딩하고 있었던 것이 그 원인이다 — 호출자가
    모바일 크기를 넣어도 덮였다. 「덜 잰 축」이 아니라 «못 재는 축» 이었다.

    A fixed translucent overlay that only exists under 768px was structurally unobservable.
    """
    _assert_token_text_aa(seeded_page, base_url, theme, "/dashboard",
                          viewport=_MOBILE_VIEWPORT, prepare=_open_mobile_nav)
    _assert_overlay_was_measured(seeded_page)


# ── E-2. 설정 «advanced» 모드 — simple 에서 숨는 표면 ─────────────────────────
# `.adv-only` 22요소가 기본(simple) 모드에서 `display:none` 이라, 이 상태를 열지 않으면
# 어떤 스윕도 그 글자를 본 적이 없다. 실측으로 그 안에 `.field-tag` pastel 2.79 가 있었다.

def _open_settings_advanced(page) -> None:
    """설정을 advanced 모드로 — `.adv-only` 가 실제로 드러날 때까지 기다린다."""
    page.click('[data-settings-mode-btn="advanced"]')
    page.wait_for_selector(".adv-only", state="visible", timeout=5000)


def _assert_advanced_was_measured(page) -> None:
    """🔴 측정이 «끝난 뒤» 상태로 advanced 가 실제 대상이었는지 되짚는다.

    이 확인을 여는 쪽에 두면 호출부에서 `prepare=` 를 지우는 뮤테이션이 초록으로 남는다
    (모바일 오버레이에서 실증한 형태). 검사는 지워지는 쪽이 아니라 «남는 쪽» 에 둔다.
    """
    res = page.evaluate("""() => {
        const vis = Array.from(document.querySelectorAll('.adv-only'))
            .filter(e => { const r = e.getBoundingClientRect();
                           return r.width > 0 && r.height > 0; });
        const mode = (document.body.getAttribute('data-settings-mode')
                      || document.querySelector('main')?.getAttribute('data-settings-mode'));
        return {visible: vis.length, total: document.querySelectorAll('.adv-only').length, mode};
    }""")
    assert res["mode"] == "advanced", (
        f"설정이 advanced 모드가 아니다(mode={res['mode']!r}) — 이 상태를 열지 않았다")
    assert res["visible"] > 0, (
        f"advanced 인데 보이는 `.adv-only` 가 0개다 (총 {res['total']}) — "
        "재지 못한 것이지 통과한 것이 아니다")


@pytest.mark.parametrize("theme", ["dark", "light", "pastel", "catppuccin"])
def test_token_text_meets_aa_in_settings_advanced(seeded_page, base_url, theme):
    """🔴 설정 advanced 는 기본 모드에서 `display:none` 이라 스윕 밖이었다.

    실측(2026-09-09): 그 안의 `.field-tag` 가 `color: var(--accent)` 라 pastel **2.79**,
    light 4.20 이었다. `--accent-text` 로 바꾸면 같은 틴트 면에서 4.93~5.52 로 통과한다.
    「목록에 못 적는 상태」가 조용히 빠지는 것이 이 스윕의 구조적 구멍이었다.

    🔴 이 시험이 «잡지 못하는» 것 — 두 감사는 «특정 토큰 값과 같은 색» 의 글자만 고른다
    (`--text-2`·`--text-3`·`--accent-text`). 그래서 `.field-tag` 를 `--accent` 로 되돌리는
    뮤테이션은 **여기서 초록으로 통과한다** — 그 색이 세 토큰 중 어디에도 해당하지 않아
    관측 대상에서 빠지기 때문이다(실증). 그 축은 정적 열거 가드
    (`tests/unit/ui/test_accent_as_text_closure.py`)가 잡는다. 이 시험이 지키는 것은
    「advanced 상태를 연다」와 「그 상태의 토큰 글자가 AA 를 넘는다」이다.

    The advanced settings pane is display:none by default, so it was never swept. Note the
    audits are token-scoped, so a color that matches none of the three tokens is not observed.
    """
    seeded_page.set_viewport_size({"width": 1440, "height": 900})
    seeded_page.goto(f"{base_url}/repos/owner%2Ftestrepo/settings")
    seeded_page.evaluate("(t) => applyTheme(t)", theme)
    seeded_page.add_style_tag(content="*,*::before,*::after{transition:none !important}")
    seeded_page.wait_for_timeout(350)
    _open_settings_advanced(seeded_page)
    _reveal_all(seeded_page)

    # 🔴 «두 감사를 다» 돌린다. 처음엔 토큰 글자(--text-2/3)만 보게 썼는데, 이 화면에서
    #    고친 것은 «accent 를 글자로 쓰는 태그»(`.field-tag`) 였다 — 그 축을 안 보고 있었다.
    #    뮤테이션(`.field-tag` 를 --accent 로 되돌림)이 green 으로 통과해 드러났다.
    #    admin 시험이 같은 교훈을 이미 담고 있었는데 그 관용구를 안 쓴 것이 원인이다.
    total, bad = 0, []
    for js, names in ((_TOKEN_TEXT_AUDIT_JS, ("--text-2", "--text-3")),
                      (_ACCENT_TEXT_AUDIT_JS, ("--accent-text",))):
        res = seeded_page.evaluate(js)
        assert not res.get("error"), res.get("error")
        total += sum(res["seen"][n] for n in names)
        bad += res["bad"]

    _assert_advanced_was_measured(seeded_page)
    assert total > 0, (
        f"[{theme}] 설정 advanced 에서 토큰 글자를 하나도 찾지 못했다 — "
        "재지 못한 것이지 통과한 것이 아니다")
    assert not bad, (
        f"[{theme}] 설정 advanced 글자 {len(bad)}건이 AA 미달 (관측 {total}건):\n  "
        + "\n  ".join(f"{b['ratio']} < {b['need']} cls={b['cls']!r} {b['text']!r}"
                      for b in bad[:10]))


# ── F. accent 를 «글자» 로 쓰는 곳 (--accent-text) ────────────────────────────
# Accent used AS text — the inverse of --accent-text-on.

# E 절과 같은 방식으로 «해석된 토큰 값» 과 같은 색인 글자를 런타임에 고른다.
_ACCENT_TEXT_AUDIT_JS = _TOKEN_TEXT_AUDIT_JS.replace(
    "for (const name of ['--text-2','--text-3'])", "for (const name of ['--accent-text'])")

_ACCENT_TEXT_PATHS = ["/repos/owner/testrepo", "/repos/owner/testrepo/settings",
                      "/repos/owner/testrepo/insights"]


@pytest.mark.parametrize("theme", ["dark", "light", "pastel", "catppuccin"])
def test_accent_used_as_text_meets_aa(seeded_page, base_url, theme):
    """🔴 `--accent-text` 로 칠해진 글자가 «칠해진» 바탕에서 AA 를 넘어야 한다.

    실측(수정 전, `--accent` 를 그대로 글자로 쓸 때): nav 뱃지 light 3.94 · pastel 2.64,
    본문 링크 pastel 3.24, 인라인 `<code>` pastel 1.86, `.hook-btn` pastel 2.07.
    dark·catppuccin 은 accent 가 어두운 바탕 위라 원래 통과한다 — 그래도 네 테마를 다 도는
    이유는, 밝은 테마용으로 고른 색이 어두운 테마를 깨뜨리지 않았는지 재기 위해서다.

    🔴 accent «면» 색은 이 수정에서 바뀌지 않는다(단위 가드가 그것을 따로 지킨다).
    """
    seeded_page.set_viewport_size({"width": 1440, "height": 900})
    total = 0
    bad = []
    for path in _ACCENT_TEXT_PATHS:
        seeded_page.goto(f"{base_url}{path}")
        seeded_page.evaluate("(t) => applyTheme(t)", theme)
        seeded_page.add_style_tag(content="*,*::before,*::after{transition:none !important}")
        seeded_page.wait_for_timeout(400)
        _reveal_all(seeded_page)
        res = seeded_page.evaluate(_ACCENT_TEXT_AUDIT_JS)
        assert not res.get("error"), res.get("error")
        total += res["seen"]["--accent-text"]
        bad += [dict(b, path=path) for b in res["bad"]]

    # 🔴 관측 0건이면 통과가 아니라 red 다 — 토큰 이름이 바뀌었거나 배선이 끊긴 것이다.
    assert total > 0, (
        f"[{theme}] --accent-text 로 칠해진 글자를 하나도 찾지 못했다 — "
        "재지 못한 것이지 통과한 것이 아니다"
    )
    assert not bad, (
        f"[{theme}] accent 글자 {len(bad)}건이 AA 미달 (관측 {total}건):\n  "
        + "\n  ".join(
            f"{b['ratio']} < {b['need']} @{b['size']:.0f}px bg={b['bg']} "
            f"cls={b['cls']!r} {b['text']!r} ({b['path']})"
            for b in bad[:10]
        )
    )


# ── G. 랜딩이 «앱에서 고른 테마» 를 따르는가 ──────────────────────────────────
# Does the landing page honour the theme the user picked in the app?


def test_landing_honours_the_stored_theme(anonymous_page, base_url):
    """🔴 앱에서 고른 테마가 랜딩에도 적용돼야 한다.

    실측(수정 전): `base.html` 은 `localStorage['sca-theme']` 에 쓰는데
    `landing.html` 은 **`'scam-theme'`** 을 읽었다. 그 키는 리포 어디에서도
    **쓰이지 않는다** — 항상 null 이라 랜딩은 늘 기본값 dark 로 떨어졌다.
    저장값 light 로 확인: `body[data-theme]` 가 `dark` 였다.

    🔴 이 화면은 로그인 상태에서는 렌더되지 않아(`overview` 가 대시보드를 준다)
    `anonymous_page` 없이는 도달할 수 없다 — 그래서 여태 검증된 적이 없다.
    """
    anonymous_page.goto(base_url)
    anonymous_page.evaluate("() => localStorage.setItem('sca-theme', 'light')")
    anonymous_page.reload()
    anonymous_page.wait_for_timeout(400)
    applied = anonymous_page.get_attribute("body", "data-theme")
    stored = anonymous_page.evaluate("() => localStorage.getItem('sca-theme')")
    assert stored == "light", f"저장 자체가 안 됐다 — 이 시험의 전제가 깨졌다 ({stored})"
    assert applied == "light", (
        f"랜딩이 저장된 테마를 무시했다 — body[data-theme]={applied!r}. "
        "앱과 랜딩이 서로 다른 localStorage 키를 읽고 있지 않은지 볼 것"
    )


# ── H. /admin/* 3화면 — 여태 e2e 로 도달할 수 없던 표면 ────────────────────────
# The three admin screens: unreachable from e2e until now.

# 🔴 admin 세션 쿠키·외부 이동 검사는 «관용구» 라 conftest 에 둔다 — 한 파일에만
#    있으면 다음 프로브가 같은 실수를 반복한다(#1639 W10).


_ADMIN_PATHS = ["/admin/tenants", "/admin/rls-audit", "/admin/operations"]


@pytest.mark.parametrize("theme", ["dark", "light", "pastel", "catppuccin"])
def test_admin_screens_render_and_meet_aa(admin_page, base_url, theme,
                                          assert_still_on_our_app):
    """🔴 admin 3화면의 `--accent-text`·`--text-2/3` 글자가 «둘 다» AA 를 넘어야 한다.

    실측(수정 전, 이 화면들이 처음 측정됐다): `.admin-link`·`.admin-ops-link` 가
    accent 를 글자로 써서 pastel 3.24 · `.badge--success` 2.68 ·
    `.admin-ops-card-hint` 가 `opacity:0.8` 로 흐려져 light 4.31.
    셋 다 이미 다른 화면에서 고친 부류인데 `admin.css` 에만 남아 있었다.
    """
    admin_page.set_viewport_size({"width": 1440, "height": 900})
    total, bad = 0, []
    for path in _ADMIN_PATHS:
        resp = admin_page.goto(f"{base_url}{path}")
        # 🔴 호스트·상태·우리 마크업을 «셋 다» 본다 — 403/503 오류 페이지도 localhost 라
        #    호스트만 보면 fail-open 이다. 그 판정은 conftest 의 공용 관용구에 있다.
        assert_still_on_our_app(admin_page, path, resp)
        admin_page.evaluate("(t) => applyTheme(t)", theme)
        admin_page.add_style_tag(content="*,*::before,*::after{transition:none !important}")
        admin_page.wait_for_timeout(350)
        _reveal_all(admin_page)
        # 🔴 «두 감사를 다» 돌린다. 처음엔 토큰 글자(--text-2/3)만 봤는데, 이 화면에서
        #    고친 것은 «accent 를 글자로 쓰는 링크» 였다 — 그 축을 안 보고 있었다.
        #    뮤테이션(`.admin-link` 를 --accent 로 되돌림)이 green 으로 통과해 드러났다.
        for js, names in ((_TOKEN_TEXT_AUDIT_JS, ("--text-2", "--text-3")),
                          (_ACCENT_TEXT_AUDIT_JS, ("--accent-text",))):
            res = admin_page.evaluate(js)
            assert not res.get("error"), res.get("error")
            total += sum(res["seen"][n] for n in names)
            bad += [dict(b, path=path) for b in res["bad"]]
    assert total > 0, (
        f"[{theme}] admin 화면에서 토큰 글자를 하나도 찾지 못했다 — "
        "재지 못한 것이지 통과한 것이 아니다"
    )
    assert not bad, (
        f"[{theme}] admin 글자 {len(bad)}건이 AA 미달 (관측 {total}건):\n  "
        + "\n  ".join(f"{b['ratio']} < {b['need']} cls={b['cls']!r} {b['text']!r} ({b['path']})"
                      for b in bad[:10])
    )


# ── I. 랜딩(비로그인) 대비 — `.reveal` 때문에 스크롤해야 잴 수 있다 ─────────────
# Landing contrast: content is revealed on scroll, so the page must be scrolled first.

@pytest.mark.parametrize("theme", ["dark", "light", "pastel", "catppuccin"])
def test_landing_text_meets_aa(anonymous_page, base_url, theme):
    """🔴 랜딩의 `--text-2/3`·`--accent-text` 글자가 AA 를 넘어야 한다.

    실측(수정 전, 이 화면이 처음 측정됐다): `.stat-label` 이 3.71(네 테마 전부) ·
    `.hero-badge` 가 1.82(light·pastel). 랜딩은 카드가 아니라 «페이지 바탕» 위라
    3차 층이 버티지 못하고, 뱃지는 «면» 전용 토큰(`--accent-hover`)을 글자로 썼다.

    🔴 `.reveal { opacity: 0 }` 이라 스크롤로 드러내지 않으면 4테마 전부 2행만 수집된다
    — 그때는 «통과» 가 아니라 재지 못한 것이다(아래 관측 하한이 그것을 red 로 만든다).
    """
    anonymous_page.set_viewport_size({"width": 1440, "height": 900})
    anonymous_page.goto(base_url)
    anonymous_page.evaluate("(t) => document.body.setAttribute('data-theme', t)", theme)
    anonymous_page.add_style_tag(content="*,*::before,*::after{transition:none !important}")
    anonymous_page.evaluate("""() => new Promise(r => {
        let y = 0;
        const step = () => { window.scrollTo(0, y); y += 600;
          if (y < document.body.scrollHeight) setTimeout(step, 30); else r(); };
        step(); })""")
    anonymous_page.evaluate("() => window.scrollTo(0, 0)")
    _settle_animations(anonymous_page)
    anonymous_page.wait_for_timeout(300)

    total, bad = 0, []
    for js, names in ((_TOKEN_TEXT_AUDIT_JS, ("--text-2", "--text-3")),
                      (_ACCENT_TEXT_AUDIT_JS, ("--accent-text",))):
        res = anonymous_page.evaluate(js)
        assert not res.get("error"), res.get("error")
        total += sum(res["seen"][n] for n in names)
        bad += res["bad"]
    # 🔴 관측 하한 — `.reveal` 이 숨은 채로 재면 «통과» 로 보인다.
    assert total >= 6, (
        f"[{theme}] 랜딩에서 토큰 글자를 {total}건만 찾았다 — "
        "`.reveal` 이 드러나지 않은 채로 잰 것이다(재지 못한 것이지 통과가 아니다)"
    )
    assert not bad, (
        f"[{theme}] 랜딩 글자 {len(bad)}건이 AA 미달 (관측 {total}건):\n  "
        + "\n  ".join(f"{b['ratio']} < {b['need']} cls={b['cls']!r} {b['text']!r}"
                      for b in bad[:8])
    )


# ── J. 포커스 표시 — 「보이는가」와 「3:1 인가」 (WCAG 2.4.7 · 1.4.11) ──────────
# Focus indicator: does it exist at all, and does it meet non-text contrast.

_FOCUSABLE_SEL = ("a[href], button, input:not([type=hidden]), select, textarea,"
                  ' [tabindex]:not([tabindex="-1"]), [role="button"], [role="tab"]')

# 🔴 표시는 요소 자신에만 있지 않다 — range 손잡이는 «의사요소» 다.
#    이 목록이 없으면 손잡이에 링을 준 슬라이더가 「표시 없음」으로 잘못 잡힌다.
_INDICATOR_PSEUDOS = ("::-webkit-slider-thumb", "::before", "::after")

_FOCUS_AUDIT_JS = r"""
(sel) => {
""" + _PARSE_COLOR_JS + r"""
  const over = (f,b) => { const a=f.a+b.a*(1-f.a); if(!a) return {r:0,g:0,b:0,a:0};
    return {r:(f.r*f.a+b.r*b.a*(1-f.a))/a, g:(f.g*f.a+b.g*b.a*(1-f.a))/a,
            b:(f.b*f.a+b.b*b.a*(1-f.a))/a, a}; };
  const lum = c => { const f=v=>{v/=255; return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);};
    return 0.2126*f(c.r)+0.7152*f(c.g)+0.0722*f(c.b); };
  const ratio = (x,y) => { const a=lum(x), b=lum(y);
    return (Math.max(a,b)+0.05)/(Math.min(a,b)+0.05); };
  const ground = n => { let acc={r:255,g:255,b:255,a:1}; const chain=[];
    for(let x=n;x;x=x.parentElement) chain.push(x);
    for(let i=chain.length-1;i>=0;i--){ const cs=getComputedStyle(chain[i]);
      const c=parse(cs.backgroundColor); if(c&&c.a>0) acc=over(c,acc);
      const bi=cs.backgroundImage;
      if(bi&&bi!=='none'){ const g=(bi.match(/rgba?\([^)]+\)|#[0-9a-fA-F]{3,8}/g)||[])
        .map(parse).filter(Boolean);
        g.forEach(s => { if(s.a>0) acc=over(s,acc); }); }
    } return acc; };
  const shadowLayers = v => { const out=[]; let d=0, cur='';
    for(const ch of v){ if(ch==='(') d++; else if(ch===')') d--;
      if(ch===',' && d===0){ out.push(cur); cur=''; } else cur+=ch; }
    if(cur.trim()) out.push(cur); return out; };
  const firstColor = s => { const m=s.match(/rgba?\([^)]*\)|#[0-9a-fA-F]{3,8}|color\([^)]*\)/);
    return m ? parse(m[0]) : null; };

  const PSEUDOS = %PSEUDOS%;
  const out = {seen: 0, skippedRange: 0, noIndicator: [], low: []};
  document.querySelectorAll(sel).forEach(el => {
    if (!el.hasAttribute('data-focus-base')) return;
    // 🔴 range 는 여기서 재지 않는다 — 링이 UA 섀도 의사요소(::-webkit-slider-thumb)에
    //    있고 getComputedStyle 은 그것을 돌려주지 않아 «요소» 값(outline none)을 준다.
    //    그 축은 test_range_slider_focus_actually_paints 가 픽셀로 맡는다.
    if (el.tagName === 'INPUT' && el.type === 'range') { out.skippedRange++; return; }
    const r = el.getBoundingClientRect();
    if (r.width < 6 || r.height < 6) return;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') return;
    let op = 1; for(let x=el;x;x=x.parentElement){
      const o=parseFloat(getComputedStyle(x).opacity); if(!isNaN(o)) op*=o; }
    if (op < 0.99) return;

    out.seen++;
    const base = JSON.parse(el.getAttribute('data-focus-base'));
    // 🔴 링은 요소 «바깥» 에 그려진다(outline-offset). 요소 «자신» 의 면만 바탕으로
    //    삼으면, accent 로 채워진 버튼 위에서 링과 면이 같은 색이라 1.00 이 나온다 —
    //    실제로는 그 링이 페이지 바탕과 4.4:1 로 잘 보인다. 두 인접색 중 «좋은 쪽» 을
    //    취한다(1.4.11 은 인접색에 대해 3:1 을 요구하지, 모든 인접색을 요구하지 않는다).
    // 🔴 표시의 «기하» 에 따라 무엇과 재는지가 다르다
    //    (Understanding 1.4.11 — Relationship with Focus Visible):
    //      · 요소 «바깥» 에 그려지는 표시(outline-offset, 비-inset box-shadow)
    //        → 요소가 «앉은» 바탕, 곧 부모의 색과 3:1. 채워진 버튼의 «면» 과는 무관하다
    //          (Figure 10: 면과 같은 색이어도 페이지와 대비되면 통과).
    //      · 요소의 «테두리» 로 그려지는 표시 → 안팎 «둘 다» 3:1.
    //    처음엔 둘 중 좋은 쪽(max)을 취했는데, 그러면 Figure 9(면과는 대비되지만 페이지와는
    //    1:1 인 바깥 링)가 통과한다 — 명세보다 무른 판정이다(Grok claim-review).
    const gnd = ground(el);
    const gndOut = el.parentElement ? ground(el.parentElement) : gnd;
    const outsideR = (c) => ratio(over(c, gndOut), gndOut);
    const insideR = (c) => ratio(over(c, gnd), gnd);
    const borderR = (c) => Math.min(insideR(c), outsideR(c));
    const cands = [];
    const consider = (colorStr, kind, how) => {
      const c = parse(colorStr); if (!c || c.a <= 0) return;
      cands.push({kind, ratio: how(c), color: colorStr});
    };
    if (parseFloat(cs.outlineWidth) > 0 && !['none','hidden'].includes(cs.outlineStyle))
      consider(cs.outlineColor, 'outline', outsideR);
    if (cs.boxShadow !== base.boxShadow && cs.boxShadow !== 'none')
      shadowLayers(cs.boxShadow).forEach(l => { const c=firstColor(l);
        if (c && c.a>0) cands.push({kind:'box-shadow',
          ratio: /\binset\b/.test(l) ? insideR(c) : outsideR(c),
          color: l.trim().slice(0,40)}); });
    if (cs.borderTopColor !== base.borderTopColor)
      consider(cs.borderTopColor, 'border', borderR);
    PSEUDOS.forEach(ps => {
      const p = getComputedStyle(el, ps);
      if (!p) return;
      if (parseFloat(p.outlineWidth) > 0 && !['none','hidden'].includes(p.outlineStyle))
        consider(p.outlineColor, 'outline' + ps, outsideR);
      if (p.boxShadow && p.boxShadow !== 'none' && p.boxShadow !== base['shadow' + ps])
        { const c = firstColor(p.boxShadow);
          if (c && c.a>0) cands.push({kind:'box-shadow'+ps,
            ratio: /\binset\b/.test(p.boxShadow) ? insideR(c) : outsideR(c),
            color: p.boxShadow.slice(0,40)}); }
    });

    const id = (el.className && String(el.className).slice(0,34)) || el.tagName.toLowerCase();
    if (!cands.length) { out.noIndicator.push(id); return; }
    const best = cands.reduce((a,b) => b.ratio > a.ratio ? b : a);
    if (best.ratio < 3.0)
      out.low.push({cls: id, ratio: +best.ratio.toFixed(2),
                    kind: best.kind, color: best.color});
  });
  return out;
}
""".replace("%PSEUDOS%", str(list(_INDICATOR_PSEUDOS)).replace("'", '"'))

_FOCUS_BASE_JS = r"""
(payload) => {
  const [sel, pseudos] = payload;
  let n = 0;
  document.querySelectorAll(sel).forEach(el => {
    const cs = getComputedStyle(el);
    const rec = {boxShadow: cs.boxShadow, borderTopColor: cs.borderTopColor};
    pseudos.forEach(ps => { const p = getComputedStyle(el, ps);
      rec['shadow' + ps] = p ? p.boxShadow : 'none'; });
    el.setAttribute('data-focus-base', JSON.stringify(rec));
    n++;
  });
  return n;
}
"""


def _force_focus(page, on: bool) -> int:
    """CDP 로 `:focus`·`:focus-visible` 을 한꺼번에 건다.

    🔴 `focus-visible` 만 걸면 안 된다 — 이 앱은 `input:focus` 로도 스타일해서
    (`settings.html`), 한쪽만 걸면 「표시가 없다」는 거짓 결론이 난다(#1617 에서 실제로).
    """
    cdp = page.context.new_cdp_session(page)
    cdp.send("DOM.enable")
    cdp.send("CSS.enable")
    doc = cdp.send("DOM.getDocument", {"depth": -1, "pierce": True})
    nodes = cdp.send("DOM.querySelectorAll",
                     {"nodeId": doc["root"]["nodeId"], "selector": "[data-focus-base]"})
    classes = ["focus", "focus-visible"] if on else []
    for nid in nodes["nodeIds"]:
        try:
            cdp.send("CSS.forcePseudoState",
                     {"nodeId": nid, "forcedPseudoClasses": classes})
        except Exception:  # noqa: BLE001 — 사라진 노드는 건너뛴다
            pass
    return len(nodes["nodeIds"])


#    🔴 목록은 «화면» 이 아니라 «상태» 다. 설정 화면은 게이트가 닫힌 리포만 있어서,
#    `approve_mode='semi-auto'` 라야 보이는 임계값 입력 3개가 한 번도 포커스 관측을
#    받지 않았다 — 그중 `#rejectVal`(`.num-input.danger`)이 1.19:1 로 미달이었다.
#    `/` 와 `?mode=` 분기도 같은 이유로 넣는다(실측: 그쪽은 미달 0).
_FOCUS_PATHS = ["/dashboard", "/repos/owner/testrepo",
                "/repos/owner/testrepo/settings", "/repos/owner/testrepo/insights",
                "/repos/add", "/",
                "/dashboard?mode=repos", "/dashboard?mode=security",
                "/repos/owner%2Fgatedrepo/settings",
                "/repos/owner%2Funclaimedrepo/settings"]


@pytest.mark.parametrize("theme", ["dark", "light", "pastel", "catppuccin"])
def test_every_focusable_shows_an_indicator_that_meets_3to1(
        seeded_page, base_url, seeded_analysis, gated_settings_repo, unclaimed_repo, theme):
    """🔴 포커스를 받은 요소는 «표시가 있어야» 하고 그 표시는 3:1 이상이어야 한다.

    실측(수정 전):
      - `#scoreMin`·`#scoreMax`(점수 범위 슬라이더)는 Tab 으로 도달해도 표시가 «전혀»
        없었다 — 픽셀로 5092px 중 0px. `.dual-slider-track input[type=range]` 의
        `outline:none` 이 전역 링을 특이도로 이기고 대체가 없었다. WCAG 2.4.7(Level AA).
      - pastel 의 링(`--accent` #8c82d2)이 페이지 바탕에서 2.77~2.88 (9건).

    🔴 표시를 «의사요소» 에서도 찾는다. 슬라이더 링은 `::-webkit-slider-thumb` 에 있어
    요소만 보면 고친 뒤에도 「표시 없음」으로 잡힌다.

    🔴 이 스윕이 **유일한 실효 관측자**다. 단위 가드
    (`tests/unit/ui/test_focus_indicator.py::test_outline_none_is_always_paired_with_a_replacement_indicator`)
    는 «파일에 대체 표시가 있는가» 를 보므로, 같은 파일 안에서 특정 규칙만 표시를 잃는
    경우를 못 본다 — `#rejectVal` 이 정확히 그랬다(1.19:1). `input:focus{outline:none}` 은
    남아 있으니, 새 상태 클래스(예: `.field-input.invalid{border-color:…}`)가 생기면 같은
    부류가 재발한다. **그 상태를 이 목록이 열지 않으면 아무도 못 본다.**

    🔴 두 픽스처(`gated_settings_repo`·`unclaimed_repo`)를 여기서 요청하므로 시드가
    이 파일 앞쪽으로 당겨진다 — 뒤의 below-the-fold 스윕이 `/dashboard` 에서
    `active_repos.total` 을 더 큰 값으로 본다(건수를 단언하지 않아 통과는 유지된다.
    Grok `01a09491` 이 내 「부작용 없음」 주장을 WEAKENED 로 깎았다).
    """
    seeded_page.set_viewport_size({"width": 1440, "height": 900})
    total, skipped_range, missing, low = 0, 0, [], []
    # 🔴 분석 상세는 경로에 id 가 들어가 상수 목록에 못 적는다 — 그래서 이 스윕 밖이었다.
    #    「목록에 못 적는 화면」이 조용히 빠지는 것이 이 가드의 구조적 구멍이었다.
    for path in [*_FOCUS_PATHS,
                 f"/repos/owner%2Ftestrepo/analyses/{seeded_analysis}"]:
        seeded_page.goto(f"{base_url}{path}")
        seeded_page.evaluate("(t) => applyTheme(t)", theme)
        # 🔴 설정 화면의 임계값 입력은 «고급 모드» 안이라, 열지 않으면 0×0 이고 포커스
        #    감사는 그것을 건너뛴다 — 열지 않은 채로는 `#rejectVal` 의 1.19:1 을 못 본다.
        seeded_page.evaluate(
            "() => { document.body.setAttribute('data-settings-mode', 'advanced');"
            " document.querySelectorAll('details').forEach(d => d.open = true); }")
        seeded_page.add_style_tag(content="*,*::before,*::after{transition:none !important}")
        seeded_page.wait_for_timeout(300)
        _reveal_all(seeded_page)
        n = seeded_page.evaluate(_FOCUS_BASE_JS,
                                 [_FOCUSABLE_SEL, list(_INDICATOR_PSEUDOS)])
        if not n:
            continue
        _force_focus(seeded_page, True)
        seeded_page.wait_for_timeout(150)
        res = seeded_page.evaluate(_FOCUS_AUDIT_JS, _FOCUSABLE_SEL)
        _force_focus(seeded_page, False)
        total += res["seen"]
        skipped_range += res["skippedRange"]
        missing += [f"{path}: {c}" for c in res["noIndicator"]]
        low += [dict(b, path=path) for b in res["low"]]

    # 🔴 관측 하한 — 하나도 못 걸면 «통과» 가 아니라 재지 못한 것이다.
    assert total >= 40, (
        f"[{theme}] 포커스 가능한 요소를 {total}건만 관측했다 — "
        "강제가 걸리지 않았거나 화면이 비었다(재지 못한 것이지 통과가 아니다)"
    )
    # 🔴 range 를 «실제로» 만났는지 — 0 이면 전용 픽셀 가드가 겨냥할 대상이 사라졌다는
    #    뜻이므로, 조용한 초록 대신 red 로 알린다.
    assert skipped_range >= 2, (
        f"[{theme}] range 입력을 {skipped_range}건만 만났다 — "
        "test_range_slider_focus_actually_paints 가 겨냥하는 대상이 바뀌었는지 볼 것"
    )
    assert not missing, (
        f"[{theme}] 포커스 표시가 «전혀» 없는 요소 {len(missing)}건 (WCAG 2.4.7 Level AA):\n  "
        + "\n  ".join(missing[:10])
    )
    assert not low, (
        f"[{theme}] 포커스 표시 {len(low)}건이 3:1 미만 (관측 {total}건):\n  "
        + "\n  ".join(f"{b['ratio']} cls={b['cls']!r} {b['kind']} {b['color']} ({b['path']})"
                      for b in low[:10])
    )


# ── K. 차트 격자선 — canvas 는 무효 색을 «조용히» 버린다 ──────────────────────
# Chart gridlines: canvas silently discards an invalid color and keeps the previous one.

_CANVAS_COLOR_JS = r"""
(names) => {
  const probe = document.createElement('canvas').getContext('2d');
  const cs = getComputedStyle(document.body);
  const out = {};
  names.forEach(n => {
    const v = cs.getPropertyValue(n).trim();
    probe.strokeStyle = '#010203';
    let ok = false;
    try { probe.strokeStyle = v; ok = probe.strokeStyle !== '#010203'; } catch (e) { ok = false; }
    out[n] = {value: v, valid: ok, resolved: probe.strokeStyle};
  });
  out._charts = [];
  document.querySelectorAll('canvas').forEach(cv => {
    const ch = (window.Chart && window.Chart.getChart) ? window.Chart.getChart(cv) : null;
    if (!ch || !ch.options || !ch.options.scales) return;
    Object.keys(ch.options.scales).forEach(k => {
      const g = ch.options.scales[k].grid;
      if (!g || g.color == null) return;
      const v = String(g.color);
      probe.strokeStyle = '#010203';
      let ok = false;
      try { probe.strokeStyle = v; ok = probe.strokeStyle !== '#010203'; } catch (e) { ok = false; }
      out._charts.push({id: cv.id, axis: k, value: v, valid: ok});
    });
  });
  return out;
}
"""

_CHART_COLOR_TOKENS = ["--chart-grid", "--border-subtle", "--accent", "--text-2"]


@pytest.mark.parametrize("theme", ["dark", "light", "pastel", "catppuccin"])
def test_chart_colors_are_valid_canvas_colors(seeded_page, base_url, theme):
    """🔴 차트에 넘기는 색은 canvas 가 «받아들이는» 형식이어야 한다.

    실측(수정 전): 격자선 색이 `border + '44'` 였다. 그 이어붙이기는 토큰이 16진일 때만
    유효한데 dark 는 `rgba(255,255,255,0.06)` 이라 결과가 파싱 불가 문자열이 된다.
    canvas 는 예외를 내지 않고 «직전 strokeStyle» 을 그대로 쓴다 — 실측 결과
    `repoTrendChart` 의 격자선 3/3 이 «불투명 검정»(0,0,0,255)으로 칠해졌다.

    여기서는 브라우저의 canvas 파서에 직접 세워 보고 되읽는다 — 계산이 아니라 관측이다.
    """
    seeded_page.set_viewport_size({"width": 1440, "height": 900})
    seeded_page.goto(f"{base_url}/repos/owner/testrepo")
    seeded_page.evaluate("(t) => applyTheme(t)", theme)
    seeded_page.wait_for_timeout(400)
    res = seeded_page.evaluate(_CANVAS_COLOR_JS, _CHART_COLOR_TOKENS)

    empty = [n for n in _CHART_COLOR_TOKENS if not res[n]["value"]]
    assert not empty, (
        f"[{theme}] 차트가 읽는 토큰이 비었다: {empty} — "
        "빈 값은 Chart.js 기본색으로 조용히 대체된다"
    )
    bad = [f"{n}={res[n]['value']!r}" for n in _CHART_COLOR_TOKENS if not res[n]["valid"]]
    assert not bad, (
        f"[{theme}] canvas 가 받지 못하는 색 형식: {bad} — "
        "무효 색은 예외 없이 «직전 색» 으로 칠해진다"
    )
    live_bad = [c for c in res["_charts"] if not c["valid"]]
    assert not live_bad, (
        f"[{theme}] 살아 있는 차트의 격자색이 무효다: "
        + ", ".join(f"#{c['id']}.{c['axis']}={c['value']!r}" for c in live_bad[:6])
    )


# ── L. range 슬라이더 — 표시가 «UA 섀도 의사요소» 에 있어 계산으로는 안 보인다 ──
# Range sliders: the indicator lives on a UA shadow pseudo-element, invisible to
# getComputedStyle — so this axis is measured in pixels instead.

_RANGE_SLIDERS = [
    ("/repos/owner/testrepo", "#scoreMin"),
    ("/repos/owner/testrepo", "#scoreMax"),
    ("/repos/owner/testrepo/settings", ".approve-range"),
    ("/repos/owner/testrepo/settings", ".reject-range"),
]


def _clip_bytes(page, sel: str) -> bytes:
    """요소 둘레를 잘라 찍는다 — 스크롤하지 않으므로 뷰포트 좌표 = 페이지 좌표."""
    r = page.evaluate(
        "(s) => { const e = document.querySelector(s); const b = e.getBoundingClientRect();"
        " return {x: b.left - 14, y: b.top - 14, width: b.width + 28, height: b.height + 28}; }",
        sel)
    return page.screenshot(clip=r)


@pytest.mark.parametrize("path,sel", _RANGE_SLIDERS)
def test_range_slider_focus_actually_paints(seeded_page, base_url, path, sel):
    """🔴 슬라이더에 포커스가 가면 «픽셀이 바뀌어야» 한다.

    실측(수정 전): Tab 으로 도달해도 5092px 중 **0px** 이 바뀌었다 — 네 테마 전부.
    `.dual-slider-track input[type=range] { outline: none }`(특이도 0,2,1)가 전역
    `*:focus-visible`(0,1,0)를 이기는데 대체가 없었다. WCAG 2.4.7 Focus Visible(Level AA).

    🔴 이 시험이 증명하는 것은 «무언가 칠해진다» 까지다. 그 표시가 3:1 인지는
    `tests/unit/ui/test_focus_indicator.py::test_range_slider_has_a_thumb_focus_ring`
    (링이 `--focus-ring` 을 지나는가)와 `--focus-ring` 토큰 대비 시험이 함께 맡는다 —
    실측상 settings 슬라이더는 일반 `input:focus` 규칙에서 15% 글로를 이미 받고 있어,
    「픽셀이 바뀐다」만으로는 약한 표시를 통과시킨다.

    🔴 이 축은 «계산» 으로 못 잰다. 고친 링은 `::-webkit-slider-thumb` 에 있고,
    `getComputedStyle(el, '::-webkit-slider-thumb')` 은 UA 섀도 의사요소를 돌려주지
    않아 요소 자신의 값(=outline none)을 준다 — 계산 기반 가드는 여기서 fail-open 이다.

    🔴 자기검사를 함께 돌린다 — 같은 자리에 빨강 링을 «강제» 했을 때도 픽셀이 안 바뀌면
    그것은 앱의 결함이 아니라 계기의 고장이다. 실제로 한 번 그랬다(`animation:none` 을
    전역 주입하면 스크린샷이 갱신을 멈춘다).
    """
    page = seeded_page
    # 높은 뷰포트 — 스크롤하지 않아야 clip 좌표계가 문제되지 않는다
    page.set_viewport_size({"width": 1440, "height": 2400})
    page.goto(f"{base_url}{path}")
    # 🔴 settings 는 «간단 모드» 가 기본이라 임계값 슬라이더가 0×0 이다 — 그대로 재면
    #    「화면에서 못 찾음」으로 red 가 나고, 정작 재려던 것은 못 잰다.
    page.evaluate("() => { document.body.setAttribute('data-settings-mode', 'advanced');"
                  " document.querySelectorAll('details').forEach(d => d.open = true);"
                  " document.querySelectorAll('.is-hidden')"
                  ".forEach(e => e.classList.remove('is-hidden')); }")
    page.add_style_tag(content="*,*::before,*::after{transition:none !important}"
                               ".atmosphere__orb{display:none !important}")
    page.wait_for_timeout(600)
    _settle_animations(page)

    visible = page.evaluate(
        "(s) => { const e = document.querySelector(s); if (!e) return false;"
        " e.scrollIntoView({block: 'center'});"
        " const b = e.getBoundingClientRect();"
        " return b.width >= 6 && b.height >= 6 && b.top >= 0"
        "        && b.bottom <= window.innerHeight; }", sel)
    page.wait_for_timeout(250)
    assert visible, (
        f"{sel} 를 화면 안에서 찾지 못했다 — 재지 못한 것이지 통과가 아니다"
    )

    before = _clip_bytes(page, sel)

    # A. 자기검사 — 계기가 링을 «볼 수 있는가»
    # 🔴 자기검사도 «손잡이» 에 얹는다. 입력 요소에 얹으면 손잡이 링이 잘려 안 보여도
    #    자기검사만 초록이 되어, 정작 재려는 자리를 못 본 채 통과할 수 있다(Grok 지적).
    handle = page.add_style_tag(
        content=f"{sel}::-webkit-slider-thumb{{outline:3px solid #ff0000 !important;"
                "outline-offset:2px !important}")
    page.wait_for_timeout(250)
    sanity = _clip_bytes(page, sel)
    page.evaluate("(el) => el.remove()", handle)
    page.wait_for_timeout(250)
    assert sanity != before, (
        f"자기검사 실패 — {sel} 자리에 빨강 링을 강제해도 픽셀이 안 바뀐다. "
        "계기가 고장난 것이므로 이 시험의 초록·빨강 모두 믿을 수 없다"
    )
    # 🔴 강제 스타일을 뗀 «뒤» 다시 기준을 잡는다 — 자리가 1px 만 움직여도 그림 크기가
    #    달라져 바이트 비교가 무의미해진다(실측: 이 자리에서 한 번 그랬다).
    before = _clip_bytes(page, sel)

    # B. 실제 포커스
    page.evaluate("(s) => document.querySelector(s).setAttribute('data-focus-base', '{}')", sel)
    forced = _force_focus(page, True)
    assert forced >= 1, "CDP 가 포커스를 강제하지 못했다"
    page.wait_for_timeout(300)
    after = _clip_bytes(page, sel)
    _force_focus(page, False)

    assert after != before, (
        f"{sel} 에 포커스가 가도 «픽셀이 하나도» 바뀌지 않는다 — 표시가 없다 "
        "(WCAG 2.4.7 Level AA). `outline:none` 을 쓴 규칙에 대체 표시가 붙었는지 볼 것"
    )


# ── I. 스윕이 «첫 화면만» 재고 있지 않은지 ────────────────────────────────────

@pytest.mark.parametrize("path", ["/repos/owner%2Ftestrepo/settings", "/dashboard"])
def test_the_aa_sweep_measures_below_the_fold_too(seeded_page, base_url, path):
    """🔴 대비 감사가 첫 화면 아래를 «보지 못한» 채 초록이면 안 된다.

    `.reveal { opacity: 0 }` + IntersectionObserver 구조라, 스크롤하지 않으면 첫 화면
    아래 글자는 전부 opacity 0 이고 감사는 그것을 「보이지 않음」으로 «건너뛴다».
    건너뛴 것은 통과가 아니다 — 이 시험이 그 차이를 잰다.

    🔴 `_settle_animations` 는 이 축을 못 막는다. `.visible` 이 붙기 전에는 기다릴
    Animation 이 0개라 그 헬퍼가 no-op 이기 때문이다.

    Without scrolling, reveal-on-intersect content stays at opacity 0 and is skipped.
    """
    seeded_page.set_viewport_size({"width": 1440, "height": 900})
    seeded_page.goto(f"{base_url}{path}")
    seeded_page.add_style_tag(content="*,*::before,*::after{transition:none !important}")
    _settle_animations(seeded_page)
    seeded_page.wait_for_timeout(300)

    # 🔴 대조군 — 이 화면에 애초에 `.reveal` 이 없으면 이 시험은 아무것도 재지 않는다.
    total = seeded_page.evaluate("() => document.querySelectorAll('.reveal').length")
    assert total > 0, f"{path} 에 `.reveal` 요소가 0개다 — 이 시험이 재는 대상이 없다"

    before = unrevealed_counts(seeded_page)
    _reveal_all(seeded_page)
    after = unrevealed_counts(seeded_page)

    # 🔴 계기 자기검증 — 스크롤 «전» 에 안 드러난 것이 하나도 없으면 이 시험은 아무것도
    #    증명하지 않는다(화면이 짧아 전부 첫 화면에 들어온 경우). 그때는 대상 화면을 바꾼다.
    assert before["stuck"] > 0, (
        f"{path}: 스크롤 전에도 가려진 `.reveal` 이 0개다 — 이 시험이 재는 대상이 없다 "
        f"(total={before['total']})")
    assert after["stuck"] == 0, (
        f"{path}: 스윕이 끝난 뒤에도 자리를 차지한 `.reveal` {after['stuck']}/{total} 개가 "
        "opacity<0.99 다 — 그 글자들의 대비는 어떤 조합에서도 관측되지 않는다(안 쟀음 ≠ 통과)")


# ── J. WCAG 2.5.8 타깃 크기 (24×24) — 모바일 ─────────────────────────────────

_TARGET_MIN = 24

# 🔴 규범 예외를 «코드로» 적는다. 손으로 셀렉터를 빼면 그 자리는 영영 안 재진다.
#   - 문장 안 링크: 「문장 안에 있거나 line-height 로 크기가 묶인 타깃」(SC 2.5.8 예외).
#     flex 아이템은 blockify 돼 line-height 에 묶이지 «않으므로» 예외가 아니다 — 실측으로
#     `.admin-link` 는 `display:block` · 부모 `flex` 였다.
#   - range 입력: 타깃은 thumb 이고 입력 상자가 아니다(#1627 이 thumb 을 24 로 만들었다).
_TARGET_AUDIT_JS = r"""
(MIN) => {
  const CTRL = 'button, a[href], input:not([type=hidden]), select, textarea,' +
               ' [role=button], [role=menuitem]';
  // 🔴 «고급 전용 컨트롤을 실제로 셌는가» 는 감사 «안에서» 세야 한다. 밖에서 «상자가
  //    있는가» 만 보면, 그 컨트롤이 면제로 빠져도(0×0·range·문장 안 링크) 되짚기는
  //    초록으로 남는다 — 감싼 상자는 여전히 보이기 때문이다(Grok `01a0945f`).
  const out = {seen: 0, advSeen: 0, small: [],
               exempt: {range: 0, inlineInSentence: 0, zeroBox: 0}};
  for (const el of document.querySelectorAll(CTRL)) {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) { out.exempt.zeroBox++; continue; }
    if (el.tagName === 'INPUT' && el.getAttribute('type') === 'range') {
      out.exempt.range++; continue; }
    const cs = getComputedStyle(el);
    if (el.tagName === 'A' && cs.display === 'inline') {
      const p = el.parentElement;
      const flow = p && Array.from(p.childNodes)
        .some(n => n.nodeType === 3 && n.textContent.trim());
      if (flow) { out.exempt.inlineInSentence++; continue; }
    }
    out.seen++;
    if (el.closest('.adv-only')) out.advSeen++;
    if (r.width < MIN || r.height < MIN)
      out.small.push({sel: (el.className && typeof el.className === 'string'
                            ? '.' + el.className.trim().split(/\s+/)[0] : el.tagName.toLowerCase()),
                      w: Math.round(r.width), h: Math.round(r.height),
                      display: cs.display,
                      text: (el.textContent || '').trim().slice(0, 20)});
  }
  return out;
}
"""

# 🔴 대시보드는 «한 화면» 이 아니다 — `?mode=` 분기마다 다른 DOM 이다. 첫 판은 이 목록에
#    `?mode=insight` 가 없어서, 프로브가 거기서 잡은 15~20px 링크를 가드가 못 봤다
#    (Grok `01a0899b`). 화면이 아니라 «상태» 를 적는다.
#    🔴 «화면» 만이 아니라 «설정 상태» 도 목록이다. 같은 설정 URL 이라도 게이트가 닫힌
#    리포와 열린 리포는 컨트롤 수가 다르고(실측 35 vs 38), 미청구 리포는 저장 버튼이 없다.
#    `/` 와 `/dashboard`(overview)는 아예 목록 밖이라 24px 축을 한 번도 받지 않았다.
_TARGET_PATHS = ["/admin/tenants", "/admin/rls-audit", "/admin/operations",
                 "/repos/owner%2Ftestrepo/insights", "/repos/owner%2Ftestrepo/settings",
                 "/dashboard?mode=insight", "/dashboard?mode=security", "/dashboard?mode=repos",
                 "/", "/dashboard",
                 "/repos/owner%2Fgatedrepo/settings", "/repos/owner%2Funclaimedrepo/settings"]


def _assert_advanced_controls_were_measured(page, audit) -> None:
    """🔴 «고급 컨트롤을 실제로 «쟀는가»» 를 측정이 끝난 뒤 되짚는다.

    세 단계로 좁힌다 — 전부 Grok `01a0945f` 가 앞 판의 구멍을 지적해 생겼다:
      ① 상태: 모드가 `advanced` 다(접힌 `<details>` 는 본문의 «하나씩 열기» 루프가 맡는다 —
         상호배타 아코디언이라 «전부 열림» 은 애초에 불가능한 상태다).
      ② 결속: **감사가 센 컨트롤 중** `.adv-only` 안의 것이 1개 이상(`audit["advSeen"]`).
         밖에서 «감싼 상자가 보이는가» 만 보면, 그 안의 컨트롤이 면제(0×0·range·문장 안
         링크)로 빠져도 초록이 된다.
      ③ 이름: 모드 토글이 있는데 `.adv-only` 가 0이면 클래스 이름이 바뀐 것이다 —
         조용히 «해당 없음» 으로 빠지지 않게 red.

    red 로 만드는 뮤테이션(실측): 본문에서 모드를 여는 `evaluate` 를 지우면
    `/repos/owner%2Ftestrepo/settings` 가 `mode='simple'` 로 red.
    🔴 단, `owner/gatedrepo` 는 설정 때문에 **처음부터 advanced** 로 뜬다
    (`settings.py::_detect_initial_mode`) — 그 경로에서는 그 뮤테이션이 초록이다. 이
    되짚기가 보는 것은 «내가 열었는가» 가 아니라 «지금 열려 있는가» 이고, 그것이 옳다.
    """
    res = page.evaluate("""() => ({
        btns: document.querySelectorAll('[data-settings-mode-btn]').length,
        mode: document.body.dataset.settingsMode || null,
        advTotal: document.querySelectorAll('.adv-only').length,
    })""")
    if not res["btns"] and not res["advTotal"]:
        return  # 고급 모드라는 개념이 없는 화면 — 이 축은 해당 없음
    assert res["advTotal"], (
        "모드 토글은 있는데 `.adv-only` 가 0개다 — 클래스 이름이 바뀌었으면 이 축은 "
        "조용히 «해당 없음» 이 되어 사라진다")
    assert res["btns"], (
        "`.adv-only` 표면은 있는데 모드 토글이 없다 — 그 컨트롤을 열 수단이 사라졌다")
    assert res["mode"] == "advanced", (
        f"설정 화면 모드가 {res['mode']!r} — 고급 컨트롤이 0×0 으로 «면제» 되어 "
        "재지 않은 채 초록이 된다(실측: 열지 않으면 14건, 열면 35건)")
    assert audit["advSeen"] > 0, (
        f"감사가 «잰» {audit['seen']}건 중 `.adv-only` 안의 것이 0 — 고급 컨트롤은 "
        "여전히 관측 밖이다(면제로 빠졌는지 볼 것)")


@pytest.mark.parametrize("path", _TARGET_PATHS)
def test_every_control_meets_the_24px_target_on_mobile(
        admin_page, base_url, gated_settings_repo, unclaimed_repo, path):
    """🔴 375px 에서 컨트롤이 24×24 미만이면 손가락으로 정확히 누를 수 없다 (SC 2.5.8 AA).

    실측(수정 전): `.admin-link`·`.admin-ops-link` 22px · `.ri-back-link` 21px ·
    `.mask-toggle` 36×23 — 전부 1~3px 모자랐다.

    🔴 예외는 «세어» 남긴다. 문장 안 링크와 range 입력은 규범상 제외지만, 그 수가 0이 되면
    판정이 조용히 넓어진 것이므로 그것도 알아야 한다.

    🔴 두 픽스처는 세션 스코프라 **첫 파라미터(`/admin/tenants`)에서 시드된다** — 종전에는
    이 파일 뒤쪽에서야 만들어지던 리포가 이제 여기서 생겨, 그 사이의 AA 스윕
    (`/dashboard`·`?mode=repos`·overview)이 리포 카드 한 장과 `active_repos.total` 2→3 을
    더 본다. 건수를 단언하는 시험이 없어 통과는 유지되지만 «부작용 없음» 은 사실이 아니다
    (Grok `01a0945f` 가 내 주장을 REFUTED).

    Controls below 24x24 cannot be hit reliably; exemptions are counted, not hidden.
    """
    admin_page.set_viewport_size(_MOBILE_VIEWPORT)
    resp = admin_page.goto(f"{base_url}{path}")
    assert "localhost" in admin_page.url, (
        f"{path} 가 렌더되지 않고 {admin_page.url[:60]} 로 이동했다 — 남의 페이지를 잰다")
    assert resp is not None and resp.status == 200, f"{path} status={resp and resp.status}"
    # 🔴 설정 화면은 «간단 모드» 가 기본이라 고급 카드의 컨트롤 20여 개가 0×0 이고,
    #    감사는 그것을 `zeroBox` 로 «면제» 한다 — 열지 않으면 절반을 영영 안 잰다
    #    (실측 14 → 35). 사용자가 여는 방식 그대로 연다: 모드 토글 + `<details>`.
    #    🔴 `.is-hidden` 은 벗기지 않는다 — 설정으로 닫힌 행은 «설정이 열린 리포»
    #    (`owner/gatedrepo`, `auto_merge=True`)가 열어서 잰다. 클래스를 손으로 벗기면
    #    실제로는 공존하지 않는 배치를 재게 된다(Grok `01a09457`).
    admin_page.evaluate("() => { document.body.setAttribute('data-settings-mode', 'advanced');"
                        " document.querySelectorAll('details').forEach(d => d.open = true); }")
    _reveal_all(admin_page)

    res = admin_page.evaluate(_TARGET_AUDIT_JS, _TARGET_MIN)
    small, seen, adv_seen = list(res["small"]), res["seen"], res["advSeen"]

    # 🔴 «전부 열기» 로는 부족하다 — `.preset-details` 3개는 `ontoggle` 로 서로를 닫는
    #    **상호배타 아코디언**이라 동시에 열리지 않는다. 실측: 한 번에 열면 첫 패널만
    #    열려 나머지 두 패널의 «적용» 버튼은 0×0 → `zeroBox` 면제 → 영영 관측 밖.
    #    그래서 하나씩 열어 각 상태를 재고 결과를 합친다.
    #    Exclusive accordions cannot all be open; measure one panel at a time and union.
    panels = admin_page.evaluate("() => document.querySelectorAll('details').length")
    unopened = []
    for i in range(panels):
        opened = admin_page.evaluate(
            "(i) => { const ds = [...document.querySelectorAll('details')];"
            " ds.forEach((d, j) => { d.open = (j === i); });"
            " return !!(ds[i] && ds[i].open); }", i)
        if not opened:
            unopened.append(i)
            continue
        r = admin_page.evaluate(_TARGET_AUDIT_JS, _TARGET_MIN)
        small += r["small"]
        seen, adv_seen = max(seen, r["seen"]), max(adv_seen, r["advSeen"])
    assert not unopened, (
        f"{path}: `<details>` 패널 {unopened} 를 열지 못했다 — 그 안의 컨트롤은 "
        "재지 못한 것이지 통과한 것이 아니다")

    _assert_advanced_controls_were_measured(admin_page, {"seen": seen, "advSeen": adv_seen})
    assert seen > 0, (
        f"{path} 에서 컨트롤을 하나도 재지 못했다 — 재지 못한 것이지 통과한 것이 아니다")
    assert not small, (
        f"{path}: {_TARGET_MIN}px 미만 컨트롤 {len(small)}건 "
        f"(관측 {seen} · 예외 {res['exempt']}):\n  "
        + "\n  ".join(f"{s['sel']} {s['w']}x{s['h']} display={s['display']} {s['text']!r}"
                      for s in small[:10]))


# ── K. 상호작용 «상태» — 클릭해야 나타나는 표면 (#1639 W9) ────────────────────
#
# 🔴 이 상태들은 열지 않으면 어떤 픽셀 감사도 그 면을 보지 못한다. 모바일 nav 오버레이
#    (#1637)와 설정 advanced(#1641)가 같은 부류였고, 둘 다 열자마자 진짜 미달이 나왔다.
#    목록은 `tests/unit/ui/test_a11y_route_coverage.py::interactive_states` 가 소스에서
#    파생해 대조한다 — 새 상태가 생기면 그 가드가 먼저 red 다.
#
# 🔴 «트리거» 가 아니라 «상태» 를 잰다. 이슈 모달의 등록 버튼은 분석에 이슈가 있어야
#    렌더되는데 e2e 시드에는 없다(그 축은 #1639 W12). 마크업은 서버가 렌더하므로
#    상태 클래스를 직접 바꿔 «칠해진 상태» 를 관측한다 — 트리거 경로는 주장하지 않는다.

# 프로덕션 `openModal` 이 채우는 것과 «같은» 필드를 채운다 — 빈 모달은 다른 화면이다.
_FILL_ISSUE_MODAL = """() => {
    document.getElementById('issueTitle').value = 'e2e: SQL 인젝션 가능성 / possible SQL injection';
    document.getElementById('issueBody').value = 'e2e 본문 / body - src/app.py:12';
    document.getElementById('issueLabels').value = 'bug, security';
    /* +error */
    document.getElementById('issueModalOverlay').classList.remove('hidden');
}"""

_STATE_OPENERS = {
    "#themeDropdown": ("/dashboard", "() => document.getElementById('themeToggle').click()"),
    "#langDropdown": ("/dashboard", "() => document.getElementById('langToggle').click()"),
    ".save-bar": ("/repos/owner%2Ftestrepo/settings",
                  "() => document.querySelector('.save-bar').classList.add('visible')"),
    # 🔴 «빈» 모달을 열면 프로덕션에 없는 화면을 재게 된다 — `openModal` 은
    #    세 입력을 채운 뒤 연다(`analysis_detail.html::function openModal`).
    #    글자가 없는 상자를 열어 초록을 받는 것은 관측이 아니다(Grok `01a08bb5`).
    # 🔴 «진짜 트리거» 로 연다 — 클래스를 손으로 벗기면 「버튼을 누르면 열린다」를
    #    증명하지 못한다. 탭은 클릭 핸들러가 `hidden` 을 벗기는 구조라 클릭이 곧 관측이다
    #    (`analysis_detail.html::document.querySelectorAll('.issue-tab')`).
    #    이 면이 «빈 컨테이너» 였던 이유는 도달성이 아니라 시드에 정적 이슈가 없어서였다
    #    (#1639 W12) — `e2e/conftest.py::seed_result` 가 이제 두 건을 넣는다.
    "#tabStatic": ("/repos/owner%2Ftestrepo/analyses/__ID__",
                   # 🔴 속성값에 따옴표를 쓰지 않는다 — 이 문자열은 JS 소스로 넘어가는데
                   #    작은따옴표를 중첩하면 `SyntaxError: missing ) after argument list`
                   #    가 나고, 스윕은 그것을 «대비 미달» 로 보고한다(실측: 네 테마 전부
                   #    거짓 red). CSS 속성 선택자는 식별자면 따옴표가 필요 없다.
                   "() => document.querySelector('.issue-tab[data-tab=static]').click()"),
    "#issueModalOverlay": ("/repos/owner%2Ftestrepo/analyses/__ID__", _FILL_ISSUE_MODAL),
    "#issueModalError": ("/repos/owner%2Ftestrepo/analyses/__ID__",
                         _FILL_ISSUE_MODAL.replace("/* +error */", """
        const e = document.getElementById('issueModalError');
        e.classList.remove('hidden');
        e.textContent = 'e2e: 이슈 생성에 실패했습니다 / issue creation failed';""")),
    "#issueToast": ("/repos/owner%2Ftestrepo/analyses/__ID__",
                    "() => { const t = document.getElementById('issueToast');"
                    " t.classList.remove('hidden');"
                    " t.textContent = 'e2e: 이슈가 생성되었습니다 / issue created'; }"),
    # 프로덕션(`repo_detail.html::state.datePreset`)은 열면서 두 날짜를 채운다.
    ".custom-date-wrap": ("/repos/owner%2Ftestrepo", """() => {
        document.getElementById('dateFrom').value = '2026-01-01';
        document.getElementById('dateTo').value = '2026-09-01';
        document.querySelector('.custom-date-wrap').classList.add('visible');
    }"""),
    # 🔴 인라인 `display:none` 축 — CSS 클래스가 없어 (a)~(c) 어디에도 안 걸렸다.
    #    `settings.html::document.getElementById('telegramOtpDisplay').style.display = ''`
    "#telegramOtpDisplay": ("/repos/owner%2Ftestrepo/settings", """() => {
        document.getElementById('telegramOtpCode').textContent = '482915';
        document.getElementById('telegramOtpDisplay').style.display = '';
    }"""),
    # `settings.html::lbl.style.display = (k === name) ? 'block' : 'none'`
    # 프리셋 카드는 접힌 `<details>` 안이라 카드를 먼저 편다.
    "#pt-label-minimal": ("/repos/owner%2Ftestrepo/settings", """() => {
        document.getElementById('preset-minimal').open = true;
        document.getElementById('pt-label-minimal').style.display = 'block';
    }"""),
    "#pt-label-standard": ("/repos/owner%2Ftestrepo/settings", """() => {
        document.getElementById('preset-standard').open = true;
        document.getElementById('pt-label-standard').style.display = 'block';
    }"""),
    "#pt-label-strict": ("/repos/owner%2Ftestrepo/settings", """() => {
        document.getElementById('preset-strict').open = true;
        document.getElementById('pt-label-strict').style.display = 'block';
    }"""),
    # `add_repo.html::toast.classList.add('show')` — 등록 실패 경로의 토스트.
    ".toast": ("/repos/add", """() => {
        const t = document.getElementById('errorToast');
        t.textContent = 'e2e: 이미 등록된 리포지터리입니다 / already registered';
        t.classList.add('show');
    }"""),
}

_STATE_VISIBLE_JS = r"""
(sel) => {
  const el = document.querySelector(sel);
  if (!el) return {error: sel + ' 미존재'};
  const cs = getComputedStyle(el), r = el.getBoundingClientRect();
  return {display: cs.display, opacity: +cs.opacity,
          w: Math.round(r.width), h: Math.round(r.height),
          texts: Array.from(el.querySelectorAll('*'))
            .filter(n => Array.from(n.childNodes).some(
                c => c.nodeType === 3 && c.textContent.trim())).length};
}
"""


@pytest.mark.parametrize("selector", sorted(_STATE_OPENERS))
@pytest.mark.parametrize("theme", ["dark", "light", "pastel", "catppuccin"])
def test_token_text_meets_aa_in_interactive_states(seeded_page, base_url, seeded_analysis,
                                                   theme, selector):
    """🔴 클릭해야 나타나는 면의 글자도 AA 를 넘어야 한다.

    Interaction-only surfaces are unobservable unless a sweep opens them.
    """
    path, opener = _STATE_OPENERS[selector]
    path = path.replace("__ID__", str(seeded_analysis))
    _assert_token_text_aa(seeded_page, base_url, theme, path,
                          prepare=lambda p: p.evaluate(opener))

    # 🔴 측정이 «끝난 뒤» 상태로 되짚는다 — 여는 쪽에 두면 `prepare=` 를 지우는
    #    뮤테이션이 초록으로 남는다(모바일 오버레이에서 실증한 형태).
    res = seeded_page.evaluate(_STATE_VISIBLE_JS, selector)
    assert not res.get("error"), res["error"]
    assert res["display"] != "none" and res["opacity"] > 0.5, (
        f"{selector} 가 열리지 않았다({res}) — 재지 못한 것이지 통과한 것이 아니다")
    assert res["w"] > 0 and res["h"] > 0, f"{selector} 의 상자가 0이다({res})"


# ── E-3. 설정 «게이트» 블록 — 기본 설정에서 `is-hidden` 인 표면 (#1639 W12-b) ──
#
# `settings.html` 은 네 블록을 설정값으로 숨긴다:
#   `{% if not config.auto_merge %}is-hidden{% endif %}`      ×2 (임계값 행·이슈 토글)
#   `{% if config.approve_mode == 'disabled' %}is-hidden{% endif %}`  (승인 임계값)
#   `{% if config.approve_mode != 'semi-auto' %}is-hidden{% endif %}` (semi-auto 힌트)
#
# 🔴 기본값이 `auto_merge=False`·`approve_mode="disabled"` 라 네 블록 전부 `display:none`
#    으로 렌더된다. 그 안에는 range 슬라이더·숫자 입력·임계값 라벨이 있는데, 어떤 스윕도
#    그 글자를 «본 적이 없다». 도달성 문제가 아니라 **설정값** 문제다.
#
# 🔴 그리고 이 자리는 「참 팔이 새 클래스를 내놓는가」로는 못 찾는다 — 참 팔이 내놓는 것은
#    공유 클래스 `is-hidden` 이고, 봐야 할 UI 는 **거짓 팔**이다(Grok `01a090cd`).
#    양쪽 팔을 다 봐야 이 부류가 보인다.

_GATE_BLOCK_IDS = ("#mergeThresholdRow", "#approveThresholds",
                   "#semiAutoHint", "#mergeIssueRow")


def _assert_gate_blocks_were_measured(page) -> None:
    """🔴 측정이 «끝난 뒤» 네 블록이 실제로 보였는지 되짚는다.

    여는 쪽이 아니라 남는 쪽에 둔다 — 호출부에서 준비 단계를 지우는 뮤테이션이
    초록으로 남지 않게(설정 advanced 시험과 같은 관용구).
    """
    res = page.evaluate("""(ids) => {
        const out = {};
        for (const id of ids) {
            const el = document.querySelector(id);
            if (!el) { out[id] = 'missing'; continue; }
            const r = el.getBoundingClientRect();
            out[id] = (r.width > 0 && r.height > 0) ? 'visible' : 'hidden';
        }
        return out;
    }""", list(_GATE_BLOCK_IDS))
    hidden = {k: v for k, v in res.items() if v != "visible"}
    assert not hidden, (
        f"게이트 블록이 열리지 않았다: {hidden} — 시드 설정"
        "(`auto_merge=True`·`approve_mode='semi-auto'`)이 닿지 않았다. "
        "재지 못한 것이지 통과한 것이 아니다."
    )


@pytest.mark.parametrize("theme", ["dark", "light", "pastel", "catppuccin"])
def test_token_text_meets_aa_in_settings_gate_blocks(
        seeded_page, base_url, gated_settings_repo, theme):
    """🔴 설정 게이트 블록은 기본 설정에서 `display:none` 이라 스윕 밖이었다.

    red 로 만드는 뮤테이션 두 가지 — 축이 다르다:
      · 시드의 `auto_merge` 를 끄면 **픽스처 단언**이 먼저 잡는다(ERROR). 시드가 닿지
        않았다는 뜻이고, 그 자리에서 멈추는 것이 맞다.
      · 템플릿이 설정과 무관하게 `class="is-hidden"` 을 박으면 시드는 멀쩡한데 화면이
        안 열린다 — 그때 `_assert_gate_blocks_were_measured` 가 FAILED 로 잡는다(실증).
    """
    from urllib.parse import quote

    seeded_page.set_viewport_size({"width": 1440, "height": 900})
    seeded_page.goto(f"{base_url}/repos/{quote(gated_settings_repo, safe='')}/settings")
    assert "localhost" in seeded_page.url, (
        f"{seeded_page.url[:60]} 로 나갔다 — 남의 페이지를 잰다")
    seeded_page.evaluate("(t) => applyTheme(t)", theme)
    seeded_page.add_style_tag(content="*,*::before,*::after{transition:none !important}")
    seeded_page.wait_for_timeout(350)
    _reveal_all(seeded_page)

    total, bad = 0, []
    for js, names in ((_TOKEN_TEXT_AUDIT_JS, ("--text-2", "--text-3")),
                      (_ACCENT_TEXT_AUDIT_JS, ("--accent-text",))):
        res = seeded_page.evaluate(js)
        assert not res.get("error"), res.get("error")
        total += sum(res["seen"][n] for n in names)
        bad += res["bad"]

    _assert_gate_blocks_were_measured(seeded_page)
    assert total > 0, (
        f"[{theme}] 게이트 블록이 열린 설정 화면에서 토큰 글자를 하나도 찾지 못했다 — "
        "재지 못한 것이지 통과한 것이 아니다")
    assert not bad, (
        f"[{theme}] 게이트 블록 글자 {len(bad)}건이 AA 미달 (관측 {total}건):\n  "
        + "\n  ".join(f"{b['ratio']} < {b['need']} cls={b['cls']!r} {b['text']!r}"
                      for b in bad[:10]))


# ── E-4. «없을 때» 의 화면 — 부재 팔 (#1639 W12-b 2차) ───────────────────────
#
# 🔴 정밀 검증에서 내 지표가 틀렸다는 것이 드러났다. 「참 팔을 못 봄」만 세면
#    `{% if X %}있음{% else %}없음{% endif %}` 의 **«없음» 쪽이 통째로 빠진다** —
#    실측: 관측 안 된 «팔» 163/410 중 **46건이 «거짓 팔»** 이었고, 그쪽이 대부분
#    사람이 «데이터가 없을 때» 보는 화면이다.
#
# 이 시험이 여는 것:
#   `analysis_detail.html:26·:33`  점수 NULL → `—` 와 등급 없는 히어로
#   `analysis_detail.html:378·:381` 줄번호·경로 없는 이슈 행
#   `dashboard.html:504·:585·:599·:777` 분석이 하나도 없는 리포의 repos 리포트

# 부재를 «무엇으로» 확인하는가: `.analysis-hero__score-num` 이 `—` 인가(점수 NULL) ·
# `.issue__path` 가 0개인가(위치 없는 이슈). 아래 단언이 그 둘을 직접 읽는다 —
# 같은 목록을 상수로 또 두면 쓰이지 않는 전역이 되고, 실제로 CodeQL
# `py/unused-global-variable`(alert #616)을 자초했다.


def _assert_absence_was_rendered(page) -> None:
    """🔴 부재 팔이 «실제로» 그려졌는지 측정 후에 되짚는다."""
    res = page.evaluate("""() => {
        const num = document.querySelector('.analysis-hero__score-num');
        const paths = document.querySelectorAll('.issue__path');
        const issues = document.querySelectorAll('.issue');
        return {score: num ? num.textContent.trim() : null,
                issues: issues.length, paths: paths.length};
    }""")
    assert res["score"] is not None, "히어로 점수 자리를 못 찾았다 — 화면이 바뀌었다"
    assert res["score"] in ("—", "-"), (
        f"점수가 {res['score']!r} — NULL 시드가 닿지 않았다. 부재 팔을 재지 못했다")
    assert res["issues"] > 0, "이슈 행이 0개 — 위치 없는 이슈 시드가 닿지 않았다"
    assert res["paths"] == 0, (
        f"`.issue__path` 가 {res['paths']}개 — 위치 «없는» 이슈여야 하는데 경로가 그려졌다")


@pytest.mark.parametrize("theme", ["dark", "light", "pastel", "catppuccin"])
def test_token_text_meets_aa_when_data_is_absent(
        seeded_page, base_url, absence_analysis, theme):
    """🔴 점수도 위치도 «없는» 분석 상세에서 글자가 AA 를 넘는가.

    red 로 만드는 뮤테이션: 시드의 `score` 에 값을 넣으면 `—` 가 사라져
    `_assert_absence_was_rendered` 가 red.
    """
    seeded_page.set_viewport_size({"width": 1440, "height": 900})
    seeded_page.goto(f"{base_url}/repos/owner%2Fgatedrepo/analyses/{absence_analysis}")
    assert "localhost" in seeded_page.url, (
        f"{seeded_page.url[:60]} 로 나갔다 — 남의 페이지를 잰다")
    seeded_page.evaluate("(t) => applyTheme(t)", theme)
    seeded_page.add_style_tag(content="*,*::before,*::after{transition:none !important}")
    seeded_page.wait_for_timeout(350)
    _reveal_all(seeded_page)

    total, bad = 0, []
    for js, names in ((_TOKEN_TEXT_AUDIT_JS, ("--text-2", "--text-3")),
                      (_ACCENT_TEXT_AUDIT_JS, ("--accent-text",))):
        res = seeded_page.evaluate(js)
        assert not res.get("error"), res.get("error")
        total += sum(res["seen"][n] for n in names)
        bad += res["bad"]

    _assert_absence_was_rendered(seeded_page)
    assert total > 0, (
        f"[{theme}] 부재 화면에서 토큰 글자를 하나도 찾지 못했다 — "
        "재지 못한 것이지 통과한 것이 아니다")
    assert not bad, (
        f"[{theme}] 부재 화면 글자 {len(bad)}건이 AA 미달 (관측 {total}건):\n  "
        + "\n  ".join(f"{b['ratio']} < {b['need']} cls={b['cls']!r} {b['text']!r}"
                      for b in bad[:10]))


@pytest.mark.parametrize("theme", ["dark", "light", "pastel", "catppuccin"])
def test_token_text_meets_aa_for_a_repo_with_no_analyses(
        seeded_page, base_url, gated_settings_repo, theme):
    """🔴 분석이 하나도 없는 리포의 repos 리포트 — «아직 아무것도 없다» 화면.

    red 로 만드는 뮤테이션: `gatedrepo` 에 분석을 시드하면 평균 점수가 생겨
    부재 팔이 닫히고 되짚기 단언이 red.
    """
    from urllib.parse import quote

    seeded_page.set_viewport_size({"width": 1440, "height": 900})
    seeded_page.goto(
        f"{base_url}/dashboard?mode=repos&repo={quote(gated_settings_repo, safe='')}")
    assert "localhost" in seeded_page.url, (
        f"{seeded_page.url[:60]} 로 나갔다 — 남의 페이지를 잰다")
    seeded_page.evaluate("(t) => applyTheme(t)", theme)
    seeded_page.add_style_tag(content="*,*::before,*::after{transition:none !important}")
    seeded_page.wait_for_timeout(350)
    _reveal_all(seeded_page)

    total, bad = 0, []
    for js, names in ((_TOKEN_TEXT_AUDIT_JS, ("--text-2", "--text-3")),
                      (_ACCENT_TEXT_AUDIT_JS, ("--accent-text",))):
        res = seeded_page.evaluate(js)
        assert not res.get("error"), res.get("error")
        total += sum(res["seen"][n] for n in names)
        bad += res["bad"]

    assert total > 0, (
        f"[{theme}] 분석 없는 리포 화면에서 토큰 글자를 하나도 찾지 못했다 — "
        "재지 못한 것이지 통과한 것이 아니다")
    assert not bad, (
        f"[{theme}] 분석 없는 리포 화면 글자 {len(bad)}건이 AA 미달 (관측 {total}건):\n  "
        + "\n  ".join(f"{b['ratio']} < {b['need']} cls={b['cls']!r} {b['text']!r}"
                      for b in bad[:10]))


# ── E-5. 보안 모드의 «데이터 있는» 상태 — 4카드 그리드 (#1639 W12-b 3차) ──────
#
# `?mode=security` 는 세 갈래다 — kill-switch · `total_alerts == 0` 빈 상태 · 4카드 그리드.
# e2e 는 알림이 0건이라 **언제나 빈 상태만** 그렸다. 카드 수치·분류 집계·대기 목록은
# 한 번도 관측되지 않았다. 빈 상태 분기는 단위 i18n 렌더 시험이 따로 덮는다
# (`tests/unit/templates/test_dashboard_i18n_render.py`).
#
# 🔴 이 자리를 고르는 데 Grok `01a092f6` 이 기여했다 — 내 초안은 insight 모드를 함께
#    넣으려 했는데, 그쪽은 `ANTHROPIC_API_KEY` + 캐시 행 + 로케일 일치가 모두 필요하고
#    기존 `test_dashboard_insight.py` 가 «status div 가 그려질 것» 을 단언한다. 분리했다.


def _assert_security_grid_was_rendered(page) -> None:
    """🔴 측정이 «끝난 뒤» 그리드가 실제로 그려졌는지 되짚는다.

    red 로 만드는 뮤테이션: 시드를 0건으로 되돌리면 빈 상태가 그려져 red.
    """
    res = page.evaluate("""() => {
        const grid = document.querySelector('.dash-insight-grid');
        const status = document.querySelector('.dash-insight-status');
        return {grid: !!grid,
                cards: grid ? grid.children.length : 0,
                status: status ? status.textContent.trim().slice(0, 40) : null};
    }""")
    assert res["grid"], (
        f"보안 그리드가 없다 — 빈 상태/kill-switch 가 그려졌다(status={res['status']!r}). "
        "재지 못한 것이지 통과한 것이 아니다")
    assert res["cards"] > 0, "그리드는 있는데 카드가 0개 — 빈 상자를 쟀다"


@pytest.mark.parametrize("theme", ["dark", "light", "pastel", "catppuccin"])
def test_token_text_meets_aa_in_security_mode_with_alerts(
        seeded_page, base_url, security_alerts, theme):
    """🔴 보안 모드가 «알림이 있을 때» 그리는 4카드 그리드에서 글자가 AA 를 넘는가."""
    seeded_page.set_viewport_size({"width": 1440, "height": 900})
    seeded_page.goto(f"{base_url}/dashboard?mode=security")
    assert "localhost" in seeded_page.url, (
        f"{seeded_page.url[:60]} 로 나갔다 — 남의 페이지를 잰다")
    seeded_page.evaluate("(t) => applyTheme(t)", theme)
    seeded_page.add_style_tag(content="*,*::before,*::after{transition:none !important}")
    seeded_page.wait_for_timeout(350)
    _reveal_all(seeded_page)

    total, bad = 0, []
    for js, names in ((_TOKEN_TEXT_AUDIT_JS, ("--text-2", "--text-3")),
                      (_ACCENT_TEXT_AUDIT_JS, ("--accent-text",))):
        res = seeded_page.evaluate(js)
        assert not res.get("error"), res.get("error")
        total += sum(res["seen"][n] for n in names)
        bad += res["bad"]

    _assert_security_grid_was_rendered(seeded_page)
    assert total > 0, (
        f"[{theme}] 보안 그리드에서 토큰 글자를 하나도 찾지 못했다 — "
        "재지 못한 것이지 통과한 것이 아니다")
    assert not bad, (
        f"[{theme}] 보안 그리드 글자 {len(bad)}건이 AA 미달 (관측 {total}건):\n  "
        + "\n  ".join(f"{b['ratio']} < {b['need']} cls={b['cls']!r} {b['text']!r}"
                      for b in bad[:10]))


# ── E-6. overview 의 «머지 이력이 있을 때» — 실패 사유 목록 + auto-merge KPI ──
#
# e2e 는 `merge_attempts` 행을 한 번도 만들지 않아 overview 는 언제나 「비교 없음」 팔만
# 그렸다. 닫혀 있던 곳: `.reason-list`(`dashboard.html:1234`) · auto-merge KPI 의
# `--text-3` PR 카운트(`:1107`) · delta ▲▼(`:1035`·`:1037`·`:1127`·`:1129`).
#
# 🔴 같은 화면의 나머지(추세 차트·자주 발생 이슈·리포 카드)는 **이미 그려지고 있었다** —
#    다만 «파일 순서» 덕이었다. 세션이 SQLite 하나를 공유하고 `test_overview_score.py`·
#    `test_performance.py`·`test_state_indication.py` 가 알파벳 순으로 먼저 분석을 심는다.
#    실측(프로브): 새 DB + `seeded_page` 만이면 grade·trend·freq·repo_cards 가 전부 0이고,
#    `test_performance.py` 를 앞세우면 전부 1이 된다. Grok `01a09345` 가 「그 파일이 유일한
#    원인」이라는 내 주장을 WEAKENED 로 깎았다(첫 삽입은 `test_overview_score.py:24-56`,
#    `frequent_issues` 만이 `_seed_analysis` 의 `result.issues` 에 유일하게 의존).
#    그래서 이 시험은 우연에 기대지 않고 픽스처로 못박는다 — 파일 하나를 지우거나
#    `-k` 로 걸러도 여기서 재는 화면은 그대로다.


def _assert_merge_history_was_rendered(page) -> None:
    """🔴 측정이 «끝난 뒤» 머지 이력 화면이 실제로 «재졌는지» 되짚는다.

    존재만 확인하면 부족하다 — 감사 JS 는 색·유효 opacity 로 거른다. 그래서 세 가지를
    같은 방법으로 되짚는다: ① 목록이 열렸는가 ② 그 글자가 감사가 세는 토큰 색인가
    ③ 조상 opacity 를 곱한 값이 1인가(`.card`→`.reveal{opacity:0}` 이면 감사는 건너뛴다).

    red 로 만드는 뮤테이션(전건 실측):
      A. 시드를 no-op 으로 → 목록 0줄.
      B. 사유 메타 색을 토큰 밖으로 → 색 단언.
      C. 본문의 `_reveal_all` 호출 삭제 → 유효 opacity 단언(첫 화면 KPI 글자만으로도
         `total > 0` 은 만족되므로 그 단언은 이 축을 못 막는다 — Grok `01a09378`).
    """
    res = page.evaluate("""() => {
        // 감사 JS 와 같은 방식으로 조상 opacity 를 곱한다.
        const eff = n => { let a = 1;
            for (let x = n; x; x = x.parentElement) {
                const o = parseFloat(getComputedStyle(x).opacity);
                if (!isNaN(o)) a *= o; }
            return a; };
        // 🔴 «감사가 세는 색인가» 를 감사와 같은 방법으로 잰다 — body 기준 `--text-3`
        //    한 값. 색이 토큰을 벗어나면 스윕은 그 글자를 조용히 건너뛴다.
        const probe = document.createElement('span');
        probe.style.color = 'var(--text-3)';
        document.body.appendChild(probe);
        const t3 = getComputedStyle(probe).color;
        probe.remove();
        const rows = document.querySelectorAll('.reason-list .reason-row').length;
        const meta = document.querySelector('.reason-list .reason-row__reason span:last-child');
        // 🔴 delta 칩은 «어느 카드의» 것인지까지 가른다. 페이지 전역으로 ▲▼ 를 세면
        //    분석 건수·활성 리포 같은 다른 카드의 칩이 대신 통과시킨다(Grok `01a09378`).
        let prSpan = null, amDelta = null, avgDelta = null;
        for (const kpi of document.querySelectorAll('.kpi')) {
            const label = kpi.querySelector('.kpi__label');
            const chip = kpi.querySelector('.kpi__delta');
            const cls = chip ? chip.className : '';
            const pr = label ? Array.from(label.querySelectorAll('span'))
                .find(e => /\\d+\\s*\\/\\s*\\d+\\s*PR/.test(e.textContent)) : null;
            if (pr) { prSpan = pr; amDelta = cls; }
            else if (label && label.querySelector('.grade')) { avgDelta = cls; }
        }
        return {rows: rows,
                t3: t3,
                metaColor: meta ? getComputedStyle(meta).color : null,
                metaOpacity: meta ? +eff(meta).toFixed(3) : null,
                prColor: prSpan ? getComputedStyle(prSpan).color : null,
                amDelta: amDelta, avgDelta: avgDelta};
    }""")
    assert res["rows"] >= 2, (
        f"실패 사유 줄이 {res['rows']}개 — `.reason-list` 가 안 열렸다(merge_failures 가 빈 목록). "
        "재지 못한 것이지 통과한 것이 아니다")
    assert res["prColor"] is not None, (
        "auto-merge KPI 의 «N/M PR» 카운트가 없다 — `distinct_prs` 팔이 닫힌 채다. "
        "그 글자가 `--text-3` 이라 이 스윕이 재려던 대상이다")
    assert res["metaColor"] == res["t3"] and res["prColor"] == res["t3"], (
        f"새로 연 글자가 `--text-3`({res['t3']}) 이 아니다 — "
        f"사유 메타={res['metaColor']} · PR 카운트={res['prColor']}. "
        "이 스윕은 그 두 토큰만 세므로, 색이 벗어나면 열어도 «안 재고» 초록이 된다")
    assert res["metaOpacity"] is not None and res["metaOpacity"] >= 0.99, (
        f"사유 메타의 유효 opacity 가 {res['metaOpacity']} — 감사는 이 글자를 «건너뛴다» "
        "(`.card` 가 `.reveal{opacity:0}` 인 채다). 스윕이 안 열린 것을 재고 초록이 된다")
    # 🔴 이 두 칩은 «열렸는지» 만 본다. 색(`--grade-a`/`--grade-f`)은 이 스윕의 관측
    #    대상이 아니고(감사는 `--text-2`·`--text-3`·`--accent-text` 만 센다),
    #    그 조합의 AA 는 `tests/unit/ui/test_grade_badge_contrast.py` 가 맡는다.
    assert res["avgDelta"] and "kpi__delta--up" in res["avgDelta"].split(), (
        f"평균 점수 카드의 delta 가 {res['avgDelta']!r} — ▲ 팔(직전 창 비교)이 안 열렸다")
    assert res["amDelta"] and "kpi__delta--down" in res["amDelta"].split(), (
        f"auto-merge 카드의 delta 가 {res['amDelta']!r} — ▼ 팔(직전 창 비교)이 안 열렸다")


@pytest.mark.parametrize("theme", ["dark", "light", "pastel", "catppuccin"])
def test_token_text_meets_aa_for_overview_with_merge_history(
        seeded_page, base_url, merge_history, theme):
    """🔴 overview 가 «머지 이력이 있을 때» 그리는 글자가 AA 를 넘는가."""
    seeded_page.set_viewport_size({"width": 1440, "height": 900})
    seeded_page.goto(f"{base_url}/dashboard")
    assert "localhost" in seeded_page.url, (
        f"{seeded_page.url[:60]} 로 나갔다 — 남의 페이지를 잰다")
    seeded_page.evaluate("(t) => applyTheme(t)", theme)
    # 🔴 테마가 «실제로 걸렸는지» 확인한다. `applyTheme` 은 모르는 이름을 조용히 dark 로
    #    되돌린다(`base.html`) — 그러면 네 갈래가 같은 화면을 네 번 재고도 초록이다.
    #    이 파일의 다른 스윕들은 아직 이 확인이 없다(Grok `01a09378`).
    applied = seeded_page.evaluate("() => document.documentElement.dataset.theme")
    assert applied == theme, (
        f"테마가 {applied!r} 로 걸렸다 — {theme!r} 을 재려 했는데 다른 화면을 쟀다")
    seeded_page.add_style_tag(content="*,*::before,*::after{transition:none !important}")
    seeded_page.wait_for_timeout(350)
    _reveal_all(seeded_page)

    total, bad = 0, []
    for js, names in ((_TOKEN_TEXT_AUDIT_JS, ("--text-2", "--text-3")),
                      (_ACCENT_TEXT_AUDIT_JS, ("--accent-text",))):
        res = seeded_page.evaluate(js)
        assert not res.get("error"), res.get("error")
        total += sum(res["seen"][n] for n in names)
        bad += res["bad"]

    _assert_merge_history_was_rendered(seeded_page)
    assert total > 0, (
        f"[{theme}] 머지 이력 화면에서 토큰 글자를 하나도 찾지 못했다 — "
        "재지 못한 것이지 통과한 것이 아니다")
    assert not bad, (
        f"[{theme}] 머지 이력 화면 글자 {len(bad)}건이 AA 미달 (관측 {total}건):\n  "
        + "\n  ".join(f"{b['ratio']} < {b['need']} cls={b['cls']!r} {b['text']!r}"
                      for b in bad[:10]))


# ── E-7. «소유자 미등록» 저장소 — 설정 화면의 팔 넷 + `/` 의 경고 배너 ────────
#
# `repo_is_claimed = repo.user_id is not None`(`settings.py:243`) 한 플래그가 설정 화면의
# 팔 셋을 동시에 뒤집는다: 자격증명 가림(`renderable_secrets`) · 안내 힌트(`:1024`) ·
# 저장 버튼 숨김(`:1204` 거짓 팔). 네 번째는 `railway_webhook_unclaimed`(`:1327-1335`) 로,
# **토큰이 설정돼 있을 때만** 열린다. e2e 의 두 리포는 전부 청구돼 있어 이 상태는 한 번도
# 렌더된 적이 없었다.
#
# 🔴 이 시드는 `/` 에 «미청구» 배너(`overview.html:210-215`)도 띄운다. 그 배너 글자는
#    `--text-1` 이고 바탕은 `color-mix(in srgb, var(--warning) 12%, transparent)` 다 —
#    **이 스윕의 토큰 목록에도, 다른 어떤 가드의 바탕 목록에도 없던 조합**이다.
#    그래서 아래 두 번째 시험이 배너 «안» 만 `--text-1` 로 잰다(감사 JS 는 같은 것을 쓰고
#    토큰 이름과 순회 범위만 바꾼다 — `_ACCENT_TEXT_AUDIT_JS` 와 같은 관용구).

_TOKEN_LIST_LINE = "for (const name of ['--text-2','--text-3'])"
_TOKEN_VALUE_LINE = "    const c = parse(bodyCs.getPropertyValue(name));"
_SCAN_LINE = "document.querySelectorAll('body *')"

# 🔴 «해석된» 토큰 값을 쓴다. `getPropertyValue` 는 저자가 쓴 정의를 그대로 준다 —
#    `--text-desc: color-mix(in srgb, ...)` 는 그 문자열에서 숫자 하나(55)만 긁혀
#    **엉뚱한 색**이 되고, 그러면 아무 글자와도 안 맞아 «관측 0건인데 초록» 이 된다.
#    프로브 요소에 `color: var(--토큰)` 을 얹어 브라우저가 계산하게 시킨다.
#    🔴 정의 «여부» 는 프로브로 못 가른다. 토큰이 없으면 `color: var(--없는것)` 은
#    computed-value 단계에서 무효가 되어 선언이 통째로 버려지고 프로브는 **부모 색을
#    상속**한다 — 그러면 그 상속색이 「토큰」 행세를 하며 무관한 글자를 세게 된다
#    (Grok `01a09432` CONFIRMED). `--text-desc` 는 `settings.html:11` 에만 있으므로
#    다른 화면에서 이 감사를 재사용하면 바로 그 상태가 된다. 원시 값이 비면 error 로 죽인다.
_RESOLVED_TOKEN_VALUE = (
    "    const _raw = bodyCs.getPropertyValue(name).trim();"
    "\n    if (!_raw) return {error: `${name} 이 이 화면에 정의돼 있지 않다 —"
    " 프로브가 상속색을 받아 «아무 글자나» 토큰으로 오인한다`};"
    "\n    const _p = document.createElement('span'); _p.style.color = 'var(' + name + ')';"
    " document.body.appendChild(_p); const _v = getComputedStyle(_p).color; _p.remove();"
    "\n    const c = parse(_v);")


def _derive_audit(js: str, *subs: tuple[str, str]) -> str:
    """감사 JS 를 파생한다 — 기준 문자열이 정확히 1회가 아니면 **즉시 실패**한다.

    🔴 `str.replace` 는 못 찾아도 조용히 원본을 돌려준다. 그러면 파생 감사가 원본
    토큰을 재면서 「관측 0건」으로 초록이 될 수 있다 — 파생 시점에 red 로 만든다.
    """
    for old, new in subs:
        if js.count(old) != 1:
            raise RuntimeError(
                f"감사 JS 파생 실패 — 기준 문자열이 {js.count(old)}회 (1회여야 한다): {old[:48]!r}")
        js = js.replace(old, new)
    return js


# `.field-hint`·`.preset-desc`·`.preset-hint`·`.t-desc` 가 쓰는 설정 화면 전용 토큰.
# 실측 18~19건 — 이 축이 없던 동안 그 글자들의 대비는 아무도 재지 않았다
# (단위 `test_settings_desc_readability.py` 는 «규칙이 이 토큰을 쓰는가» 만 본다).
_DESC_TEXT_AUDIT_JS = _derive_audit(
    _TOKEN_TEXT_AUDIT_JS,
    (_TOKEN_LIST_LINE, "for (const name of ['--text-desc'])"),
    (_TOKEN_VALUE_LINE, _RESOLVED_TOKEN_VALUE))

_BANNER_TEXT1_AUDIT_JS = _derive_audit(
    _TOKEN_TEXT_AUDIT_JS,
    (_TOKEN_LIST_LINE, "for (const name of ['--text-1'])"),
    (_TOKEN_VALUE_LINE, _RESOLVED_TOKEN_VALUE),
    (_SCAN_LINE, "document.querySelectorAll('.ov-unclaimed-banner, .ov-unclaimed-banner *')"))


def _assert_unclaimed_settings_was_rendered(page, expected_hints: dict) -> None:
    """🔴 측정이 «끝난 뒤» 미청구 팔 넷이 실제로 그려졌는지 되짚는다.

    red 로 만드는 뮤테이션: 시드에서 `user_id` 를 채우면 넷이 한꺼번에 닫히고,
    토큰만 비우면 railway 팔이 «미설정» 문구로 바뀐다(둘 다 red).
    """
    res = page.evaluate("""() => {
        const eff = n => { let a = 1;
            for (let x = n; x; x = x.parentElement) {
                const o = parseFloat(getComputedStyle(x).opacity);
                if (!isNaN(o)) a *= o; }
            return a; };
        const probe = document.createElement('span');
        document.body.appendChild(probe);
        const val = n => { probe.style.color = 'var(' + n + ')';
                           return getComputedStyle(probe).color; };
        // 설정 화면의 안내 글자는 `--text-desc`(color-mix) 다 — `--text-2/3` 이 아니다.
        const tokens = [val('--text-desc')];
        probe.remove();
        const hint = document.querySelector('.field-hint[role="status"]');
        return {
            renderedUnclaimed: document.querySelectorAll('input[name="rendered_unclaimed"]').length,
            hintText: hint ? hint.textContent.trim() : null,
            hintColor: hint ? getComputedStyle(hint).color : null,
            hintOpacity: hint ? +eff(hint).toFixed(3) : null,
            tokens: tokens,
            saveBtn: document.querySelectorAll('#saveBtn').length,
            railwayUrlInput: document.querySelectorAll('#railway-webhook-url').length,
            // 🔴 «설정돼 있는데 가려진다» 를 확인한다 — 시드는 `notify_chat_id` 를 채웠다.
            filledSecrets: Array.from(document.querySelectorAll('input[name^="notify_"]'))
                .filter(e => e.value).map(e => e.name),
            hints: Array.from(document.querySelectorAll('.field-hint'))
                .map(e => e.textContent.trim()),
        };
    }""")
    assert res["renderedUnclaimed"] == 1, (
        f"`rendered_unclaimed` 히든 입력이 {res['renderedUnclaimed']}개 — "
        "미청구 팔이 안 열렸다(리포가 청구된 상태다). 재지 못한 것이지 통과가 아니다")
    assert res["hintText"], "`.field-hint[role=status]` 안내가 없다 — 미청구 팔이 닫힌 채다"
    assert res["saveBtn"] == 0, (
        "저장 버튼이 있다 — 미청구 저장소의 POST 는 403 이라 버튼이 없어야 한다"
        "(`settings.html:1204` 거짓 팔)")
    assert res["railwayUrlInput"] == 0, (
        "미청구 저장소에 railway webhook URL 이 노출됐다 — 세션 없는 엔드포인트의 "
        "인증 수단이 평문으로 나가면 안 된다")
    assert not res["filledSecrets"], (
        f"미청구인데 자격증명 값이 렌더됐다: {res['filledSecrets']} — "
        "`renderable_secrets(..., claimed=False)` 가 가려야 한다")
    # 🔴 부분문자열이 아니라 **정본 문자열 자체**와 대조한다(카탈로그에서 읽어 온다).
    assert expected_hints["unclaimed"] in res["hints"], (
        "railway «청구 필요» 안내가 화면에 없다 — 토큰이 없어 «미설정» 팔로 갔을 수 있다")
    assert expected_hints["pending"] not in res["hints"], (
        "railway «미설정(pending)» 안내가 떴다 — 토큰이 설정돼 있으므로 거짓 안내다")
    assert res["hintColor"] in res["tokens"], (
        f"안내 글자가 {res['hintColor']} — `--text-desc` {res['tokens']} 가 아니라서 "
        "이 스윕이 세지 않는다. 열어도 «안 재고» 초록이 된다")
    assert res["hintOpacity"] is not None and res["hintOpacity"] >= 0.99, (
        f"안내 글자의 유효 opacity 가 {res['hintOpacity']} — 감사가 건너뛴다")


@pytest.mark.parametrize("theme", ["dark", "light", "pastel", "catppuccin"])
def test_token_text_meets_aa_for_an_unclaimed_repo_settings(
        seeded_page, base_url, unclaimed_repo, theme):
    """🔴 «소유자 미등록» 설정 화면의 글자가 AA 를 넘는가."""
    from urllib.parse import quote  # noqa: PLC0415

    from src.i18n.loader import get_text  # noqa: PLC0415

    seeded_page.set_viewport_size({"width": 1440, "height": 900})
    seeded_page.goto(f"{base_url}/repos/{quote(unclaimed_repo, safe='')}/settings")
    assert "localhost" in seeded_page.url, (
        f"{seeded_page.url[:60]} 로 나갔다 — 남의 페이지를 잰다")
    seeded_page.evaluate("(t) => applyTheme(t)", theme)
    applied = seeded_page.evaluate("() => document.documentElement.dataset.theme")
    assert applied == theme, (
        f"테마가 {applied!r} 로 걸렸다 — {theme!r} 을 재려 했는데 다른 화면을 쟀다")
    # 🔴 설정은 «간단 모드» 가 기본이라 고급 카드가 접혀 있다 — railway 블록이 그 안이다.
    seeded_page.evaluate("() => { document.body.setAttribute('data-settings-mode', 'advanced');"
                         " document.querySelectorAll('details').forEach(d => d.open = true); }")
    seeded_page.add_style_tag(content="*,*::before,*::after{transition:none !important}")
    seeded_page.wait_for_timeout(350)
    _reveal_all(seeded_page)

    total, bad, desc_seen = 0, [], 0
    for js, names in ((_TOKEN_TEXT_AUDIT_JS, ("--text-2", "--text-3")),
                      (_ACCENT_TEXT_AUDIT_JS, ("--accent-text",)),
                      (_DESC_TEXT_AUDIT_JS, ("--text-desc",))):
        res = seeded_page.evaluate(js)
        assert not res.get("error"), res.get("error")
        seen = sum(res["seen"][n] for n in names)
        if names == ("--text-desc",):
            desc_seen = seen
        total += seen
        bad += res["bad"]

    # 🔴 `--text-desc` 는 이번에 «처음» 재는 축이다 — 0건이면 파생이 깨진 것이지 통과가 아니다.
    assert desc_seen > 0, (
        f"[{theme}] `--text-desc` 글자를 하나도 찾지 못했다 — 설정 화면의 안내·설명 글자가 "
        "전부 그 토큰인데 0건이면 계기가 고장난 것이다(파생 감사의 토큰 해석 확인)")

    # 화면이 쓰는 로케일 그대로 정본 문자열을 뽑는다 — 'en' 을 손으로 적지 않는다.
    locale = seeded_page.evaluate("() => document.documentElement.lang") or "ko"
    _assert_unclaimed_settings_was_rendered(seeded_page, {
        "unclaimed": get_text("settings_page.inbound.railway_webhook_unclaimed", locale),
        "pending": get_text("settings_page.inbound.railway_webhook_pending", locale),
    })
    assert total > 0, (
        f"[{theme}] 미청구 설정 화면에서 토큰 글자를 하나도 찾지 못했다 — "
        "재지 못한 것이지 통과한 것이 아니다")
    assert not bad, (
        f"[{theme}] 미청구 설정 화면 글자 {len(bad)}건이 AA 미달 (관측 {total}건):\n  "
        + "\n  ".join(f"{b['ratio']} < {b['need']} cls={b['cls']!r} {b['text']!r}"
                      for b in bad[:10]))


@pytest.mark.parametrize("theme", ["dark", "light", "pastel", "catppuccin"])
def test_the_unclaimed_banner_text_meets_aa_on_its_warning_wash(
        seeded_page, base_url, unclaimed_repo, theme):
    """🔴 `/` 의 «미청구» 배너 — `--text-1` 글자가 «경고 워시» 위에서 AA 를 넘는가.

    이 조합은 어느 가드의 바탕 목록에도 없었다. 배너는 자기 바탕을
    `color-mix(in srgb, var(--warning) 12%, transparent)` 로 깔고(`overview.html:55`)
    그 위에 `--text-1` 을 얹는다 — 앞선 두 스윕은 `--text-2`·`--text-3`·`--accent-text`
    만 세므로 이 글자는 열려 있어도 관측 밖이었다.

    red 로 만드는 뮤테이션: 배너 바탕을 `var(--warning)` 100% 로 바꾸면
    (진한 주황 위 밝은 글자) 네 테마 중 여럿이 미달로 잡힌다.
    """
    seeded_page.set_viewport_size({"width": 1440, "height": 900})
    seeded_page.goto(f"{base_url}/")
    assert "localhost" in seeded_page.url, (
        f"{seeded_page.url[:60]} 로 나갔다 — 남의 페이지를 잰다")
    seeded_page.evaluate("(t) => applyTheme(t)", theme)
    applied = seeded_page.evaluate("() => document.documentElement.dataset.theme")
    assert applied == theme, (
        f"테마가 {applied!r} 로 걸렸다 — {theme!r} 을 재려 했는데 다른 화면을 쟀다")
    seeded_page.add_style_tag(content="*,*::before,*::after{transition:none !important}")
    seeded_page.wait_for_timeout(350)
    _reveal_all(seeded_page)

    banners = seeded_page.evaluate(
        "() => document.querySelectorAll('.ov-unclaimed-banner').length")
    assert banners == 1, (
        f"미청구 배너가 {banners}개 — 시드가 열지 못했다(`unclaimed_count` 가 0이다). "
        "재지 못한 것이지 통과한 것이 아니다")

    res = seeded_page.evaluate(_BANNER_TEXT1_AUDIT_JS)
    assert not res.get("error"), res.get("error")
    seen = res["seen"]["--text-1"]
    assert seen > 0, (
        f"[{theme}] 배너 안에서 `--text-1` 글자를 하나도 찾지 못했다 — "
        "이 시험이 재는 대상이 없다(배너 글자색이 토큰을 벗어났는지 볼 것)")
    assert not res["bad"], (
        f"[{theme}] 미청구 배너 글자 {len(res['bad'])}건이 AA 미달 (관측 {seen}건):\n  "
        + "\n  ".join(f"{b['ratio']} < {b['need']} cls={b['cls']!r} {b['text']!r}"
                      for b in res["bad"][:10]))
