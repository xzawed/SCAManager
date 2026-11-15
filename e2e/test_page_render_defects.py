"""화면별 렌더링 결함 (2026-10-16 화면별 렌더링 검수) — 실제로 그려진 화면에서 잰다.

1. repos 리포트 «점수 트렌드» 캔버스가 끝없이 자랐다(12초에 데스크톱 4,738px · 모바일 15,482px).
2. 리포 상세 이력 표가 점수 없는 분석(AI 실패 — 점수 NULL)을 기본 필터에서도 늘 숨겼다.
3. 랜딩 로그인 실패 배너가 모바일에서 화면 절반 폭(~180px)으로 접혀 히어로 제목을 덮었다.
4. 언어 전환(body 만 교체) 뒤 `<html lang>` 이 새로고침 전까지 이전 언어였다.
5. 카운트업 끝값이 서버 표기와 달랐고(«50.0%» → «50%»), 첫 프레임이 음수일 때가 있었다.
6. (2026-10-17 신고) 검증된 점수가 없는 리포(AI 리뷰 꺼짐)의 개요 카드가 등급·막대 없이 비었다.

Rendering defects found by the 2026-10-16 page-by-page review, measured on painted pages.
"""
from __future__ import annotations

import os
import re
from urllib.parse import quote


def _canvas_heights(page) -> dict:
    return page.evaluate("""() => Object.fromEntries(Array.from(document.querySelectorAll('canvas'))
        .filter(c => c.checkVisibility()).map(c => [c.id || '?', Math.round(c.getBoundingClientRect().height)]))""")


def test_chart_canvases_keep_a_fixed_height(browser_instance, live_server, seeded_analysis, paginated_history):
    """🔴 차트 캔버스 높이가 시간이 지나도 그대로고 상식적인 높이다 — 자유 높이 차트가 «자라지» 않는다.

    Chart canvases keep a stable, sane height over time; nothing grows without bound.
    """
    paths = ["/dashboard", f"/dashboard?mode=repos&repo={quote('owner/testrepo', safe='')}",
             "/repos/owner/testrepo", f"/repos/owner/testrepo/analyses/{seeded_analysis}",
             "/repos/owner/testrepo/insights"]
    problems, seen = [], set()
    for vw, vh in ((1440, 900), (375, 812)):
        ctx = browser_instance.new_context(base_url=live_server, viewport={"width": vw, "height": vh})
        page = ctx.new_page()
        for path in paths:
            page.goto(path, wait_until="load")
            page.wait_for_timeout(700)
            first = _canvas_heights(page)
            page.wait_for_timeout(2500)
            later = _canvas_heights(page)
            seen |= set(later)
            for cid, h in later.items():
                if abs(h - first.get(cid, h)) > 2 or h > 420:
                    problems.append(f"{vw}px {path} #{cid}: {first.get(cid)}px → {h}px")
        ctx.close()
    # 🔴 대조군 — 고친 그 차트를 실제로 쟀는가(안 그려졌으면 «위반 0» 은 공허하다).
    assert "repoTrendChart" in seen, f"repos 리포트 차트가 그려지지 않았다 — 잰 캔버스: {sorted(seen)}"
    assert not problems, "차트 캔버스가 자라거나 지나치게 높다:\n  " + "\n  ".join(problems)


