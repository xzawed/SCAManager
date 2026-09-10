"""`--success` 를 «글자» 로도 «면» 으로도 쓰는 데서 오는 AA 미달.

## 무엇이 문제였나

`--success` 하나가 세 역할을 겸한다 — 카드 바탕 «위의 글자», 칩의 «틴트 면», 그리고
버튼의 «채운 면». 세 역할은 서로 다른 대비를 요구하는데 값이 하나라 전부 만족할 수 없다.
`--danger` 에서 이미 같은 구조가 나왔고(#1642), 이쪽은 아직 남아 있었다.

## 실측 (2026-09-10, 400조합 픽셀 + 정적 계산)

| 역할 | 현재 | 판정 |
|---|---|---|
| 카드 위 «글자» | light **3.77** · pastel **3.13** | 미달 → `--success-text` 로 분리 |
| 채운 «면» 위 글자 | light **3.77**(`--btn-on-accent` = 흰색) | 미달 → `--success-text-on` 으로 분리 |
| 15% «틴트» 위 글자 | 위 `--success-text` 로 바꿔도 **3.88 / 3.96** | 🔴 이 축은 여기서 못 고친다(아래) |

## 🔴 틴트 칩 — 색만 바꿔서는 못 고친다

`.severity-low`·`.issue-badge--closed`·`.fb-btn.active.fb-up`·`.hook-alert.ok`·
`.save-toast-ok` 는 같은 규칙에서 틴트 면·테두리·글자를 모두 `--success` 로 잡았다.
바탕용으로 진하게 만든 `--success-text` 를 얹어도 틴트 위에서는 **3.88(light) /
3.96(pastel)** 이라 여전히 미달이다.

그래서 면·테두리·글자를 «함께» 고른 **잠긴 3종 세트**(`--grade-a`/`-bg`/`-bd`)로 옮겼다 —
#1633 이 등급 칩에 한 처방과 같다. 그 세트는 자기 면 위에서 **4.52~8.40** 으로 네 테마
전부 통과한다.

🔴 처음에는 이 자리를 «세기만» 했다(고칠 방법을 정하기 전이었으므로). 세는 시험을
0-요구로 뒤집을 때 **반공허 단언의 근거도 함께 옮겨야 한다** — 「위반이 있는가」로 두면
전부 고친 순간 그 단언이 발화한다(실제로 발화했다). 계기 생존은 «대체 토큰이 실제로
쓰이는가» 로 잰다.
"""
from __future__ import annotations

import re
from pathlib import Path

from ._contrast import (AA, ROOT, THEMES, decl, over, parse_color, ratio, resolve,
                        strip_css_comments, theme_block)

_TOKENS = (ROOT / "src" / "static" / "css" / "tokens.css").read_text(encoding="utf-8")

# 틴트 칩 — 같은 규칙에서 `--success` 를 «면» 으로도 쓰는 자리. 여기서 고치지 않는다.
_TINT_MARKER = re.compile(r"color-mix\([^)]*--success[^)]*\)")


def _strip_jinja(src: str) -> str:
    """🔴 Jinja 태그를 먼저 걷어낸다.

    `style="color: {% if … %}var(--danger){% else %}var(--success){% endif %}"` 처럼
    선언 «값 안» 에 분기가 끼면, `color:` 와 `var(--success)` 가 붙어 있지 않고
    `%}` 의 중괄호가 CSS 규칙 끝으로 오인된다. 그래서 이 자리는 두 판의 스캐너가
    연달아 놓쳤다(Grok `01a0880b`). 태그를 지우면 값만 남는다.
    """
    return re.sub(r"\{%.*?%\}|\{\{.*?\}\}", "", src, flags=re.S)


def _sources() -> list[Path]:
    return (sorted((ROOT / "src" / "templates").rglob("*.html"))
            + sorted((ROOT / "src" / "static").rglob("*.css")))


def _tok(theme: str, name: str) -> tuple:
    block = theme_block(_TOKENS, theme)
    value = resolve(block, decl(block, name))
    assert value, f"{theme} 에서 `{name}` 을 해석하지 못했다"
    return parse_color(value)


