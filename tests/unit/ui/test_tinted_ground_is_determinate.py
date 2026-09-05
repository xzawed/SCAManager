"""글자를 얹는 «틴트 면» 은 바탕이 정해져 있어야 한다.

`color-mix(…, transparent)` 나 `… , transparent 100%` 로 끝나는 그라디언트는 **뒤에 오는
것** 이 바탕이 된다. 이 앱의 페이지 뒤에서는 `.atmosphere__orb` 셋이 계속 움직이므로,
그런 면 위의 글자는 «칠해지는 배경이 시시각각 달라진다» — 어떤 글자색으로도 대비를
약속할 수 없다.

실측(픽셀·5위상): `.ri-day-btn.active` 3.64 · `.dash-cta-meta` 3.05 ·
`.dash-cta-title` 3.62. 같은 파일 안에서 `.ri-kpi-card` 는 이미 `var(--bg-card)` 에
섞고 있었다 — 규칙이 아니라 «누락» 이었다.

#1613 이 dark 카드에, #1614 가 `.ri-grade-badge` 에 쓴 것과 같은 처방이다.
"""
import re

from ._contrast import read, strip_css_comments

# 글자를 담는 틴트 면들. 바탕 토큰에 섞어 «불투명» 으로 만들어야 한다.
_TEXT_BEARING_TINTS = (
    ("src/static/css/repo_insights.css", ".ri-day-btn.active"),
    ("src/templates/dashboard.html", ".dash-cta-banner"),
)


def _rule_bodies(src: str, selector: str) -> list[str]:
    clean = strip_css_comments(src)
    out = []
    for m in re.finditer(rf"(?:^|[}}\n;>,])\s*{re.escape(selector)}\s*\{{", clean, re.MULTILINE):
        j = clean.find("}", m.end())
        assert j > m.end(), f"`{selector}` 블록이 닫히지 않는다"
        out.append(clean[m.end():j])
    assert out, f"`{selector}` 규칙 부재 — 테스트가 늙었다"
    return out


def test_text_bearing_tints_have_a_determinate_ground():
    """🔴 글자를 담는 틴트 면의 `background` 는 `transparent` 에 섞지 않는다.

    섞는 대상이 `transparent` 면 바탕이 «뒤에 오는 것» 이 되고, 이 앱에서는 그것이
    움직이는 orb 다. 표면 토큰(`--bg-card`·`--bg-base`)에 섞어 불투명하게 만든다.
    """
    offenders = []
    for rel, selector in _TEXT_BEARING_TINTS:
        for body in _rule_bodies(read(rel), selector):
            for m in re.finditer(r"background\s*:\s*([^;]+);", body):
                value = m.group(1)
                # 🔴 `[^)]*` 는 `var(--accent)` 의 닫는 괄호에서 멈춘다 — 중첩을 허용해야
                #    `color-mix(in srgb, var(--accent) 12%, transparent)` 를 잡는다.
                if re.search(r"color-mix\(.*?,\s*transparent\s*\)", value) or \
                        re.search(r"transparent\s+100%", value):
                    offenders.append(f"{rel}: `{selector}` 의 배경이 transparent 에 섞인다 "
                                     f"— {value.strip()[:70]}")
    assert not offenders, (
        "글자를 담는 틴트 면의 바탕이 정해지지 않는다 — orb 가 움직이면 대비도 움직인다:\n  "
        + "\n  ".join(offenders)
    )