def test_unscored_analyses_are_listed_until_the_score_range_is_narrowed(
        seeded_page, base_url, analysis_variants):
    """🔴 점수 없는 분석은 기본 필터에서 보이고(점수 «—»·중립 배지), 점수 범위를 좁히면 빠진다."""
    seeded_page.goto(f"{base_url}/repos/{quote('owner/gatedrepo', safe='')}")
    seeded_page.wait_for_timeout(600)
    rows = seeded_page.evaluate("""() => Array.from(document.querySelectorAll('#analysisTable tr.analysis-row'))
        .map(tr => { const g = tr.querySelector('span.grade'); const s = tr.querySelector('.score-val');
                     return {score: s ? s.textContent.trim() : null, cls: s ? s.className : '',
                             grade: g ? g.textContent.trim() : null, gcls: g ? g.className : ''}; })""")
    unscored = [r for r in rows if r["score"] == "—"]
    ungraded = [r for r in rows if r["grade"] == "—"]
    # 점수·등급 NULL 행(analysis_variants)이 반드시 있다. 점수만 NULL 이고 등급 F 가 남은 옛 모양
    # (absence_analysis)은 등급대로 F 다 — 그래서 «등급 —» 행과 «점수 —» 행을 따로 본다.
    assert unscored and ungraded, f"기본 필터에서 점수·등급 없는 분석이 표에 없다 — 행: {rows[:5]}"
    for r in ungraded:
        assert "grade--" not in r["gcls"], f"등급 없는 행에 등급 색 배지: {r}"
    for r in unscored:
        assert r["cls"].split() == ["score-val"], f"점수 없는 행의 «—» 에 점수 색이 붙었다: {r}"
    count = seeded_page.locator("#historyCount").inner_text()
    assert "/" not in count, f"필터를 안 걸었는데 머리 문구가 «걸러진 수» 다: {count!r}"
    # 점수 범위를 1 부터로 좁히면 점수 없는 행은 빠진다.
    seeded_page.evaluate("""() => { const el = document.getElementById('scoreMin'); el.value = '1';
                                     el.dispatchEvent(new Event('input', {bubbles: true})); }""")
    seeded_page.wait_for_timeout(400)
    narrowed = seeded_page.evaluate("""() => Array.from(document.querySelectorAll('#analysisTable .score-val'))
        .map(s => s.textContent.trim())""")
    assert "—" not in narrowed, f"점수 범위를 좁혔는데 점수 없는 행이 남았다: {narrowed}"


def test_login_error_banner_fits_a_phone(anonymous_page, base_url):
    """🔴 375px 에서 로그인 실패 배너가 화면 폭을 쓰고(한 단어씩 줄바꿈 금지), 면이 불투명하다."""
    anonymous_page.set_viewport_size({"width": 375, "height": 812})
    anonymous_page.goto(f"{base_url}/?error=oauth_failed")
    anonymous_page.wait_for_timeout(500)
    box = anonymous_page.locator("#authErrorBanner").bounding_box()
    assert box, "로그인 실패 배너가 그려지지 않았다"
    assert box["width"] >= 0.85 * (375 - 32), f"배너 폭이 좁다({box['width']:.0f}px) — 글자가 한 단어씩 접힌다"
    assert box["height"] <= 110, f"배너 높이 {box['height']:.0f}px — 문구가 여러 줄로 쪼개졌다"
    assert box["x"] >= 15 and box["x"] + box["width"] <= 375 - 15, f"배너가 화면 가장자리를 넘었다: {box}"
    image = anonymous_page.evaluate(
        "() => getComputedStyle(document.getElementById('authErrorBanner')).backgroundImage")
    color = anonymous_page.evaluate(
        "() => getComputedStyle(document.getElementById('authErrorBanner')).backgroundColor")
    assert "gradient" in image and not color.endswith(", 0)") and color != "rgba(0, 0, 0, 0)", (
        f"배너 면이 불투명 카드 면 위 틴트가 아니다(image={image!r}, color={color!r}) — 아래 제목이 비친다")


def test_language_switch_updates_the_html_lang(seeded_page, base_url):
    """🔴 언어를 바꾸면 새로고침 전에도 `<html lang>` 이 새 언어다(body 만 교체되는 경로).

    🔴 전환은 사용자 행(`users.preferred_language`)도 바꾼다 — 관리자 운영 화면의 언어 분포가
       뒤 시험에서 달라지지 않게 원래 값으로 되돌린다(쿠키는 이 시험의 컨텍스트와 함께 사라진다).
    """
    from sqlalchemy import create_engine, text  # noqa: PLC0415

    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as conn:
        original = conn.execute(text("SELECT preferred_language FROM users WHERE id = 1")).scalar()
    try:
        seeded_page.goto(f"{base_url}/dashboard")
        seeded_page.wait_for_timeout(500)
        before = seeded_page.evaluate("() => document.documentElement.lang")
        target = "ja" if before != "ja" else "en"
        with seeded_page.expect_response(lambda r: "preferred-language" in r.url) as resp:
            seeded_page.click("#langToggle")
            seeded_page.click(f".lang-option[data-lang='{target}']")
        assert resp.value.ok, f"언어 저장 응답 {resp.value.status} — 전환 자체가 안 됐다"
        seeded_page.wait_for_timeout(1500)
        heading = seeded_page.locator("nav a.nav-link[href='/dashboard']").inner_text()
        lang = seeded_page.evaluate("() => document.documentElement.lang")
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE users SET preferred_language = :v WHERE id = 1"), {"v": original})
        engine.dispose()
    assert heading.strip() == {"ja": "ダッシュボード", "en": "Dashboard"}[target], (
        f"본문이 {target} 로 바뀌지 않았다({heading!r}) — 전환 경로 자체를 재지 못했다")
    assert lang == target, f"언어를 {target} 로 바꿨는데 <html lang> 이 {lang!r} 로 남았다"


