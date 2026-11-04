r"""스타일시트 무결성 — Chromium 이 저자가 쓴 규칙을 «전부» 들고 있는가.

두 판정자를 맞댄다. 저자 구조 = `tests/unit/ui/_css_structure.py` 의 엄격 스캐너가 원문에서 읽은
블록 목록(깊이 · 종류 · 셀렉터의 클래스/id), 브라우저 = 같은 원문을 Chromium 에 넣은 CSSOM.

🔴 왜 e2e 인가 — 단위 스캐너는 «구조» 만 본다. 셀렉터 오타(`:hovr`) · 모르는 at-rule ·
   서술자가 빠진 `@property` 처럼 구조는 멀쩡한데 브라우저가 버리는 규칙은 브라우저만 안다.
   반대로 브라우저가 «적법하게» 복구한 깨짐(`}` 누락 → 뒤 규칙이 중첩 규칙)은 스캐너가 안다.
🔴 화면 시험은 «받았는가» 를 본다 — CSP·404·교차 출처면 `sheet` 가 없거나 `cssRules` 가 막힌다.
   앱이 자기 CSP 로 자기 웹폰트 시트를 막았을 때도, 주석 하나가 규칙을 죽였을 때도 진단은
   CSSOM 이 했는데 남은 것은 텍스트 가드뿐이었다(`tests/unit/ui/test_csp_external_asset_parity.py`).
   이 파일이 그 계기다.

Stylesheet integrity: Chromium's CSSOM must hold every rule the author wrote, and every
stylesheet a page links must arrive readable and whole.
"""
from __future__ import annotations

from tests.unit.ui._css_structure import (authored_sources, chromium_expected, chromium_kept,
                                          scan, selector_signature, template_links)

_ROOT_CSS = "/static/css/"
_BUILT = "/static/css/dist/"

_WALK_JS = r"""
const KIND = {CSSStyleRule: 'style', CSSMediaRule: 'media', CSSSupportsRule: 'supports',
  CSSKeyframesRule: 'keyframes', CSSKeyframeRule: 'keyframe', CSSFontFaceRule: 'font-face',
  CSSLayerBlockRule: 'layer', CSSLayerStatementRule: 'layer-statement', CSSImportRule: 'import',
  CSSPropertyRule: 'property', CSSContainerRule: 'container', CSSPageRule: 'page',
  CSSStartingStyleRule: 'starting-style', CSSScopeRule: 'scope',
  CSSCounterStyleRule: 'counter-style', CSSNamespaceRule: 'namespace'};
const walk = (rules, depth, out) => {
  for (const r of rules) {
    const name = r.constructor.name;
    // 선언이 중첩 규칙 뒤에 오면 Chromium 이 만드는 껍데기 — 저자가 쓴 블록이 아니다.
    if (name === 'CSSNestedDeclarations') continue;
    out.push([depth, KIND[name] || ('?' + name), r.selectorText || '']);
    if (r.cssRules) walk(r.cssRules, depth + 1, out);
  }
  return out;
};
"""

_PARSE_JS = "(css) => {" + _WALK_JS + r"""
  const el = document.createElement('style');
  el.textContent = css;
  document.head.appendChild(el);
  const out = walk(el.sheet.cssRules, 0, []);
  el.remove();
  return out;
}"""

_SERVED_JS = "() => {" + _WALK_JS + r"""
  return [...document.querySelectorAll('link[rel~="stylesheet"], style')].map((el) => {
    let rules = null, err = null;
    if (el.sheet) {
      try { rules = walk(el.sheet.cssRules, 0, []); } catch (e) { err = String(e.name); }
    }
    return {tag: el.tagName.toLowerCase(),
            href: el.tagName === 'LINK' ? new URL(el.href, location.href).pathname : null,
            text: el.tagName === 'STYLE' ? el.textContent : null, rules, err};
  });
}"""


def _triples(raw: list) -> list[tuple[int, str, str]]:
    return [(d, k, selector_signature(k, sel)) for d, k, sel in raw]


def _divergence(label: str, line: int, text: str, got: list[tuple[int, str, str]]) -> str | None:
    """같으면 None, 다르면 «어디서» 갈렸는지 — 스캐너 블록의 파일 줄과 Chromium 쪽 규칙."""
    kept = chromium_kept(scan(text).blocks)
    expected = chromium_expected(scan(text).blocks)
    if expected == got:
        return None
    i = next((k for k, (a, b) in enumerate(zip(expected, got)) if a != b),
             min(len(expected), len(got)))
    where = (f"{label}:{line + kept[i].line - 1}  {' '.join(kept[i].prelude.split())[:70]!r}"
             if i < len(kept) else f"{label}  (저자 블록 끝)")
    return (f"{where} — 저자 {len(expected)} 블록 · Chromium {len(got)} 규칙 · "
            f"첫 갈림 저자={expected[i] if i < len(expected) else None} "
            f"Chromium={got[i] if i < len(got) else None}")


def _parse_in_chromium(page, css: str) -> list[tuple[int, str, str]]:
    return _triples(page.evaluate(_PARSE_JS, css))


