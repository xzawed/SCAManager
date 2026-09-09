"""`--accent` 를 «글자» 로 쓰는 자리를 열거해 닫는다.

## 무엇이 문제였나

이 리포는 accent 를 글자로 쓸 때의 색을 `--accent-text` 로 따로 두고, 그 토큰이 네 테마
× 네 바탕에서 AA 를 넘는지 `test_accent_text_contrast.py` 가 잰다. 그런데 그 가드는
**토큰과 특정 셀렉터 몇 개**만 본다 — `color: var(--accent)` 를 «새로 쓰는 자리» 는
열거하지 않는다. 그래서 토큰을 만든 뒤에도 같은 결함이 계속 들어왔다.

실측(2026-09-09, 400조합 픽셀 측정): `settings.html::.field-tag` 가 `color: var(--accent)`
라 pastel **2.79** · light **4.20**(기준 4.5). `--accent-text` 로 바꾸면 같은 틴트 면에서
dark 5.08 · light 4.93 · pastel 5.20 · catppuccin 5.52 로 전부 통과한다.

## 🔴 이 가드가 «글자» 로 보는 것

`color:` 로 accent 를 지정하는 자리만이다. 면(`background`)·테두리는 다른 축이고,
`:hover` 처럼 «순간 상태» 이거나 글리프(`svg`)인 자리는 사유를 달아 면제한다.
면제가 소스에서 사라지면 그 줄도 red 다(역방향).

## 🔴 이 가드가 «하지 못하는» 것

**리터럴로 우회하면 못 잡는다.** `color: var(--accent-text)` 를 `color: #6366f1` 로 바꾸면
이 스캔은 조용해진다(뮤테이션 실증). 토큰 이름을 보는 정적 검사의 원리적 천장이다.
그 축은 «실제로 칠해진 픽셀» 을 재는 e2e 대비 스윕이 잡는다 — 심각도 칩이 리터럴 hex 라
24조합 중 16건이 미달이던 것을 그 스윕이 잡은 전례가 있다(#1633). 두 층을 다 둔다.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]

# `color: var(--accent)` — 정확히 `--accent` 만. `--accent-text`·`--accent-1` 등은 별개다.
_ACCENT_AS_TEXT = re.compile(r"(?<![-\w])color\s*:\s*var\(\s*--accent\s*[,)]")

# 면제 — «사유와 함께». 사라지면 red 다.
_EXEMPT = {
    ".btn-ghost:hover, .btn--ghost:hover":
        ":hover 는 순간 상태다. 기본 상태의 글자색이 AA 를 넘으면 1.4.3 은 충족되고, "
        "hover 대비는 #1617 이 따로 쟀다.",
    ".filter-btn:hover": ":hover — 위와 같다.",
    ".sortable-th:hover": ":hover — 위와 같다.",
    ".page-btn:hover:not(:disabled)": ":hover — 위와 같다.",
    ".chart-empty-state svg":
        "글리프다. 1.4.3(글자 대비)이 아니라 1.4.11(비-텍스트) 대상이라 기준이 3:1 이다.",
}


def _sources() -> list[Path]:
    """🔴 i18n JSON 도 본다 — 번역 문자열 안에 인라인 스타일이 박혀 `| safe` 로 렌더된다.

    실측: `translations/{en,ko,ja}.json` 의 `semi_auto_hint` 가
    `style="color:var(--accent);…"` 를 담고 `settings.html::semi_auto_hint` 에서
    `| safe` 로 나간다. 템플릿·CSS 만 훑던 첫 판은 이 세 곳을 통째로 놓쳤다
    (Grok 반증 `01a0836e`). 「어디에 색이 적히는가」는 확장자로 정해지지 않는다.
    """
    return (sorted((_ROOT / "src" / "templates").rglob("*.html"))
            + sorted((_ROOT / "src" / "static").rglob("*.css"))
            + sorted((_ROOT / "src" / "i18n" / "translations").rglob("*.json")))


def accent_as_text_sites() -> dict[str, str]:
    """{셀렉터: 'path:line'} — accent 를 글자색으로 지정하는 자리."""
    found: dict[str, str] = {}
    for path in _sources():
        raw = path.read_text(encoding="utf-8")
        src = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)
        for m in _ACCENT_AS_TEXT.finditer(src):
            line = src[:m.start()].count("\n") + 1
            head = src[:m.start()].rsplit("{", 1)[0]
            sel = " ".join(head.rsplit("}", 1)[-1].split())[-60:].strip()
            found[sel] = f"{path.relative_to(_ROOT).as_posix()}:{line}"
    return found


def test_accent_is_not_used_as_text_without_the_text_token():
    """🔴 accent 를 글자로 쓰면 밝은 테마에서 AA 미달이다 — `--accent-text` 를 쓴다.

    실측: `.field-tag` pastel 2.79. 토큰만 만들어 두고 «쓰는 자리» 를 열거하지 않으면
    같은 결함이 계속 새로 들어온다.

    Accent as text fails AA on light grounds; the dedicated --accent-text token exists.
    """
    sites = accent_as_text_sites()
    offenders = sorted(f"{sel}  ({where})" for sel, where in sites.items()
                       if sel not in _EXEMPT)
    assert not offenders, (
        "`color: var(--accent)` 로 글자를 칠하는 자리가 있다 — `var(--accent-text)` 를 쓴다:\n  "
        + "\n  ".join(offenders))


def test_the_scan_still_finds_the_exempted_sites():
    """🔴 대조군 — 스캔이 죽으면 위 시험은 「위반 0」으로 조용히 통과한다.

    면제한 자리들은 «여전히 존재» 해야 한다. 하나도 못 찾으면 정규식이나 경로가 늙은 것이다.
    """
    sites = accent_as_text_sites()
    assert sites, "`color: var(--accent)` 를 0곳 찾았다 — 스캔이 죽었다(공허한 초록)"
    stale = sorted(sel for sel in _EXEMPT if sel not in sites)
    assert not stale, (
        "소스에서 사라진 셀렉터를 아직 면제하고 있다 — 지우거나 갱신한다:\n  "
        + "\n  ".join(stale))


def test_the_text_token_exists_in_every_theme():
    """🔴 대체 토큰이 없으면 위 처방은 실행 불가능한 요구가 된다."""
    css = (_ROOT / "src" / "static" / "css" / "tokens.css").read_text(encoding="utf-8")
    themes = sorted(set(re.findall(r'\[data-theme="([a-z]+)"\]', css)))
    assert themes, "테마를 0개 찾았다 — 스캔이 죽었다"
    missing = []
    for theme in themes:
        m = re.search(rf'\[data-theme="{theme}"\]\s*\{{(.*?)\n\}}', css, re.S)
        block = m.group(1) if m else ""
        root = re.search(r"^:root\s*\{(.*?)\n\}", css, re.S | re.M)
        both = block + (root.group(1) if root else "")
        if not re.search(r"--accent-text\s*:", both):
            missing.append(theme)
    assert not missing, f"`--accent-text` 가 정의되지 않은 테마: {missing}"
