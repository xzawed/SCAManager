"""`--warning` 을 «글자» 로 쓰는 자리를 닫고, 글자용 짝 토큰 `--warning-text` 를 잰다.

## 무엇이 문제였나 (2026-09-16 회고 P1-7)

`--accent`(#1609)·`--success`(#1643)·`--danger`(#1642) 는 «면» 색과 «글자» 색을 이미 갈랐다
(`--accent-text`·`--success-text`·`--danger-text-on` …). `--warning` 만 짝이 없어, 그 면 색을
글자로 쓰는 자리가 pastel 에서 카드 위 **2.79**(기준 4.5)였다:

- `analysis_detail.html` — AI 기본값 적용 배너의 제목
- `dashboard.html::.repos-cat-security-warn .repos-cat-value` — repos 리포트의 보안 경고 수
- `dashboard.html` — 평균 점수 KPI 의 «신뢰 불가 제외» 각주
- `repo_detail.html::renderSourceBadge` — 분석 표의 CLI 출처 배지(JS 가 `color:` 를 조립)

## 🔴 이 가드가 «글자» 로 보는 것

`color:` 로 `--warning`·`--status-warn` 을 지정하는 자리, 그리고 템플릿 안의 따옴표 친
`'var(--warning)'` 리터럴(JS 가 문자열로 넘겨 `color:` 를 조립한다 — 이 리포에서 그 리터럴은
글자색으로만 쓰였다). 면(`background`)·테두리는 다른 축이다. 글리프(⚠)도 글자 토큰을 쓴다 —
3:1(1.4.11)이면 되는 자리지만 `--warning` 은 pastel 카드에서 그것도 못 넘는다(2.79).

Close every place that paints text with the warning surface colour; route it through
`--warning-text`, and give filled warning surfaces their own on-token.
"""
from __future__ import annotations

import re

from ._contrast import (AA, ROOT, THEMES, over, paint_colours, ratio, read,
                        strip_css_comments, token_scope)

_TOKENS = read("src/static/css/tokens.css")
_SCOPES = {t: token_scope(_TOKENS, t) for t in THEMES}

# 정확히 면 토큰만 — `--warning-text`·`--warning-faint`·`--warning-rgb` 는 별개다.
_WARNING_AS_TEXT = re.compile(
    r"(?<![-\w])color\s*:\s*var\(\s*--(?:warning|status-warn)\s*[,)]")
_WARNING_LITERAL = re.compile(r"""(['"])var\(\s*--(?:warning|status-warn)\s*\)\1""")

# 글자가 앉는 바탕 — `test_accent_text_contrast.py::_ACCENT_TEXT_GROUNDS` 와 같은 목록.
_GROUNDS = ("--bg-base", "--bg-canvas", "--bg-card", "--bg-elevated", "--bg-mute")


def _sources() -> list:
    return (sorted((ROOT / "src" / "templates").rglob("*.html"))
            + sorted((ROOT / "src" / "static").rglob("*.css"))
            + sorted((ROOT / "src" / "i18n" / "translations").rglob("*.json")))


def warning_as_text_sites(src: str) -> list[int]:
    """그 원문에서 warning 면 색으로 글자를 칠하는 자리의 줄 번호."""
    clean = strip_css_comments(src)
    hits = [m.start() for m in _WARNING_AS_TEXT.finditer(clean)]
    hits += [m.start() for m in _WARNING_LITERAL.finditer(clean)]
    return sorted(clean.count("\n", 0, i) + 1 for i in hits)


def test_warning_is_not_used_as_text():
    """🔴 warning 면 색을 글자로 쓰면 pastel 카드에서 2.79 다 — `--warning-text` 를 쓴다."""
    offenders = [f"{p.relative_to(ROOT).as_posix()}:{line}"
                 for p in _sources()
                 for line in warning_as_text_sites(p.read_text(encoding="utf-8"))]
    assert not offenders, (
        "warning 면 색으로 글자를 칠한다 — `var(--warning-text)` 를 쓴다:\n  "
        + "\n  ".join(offenders))


def test_the_scan_catches_the_fallback_and_literal_forms():
    r"""claimed\cheap — `var(--warning)` 을 «정확히» 찾는 싼 과정은 대체값 꼴
    (`var(--warning, #d97706)`)과 JS 리터럴(`'var(--warning)'`)을 둘 다 놓친다."""
    assert warning_as_text_sites('<div style="color:var(--warning, #d97706)">x</div>') == [1]
    assert warning_as_text_sites("cli: [label, 'var(--warning)'],") == [1]


def test_the_scan_ignores_fills_and_sibling_tokens():
    r"""cheap\claimed — 이름이 «등장» 하는 것으로 세면 면·테두리·짝 토큰까지 걸린다."""
    src = (".a { background: var(--warning); border-left: 4px solid var(--warning); }\n"
           ".b { color: var(--warning-text); background: var(--warning-faint); }\n"
           "/* .c { color: var(--warning); } */")
    assert warning_as_text_sites(src) == []


def test_warning_text_meets_aa_on_every_ground():
    """🔴 `--warning-text` 는 네 테마 «전부» 에 있고, 글자가 앉는 바탕마다 AA 를 넘는다."""
    bad = []
    for theme in THEMES:
        scope = _SCOPES[theme]
        [fg] = paint_colours(scope, "var(--warning-text)")
        card = paint_colours(scope, "var(--bg-card)")[0]
        for name in _GROUNDS:
            [bg] = paint_colours(scope, f"var({name})")
            bg = bg if bg[3] >= 1 else over(bg, card)
            got = ratio(over(fg, bg), bg)
            if got < AA:
                bad.append(f"[{theme}] --warning-text on {name}: {got:.2f} < {AA}")
    assert not bad, "warning 글자색이 AA 미달이다:\n  " + "\n  ".join(bad)


def test_text_on_a_filled_warning_surface_meets_aa():
    """🔴 warning 으로 «채운» 면 위 글자는 그 면에 맞춘 `--warning-text-on` 을 쓴다.

    실측: `.repos-rec-warning` 이 리터럴 `#000` 이라 light(#b45309) 에서 4.18,
    `.filter-btn[data-source="cli"].active` 는 accent 용 on-토큰을 빌려 «우연히» 통과했다.
    """
    bad = []
    for theme in THEMES:
        scope = _SCOPES[theme]
        [fill] = paint_colours(scope, "var(--warning)")
        [fg] = paint_colours(scope, "var(--warning-text-on)")
        got = ratio(over(fg, fill), fill)
        if got < AA:
            bad.append(f"[{theme}] --warning-text-on on --warning: {got:.2f} < {AA}")
    assert not bad, "warning 면 위 글자가 AA 미달이다:\n  " + "\n  ".join(bad)


def test_filled_warning_surfaces_use_the_on_token():
    """정의 ≠ 배선 — 토큰을 만들어도 쓰는 자리가 안 바뀌면 화면은 그대로다."""
    bad = []
    for path in _sources():
        src = strip_css_comments(path.read_text(encoding="utf-8"))
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", src):
            body = m.group(2)
            if not re.search(r"(?<![\w-])background(?:-color)?\s*:\s*var\(\s*--warning\s*[,)]",
                             body):
                continue
            cm = re.search(r"(?<![\w-])color\s*:\s*([^;]+)", body)
            if cm and "--warning-text-on" not in cm.group(1):
                bad.append(f"{path.name}: {' '.join(m.group(1).split())[:50]} "
                           f"color:{cm.group(1).strip()}")
    assert not bad, ("warning 으로 채운 면 위 글자가 전용 on-토큰을 쓰지 않는다:\n  "
                     + "\n  ".join(bad))
