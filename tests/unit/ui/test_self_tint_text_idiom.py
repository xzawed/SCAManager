"""«자기 틴트 면 + 같은 토큰 글자» 관용구를 리포 전체에서 금지한다 — #1639 W15 2차.

🔴 무엇을 금지하는가

    background: color-mix(in srgb, var(--X) 15%, transparent);
    color:      var(--X);                       /* ← 면을 만든 그 토큰을 글자로 */

   `--danger`·`--warning`·`--btn-on-accent` 같은 토큰은 «면» 으로 쓰려고 고른 값이다.
   그것을 15% 로 옅게 깔고 **같은 값을 글자로** 쓰면, 밝은 테마에서 글자와 면이 서로
   가까워져 대비가 무너진다. `--text-1/2/3` 만 예외다 — 그것들은 애초에 글자용으로
   골라 카드 위 여유가 있고, 자기 틴트를 깔아도 면이 거의 안 움직인다(실측 5.71~7.23).

🔴 왜 «값» 이 아니라 «관용구» 를 금지하는가: 바탕이 카드인지 그라디언트 헤더인지에 따라
   실제 비율이 달라져, 한 가지 배경 모델로는 정직하게 못 센다. 관용구 금지는 배경과
   무관하게 성립한다. 실제 비율은 e2e 대비 스윕이 «칠해진 픽셀» 로 잰다.

🔴 어떻게 찾았나: 커밋된 e2e 대비 감사는 `--text-2`/`--text-3`/`--accent-text` 로 칠해진
   글자만 판정한다. 그 필터를 떼고 「모든 글자」로 넓혀 스윕을 다시 돌리니(감사 308회 발화)
   예외 범주 밖 336행·고유 20자리가 나왔고 **그중 토큰 감사가 볼 수 있는 것은 0건**이었다.
   렌더 실측과 `tokens.css` 정적 계산이 소수점까지 일치했다 —
   pastel warning **2.44** · pastel error 3.76 · light warning 4.08 · catppuccin error 4.18.

   #1683 이 `.ri-badge-*` 두 곳을 고쳤지만 **같은 관용구의 형제 여섯 곳이 남아 있었다.**
   그것이 이 가드가 선택자 목록이 아니라 «관용구» 를 보는 이유다.

🔴 그리고 그 «관용구» 도 처음엔 한 가지 **표기** 로만 봤다. Grok claim-review `01a0a9e5` 가
   `color-mix(in srgb, transparent, var(--X) 15%)` 를 반례로 냈다 — 뜻은 같은데 인자 순서가
   반대라 빠져나갔다. 리포에 그 형태가 실재하지는 않았다(실측 0건). 실재하지 않는 회피
   경로를 열어 둔 채 「리포 전체에서 금지한다」고 적어 둔 것이 결함이었다.

Forbid painting text with the very token that tints its own background.
"""
from __future__ import annotations

import re

from ._contrast import ROOT, strip_css_comments

# 글자용으로 설계된 토큰 — 자기 틴트를 깔아도 면이 거의 안 움직인다.
_TEXT_TOKENS = {"--text-1", "--text-2", "--text-3"}

_COLOR = re.compile(r"(?<![-\w])color:\s*var\((--[\w-]+)\)")
_BG = re.compile(r"(?<![-\w])background(?:-color)?:\s*([^;]+);")
_RULE = re.compile(r"([^{}]+)\{([^}]*)\}")
_VAR = re.compile(r"var\(\s*(--[\w-]+)")


