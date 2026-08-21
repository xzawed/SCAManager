import pytest
"""log_safety.sanitize_for_log 단위 테스트."""
from src.shared.log_safety import safe_repo_full_name, sanitize_for_log


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


# ── 리포 전체이름 형태 검증 (2026-08-21 · CodeQL 자초 차단) ────────────────
#
# 🔴 CodeQL 은 「접근 가능 목록에 있는가」 같은 **의미 검증**을 sanitizer 로 인식하지
#    못한다. `add_repo.py:150` 이 이미 그 검사를 하는데도 py/url-redirection 이,
#    `repos.py` 의 `GET /repos/{full}` 이 py/partial-ssrf 가 떴다.
#    URL 에 들어가는 값은 **형태**를 명시적으로 좁혀야 taint 가 끊긴다.


class TestSafeRepoFullName:
    """`owner/repo` 형태만 통과시키는가."""

    @pytest.mark.parametrize("value", ["owner/repo", "o/r", "a-b.c/d_e-f", "Org1/Repo.2"])
    def test_accepts_wellformed(self, value):
        assert safe_repo_full_name(value) == value

    @pytest.mark.parametrize("value", [
        "owner/sub/repo",          # 슬래시 2개 — 경로 탈출
        "https://evil@host/x",     # 호스트 주입
        "owner/",                  # 빈 repo
        "/repo",                   # 빈 owner
        "a b/c",                   # 공백
        "owner/repo?x=1",          # 쿼리 주입
        "owner/repo#frag",
        "../../etc/passwd",
        "",
    ])
    def test_rejects_malformed(self, value):
        assert safe_repo_full_name(value) is None, f"거부됐어야 한다: {value!r}"

    @pytest.mark.parametrize("value", [None, 123, ["owner/repo"], {"a": 1}])
    def test_rejects_non_string(self, value):
        """🔴 `None` 반환은 「비었다」가 아니라 **「믿을 수 없다」** 다."""
        assert safe_repo_full_name(value) is None

    def test_does_not_mutate_the_value(self):
        """대조군 — 통과시킬 때는 **원문 그대로** 돌려준다(자르거나 고치지 않는다)."""
        v = "Owner-Name/Repo.Name_1"
        assert safe_repo_full_name(v) == v
