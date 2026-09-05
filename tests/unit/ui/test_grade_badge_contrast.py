"""등급·심각도 뱃지의 글자 대비 — 템플릿이 테마 토큰을 하드코딩으로 덮고 있었다.

#1609 가 `.btn-primary { color: #fff }` 에서 본 것과 «같은» 형태다: 페이지 인라인
`<style>` 의 리터럴이 `components.css` 의 테마별 토큰을 같은 명시도로 나중에 와서 덮는다.

실측(픽셀, 수정 전): `.grade--b` 가 light·pastel·catppuccin 에서 1.84~4.35.
템플릿 넷이 dark 용 색(`#60a5fa` 등)을 그대로 박아, 밝은 테마에서도 그 색이 칠해졌다.
토큰판으로 되돌리면 같은 자리가 light 5.17 로 올라간다.
"""
import re

from ._contrast import (AA, THEMES, card_surface, decl, over, parse_color, ratio,
                        read, resolve, strip_css_comments, theme_block)

_GRADES = ("a", "b", "c", "d", "f")

# 등급 칩을 그리는 템플릿들. 여기에 리터럴이 있으면 테마 토큰이 무력화된다.
_TEMPLATES = ("src/templates/analysis_detail.html", "src/templates/dashboard.html",
              "src/templates/overview.html", "src/templates/repo_detail.html")


def test_no_template_hardcodes_grade_chip_colours():
    """🔴 등급 칩 색을 템플릿에 박지 않는다 — 테마별 토큰이 이겨야 한다.

    실측: 네 템플릿이 `.grade--b { color: #60a5fa }` 를 갖고 있었다. `components.css` 의
    `.grade--b { --g-color: var(--grade-b) }` 와 명시도가 같고 «나중에» 로드되므로,
    light·pastel 이 이미 갖고 있던 어두운 등급색이 한 번도 칠해지지 않았다.
    """
    offenders = []
    for rel in _TEMPLATES:
        src = strip_css_comments(read(rel))
        for m in re.finditer(r"\.grade--[abcdf]\s*\{([^}]*)\}", src):
            body = m.group(1)
            if re.search(r"#[0-9a-fA-F]{3,6}|rgba?\(", body):
                offenders.append(f"{rel}: .grade--* 에 리터럴 색 — {body.strip()[:70]}")
    assert not offenders, (
        "등급 칩 색이 템플릿에 하드코딩돼 테마 토큰을 덮는다:\n  " + "\n  ".join(offenders)
    )


def test_grade_chip_text_meets_aa_on_the_card_ground():
    """🔴 다섯 등급 칩의 글자가 «카드 면 위에서» 네 테마 전부 AA 를 넘어야 한다.

    칩은 `--grade-X-bg`(틴트)를 카드 면 위에 얹고 그 위에 `--grade-X` 를 쓴다.
    실측(하드코딩 상태): light 1.57~2.46 · pastel 1.51~2.38.

    🔴 **이 검사가 덮는 바탕은 `--bg-card` 하나다.** 같은 칩이 hero 배너처럼 accent 로
    물든 «다른» 면 위에도 놓이는데, 그 면은 토큰이 아니라 그라디언트라 여기서 계산할 수
    없다(실측: catppuccin 등급칩이 repo 상세 hero 위에서 3.40). 그 축은 픽셀 측정이
    맡는다 — 이 테스트를 「전부 통과」로 읽지 말 것.

    This only covers the card ground; the same chip also sits on accent-tinted hero banners,
    which are gradients this calculation cannot model.
    """
    src = read("src/static/css/tokens.css")
    failures = []
    for theme in THEMES:
        block = theme_block(src, theme)
        card = card_surface(block)
        for g in _GRADES:
            chip = over(parse_color(resolve(block, decl(block, f"--grade-{g}-bg"))), card)
            fg = parse_color(resolve(block, decl(block, f"--grade-{g}")))
            r = ratio(over(fg, chip), chip)
            if r < AA:
                failures.append(f"[{theme}] --grade-{g} on its chip: {r:.2f} < {AA}")
    assert not failures, "등급 칩 글자가 AA 미달인 조합:\n  " + "\n  ".join(failures)


def test_grade_base_rule_does_not_reset_the_per_grade_border():
    """🔴 페이지의 `.grade` 규칙이 `border` «단축» 을 쓰면 등급별 테두리 색이 사라진다.

    `base.html` 이 `.grade--X { border-color: var(--grade-X-bd) }` 를 «먼저» 정한다.
    페이지 템플릿의 `.grade { border: 1px solid transparent }` 는 명시도가 같고 나중에
    오므로 `border-color` 까지 되감는다. 하드코딩 블록을 지우기 전에는 그 블록이
    유일하게 «더 나중에» 색을 되살리고 있었다 — 지우자 테두리가 투명해졌다.

    The `border` shorthand also resets border-color, silently dropping the per-grade tint.
    """
    offenders = []
    for rel in _TEMPLATES:
        src = strip_css_comments(read(rel))
        for m in re.finditer(r"(?:^|[}\n;])\s*\.grade\s*\{([^}]*)\}", src, re.MULTILINE):
            body = m.group(1)
            if re.search(r"(?<![-\w])border\s*:", body):
                offenders.append(f"{rel}: `.grade` 가 border 단축을 쓴다 — {body.strip()[:60]}")
    assert not offenders, (
        "`.grade` 가 border 단축으로 등급별 테두리 색을 되감는다 "
        "(굵기·선형만 정하고 색은 `.grade--X` 에 맡길 것):\n  " + "\n  ".join(offenders)
    )
