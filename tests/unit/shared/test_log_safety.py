"""log_safety.sanitize_for_log 단위 테스트."""
from src.shared.log_safety import sanitize_for_log


def test_sanitize_strips_cr_lf():
    assert sanitize_for_log("hello\r\nworld") == "helloworld"


def test_sanitize_converts_tab_to_space():
    assert sanitize_for_log("a\tb") == "a b"


def test_sanitize_removes_null():
    assert sanitize_for_log("pre\x00post") == "prepost"


def test_sanitize_none_returns_empty():
    assert sanitize_for_log(None) == ""


def test_sanitize_numeric_coerced_to_string():
    assert sanitize_for_log(42) == "42"


def test_sanitize_truncates_long_input():
    out = sanitize_for_log("x" * 500, max_len=50)
    assert len(out) == 51  # 50 + 단일 ellipsis
    assert out.endswith("…")


def test_sanitize_short_input_not_truncated():
    assert sanitize_for_log("short") == "short"
