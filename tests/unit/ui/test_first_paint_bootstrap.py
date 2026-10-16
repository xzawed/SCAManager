"""첫 그림 부트스트랩 — 저장 테마·«등장 전» 표식은 `<head>` 가 걸고, 그 표식이 가리는 대상은
reveal · effects.js 의 실제 등장 대상과 같아야 한다.

## 무엇이 문제였나 (2026-10-16 렌더링 검수)

저장 테마 적용 · reveal · 카운트업이 전부 `base.html` 의 `<body>` 맨 끝 스크립트에서 시작했다.
그 앞의 외부 스크립트(htmx · effects · Chart.js — `no-cache` 재검증)를 기다리는 동안 브라우저가
먼저 그려서, 라이트 사용자에게 dark 가 보였고 카드가 «보였다가 숨고» KPI 가 0 부터 다시 셌다.

## 행동 판정은 e2e

지연(왕복 300ms)을 건 실제 프레임 판정은 `e2e/test_first_paint.py` 다. 여기는 그 수정이
되돌려지거나, 두 스크립트가 새 등장 대상을 얻었는데 CSS 표식 목록이 따라가지 않는 것을
단위 수준에서 빠르게 잡는다.

## 🔴 이 가드가 «하지 못하는» 것

- 스크립트가 «무엇을 하는지» 는 보지 않는다 — 위치와 목록만 본다. 그 축은 e2e 다.
- 다른 템플릿이 자기 등장 애니메이션을 따로 만들면(두 목록 밖) 보지 못한다.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.i18n.filters import register_i18n_filters

from ._contrast import ROOT, read, strip_css_comments


def _rendered_base() -> str:
    """렌더된 base.html — Jinja 주석·분기가 걷힌 «브라우저가 받는» 순서를 본다."""
    env = Environment(loader=FileSystemLoader(str(ROOT / "src" / "templates")),
                      autoescape=select_autoescape(["html", "xml"]))
    register_i18n_filters(env)
    return env.get_template("base.html").render(current_user=None, locale="ko")

# effects.js — `freshOnly(document.querySelectorAll("..."), "entry")` 의 문자열 하나.
_EFFECTS_TARGETS = re.compile(
    r'freshOnly\(\s*document\.querySelectorAll\(\s*"([^"]+)"\s*\)\s*,\s*"entry"\s*\)')
# base.html — `function _initReveal() { ... querySelectorAll('...')` 의 문자열 하나.
_REVEAL_TARGETS = re.compile(r"function _initReveal\(\)\s*\{.*?querySelectorAll\('([^']+)'\)", re.S)
# `html.fx-pending :is(<목록>):not(<해제 클래스>)` — 해제 클래스별로 목록을 모은다.
_PENDING_RULE = re.compile(r"html\.fx-pending\s+:is\(([^)]*)\)\s*:not\(\s*(\.[\w-]+)\s*\)")


def _selectors(text: str) -> set[str]:
    return {s.strip() for s in text.split(",") if s.strip()}


def pending_groups(css: str) -> dict[str, set[str]]:
    """{해제 클래스: `:is()` 안 선택자 집합} — 주석을 지운 뒤 읽는다(주석 속 인용은 규칙이 아니다)."""
    out: dict[str, set[str]] = {}
    for m in _PENDING_RULE.finditer(strip_css_comments(css)):
        out.setdefault(m.group(2), set()).update(_selectors(m.group(1)))
    return out


def _one(rx: re.Pattern, src: str, what: str) -> set[str]:
    found = rx.findall(src)
    # 🔴 못 찾으면 초록이 아니라 red — 목록이 비면 «위반 0» 으로 조용히 통과한다.
    assert len(found) == 1, f"{what} 를 정확히 1곳에서 찾아야 한다 — {len(found)}곳 (스캐너가 늙었다)"
    return _selectors(found[0])


class _Order(HTMLParser):
    """`<head>` 의 인라인 스크립트와 스타일시트 순서 · `<body>` 의 첫 자식 태그."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.in_head = False
        self.head_events: list[str] = []
        self.body_seen = False
        self.body_first_child: tuple[str, dict] | None = None
        self.html_attrs: dict = {}
        self.body_attrs: dict = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.html_attrs = a
        elif tag == "head":
            self.in_head = True
        elif tag == "body":
            self.in_head, self.body_seen, self.body_attrs = False, True, a
        elif self.body_seen and self.body_first_child is None:
            self.body_first_child = (tag, a)
        elif self.in_head and tag == "script" and not a.get("src"):
            self.head_events.append("inline-script")
        elif self.in_head and tag == "link" and a.get("rel") == "stylesheet":
            self.head_events.append("stylesheet")

    def handle_endtag(self, tag):
        if tag == "head":
            self.in_head = False


