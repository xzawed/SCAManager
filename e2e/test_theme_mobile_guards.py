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

    # 8 토큰 모두 :root 에 정의되어 있어야 함 (빈 문자열이면 미정의 = invalid var())
    # All 8 tokens must be defined on :root (empty value = undefined = invalid).
    required = [
        "--grad-gate",
        "--grad-merge",
        "--grad-notify",
        "--grad-hook",
        "--title-gradient",
        "--save-btn-bg",
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
_TOKEN_TEXT_PATHS = ["/", "/dashboard", "/repos/owner/testrepo", "/repos/owner/testrepo/insights"]


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
    seeded_page.set_viewport_size({"width": 1440, "height": 900})
    seeded_page.goto(f"{base_url}{path}")
    seeded_page.evaluate("(t) => applyTheme(t)", theme)
    # 🔴 테마 전환에 transition 이 걸려 있다 — 끄지 않으면 «중간색» 을 잰다(전 테마의
    #    글자색 위에 다음 테마의 바탕이 겹친 값이 나온다).
    seeded_page.add_style_tag(content="*,*::before,*::after{transition:none !important}")
    seeded_page.wait_for_timeout(400)
    _settle_animations(seeded_page)
    res = seeded_page.evaluate(_TOKEN_TEXT_AUDIT_JS)

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
        _settle_animations(seeded_page)
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

def _admin_session_cookie(user_id: int = 1) -> dict:
    """실제 서명 세션 쿠키.

    🔴 의존성을 override 하지 «않는다». `require_admin` 은 `require_login` 을
    의존성이 아니라 «평범한 함수» 로 부르기 때문에(`src/auth/session.py`),
    conftest 의 `dependency_overrides[require_login]` 이 이 경로에는 적용되지 않는다 —
    그래서 admin 화면은 여태 e2e 로 렌더된 적이 없다. 진짜 세션을 만들어
    kill-switch → require_login → email allow-list 사슬을 그대로 태운다.
    """
    import base64  # noqa: PLC0415
    import json as _json  # noqa: PLC0415
    import os  # noqa: PLC0415

    import itsdangerous  # noqa: PLC0415
    # 🔴 비밀키를 여기 복제하지 않는다 — conftest 가 서버에 세운 값을 그대로 읽는다.
    #    복제하면 conftest 가 키를 바꾼 날 조용히 302 로 흘러간다.
    secret = os.environ["SESSION_SECRET"]
    data = base64.b64encode(_json.dumps({"user_id": user_id}).encode())
    value = itsdangerous.TimestampSigner(secret).sign(data).decode()
    return {"name": "session", "value": value, "domain": "localhost", "path": "/"}


_ADMIN_PATHS = ["/admin/tenants", "/admin/rls-audit", "/admin/operations"]


@pytest.mark.parametrize("theme", ["dark", "light", "pastel", "catppuccin"])
def test_admin_screens_render_and_meet_aa(seeded_page, base_url, theme):
    """🔴 admin 3화면의 `--accent-text`·`--text-2/3` 글자가 «둘 다» AA 를 넘어야 한다.

    실측(수정 전, 이 화면들이 처음 측정됐다): `.admin-link`·`.admin-ops-link` 가
    accent 를 글자로 써서 pastel 3.24 · `.badge--success` 2.68 ·
    `.admin-ops-card-hint` 가 `opacity:0.8` 로 흐려져 light 4.31.
    셋 다 이미 다른 화면에서 고친 부류인데 `admin.css` 에만 남아 있었다.
    """
    seeded_page.context.add_cookies([_admin_session_cookie()])
    seeded_page.set_viewport_size({"width": 1440, "height": 900})
    total, bad = 0, []
    for path in _ADMIN_PATHS:
        resp = seeded_page.goto(f"{base_url}{path}")
        # 🔴 호스트만 보면 안 된다 — 403/503 오류 페이지도 localhost 다(fail-open).
        #    상태와 «admin 화면의 실제 마크업» 을 함께 본다.
        assert "localhost" in seeded_page.url, (
            f"{path} 가 렌더되지 않고 {seeded_page.url[:60]} 로 이동했다 — "
            "admin 인가 사슬이 막았다(세션·SAAS_ADMIN_EMAILS 확인)"
        )
        assert resp is not None and resp.status == 200, (
            f"{path} 가 {resp.status if resp else '무응답'} 를 냈다 — "
            "인가는 통과했는지, kill-switch·allow-list 를 볼 것"
        )
        assert seeded_page.locator("nav").count() > 0, (
            f"{path} 에 nav 가 없다 — admin 화면이 아니라 오류 페이지를 잰 것이다"
        )
        seeded_page.evaluate("(t) => applyTheme(t)", theme)
        seeded_page.add_style_tag(content="*,*::before,*::after{transition:none !important}")
        seeded_page.wait_for_timeout(350)
        _settle_animations(seeded_page)
        # 🔴 «두 감사를 다» 돌린다. 처음엔 토큰 글자(--text-2/3)만 봤는데, 이 화면에서
        #    고친 것은 «accent 를 글자로 쓰는 링크» 였다 — 그 축을 안 보고 있었다.
        #    뮤테이션(`.admin-link` 를 --accent 로 되돌림)이 green 으로 통과해 드러났다.
        for js, names in ((_TOKEN_TEXT_AUDIT_JS, ("--text-2", "--text-3")),
                          (_ACCENT_TEXT_AUDIT_JS, ("--accent-text",))):
            res = seeded_page.evaluate(js)
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
