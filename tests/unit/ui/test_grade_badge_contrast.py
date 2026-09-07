"""등급·심각도 뱃지의 글자 대비 — 템플릿이 테마 토큰을 하드코딩으로 덮고 있었다.

#1609 가 `.btn-primary { color: #fff }` 에서 본 것과 «같은» 형태다: 페이지 인라인
`<style>` 의 리터럴이 `components.css` 의 테마별 토큰을 같은 명시도로 나중에 와서 덮는다.

실측(픽셀, 수정 전): `.grade--b` 가 light·pastel·catppuccin 에서 1.84~4.35.
템플릿 넷이 dark 용 색(`#60a5fa` 등)을 그대로 박아, 밝은 테마에서도 그 색이 칠해졌다.
토큰판으로 되돌리면 같은 자리가 light 5.17 로 올라간다.
"""
import re

from ._contrast import (AA, ROOT, THEMES, card_surface, decl, over, parse_color, ratio,
                        read, resolve, strip_css_comments, theme_block)

_GRADES = ("a", "b", "c", "d", "f")

# 등급 칩을 그리는 템플릿들. 여기에 리터럴이 있으면 테마 토큰이 무력화된다.
_TEMPLATES = ("src/templates/analysis_detail.html", "src/templates/dashboard.html",
              "src/templates/landing.html", "src/templates/overview.html",
              "src/templates/repo_detail.html")

_GRADE_MARKUP = 'class="grade'


def _templates_rendering_grade_chips() -> list[str]:
    """등급 칩을 «렌더하는» 템플릿 — 열거가 아니라 파생이다.

    🔴 술어를 `grade-badge` 로 잡으면 안 된다 — 실측상 그 문자열은 production 템플릿
    **0건**에 맞는다(`repo_insights` 계열의 다른 컴포넌트 이름이다). 실제 마크업은
    `class="grade ...` 이고, 그 기준으로 세면 5건이다. 목록은 4건이었다 —
    `landing.html` 이 밖에 있었고, 거기에 색 규칙이 생겨도 아무도 재지 않았다.
    """
    out = []
    for path in sorted((ROOT / "src" / "templates").rglob("*.html")):
        if _GRADE_MARKUP in path.read_text(encoding="utf-8"):
            out.append(path.relative_to(ROOT).as_posix())
    return out


_COMPONENTS = "src/static/css/components.css"


