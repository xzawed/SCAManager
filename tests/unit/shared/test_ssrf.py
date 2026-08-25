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


def test_every_control_code_point_is_rejected():
    """🔴 C0 전 범위(U+0000–U+001F) **와 DEL(U+007F)** 을 전수 검사한다.

    위 parametrize 는 대표 6종만 본다 — `== 0x7F` 조건만 지우는 뮤테이션이 그대로 초록이었다.
    거부 집합은 httpx 가 실제로 거부하는 코드포인트와 일치해야 하므로 전수로 못박는다.

    The representative sample above left `== 0x7F` unguarded; pin the whole measured set.
    """
    from src.shared.ssrf import is_safe_webhook_url  # noqa: PLC0415

    leaked = [
        hex(cp) for cp in list(range(0x00, 0x20)) + [0x7F]
        if is_safe_webhook_url(f"https://hooks.example.com/a{chr(cp)}b") is not False
    ]
    assert not leaked, f"저장 게이트를 통과하는 제어문자: {leaked}"


def test_space_is_not_treated_as_a_control_char():
    """대조군 — U+0020 은 httpx 가 인코딩하므로 거부 대상이 아니다(과잉 차단 방지)."""
    from src.shared.ssrf import is_safe_webhook_url  # noqa: PLC0415

    assert is_safe_webhook_url("https://hooks.example.com/a b") is True


def test_narrow_httpx_except_is_not_used_anywhere_in_src():
    """🔴 **배선 단언** — 공용 튜플을 정의만 하고 호출부가 안 쓰면 구멍은 그대로다.

    구조 가드(`covers_every_httpx_exception`)는 튜플만 본다. 호출부를 옛 좁은 절로
    되돌려도 그 테스트는 초록이다 — 정의 ≠ 배선. AST 로 실제 except 절을 읽는다.

    Wiring assertion: the structural guard only inspects the tuple; reverting the call sites
    would keep it green. Read the actual except clauses via AST.
    """
    import ast  # noqa: PLC0415
    import pathlib  # noqa: PLC0415

    # #1498 — 범위를 `webhook/providers` 에서 **src/ 전체**로 넓혔다.
    #   그전에는 3곳만 보고 나머지 24곳의 같은 구멍을 못 봤다.
    #   Scope widened from webhook/providers to all of src/ (#1498).
    root = pathlib.Path(__file__).resolve().parents[3] / "src"
    files = sorted(root.rglob("*.py"))
    assert len(files) > 100, f"src/ 에서 {len(files)}개 파일만 찾았다 — 스캐너 점검 필요"

    narrow: list[str] = []
    wired = 0
    for f in files:
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler) or node.type is None:
                continue
            src = ast.unparse(node.type)
            # 🔴 튜플 안에 숨은 것도 같은 구멍이다 — `except (httpx.HTTPError, KeyError)`
            #   는 7종을 여전히 흘린다. 첫 판은 정확 일치만 봐서 19곳을 못 봤다(Grok Q5).
            #   A tuple member is the same hole; exact-match missed 19 sites.
            in_tuple = isinstance(node.type, ast.Tuple) and any(
                ast.unparse(e) == "httpx.HTTPError" for e in node.type.elts
            )
            if src == "httpx.HTTPError" or in_tuple:
                narrow.append(f"{f.name}:{node.lineno}")
            elif "HTTPX_SEND_ERRORS" in src:
                wired += 1

    assert not narrow, (
        "좁은 `httpx.HTTPError` 가 남아 있다(단독 또는 튜플 원소) — "
        f"HTTPError 밖 7종이 빠져나간다: {narrow}"
    )
    assert wired >= 46, f"HTTPX_SEND_ERRORS 를 쓰는 except 가 {wired}곳뿐이다 (기대 46곳 이상)"
