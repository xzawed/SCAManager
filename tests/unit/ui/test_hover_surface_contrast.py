"""hover 가 바꿔 칠하는 «면» — 행·카드는 hover 전용 토큰을 지난다(2026-09-16 회고 P1-28).

## 무엇이 문제였나

행·카드 hover 가 «중립 칩 면»(`--bg-mute`·`--bg-card-hi`)을 빌려 칠했다. 세 밝은 테마에서는
그 면이 카드와 거의 같아 티가 안 났지만, catppuccin 은 그것이 카드보다 «밝은» surface1 이라
행에 마우스를 올리면 그 안의 등급 F 칩이 3.41 · 3차 글자가 4.10 으로 떨어졌다. 55 PR 동안의
AA 스윕에 hover 축이 없어 아무도 못 봤다.

## 이 가드가 지키는 것

`:hover` 규칙이 중립 칩 면으로 «면을» 칠하면 red 다 — 행·카드는 `--table-row-hover`·
`--bg-card-hover` 를 쓴다. 그 두 토큰은 `_contrast.HOVER_GROUNDS` 로 모든 글자 토큰 가드의
바탕 목록 «안» 에 있다(`test_grade_badge_contrast.py` · `test_secondary_text_contrast.py` ·
`text_grounds` 를 쓰는 형제들). 제 글자색만 얹는 «컨트롤» 은 사유를 달아 면제한다.

## 🔴 이 가드가 «하지 못하는» 것

같은 블록의 선택자만 본다 — 리터럴 색이나 `color-mix()` 로 칠한 hover 면은 이 스캔 밖이다.
그 축은 실제로 칠해진 픽셀을 재는 e2e hover 스윕
(`e2e/test_theme_mobile_guards.py::_audit_text_under_hover`)이 맡는다. 두 층을 다 둔다.
"""
from __future__ import annotations

import re

from ._contrast import ROOT, strip_css_comments

# 중립 칩·인셋 면 — 글자 토큰 가드가 «바탕» 으로 보장하지 않는 면이다.
_NEUTRAL_SURFACES = ("--bg-mute", "--bg-card-hi", "--bg-hover")
_PAINTS_NEUTRAL = re.compile(
    r"(?<![\w-])background(?:-color)?\s*:[^;{}]*var\(\s*("
    + "|".join(re.escape(n) for n in _NEUTRAL_SURFACES) + r")(?![\w-])")
# `:not(:hover)` 는 hover 가 «아닌» 상태다 — 그 안의 `:hover` 는 세지 않는다.
_HOVER_PSEUDO = re.compile(r":hover(?![\w-])")
_NOT_HOVER = re.compile(r":not\([^()]*:hover[^()]*\)")

# 면제 — «사유와 함께». 사라지면 red 다(역방향).
_EXEMPT = {
    ".btn--secondary:hover": "버튼 — 제 글자(`--text-1`)만 얹는다. 등급색·3차 글자를 품지 않는다.",
    ".btn--ghost:hover": "버튼 — 위와 같다(`base.html` 의 같은 선택자가 면을 다시 칠한다).",
    ".fb-btn:hover": "피드백 버튼 — 제 글자만 얹는다. 활성 칩(`.fb-btn.active.fb-up`)은 "
                     "명시도가 높아 hover 에서도 제 틴트를 유지한다.",
    ".mode-toggle-btn:hover:not(.active)": "세그먼트 버튼 — 제 글자(`--text-1`)만 얹는다.",
    ".gate-mode-btn:hover:not(.active)": "세그먼트 버튼 — 제 글자(`--text-2`)만 얹는다(catppuccin 5.15).",
    ".mask-toggle:hover": "글리프 버튼(👁) — 글자가 없다.",
}


def hover_neutral_sites_in(src: str) -> list[tuple[str, int]]:
    """[(선택자, 줄)] — `:hover` 상태에서 중립 칩 면으로 면을 칠하는 규칙."""
    clean = strip_css_comments(src)
    out = []
    for m in _PAINTS_NEUTRAL.finditer(clean):
        head = clean[:m.start()].rsplit("{", 1)[0]
        # 직전 `}` 뒤, 그리고 `@media (...) {` 같은 감싸는 블록의 `{` 뒤만 선택자다.
        sel = " ".join(head.rsplit("}", 1)[-1].rsplit("{", 1)[-1].split())
        if _HOVER_PSEUDO.search(_NOT_HOVER.sub("", sel)):
            out.append((sel, clean[:m.start()].count("\n") + 1))
    return out


def hover_neutral_sites() -> dict[str, str]:
    """{선택자: 'path:line'} — 템플릿 인라인 `<style>` 과 정적 CSS 전부."""
    found: dict[str, str] = {}
    for path in (sorted((ROOT / "src" / "templates").rglob("*.html"))
                 + sorted((ROOT / "src" / "static").rglob("*.css"))):
        for sel, line in hover_neutral_sites_in(path.read_text(encoding="utf-8")):
            found[sel] = f"{path.relative_to(ROOT).as_posix()}:{line}"
    return found


def test_the_scan_judges_the_hover_state_not_the_mention():
    """🔴 스캐너 자기검증 — hover 면은 잡고, 쉬는 면·hover 토큰·`:not(:hover)` 는 놓아준다."""
    src = """
      .row:hover td { background: var(--bg-mute); }
      @media (max-width: 9px) { .card:hover { background-color: var(--bg-card-hi, #fff); } }
      .chip { background: var(--bg-mute); }
      .row2:hover td { background: var(--table-row-hover); }
      .x:not(:hover) { background: var(--bg-hover); }
      .y:hover { border-color: var(--bg-mute); }
      /* .z:hover { background: var(--bg-mute); } */
    """
    sels = [s for s, _ in hover_neutral_sites_in(src)]
    assert sels == [".row:hover td", ".card:hover"], sels


def test_rows_and_cards_repaint_hover_with_the_hover_tokens():
    """🔴 행·카드 hover 는 `--table-row-hover`·`--bg-card-hover` 로 칠한다 — 중립 칩 면을 빌리지 않는다.

    실측(수정 전, hover 강제 · 13화면 × 4테마): catppuccin 에서 `.tbl tr:hover td` ·
    `.issue:hover` · `.kpi:hover` · `.repo-card:hover` 가 surface1 을 칠해 그 안의 등급 F 칩 3.41 ·
    3차 글자 4.10 · 점수 숫자 3.94 였다.

    Rows and cards repaint hover through the dedicated hover tokens, never a neutral chip surface.
    """
    sites = hover_neutral_sites()
    offenders = sorted(f"{sel}  ({where})" for sel, where in sites.items() if sel not in _EXEMPT)
    assert not offenders, (
        "`:hover` 가 중립 칩 면으로 면을 칠한다 — 행이면 `var(--table-row-hover)`, 카드면 "
        "`var(--bg-card-hover)` 를 쓴다(제 글자만 얹는 컨트롤이면 사유와 함께 `_EXEMPT` 에):\n  "
        + "\n  ".join(offenders))


def test_the_scan_still_finds_the_exempted_controls():
    """🔴 대조군 — 스캔이 죽으면 위 시험은 「위반 0」으로 조용히 통과한다."""
    sites = hover_neutral_sites()
    assert sites, "중립 면을 칠하는 `:hover` 를 0곳 찾았다 — 스캔이 죽었다(공허한 초록)"
    stale = sorted(sel for sel in _EXEMPT if sel not in sites)
    assert not stale, (
        "소스에서 사라진 선택자를 아직 면제하고 있다 — 지우거나 갱신한다:\n  " + "\n  ".join(stale))
