"""2.5.8 타깃 크기 하한이 «소스에» 남아 있는지 — e2e 닫힘의 값싼 짝.

## 이 파일과 e2e 의 분업

- **닫힘**은 e2e 가 맡는다(`test_every_control_meets_the_24px_target_on_mobile`).
  375px 에서 8화면의 «모든» 컨트롤을 열거해 24×24 를 요구한다 — 새 컨트롤이 생겨도 잡힌다.
- **이 파일**은 그 e2e 가 잡아낸 자리들이 «소스에서 조용히 되돌려지지» 않았는지만 잰다.
  브라우저 없이 도는 값싼 핀이다.

## 🔴 왜 필요했나

역-뮤테이션 게이트가 이 PR 을 red 로 잡았다 — 생산 파일(CSS·템플릿)을 전부 되돌려도
이 PR 의 «단위» 시험이 초록이었기 때문이다. 그 관측은 e2e 에만 있었고, 게이트는 브라우저를
띄우지 못한다. 면제 선언으로 빠져나가는 대신 정적으로도 관측되게 한다.

## 🔴 이 목록은 «닫힘» 이 아니다

여기 적힌 셀렉터는 e2e 실측이 잡아낸 자리다. 새 컨트롤의 발견은 이 목록이 아니라 e2e
열거가 한다 — 여기에 이름을 더하는 것으로 안심하지 말 것. 대신 목록의 각 항목이 소스에
실재하는지 역방향으로 확인해, 셀렉터가 사라진 뒤 남은 죽은 줄을 막는다.
"""
from __future__ import annotations

import re

from ._contrast import ROOT, strip_css_comments

# WCAG 2.5.8 Target Size (Minimum) = 24 CSS px. (2.5.5 의 AAA 44 가 아니다.)
_MIN_PX = 24

# {셀렉터: (파일, 실측 이전 크기)} — 전부 2026-09-10 375px 실측에서 나온 자리다.
_PINNED = {
    ".admin-link": ("src/static/css/admin.css", "22px"),
    ".admin-ops-link": ("src/templates/admin_operations.html", "22px"),
    ".ri-back-link": ("src/static/css/repo_insights.css", "21px"),
    ".mask-toggle": ("src/templates/settings.html", "36x23"),
}


def _rule_body(path: str, selector: str) -> str:
    src = strip_css_comments((ROOT / path).read_text(encoding="utf-8"))
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", src)
    assert m, f"`{selector}` 규칙이 `{path}` 에 없다 — 셀렉터가 사라졌으면 이 줄도 지운다"
    return m.group(1)


def test_pinned_controls_declare_the_24px_minimum():
    """🔴 실측으로 잡아낸 자리의 하한이 소스에서 사라지면 red.

    브라우저 없이 도는 값싼 핀이다 — «발견» 은 e2e 열거가 한다.
    """
    bad = []
    for selector, (path, before) in sorted(_PINNED.items()):
        body = _rule_body(path, selector)
        m = re.search(r"(?<![-\w])min-height\s*:\s*([0-9.]+)px", body)
        if not m:
            bad.append(f"{selector} ({path}): `min-height` 선언 없음 — 실측 {before} 였다")
        elif float(m.group(1)) < _MIN_PX:
            bad.append(f"{selector} ({path}): min-height {m.group(1)}px < {_MIN_PX}px")
    assert not bad, (
        "2.5.8 하한이 소스에서 빠졌다 — 손가락으로 정확히 누를 수 없게 된다:\n  "
        + "\n  ".join(bad))


def test_inline_refresh_links_declare_the_minimum():
    """🔴 인라인 style 로 붙인 하한도 함께 잰다 — 규칙이 아니라 속성에 있다.

    실측: 인사이트 `↺ Refresh` 15px · 대시보드 insight `Refresh` 20px.
    둘 다 «인라인 style» 이라 위 규칙 검사로는 안 보인다.
    """
    targets = {
        "src/templates/repo_insights.html": "insights ↺ Refresh",
        "src/templates/dashboard.html": "dashboard insight Refresh",
    }
    bad = []
    for path, label in targets.items():
        src = (ROOT / path).read_text(encoding="utf-8")
        styles = [m.group(1) for m in re.finditer(r"<a\b[^>]*style=\"([^\"]*)\"", src, re.S)]
        hits = [s for s in styles if "refresh" in s.lower() or "min-height" in s]
        withmin = [s for s in styles
                   if (m := re.search(r"min-height\s*:\s*([0-9.]+)px", s))
                   and float(m.group(1)) >= _MIN_PX]
        if not withmin:
            bad.append(f"{label} ({path}): 24px 하한을 선언한 인라인 링크가 없다 "
                       f"(인라인 style 링크 {len(styles)}개, 후보 {len(hits)}개)")
    assert not bad, "인라인 Refresh 링크의 2.5.8 하한이 빠졌다:\n  " + "\n  ".join(bad)


def test_the_pinned_list_only_names_selectors_that_exist():
    """🔴 죽은 핀은 「이미 봤다」로 읽히면서 아무것도 가리지 않는다(역방향)."""
    missing = []
    for selector, (path, _before) in sorted(_PINNED.items()):
        src = strip_css_comments((ROOT / path).read_text(encoding="utf-8"))
        if not re.search(re.escape(selector) + r"\s*\{", src):
            missing.append(f"{selector} ({path})")
    assert not missing, (
        "소스에 없는 셀렉터를 아직 핀으로 들고 있다 — 지우거나 갱신한다:\n  "
        + "\n  ".join(missing))


def test_this_file_does_not_claim_to_be_the_closure():
    """🔴 계기 자기검증 — 이 파일이 «발견» 을 맡는다고 읽히면 e2e 를 지워도 조용해진다.

    닫힘은 e2e 열거에 있다. 그 시험이 사라지면 여기서 red 가 나야 한다.
    """
    sweep = (ROOT / "e2e" / "test_theme_mobile_guards.py").read_text(encoding="utf-8")
    assert "test_every_control_meets_the_24px_target_on_mobile" in sweep, (
        "e2e 의 타깃 크기 «열거» 시험이 사라졌다 — 이 파일의 핀만으로는 "
        "새로 생긴 작은 컨트롤을 못 찾는다")