# 카운트업 대상 = effects.js `setupCountUp` 의 선택자 + base.html `_initKpiCountup` 의 `[data-count]`.
# Count-up targets: effects.js setupCountUp selectors plus base.html's [data-count] elements.
_COUNTUP_TARGETS = ('.kpi__value, .repo-card__score, .detail-hero__num, .reason-row__count, '
                    '.freq-row__count, .breakdown__val, [data-count]')

# 도중에 그려진 값만 본다(음수 프레임). 서버 글자는 응답 HTML 에서 읽는다 — 아래 시험 주석.
# Watches the frames in between (negative values); the server text comes from the response HTML.
_COUNTUP_WATCH_JS = r"""
(() => {
  const W = window.__cu = {negative: []};
  new MutationObserver(ms => { for (const m of ms) {
    const v = m.type === 'characterData' ? m.target.nodeValue : null;
    if (v && /^\s*-\d/.test(v)) W.negative.push(v.trim().slice(0, 12));
  } }).observe(document, {subtree: true, characterData: true});
})();
"""

# 같은 선택자로 «응답 HTML»(스크립트가 손대기 전)과 «지금 화면» 의 글자를 읽는다.
# Reads the same targets from the response HTML (before any script ran) and from the live page.
_COUNTUP_READ_JS = """([html, sel]) => {
    const read = root => Array.from(root.querySelectorAll(sel)).map(e => e.textContent.replace(/\\s+/g, ' ').trim());
    return {server: read(new DOMParser().parseFromString(html, 'text/html')), final: read(document),
            negative: window.__cu.negative};
}"""


def test_countup_lands_on_the_server_text_and_never_goes_negative(
        browser_instance, live_server, seeded_analysis, merge_history):
    """🔴 카운트업이 끝나면 서버가 쓴 글자와 같고(소수 자릿수 포함), 도중에 음수를 그리지 않는다."""
    problems, measured = [], 0
    ctx = browser_instance.new_context(base_url=live_server, viewport={"width": 1440, "height": 900})
    ctx.add_init_script(script=_COUNTUP_WATCH_JS)
    for path in ("/", "/dashboard", "/dashboard?days=30", "/dashboard?days=30", "/", "/"):
        page = ctx.new_page()
        # 🔴 서버 글자는 응답 HTML 에서 읽는다. DOMContentLoaded 에서 읽으면 늦을 때가 있다 — 대시보드의
        #    `[data-count]` 카운트업은 파싱 중 인라인 스크립트에서 시작해, 그 사이 그림 갱신이 끼면 첫 틱
        #    («0.0»)이 DOMContentLoaded 보다 먼저 쓰인다(#1763 실측: 첫 틱 87.0ms · DOMContentLoaded 88.8ms).
        #    그러면 끝값이 맞아도 비교 기준이 «0.0» 이 돼 실패했다.
        # Read the server text from the response: the dashboard count-up starts from an inline script
        # during parsing, so its first frame can land before DOMContentLoaded.
        resp = page.goto(path, wait_until="load")
        page.wait_for_timeout(600)
        # 카운트업은 «화면에 들어올 때» 시작한다 — 아래쪽 대상까지 지나가게 한 뒤 끝나길 기다린다.
        # Count-up starts on entering the viewport: scroll past every target, then let it finish.
        page.evaluate("""async () => {
            const step = Math.max(200, Math.floor(innerHeight * 0.6));
            for (let y = 0; y < document.body.scrollHeight; y += step) {
                scrollTo(0, y); await new Promise(r => setTimeout(r, 250)); }
            scrollTo(0, 0); }""")
        page.wait_for_timeout(1800)
        res = page.evaluate(_COUNTUP_READ_JS, [resp.text(), _COUNTUP_TARGETS])
        page.close()
        measured += len(res["server"])
        if res["negative"]:
            problems.append(f"{path}: 음수 프레임 {res['negative'][:3]}")
        # 개수가 다르면 짝이 어긋나 엉뚱한 쌍을 비교한다 — 먼저 그것부터 알린다.
        # A count mismatch would pair the wrong elements; report it first.
        if len(res["server"]) != len(res["final"]):
            problems.append(f"{path}: 대상 수가 다르다 — 응답 {len(res['server'])} · 화면 {len(res['final'])}")
        diff = [(a, b) for a, b in zip(res["server"], res["final"]) if a != b]
        if diff:
            problems.append(f"{path}: 끝값이 서버 표기와 다르다 (서버, 끝) {diff[:4]}")
    ctx.close()
    assert measured, "카운트업 대상을 0개 쟀다 — 선택자가 화면과 어긋났다(공허한 초록)"
    assert not problems, "카운트업:\n  " + "\n  ".join(problems)


