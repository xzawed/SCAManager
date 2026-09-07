"""테마 목록이 «손으로 유지되는 사본» 이라는 사실을 닫는다 (회고 2026-09-07 C).

## 무엇이 문제인가

테마 이름 목록이 리포에 **네 벌** 있었다 — `tests/unit/ui/_contrast.py` 의 정본과
`test_accent_text_contrast.py` · `test_secondary_text_contrast.py` ·
`e2e/test_state_indication.py` 의 사본 셋. 넷이 같은 값이라 지금은 무해하지만, 테마가
하나 늘면 «어느 목록이 갱신되는가» 가 사람 기억에 달린다. 갱신 안 된 목록의 시험은
새 테마를 **한 번도 재지 않고** 초록으로 남는다 — 이 리포가 반복해 적발한 형태다.

## 정본을 무엇으로 두는가

`src/static/css/tokens.css` 의 `[data-theme="X"]` 선언 이름 집합이다.

🔴 HTML 을 훑어 파생하면 안 된다 — `settings.html` 에 죽은 `glass` 테마의 잔재 CSS 가
남아 있어(Grok 지적) 없는 테마를 되살린다. 토큰 팔레트가 실제 판정면이므로 거기서 뽑는다.
🔴 `[data-variant=…]` 같은 서명 변형과 `body[data-theme=…]` 중복은 이름 집합으로 접으면
자연히 사라진다 — 개수가 아니라 **이름**을 센다.

## 🔴 왜 «공유 헬퍼» 로 뽑지 않는가

정책 16(최소 추상화)은 「같은 로직이 3회 이상」일 때 추출을 허용한다. 열거 폐쇄의
술어는 가드마다 다르다(HTML 파서 · CSS 규칙 · 마크업 문자열). 그래서 각 가드가 자기
술어를 갖고, 공통은 이미 있는 `_contrast` 헬퍼를 재사용하는 선에서 멈춘다.
"""
from __future__ import annotations

import ast
import re

from ._contrast import ROOT, THEMES, read

# 사본이 사는 곳 — 사본을 «지우는» 것이 목표지만, e2e 는 rootdir 이 달라 import 로
# 합칠 수 없다. 그래서 사본이 남는 자리는 여기서 값 일치를 강제한다.
_COPIES = ("e2e/test_state_indication.py",)

_DATA_THEME = re.compile(r'\[data-theme="([a-z]+)"\]')


def _themes_declared_in_tokens() -> set[str]:
    """`tokens.css` 가 팔레트를 선언한 테마 이름 — 이것이 정본이다."""
    return set(_DATA_THEME.findall(read("src/static/css/tokens.css")))


def test_helper_theme_list_matches_the_token_palettes():
    """🔴 `_contrast.THEMES` 가 토큰이 선언한 집합과 정확히 같아야 한다.

    남으면(목록에 있는데 팔레트 없음) 그 테마 검사는 `theme_block` 에서 터지고,
    빠지면(팔레트 있는데 목록 없음) 그 테마는 **아무 대비 시험도 받지 않는다.**
    후자가 조용해서 위험하다.
    """
    declared = _themes_declared_in_tokens()
    assert declared, "tokens.css 에서 테마 선언을 0개 찾았다 — 스캔이 죽었다(공허한 초록)"
    assert set(THEMES) == declared, (
        f"`_contrast.THEMES` 와 tokens.css 가 다르다:\n"
        f"  목록에만: {sorted(set(THEMES) - declared)}\n"
        f"  토큰에만: {sorted(declared - set(THEMES))}")


def test_every_hand_copy_of_the_theme_list_matches_the_canonical_one():
    """🔴 import 로 합칠 수 없는 사본은 **값 일치**를 강제한다.

    `e2e/` 는 rootdir 이 달라 `tests/unit/ui/_contrast` 를 import 할 수 없다. 그래서
    사본이 불가피한데, 사본이 조용히 갈라지면 e2e 가 새 테마를 영영 안 잰다.
    파일을 AST 로 읽어 값을 대조한다 — 산문이 아니라 실제 리터럴을 본다.
    """
    canonical = set(THEMES)
    for rel in _COPIES:
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        found = None
        for node in tree.body:
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id == "_THEMES"
                    and isinstance(node.value, (ast.List, ast.Tuple))):
                found = {e.value for e in node.value.elts
                         if isinstance(e, ast.Constant) and isinstance(e.value, str)}
                break
        assert found is not None, (
            f"{rel}: `_THEMES` 리터럴을 찾지 못했다 — 이름이 바뀌었으면 이 가드도 갱신할 것")
        assert found == canonical, (
            f"{rel}: 테마 사본이 정본과 다르다\n"
            f"  사본에만: {sorted(found - canonical)}\n"
            f"  정본에만: {sorted(canonical - found)}")


def test_no_unit_test_keeps_its_own_theme_literal():
    """🔴 단위 스위트에는 사본이 **없어야** 한다 — import 로 합칠 수 있기 때문이다.

    사본이 불가피한 곳(e2e)만 위 시험이 값으로 잡고, 합칠 수 있는 곳은 애초에 사본을
    두지 않는다. 「합칠 수 있는데 안 합친 사본」이 이번 회고가 지목한 상태였다.
    """
    offenders = []
    for path in sorted((ROOT / "tests" / "unit" / "ui").rglob("test_*.py")):
        if path.name == "test_theme_list_closure.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and isinstance(node.value, (ast.List, ast.Tuple))):
                vals = {e.value for e in node.value.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)}
                if vals and vals <= set(THEMES) and len(vals) >= 2:
                    offenders.append(
                        f"{path.relative_to(ROOT).as_posix()}: `{node.targets[0].id}` "
                        f"가 테마 목록 사본이다 — `from ._contrast import THEMES` 로 바꿀 것")
    assert not offenders, "단위 스위트에 테마 목록 사본이 있다:\n  " + "\n  ".join(offenders)
