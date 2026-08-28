"""`*` 는 리터럴 태그가 아니라 **언어 범위**다 (RFC 7231 §5.3.5, #1536 축②).

축①(`q=0` 을 무시하고 거부한 언어를 고름)은 #1548 로 나갔다. 남은 것이 축②다:
`*` 가 `supported` 조회에 리터럴로 들어가 절대 매치되지 않고, 그래서 클라이언트가
「영어 말고 아무거나」라고 말해도 영어를 받는다.

## 의미론

`*` 의 범위 = `supported` − **헤더에 명시된 모든 태그**(`q=0` 으로 언급된 것 포함).

- `*` 단독 → 범위가 supported 전체이고 전부 동률이다. 서버가 기본값을 고르는 것이
  정당하므로 `None` 을 돌려준다(호출부가 `settings.default_locale` 로 간다).
- 기본값이 범위 **안**이면 마찬가지로 `None` — 기본값이 클라이언트를 만족시킨다.
- 기본값이 범위 **밖**이면(명시적으로 거부됐거나 더 낮은 q 를 받았으면) 범위에서
  고른다. 그때 `sorted()` 로 고른다 — `supported_locales` 설정 **순서에 결합하지 않는다**.

## 🔴 함정

`_parse_lang_items` 는 `q=0` 항목을 **버린다**(`rejected` → `continue`). 「명시된 태그」를
그 결과에서 뽑으면 `en;q=0, *` 에서 `en` 이 명시되지 않은 것처럼 보여 `*` 가 en 을
되살린다 — 사용자가 거부한 바로 그 언어를. 명시 집합은 **원문에서** 뽑아야 한다.
"""
from __future__ import annotations

import pytest

from src.middleware.locale import LocaleMiddleware

SUPPORTED = frozenset({"en", "ko", "ja"})
DEFAULT = "en"


def _pick(header: str, supported: frozenset = SUPPORTED, default: str | None = DEFAULT):
    """헤더 하나를 협상에 태운다.

    🔴 헤더 이름은 **바이트**로 비교된다(`name.lower() != b"accept-language"`). 문자열을
    넘기면 전 케이스가 `None` 이 되어 「전부 통과」처럼 보인다 — 실제로 겪었다.
    """
    return LocaleMiddleware._parse_accept_language(  # noqa: SLF001
        [(b"accept-language", header.encode())], supported, default)


def test_the_harness_still_measures_the_shipped_axis():
    """계기 자기검사 — 이미 고쳐진 축①이 맞게 나와야 아래 결과를 믿는다."""
    assert _pick("ko-KR,ko;q=0.9,en;q=0.8") == "ko"
    assert _pick("ko;q=0") is None
    assert _pick("en") == "en"


# ─── `*` 가 기본값을 정당화하는 경우 — 지금도 옳다, 깨뜨리면 안 된다 ────────


@pytest.mark.parametrize("header", ["*", "zh, *", "ko;q=0.5, *;q=0.9", "*;q=0",
                                    "zh, *;q=0"])
def test_default_applies_when_it_satisfies_the_client(header: str):
    """기본값이 범위 안이거나 아무것도 수용되지 않으면 `None` — 호출부가 기본값으로 간다."""
    assert _pick(header) is None


def test_an_explicit_tag_still_beats_the_wildcard_at_the_same_weight():
    """`ko-KR, *` 는 둘 다 q=1 이고 입력 순서가 앞선 ko 가 이긴다."""
    assert _pick("ko-KR, *") == "ko"


def test_explicitly_accepted_language_wins_when_everything_else_is_rejected():
    assert _pick("en, *;q=0") == "en"


# ─── 살아 있는 결함 4건 ─────────────────────────────────────────────────────


def _effective(header: str) -> str:
    """사용자가 실제로 보게 되는 로케일.

    🔴 원시 반환값이 아니라 이것을 단언한다. `None` 은 「기본값을 써라」는 뜻이라
    기본값이 범위 안이면 `None` 도 정답이다 — 원시값으로 단언하면 옳은 구현을 red 로 만든다.
    """
    return _pick(header) or DEFAULT