# 대시보드 응답에서 카운트업 대상 둘을 1000 이상으로 바꾼다 — 시드 최대값(27)으로는 자릿수 구분 분기를 못 연다(회고 원장
# L04 P2-63). `[data-count]`(base.html countUp) 하나와 `.freq-row__count`(effects.js) 하나.
# Lift two count-up targets in the dashboard response above 1000: the seed's maximum (27) never opens the grouping branch.
_BIG_TARGETS = (
    (re.compile(r'(<span class="t-num" data-count=")(\d+)(">)(\d+)(</span>)'), r"\g<1>1234\g<3>1234\g<5>"),
    (re.compile(r'(<span class="freq-row__count">)(\d+)(</span>)'), r"\g<1>1234\g<3>"),
)


def test_countup_lands_on_the_server_text_above_a_thousand(browser_instance, live_server, seeded_analysis):
    """🔴 1000 이상도 끝값이 서버 글자 그대로다 — `toLocaleString()` 은 브라우저 로케일로 자릿수를 묶어 «1234» 를
    «1,234»(de 계열은 «1.234»)로 끝냈다(회고 원장 L04 P2-63). 독일어 로케일 브라우저로 잰다.
    The final text equals the server's even above 1000; toLocaleString grouped it by the browser locale."""
    ctx = browser_instance.new_context(base_url=live_server, viewport={"width": 1440, "height": 900}, locale="de-DE")
    replaced = []

    def lift(route):
        resp = route.fetch()
        body = resp.text()
        for pattern, repl in _BIG_TARGETS:
            body, n = pattern.subn(repl, body, count=1)
            replaced.append(n)
        route.fulfill(response=resp, body=body)

    page = ctx.new_page()
    page.route("**/dashboard", lift)
    try:
        resp = page.goto("/dashboard", wait_until="load")
        page.evaluate("""async () => {
            const step = Math.max(200, Math.floor(innerHeight * 0.6));
            for (let y = 0; y < document.body.scrollHeight; y += step) {
                scrollTo(0, y); await new Promise(r => setTimeout(r, 250)); }
            scrollTo(0, 0); }""")
        page.wait_for_timeout(1800)
        page.evaluate("() => { window.__cu = window.__cu || {negative: []}; }")
        res = page.evaluate(_COUNTUP_READ_JS, [resp.text(), _COUNTUP_TARGETS])
    finally:
        ctx.close()
    assert replaced == [1, 1], f"1000 이상으로 바꿀 대상을 못 찾았다(바꾼 수 {replaced}) — 재지 못했다"
    big = [(a, b) for a, b in zip(res["server"], res["final"]) if "1234" in a]
    # 부모 `.kpi__value` 도 같은 숫자를 담으므로 둘 이상 / the parent .kpi__value carries the same number too
    assert len(big) >= 2, f"바꾼 대상 둘을 화면에서 못 짝지었다: {big}"
    assert all(a == b for a, b in big), f"1000 이상의 끝값이 서버 글자와 다르다 (서버, 끝) {big}"