def success_as_text_sites() -> dict[str, dict]:
    """{어디: {'tint': 틴트칩인가}} — `--success` 를 글자색으로 쓰는 자리."""
    found: dict[str, dict] = {}
    for path in _sources():
        src = _strip_jinja(strip_css_comments(path.read_text(encoding="utf-8")))
        # 🔴 `color:` 와 `var(--success)` 사이에 Jinja 분기가 끼면 붙어 있지 않다 —
        #    `style="color: {% if … %}var(--danger){% else %}var(--success){% endif %}"`
        #    가 그 형태였고, 첫 판 스캐너는 그 자리를 통째로 놓쳤다(Grok `01a0880b`).
        #    선언 «값 쪽» 어디에든 `var(--success)` 가 있으면 글자색으로 센다.
        for m in re.finditer(r"(?<![-\w])color\s*:[^;}\"]*var\(\s*--success\s*[,)]", src):
            # 같은 «규칙» 안에 success 틴트가 있으면 칩이다.
            start = src.rfind("{", 0, m.start())
            end = src.find("}", m.start())
            rule = src[start:end] if start != -1 and end != -1 else ""
            line = src[:m.start()].count("\n") + 1
            found[f"{path.name}:{line}"] = {"tint": bool(_TINT_MARKER.search(rule))}
    return found


def _replacement_sites() -> int:
    """`--success-text` 를 글자로 쓰는 자리 수 — 계기가 살아 있는지 재는 대조군."""
    n = 0
    for path in _sources():
        src = _strip_jinja(strip_css_comments(path.read_text(encoding="utf-8")))
        n += len(re.findall(r"(?<![-\w])color\s*:[^;}\"]*var\(\s*--success-text\s*[,)]", src))
    return n


def test_success_is_not_used_as_text_on_plain_grounds():
    """🔴 바탕 위 글자에 `--success` 를 쓰면 밝은 테마에서 AA 미달이다.

    실측: light 3.77 · pastel 3.13. 글자용은 `--success-text` 를 쓴다.
    """
    # 🔴 반공허 확인을 «위반이 있는가» 로 두면 안 된다. 전부 고친 뒤에는 0이 정답이라
    #    그 단언이 발화한다(실제로 발화했다). 계기가 살아 있는지는 «대체 토큰이 실제로
    #    쓰이는가» 로 잰다 — 스캔 경로·정규식이 죽으면 그쪽도 0이 된다.
    assert _replacement_sites() > 0, (
        "`color: var(--success-text)` 를 0곳 찾았다 — 스캔이 죽었다(공허한 초록)")
    sites = success_as_text_sites()
    plain = sorted(where for where, info in sites.items() if not info["tint"])
    assert not plain, (
        "바탕 위 글자에 `--success` 를 쓴다 — `var(--success-text)` 로 바꾼다:\n  "
        + "\n  ".join(plain))


def test_no_success_tint_chip_remains():
    """🔴 틴트 칩은 «잠긴 3종 세트» 로 옮긴다 — 색만 바꿔서는 못 고친다.

    실측: 바탕용으로 진하게 만든 `--success-text` 를 얹어도 15% 틴트 위에서는
    light **3.88** · pastel **3.96** 이라 여전히 미달이다. 면·테두리·글자를 «함께»
    고른 `--grade-a` 3종 세트는 자기 면 위에서 4.52~8.40 으로 네 테마 전부 통과한다
    (#1633 이 등급 칩에 한 처방과 같다).

    이전 판은 이 자리를 «세기만» 했다(고칠 수 없었으므로). 이제 0을 요구한다.
    """
    chips = sorted(w for w, info in success_as_text_sites().items() if info["tint"])
    assert not chips, (
        "success 를 «틴트 면 + 글자» 로 함께 쓰는 칩이 남아 있다 — "
        "`--grade-a`/`-bg`/`-bd` 3종 세트로 옮긴다:\n  " + "\n  ".join(chips))


def test_success_text_token_meets_aa_on_every_card():
    """글자용 토큰이 네 테마 카드 바탕에서 AA 를 넘어야 한다."""
    bad = []
    for theme in THEMES:
        block = theme_block(_TOKENS, theme)
        card = parse_color(resolve(block, decl(block, "--bg-card")))
        assert decl(block, "--success-text"), (
            f"{theme} 에 `--success-text` 가 없다 — 글자용과 면용을 한 값으로 겸할 수 없다")
        got = ratio(over(_tok(theme, "--success-text"), card), card)
        if got < AA:
            bad.append(f"{theme}: {got:.2f} < {AA}")
    assert not bad, "`--success-text` 가 카드 바탕에서 AA 미달이다:\n  " + "\n  ".join(bad)


