"""차트 격자선 색 — 문자열 이어붙이기는 «무효 색» 을 만든다.

실측(브라우저 canvas 로 되읽음):

    rgba(255, 255, 255, 0.06)44  →  ctx.strokeStyle 이 거부, 이전 값 유지
    #ececf344                    →  rgba(236, 236, 243, 0.267) 로 정상

`border + '44'` 는 토큰이 **16진일 때만** 동작한다. dark(`rgba(255,255,255,0.06)`)와
catppuccin(`rgba(205,214,244,0.08)`)에서는 무효라, 격자선이 직전 strokeStyle 인
**불투명 검정**으로 칠해졌다 — 실측 `repoTrendChart` 3/3 행이 `0,0,0,255`.

정본은 이미 있었다: `--chart-grid` 가 네 테마에 정의돼 있는데 **소비자가 0곳**이었다.
"""
import re

from ._contrast import THEMES, decl, parse_color, read, resolve, strip_css_comments, theme_block

# 차트가 있는 템플릿 — 이 목록이 비면 테스트가 공허하다
_CHART_TEMPLATES = (
    "src/templates/dashboard.html",
    "src/templates/repo_detail.html",
    "src/templates/analysis_detail.html",
)


def test_chart_grid_color_never_uses_string_concatenation():
    """🔴 색 값에 문자열을 이어붙이지 않는다 — 토큰 형식이 테마마다 다르다.

    `x + '44'` 는 16진 토큰에서만 유효하고 `rgba()` 토큰에서는 파싱 불가 문자열이 된다.
    예외도 경고도 없이 «직전 색» 으로 칠해지므로 조용히 틀린다.
    """
    offenders = []
    scanned = 0
    for rel in _CHART_TEMPLATES:
        # 🔴 주석을 먼저 지운다 — 「무엇이 틀렸었나」를 적은 «내» 주석이 이 판정식에
        #    걸려 거짓 red 를 냈다. 가드는 산문이 아니라 코드를 봐야 한다.
        src = strip_css_comments(read(rel))
        scanned += 1
        for m in re.finditer(r"^.*\+\s*['\"][0-9a-fA-F]{2}['\"].*$", src, re.MULTILINE):
            offenders.append(f"{rel}: {m.group(0).strip()[:90]}")
    assert scanned == len(_CHART_TEMPLATES), "차트 템플릿을 다 못 읽었다"
    assert not offenders, (
        "색 문자열에 16진 알파를 이어붙인다 — rgba() 토큰에서 무효 색이 된다:\n  "
        + "\n  ".join(offenders))


def test_every_chart_grid_reads_the_chart_grid_token():
    """격자선 색은 `--chart-grid` 에서 온다.

    🔴 「이어붙이지 않는다」만으로는 부족하다 — `border` 를 그대로 써도 통과하는데,
    그러면 light/pastel 에서 27% 였던 선이 100% 로 진해진다. 어떤 토큰을 쓰는지를 본다.
    """
    found = 0
    offenders = []
    for rel in _CHART_TEMPLATES:
        src = strip_css_comments(read(rel))
        for m in re.finditer(r"grid\s*:\s*\{([^}]*)\}", src):
            body = m.group(1)
            cm = re.search(r"color\s*:\s*([^,}]+)", body)
            if not cm:
                continue
            found += 1
            expr = cm.group(1).strip()
            if "gridColor" not in expr and "--chart-grid" not in expr:
                offenders.append(f"{rel}: grid color = {expr[:70]}")
    assert found >= 4, f"격자선 설정을 {found}곳만 찾았다 — 못 재면 초록이 아니라 red 다"
    assert not offenders, (
        "격자선이 `--chart-grid` 를 쓰지 않는다:\n  " + "\n  ".join(offenders))
    for rel in _CHART_TEMPLATES:
        src = strip_css_comments(read(rel))
        if "gridColor" in src:
            assert "--chart-grid" in src, f"{rel}: gridColor 를 쓰는데 토큰을 안 읽는다"


def test_chart_grid_token_parses_in_every_theme():
    """네 테마의 `--chart-grid` 가 «읽히는 색 형식» 이어야 한다.

    못 읽는 형식이면 이 계기가 예외로 죽는다 — 초록으로 넘기지 않는다.
    """
    src = read("src/static/css/tokens.css")
    for theme in THEMES:
        block = theme_block(src, theme)
        c = parse_color(resolve(block, decl(block, "--chart-grid")))
        assert 0 < c[3] <= 1, f"{theme}: --chart-grid 알파가 {c[3]} — 안 보이거나 불투명하다"
