"""등급·심각도 뱃지의 글자 대비 — 템플릿이 테마 토큰을 하드코딩으로 덮고 있었다.

#1609 가 `.btn-primary { color: #fff }` 에서 본 것과 «같은» 형태다: 페이지 인라인
`<style>` 의 리터럴이 `components.css` 의 테마별 토큰을 같은 명시도로 나중에 와서 덮는다.

실측(픽셀, 수정 전): `.grade--b` 가 light·pastel·catppuccin 에서 1.84~4.35.
템플릿 넷이 dark 용 색(`#60a5fa` 등)을 그대로 박아, 밝은 테마에서도 그 색이 칠해졌다.
토큰판으로 되돌리면 같은 자리가 light 5.17 로 올라간다.
"""
import re

from ._contrast import (AA, HOVER_GROUNDS, ROOT, THEMES, over, paint_colours, ratio, read,
                        strip_css_comments, text_grounds, token_scope)

_GRADES = ("a", "b", "c", "d", "f")

# 등급색이 앉는 바탕 = `_contrast.text_grounds` 에서 «중립 칩 면» 하나를 뺀 것.
# 등급색은 자기 틴트 칩의 글자이거나 행·카드·페이지 위 맨 글자다 — 중립 칩(`--bg-mute`) 위에
# 얹지 않는다. catppuccin 은 그 면이 surface1 이라 F 칩 3.41 · 맨 글자 3.94 다(팔레트 그대로).
# 그 제외가 정당한 근거는 `test_no_rule_paints_grade_text_on_a_neutral_chip_surface` 다.
# 행·카드 hover 가 이 면을 빌려 칠하던 것이 회고 P1-28 이었다 — hover 면은 `HOVER_GROUNDS` 로 따로 잰다.
# Grade colours sit on their own tint or on rows/cards/page — never on the neutral chip surface.
_NEUTRAL_CHIP_SURFACES = ("--bg-mute",)

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


def _grade_grounds(theme: str) -> dict[str, tuple]:
    return {k: v for k, v in text_grounds(theme).items() if k not in _NEUTRAL_CHIP_SURFACES}


def test_grade_text_meets_aa_on_every_ground_it_sits_on():
    """🔴 다섯 등급색이 «칩 글자» 로도 «맨 글자» 로도, 앉는 모든 바탕에서 AA 를 넘어야 한다.

    칩은 `--grade-X-bg`(틴트)를 바탕 위에 얹고 그 위에 `--grade-X` 를 쓴다. 맨 글자는
    점수 숫자(`.score-val`)·증감(`.ri-delta-*`)처럼 바탕에 바로 앉는다.

    🔴 종전 판은 카드 «한 면» 만 쟀고, 여유가 0.00~0.04 였다(회고 P2-19). 그래서 행에
    마우스를 올려 바탕이 `--bg-mute` 로 바뀌면 light 점수 숫자 4.13 · catppuccin F 칩 3.41 로
    떨어지는 것을 못 봤다(P1-28). 페이지 바탕·body 그라디언트 stop·hover 면을 다 잰다.

    🔴 hero 배너처럼 accent 그라디언트로 물든 면은 토큰이 아니라 여기서 계산할 수 없다 —
    그 축은 e2e 픽셀 측정이 맡는다.

    The previous version measured the card alone with 0.00-0.04 headroom; a hovered row
    dropped grade text below AA. Every page ground, gradient stop and hover surface is measured.
    """
    src = read("src/static/css/tokens.css")
    failures = []
    for theme in THEMES:
        scope = token_scope(src, theme)
        grounds = _grade_grounds(theme)
        # 🔴 hover 면이 목록에서 빠지면 이 시험은 P1-28 을 다시 못 본다 — 못 재면 red.
        assert set(HOVER_GROUNDS) <= set(grounds), f"[{theme}] hover 면이 바탕 목록에 없다"
        for g in _GRADES:
            fg = paint_colours(scope, f"var(--grade-{g})")[0]
            tint = paint_colours(scope, f"var(--grade-{g}-bg)")[0]
            for name, ground in grounds.items():
                for kind, bg in (("chip", over(tint, ground)), ("plain", ground)):
                    r = ratio(over(fg, bg), bg)
                    if r < AA:
                        failures.append(f"[{theme}] --grade-{g} {kind} on {name}: {r:.2f} < {AA}")
    assert not failures, "등급색 글자가 AA 미달인 조합:\n  " + "\n  ".join(failures)


