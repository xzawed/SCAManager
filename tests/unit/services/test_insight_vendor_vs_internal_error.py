"""repo_insight_narrative — 벤더 실패와 **우리 코드 버그**를 다른 status 로 가른다 (#1458).

🔴 왜 이 파일이 있는가 — 운영 실측이 요구했다.

`claude_api_calls` 전수 조회에서 **비-벤더 클래스**가 나왔다:

| error_type | n | input/output tokens | 출처 |
|---|---|---|---|
| `JSONDecodeError` | 3 | 2건이 `693 / 600` | `repo_insight_service` |

`output_tokens=600` 이 핵심이다 — **API 호출은 성공했고 과금까지 됐다.** 그 뒤 우리
파싱이 터졌다. 그런데 기록된 status 는 `api_error` 였다. 즉 「벤더가 실패했다」와
「우리 코드가 버그다」가 같은 라벨을 달았고, 대시보드·집계·알림은 그 라벨을 본다.

🔴 **형제 호출부는 이미 갈라져 있다** — 여기만 안 갈라져 있었다:

- `analyzer/io/ai_review.py:337` — `_parse_response` 가 `json.JSONDecodeError` 를
  자체 포착해 `parse_error` 로 돌린다. 바깥 `except Exception` 까지 안 올라간다.
- `services/dashboard_service.py` — 카드 JSON 파싱이 API try **밖**이라 별도 분기다.
- `services/repo_insight_service.py` — `json.loads` 가 API try **안**이고
  (`R63` 2행 기록 버그를 고치며 의도적으로 넣었다) `except Exception` 하나가 전부를
  `api_error` 로 덮었다. **측정된 3건이 전부 여기서 나왔다.**

즉 #1458 의 처방(`except anthropic.APIError` vs `except Exception`)은 옳았지만
**대상 파일이 틀렸다.** `ai_review` 에 적용하면 무동작이다(파싱이 이미 갈려 있으므로).

🔴 이 분류가 **못 하는 것**: 벤더의 400 이 「우리 요청이 malformed」인지 「계정 지출
한도 도달」인지는 여전히 구분 못 한다 — 둘 다 `anthropic.BadRequestError` 이고 둘 다
`api_error` 가 된다. 그것은 별개 축이고 구조화 판별자가 400 에는 없다(429 는
`error.details.error_code` 가 있다). 여기서 「해결됐다」고 읽지 마라.

Vendor failures and our own bugs shared one status at this call site; the sibling call sites
already split them. Applies #1458's prescription where the measured evidence actually is.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401  side-effect: populate Base.metadata
from src.database import Base
from src.models.insight_narrative_cache import InsightNarrativeCache  # noqa: F401
from src.models.repository import Repository
from src.models.user import User

_KPI = {
    "analysis_count": 2, "avg_score": 60, "grade": "D", "score_delta": None,
    "high_security_count": 0, "top_recurring_issue": None, "top_recurring_count": 0,
}


# ─── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def user(db):
    u = User(github_id=99, github_login="tester", email="t@x.com", display_name="T")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture()
def repo(db, user):
    r = Repository(full_name=f"o/r-{uuid.uuid4().hex[:6]}", user_id=user.id)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


# ─── 헬퍼 ───────────────────────────────────────────────────────────────────


def _text_response(text: str) -> MagicMock:
    """Anthropic 응답 더블 — `first_text_block` 이 읽는 모양만 갖춘다."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    resp.usage = MagicMock(
        input_tokens=693, output_tokens=600,
        cache_read_input_tokens=0, cache_creation_input_tokens=0,
    )
    return resp


def _vendor_error(cls, status_code: int) -> Exception:
    """실제 anthropic SDK 예외 — `RuntimeError` 더블로 벤더 실패를 흉내 내지 않는다.

    🔴 기존 테스트는 `RuntimeError("network down")` 으로 「API 예외」를 흉내 냈다.
    그 더블은 **벤더 실패와 우리 버그의 차이 자체를 지운다** — 진짜 네트워크 실패는
    `anthropic.APIConnectionError` 이고, 그것이 `anthropic.APIError` 하위라는 사실이
    이 분류의 유일한 근거다.
    """
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    if cls is anthropic.APIConnectionError:
        return cls(message="connection failed", request=request)
    response = httpx.Response(
        status_code, request=request,
        json={"error": {"type": "test_error", "message": "test"}},
    )
    return cls("boom", response=response, body=None)


async def _run(db, repo, *, side_effect=None, return_value=None):
    from src.services.repo_insight_service import repo_insight_narrative  # noqa: PLC0415

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(side_effect=side_effect, return_value=return_value)
    with patch("src.services.repo_insight_service.settings") as s, \
         patch("src.services.repo_insight_service.anthropic.AsyncAnthropic",
               return_value=mock_client):
        s.anthropic_api_key = "sk-ant-test"
        s.claude_insight_model = "claude-haiku-4-5"
        return await repo_insight_narrative(db, repo.id, kpi=_KPI, recurring=[])


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_the_split_discriminator_actually_discriminates():
    """🔴 분류 근거가 성립하는지 먼저 잰다 — 성립 안 하면 아래 단언이 전부 공허하다.

    벤더 예외는 전부 `anthropic.APIError` 하위여야 하고, 우리 파싱 실패는
    그 밖이어야 한다. 하나라도 어긋나면 이 파일의 분류학이 무너진다.
    """
    vendor = [
        anthropic.APIConnectionError, anthropic.APITimeoutError,
        anthropic.RateLimitError, anthropic.BadRequestError,
        anthropic.InternalServerError, anthropic.AuthenticationError,
        anthropic.PermissionDeniedError,
    ]
    outside = [json.JSONDecodeError, AttributeError, TypeError, KeyError, ValueError]

    not_vendor = [c.__name__ for c in vendor if not issubclass(c, anthropic.APIError)]
    assert not not_vendor, f"벤더로 분류한 것이 APIError 하위가 아니다: {not_vendor}"

    leaked = [c.__name__ for c in outside if issubclass(c, anthropic.APIError)]
    assert not leaked, f"우리 쪽 예외가 APIError 하위다 — 분류 불가: {leaked}"


