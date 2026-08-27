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


# ─── q=0 은 「수용 불가」다 (#1536 ①축) ──────────────────────────────────────
#
# 선택 루프가 q 로 **정렬만** 하고 가중치를 다시 보지 않았다(`for lang, _weight in items`).
# q=0 은 최저 가중치라 **정렬이 대부분 가려준다** — 다른 후보가 하나라도 있으면 뒤로
# 밀린다. 실제로 물리는 자리는 셋뿐이고, 아래 세 테스트가 각각 하나씩이다.


def test_a_rejected_language_alone_is_not_selected(middleware):
    """🔴 `q=0` 은 RFC 7231 §5.3.1 에서 **수용 불가**다 — 그것을 고르면 안 된다.

    단독이라 정렬이 가려주지 못하는 자리다. #1519 C1(#1535) 의 Grok 적대 검토에서
    나왔고, 그 변경이 만든 것이 **아니라** 그 전부터 있던 결함이다.
    """
    assert _detect(middleware, "ko;q=0") == settings.default_locale, (
        "q=0 으로 거부한 언어를 골랐다"
    )


def test_rejected_languages_tied_at_zero_do_not_win_by_input_order(middleware):
    """🔴 0끼리 동률이면 **안정 정렬이 입력 순서를 그대로 유지**한다.

    가중치를 안 보므로 맨 앞의 거부된 언어가 그대로 뽑힌다. 기본값을 **맨 뒤**에 두어
    「우연히 기본값이 나와서 초록」이 되지 않게 한다 — 앞자리를 차지하는 언어가
    무엇인지는 지원 집합에서 파생하고, 손으로 적지 않는다.
    """
    others = sorted(middleware._supported - {settings.default_locale})  # noqa: SLF001
    header = ",".join(f"{lang};q=0" for lang in [*others, settings.default_locale])
    assert others, "지원 언어가 기본값 하나뿐이면 이 테스트는 공허하다"
    assert _detect(middleware, header) == settings.default_locale, (
        f"전부 거부됐는데 거부된 언어를 골랐다 — 헤더 앞자리는 {others[0]} 다: {header}"
    )


def test_a_rejected_language_is_not_selected_without_a_supported_set():
    """🔴 `supported=None`(구 경로) 에서도 q=0 은 고르면 안 된다.

    「수용 불가」는 지원 목록과 무관한 **클라이언트의 명시적 거부**다. 그 판정을
    선택 루프에 두면 이 경로는 위쪽 `return items[0][0]` 으로 빠져나가 눈이 먼다.
    """
    parsed = LocaleMiddleware._parse_accept_language(  # noqa: SLF001
        [(b"accept-language", b"ko;q=0")], None)
    assert parsed is None, f"supported=None 경로가 거부된 언어를 골랐다: {parsed}"


# ─── 「깨진 q」는 거부가 아니다 ──────────────────────────────────────────────
#
# 🔴 이 절이 이 PR 의 첫 시도를 반증했다(Grok 01a041e9). 처음엔 파싱 결과에
# `weight > 0` 필터 한 줄을 걸었는데, `_parse_q_weight` 가 **파싱 실패에도 `0.0`** 을
# 돌려주고 있었다. 두 뜻이 한 값에 겹쳐 있어서, 그 필터는 거부하지 않은 언어까지 버렸다:
#
#     "ko;q=abc"  ->  기본값   🔴  클라이언트는 ko 를 거부한 적이 없다
#
# 그래서 판정을 파서 안으로 옮겼다 — 실패는 `None`, 거부는 항목 미생성.


@pytest.mark.parametrize("broken", ["q=abc", "q=", "q=-1", "q=nan", "q=1.5", "q=inf"])
def test_an_unparseable_weight_is_not_a_rejection(middleware, broken):
    """🔴 깨진 q 를 「거부」로 읽으면 클라이언트가 요청한 언어가 사라진다."""
    assert _detect(middleware, f"ko;{broken}") == "ko", (
        f"깨진 q 를 거부로 읽었다: ko;{broken}"
    )


@pytest.mark.parametrize("bogus", ["q=1.5", "q=inf", "q=99"])
def test_an_out_of_range_weight_does_not_outrank_a_valid_one(middleware, bogus):
    """🔴 범위 밖 q 는 유효한 `q=1` 을 이기면 안 된다.

    `float()` 은 `inf` 도 받는다. 그대로 두면 어떤 정렬도 이기므로, 깨진 헤더 하나가
    협상을 통째로 장악한다.
    """
    assert _detect(middleware, f"ko;{bogus},en;q=1") == "en", (
        f"범위 밖 q 가 유효한 q=1 을 이겼다: ko;{bogus}"
    )