def _tinted_tokens(value: str) -> set[str]:
    """`color-mix(...)` 가 `transparent` 와 함께 섞는 토큰 이름들.

    🔴 인자 «순서» 를 보지 않는다. `color-mix(in srgb, transparent, var(--d) 15%)` 는
       `color-mix(in srgb, var(--d) 15%, transparent)` 와 같은 뜻인데,
       순서를 박아 둔 정규식은 앞쪽만 잡았다 — Grok claim-review `01a0a9e5` 의 반례다.
    Order-independent: color-mix arguments may be written either way round.
    """
    out: set[str] = set()
    for m in re.finditer(r"color-mix\(", value):
        depth, j = 1, m.end()
        while j < len(value) and depth:
            depth += (value[j] == "(") - (value[j] == ")")
            j += 1
        inner = value[m.end():j - 1]
        if "transparent" in inner:
            out |= {v.group(1) for v in _VAR.finditer(inner)}
    return out


def _sources() -> dict[str, str]:
    """정적 CSS + 템플릿 `<style>` 블록. 🔴 둘을 같이 봐야 한다 — 이 관용구의 여섯 곳 중
    네 곳이 템플릿 안에 있다."""
    out: dict[str, str] = {}
    for f in sorted((ROOT / "src" / "static" / "css").glob("*.css")):
        out[f.name] = strip_css_comments(f.read_text(encoding="utf-8"))
    for f in sorted((ROOT / "src" / "templates").rglob("*.html")):
        blocks = re.findall(r"<style[^>]*>(.*?)</style>", f.read_text(encoding="utf-8"),
                            re.S | re.I)
        if blocks:
            out[f.name] = strip_css_comments("\n".join(blocks))
    return out


def _self_tint_sites() -> list[tuple[str, str, str]]:
    sites = []
    for name, src in _sources().items():
        for m in _RULE.finditer(src):
            selector, body = m.group(1).strip().replace("\n", " "), m.group(2)
            bg, col = _BG.search(body), _COLOR.search(body)
            if not (bg and col):
                continue
            if col.group(1) in _tinted_tokens(bg.group(1)):
                sites.append((name, selector[-60:], col.group(1)))
    return sites


def test_the_idiom_is_caught_written_either_way_round():
    """🔴 Grok claim-review `01a0a9e5` 의 반례 — 인자 순서를 뒤집으면 빠져나갔다.

    리포에 그 형태가 실재하지는 않았다(실측 0건). 실재하지 않는 회피 경로를 열어 둔 채
    「리포 전체에서 금지한다」고 적어 둔 것이 결함이다.
    """
    token_first = "color-mix(in srgb, var(--danger) 15%, transparent)"
    transparent_first = "color-mix(in srgb, transparent, var(--danger) 15%)"
    assert _tinted_tokens(token_first) == {"--danger"}
    assert _tinted_tokens(transparent_first) == {"--danger"}
    # 🔴 파생되지 않은 바닥 — `transparent` 가 없으면 자기 틴트가 아니다.
    assert _tinted_tokens("color-mix(in srgb, var(--danger) 15%, var(--bg-1))") == set()


def test_the_scan_actually_reaches_both_static_css_and_template_styles():
    """🔴 공허화 방어 — 「위반 0」과 「아무것도 안 읽었다」를 가른다.

    이 관용구의 실제 사용처가 템플릿에 몰려 있어서, 정적 CSS 만 읽으면 조용히 통과한다.
    """
    srcs = _sources()
    assert any(n.endswith(".css") for n in srcs), "정적 CSS 를 하나도 안 읽었다"
    assert any(n.endswith(".html") for n in srcs), "템플릿 `<style>` 을 하나도 안 읽었다"
    # 규칙을 실제로 파싱했는가 — 이 리포에는 수백 개가 있다.
    assert sum(len(_RULE.findall(s)) for s in srcs.values()) > 200


def test_no_rule_paints_text_with_the_token_that_tints_its_own_background():
    bad = [(f, s, t) for f, s, t in _self_tint_sites() if t not in _TEXT_TOKENS]
    assert not bad, (
        "면을 만든 토큰을 글자로도 쓴다 — 면·테두리·글자를 «함께» 고른 잠긴 3종 세트"
        "(`--grade-c`/`--grade-f` 등)로 옮긴다:\n  "
        + "\n  ".join(f"{f}: {s}  ({t})" for f, s, t in bad))