# 동작 줄이기에서 카운트업 대상의 글자를 프레임마다 모은다 — 위아래로 훑어 화면 안 진입 시점도 지나간다.
# Under reduced motion, collect every count-up target's text on every frame while scrolling through the page.
_COUNTUP_FRAMES_JS = r"""async (sel) => {
  const seen = [];
  const sample = () => document.querySelectorAll(sel).forEach((e, i) => {
    (seen[i] = seen[i] || new Set()).add(e.textContent.replace(/\s+/g, ' ').trim()); });
  const frame = () => new Promise(r => requestAnimationFrame(r));
  const t0 = performance.now();
  const step = Math.max(200, Math.floor(innerHeight * 0.6));
  for (let y = 0; y < document.body.scrollHeight; y += step) { scrollTo(0, y); for (let k = 0; k < 8; k++) { sample(); await frame(); } }
  scrollTo(0, 0);
  while (performance.now() - t0 < 2500) { sample(); await frame(); }
  return seen.map(s => Array.from(s));
}"""


def test_reduced_motion_never_paints_an_intermediate_countup_value(browser_instance, live_server, seeded_analysis):
    """🔴 «동작 줄이기» 에서는 카운트업 대상이 처음부터 끝까지 서버 글자 하나만 칠한다 (회고 원장 L04 P2-62).

    대시보드 KPI(base.html countUp)는 이 설정을 보지 않고 약 1.4초 동안 값 22개를 그렸다. #1779 의 계기
    (`getAnimations`)는 rAF 로 바꾸는 글자를 원리적으로 못 봐 초록이었다 — 여기서는 프레임마다 글자를 모은다.
    Under reduced motion every count-up target paints only the server's text; this samples text on every frame.
    """
    ctx = browser_instance.new_context(base_url=live_server, viewport={"width": 1440, "height": 900},
                                       reduced_motion="reduce")
    problems, measured = [], 0
    try:
        for path in ("/dashboard", "/"):
            page = ctx.new_page()
            resp = page.goto(path, wait_until="domcontentloaded")
            frames = page.evaluate(_COUNTUP_FRAMES_JS, _COUNTUP_TARGETS)
            page.evaluate("() => { window.__cu = window.__cu || {negative: []}; }")
            server = page.evaluate(_COUNTUP_READ_JS, [resp.text(), _COUNTUP_TARGETS])["server"]
            page.close()
            measured += len(server)
            if len(frames) != len(server):
                problems.append(f"{path}: 대상 수가 다르다 — 응답 {len(server)} · 화면 {len(frames)}")
                continue
            for i, (want, painted) in enumerate(zip(server, frames)):
                extra = [v for v in painted if v != want]
                if extra:
                    problems.append(f"{path} #{i}: 서버 글자 {want!r} 말고도 {extra[:4]} 를 칠했다")
    finally:
        ctx.close()
    assert measured, "카운트업 대상을 0개 쟀다 — 선택자가 화면과 어긋났다(공허한 초록)"
    assert not problems, "동작 줄이기에서 카운트업이 돈다:\n  " + "\n  ".join(problems)

def test_a_missing_page_opened_in_the_browser_is_an_error_page(seeded_page, base_url):
    """🔴 브라우저로 없는 리포 주소를 열면 JSON 원문이 아니라 nav 가 있는 오류 화면이다(상태 404 유지)."""
    resp = seeded_page.goto(f"{base_url}/repos/{quote('owner/no-such-repo', safe='')}")
    assert resp.status == 404, f"상태가 {resp.status} — 404 를 유지해야 한다"
    assert resp.headers.get("content-type", "").startswith("text/html"), resp.headers.get("content-type")
    body = seeded_page.locator("body").inner_text()
    assert '"detail"' not in body, f"브라우저에 JSON 원문이 보인다: {body[:120]!r}"
    assert seeded_page.locator("nav").count() == 1, "base 를 상속한 화면이 아니다(nav 없음)"
    assert seeded_page.locator(".error-page h1").is_visible(), "오류 제목이 보이지 않는다"
    assert seeded_page.locator(".error-page a[href='/']").count() == 1, "개요로 돌아가는 길이 없다"



