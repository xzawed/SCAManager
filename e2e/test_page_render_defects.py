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
_COUNTUP_WATCH_JS = r"""
(() => {
  const W = window.__cu = {server: null, negative: []};
  document.addEventListener('DOMContentLoaded', () => {
    W.server = Array.from(document.querySelectorAll(
      '.kpi__value, .repo-card__score, .detail-hero__num, .reason-row__count, .freq-row__count, .breakdown__val, [data-count]'
    )).map(e => e.textContent.replace(/\s+/g, ' ').trim());
  });
  new MutationObserver(ms => { for (const m of ms) {
    const v = m.type === 'characterData' ? m.target.nodeValue : null;
    if (v && /^\s*-\d/.test(v)) W.negative.push(v.trim().slice(0, 12));
  } }).observe(document, {subtree: true, characterData: true});
})();
"""


def test_countup_lands_on_the_server_text_and_never_goes_negative(
        browser_instance, live_server, seeded_analysis, merge_history):
    """🔴 카운트업이 끝나면 서버가 쓴 글자와 같고(소수 자릿수 포함), 도중에 음수를 그리지 않는다."""
    problems, measured = [], 0
    ctx = browser_instance.new_context(base_url=live_server, viewport={"width": 1440, "height": 900})
    ctx.add_init_script(script=_COUNTUP_WATCH_JS)
    for path in ("/", "/dashboard", "/dashboard?days=30", "/dashboard?days=30", "/", "/"):
        page = ctx.new_page()
        page.goto(path, wait_until="load")
        page.wait_for_timeout(600)
        # 카운트업은 «화면에 들어올 때» 시작한다 — 아래쪽 대상까지 지나가게 한 뒤 끝나길 기다린다.
        # Count-up starts on entering the viewport: scroll past every target, then let it finish.
        page.evaluate("""async () => {
            const step = Math.max(200, Math.floor(innerHeight * 0.6));
            for (let y = 0; y < document.body.scrollHeight; y += step) {
                scrollTo(0, y); await new Promise(r => setTimeout(r, 250)); }
            scrollTo(0, 0); }""")
        page.wait_for_timeout(1800)
        res = page.evaluate("""() => ({server: window.__cu.server, negative: window.__cu.negative,
            final: Array.from(document.querySelectorAll(
              '.kpi__value, .repo-card__score, .detail-hero__num, .reason-row__count, .freq-row__count, .breakdown__val, [data-count]'
            )).map(e => e.textContent.replace(/\\s+/g, ' ').trim())})""")
        page.close()
        measured += len(res["server"] or [])
        if res["negative"]:
            problems.append(f"{path}: 음수 프레임 {res['negative'][:3]}")
        diff = [(a, b) for a, b in zip(res["server"] or [], res["final"]) if a != b]
        if diff:
            problems.append(f"{path}: 끝값이 서버 표기와 다르다 {diff[:4]}")
    ctx.close()
    assert measured, "카운트업 대상을 0개 쟀다 — 선택자가 화면과 어긋났다(공허한 초록)"
    assert not problems, "카운트업:\n  " + "\n  ".join(problems)


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


# 개요 카드 한 장에서 등급 자리·막대 자리·사유 문구를 잰다.
# Measures the grade slot, the bar slot and the reason labels of one overview card.
_UNVERIFIED_CARD_JS = r"""c => {
  const q = s => c.querySelector(s), cr = c.getBoundingClientRect();
  const chip = q('.grade'), bar = q('.score-bar'), lab = q('.repo-card__unverified'), off = q('.repo-card__ai-off');
  const row = lab ? lab.closest('.repo-card__score-row') : null;
  const inside = el => { if (!el) return null; const r = el.getBoundingClientRect();
    return r.width > 0 && r.left >= cr.left - 1 && r.right <= cr.right + 1 && r.top >= cr.top - 1 && r.bottom <= cr.bottom + 1; };
  return {lang: document.documentElement.lang,
          chip: chip ? chip.textContent.trim() : null, chipCls: chip ? chip.className : null,
          barCls: bar ? bar.className : null, fill: bar ? getComputedStyle(bar, '::after').width : null,
          label: lab ? lab.innerText.trim() : null, labelInside: inside(lab),
          off: off ? off.innerText.trim() : null, offInside: inside(off),
          score: !!q('.repo-card__score'),
          overflow: Math.max(c.scrollWidth - c.clientWidth, row ? row.scrollWidth - row.clientWidth : 0)};
}"""


def test_an_unverified_repo_card_says_why_it_has_no_grade(browser_instance, live_server, unverified_repo):
    """🔴 분석은 있는데 검증된 점수가 없는 리포(AI 리뷰 꺼짐) — 등급·막대 자리가 비지 않고 이유를 말한다.

    운영(2026-10-17): AI 리뷰 토글을 끈 뒤 추가한 리포 3개(분석 196·590·5회)의 카드가 등급 칩도
    점수 막대도 없이 «N회» 한 줄이었다. 데스크톱·모바일에서 중립 칩 «—»(등급 색 없음) · 빈 막대 ·
    «검증된 점수 없음 · AI 리뷰 꺼짐» 이 카드 안에 보이는지 잰다.
    """
    from src.i18n.loader import get_text  # noqa: PLC0415

    problems = []
    for vw, vh in ((1440, 900), (375, 812)):
        ctx = browser_instance.new_context(base_url=live_server, viewport={"width": vw, "height": vh},
                                           locale="ko-KR")
        page = ctx.new_page()
        page.goto("/", wait_until="load")
        card = page.locator(f'a.repo-card[href="/repos/{unverified_repo}"]')
        card.scroll_into_view_if_needed()
        page.wait_for_timeout(900)
        got = card.evaluate(_UNVERIFIED_CARD_JS)
        ctx.close()
        lang = got["lang"] or "ko"
        keys = ("overview.no_verified_score", "overview.ai_review_off")
        want = tuple(get_text(k, lang) for k in keys)
        if not all(w and w != k for w, k in zip(want, keys)):
            problems.append(f"{vw}px 번역 문구가 없다({lang}): {want!r}")
        if got["chip"] != "—" or (got["chipCls"] or "").split() != ["grade"]:
            problems.append(f"{vw}px 등급 자리: {got['chip']!r} class={got['chipCls']!r} (중립 «—» 여야 한다)")
        if (got["barCls"] or "").split() != ["score-bar"] or got["fill"] != "0px":
            problems.append(f"{vw}px 막대 자리: class={got['barCls']!r} 채움={got['fill']!r} (빈 막대여야 한다)")
        if (got["label"], got["off"]) != want:
            problems.append(f"{vw}px 사유: {(got['label'], got['off'])!r} ≠ {want!r}")
        if not (got["labelInside"] and got["offInside"]):
            problems.append(f"{vw}px 사유 문구가 카드 밖이거나 안 보인다: {got}")
        if got["score"]:
            problems.append(f"{vw}px 검증 점수가 없는데 점수 숫자가 그려졌다")
        if got["overflow"] > 1:
            problems.append(f"{vw}px 카드 글자가 넘친다({got['overflow']}px)")
    assert not problems, "검증 점수 없는 리포 카드:\n  " + "\n  ".join(problems)
