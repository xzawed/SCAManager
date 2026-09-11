"""프리셋 비교표의 «변경 없는» 행을 알파로 흐리지 않는다.

Unchanged preset-diff rows must be de-emphasised by color token, never by alpha.
"""
from __future__ import annotations

import re
from pathlib import Path

_SETTINGS = Path(__file__).resolve().parents[3] / "src" / "templates" / "settings.html"

# 대비가 검증된 글자 토큰 — `--text-3` 은 네 테마에서 4.73~7.37 이다(#1611).
_AA_TEXT_TOKENS = {"--text-1", "--text-2", "--text-3"}


def _render_preset_diff_body() -> str:
    """`renderPresetDiff` 본문만 잘라 낸다 — 없으면 red(공허한 초록 방지)."""
    src = _SETTINGS.read_text(encoding="utf-8")
    head = "function renderPresetDiff(name) {"
    assert head in src, (
        f"`{head}` 를 찾지 못했다 — 함수가 사라졌거나 이름이 바뀌었다. "
        "이 가드가 무엇을 지키는지 다시 정해야 한다.")
    i = src.index(head) + len(head)
    depth, j = 1, i
    while depth:
        assert j < len(src), "중괄호가 닫히지 않는다 — 잘라내기가 실패했다"
        depth += {"{": 1, "}": -1}.get(src[j], 0)
        j += 1
    return src[i:j]


def test_unchanged_rows_are_not_dimmed_by_alpha():
    """🔴 알파로 흐리면 대비는 «항상» 내려간다.

    실측(#1639 W9): `opacity:.45` 를 씌운 행의 합성 대비는 dark 2.52 · light 2.08 ·
    pastel 2.18 · catppuccin 2.98 로 **네 테마 전부 AA 미달**이었다. 그 행은 프리셋
    카드를 펴야 보이므로 어떤 감사에도 걸린 적이 없었다.

    🔴 이 가드가 단위 축에 있는 이유: 이 변경을 관측하는 것은 e2e 스윕뿐이라
    역-뮤테이션 게이트(단위만 실행)가 초록이었다 — 「관측되지 않는 수정」이다.
    """
    body = _render_preset_diff_body()
    # 🔴 주석은 코드가 아니다 — «왜 쓰지 않는가» 를 적어둔 줄이
    #    이 가드에 걸려 red 가 됐다. 금지어를 설명하는 자리까지 금지하면
    #    다음 사람은 주석을 지우고 넘어간다.
    code = "\n".join(
        ln for ln in body.splitlines() if not ln.strip().startswith("//"))
    dimmed = re.findall(r"opacity\s*:\s*(?:0?\.\d+|0)\b", code)
    assert not dimmed, (
        f"행을 알파로 흐리고 있다({dimmed}) — 합성 대비가 AA 아래로 떨어진다. "
        "구분은 «약한 글자색» 으로 한다.")

    # 공허 방지 — 대체 수단이 «실제로» 쓰이고, 그 색이 검증된 토큰인지 본다.
    assert 'class="pt-row-same"' in body, (
        "변경 없는 행을 구분하는 수단이 없다 — 알파를 지우기만 하면 구분이 사라진다")
    rule = re.search(
        r"\.preset-table\s+tr\.pt-row-same\s+td\s*\{[^}]*color\s*:\s*var\(\s*(--[\w-]+)\s*\)",
        _SETTINGS.read_text(encoding="utf-8"))
    assert rule, "`tr.pt-row-same td` 의 글자색 규칙이 없다 — 클래스만 붙고 색이 안 바뀐다"
    assert rule.group(1) in _AA_TEXT_TOKENS, (
        f"대비가 확인되지 않은 토큰이다: {rule.group(1)} — 네 테마 실측 후 넣는다")
