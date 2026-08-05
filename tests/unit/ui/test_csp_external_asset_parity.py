"""CSP ↔ 템플릿 외부 자원 정합 가드 — "앱이 자기 자산을 자기 CSP 로 차단" 재발 차단.

## 왜 필요한가 (2026-08-06, R52 — 14개월간 아무도 몰랐다)

`src/main.py` 의 CSP 는 `style-src 'self' 'unsafe-inline'` · `font-src 'self' data:` 다.
그런데 `base.html`·`landing.html` 이 Pretendard(jsDelivr)와 Google Fonts 스타일시트를
`<link rel="stylesheet">` 로 로드하고 있었다. **브라우저는 그것을 차단**했고, 결과적으로

- 폰트는 **한 번도 적용된 적이 없었다**(실측: `document.fonts.size == 0`, 두 시트 모두
  `cssRules` 접근 BLOCKED) — 페이지는 계속 `font-family` 스택 뒤쪽(system-ui)으로 렌더됐다
- 매 요청 **실패하는 스타일시트 2건 + preconnect 3건**과 콘솔 에러 2건이 났다

정적 코드 리뷰로는 이 모순이 보이지 않는다 — CSP 는 `main.py` 에, 링크는 템플릿에 있어서
**두 파일을 나란히 놓고 봐야** 드러난다. 이 테스트가 그 대조를 기계로 한다.

🔴 **이 가드는 "외부 자원을 쓰지 마라" 가 아니다** — CSP 가 허용하지 않는 출처를 쓰지 말라는
것이다. 정말 필요하면 (a) `src/static/vendor/` 로 vendoring 하거나 (b) CSP 에 그 출처를
명시 추가(보안 결정 — 사용자 확인)한 뒤 이 테스트가 자동으로 통과하게 된다.

CSP↔template parity: the app was blocking its own webfonts for 14 months. The contradiction
spans two files, so only a cross-file check surfaces it.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_TEMPLATES = _ROOT / "src" / "templates"
_MAIN = _ROOT / "src" / "main.py"

# `<link ... rel="stylesheet" ... href="https://...">` (속성 순서 무관)
_EXTERNAL_STYLESHEET = re.compile(
    r"""<link\b(?=[^>]*\brel=["']stylesheet["'])[^>]*\bhref=["'](https?://[^"']+)["']""",
    re.IGNORECASE,
)
_CSP_DIRECTIVE = re.compile(r'"(style-src|font-src|script-src)([^"]*)"')


def _csp_allows_external(directive: str) -> bool:
    """해당 디렉티브가 http(s) 출처를 허용하는가 (`'self'`·`data:` 만이면 불허)."""
    body = ""
    for name, value in _CSP_DIRECTIVE.findall(_MAIN.read_text(encoding="utf-8")):
        if name == directive:
            body = value
    assert body, f"main.py 에서 CSP `{directive}` 를 못 찾았다 — 형식이 바뀌었으면 가드도 갱신할 것"
    return "http://" in body or "https://" in body or "*" in body


def test_no_template_loads_a_stylesheet_the_csp_blocks():
    """CSP `style-src` 가 외부 출처를 허용하지 않으면 템플릿도 외부 스타일시트를 쓰지 않는다."""
    if _csp_allows_external("style-src"):
        return  # CSP 가 외부를 허용하도록 바뀌었다면 이 가드는 적용 대상이 아니다

    offenders: list[str] = []
    for path in sorted(_TEMPLATES.rglob("*.html")):
        for href in _EXTERNAL_STYLESHEET.findall(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.relative_to(_ROOT).as_posix()} → {href}")

    assert not offenders, (
        "CSP `style-src` 가 외부 출처를 막는데 템플릿이 외부 스타일시트를 로드한다 — "
        "브라우저가 차단하므로 **적용되지 않으면서 콘솔 에러만 낸다**:\n  "
        + "\n  ".join(offenders)
        + "\n해결: src/static/vendor/ 로 vendoring 하거나, 정말 필요하면 CSP 에 출처를 "
          "명시 추가할 것(보안 결정 — 사용자 확인 의무)."
    )


def test_guard_is_not_vacuous():
    """🔴 대조군 — 탐지 정규식이 실제로 외부 스타일시트를 잡는지 확인한다.

    이것이 없으면 "정규식이 아무것도 못 잡아서 통과" 하는 공허한 가드와 구별되지 않는다.
    """
    sample = (
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter">\n'
        '<link rel="stylesheet" href="/static/css/tokens.css">\n'
    )
    found = _EXTERNAL_STYLESHEET.findall(sample)
    assert found == ["https://fonts.googleapis.com/css2?family=Inter"], found


def test_csp_directives_are_actually_read():
    """🔴 대조군 — `main.py` 에서 CSP 디렉티브를 진짜로 읽는지.

    `_csp_allows_external` 이 항상 False 를 반환하면 위 테스트는 통과하지만 아무 의미가 없다.
    현재 CSP 는 style-src 가 외부 불허, img-src 는 https 허용이므로 두 방향이 모두 관측된다.
    """
    assert not _csp_allows_external("style-src"), "style-src 가 외부를 허용하도록 바뀌었다"
    assert not _csp_allows_external("font-src"), "font-src 가 외부를 허용하도록 바뀌었다"