@pytest.mark.parametrize("header", ["*;q=0.9, en;q=0.1", "en;q=0.1, *;q=0.9"])
def test_wildcard_outranking_an_explicit_tag_does_not_serve_that_tag(header: str):
    """사용자가 en 을 **최하위**로 뒀는데 en 을 받는다 — 지금의 결함."""
    assert _effective(header) in {"ko", "ja"}


def test_a_rejected_tag_is_not_revived_by_the_wildcard():
    """🔴 이 시험이 함정을 잡는다.

    `en;q=0, *` 는 「영어만 빼고 아무거나」다. `q=0` 항목은 파싱 결과에서 사라지므로
    「명시된 태그」를 그 결과에서 뽑으면 en 이 `*` 의 범위에 다시 들어온다.
    """
    assert _effective("en;q=0, *") in {"ko", "ja"}


def test_wildcard_outranks_a_lower_weighted_explicit_tag():
    """`*;q=1, ko;q=0.5` — 범위는 {en, ja} 이고 q 가 더 높다. ko 를 주면 안 된다."""
    assert _effective("*;q=1, ko;q=0.5") in {"en", "ja"}


# ─── 고르는 방식이 설정 순서에 결합하지 않는다 ──────────────────────────────


def test_the_pick_is_the_same_on_every_process():
    """🔴 범위에서 고를 때 **집합 순회 순서**에 기대면 안 된다.

    파이썬 문자열 해시는 프로세스마다 무작위다(`PYTHONHASHSEED`). 실측 — 같은
    6-로케일 frozenset 의 순회 순서:

        seed=1  ['en', 'zh', 'fr', 'ja', 'ko', 'de']
        seed=3  ['ja', 'ko', 'fr', 'zh', 'en', 'de']

    그래서 `next(iter(...))` 로 고르면 **재시작마다 화면 언어가 달라진다**. 정렬로
    고정한다. 이 단언이 그것을 못 박는다 — 값을 적어야 실효가 있다.

    같은 프로세스 안에서 여러 번 부르거나, 같은 원소를 다른 순서로 만들어 비교하는
    것은 **공허하다**(둘 다 같은 순서가 나온다 — 실측). 그래서 정확한 값을 단언한다.
    """
    supported = frozenset({"en", "ko", "ja", "zh", "fr", "de"})
    got = LocaleMiddleware._parse_accept_language(  # noqa: SLF001
        [(b"accept-language", b"en;q=0, *")], supported, "en")
    assert got == "de", "정렬이 아니라 집합 순회로 골랐다 — 프로세스마다 달라진다"


def test_wildcard_range_can_be_empty_and_then_the_default_applies():
    """지원 언어가 전부 명시적으로 거부되면 `*` 가 고를 것이 없다."""
    assert _pick("en;q=0, ko;q=0, ja;q=0, *") is None


def test_an_empty_range_falls_through_to_the_next_item_not_to_the_default():
    """🔴 「범위가 비었다」와 「기본값을 써라」는 다른 신호다 — 센티널이 필요한 이유.

    `en;q=0, ja;q=0, *;q=0.9, ko;q=0.5` 에서 `*` 의 범위는 비어 있다(셋 다 명시됐다).
    그때 `None` 을 돌려주면 호출부가 기본값 `en` 으로 가는데, **en 은 사용자가 명시적으로
    거부한 언어**다. 다음 항목 `ko;q=0.5` 로 내려가야 한다.

    뮤테이션으로 찾았다 — 이 시험이 없을 때 센티널을 `None` 으로 바꿔도 red 가 0 이었다.
    """
    assert _effective("en;q=0, ja;q=0, *;q=0.9, ko;q=0.5") == "ko"


def test_supported_none_keeps_the_legacy_contract():
    """`supported` 가 None 이면 옛 동작(최고 q 그대로) — 회귀 가드."""
    got = LocaleMiddleware._parse_accept_language(  # noqa: SLF001
        [(b"accept-language", b"zh,ko;q=0.9")], None, None)
    assert got == "zh"
