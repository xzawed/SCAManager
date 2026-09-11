"""자식 템플릿이 정의한 `{% block %}` 이 레이아웃에 «자리가 있는가».

🔴 Jinja 는 레이아웃이 모르는 블록을 **조용히 버린다**. 에러도, 경고도 없다.
   `analysis_detail.html` 이 `{% block head %}` 안에 CSS **361줄**을 넣었는데
   `base.html` 에는 그 블록이 없었다 — 전체 git 이력을 봐도 **한 번도 없었다**.
   그 CSS 는 #628(2026-05-25) 이래 **한 번도 브라우저에 도달한 적이 없다**.

실측(그 상태에서): 그 블록에만 있는 셀렉터 **87개** — 이슈 등록 패널 전체
(`.issue-reg-panel`·`.issue-tab`·`.issue-row`·`.btn-register`·`.issue-modal`·`.issue-toast`)와
분석 히어로(`.analysis-hero__*`), 상세 표(`.ad-breakdown`), 심각도 칩. 화면은 그만큼
날것으로 렌더됐고, 렌더된 HTML 에 그 블록의 고유 문자열이 하나도 없었다.

🔴 **이 결함은 어떤 시험도 잡지 못했다.** 단위 시험은 템플릿 «소스» 를 읽어 CSS 가
   거기 있다는 것만 봤고, e2e 는 클래스 이름과 글자만 봤다 — 둘 다 「그 CSS 가 실제로
   칠해지는가」를 묻지 않았다. 그래서 관측자가 셋(단위·e2e·사람)이나 있는데도 3개월 반을
   살아남았다.

Jinja silently drops blocks the layout never renders. This guard is the cheap mechanical
observer that would have caught it on day one.
"""
import pathlib
import re

from ._contrast import ROOT

TEMPLATE_DIR = ROOT / "src" / "templates"

_EXTENDS_RE = re.compile(r"\{%-?\s*extends\s+[\"']([^\"']+)[\"']\s*-?%\}")
_BLOCK_RE = re.compile(r"\{%-?\s*block\s+([A-Za-z_][\w]*)")


def _templates() -> dict[str, str]:
    found = {
        p.name: p.read_text(encoding="utf-8")
        for p in sorted(TEMPLATE_DIR.glob("*.html"))
    }
    assert len(found) > 5, f"템플릿 {len(found)}개 — 경로가 바뀌었다(공허한 초록 방지)"
    return found


def _blocks(src: str) -> set[str]:
    return {m.group(1) for m in _BLOCK_RE.finditer(src)}


def _layout_blocks(name: str, all_tpl: dict[str, str], depth: int = 0) -> set[str]:
    """그 레이아웃과 «그 조상들» 이 렌더하는 블록 이름 전부."""
    assert depth < 8, f"extends 사슬이 순환한다: {name}"
    src = all_tpl.get(pathlib.Path(name).name)
    assert src is not None, f"레이아웃 `{name}` 을 못 찾았다 — 경로가 바뀌었다"
    names = _blocks(src)
    if m := _EXTENDS_RE.search(src):
        names |= _layout_blocks(m.group(1), all_tpl, depth + 1)
    return names


def orphan_blocks() -> dict[str, set[str]]:
    """{템플릿: 레이아웃에 자리가 없는 블록 이름}."""
    all_tpl = _templates()
    orphans: dict[str, set[str]] = {}
    for name, src in all_tpl.items():
        m = _EXTENDS_RE.search(src)
        if not m:
            continue
        extra = _blocks(src) - _layout_blocks(m.group(1), all_tpl)
        if extra:
            orphans[name] = extra
    return orphans


def test_no_template_defines_a_block_the_layout_never_renders():
    """🔴 «정의했지만 렌더되지 않는» 블록의 집합이 비어야 한다 — 양방향 등식.

    red 로 만드는 뮤테이션: 아무 자식 템플릿에 `{% block sidebar %}x{% endblock %}` 을
    넣으면 red. 반대로 `base.html` 에서 `{% block content %}` 를 지워도 red다
    (자식들이 전부 고아가 되므로).
    """
    orphans = orphan_blocks()
    assert not orphans, (
        "레이아웃이 렌더하지 않는 블록이 있다 — Jinja 는 이것을 «조용히 버린다»:\n  "
        + "\n  ".join(f"{tpl}: {sorted(names)}" for tpl, names in sorted(orphans.items()))
        + "\n레이아웃에 그 블록을 추가하거나, 내용을 정본(components.css 등)으로 옮긴다."
    )