def _severity_sources() -> dict[str, set[str]]:
    """칩 수식자로 렌더될 수 있는 심각도 — **출처별로** 나눠 돌려준다.

    🔴 템플릿을 훑어 파생하면 **원리적으로 0건**이다. 마크업은
    `grade--{{ (iss.get('severity', 'warning') or 'warning') | lower }}` 처럼 **동적**이라
    이름이 소스에 없다. 첫 판이 그렇게 세다가 공허해졌고, 뮤테이션이 그것을 잡았다.

    🔴 합집합 하나로 돌려주면 «한 출처가 죽어도» 다른 쪽이 채워 통과한다 — 실측으로
    enum 파생을 죽였을 때 대문자 리터럴 쪽이 남아 초록이었다. 그래서 나눠 돌려주고
    호출부가 **각각** 비지 않았는지 본다.

    출처는 둘이다(`dashboard_service` 가 「이중 표현」으로 문서화한 그대로):
      1. `Severity` StrEnum 의 값 — 분석기가 «지금» 내는 것.
      2. 코드가 severity 로 «받아들이는» 대문자 리터럴 — 저장된 옛 행에서 온다.
    """
    from src.analyzer.pure.registry import Severity  # noqa: PLC0415

    legacy: set[str] = set()
    for rel in ("src/notifier/github_issue.py", "src/services/dashboard_service.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        for m in re.finditer(r'severity[^\n]*?\.upper\(\)[^\n]*', text):
            legacy |= {v.lower() for v in re.findall(r'"([A-Z]+)"', m.group(0))}
    return {"enum": {s.value.lower() for s in Severity}, "legacy": legacy}


def test_every_renderable_severity_maps_onto_a_grade_token():
    """🔴 렌더될 수 있는 모든 심각도가 «등급 3종 세트» 로 정의돼 있어야 한다.

    실측(이 결함이 살아남은 경로): 이슈 심각도 여섯(`error`·`warning`·`high`·`medium`·
    `low`·`info`)은 `components.css` 에 정의가 **없었고**, 페이지 `<style>` 이 리터럴 hex 로
    대신 칠했다. 페이지 스타일은 컴포넌트보다 나중에 로드돼 이기므로 테마 토큰이 닿지
    않았다 — light 1.57~2.46 · pastel 1.51~2.38 (24조합 중 16건 미달).

    🔴 새 색을 «만드는» 것도 막는다. 정의가 있어도 `--grade-*` 가 아니면 그 칩의 대비는
    아무도 재지 않는다 — 위 AA 시험이 도는 것은 `--grade-*` 조합뿐이다.

    Every severity the code can render must resolve to the AA-locked grade triple.
    """
    sources = _severity_sources()
    # 🔴 계기 자기검증 — 출처가 «각각» 살아 있어야 한다. 합집합만 보면 한쪽이 죽어도
    #    다른 쪽이 채워 초록이 된다(실측으로 그 상태를 한 번 밟았다).
    for name, values in sources.items():
        assert values, f"심각도 출처 `{name}` 이 0개를 냈다 — 스캔이 죽었다(공허한 초록)"
    used = set().union(*sources.values())

    css = strip_css_comments(read(_COMPONENTS))
    mapped = {}
    for m in re.finditer(r"([^{}]*\.grade--[a-z][^{}]*)\{([^}]*)\}", css):
        token = re.search(r"--g-color\s*:\s*var\(\s*(--grade-[a-z]+)\s*\)", m.group(2))
        if not token:
            continue
        for name in re.findall(r"\.grade--([a-z]+)", m.group(1)):
            mapped[name] = token.group(1)

    missing = sorted(n for n in used if n not in mapped)
    assert not missing, (
        f"렌더될 수 있는 심각도가 `{_COMPONENTS}` 에서 등급 토큰으로 정의되지 않았다 — "
        f"정의가 없으면 페이지 스타일이 리터럴로 칠하고 아무도 재지 않는다: {missing}")


def test_every_template_rendering_a_grade_chip_is_in_the_list():
    """🔴 목록 밖 템플릿의 등급 칩은 «아무도 안 잰다» — 열거 가드의 공통 결함이다."""
    found = _templates_rendering_grade_chips()
    assert found, "등급 칩을 쓰는 템플릿을 0개 찾았다 — 스캔이 죽었다(공허한 초록)"
    missing = [f for f in found if f not in _TEMPLATES]
    assert not missing, (
        "등급 칩을 렌더하는데 `_TEMPLATES` 밖이다 — 하드코딩 색을 아무도 재지 않는다:\n  "
        + "\n  ".join(missing))
    stale = [f for f in _TEMPLATES if f not in found]
    assert not stale, (
        "목록에 있는데 등급 칩이 없다 — 낡은 항목은 거짓을 가르친다:\n  " + "\n  ".join(stale))


def test_no_template_hardcodes_grade_chip_colours():
    """🔴 등급 칩 색을 템플릿에 박지 않는다 — 테마별 토큰이 이겨야 한다.

    실측: 네 템플릿이 `.grade--b { color: #60a5fa }` 를 갖고 있었다. `components.css` 의
    `.grade--b { --g-color: var(--grade-b) }` 와 명시도가 같고 «나중에» 로드되므로,
    light·pastel 이 이미 갖고 있던 어두운 등급색이 한 번도 칠해지지 않았다.
    """
    offenders = []
    for rel in _TEMPLATES:
        src = strip_css_comments(read(rel))
        # 🔴 `[abcdf]` 로 좁히면 안 된다 — 같은 파일을 읽으면서도 이슈 심각도 수식자
        #    (`error`·`warning`·`high`·`medium`·`low`·`info`) 여섯을 지나쳤다. 그것들이
        #    리터럴 hex 로 박혀 24조합 중 16건이 AA 미달이었는데 이 가드는 초록이었다.
        #    수식자 «이름» 을 열거하지 않는다 — 새 이름이 생겨도 자동으로 걸리게 한다.
        for m in re.finditer(r"\.grade--[a-z]+\s*\{([^}]*)\}", src):
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


def test_badge_colours_are_not_redefined_outside_components():
    """🔴 `.badge--*` 색을 `components.css` 밖에서 다시 정하지 않는다.

    `admin.css` 가 admin 화면에서 «나중에» 로드돼 `components.css` 의 등급 토큰 판을
    덮고 있었다. 그 사본은 두 결함을 함께 들여왔다 — 틴트를 `transparent` 에 섞어
    바탕이 움직였고(실측 2.68), 글자는 크롬용 `--status-*` 를 썼다.

    같은 사실의 사본은 갈라진다. 정본은 `components.css` 한 곳이다.
    """
    offenders = []
    for path in sorted((ROOT / "src").rglob("*.css")) + sorted(
        (ROOT / "src" / "templates").glob("*.html")
    ):
        if path.name == "components.css":
            continue
        text = strip_css_comments(path.read_text(encoding="utf-8"))
        for m in re.finditer(r"\.badge--(?:success|danger|warn|info)\b[^{]*\{([^}]*)\}", text):
            if re.search(r"(?<![-\w])(?:color|background)\s*:", m.group(1)):
                offenders.append(f"{path.relative_to(ROOT).as_posix()}: "
                                 f"{m.group(0)[:60].strip()}")
    assert not offenders, (
        "`.badge--*` 색이 `components.css` 밖에서 재정의된다 — 나중에 로드되는 쪽이\n"
        "정본을 덮어 등급 토큰이 무력화된다:\n  " + "\n  ".join(offenders)
    )
