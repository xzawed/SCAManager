"""UI 감사 후속 — accent 위 글자색 · 좁은 화면 nav 접기 · 죽은 배선 제거 정적 가드.

행동 판정은 e2e(`e2e/test_theme_mobile_guards.py`)가 실제 브라우저에서 «칠해진 색» 과
«문서 넘침» 으로 한다. 여기 있는 것은 그 수정이 **되돌려졌는지**를 단위 수준에서 빠르게
잡는 가드다 — e2e 를 돌리지 않는 경로(역-뮤테이션 게이트 포함)에서도 회귀가 red 가 된다.

Behavioral judgment lives in e2e (real browser: painted color, document overflow).
These are fast static guards that catch a revert where e2e is not run.
"""
import pathlib
import re

from ._contrast import strip_css_comments

_ROOT = pathlib.Path(__file__).resolve().parents[3]


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def test_primary_button_does_not_hardcode_white_label():
    """🔴 `.btn-primary` 라벨 색은 하드코딩이 아니라 토큰이어야 한다.

    사고: `base.html` 인라인 `<style>` 의 `color: #fff` 가 `components.css` 의
    `var(--accent-text-on)` 을 **같은 명시도로 나중에 와서** 덮었다. 그래서 catppuccin 은
    토큰에 어두운 글자색을 이미 갖고도 흰 글자로 그려져 2.03:1 이었다.
    A hardcoded #fff overrode components.css's var(--accent-text-on) at equal specificity.
    """
    src = _read("src/templates/base.html")
    i = src.find(".btn-primary, .btn--primary {")
    assert i >= 0, "`.btn-primary, .btn--primary` 규칙 부재 — 테스트 stale"
    # 규칙 블록(선언부)만 본다 — 뒤따르는 :hover 등은 별도 블록
    block = src[i:src.find("}", i)]
    assert "var(--accent-text-on" in block, (
        "`.btn-primary` 라벨 색이 토큰이 아니다 — 테마별 on-accent 대비가 무력화된다"
    )
    assert "color: #fff" not in block and "color: #ffffff" not in block, (
        "`.btn-primary` 에 흰색이 하드코딩됐다 — components.css 의 토큰을 덮어 "
        "catppuccin 2.03:1 회귀"
    )


def test_light_accent_themes_do_not_use_white_on_accent():
    """🔴 accent 면이 밝은 테마는 흰 글자를 쓰면 안 된다 (AA 미달).

    실측: 흰 글자 기준 dark 3.45 · pastel 3.37 · catppuccin 2.03 — 전부 4.5 미달.
    accent(브랜드 색)는 그대로 두고 «글자색» 을 어둡게 해 통과시켰다.
    Themes whose accent surface is light must not paint white labels on it.
    """
    src = _read("src/static/css/tokens.css")
    for theme in ("dark", "pastel", "catppuccin"):
        i = src.find(f'[data-theme="{theme}"] {{')
        assert i >= 0, f"{theme} 테마 블록 부재 — 테스트 stale"
        block = src[i:src.find("\n}", i)]
        j = block.find("--accent-text-on:")
        assert j >= 0, f"{theme} 에 --accent-text-on 미정의"
        value = block[j:block.find(";", j)].split(":", 1)[1].strip().lower()
        assert value not in ("#fff", "#ffffff", "white"), (
            f"[{theme}] --accent-text-on 이 흰색이다 — 이 테마의 accent 면에서 AA 미달"
        )


def _max_width_blocks(src: str) -> list[tuple[int, str]]:
    """`@media (max-width: Npx) { … }` 블록마다 (N, 본문) — 중괄호 짝으로 끝을 찾는다."""
    out = []
    for m in re.finditer(r"@media \(max-width: (\d+)px\) \{", src):
        depth, j = 1, m.end()
        while depth and j < len(src):
            depth += {"{": 1, "}": -1}.get(src[j], 0)
            j += 1
        out.append((int(m.group(1)), src[m.end():j - 1]))
    return out


def _hidden_selectors(block: str) -> set[str]:
    """블록 안에서 `display: none` 을 거는 규칙의 선택자 조각들."""
    hidden = set()
    for sel, decl in re.findall(r"([^{}]+)\{([^{}]*)\}", block):
        if re.search(r"display:\s*none", decl):
            hidden |= {s.strip() for s in sel.split(",")}
    return hidden