def test_chromium_keeps_every_rule_the_author_wrote(page):
    """브라우저가 받는 CSS 덩어리 전부 — 템플릿이 거는 정적 파일 + 템플릿 `<style>`(화면 무관)."""
    sources = [s for s in authored_sources() if s.served]
    assert sum(s.path.endswith(".html") for s in sources) >= 10, "템플릿 `<style>` 을 거의 못 읽었다"
    assert sum(s.path.endswith(".css") for s in sources) >= 5, "정적 CSS 를 거의 못 읽었다"
    page.set_content("<!doctype html><meta charset=utf-8><title>css</title>")
    bad, seen = [], 0
    for s in sources:
        # 구조가 깨졌으면 대조는 스캐너의 «복구» 와 브라우저의 복구를 맞대는 셈이다 — 함께 보고한다.
        # A structural defect makes the comparison meaningless; report it alongside.
        bad += [f"{s.path}:{s.line + ln - 1}  구조 결함 — {kind}" for ln, kind in scan(s.text).defects]
        got = _parse_in_chromium(page, s.text)
        seen += len(got)
        if (msg := _divergence(s.path, s.line, s.text, got)) is not None:
            bad.append(msg)
    assert seen > 1000, f"Chromium 규칙을 {seen} 개만 셌다 — 대조가 비었다"
    assert not bad, ("Chromium 이 저자가 쓴 규칙을 버리거나 옮겼다:\n  " + "\n  ".join(bad))


def test_the_browser_judge_sees_what_the_structure_scan_cannot(page):
    r"""계기 뒤집기 — 운영 파일(`components.css`)에 심어 브라우저 판정이 실제로 갈리는가.

    claimed\cheap: 구조는 멀쩡한 셀렉터 오타 → 스캐너는 결함 0, 브라우저는 그 규칙을 버린다 → 갈림.
    cheap\claimed: 다른 엔진 전용 규칙 → 브라우저가 버리지만 «적법» → 갈리면 안 된다.
    바닥: `}` 하나 빠짐 → 브라우저가 뒤 규칙을 중첩으로 옮긴다 → 갈림.
    """
    src = next(s for s in authored_sources() if s.path.endswith("/components.css"))
    page.set_content("<!doctype html><meta charset=utf-8><title>css</title>")
    assert _divergence(src.path, 1, src.text, _parse_in_chromium(page, src.text)) is None

    typo = src.text + "\n.zz-plant:hovr { color: red; }\n"
    assert scan(typo).defects == [], "이 심음은 구조가 멀쩡해야 한다 — 스캐너가 못 보는 쪽"
    assert _divergence(src.path, 1, typo, _parse_in_chromium(page, typo)) is not None

    foreign = src.text + "\n.zz-plant::-moz-range-thumb { color: red; }\n"
    assert _divergence(src.path, 1, foreign, _parse_in_chromium(page, foreign)) is None

    top = [b for b in scan(src.text).blocks if b.depth == 0 and b.kind == "style"]
    _, close = top[len(top) // 2].span
    lost = src.text[:close] + src.text[close + 1:]
    assert _divergence(src.path, 1, lost, _parse_in_chromium(page, lost)) is not None


def _link_groups() -> tuple[set[str], set[str]]:
    """(로그인 화면 가족이 거는 시트, 홀로 서는 템플릿이 거는 시트) — 템플릿 상속에서 파생한다."""
    links = template_links()
    parents = {p for p, _ in links.values() if p}
    alone = {n for n, (p, _) in links.items() if p is None and n not in parents}
    family = {h for n, (_, hrefs) in links.items() if n not in alone for h in hrefs}
    standalone = {h for n in alone for h in links[n][1]}
    return family, standalone


def _assert_served_whole(page, base_url: str, paths: list[str], must_see: set[str]) -> None:
    """화면마다 걸린 시트가 전부 받아졌고, 원문과 같은 구조인가 + 봐야 할 시트를 다 봤는가."""
    by_href = {f"{_ROOT_CSS}{s.path.rsplit('/', 1)[1]}": s.text
               for s in authored_sources() if s.path.endswith(".css")}
    bad, seen = [], set()
    for path in paths:
        page.goto(f"{base_url}{path}", wait_until="load")
        for el in page.evaluate(_SERVED_JS):
            name = el["href"] or f"<style> on {path}"
            if el["rules"] is None:
                bad.append(f"{path}: {name} — 브라우저가 받지 못했다(sheet 없음·{el['err']})")
                continue
            if el["href"]:
                seen.add(el["href"])
            if el["href"] and el["href"].startswith(_BUILT):
                if not el["rules"]:
                    bad.append(f"{path}: {name} — 빌드 산출물이 비었다")
                continue
            text = el["text"] if el["tag"] == "style" else by_href.get(el["href"])
            if text is None:
                bad.append(f"{path}: {name} — 저자 원문이 없는 시트")
                continue
            if (msg := _divergence(name, 1, text, _triples(el["rules"]))) is not None:
                bad.append(f"{path}: {msg}")
    assert seen, "링크된 시트를 하나도 못 봤다"
    assert must_see <= seen, f"템플릿이 거는데 이 화면들에서 못 본 시트 — 화면을 더한다: {must_see - seen}"
    assert not bad, "\n  ".join(["받은 스타일시트가 원문과 다르다:", *bad])


def test_every_stylesheet_the_logged_in_screens_link_arrives_whole(admin_page, base_url):
    family, _ = _link_groups()
    _assert_served_whole(admin_page, base_url,
                         ["/dashboard", "/repos/owner/testrepo/insights", "/admin/rls-audit"],
                         family)


def test_every_stylesheet_the_landing_links_arrives_whole(anonymous_page, base_url):
    _, standalone = _link_groups()
    assert standalone, "홀로 서는 템플릿(랜딩)의 시트를 하나도 못 뽑았다"
    _assert_served_whole(anonymous_page, base_url, ["/"], standalone)
