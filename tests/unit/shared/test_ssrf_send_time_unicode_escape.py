"""발신 SSRF 검증이 `UnicodeEncodeError` 로 통째로 빠져나간다 (감사 A6, #1519).

🔴 실측. `src/shared/ssrf.py::is_safe_webhook_url` 의 docstring 은 도메인명을
저장 게이트에서 통과시키는 근거를 이렇게 적는다:

    「도메인명은 IP 가 아니라 통과 → send-time validate_external_url 가 DNS 해석 후 최종 차단」
    "Domain names pass (not IPs) and are resolved+blocked at send time by validate_external_url."

그런데 DNS 라벨이 63자를 넘으면 `socket.getaddrinfo` 는 **해석하지도 차단하지도**
않는다 — `idna` 코덱이 `UnicodeEncodeError` 를 올린다. 그것은 `ValueError` 이지
**`OSError` 가 아니다**(실측):

    socket.getaddrinfo('a'*70 + '.example.com', None)
      -> UnicodeEncodeError   OSError? False   ValueError? True

`src/notifier/_http.py::validate_external_url` 의 fail-closed 핸들러는
`except OSError` 다. 그래서 예외가 그대로 통과해 알림 태스크 밖으로 전파된다 —
그 핸들러의 주석이 스스로 「notify 태스크로 전파돼 크래시」를 막는다고 적는 그 경로다.

end-to-end 실측:

    is_safe_webhook_url('https://' + 'a'*70 + '.example.com/hook')  -> True   (저장 통과)
    validate_external_url(같은 URL)                                  -> RAISED UnicodeEncodeError

즉 이런 URL 은 설정 폼·REST API 를 통과해 저장되고, 그 리포의 **모든 알림 발신**이
차단·로깅 대신 예외로 죽는다.

비-ASCII 호스트는 `gaierror`(= `OSError`)라 이미 잡힌다 — 63자 라벨만 다른 축이다.

The send-time layer neither resolves nor blocks; it raises a ValueError that escapes
the OSError fail-closed handler.
"""
from __future__ import annotations

import os
import socket

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest  # noqa: E402

from src.notifier._http import validate_external_url  # noqa: E402
from src.shared.ssrf import is_safe_webhook_url  # noqa: E402

_LONG_LABEL_HOST = "a" * 70 + ".example.com"
_URL = f"https://{_LONG_LABEL_HOST}/hook"


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_getaddrinfo_really_raises_a_non_oserror():
    """🔴 전제 — 63자 초과 라벨이 정말 `OSError` 밖의 예외를 내는가.

    `OSError` 였다면 기존 핸들러가 이미 잡으므로 이 파일 전체가 공허하다.
    """
    with pytest.raises(UnicodeError) as excinfo:
        socket.getaddrinfo(_LONG_LABEL_HOST, None)
    assert not isinstance(excinfo.value, OSError), (
        "getaddrinfo 가 OSError 를 낸다 — 전제가 바뀌었다(파이썬/플랫폼 변경)"
    )
    assert isinstance(excinfo.value, ValueError)


def test_a_non_ascii_host_is_already_covered():
    """대조군 — 비-ASCII 호스트는 `gaierror`(= `OSError`)라 기존 핸들러가 잡는다.

    두 축을 섞으면 「이미 막혀 있다」고 오판하게 된다.
    """
    try:
        socket.getaddrinfo("호스트.example.invalid", None)
    except OSError:
        pass  # 기대한 경로
    except UnicodeError:  # pragma: no cover — 플랫폼차
        pytest.skip("이 플랫폼은 비-ASCII 호스트도 UnicodeError 를 낸다")


def test_the_storage_gate_lets_the_hostname_through():
    """🔴 전제 — 저장 게이트가 이 URL 을 통과시킨다.

    막았다면 발신 층까지 도달하지 않으므로 아래 단언이 무의미하다.
    """
    assert is_safe_webhook_url(_URL) is True, (
        "저장 게이트가 이미 막는다 — docstring 의 「발신에서 최종 차단」 서술과 다르다"
    )


# ─── 결함 ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_time_validation_blocks_instead_of_raising():
    """🔴 발신 검증이 **차단 판정을 돌려준다** — 예외를 알림 태스크로 올리지 않는다.

    올리면 그 리포의 모든 알림 발신이 죽고, `except OSError` 핸들러의 주석이
    스스로 막는다고 적은 「notify 태스크로 전파돼 크래시」가 그대로 일어난다.
    """
    result = await validate_external_url(_URL)
    assert result is False, (
        f"63자 초과 DNS 라벨이 차단되지 않았다 (반환 {result!r}) — "
        "해석 불가는 fail-closed 여야 한다"
    )


@pytest.mark.asyncio
async def test_a_normal_host_still_resolves_or_fails_safely():
    """대조군 — 정상 호스트는 이 수정으로 동작이 바뀌지 않는다."""
    result = await validate_external_url("https://example.invalid/hook")
    assert result is False, "해석 실패는 여전히 fail-closed"