def test_overview_link_on_an_error_page_opens_the_landing_with_its_own_styles(anonymous_page, base_url):
    """🔴 로그인 안 한 방문자가 오류 화면의 «개요로 가기» 를 누르면 랜딩이 «자기 문서» 로 열린다 (회고 원장 L04 P2-60).

    랜딩은 자기 `<head>`(CSS)를 가진 독립 페이지라, hx-boost 가 body 만 끼우면 오류 화면의 head 아래에서 CSS 없이 그려졌다.
    전체 이동이면 새 문서가 읽혀 이동 전 창에 심은 표식이 사라진다 — 그것으로 «body 만 끼웠는가» 를 가른다.
    The landing is a standalone page: a boosted body-only swap rendered it without its own styles.
    """
    page = anonymous_page
    resp = page.goto(f"{base_url}/no-such-page-for-e2e")
    assert resp.status == 404 and page.locator(".error-page a[href='/']").count() == 1, (
        f"오류 화면이 아니다(상태 {resp.status}) — 재지 못했다")
    page.evaluate("() => { window.__beforeNav = 1; }")
    page.locator(".error-page a[href='/']").click()
    page.wait_for_load_state("load")
    page.wait_for_timeout(800)
    got = page.evaluate("""() => ({marker: window.__beforeNav === 1, path: location.pathname,
                                  boostBody: document.body.getAttribute('hx-boost')})""")
    assert got["path"] == "/", f"개요로 가지 않았다: {got}"
    assert not got["marker"], f"랜딩을 body 만 끼워 그렸다(이동 전 창 그대로): {got}"
    assert got["boostBody"] is None, f"랜딩 문서가 아니다(body 가 앱 화면의 것): {got}"


def test_boosted_link_to_a_missing_page_shows_the_error_page_and_ends_the_progress_bar(seeded_page, base_url):
    """🔴 앱 안 boost 링크가 404 를 받으면 오류 화면이 보이고 진행 막대가 끝난다 (회고 원장 L04 P2-60).

    htmx 는 `Accept: text/html` 을 보내지 않아 서버가 JSON 404 를 주고, htmx 기본값은 오류 응답을 바꿔 넣지 않는다 —
    화면은 그대로인 채 진행 막대가 끝없이 돌았다(막대는 `htmx:afterSettle` 에서만 끝난다).
    A boosted link that gets a 404 must show the error page and stop the progress bar.
    """
    page = seeded_page
    page.goto(f"{base_url}/dashboard")
    page.wait_for_timeout(500)
    page.evaluate("""() => { const a = document.createElement('a'); a.id = 'e2eMissing';
        a.href = '/repos/' + encodeURIComponent('owner/no-such-repo-e2e'); a.textContent = 'missing';
        document.querySelector('.container').appendChild(a); htmx.process(a); }""")
    # 실제 화면의 링크처럼 hx-boost 가 걸렸는지 — 안 걸리면 평범한 이동이라 공허한 초록이다(첫 판 실측).
    # The link must really be boosted like the app's own links; otherwise this is a plain navigation.
    boosted = page.evaluate("() => { const d = document.getElementById('e2eMissing')['htmx-internal-data']; return !!(d && d.boosted); }")
    assert boosted, "심은 링크에 hx-boost 가 안 걸렸다 — 재지 못했다"
    page.locator("#e2eMissing").click()
    page.wait_for_timeout(2500)
    got = page.evaluate("""() => ({errorPage: !!document.querySelector('.error-page h1'),
        loading: !!document.querySelector('#page-progress.is-loading'), path: location.pathname})""")
    assert got["errorPage"], f"404 를 받았는데 오류 화면이 안 보인다: {got}"
    assert not got["loading"], f"진행 막대가 끝나지 않았다: {got}"

# 개요 카드 한 장에서 등급 칩·막대·점수·표식을 잰다.
# Measures the grade chip, the bar, the score and the markers of one overview card.
_RECORDED_CARD_JS = r"""c => {
  const q = s => c.querySelector(s), cr = c.getBoundingClientRect();
  const chip = q('.grade'), bar = q('.score-bar'), score = q('.repo-card__score');
  const mark = q('.repo-card__unverified'), off = q('.repo-card__ai-off');
  const reason = mark ? mark.closest('.repo-card__reason') : null;
  const inside = el => { if (!el) return null; const r = el.getBoundingClientRect();
    return r.width > 0 && r.left >= cr.left - 1 && r.right <= cr.right + 1 && r.top >= cr.top - 1 && r.bottom <= cr.bottom + 1; };
  const track = bar ? bar.getBoundingClientRect().width : 0;
  const fill = bar ? parseFloat(getComputedStyle(bar, '::after').width) || 0 : 0;
  return {lang: document.documentElement.lang,
          chip: chip ? chip.textContent.trim() : null, chipCls: chip ? chip.className : null,
          barCls: bar ? bar.className : null, fillRatio: track ? fill / track : null,
          score: score ? score.textContent.trim() : null,
          mark: mark ? mark.innerText.trim() : null, markInside: inside(mark),
          off: off ? off.innerText.trim() : null, offInside: inside(off),
          noScore: !!q('.repo-card__no-score'),
          overflow: Math.max(c.scrollWidth - c.clientWidth, reason ? reason.scrollWidth - reason.clientWidth : 0)};
}"""