def test_nav_folds_labels_past_the_phone_breakpoint():
    """🔴 nav 라벨 접기는 480px 너머까지 걸려야 한다 — 안 접으면 문서가 가로로 밀린다.

    `nav` 는 줄바꿈하지 않고 대부분의 항목이 제 글자 폭 아래로 줄지 않아, 접지 않은 폭에서는 **문서 전체**를
    늘린다(실측: 320px +89px). 접기가 480px 에서 멈추면 481px 부터 사용자 이름 · 테마/언어 이름 · 펼침 표시가
    돌아오는데, 그 nav 의 최소 폭은 588~652px(ja · catppuccin 이 가장 넓다)라 481~652px 가 가로로 밀렸다.
    어디까지 걸려야 하는지는 e2e(`test_nav_fits_the_narrowest_width_of_every_css_band`)가 최악 조건으로 잰다.
    The fold must reach past 480px; the e2e measures how far it has to go.
    """
    src = _read("src/templates/base.html")
    targets = (".nav-user-name", "#themeName", "#langName", ".theme-btn .chevron")
    folding = [n for n, body in _max_width_blocks(src) if set(targets) <= _hidden_selectors(body)]
    assert folding, f"{targets} 를 함께 접는 max-width 분기가 없다 — 좁은 화면에서 문서가 가로로 밀린다"
    assert max(folding) > 480, (
        f"라벨 접기가 {max(folding)}px 에서 멈춘다 — 481px 부터 라벨을 다 편 nav(588~652px)가 문서를 민다")


def test_nav_stays_on_one_line_and_only_the_name_gives_way():
    """🔴 nav 는 한 줄이고, 자리가 모자라면 사용자 이름만 줄어든다.

    769px 이상에서는 nav 링크와 140px 까지 자라는 이름이 돌아온다. 이름 묶음(`.nav-user`)이 줄지 않는 상자이면
    긴 GitHub 프로필 이름이 문서를 가로로 밀었고(실측 +47~76px), 일본어 링크는 넘치는 대신 여러 줄로 쌓였다.
    The nav never wraps, and the user group is unwrapped so only the name (overflow hidden) shrinks.
    """
    src = _read("src/templates/base.html")
    nav = re.search(r"\n    nav \{([^}]*)\}", src)
    assert nav, "`nav {` 규칙 부재 — 테스트 stale"
    assert re.search(r"white-space:\s*nowrap", nav.group(1)), (
        "nav 가 한 줄이 아니다 — 일본어 링크가 자리가 모자라면 여러 줄로 쌓인다(실측 769px 7줄)")
    user = re.search(r"\.nav-user \{([^}]*)\}", src)
    assert user and re.search(r"display:\s*contents", user.group(1)), (
        "`.nav-user` 가 줄지 않는 상자다 — 긴 이름이 769px 이상에서 문서를 가로로 민다")


_INSET = re.compile(r"env\(\s*safe-area-inset-(left|right)\b", re.I)
_SLOTS = ("top", "right", "bottom", "left")


def _values(decl: str) -> list[str]:
    """선언 값을 최상위 공백으로 자른다 — 괄호 안(`max(1rem, env(…))`)은 자르지 않는다."""
    out, depth, cur = [], 0, ""
    for ch in decl.replace("!important", "").strip():
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if ch.isspace() and depth == 0:
            if cur:
                out.append(cur)
            cur = ""
        else:
            cur += ch
    return out + ([cur] if cur else [])


def _misplaced_insets(css: str) -> tuple[int, list[str]]:
    """좌우 inset 을 쓰는 padding 선언 수와, inset 이 제 쪽이 아닌 자리(위 · 아래 · 반대쪽 · 좌우 공용 값)에 든 선언.

    CSS 의 속성 · 함수 이름은 대소문자를 가리지 않는다 — 판정도 가리지 않는다.
    """
    seen, wrong = 0, []
    pattern = r"(padding(?:-(?:top|right|bottom|left))?)\s*:\s*([^;{}]+)"
    for prop, decl in re.findall(pattern, strip_css_comments(css), flags=re.I):
        if not _INSET.search(decl):
            continue
        seen += 1
        prop, vals = prop.lower(), _values(decl)
        if prop != "padding":
            slots = {prop.split("-")[1]: decl}
        elif len(vals) == 4:
            slots = dict(zip(_SLOTS, vals))
        else:
            # 값이 하나 · 둘 · 셋이면 좌우가 같은 값을 받는다 — 한쪽 inset 이 반대쪽에도 붙는다.
            slots = None
        # 좌우 inset 은 제 이름의 자리에만 — 위 · 아래 자리에 든 것도 틀렸다.
        if slots is None or any(side.lower() != own for own, v in slots.items() for side in _INSET.findall(v)):
            wrong.append(f"{prop}: {' '.join(vals)}")
    return seen, wrong