def test_stored_theme_is_applied_before_the_stylesheets_and_the_body():
    """🔴 `<head>` 의 인라인 스크립트가 첫 스타일시트보다 앞서고, `<body>` 의 첫 자식이 테마 동기화 스크립트다.

    The stored theme is applied by an inline <head> script ahead of the stylesheets, and the
    first child of <body> is the inline sync script.
    """
    order = _Order()
    order.feed(_rendered_base())
    assert "stylesheet" in order.head_events, "head 에서 스타일시트를 0개 찾았다 — 스캐너가 늙었다"
    first_sheet = order.head_events.index("stylesheet")
    assert "inline-script" in order.head_events[:first_sheet], (
        "저장 테마를 거는 인라인 스크립트가 첫 스타일시트보다 앞에 없다 — body 끝 스크립트만 테마를 "
        "걸면 외부 스크립트를 기다리는 동안 dark 가 먼저 그려진다(e2e/test_first_paint.py)")
    tag, attrs = order.body_first_child or ("(없음)", {})
    assert tag == "script", (
        f"<body> 의 첫 자식이 테마 동기화 스크립트가 아니다({tag}) — body[data-theme] 를 읽는 "
        "규칙·코드가 본문 첫 그림에서 값을 못 본다")
    assert not attrs.get("src"), "<body> 첫 스크립트가 외부 파일이다 — 인라인이어야 본문보다 먼저 돈다"
    # 🔴 서버는 body 에 테마를 쓰지 않는다 — 쓰면 동기화 스크립트가 돌기 전 «빈 배경» 프레임이 그
    #    값(dark)으로 그려질 틈이 생긴다(Grok `99aa48c8`). 토큰은 html 에서 상속된다.
    assert "data-theme" not in order.body_attrs, (
        f"서버가 <body> 에 data-theme={order.body_attrs.get('data-theme')!r} 를 썼다 — 동기화 전 프레임이 그 테마다")
    # JS 가 꺼진 화면의 기본값은 html 에 있다 — 없으면 토큰이 하나도 안 걸린다.
    assert order.html_attrs.get("data-theme") == "dark", (
        f"<html> 에 JS 없는 기본 테마가 없다({order.html_attrs.get('data-theme')!r}) — 토큰이 안 걸린 화면이 된다")


def test_pending_flag_covers_every_entrance_target():
    """🔴 `html.fx-pending` 이 reveal · effects.js 의 등장 대상을 «전부» 첫 그림부터 등장 전 상태로 둔다.

    The first-paint flag must cover every reveal and effects.js entrance target.
    """
    base = _rendered_base()
    effects = _one(_EFFECTS_TARGETS, read("src/static/js/effects.js"), "effects.js 등장 대상")
    reveal = _one(_REVEAL_TARGETS, base, "_initReveal 대상") - {".reveal"}   # .reveal 은 원래 투명
    groups = pending_groups(base)
    assert groups, "html.fx-pending 규칙을 0개 찾았다 — 표식 CSS 가 사라졌다"
    missing_fx = sorted(effects - groups.get(".is-in-view", set()))
    missing_rv = sorted(reveal - groups.get(".visible", set()))
    assert not missing_fx, (
        f"첫 그림 표식이 가리지 않는 effects.js 등장 대상(.is-in-view 해제) — «보였다가 숨는다»: {missing_fx}")
    assert not missing_rv, (
        f"첫 그림 표식이 가리지 않는 reveal 대상(.visible 해제) — «보였다가 숨는다»: {missing_rv}")


def test_the_scanner_reads_rules_not_mentions():
    """🔴 스캐너 자기검증 — 주석 속 규칙은 세지 않고, 다른 freshOnly 태그는 고르지 않는다."""
    css = """
      /* html.fx-pending :is(.ghost):not(.visible) { opacity: 0 } */
      html.fx-pending :is(.a, .b):not(.visible),
      html.fx-pending :is(.c,
                          .d):not(.is-in-view) { opacity: 0; }
    """
    assert pending_groups(css) == {".visible": {".a", ".b"}, ".is-in-view": {".c", ".d"}}
    js = ('freshOnly(document.querySelectorAll(".x, .y"), "countup");\n'
          'freshOnly(document.querySelectorAll(".p, .q"), "entry");')
    assert _one(_EFFECTS_TARGETS, js, "등장 대상") == {".p", ".q"}