def test_an_unverified_repo_card_shows_its_recorded_grade(browser_instance, live_server, unverified_repo):
    """🔴 검증된 분석이 없는 리포(AI 리뷰 꺼짐)도 기록된 점수로 등급·막대를 그리고 «미검증 포함» 을 단다.

    운영(2026-10-17): AI 리뷰를 끈 뒤 추가한 리포 3개(분석 196·590·5회)의 카드에 등급·막대가 없었다.
    사용자 결정 = 자동 채점 여부와 상관없이 기록된 점수로 등급과 그래프를 같이 보인다.
    데스크톱·모바일에서 등급 칩(색 있음) · 평균만큼 찬 막대 · 점수 · «미검증 포함 · AI 리뷰 꺼짐» 이
    카드 안에 보이는지 잰다. 시드 = 70점 분석 2회.
    """
    from playwright.sync_api import expect  # noqa: PLC0415

    from src.i18n.loader import get_text  # noqa: PLC0415
    from src.scorer.calculator import calculate_grade  # noqa: PLC0415

    grade = calculate_grade(70)
    problems = []
    for vw, vh in ((1440, 900), (375, 812)):
        ctx = browser_instance.new_context(base_url=live_server, viewport={"width": vw, "height": vh},
                                           locale="ko-KR")
        page = ctx.new_page()
        page.goto("/", wait_until="load")
        card = page.locator(f'a.repo-card[href="/repos/{unverified_repo}"]')
        card.scroll_into_view_if_needed()
        # 카운트업(0 → 70)이 끝날 때까지 — 끝나기 전 값을 재면 막대·점수가 덜 찬 채 읽힌다.
        expect(card.locator(".repo-card__score")).to_have_text(re.compile(r"^70\b"), timeout=5000)
        page.wait_for_timeout(600)
        got = card.evaluate(_RECORDED_CARD_JS)
        ctx.close()
        lang = got["lang"] or "ko"
        keys = ("overview.includes_unverified", "overview.ai_review_off")
        want = tuple(get_text(k, lang) for k in keys)
        if not all(w and w != k for w, k in zip(want, keys)):
            problems.append(f"{vw}px 번역 문구가 없다({lang}): {want!r}")
        if got["chip"] != grade or (got["chipCls"] or "").split() != ["grade", f"grade--{grade.lower()}"]:
            problems.append(f"{vw}px 등급 칩: {got['chip']!r} class={got['chipCls']!r} (기록된 평균 70 의 {grade})")
        if (got["barCls"] or "").split() != ["score-bar", f"score-bar--{grade.lower()}"]:
            problems.append(f"{vw}px 막대 등급: class={got['barCls']!r}")
        if got["fillRatio"] is None or abs(got["fillRatio"] - 0.70) > 0.03:
            problems.append(f"{vw}px 막대가 평균만큼 차지 않았다: 채움 비율 {got['fillRatio']!r} (0.70)")
        if (got["mark"], got["off"]) != want:
            problems.append(f"{vw}px 표식: {(got['mark'], got['off'])!r} ≠ {want!r}")
        if not (got["markInside"] and got["offInside"]):
            problems.append(f"{vw}px 표식이 카드 밖이거나 안 보인다: {got}")
        if got["noScore"]:
            problems.append(f"{vw}px 점수가 있는데 «기록된 점수 없음» 이 그려졌다")
        if got["overflow"] > 1:
            problems.append(f"{vw}px 카드 글자가 넘친다({got['overflow']}px)")
    assert not problems, "검증된 분석이 없는 리포 카드:\n  " + "\n  ".join(problems)