def test_the_inset_check_flips_on_a_swapped_declaration():
    """계기 뒤집기 — 같은 판정이 맞은 선언은 통과시키고, 뒤바뀐 선언 · 좌우 공용 값 · 반대쪽 longhand 는 잡는가."""
    good = "a { padding: 0 max(1rem, env(safe-area-inset-right)) 0 max(1rem, env(safe-area-inset-left)); }"
    assert _misplaced_insets(good) == (1, []), "맞은 선언을 잡는다 — 거짓 red"
    for bad in ("a { padding: 0 max(1rem, env(safe-area-inset-left)) 0 max(1rem, env(safe-area-inset-right)); }",
                "a { padding: 0 max(1rem, env(safe-area-inset-left)); }",
                "a { padding-left: env(safe-area-inset-right); }",
                # 뒤 두 값이 뒤바뀐 메뉴 패널 — 왼쪽 inset 이 아래 자리로 갔다.
                "a { padding: 1rem max(1rem, env(safe-area-inset-right)) max(1rem, env(safe-area-inset-left)) "
                "calc(1rem + env(safe-area-inset-bottom, 0px)); }",
                "a { padding: env(safe-area-inset-left) 1rem 0 1rem; }",
                "a { padding-top: env(safe-area-inset-right); }",
                "a { PADDING: 0 MAX(1rem, ENV(safe-area-inset-left)) 0 MAX(1rem, ENV(safe-area-inset-right)); }"):
        seen, wrong = _misplaced_insets(bad)
        assert seen == 1 and wrong, f"뒤바뀐 선언을 못 잡는다 — 거짓 초록: {bad}"


def test_safe_area_insets_pad_their_own_side():
    """🔴 좌우 safe-area inset 은 제 쪽 여백에 들어가야 한다.

    `padding` 네 값은 위 · 오른쪽 · 아래 · 왼쪽이다. nav 는 오른쪽 자리에 왼쪽 inset 을 넣고 있어(기본 · 768px ·
    480px), 한쪽에만 inset 이 있는 기기에서 여백이 반대쪽에 붙고 로고는 inset 밑에 있었다. 행동은
    e2e(`test_nav_and_body_stay_inside_a_one_sided_safe_area`)가 inset 을 심어 잰다.
    Each side's safe-area inset must pad its own side.
    """
    seen, wrong = _misplaced_insets(_read("src/templates/base.html"))
    assert seen, "좌우 safe-area inset 을 쓰는 padding 이 없다 — 테스트 stale"
    assert not wrong, "inset 이 반대쪽 여백에 들어 있다:\n  " + "\n  ".join(wrong)


_THEMES = ("dark", "light", "pastel", "catppuccin")


def _themes_where_not_opaque(token: str) -> list[str]:
    """토큰이 알파 없는 색(#rgb · #rrggbb)이 아닌 테마 — 원천은 `tokens.css` 의 테마 블록이다."""
    css = _read("src/static/css/tokens.css")
    bad = []
    for theme in _THEMES:
        i = css.find(f'[data-theme="{theme}"] {{')
        block = css[i:css.find("\n}", i)] if i >= 0 else ""
        m = re.search(re.escape(token) + r":\s*([^;]+);", block)
        if not m or not re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", m.group(1).strip()):
            bad.append(theme)
    return bad


def test_the_opacity_check_flips_on_a_translucent_token():
    """계기 뒤집기 — nav 의 반투명 토큰은 네 테마 모두 걸리고, 바탕 토큰은 하나도 안 걸린다."""
    assert _themes_where_not_opaque("--bg-nav") == list(_THEMES), "반투명 토큰을 불투명으로 읽었다 — 거짓 초록"
    assert _themes_where_not_opaque("--bg-base") == [], "불투명 토큰을 반투명으로 읽었다 — 거짓 red"


