"""벤더 오류의 **구조화 필드**를 남긴다 — 계정 상태와 우리 요청을 가르기 위해 (#1506).

🔴 왜 필요한가 — 5일 100% 장애를 클래스명만으로는 진단할 수 없었다.

2026-08-20~25 에 AI 리뷰가 44건 연속 실패했다. 기록된 것은 전부
`error_type='BadRequestError'` / `status_code=400` 이었다. 그 이름은 「우리 요청이
malformed」를 가리키고, 나는 그 축(모델 ID·SDK 버전·스키마·max_tokens)만 5일 팠다.
전부 반증됐다. 실제 원인은 **조직 지출 한도 도달** — 벤더 장애도 우리 버그도 아닌
**계정 상태**였고, 사용자가 콘솔에서 조치해야 풀리는 종류였다.

🔴 **무엇이 그것을 갈랐을 수 있었나 — 실측** (anthropic 1.0.0, 공식 문서 페이로드 재현):

| 케이스 | HTTP | vendor type | error_code | retry-after | 구분 |
|---|---|---|---|---|---|
| 티어 월 상한 | 429 | `rate_limit_error` | **`enforced_spend_limit_reached`** | 없음 | ✅ |
| 일반 rate limit | 429 | `rate_limit_error` | 없음 | **있음** | ✅ |
| 내가 설정한 한도 | 400 | `invalid_request_error` | 없음 | 없음 | ❌ |
| malformed 요청 | 400 | `invalid_request_error` | 없음 | 없음 | ❌ |

즉 **429 축은 구조화 신호로 완전히 갈리고, 400 축은 원리적으로 안 갈린다**
(공식 문서상 400 에는 `error_code` 가 없고 메시지 접두사뿐이다). 그래서 400 은
`request_id` 를 남겨 사람이 Anthropic 에 추적할 수 있게 한다.

🔴 **메시지는 담지 않는다.** `ai_review.py` 의 규칙 그대로다 — anthropic 오류 본문은
요청 내용을 되비추므로 diff 조각이 `analyses.result` 로 새고 그 JSON 은 대시보드와
알림으로 흐른다. 여기 담는 네 값은 전부 **요청 내용을 담을 수 없는 형태**다:
고정 어휘 2개(`type`·`error_code`), 불투명 ID 1개(`request_id`), 숫자 1개(`retry-after`).

🔴 **이 파일은 status 값을 바꾸지 않는다.** `account_error` 같은 새 status 는 소비자
6곳(`gate/_common.py` · `scorer/reliability.py` · `notifier/score_warnings.py` ·
`notifier/_common.py` · `api/hook.py` · `templates/analysis_detail.html`)에 걸리고
그중 하나는 i18n 배너라 사람이 눈으로 봐야 한다. 관측이 먼저다 — 데이터가 쌓인 뒤에
분류를 정한다(#1458 이 그 순서를 지켜 옳았던 선례).

Records the vendor's structured error fields (fixed vocabulary + opaque id only, never the
message) so an account-state failure is distinguishable from a malformed request. Does not
change any status value — observability first.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")

from unittest.mock import AsyncMock, patch

import anthropic
import httpx
import pytest

from src.analyzer.io.ai_review import review_code

_REQ = "https://api.anthropic.com/v1/messages"


def _vendor_error(cls, code, body, headers=None):
    """공식 문서의 오류 페이로드를 그대로 재현한 SDK 예외."""
    request = httpx.Request("POST", _REQ)
    response = httpx.Response(
        code, request=request, json=body,
        headers={**(headers or {}), "request-id": body.get("request_id", "req_probe")},
    )
    return cls("boom", response=response, body=body)


_TIER_CAP = _vendor_error(
    anthropic.RateLimitError, 429,
    {"type": "error",
     "error": {"type": "rate_limit_error",
               "message": "You have reached your API usage limits: ...",
               "details": {"error_code": "enforced_spend_limit_reached"}},
     "request_id": "req_tiercap"},
)
_RATE_LIMIT = _vendor_error(
    anthropic.RateLimitError, 429,
    {"type": "error", "error": {"type": "rate_limit_error", "message": "slow down"},
     "request_id": "req_rate"},
    headers={"retry-after": "30"},
)
_OWN_LIMIT = _vendor_error(
    anthropic.BadRequestError, 400,
    {"type": "error",
     "error": {"type": "invalid_request_error",
               "message": "You have reached your specified API usage limits. ..."},
     "request_id": "req_ownlimit"},
)


async def _run(exc):
    """review_code 를 한 번 돌려 결과를 받는다 — 호출은 주어진 예외로 실패시킨다."""
    client = AsyncMock()
    client.messages.create = AsyncMock(side_effect=exc)
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=client), \
         patch("src.analyzer.io.ai_review.log_claude_api_call"), \
         patch("src.analyzer.io.ai_review.aclose_anthropic_client", AsyncMock()):
        return await review_code("sk-ant-test", "feat: x", [("x.py", "+x = 1")])


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_the_probe_payloads_match_the_documented_shape():
    """🔴 재현한 페이로드가 문서와 같은 모양인지 먼저 잰다.

    모양이 틀리면 아래 단언이 **내가 만든 허구**를 검사하는 것이 된다.
    """
    body = _TIER_CAP.body
    assert body["error"]["details"]["error_code"] == "enforced_spend_limit_reached"
    assert _TIER_CAP.response.headers.get("retry-after") is None, (
        "티어 상한 429 는 retry-after 가 없어야 한다 (문서 명시)"
    )
    assert _RATE_LIMIT.response.headers.get("retry-after") == "30", (
        "일반 rate limit 429 는 retry-after 를 준다 (문서 명시)"
    )
    assert _OWN_LIMIT.status_code == 400
    assert (_OWN_LIMIT.body or {})["error"]["type"] == "invalid_request_error"


# ─── 429 축 — 구조화 신호로 갈린다 ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_tier_spend_cap_records_its_error_code():
    """🔴 티어 월 상한은 `error_code` 로 **일반 rate limit 과 갈린다**.

    문서: "On the Messages API, `error.details.error_code` is
    `enforced_spend_limit_reached`. Use it to tell this response apart from a rate limit."
    """
    result = await _run(_TIER_CAP)

    assert result.error_code == "enforced_spend_limit_reached", (
        f"티어 상한 신호를 못 남겼다 — 일반 rate limit 과 구분 불가: {result.error_code!r}"
    )
    assert result.error_vendor_type == "rate_limit_error"
    assert result.error_request_id == "req_tiercap"


@pytest.mark.asyncio
async def test_plain_rate_limit_records_retry_after_and_no_error_code():
    """대조군 — 일반 rate limit 은 `error_code` 가 없고 `retry-after` 가 있다.

    이 축이 없으면 위 테스트가 「모든 429 에 error_code 가 있다」로도 통과한다.
    """
    result = await _run(_RATE_LIMIT)

    assert result.error_code is None, "일반 rate limit 에 상한 신호가 붙었다"
    assert result.error_retry_after == "30"


# ─── 400 축 — 갈리지 않는다는 사실 자체를 고정한다 ────────────────────────────


@pytest.mark.asyncio
async def test_own_spend_limit_400_is_not_structurally_distinguishable():
    """🔴 400 은 구조화 신호가 **없다** — 그 한계를 고정한다.

    「내가 설정한 한도」와 「malformed 요청」이 둘 다
    `invalid_request_error` / `error_code=None` / `retry-after=None` 이다.
    남는 것은 `request_id` 뿐이고, 그것이 사람이 Anthropic 에 추적할 유일한 실마리다.
    이 테스트가 red 가 되면 벤더가 400 에 구조화 신호를 추가한 것이니 분류를 다시 짜라.
    """
    result = await _run(_OWN_LIMIT)

    assert result.error_vendor_type == "invalid_request_error"
    assert result.error_code is None, (
        "400 에 error_code 가 생겼다 — 벤더가 신호를 추가했다면 400 축도 자동 분류가 "
        "가능해진다. #1506 의 설계를 다시 판단하라"
    )
    assert result.error_request_id == "req_ownlimit", (
        "request_id 마저 없으면 400 실패는 추적 불가능해진다"
    )


# ─── 담지 않는 것 ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_vendor_message_is_never_stored():
    """🔴 메시지는 **어느 필드에도** 담기지 않는다 — 요청 내용 에코 위험.

    anthropic 오류 본문은 요청을 되비춘다. 여기 담는 값이 전부 고정 어휘·불투명 ID·
    숫자인지 확인한다 — 하나라도 자유 텍스트면 diff 조각이 `analyses.result` 로 새고
    대시보드·알림까지 흐른다.
    """
    leak = "SECRET_DIFF_FRAGMENT_xyz"
    exc = _vendor_error(
        anthropic.BadRequestError, 400,
        {"type": "error",
         "error": {"type": "invalid_request_error",
                   "message": f"messages.0.content: {leak}"},
         "request_id": "req_leak"},
    )
    result = await _run(exc)

    captured = (
        result.error_type, result.error_status_code, result.error_vendor_type,
        result.error_code, result.error_request_id, result.error_retry_after,
    )
    for value in captured:
        assert leak not in str(value), (
            f"벤더 메시지가 필드로 새어 들어왔다 — 요청 내용 에코: {value!r}"
        )


@pytest.mark.asyncio
async def test_success_path_leaves_the_fields_empty():
    """성공 경로에서는 네 값이 전부 None — 실패 표식이 남지 않는다."""
    from unittest.mock import MagicMock  # noqa: PLC0415

    block = MagicMock()
    block.type = "text"
    block.text = '{"total_score": 80, "summary": "ok"}'
    response = MagicMock()
    response.content = [block]
    response.usage = MagicMock(
        input_tokens=10, output_tokens=5,
        cache_read_input_tokens=0, cache_creation_input_tokens=0,
    )
    client = AsyncMock()
    client.messages.create = AsyncMock(return_value=response)
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=client), \
         patch("src.analyzer.io.ai_review.log_claude_api_call"), \
         patch("src.analyzer.io.ai_review.aclose_anthropic_client", AsyncMock()):
        result = await review_code("sk-ant-test", "feat: x", [("x.py", "+x = 1")])

    assert result.error_vendor_type is None
    assert result.error_code is None
    assert result.error_request_id is None
    assert result.error_retry_after is None


# ─── 배선 — 값이 result dict 까지 실제로 흐르는가 ────────────────────────────


def test_pipeline_projects_the_vendor_fields_into_the_result_dict():
    """🔴 정의 ≠ 배선 — 필드를 만들어도 `analyses.result` 로 안 흐르면 무의미하다.

    이 값들의 목적은 **운영 DB 에서 SQL 로 읽는 것**이다. 파이프라인의 result 투영이
    키를 안 내면 사고 때 또 로그를 뒤져야 한다. 그 배선을 여기서 고정한다.

    🔴 실패 경로에서만 키를 내면 안 된다 — `ai_review_error_type` 이 이미
    「성공에서도 키를 낸다(값 None)」로 돼 있고, 그 이유는 「키 없음」이
    "실패가 아니었다" 와 "이 필드 이전의 낡은 행이다" 두 가지를 뜻하지 않게 하기
    위해서다(`pipeline.py` 주석). 같은 규율을 따른다.
    """
    import ast  # noqa: PLC0415
    import pathlib  # noqa: PLC0415

    root = pathlib.Path(__file__).resolve().parents[4]
    src = (root / "src" / "worker" / "pipeline.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    # result dict 로 투영되는 문자열 키를 AST 로 모은다 (문자열 탐색이 아니라 구조)
    keys = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and node.value.startswith("ai_review_error")
    }
    expected = {
        "ai_review_error_type",
        "ai_review_error_status_code",
        "ai_review_error_vendor_type",
        "ai_review_error_code",
        "ai_review_error_request_id",
        "ai_review_error_retry_after",
    }
    missing = expected - keys
    assert not missing, (
        f"pipeline 이 result dict 로 안 내보내는 벤더 오류 키: {sorted(missing)} — "
        "필드를 정의만 하고 배선을 빠뜨리면 운영 DB 에서 읽을 수 없다"
    )


@pytest.mark.asyncio
async def test_absurdly_long_vendor_values_are_bounded():
    """🔴 길이 상한 — 이 값들은 대시보드·알림으로 흐른다 (Grok 지적).

    실측상 벤더의 `type`·`error_code` 는 고정 어휘, `request_id` 는 `req_…` 형태,
    `retry-after` 는 초 단위 숫자다. 그래서 **지금은** 안전하다. 다만 이 코드에는
    allowlist 도 형식 검사도 없어, 벤더가 그 키에 긴 문자열을 넣거나 중간자가 응답을
    바꾸면 그대로 저장돼 `analyses.result` 를 타고 UI 까지 간다.

    「지금 안전하다」는 관측이지 계약이 아니다 — 상한을 계약으로 만든다.
    Bounded length: measured vendor values are short fixed tokens, but nothing in the code
    enforces that, and these values reach dashboards and notifications.
    """
    huge = "A" * 5000
    exc = _vendor_error(
        anthropic.BadRequestError, 400,
        {"type": "error",
         "error": {"type": huge, "message": "x", "details": {"error_code": huge}},
         "request_id": huge},
        headers={"retry-after": huge},
    )
    result = await _run(exc)

    for name in (
        "error_vendor_type", "error_code", "error_request_id", "error_retry_after",
    ):
        value = getattr(result, name)
        assert value is None or len(value) <= 200, (
            f"{name} 이 상한 없이 저장된다 — {len(value)}자. "
            "이 값은 analyses.result 를 타고 대시보드·알림으로 흐른다"
        )
