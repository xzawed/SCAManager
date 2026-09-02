"""UI 감사 후속 — accent 위 글자색 · 좁은 화면 nav 접기 · 죽은 배선 제거 정적 가드.

행동 판정은 e2e(`e2e/test_theme_mobile_guards.py`)가 실제 브라우저에서 «칠해진 색» 과
«문서 넘침» 으로 한다. 여기 있는 것은 그 수정이 **되돌려졌는지**를 단위 수준에서 빠르게
잡는 가드다 — e2e 를 돌리지 않는 경로(역-뮤테이션 게이트 포함)에서도 회귀가 red 가 된다.

Behavioral judgment lives in e2e (real browser: painted color, document overflow).
These are fast static guards that catch a revert where e2e is not run.
"""
import pathlib

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


def test_nav_folds_labels_on_narrow_viewport():
    """🔴 좁은 화면에서 nav 가 라벨을 접어야 한다 — 안 접으면 문서가 가로로 밀린다.

    `nav` 는 `flex-wrap: nowrap` 이고 자식 넷이 `flex-shrink: 0` 이라 좁아져도 줄바꿈으로
    도망치지 못하고 **문서 전체**를 늘린다(실측: min-content 409px 고정 → 320px 에서 +89px).
    The nav cannot wrap, so its min-content width stretches the document sideways.
    """
    src = _read("src/templates/base.html")
    i = src.find("@media (max-width: 480px) {")
    assert i >= 0, "480px 분기 부재 — 테스트 stale"
    block = src[i:src.find("\n    }", i)]
    assert "#themeName" in block and "#langName" in block, (
        "좁은 화면에서 테마/언어 «라벨» 을 접지 않는다 — nav min-content 가 뷰포트를 넘어 "
        "문서가 가로로 스크롤된다 (실측 320px +89px)"
    )


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