def test_text_on_a_filled_success_surface_meets_aa():
    """🔴 success 로 «채운» 면 위 글자는 accent 용 on-토큰을 빌려 쓰면 안 된다.

    실측: `repo_detail.html::.filter-btn[data-source="push"].active` 가 light 에서
    흰 글자 **3.77** 이었다 — danger 에서 고친 것과 같은 부류다(#1642).
    """
    bad = []
    for theme in THEMES:
        block = theme_block(_TOKENS, theme)
        assert decl(block, "--success-text-on"), (
            f"{theme} 에 `--success-text-on` 이 없다 — accent 용 on-토큰은 면이 달라 "
            "테마마다 우연히 맞거나 틀린다")
        fill = _tok(theme, "--success")
        got = ratio(over(_tok(theme, "--success-text-on"), fill), fill)
        if got < AA:
            bad.append(f"{theme}: {got:.2f} < {AA}")
    assert not bad, "success 면 위 글자가 AA 미달이다:\n  " + "\n  ".join(bad)


def test_filled_success_controls_use_the_on_token():
    """정의 ≠ 배선 — 토큰을 만들어도 쓰는 자리가 안 바뀌면 화면은 그대로다."""
    bad = []
    for path in _sources():
        src = strip_css_comments(path.read_text(encoding="utf-8"))
        for m in re.finditer(r"background:\s*var\(--success[^;]*;[^}\"]*", src):
            chunk = m.group(0)
            cm = re.search(r"(?<![-\w])color\s*:\s*([^;}\"]+)", chunk)
            if not cm:
                continue                      # 면만 칠하는 자리(점수 막대 등)
            value = cm.group(1).strip()
            if "--success-text-on" in value:
                continue
            bad.append(f"{path.name}: color:{value}")
    assert not bad, (
        "success 로 채운 면 위 글자가 전용 on-토큰을 쓰지 않는다:\n  " + "\n  ".join(bad))


def test_migrated_chips_keep_their_siblings_border_treatment():
    """🔴 형제와 «테두리 취급» 이 갈리지 않아야 한다.

    `.severity-low` 는 `.severity-high`(`--danger`)·`.severity-medium`(`--warning`) 과
    나란히 놓인다. 셋 다 **불투명** 테두리였는데, 3종 세트로 옮기며 low 만
    `--grade-a-bd`(반투명/연한 민트, 카드 대비 1.28~2.41)로 바뀌면 셋의 모양이 갈린다.
    `.fb-btn.active.fb-up` 도 형제 `.fb-btn.active.fb-down` 이 불투명 `--danger` 를 쓴다.

    🔴 이건 **1.4.11 위반이 아니다.** 이 리포는 「보이는 글자가 있는 컨트롤은 경계 표시
    요구 대상이 아니다」를 실측으로 확립했다(#1621, 185/216 → 1/58). 여기서 잡는 것은
    «접근성» 이 아니라 «일관성» 이다 — 그렇게 적어야 다음 사람이 기준을 헷갈리지 않는다.
    Grok `01a08ab4` 가 테두리 약화를 지적했고, 그 지적의 «옳은 부분» 이 이것이다.
    """
    src = strip_css_comments(
        (ROOT / "src" / "templates" / "analysis_detail.html").read_text(encoding="utf-8"))
    pairs = [(".severity-low", (".severity-high", ".severity-medium")),
             (".fb-btn.active.fb-up", (".fb-btn.active.fb-down",))]
    bad = []
    for target, siblings in pairs:
        m = re.search(re.escape(target) + r"\s*\{([^}]*)\}", src)
        assert m, f"`{target}` 규칙이 없다 — 시험이 늙었다"
        got = re.search(r"border(?:-color)?\s*:[^;]*var\(\s*(--[\w-]+)\s*\)", m.group(1))
        assert got, f"`{target}` 에 토큰 테두리가 없다"
        if got.group(1).endswith("-bd"):
            bad.append(f"{target}: `{got.group(1)}` — 형제 {siblings} 는 불투명 토큰을 쓴다")
    assert not bad, (
        "3종 세트로 옮긴 칩만 테두리가 옅어져 형제와 갈린다:\n  " + "\n  ".join(bad))
