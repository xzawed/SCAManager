"""src/shared/ssrf.py 단위 테스트 — is_dangerous_ip 단일 출처 IP 분류.
Unit tests for src/shared/ssrf.py — is_dangerous_ip single-source IP classification.
"""
import pytest

from src.shared.ssrf import is_dangerous_ip


@pytest.mark.parametrize(
    "addr",
    [
        "10.0.0.1",            # private
        "192.168.1.1",         # private
        "172.16.0.1",          # private
        "127.0.0.1",           # loopback
        "169.254.169.254",     # link-local (cloud metadata)
        "0.0.0.0",             # reserved
        "224.0.0.1",           # multicast
        "100.64.1.1",          # CGNAT (RFC 6598) — 핵심 회귀 가드 / key regression guard
        "100.127.255.255",     # CGNAT 상단 경계 / CGNAT upper boundary
        "::1",                 # IPv6 loopback
        "fe80::1",             # IPv6 link-local
    ],
)
def test_dangerous_ips_blocked(addr):
    assert is_dangerous_ip(addr) is True


@pytest.mark.parametrize(
    "addr",
    [
        "8.8.8.8",             # public
        "1.1.1.1",             # public
        "100.63.255.255",      # CGNAT 직전 (공인) / just below CGNAT (public)
        "100.128.0.0",         # CGNAT 직후 (공인) / just above CGNAT (public)
    ],
)
def test_public_ips_allowed(addr):
    assert is_dangerous_ip(addr) is False


def test_domain_name_returns_false():
    # 도메인명은 IP 파싱 실패 → False (DNS 해석은 호출자 책임)
    # Domain names fail IP parsing → False (DNS resolution is the caller's responsibility)
    assert is_dangerous_ip("example.com") is False
    assert is_dangerous_ip("") is False


def test_cgnat_check_no_version_error_for_ipv6():
    # IPv6 주소가 IPv4 CGNAT 네트워크와 비교돼도 TypeError 없이 동작 (다른 사유로 차단/허용)
    # IPv6 vs IPv4-CGNAT comparison must not raise TypeError (blocked/allowed by other rules)
    assert is_dangerous_ip("2001:4860:4860::8888") is False  # public IPv6 (Google DNS)


# ─── #1489 — 제어문자 URL 은 저장 시점에 막는다 ────────────────────────────


_CONTROL_CHARS = {
    "TAB": chr(9), "LF": chr(10), "CR": chr(13),
    "VT": chr(11), "FF": chr(12), "NUL": chr(0),
}


@pytest.mark.parametrize("name,ch", sorted(_CONTROL_CHARS.items()))
def test_control_char_url_is_rejected_at_storage(name, ch):
    """🔴 제어문자가 든 URL 은 **배달 불가능**하므로 저장 시점에 거부한다.

    `urlparse` 는 제어문자를 안전으로 본다. 그래서 검증 3층(저장 게이트 ·
    `validate_external_url` · 발신)을 전부 통과한 뒤 `httpx.InvalidURL` 로 죽었다.
    그 예외는 `httpx.HTTPError` 밖이라(28종 중 7종) 「여기가 유일한 통제」라고
    적어 둔 `except httpx.HTTPError` 절을 그대로 빠져나간다(#1489).

    urlparse treats control characters as safe, so an undeliverable URL was accepted and
    persisted, then failed at send time with an exception outside the guarded hierarchy.
    """
    from src.shared.ssrf import is_safe_webhook_url  # noqa: PLC0415

    assert is_safe_webhook_url(f"https://hooks.example.com/a{ch}b") is False, (
        f"{name} 이 든 URL 이 저장 게이트를 통과한다"
    )


def test_normal_url_still_allowed():
    """대조군 — 제어문자 거부가 정상 URL 을 막으면 안 된다."""
    from src.shared.ssrf import is_safe_webhook_url  # noqa: PLC0415

    assert is_safe_webhook_url("https://hooks.slack.com/services/T00/B00/XXXX") is True
    assert is_safe_webhook_url("https://n8n.example.com/webhook/abc-123_x?y=1") is True


def test_percent_encoded_control_char_is_allowed():
    """퍼센트 인코딩된 값은 제어문자가 아니다 — 과잉 차단 방지."""
    from src.shared.ssrf import is_safe_webhook_url  # noqa: PLC0415

    assert is_safe_webhook_url("https://hooks.example.com/a%0Ab") is True


# ─── #1489 — HTTPX_SEND_ERRORS 가 httpx 예외 계층 전체를 덮는가 ──────────────


def test_httpx_send_errors_covers_every_httpx_exception():
    """🔴 **구조 가드** — `HTTPX_SEND_ERRORS` 가 httpx 의 모든 예외 클래스를 덮어야 한다.

    `except httpx.HTTPError` 만 쓰던 동안, 28종 중 **7종**(`InvalidURL` ·
    `CookieConflict` · `StreamError` 계열 5종)이 그대로 빠져나갔다. 좁은 catch 를 쓰는
    지점이 3곳이라 공용 튜플로 묶었고, httpx 가 새 예외를 추가하면 여기서 red 가 된다.

    Structural guard: if httpx adds an exception class outside the tuple, this goes red —
    the narrow `except httpx.HTTPError` hole must not silently return.
    """
    import inspect  # noqa: PLC0415

    import httpx  # noqa: PLC0415

    from src.shared.http_client import HTTPX_SEND_ERRORS  # noqa: PLC0415

    all_exc = [
        (n, o) for n, o in vars(httpx).items()
        if inspect.isclass(o) and issubclass(o, Exception)
    ]
    assert all_exc, "httpx 예외를 하나도 못 찾았다 — 계기 고장"

    uncovered = sorted(n for n, o in all_exc if not issubclass(o, HTTPX_SEND_ERRORS))
    assert not uncovered, (
        f"HTTPX_SEND_ERRORS 가 못 덮는 httpx 예외: {uncovered} — "
        "좁은 except 가 이것들을 ASGI 밖으로 흘린다"
    )


def test_httpx_send_errors_is_not_bare_exception():
    """계기 대조군 — 튜플이 `Exception` 을 담으면 위 테스트가 공허해진다."""
    from src.shared.http_client import HTTPX_SEND_ERRORS  # noqa: PLC0415

    assert Exception not in HTTPX_SEND_ERRORS
    assert BaseException not in HTTPX_SEND_ERRORS
