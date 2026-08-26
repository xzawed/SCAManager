"""Accept-Language 협상이 **지원 언어를 건너뛴다** (감사 C1, #1519).

🔴 실측. `_parse_accept_language` 는 q-weight 로 정렬한 뒤 **맨 앞 하나만** 돌려준다:

    items.sort(key=lambda x: x[1], reverse=True)
    return items[0][0]

그 값이 지원 목록에 없으면 `_detect_locale` 이 그냥 버리고 기본 로케일로 간다
(`locale.py:88-89`). 그래서 클라이언트가 **지원 언어를 명시적으로 요청했는데도**
영어가 나온다:

    supported = en, ko, ja        default = en

    "ko-KR,ko;q=0.9,en;q=0.8"        -> ko   (정상)
    "zh-CN,ko;q=0.9"                 -> en   🔴 ko 여야 한다
    "fr-FR,fr;q=0.9,ja;q=0.8,en;q=0.7" -> en   🔴 ja 여야 한다 (ja q=0.8 > en q=0.7)
    "zh-CN,zh;q=0.9,ko;q=0.8,ja;q=0.7" -> en   🔴 ko 여야 한다

세 번째가 특히 명확하다 — `ja` 와 `en` 이 **둘 다 지원 목록**에 있고 클라이언트가
`ja` 를 더 높게 매겼는데 `en` 이 나간다.

RFC 7231 §5.3.5 는 최고 q 의 **수용 가능한(acceptable)** 언어를 고르라고 한다.
모듈 docstring 도 우선순위 2를 「Accept-Language 헤더 (RFC 7231 q-weight 파싱)」라
적고, 파서 docstring 은 「return top locale」이라 적는다 — 「top **supported** locale」
이어야 맞다.

The parser returns the top-q language even when it is not one we support.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest  # noqa: E402

from src.config import settings  # noqa: E402
from src.middleware.locale import LocaleMiddleware  # noqa: E402


@pytest.fixture()
def middleware() -> LocaleMiddleware:
    return LocaleMiddleware(app=lambda *a, **k: None)


def _detect(mw: LocaleMiddleware, header: str) -> str:
    return mw._detect_locale([(b"accept-language", header.encode())])  # noqa: SLF001


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_the_supported_set_has_more_than_the_default(middleware):
    """🔴 전제 — 지원 언어가 기본값 하나뿐이면 이 파일 전체가 공허하다."""
    assert len(middleware._supported) > 1, (  # noqa: SLF001
        f"지원 로케일이 {middleware._supported} 뿐이다 — 협상할 것이 없다"  # noqa: SLF001
    )
    assert settings.default_locale in middleware._supported  # noqa: SLF001


def test_a_plain_supported_header_still_works(middleware):
    """대조군 — 최고 q 가 지원 언어면 기존 동작 그대로다."""
    assert _detect(middleware, "ko-KR,ko;q=0.9,en;q=0.8") == "ko"


def test_no_acceptable_language_falls_back_to_default(middleware):
    """대조군 — 지원 언어가 **하나도** 없으면 기본 로케일이다."""
    assert _detect(middleware, "zh-CN,fr;q=0.9") == settings.default_locale


# ─── 결함 ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("header,expected", [
    # 최고 q 는 미지원이지만 그 다음이 지원 언어
    ("zh-CN,ko;q=0.9", "ko"),
    # 지원 언어 둘이 있고 클라이언트가 ja 를 더 높게 매겼다
    ("fr-FR,fr;q=0.9,ja;q=0.8,en;q=0.7", "ja"),
    # 미지원 둘을 건너뛰고 ko(q=0.8) 를 골라야 한다
    ("zh-CN,zh;q=0.9,ko;q=0.8,ja;q=0.7", "ko"),
])
def test_picks_the_highest_q_supported_language(middleware, header, expected):
    """🔴 최고 q 의 **수용 가능한** 언어를 고른다 (RFC 7231 §5.3.5).

    최고 q 하나만 보고 버리면, 클라이언트가 지원 언어를 명시적으로 요청했는데도
    기본 로케일이 나간다.
    """
    got = _detect(middleware, header)
    assert got == expected, (
        f"{header!r} -> {got!r} 이 나왔다 (기대 {expected!r}) — "
        "지원 언어를 건너뛰고 기본값으로 갔다"
    )


def test_ties_preserve_header_order(middleware):
    """🔴 q 가 같으면 헤더에 먼저 나온 지원 언어를 고른다 — 안정 정렬 유지."""
    assert _detect(middleware, "ja;q=0.9,ko;q=0.9") == "ja"
    assert _detect(middleware, "ko;q=0.9,ja;q=0.9") == "ko"


def test_a_region_subtag_still_matches_its_base(middleware):
    """대조군 — `ko-KR` 같은 지역 하위태그가 `ko` 로 매칭되는 기존 동작 유지."""
    assert _detect(middleware, "ko-KR") == "ko"