def test_the_guard_can_actually_see_an_orphan_block():
    """가드가 «잴 수 있는지» 를 잰다 — 고아를 심으면 탐지되는가."""
    fake = {
        "layout.html": "<html>{% block content %}{% endblock %}</html>",
        "child.html": '{% extends "layout.html" %}{% block content %}c{% endblock %}'
                      '{% block head %}dead{% endblock %}',
    }
    child_blocks = _blocks(fake["child.html"])
    assert child_blocks == {"content", "head"}, f"블록 파서가 늙었다: {child_blocks}"
    layout = _layout_blocks("layout.html", fake)
    assert layout == {"content"}, f"레이아웃 파서가 늙었다: {layout}"
    assert child_blocks - layout == {"head"}, "고아 블록을 탐지하지 못한다"


def test_the_guard_follows_the_extends_chain():
    """조상 레이아웃이 정의한 블록은 고아가 아니다 — 과잉 red 를 막는다."""
    fake = {
        "root.html": "{% block head %}{% endblock %}{% block content %}{% endblock %}",
        "mid.html": '{% extends "root.html" %}{% block content %}{% endblock %}',
        "leaf.html": '{% extends "mid.html" %}{% block head %}ok{% endblock %}',
    }
    assert _blocks(fake["leaf.html"]) - _layout_blocks("mid.html", fake) == set(), (
        "조상이 정의한 블록을 고아로 오판한다 — extends 사슬을 따라가지 않는다"
    )


# ── 페이지 전용 절이 «전역 이름» 을 잡지 않는가 ────────────────────────────
#
# 🔴 죽은 블록 안에서는 무해했던 규칙이 전역 CSS 로 옮기는 순간 사이트 전체를 바꾼다.
#    실측: 옮긴 블록에 `@media (max-width:768px) { .card { padding: 0 } }` 가 있었고,
#    그대로 두면 768px 이하에서 **모든 화면**의 카드 패딩이 0 이 된다
#    (dashboard·repo_insights·repo_detail 차트 카드). Grok `01a0907c` 가 지목했다.
#    이름이 페이지 전용인지는 «마크업이 어디서 쓰는가» 로만 알 수 있다.

_PAGE_SECTIONS = {
    # {components.css 안의 절 표지: 그 절이 담당하는 템플릿}
    "ANALYSIS DETAIL": "analysis_detail.html",
}


def _section_body(marker: str) -> str:
    css = (ROOT / "src" / "static" / "css" / "components.css").read_text(encoding="utf-8")
    i = css.find(marker)
    assert i >= 0, f"`{marker}` 절을 못 찾았다 — 표지가 바뀌었다"
    return re.sub(r"/\*.*?\*/", "", css[i:], flags=re.S)


def _classes_in_markup(template: str) -> set[str]:
    src = (TEMPLATE_DIR / template).read_text(encoding="utf-8")
    out: set[str] = set()
    for m in re.finditer(r'class\s*=\s*"([^"]*)"', src):
        out |= set(re.findall(r"[A-Za-z][\w-]*", m.group(1)))
    for m in re.finditer(r"""(?:classList\.\w+|className\s*=)\s*\(?\s*['"]([^'"]+)""", src):
        out |= set(m.group(1).split())
    return out


def test_page_scoped_sections_only_style_page_scoped_names():
    """🔴 페이지 전용 절의 «홑 클래스» 셀렉터는 그 페이지 밖에서 쓰이면 안 된다.

    red 로 만드는 뮤테이션: 그 절에 `.card { padding: 0; }` 한 줄을 넣으면 red
    (`.card` 를 dashboard·landing·repo_detail·repo_insights 가 쓴다).
    """
    offenders = []
    for marker, owner in _PAGE_SECTIONS.items():
        body = _section_body(marker)
        elsewhere: set[str] = set()
        for p in sorted(TEMPLATE_DIR.glob("*.html")):
            if p.name == owner:
                continue
            elsewhere |= _classes_in_markup(p.name)
        assert elsewhere, "다른 템플릿의 클래스를 하나도 못 읽었다 — 스캔이 죽었다"
        for m in re.finditer(r"(?:^|\}|\{)\s*([^{}@]+?)\s*\{", body):
            for sel in (x.strip() for x in m.group(1).split(",")):
                if re.fullmatch(r"\.[\w-]+", sel) and sel[1:] in elsewhere:
                    offenders.append(f"{marker}: {sel} — 다른 템플릿도 쓰는 이름이다")
    assert not offenders, (
        "페이지 전용 절이 전역 이름을 잡는다 — 조상 셀렉터로 한정할 것:\n  "
        + "\n  ".join(sorted(set(offenders)))
    )
