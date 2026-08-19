"""STATE 종합 수치 줄의 **통합 수**가 파생되는가 (2026-08-19 실측).

## 사고 — 12커밋 이상 얼어 있었다

`docs/STATE.md` 10행은 이렇게 생겼다:

    전체 **7169** 수집 (단위 **6990** + 통합 179)

`check_docs_sync.py --fix` 는 이 줄의 **전체·단위만** 다시 쓴다. `_STATE_TOTAL` 정규식이
`단위 \*\*(\d+)\*\*` 에서 끊기고 치환 문자열도 거기서 끝나기 때문이다. 그래서
`+ 통합 N)` 은 도입 이래 **한 번도 갱신된 적이 없다**.

실측(`git log -- docs/STATE.md`): 2026-08-17 `7061` → 08-19 `7164` 로 전체가 12회
갱신되는 동안 통합은 내내 `171` 이었다. 머지 시점의 참값은 `174`(그리고 지금 `179`).

🔴 **그동안 게이트는 「✅ 테스트 수치 일치」를 냈다** — 자기가 방금 다시 쓴 바로 그 줄의
숫자가 틀렸는데도. 검증하는 쪽이 자기가 안 보는 자리에 초록을 발행한 형태다
(`.claude` 메모리 「거짓 집행자가 무집행보다 나쁘다」와 같은 클래스).

## 이 파일이 강제하는 것

1. 정규식이 통합 수를 **읽는다**(그래야 쓸 수 있다).
2. `--fix` 가 그 값을 **다시 쓴다** — 틀린 값을 넣어 두고 고쳐지는지 본다.
3. 리포의 실제 `STATE.md` 에서 `전체 == 단위 + 통합` 이 성립한다 (산술 불변식).

Fix must own every number on the line it rewrites; a number it silently skips will freeze.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "scripts"))

import check_docs_sync  # noqa: E402  # pylint: disable=wrong-import-position

_HEADLINE = re.compile(r"전체 \*\*(\d+)\*\* 수집 \(단위 \*\*(\d+)\*\* \+ 통합 (\d+)\)")


def _state_text() -> str:
    text = (_ROOT / "docs" / "STATE.md").read_text(encoding="utf-8")
    assert text.strip(), "STATE.md 가 비었다 — 빈 텍스트 위의 ✅ 는 fail-open"
    return text


# ── ① 정규식이 통합 수를 읽는가 ────────────────────────────────────────────


def test_the_headline_pattern_captures_the_integration_count():
    """🔴 읽지 못하면 쓸 수도 없다 — 이 그룹이 없던 것이 사고의 기전이었다."""
    match = check_docs_sync._STATE_TOTAL.search(_state_text())  # pylint: disable=protected-access

    assert match is not None, "종합 수치 줄을 못 찾는다 — 형식이 바뀌었는지 확인"
    assert match.lastindex is not None and match.lastindex >= 3, (
        f"통합 수를 캡처하지 않는다(그룹 {match.lastindex}개) — "
        "`--fix` 가 그 값을 소유하지 않으므로 다시 얼어붙는다"
    )


# ── ② --fix 가 그 값을 실제로 고치는가 ─────────────────────────────────────


def test_fix_rewrites_a_wrong_integration_count(tmp_path: Path):
    """🔴 배선 단언 — 틀린 값을 심어 두고 `apply_fix` 가 고치는지 본다.

    정규식만 넓히고 치환 문자열을 안 고치면 ①은 통과하고 값은 그대로 언다.
    두 축이 따로 필요한 이유다. `apply_fix` 는 프로젝트 루트를 받아 STATE 와
    README 배지 2개를 함께 쓰므로 셋을 다 복사한 임시 루트에서 돌린다.
    """
    state = _state_text()
    match = _HEADLINE.search(state)
    assert match, "종합 수치 줄 형식 불일치"
    total, unit, integ = (int(g) for g in match.groups())
    assert total == unit + integ, "리포 상태가 이미 어긋나 이 테스트가 신뢰할 수 없다"

    broken = state.replace(
        f"전체 **{total}** 수집 (단위 **{unit}** + 통합 {integ})",
        f"전체 **{total}** 수집 (단위 **{unit}** + 통합 {integ + 7})",
        1,
    )
    assert broken != state, "오염 주입 실패 — 이 테스트가 공허하다"

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "STATE.md").write_text(broken, encoding="utf-8")
    for name in ("README.md", "README.ko.md"):
        (tmp_path / name).write_text(
            (_ROOT / name).read_text(encoding="utf-8"), encoding="utf-8",
        )

    ok, msgs = check_docs_sync.apply_fix(tmp_path)

    assert ok, f"apply_fix 가 거부했다: {msgs}"
    after = _HEADLINE.search((tmp_path / "docs" / "STATE.md").read_text(encoding="utf-8"))
    assert after, "치환 후 형식이 깨졌다"
    assert int(after.group(3)) == integ, (
        f"통합 수가 {after.group(3)} 로 남았다(기대 {integ}) — `apply_fix` 가 그 값을 소유하지 않는다"
    )


# ── ③ 리포의 실제 상태가 산술적으로 성립하는가 ─────────────────────────────


def test_the_real_headline_is_arithmetically_sound():
    """🔴 대조군 — 위 두 축이 통과해도 현재 파일이 틀려 있으면 의미가 없다."""
    match = _HEADLINE.search(_state_text())
    assert match, "종합 수치 줄을 못 찾는다"
    total, unit, integ = (int(g) for g in match.groups())

    assert total == unit + integ, (
        f"STATE 10행이 산술적으로 불가능하다 — 전체 {total} ≠ 단위 {unit} + 통합 {integ} "
        f"(차 {total - unit - integ:+})"
    )


def test_the_headline_and_the_tracking_cell_agree():
    """두 사본이 같은 통합 수를 말하는가 — 한쪽만 갱신되던 것이 사고였다."""
    text = _state_text()
    head = _HEADLINE.search(text)
    cell = re.search(r"단위 (\d+) \+ 통합 (\d+) \(현재\)", text)
    assert head and cell, "두 지점 중 하나를 못 찾는다"

    assert head.group(2) == cell.group(1), (
        f"단위 불일치 — 종합 {head.group(2)} vs 추적셀 {cell.group(1)}"
    )
    assert head.group(3) == cell.group(2), (
        f"통합 불일치 — 종합 {head.group(3)} vs 추적셀 {cell.group(2)}. "
        "종합 쪽이 파생되지 않으면 이렇게 갈린다(2026-08-19 실측: 171 vs 179)"
    )


def test_the_headline_pattern_matches_exactly_once(  # noqa: D401
):
    """🔴 유일성 — `count=1` 치환이 **의도한 줄**을 고르는가 (Grok `01a019f1` G5).

    `apply_fix` 는 `_STATE_TOTAL.sub(..., count=1)` 로 첫 매치를 덮는다. 같은 모양의
    줄이 하나 더 있으면 앞선 것이 대신 덮이고, 정작 종합 수치는 그대로 언다 —
    이 파일이 고치려는 것과 **같은 결과**가 다른 경로로 재현된다.

    이 리포에는 실제로 그 사고의 형제가 있다: `_STATE_CELL_TOTAL` 주석이 「전역 sub 는
    원장 `**5365 수집**` 을 덮는다」고 적어 둔 것. 그래서 여기서도 센다.
    """
    matches = check_docs_sync._STATE_TOTAL.findall(_state_text())  # pylint: disable=protected-access

    assert len(matches) == 1, (
        f"종합 수치 형식 줄이 {len(matches)}개 — `count=1` 치환이 어느 것을 고를지 보장되지 않는다"
    )


def test_the_history_ledger_has_no_line_of_this_shape():
    """🔴 치환이 이력 절로 미끄러지지 않는다 — `apply_fix` 가 명시적으로 금지한 영역이다.

    `apply_fix` 는 이력 절 바이트가 바뀌면 쓰기를 거부하는 사후 단언을 갖고 있다.
    이 테스트는 그 방어가 **발동할 일 자체가 없는지**를 앞에서 확인한다.
    """
    text = _state_text()
    heading = "## 테스트 수 추적 이력"
    assert heading in text, "이력 절 제목이 없다 — 이 테스트가 공허하다"
    _, _, ledger = text.partition(heading)

    assert not check_docs_sync._STATE_TOTAL.findall(ledger), (  # pylint: disable=protected-access
        "이력 절에 같은 모양의 줄이 있다 — 치환이 원장을 덮을 수 있다"
    )
