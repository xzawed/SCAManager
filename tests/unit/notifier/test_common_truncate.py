"""truncate_message 경계 회귀 가드 (품질감사 notifier-004).

truncate_message boundary regression guard (audit notifier-004).

max_length < len(suffix) 일 때 기존 구현 `text[:max_length - len(suffix)]` 은 음수 슬라이스가 되어
출력이 오히려 max_length 를 초과하는 계약 위반이 발생했다(예: truncate_message("hello world", 2)
== "hello worl..."). 현재 운영 호출자(discord 4096·slack 3000·telegram 4096·기본 80)는 suffix(3)보다
훨씬 커 도달 불가였으나 잠재 footgun → 출력 ≤ max_length 계약을 봉인한다.
"""
import pytest

from src.notifier._common import truncate_message


@pytest.mark.parametrize("max_length", [0, 1, 2, 3])
def test_truncate_never_exceeds_max_length_below_suffix(max_length):
    """max_length 가 suffix 길이 이하라도 출력은 max_length 를 넘지 않는다."""
    out = truncate_message("hello world", max_length)
    assert len(out) <= max_length, f"max_length={max_length} 인데 출력 {out!r}(len {len(out)}) 초과"


def test_truncate_no_truncation_when_within_limit():
    """한도 이내 텍스트는 그대로 반환 (회귀)."""
    assert truncate_message("short", 100) == "short"


def test_truncate_appends_suffix_when_over_limit():
    """한도 초과 + 충분한 여유 시 잘라내고 suffix 부착 (정상 케이스 회귀)."""
    out = truncate_message("hello world", 8)
    assert out == "hello..."
    assert len(out) == 8
