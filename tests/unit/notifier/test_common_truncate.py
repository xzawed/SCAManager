"""truncate_message 경계 회귀 가드 (품질감사 notifier-004).

truncate_message boundary regression guard (audit notifier-004).

max_length < len(suffix) 일 때 기존 구현 `text[:max_length - len(suffix)]` 은 음수 슬라이스가 되어
출력이 오히려 max_length 를 초과하는 계약 위반이 발생했다(예: truncate_message("hello world", 2)
== "hello worl..."). 현재 운영 호출자(discord 4096·slack 3000·telegram 4096·기본 80)는 suffix(3)보다
훨씬 커 도달 불가였으나 잠재 footgun → 출력 ≤ max_length 계약을 봉인한다.
"""
import pytest

from src.notifier._common import truncate_html_message, truncate_message


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


# ── truncate_html_message — Telegram HTML 안전 절단 (종합감사 P1-8) ──────────

def test_truncate_html_short_unchanged():
    """한도 이내면 그대로 반환."""
    assert truncate_html_message("<b>hi</b>", 4096) == "<b>hi</b>"


def test_truncate_html_strips_partial_entity():
    """🔴 절단점이 이스케이프 엔티티(&lt;) 중간이면 부분 엔티티를 남기지 않는다 (400 방지)."""
    text = "x" * 4090 + "&lt;danger"
    out = truncate_html_message(text, 4096)
    # 끝에 미완결 '&...'(;' 없음)이 남으면 안 됨
    tail = out.rstrip("…")
    amp = tail.rfind("&")
    assert amp == -1 or ";" in tail[amp:], f"partial entity leaked: {out[-12:]!r}"
    assert len(out) <= 4096


def test_truncate_html_closes_unclosed_tag():
    """🔴 절단으로 <b> 가 열린 채 남으면 </b> 로 닫는다 (Telegram parse 400 방지)."""
    text = "<b>" + "x" * 4200 + "</b>"
    out = truncate_html_message(text, 4096)
    assert out.count("<b>") == out.count("</b>"), f"unbalanced: {out[:6]!r}..{out[-8:]!r}"
    assert len(out) <= 4096


def test_truncate_html_strips_partial_tag():
    """절단점이 태그(<...) 중간이면 미완결 태그를 제거한다 (cut≈4055 를 태그가 straddle)."""
    text = "y" * 4050 + "<verylongtagname>" + "z" * 200  # 4096 초과 → 절단 발생
    out = truncate_html_message(text, 4096)
    # 끝에 미완결 태그('<...'에 '>' 없음)가 남으면 안 됨
    tail = out.rstrip("…")
    lt = tail.rfind("<")
    assert lt == -1 or ">" in tail[lt:], f"partial tag leaked: {out[-12:]!r}"
    assert len(out) <= 4096