def test_open_mobile_menu_paints_an_opaque_surface():
    """🔴 열린 모바일 메뉴 패널의 바탕은 네 테마 모두에서 불투명이어야 한다.

    패널이 nav 의 반투명 바탕(--bg-nav)을 쓰면, 화면 끝까지 펼친 fixed 패널은 nav 의 블러 밖이라 아래 페이지 제목이
    비쳐 링크 글자와 겹친다. 행동은 e2e(`test_open_mobile_menu_hides_the_page_behind_it`)가 칠해진 픽셀로 잰다.
    The open mobile menu panel must sit on a token that is opaque in every theme.
    """
    src = strip_css_comments(_read("src/templates/base.html"))
    rule = re.search(r"\.nav-links\.open\s*\{([^}]*)\}", src)
    assert rule, "`.nav-links.open {` 규칙 부재 — 테스트 stale"
    bg = re.search(r"background(?:-color)?\s*:\s*var\((--[\w-]+)\)\s*;", rule.group(1))
    assert bg, f"`.nav-links.open` 바탕이 토큰 하나가 아니다 — 불투명인지 못 잰다: {rule.group(1).strip()[:120]}"
    bad = _themes_where_not_opaque(bg.group(1))
    assert not bad, f"`.nav-links.open` 바탕 `{bg.group(1)}` 이 {bad} 에서 불투명이 아니다 — 아래 페이지가 비친다"



def test_dashboard_segment_toggles_scroll_internally():
    """🔴 세그먼트 토글은 좁은 화면에서 «안쪽» 으로 스크롤해야 한다.

    토글은 내부에서 줄바꿈하지 않아, 제 폭(실측 362px)으로 문서를 가로로 늘린다.
    그리고 스크롤로 만든 뒤에는 활성 항목이 잘려 보이지 않는 2차 결함이 따라온다 —
    그래서 활성 항목을 토글 «자신의» scrollLeft 로 끌어와야 한다.
    A segmented control never wraps; make it scroll internally, then reveal the active item.
    """
    src = _read("src/templates/dashboard.html")
    assert "overflow-x: auto" in src, (
        "세그먼트 토글이 안쪽 스크롤이 아니다 — 문서가 가로로 밀린다 (실측 320px +74px)"
    )
    assert "_dashRevealActiveSegment" in src, (
        "활성 세그먼트를 보이게 하는 로직이 없다 — 뒤쪽 모드에서 현재 위치 표시가 잘린다 "
        "(실측 320px: security +32px · usage +117px)"
    )
    # 🔴 «호출 형태»(`.scrollIntoView(`)로 본다 — 이 파일의 주석이 왜 쓰지 않는지 설명하며
    #    같은 낱말을 담고 있어, 맨 낱말로 재면 주석이 판정을 뒤집는다(실측: 이 시험의 첫 판이
    #    그렇게 거짓 red 였다). 부분문자열은 상태가 아니다.
    # Match the CALL form: this file's own comment explains why it is avoided and contains
    # the bare word, so a bare-substring check is flipped by prose.
    assert ".scrollIntoView(" not in src, (
        "scrollIntoView 는 조상까지 스크롤해 페이지가 통째로 뛴다 — "
        "토글 자신의 scrollLeft 만 움직여야 한다"
    )


def test_dead_tweaks_controller_is_gone():
    """🔴 `tweaks.js` 는 삭제됐고 다시 로드되면 안 된다.

    선택자(`.tweaks`·`.tw-options`)가 어느 템플릿에도 없어 조종할 UI 가 없었고,
    `DOMContentLoaded` 에서 `html[data-theme]` 를 자기 기본값 dark 로 덮어
    저장된 테마와 갈라놓았다(html=dark · body=light).
    The dead controller also overwrote html[data-theme] with its own default.
    """
    assert not (_ROOT / "src/static/js/tweaks.js").exists(), (
        "tweaks.js 가 되살아났다 — 조종할 UI 가 없고 html[data-theme] 를 덮는다"
    )
    assert "js/tweaks.js" not in _read("src/templates/base.html"), (
        "base.html 이 tweaks.js 를 다시 로드한다"
    )
