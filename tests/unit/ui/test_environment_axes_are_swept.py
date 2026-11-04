"""«앱이 적지 않은» 환경 상태도 프레임 안에 둔다 — 환경 축 원장 (회고 2026-09-16 P2-65).

## 무엇이 문제였나

이 리포의 폐쇄 가드는 «앱 안에 정본이 있는 열거» 에만 걸렸다 — 화면은 라우트에서, 모드는
`_VALID_MODES` 에서, 클릭으로 여는 상태는 템플릿 마크업에서 파생한다
(`test_a11y_route_coverage.py`). 파생은 손 목록보다 낫지만, **앱이 한 줄도 적지 않은 상태는
원리적으로 파생될 수 없다.** 실제로 `forced-colors` 선언이 0건이라 어떤 가드도 그 모드를 요구하지
않았고, 그 모드에서 «색만으로» 나르던 상태들이 아무것도 나르지 않았다(P2-64).

## 이 가드가 프레임을 정하는 방법

축의 출처를 앱이 아니라 **명세**로 둔다 — Media Queries 5 의 사용자 선호 기능과 WCAG 가 요구하는
환경(리플로 320px · 엔진). 축마다 둘 중 하나여야 한다:

- `opener` — 그 환경을 실제로 여는 e2e 호출(정규식). e2e 소스에 없으면 red(죽은 주장).
- `reason` — 열지 않는 사유(16자 이상). 단 앱 CSS 가 그 미디어 기능에 «반응하기 시작하면»
  사유로는 버틸 수 없다 — 그 순간 red 가 되어 opener 를 요구한다.

반대 방향도 닫는다: 앱 CSS 가 쓰는 미디어 기능은 전부 이 원장의 어느 축에 속해야 한다.

Environment axes come from the spec, not the app: each needs an e2e opener or a reason, and a
reason stops being acceptable the moment the app's CSS starts reacting to that feature.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from ._contrast import ROOT, read, strip_css_comments
from ._css_structure import style_blocks

_E2E = Path(__file__).resolve().parents[3] / "e2e"

# 축 → (그 축을 이루는 미디어 기능, opener 정규식 또는 None, 사유 또는 None)
# 🔴 opener 와 사유 중 «정확히 하나». 둘 다 두면 무엇이 지키는지 읽히지 않는다.
_AXES: dict[str, tuple[tuple[str, ...], str | None, str | None]] = {
    "forced-colors": (("forced-colors",), r"emulate_media\([^)]*forced_colors\s*=", None),
    "reduced-motion": (("prefers-reduced-motion",), r"emulate_media\([^)]*reduced_motion\s*=", None),
    "viewport": (("width", "min-width", "max-width", "height", "min-height", "max-height",
                  "aspect-ratio", "min-aspect-ratio", "max-aspect-ratio", "orientation"),
                 r"set_viewport_size\(", None),
    "reflow-320": ((), r"\(\s*320\s*,\s*\d+\s*\)|[\"']width[\"']\s*:\s*320\b", None),
    "color-scheme": (("prefers-color-scheme",), None,
                     "앱은 자체 테마 4종(사용자 선택)만 쓰고 OS 색 구성표를 읽지 않는다"),
    "contrast": (("prefers-contrast",), None,
                 "고대비 선호를 읽는 규칙이 없다 — 대비는 네 테마 모두 AA 로 잰다"),
    "reduced-transparency": (("prefers-reduced-transparency",), None,
                             "투명도 선호를 읽는 규칙이 없다 — 유리 효과의 글자 대비는 바탕을 합성해 잰다"),
    "hover-pointer": (("hover", "any-hover", "pointer", "any-pointer"), None,
                      "입력 장치로 갈리는 규칙이 없다 — 터치 대상 크기는 24px·44px 스윕이 잰다"),
    "print": (("print",), None, "인쇄용 규칙이 없다 — 화면 전용 대시보드다"),
    "engine": ((), None,
               "CI 는 Chromium 만 돈다(E2E 시간 예산) — 포커스 캠페인은 CDP 없이 짜여 엔진 무관"),
}


def _css_files() -> list[str]:
    """CSS 를 담는 운영 파일 전부(`dist/` 제외) — 손 목록이 아니라 파생이다."""
    return [p.relative_to(ROOT).as_posix()
            for root in ("src/templates", "src/static/css")
            for p in sorted((ROOT / root).rglob("*"))
            if p.suffix in (".html", ".css") and "dist" not in p.parts]


_MEDIA_TYPES = ("all", "print", "screen", "speech", "tv", "projection", "handheld", "braille",
                "embossed", "aural", "tty")


def _features_in(css: str) -> set[str]:
    """CSS 한 덩어리가 쓰는 미디어 기능·타입 이름.

    괄호 묶음마다 이름을 꺼낸다 — `(name: v)` · 범위 구문 `(width >= 600px)` ·
    `(600px <= width <= 900px)` · 불리언 `(hover)`. 🔴 `(name: v)` 만 읽던 첫 판은 범위 구문을
    통째로 놓쳤다(Grok `043a9e15` BROKEN: `(height >= 500px)` → 빈 집합).
    """
    out: set[str] = set()
    for m in re.finditer(r"@media([^{]*)\{", css):
        query = m.group(1).lower()
        for group in re.findall(r"\(([^()]*)\)", query):
            g = group.strip()
            if ":" in g:
                out.add(g.split(":", 1)[0].strip())
            elif re.search(r"[<>=]", g):
                out.update(t.strip() for t in re.split(r"<=|>=|<|>|=", g)
                           if re.fullmatch(r"\s*[a-z][a-z-]*\s*", t))
            elif re.fullmatch(r"[a-z][a-z-]*", g):
                out.add(g)
        out.update(t for t in re.findall(r"[a-z][a-z-]*", re.sub(r"\([^()]*\)", " ", query))
                   if t in _MEDIA_TYPES)
    return out


def _css_text(rel: str) -> str:
    """판정할 CSS — 템플릿은 `<style>` 블록만, 주석은 지운다.

    🔴 템플릿 전체를 읽으면 `<script>` 주석의 «@media 768px)…(실측 320px: …» 를 미디어 질의로 읽는다.
    """
    text = read(rel)
    if rel.endswith(".html"):
        text = "\n".join(css for _, css in style_blocks(text))
    return strip_css_comments(text)


def _media_features() -> dict[str, set[str]]:
    """{앱 CSS 가 쓰는 미디어 기능·타입: 그것을 쓰는 파일}."""
    out: dict[str, set[str]] = {}
    for rel in _css_files():
        for name in _features_in(_css_text(rel)):
            out.setdefault(name, set()).add(rel)
    return out


def _stale_reasons(used: set[str]) -> list[str]:
    """앱이 반응하는데 사유로만 버티는 축."""
    return sorted(name for name, (feats, opener, _r) in _AXES.items()
                  if opener is None and set(feats) & used)


def _unknown_features(used: set[str]) -> set[str]:
    """원장의 어느 축에도 속하지 않는 미디어 기능."""
    known = {feat for feats, _o, _r in _AXES.values() for feat in feats} | {"screen", "all"}
    return used - known


def _e2e_source() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(_E2E.glob("*.py")))


def test_every_axis_has_exactly_one_of_opener_or_reason():
    """축마다 opener 와 사유 중 정확히 하나 — 사유는 16자 이상."""
    bad = [name for name, (_, opener, reason) in _AXES.items()
           if (opener is None) == (reason is None) or (reason is not None and len(reason) < 16)]
    assert not bad, f"opener·사유 중 정확히 하나가 아닌 축: {bad}"


def test_every_opener_is_really_in_the_e2e_suite():
    """🔴 opener 는 «주장» 이 아니라 e2e 소스에 실재해야 한다 — 없으면 죽은 주장이다."""
    src = _e2e_source()
    assert "def test_" in src, "e2e 소스를 못 읽었다 — 판정이 공허하다"
    dead = [f"{name}: /{opener}/" for name, (_, opener, _r) in _AXES.items()
            if opener and not re.search(opener, src)]
    assert not dead, "e2e 에 없는 opener — 그 환경은 실제로 열리지 않는다:\n  " + "\n  ".join(dead)


def test_a_reason_stops_counting_once_the_app_reacts_to_that_feature():
    """🔴 사유는 «앱이 그 기능에 반응하지 않는다» 가 참일 때만 버틴다 — 반응하기 시작하면 red."""
    used = _media_features()
    assert used, "앱 CSS 에서 미디어 기능을 0개 찾았다 — 스캔이 죽었다(공허한 초록)"
    stale = _stale_reasons(set(used))
    assert not stale, (
        "앱 CSS 가 반응하는데 사유로만 버티는 축 — 그 환경을 여는 e2e 를 더하고 opener 로 바꿀 것: "
        + ", ".join(f"{name} ← {sorted(f for feat in _AXES[name][0] for f in used.get(feat, ()))}"
                    for name in stale))


def test_every_media_feature_the_app_uses_belongs_to_an_axis():
    """반대 방향 — 앱 CSS 가 새 미디어 기능을 쓰면 원장에 축이 생겨야 한다."""
    used = _media_features()
    unknown = {feat: sorted(used[feat]) for feat in _unknown_features(set(used))}
    assert not unknown, f"원장에 없는 미디어 기능 — 축을 더하고 opener 나 사유를 줄 것: {unknown}"


# 계기 뒤집기(verify.md 「판정식을 쓸 때」 4) — 심은 CSS 로 두 판정이 뒤집히는가.
#   cheap(「앱 CSS 에 쓰인 기능만 원장과 맞춘다」)은 «앱이 안 쓰는» forced-colors 를 영원히 못 본다 —
#   그래서 원장이 명세에서 축을 가져오고, 사유는 앱이 반응하는 순간 무효가 된다.
@pytest.mark.parametrize("css,stale,unknown", [
    ("@media (prefers-color-scheme: dark){a{b:c}}", ["color-scheme"], set()),
    ("@media (prefers-contrast: more){a{b:c}}", ["contrast"], set()),
    ("@media (forced-colors: active){a{b:c}}", [], set()),            # opener 가 있다
    ("@media (max-width: 1px) and (prefers-reduced-motion: reduce){a{b:c}}", [], set()),
    ("@media (scripting: none){a{b:c}}", [], {"scripting"}),           # 원장에 없는 기능
    ("@media print{a{b:c}}", ["print"], set()),
    # Grok `043a9e15`: 범위 구문 · 그 밖의 미디어 타입 · not/only · 쉼표 목록
    ("@media (height >= 500px){a{b:c}}", [], set()),
    ("@media (600px <= width <= 900px){a{b:c}}", [], set()),
    ("@media only screen and (prefers-contrast: more), print{a{b:c}}", ["contrast", "print"], set()),
    ("@media not all and (monochrome){a{b:c}}", [], {"monochrome"}),
    ("@media tv{a{b:c}}", [], {"tv"}),
])
def test_the_ledger_flips_on_planted_css(css, stale, unknown):
    used = _features_in(css)
    assert used, f"심은 CSS 에서 기능을 못 읽었다: {css}"
    assert _stale_reasons(used) == stale
    assert _unknown_features(used) == unknown


def test_the_ledger_names_the_axis_that_was_missing():
    """P2-64 의 자리 — forced-colors 는 앱 선언이 0건이어도 이 원장에 opener 로 있어야 한다."""
    _feats, opener, _reason = _AXES["forced-colors"]
    assert opener, "forced-colors 를 사유로 면제했다 — 그 모드에서 색만으로 나르는 상태를 아무도 안 잰다"
