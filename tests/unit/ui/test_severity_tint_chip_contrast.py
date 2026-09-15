"""심각도 틴트 칩(`.ri-badge-*`)이 «잠긴 3종 세트» 를 쓰는가 — W15 실측에서 나온 결함.

🔴 왜 이 시험이 생겼나: 대비 감사가 `--text-2`/`--text-3`/`--accent-text` **세 토큰으로
   칠해진 글자만** 보고 있었다(#1639 W15). 「모든 글자」로 넓혀 재보니 반복 이슈 표의
   심각도 뱃지 네 조합이 AA 미달이었다 — 토큰 범위 감사에는 **구조적으로 안 보이던** 자리다.

   브라우저 실측(렌더 픽셀, 틴트 «안» 에서 표본):
     light  `.ri-badge-warning` 4.08 · pastel `.ri-badge-error` 3.75
     pastel `.ri-badge-warning` **2.43** · catppuccin `.ri-badge-error` 4.22

🔴 색만 바꿔서는 못 고친다 — `--warning`/`--danger` 를 15% 틴트로 깔고 **같은 토큰을 글자로**
   쓰는 형태 자체가 문제다(#1645 가 success 에서 같은 결론에 닿았다). 면·테두리·글자를
   «함께» 고른 잠긴 3종 세트(`--grade-c`/`--grade-f`)로 옮긴다.
"""
from __future__ import annotations

import re

from ._contrast import (AA, ROOT, THEMES, decl, over, parse_color, ratio, resolve,
                        strip_css_comments, theme_block)

_CSS = strip_css_comments(
    (ROOT / "src" / "static" / "css" / "repo_insights.css").read_text(encoding="utf-8"))
_TOKENS = (ROOT / "src" / "static" / "css" / "tokens.css").read_text(encoding="utf-8")

# {규칙 이름: 그 칩이 써야 하는 잠긴 3종 세트의 접두}
_CHIPS = {".ri-badge-error": "--grade-f", ".ri-badge-warning": "--grade-c"}


def _rule(selector: str) -> str:
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", _CSS)
    assert m, f"{selector} 규칙을 못 찾았다 — 이름이 바뀌었으면 이 시험을 따라 고친다"
    return m.group(1)


def _tok(theme: str, name: str) -> tuple:
    block = theme_block(_TOKENS, theme)
    raw = decl(block, name)
    assert raw, f"{theme} 에 `{name}` 이 없다"
    return parse_color(resolve(block, raw))


def test_severity_chips_do_not_paint_text_with_their_own_tint_token():
    """🔴 «틴트 면 + 같은 토큰 글자» 조합이 남아 있으면 red."""
    bad = []
    for sel in _CHIPS:
        body = _rule(sel)
        tinted = re.search(r"color-mix\([^)]*var\((--\w[\w-]*)\)[^)]*\)", body)
        colored = re.search(r"(?<!-)color:\s*var\((--\w[\w-]*)\)", body)
        if tinted and colored and tinted.group(1) == colored.group(1):
            bad.append(f"{sel}: 면과 글자가 둘 다 `var({tinted.group(1)})` 다")
    assert not bad, (
        "심각도 칩이 자기 틴트 토큰을 글자색으로도 쓴다 — 잠긴 3종 세트로 옮긴다:\n  "
        + "\n  ".join(bad))


def test_severity_chips_meet_aa_on_their_own_tint():
    """🔴 네 테마 전부에서, 그 칩의 «자기 면» 위 글자가 AA 를 넘어야 한다.

    면 = 3종 세트의 `-bg` 를 카드 위에 합성한 값. 글자 = 같은 세트의 본색.
    """
    bad = []
    for sel, prefix in _CHIPS.items():
        for theme in THEMES:
            block = theme_block(_TOKENS, theme)
            card = parse_color(resolve(block, decl(block, "--bg-card")))
            surface = over(_tok(theme, f"{prefix}-bg"), card)
            got = ratio(over(_tok(theme, prefix), surface), surface)
            if got < AA:
                bad.append(f"{sel} {theme}: {got:.2f} < {AA}")
    assert not bad, (
        "잠긴 3종 세트가 자기 면 위에서 AA 미달이다 — 토큰을 고쳐야 한다:\n  "
        + "\n  ".join(bad))