def test_danger_text_meets_aa_on_every_ground_it_sits_on():
    """🔴 `--danger` 도 «글자» 다 — 위험 구역 제목·오류 문구·`.btn--danger`. 등급 F 와 같은 바탕에 앉는다.

    실측(수정 전): pastel 은 카드 위 4.55 였지만 행 hover 면 3.81 · body 그라디언트 stop 3.79 —
    가드가 없어 아무도 재지 않았다. dark·catppuccin 은 값이 `--grade-f` 와 같다.
    `--danger` is used as text on the same grounds as grade F; nothing measured it.
    """
    src = read("src/static/css/tokens.css")
    failures = []
    for theme in THEMES:
        scope = token_scope(src, theme)
        fg = paint_colours(scope, "var(--danger)")[0]
        for name, ground in _grade_grounds(theme).items():
            r = ratio(over(fg, ground), ground)
            if r < AA:
                failures.append(f"[{theme}] --danger on {name}: {r:.2f} < {AA}")
    assert not failures, "`--danger` 글자가 AA 미달인 조합:\n  " + "\n  ".join(failures)


# 등급색(과 `--danger`)을 «글자» 로 칠하는 선언 — `color`·`--g-color`(칩이 그것을 글자색으로 쓴다).
# `--grade-a-bg`·`--danger-text-on` 같은 형제 토큰은 아니다.
_GRADE_TEXT_RE = re.compile(
    r"(?<![\w-])(?:color|-webkit-text-fill-color|--g-color)\s*:[^;{}]*"
    r"var\(\s*(?:--grade-[a-z]|--danger)(?![\w-])")
_NEUTRAL_SURFACE_RE = re.compile(
    r"(?<![\w-])(?:background(?:-color)?|--g-bg)\s*:[^;{}]*var\(\s*("
    + "|".join(re.escape(n) for n in _NEUTRAL_CHIP_SURFACES) + r")(?![\w-])")


def _pairs_grade_text_with_neutral_chip(body: str) -> bool:
    return bool(_GRADE_TEXT_RE.search(body) and _NEUTRAL_SURFACE_RE.search(body))


def test_the_grade_pairing_probe_judges_by_role_not_by_mention():
    """🔴 아래 가드가 «잴 수 있는지» — 진짜 짝은 잡고, 형제 토큰·별칭은 놓아준다."""
    assert _pairs_grade_text_with_neutral_chip("color: var(--grade-f); background: var(--bg-mute);")
    assert _pairs_grade_text_with_neutral_chip("--g-color: var(--grade-b); --g-bg: var(--bg-mute);")
    assert not _pairs_grade_text_with_neutral_chip(
        "color: var(--text-2); background: var(--bg-mute);"), "중립 글자를 등급 글자로 오판한다"
    assert not _pairs_grade_text_with_neutral_chip(
        "color: var(--grade-a); background: var(--grade-a-bg);"), "제 틴트 칩을 중립 칩으로 오판한다"
    assert not _pairs_grade_text_with_neutral_chip(
        "border-color: var(--grade-a-bd); background: var(--bg-mute);"), "테두리를 글자로 오판한다"
    assert _pairs_grade_text_with_neutral_chip("color: var(--danger); background: var(--bg-mute);")
    assert not _pairs_grade_text_with_neutral_chip(
        "color: var(--danger-text-on); background: var(--bg-mute);"), "on-토큰을 위험 글자로 오판한다"


def test_no_rule_paints_grade_text_on_a_neutral_chip_surface():
    """🔴 어떤 규칙도 «중립 칩 면 위에 등급색·`--danger` 글자» 를 만들지 않는다 — 위 두 시험의 바탕
    목록이 그 면을 빼는 근거.

    `test_secondary_text_contrast.py::test_no_rule_pairs_the_faintest_tier_with_a_chip_surface`
    와 같은 구조다. 같은 블록 안의 짝만 본다 — 조상 hover 가 면을 바꾸는 경우는
    e2e hover 스윕(`e2e/test_theme_mobile_guards.py::_audit_text_under_hover`)과
    `test_hover_surface_contrast.py` 가 맡는다.
    """
    offenders = []
    for path in sorted((ROOT / "src").rglob("*.css")) + sorted(
            (ROOT / "src" / "templates").glob("*.html")):
        text = strip_css_comments(path.read_text(encoding="utf-8"))
        for m in re.finditer(r"\{([^{}]*)\}", text):
            if _pairs_grade_text_with_neutral_chip(m.group(1)):
                offenders.append(f"{path.relative_to(ROOT).as_posix()}: "
                                 f"{text[max(0, m.start() - 60):m.start()].split(chr(10))[-1]}")
    assert not offenders, (
        "중립 칩 면 위에 등급색 글자를 얹는 규칙이 있다 — catppuccin 에서 3.41~3.94 다:\n  "
        + "\n  ".join(offenders))


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
