"""STATE 헤더의 **구조 불변식** — 산문이 아니라 대응 관계만 본다.

'최신' 블록이 체인으로 누적되면 SSOT 가 자기 규칙을 어긴다.
헤더 영역의 테스트 수가 두 값이면 어느 쪽을 믿을지 알 수 없다.

Only correspondences are checked — prose truth is undecidable.
"""
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_STATE = _ROOT / "docs" / "STATE.md"


def test_state_has_exactly_one_latest_block():
    """🔴 STATE 헤더의 `**최신 (…)**` 블록은 **정확히 1개**다.

    헤더에 직전 작업을 체인으로 쌓지 않는다.
    """
    blocks = re.findall(r"^\*\*최신 \(", _STATE.read_text(encoding="utf-8"), re.M)
    assert len(blocks) == 1, (
        f"STATE 의 '최신' 블록이 {len(blocks)}개다(1이어야 함).\n"
        "→ 직전 블록을 헤더에서 빼고 최신 1건만 남길 것."
    )


def _state_current_region(text: str) -> str:
    """'현재 값' 영역만 — 지표 표(append-only 추적 이력) 앞까지.

    🔴 표 안의 `단위 **5206**` 류는 **과거 시점 기록**이라 현재 값과 다른 게 정상이다.
    파일 전체를 비교하면 이 테스트는 정상적인 이력을 위반으로 신고한다.
    """
    head, _, _ = text.partition("\n| 지표 |")
    return head


def test_state_current_counts_agree_across_the_header():
    """🔴 헤더 영역(현재 값)의 테스트 수는 한 값이어야 한다."""
    region = _state_current_region(_STATE.read_text(encoding="utf-8"))
    totals = re.findall(r"전체 \*\*(\d+)\*\* 수집", region)
    units = re.findall(r"단위 \*\*(\d+)\*\*", region)
    assert totals, "'전체 N 수집' 표현을 헤더에서 못 찾았다 — 형식이 바뀌었는지 확인할 것"
    assert len(set(totals)) == 1, f"헤더의 '전체 수집' 수가 어긋난다: {sorted(set(totals))}"
    assert len(set(units)) == 1, f"헤더의 '단위' 수가 어긋난다: {sorted(set(units))}"


def test_current_region_excludes_the_append_only_ledger():
    """🔴 관측 범위 자체를 고정한다 — 표까지 삼키면 이력이 위반으로 신고된다."""
    text = _STATE.read_text(encoding="utf-8")
    region = _state_current_region(text)
    assert len(region) < len(text), "추적 표를 잘라내지 못했다 — 표 머리글 형식 확인"
    assert "추적 이력" in text, "추적 이력 표가 사라졌다 — 이 가드의 전제 붕괴"
    assert "추적 이력" not in region, "추적 이력이 현재-값 영역에 포함됐다"
