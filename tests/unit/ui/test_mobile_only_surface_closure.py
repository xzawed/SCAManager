"""모바일에만 존재하는 «면» 이 접근성 관측 밖에 생기지 않게 닫는다.

## 무엇이 문제였나

AA 대비·포커스 e2e 헬퍼는 뷰포트를 데스크탑(1440×900)으로 **스스로 되돌리고** 있었다.
호출자가 모바일 크기를 넣어도 덮였으므로, 모바일에서만 그려지는 면은 원리적으로 관측
대상이 아니었다. 실측으로 그런 면이 실제로 있었다 — `@media (max-width: 768px)` 의
`.nav-links.open` 은 `position:fixed` · `background: var(--bg-nav)`(알파 0.72~0.82) 오버레이라
1440 에서는 «존재조차» 하지 않는다.

## 이 가드가 잰다고 «주장하는» 것

`@media (max-width: …)` 안에서

- 칠을 바꾸거나(색·바탕·테두리색·outline·box-shadow·opacity)
- 데스크탑에서 숨은 것을 드러내는(`display` 가 `none` 이 아닌)

셀렉터를 소스에서 **파생** 하고, 그 각각이 모바일 e2e 에 이름으로 등장하는지 본다.
손 목록이 아니라 파생이므로, 새 모바일 전용 규칙이 생기면 이 시험이 먼저 red 가 된다.

## 🔴 면제는 «사유와 함께» · 양방향으로 잰다

면제 항목이 소스에서 사라지면 그 줄도 red 다. 죽은 면제는 다음 사람에게 「이건 이미
따져봤다」로 읽히면서 실제로는 아무것도 가리지 않는다.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_E2E = _ROOT / "e2e" / "test_theme_mobile_guards.py"

# 🔴 손으로 적은 목록에서 `border-left`·`outline-color` 가 빠져 있었다(Grok 반증
#    `01a07c5f`). 그래서 「이름이 color 로 끝나는 속성」을 «부류» 로 받는다.
#    반대로 접두사 통짜(`border[-\w]*`)로 넓혔더니 `border-radius`·`background-size`
#    같은 «배치» 속성까지 칠로 세어 3건을 거짓 검출했다 — 넓힘도 좁힘만큼 틀린다.
#    각 대안 뒤가 곧바로 `:` 이므로 `border-radius:` 는 `border` 에 걸리지 않는다.
_PAINT = re.compile(
    r"(?<![-\w])(?:[-\w]*color|background|background-image|border|border-top|"
    r"border-bottom|border-left|border-right|outline|box-shadow|text-shadow|"
    r"opacity|fill|stroke|filter|backdrop-filter)\s*:", re.I)

# `max-width: 768px` 과 range 문법(`width <= 768px`)을 함께 본다.
_MOBILE_AT = re.compile(r"@media[^{]*(?:max-width|width\s*<=?)[^{]*\{")

# 관측하지 않아도 되는 면 — 사유가 있어야 하고, 사라지면 red 다(양방향).
_EXEMPT = {
    ".nav-hamburger":
        "글리프 «☰» 뿐이라 1.4.3(글자 대비) 대상이 아니다. 크기(2.5.5)는 "
        "`test_mobile_nav_hamburger_44x44` 가 이미 잰다.",
    ".ov-unclaimed-banner .btn":
        "모바일 전용 «면» 이 아니다 — 같은 버튼이 데스크탑에서도 보이고 "
        "(`overview.html` 의 `@media` 밖 규칙), 모바일 블록은 배치만 바꾼다.",
    ".nav-links.open a.nav-link":
        "오버레이 «안» 의 링크다. 오버레이를 여는 e2e 가 이 링크들의 글자를 "
        "그대로 감사한다(`_assert_overlay_was_measured` 가 개수로 확인).",
}


def _sources() -> list[Path]:
    """🔴 `src/static/**.html`(목업 등)도 본다 — 글로브 밖에 CSS 를 두면 그것만으로
    이 가드가 조용해진다. 실측상 지금은 추가되는 면이 0이라 공짜로 구멍만 닫힌다."""
    return (sorted((_ROOT / "src" / "templates").rglob("*.html"))
            + sorted((_ROOT / "src" / "static").rglob("*.css"))
            + sorted((_ROOT / "src" / "static").rglob("*.html")))


def _blocks(text: str):
    """모바일 `@media` 블록 본문을 중괄호 균형으로 잘라 낸다."""
    for m in _MOBILE_AT.finditer(text):
        i, depth = m.end(), 1
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        yield text[m.end():i - 1]


def mobile_only_surfaces() -> dict[str, str]:
    """{셀렉터: 어디서} — 모바일에서 칠이 바뀌거나 새로 드러나는 셀렉터."""
    found: dict[str, str] = {}
    for path in _sources():
        text = path.read_text(encoding="utf-8")
        where = path.relative_to(_ROOT).as_posix()
        for block in _blocks(text):
            for rule in re.finditer(r"([^{}]+)\{([^{}]*)\}", block):
                sel = " ".join(rule.group(1).split())
                sel = re.sub(r"/\*.*?\*/", "", sel).strip()
                body = rule.group(2)
                if not sel:
                    continue
                display = re.search(r"(?<![-\w])display\s*:\s*([^;}]+)", body)
                reveals = bool(display) and display.group(1).strip() != "none"
                if _PAINT.search(body) or reveals:
                    found.setdefault(sel, where)
    return found


def e2e_selector_literals() -> set[str]:
    """모바일 e2e 가 «셀렉터로» 적은 문자열들 — 파일 전체 문자열이 아니다.

    🔴 이전 판은 `sel not in <파일 전체>` 였다. 그것은 이 리포가 명시적으로 금지한
    「부분문자열로 부류를 판정」이고, 실측으로 무너진다 — 타입 셀렉터 `th` 는 e2e 안의
    «theme» 에, `a`·`nav`·`.btn`·`.open` 도 각각 다른 낱말에 걸려 «덮였다» 가 됐다.
    그러면 모바일 전용으로 `th { color: … }` 를 새로 칠해도 이 가드는 초록이다.

    그래서 파이썬 리터럴을 AST 로 걷고, 그 안에 박힌 JS 따옴표 문자열까지 꺼내
    **정확히 같은 셀렉터인가** 로만 판정한다.

    Substring matching made `th` look covered by the word "theme"; compare literals instead.
    """
    src = _E2E.read_text(encoding="utf-8")
    out: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        text = node.value
        # JS 블롭 안의 `querySelector('.nav-links')` 같은 따옴표 문자열도 셀렉터다.
        for piece in [text] + re.findall(r"['\"]([^'\"\n]{1,120})['\"]", text):
            for part in piece.split(","):
                part = " ".join(part.split())
                if part:
                    out.add(part)
    return out


def test_coverage_is_not_a_substring_match():
    """🔴 계기 자기검증 — 「덮였다」 판정이 부분문자열로 돌아가면 이 축은 조용히 열린다.

    `th` 는 e2e 파일 «본문» 에는 (theme 안에) 들어 있지만 셀렉터 리터럴은 아니다.
    아래가 True 가 되는 순간 그 판정식은 다시 거짓 초록을 만든다.
    """
    src = _E2E.read_text(encoding="utf-8")
    literals = e2e_selector_literals()
    # 🔴 대조군은 «실측으로» 골랐다. `a`·`nav`·`span` 은 e2e 에 진짜 셀렉터 리터럴로
    #    있어서 대조군이 될 수 없다(`td` 는 반대로 본문에 아예 없어 무효). 아래 넷은
    #    모두 본문에는 있으나 리터럴은 아닌, HTML 타입 셀렉터로 쓸 수 있는 이름이다.
    for decoy in ("th", "tr", "li", "code"):
        assert decoy in src, f"전제가 깨졌다 — {decoy!r} 가 e2e 본문에 없다(대조군 무효)"
        assert decoy not in literals, (
            f"{decoy!r} 가 셀렉터 리터럴로 잡혔다 — 부분문자열 판정으로 되돌아갔다")
    # 대조군 — 실제로 쓰는 셀렉터는 잡혀야 한다(공허하게 «전부 아님» 이 되지 않도록).
    assert ".nav-links.open" in literals, (
        "실제 셀렉터도 못 잡는다 — 리터럴 추출이 죽었다(공허한 초록)")


def test_every_mobile_only_surface_is_observed_or_exempt():
    """🔴 모바일에서만 그려지는 면이 관측 밖에 있으면 그 면의 대비는 아무도 재지 않는다.

    데스크탑 스윕은 그 면을 «덜» 재는 게 아니라 «못» 잰다 — 요소가 그 뷰포트에
    존재하지 않기 때문이다.
    """
    surfaces = mobile_only_surfaces()
    assert surfaces, "모바일 전용 규칙을 0개 찾았다 — 스캔이 죽었다(공허한 초록)"
    literals = e2e_selector_literals()

    uncovered = [f"{sel}  ({where})" for sel, where in sorted(surfaces.items())
                 if sel not in _EXEMPT and sel not in literals]
    assert not uncovered, (
        "모바일에서만 그려지는데 모바일 e2e 가 이름으로도 열지 않는 면이 있다 — "
        "그 면의 글자 대비는 어떤 뷰포트에서도 관측되지 않는다:\n  "
        + "\n  ".join(uncovered))


def test_exemptions_still_point_at_something_real():
    """🔴 죽은 면제는 「이미 따져봤다」로 읽히면서 아무것도 가리지 않는다."""
    surfaces = mobile_only_surfaces()
    stale = sorted(sel for sel in _EXEMPT if sel not in surfaces)
    assert not stale, (
        "소스에서 사라진 셀렉터를 아직 면제하고 있다 — 지우거나 갱신한다:\n  "
        + "\n  ".join(stale))


def test_the_aa_helper_does_not_hardcode_the_viewport_again():
    """🔴 헬퍼가 뷰포트를 다시 하드코딩하면 이 축은 조용히 닫힌다.

    이것이 원래 원인이었다 — 호출자가 모바일 크기를 넘겨도 헬퍼가 데스크탑으로 덮었고,
    그래서 모바일 면은 「덜 잰 축」이 아니라 «못 재는 축» 이었다.
    """
    src = _E2E.read_text(encoding="utf-8")
    body = src[src.index("def _assert_token_text_aa"):]
    body = body[:body.index("\n\n\n")]
    assert "viewport or " in body, (
        "_assert_token_text_aa 가 `viewport` 인자를 쓰지 않는다 — 호출자의 모바일 크기가 덮인다")
    assert "def _assert_token_text_aa(page, base_url, theme, path, viewport" in src, (
        "_assert_token_text_aa 의 시그니처에 `viewport` 가 없다")