# ─── 우리 코드 버그 → internal_error ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_unparsable_model_output_is_internal_error_not_api_error(db, repo):
    """🔴 측정된 결함 그 자체 — 모델이 응답했는데 우리 `json.loads` 가 터진다.

    운영 3건이 이 경로다(`output_tokens=600`, 즉 과금 완료). 확대 전에는 `api_error`
    라서 「벤더 탓」으로 보였고, 우리 파서 버그가 벤더 장애 통계에 섞였다.
    """
    result = await _run(db, repo, return_value=_text_response("이건 JSON 이 아니다 {{{"))

    assert result["status"] == "internal_error", (
        f"파싱 실패가 아직 벤더 실패로 분류된다: {result['status']!r}"
    )


@pytest.mark.asyncio
async def test_valid_json_but_not_a_dict_is_internal_error(db, repo):
    """유효 JSON 이지만 dict 가 아니면 `data.get` 이 터진다 — 이것도 우리 쪽이다.

    소스 주석(R63 2차 수정)이 명시한 경로다: `"문자열"` · `[1,2]` 가 `data.get` 에서
    `AttributeError` 를 낸다.
    """
    result = await _run(db, repo, return_value=_text_response('["배열은 dict 가 아니다"]'))

    assert result["status"] == "internal_error", (
        f"비-dict 페이로드가 벤더 실패로 분류된다: {result['status']!r}"
    )


# ─── 벤더 실패 → api_error (대조군) ──────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("cls,code", [
    (anthropic.APIConnectionError, 0),
    (anthropic.APITimeoutError, 0),
    (anthropic.RateLimitError, 429),
    (anthropic.BadRequestError, 400),
    (anthropic.InternalServerError, 500),
    (anthropic.AuthenticationError, 401),
])
async def test_real_sdk_exceptions_stay_api_error(db, repo, cls, code):
    """🔴 대조군 — 진짜 벤더 예외는 여전히 `api_error` 다.

    분류가 한쪽으로 쏠려 **모든 것이 internal_error** 가 되면 이 PR 은 라벨만 바꾼
    셈이다. 벤더 축이 살아 있는지 클래스마다 확인한다.
    """
    if cls is anthropic.APITimeoutError:
        exc = cls(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    else:
        exc = _vendor_error(cls, code)

    result = await _run(db, repo, side_effect=exc)

    assert result["status"] == "api_error", (
        f"{cls.__name__} 이 벤더 실패로 분류되지 않았다: {result['status']!r}"
    )


# ─── 성공 경로는 그대로 ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_success_path_is_unchanged(db, repo):
    """정상 JSON 은 여전히 `success` — 분류 변경이 성공 경로를 건드리지 않는다."""
    result = await _run(db, repo, return_value=_text_response('{"text": "좋은 리포다"}'))

    assert result["status"] == "success"
    assert result["text"] == "좋은 리포다"


@pytest.mark.asyncio
async def test_non_sdk_exception_from_the_call_itself_is_internal_error(db, repo):
    """🔴 Grok Q1 공백 — 호출 자체가 **SDK 밖 예외**를 내면 `internal_error` 다.

    위 두 테스트는 파싱 단계만 덮는다. 판정은 「어느 단계인가」가 아니라 「`anthropic.
    APIError` 하위인가」이므로, `messages.create` 가 `RuntimeError` 를 내는 경우도
    우리 쪽으로 분류돼야 한다 — 이 축을 고정하지 않으면 판정식을
    `단계 기준`으로 바꿔도 테스트가 안 잡는다.

    이것이 옛 테스트가 `RuntimeError("network down")` 으로 **벤더 실패를 흉내 내며**
    `api_error` 를 단언하던 자리다. 그 더블은 검사 대상인 구분 자체를 지웠다.
    """
    result = await _run(db, repo, side_effect=RuntimeError("우리 코드가 낸 오류"))

    assert result["status"] == "internal_error", (
        f"SDK 밖 예외가 벤더 실패로 분류된다: {result['status']!r}"
    )


@pytest.mark.asyncio
async def test_bare_anthropic_error_is_not_treated_as_vendor(db, repo):
    """경계 — SDK 루트 `AnthropicError` 는 `APIError` 하위가 **아니다**.

    `AnthropicError` 는 「SDK 가 낸 오류」일 뿐 벤더 HTTP 응답을 뜻하지 않는다.
    판정식이 `anthropic.AnthropicError` 로 넓어지면 우리 쪽 오류가 벤더로 위장한다.
    """
    assert not issubclass(anthropic.AnthropicError, anthropic.APIError), (
        "AnthropicError 가 APIError 하위가 됐다 — 판정 경계를 재검토하라"
    )

    result = await _run(db, repo, side_effect=anthropic.AnthropicError("SDK 내부 오류"))

    assert result["status"] == "internal_error", (
        f"루트 AnthropicError 가 벤더로 분류된다: {result['status']!r}"
    )