def test_the_q_weight_parse_contract():
    """파싱 계약을 한자리에서 못 박는다 — `None` = 실패, `0.0` = 클라이언트가 쓴 진짜 0."""
    parse = LocaleMiddleware._parse_q_weight  # noqa: SLF001
    assert parse("q=0") == 0.0, "진짜 0 이 실패로 읽히면 거부가 무시된다"
    assert parse("q=0.000") == 0.0
    assert parse("q=1") == 1.0
    assert parse("q=0.001") == 0.001
    assert parse("lang") == 1.0, "q= 가 없으면 RFC 기본값 1"
    assert parse("Q=0") == 0.0, "파라미터명은 대소문자 무시 — Q=0 도 진짜 0 이다"
    assert parse("Q=0.5") == 0.5
    assert parse("q=0.") == 0.0, "ABNF 는 소수점 뒤 0자리를 허용한다"
    assert parse("q=0.50") == 0.5
    assert parse("q=1.000") == 1.0
    for broken in ("q=abc", "q=", "q=-1", "q=nan", "q=inf", "q=1.5", "q=99", "q=2",
                   "q=1.001", "q=1e-400", "q=0e0", "q=1E5", "q=+0", "q=00", "q=.0",
                   "q=-0", "q=0.0000", "q=\u0660"):
        assert parse(broken) is None, f"{broken} 이 실패로 읽히지 않았다"


@pytest.mark.parametrize("weight", ["Q=0", "Q=0.000", "q=0"])
def test_the_weight_parameter_name_is_case_insensitive(middleware, weight):
    """🔴 RFC 7231 의 `q` 는 대소문자를 가리지 않는다 — `Q=0` 도 거부다.

    소문자만 보면 `Q=` 는 가중치로 **인식조차 되지 않아** 기본값 1.0 이 남는다.
    거부한 언어가 최우선으로 뽑히는, 이 PR 이 닫으려는 바로 그 자리다.
    """
    assert _detect(middleware, f"ko;{weight}") == settings.default_locale, (
        f"거부를 대소문자 때문에 놓쳤다: ko;{weight}"
    )


def test_an_uppercase_weight_is_still_read_as_a_weight(middleware):
    """`Q=` 를 인식한다는 것은 그 **값**도 쓴다는 뜻이다 — 무시하면 q=1 로 남는다."""
    assert _detect(middleware, "ko;Q=0.1,en;q=0.9") == "en"


_NOT_A_QVALUE_ZERO = ["q=+0", "q=00", "q=.0", "q=-0", "q=0e0", "q=1e-400", "q=\u0660",
                      "q=0.0000"]


def test_the_zero_forms_really_do_float_to_zero():
    """🔴 전제 — 아래 형식들이 실제로 `float()` 에서 0.0 이 되는지 먼저 잰다.

    되지 않는다면 다음 테스트는 **다른 이유로** 초록이고, 아무것도 지키지 못한다.
    """
    for raw in _NOT_A_QVALUE_ZERO:
        assert float(raw[2:].replace("\u0660", "0")) == 0.0, (
            f"{raw} 가 0.0 이 아니다 — 다음 테스트가 공허해진다"
        )


@pytest.mark.parametrize("zeroish", _NOT_A_QVALUE_ZERO)
def test_a_zero_that_is_not_an_rfc_qvalue_is_not_a_rejection(middleware, zeroish):
    """🔴 `float()` 이 0.0 을 준다고 클라이언트가 0 을 쓴 것은 아니다.

    RFC 7231 §5.3.1 의 qvalue 는 `0[.0~3자리]` 또는 `1[.0~3자리]` 뿐이다. 부호·선행 0·
    선행 소수점·지수 표기·유니코드 숫자는 전부 그 문법 밖이고, 거부로 읽으면
    클라이언트가 거부한 적 없는 언어가 사라진다.

    이 목록은 Grok(01a0420c)이 `"e" in raw` 열거의 맹점을 반증하며 준 것이다 —
    나는 지수 표기 하나만 막고 같은 부류의 나머지를 놓쳤다.
    """
    assert _detect(middleware, f"ko;{zeroish}") == "ko", (
        f"qvalue 가 아닌 0 을 거부로 읽었다: ko;{zeroish}"
    )


def test_a_real_zero_in_every_grammatical_form_is_a_rejection(middleware):
    """반대쪽 — 문법에 맞는 0 은 **전부** 거부다. 한쪽만 넓히면 다른 쪽이 눈먼다."""
    for real_zero in ("q=0", "q=0.", "q=0.0", "q=0.00", "q=0.000", "Q=0"):
        assert _detect(middleware, f"ko;{real_zero}") == settings.default_locale, (
            f"문법에 맞는 0 을 거부로 읽지 않았다: ko;{real_zero}"
        )


# ─── 대조군 — 이미 초록이다. 수정이 이것들을 깨지 않는지만 본다 ──────────────


def test_a_rejected_language_still_falls_through_to_the_next_one(middleware):
    """거부된 언어는 **건너뛰고** 다음 수용 가능한 것을 본다 — 헤더를 통째로 버리지 않는다."""
    assert _detect(middleware, "ko;q=0,ja;q=0.5") == "ja"
    assert _detect(middleware, "ja;q=0,ko;q=0.3") == "ko"


def test_a_tiny_positive_weight_is_still_acceptable(middleware):
    """0 과 「아주 작은 양수」는 다르다 — `q=0.001` 은 여전히 수용 가능하다."""
    assert _detect(middleware, "ko;q=0.001") == "ko"


def test_an_absent_weight_still_defaults_to_one(middleware):
    """가중치 생략은 q=1 이다 — 거부 판정이 그것까지 걸러내면 협상이 통째로 죽는다."""
    assert _detect(middleware, "ko") == "ko"
    assert _detect(middleware, "ko,en;q=0.9") == "ko"
