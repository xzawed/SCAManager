"""anthropic SDK 재시도 대기에 Retry-After 상한을 둔다 (#1690).

anthropic 1.6.0 부터 SDK 는 `retry-after` 를 상한 없이 따른다(`min(ra, 4_294_967)`) — 이 대기는
`timeout=` 이 묶지 않는다. 여기 테스트는 `AsyncAnthropic` 을 더블로 바꾸지 않고 **실제 SDK
재시도 루프**를 돌린다: 전송만 `httpx2.MockTransport`, 대기만 `anyio.sleep` 기록으로 바꾼다.
세 호출부(`review_code` · `insight_narrative` · `repo_insight_narrative`)를 그대로 부른다.

상한은 호출부마다 다르다 — 파이프라인 60s(1.5.0 의 판정값), 페이지 두 곳 15s. 기대값은
**상수에서 뽑지 않은 리터럴**이다(상수가 바뀌면 여기가 red 가 되어야 한다).

Drives the REAL SDK retry loop (transport and sleep faked only) through the three call sites.
Expected caps are literals, not derived from the constants.
"""
from __future__ import annotations

import ast
import asyncio
import email.utils
import logging
import pathlib
import subprocess
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import anthropic
import anthropic._base_client as _sdk_base
import anthropic._constants as _sdk_constants
import httpx2
import pytest
from sqlalchemy.orm import Session

from src.analyzer.io.ai_review import review_code
from src.config import settings
from src.services import dashboard_service, repo_insight_service
from src.services.repo_insight_service import repo_insight_narrative
from src.shared import claude_metrics
from src.shared.claude_metrics import _sdk_will_retry

_REAL_CTOR = anthropic.AsyncAnthropic
# SDK 자체 backoff 의 범위 — 최댓값 MAX_RETRY_DELAY 8.0, 첫 대기 하한 = INITIAL_RETRY_DELAY 0.5 × 최소 지터 0.75.
#   (anthropic/_constants.py · `_calculate_retry_timeout`: `min(0.5 * 2**n, 8.0) * (1 - 0.25 * random())`)
#   하한이 없으면 `retry-after-ms: "1"`(1ms 대기)도 「backoff」로 통과한다.
# The SDK's own backoff range: at most 8.0, at least 0.5 x 0.75 = 0.375 (first retry, min jitter).
# Without the floor a 1 ms honoured wait would pass as "backoff".
_BACKOFF_MIN = 0.375
_BACKOFF_MAX = 8.0

_SITES = ["ai_review", "dashboard_insight", "repo_insight"]
# 호출부별 시도 수(max_retries + 1)와 상한 리터럴 / attempts and literal cap per site
_ATTEMPTS = {"ai_review": 2, "dashboard_insight": 3, "repo_insight": 3}
_CAP = {"ai_review": "60", "dashboard_insight": "15", "repo_insight": "15"}
_JUST_ABOVE = {"ai_review": "61", "dashboard_insight": "16", "repo_insight": "16"}

_OK_TEXT = (
    '{"text": "ok", "positive_highlights": [], "focus_areas": [], '
    '"key_metrics": [], "next_actions": []}'
)
_OK_BODY = {
    "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-test",
    "content": [{"type": "text", "text": _OK_TEXT}],
    "stop_reason": "end_turn", "stop_sequence": None,
    "usage": {"input_tokens": 1, "output_tokens": 1},
}
_ERR_BODY = {"type": "error", "error": {"type": "rate_limit_error", "message": "slow down"}}


@pytest.fixture
def real_sdk(monkeypatch):
    """실제 SDK 재시도 루프 — 전송은 MockTransport, 대기는 기록만 / real loop; transport + sleep faked."""
    h = SimpleNamespace(script=[], calls=0, sleeps=[], responses=[])

    def handler(_req):
        i = h.calls
        h.calls += 1
        status, headers = h.script[min(i, len(h.script) - 1)]
        body = _OK_BODY if status == 200 else _ERR_BODY
        resp = httpx2.Response(status, json=body, headers={"request-id": f"req_{i}", **headers})
        # 미들웨어는 이 객체의 헤더를 제자리에서 고친다 — 위조 여부를 여기서 잰다.
        # The middleware edits this very object's headers in place; forged headers show up here.
        h.responses.append(resp)
        return resp

    async def fake_sleep(seconds, *_a, **_k):
        h.sleeps.append(seconds)

    def ctor(*args, **kwargs):
        # 생성마다 새 전송 클라이언트 — 공유하면 첫 호출부의 aclose 가 다음 호출부의 전송을 닫아
        # 전송 0회 APIConnectionError 가 난다(두 호출부를 잇달아 부르는 테스트가 공허 초록이 된다).
        # A fresh transport client per construction: a shared one is closed by the first site's aclose.
        return _REAL_CTOR(*args, base_url="http://anthropic.test",
                          http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
                          **kwargs)

    monkeypatch.setattr(_sdk_base.anyio, "sleep", fake_sleep)
    # 전역 속성을 바꾼다 — 호출부가 어떤 경로로 생성하든 이 전송을 탄다.
    # Patch the global attribute so every construction path uses this transport.
    monkeypatch.setattr(anthropic, "AsyncAnthropic", ctor)
    # 조기 반환을 모두 끈다 — 킬스위치·키 부재(.env 키가 새지 않게 명시 설정).
    # Defeat every early return; set the key explicitly so a developer .env key never leaks in.
    monkeypatch.delenv("AI_REVIEW_DISABLED", raising=False)
    monkeypatch.delenv("INSIGHT_DISABLED", raising=False)
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    return h


async def _run_ai_review():
    return await review_code("sk-test", "feat: x", [("a.py", "+ x = 1")])


async def _run_dashboard():
    # user_id=None → 캐시 조회를 타지 않는다. KPI 헬퍼는 데이터가 있다고 답한다(no_data 조기 반환 차단).
    # 세션은 바인드 없는 빈 `Session` — 호출 전 커밋(#1697)이 미완료 쓰기 가드를 실제 집합으로 읽는다.
    # user_id=None skips the cache; KPI helpers report data so the no_data early return is defeated.
    # An unbound empty Session: the pre-await commit (#1697) reads real pending-write sets.
    with patch.object(dashboard_service, "dashboard_kpi", return_value={"analysis_count": {"value": 3}}), \
         patch.object(dashboard_service, "dashboard_trend", return_value={}), \
         patch.object(dashboard_service, "frequent_issues_v2", return_value=[]), \
         patch.object(dashboard_service, "auto_merge_kpi", return_value={}), \
         patch.object(dashboard_service, "_build_insight_user_prompt", return_value="prompt"):
        return await dashboard_service.insight_narrative(Session(), 7, api_key="sk-test", user_id=None)


async def _run_repo_insight():
    return await repo_insight_narrative(
        Session(), 1, 30, repo_full_name="o/r", kpi={"analysis_count": 3}, recurring=[], user_id=None,
    )


_RUN = {"ai_review": _run_ai_review, "dashboard_insight": _run_dashboard, "repo_insight": _run_repo_insight}


def _status(site, out):
    return out.status if site == "ai_review" else out["status"]


def _assert_backoff(sleeps, n=1):
    """대기 n 번이 전부 SDK backoff 범위 [0.375, 8.0] 안 / every one of n sleeps is SDK backoff."""
    assert len(sleeps) == n and all(_BACKOFF_MIN <= s <= _BACKOFF_MAX for s in sleeps), sleeps


async def _bounded(coro):
    """가짜 sleep 이 가로채지 못하면 5초 안에 red / red within 5s if the fake sleep stops intercepting."""
    return await asyncio.wait_for(coro, 5)


def _raised(caplog, logger_name):
    """호출부가 삼킨 벤더 예외 — `logger.exception` 기록의 exc_info 에서 꺼낸다.
    The vendor exception the call site swallowed, recovered from its logger.exception record.
    """
    recs = [r for r in caplog.records if r.name == logger_name and r.exc_info]
    assert len(recs) == 1, f"{logger_name} 예외 기록 {len(recs)}건 — 1건이어야 한다"
    return recs[0].exc_info[1]


def _cap_warnings(caplog):
    return [r for r in caplog.records
            if r.name == "src.shared.claude_metrics" and r.levelno == logging.WARNING
            and "Retry-After" in r.getMessage()]


# ── 호출부별: 상한 초과는 backoff, 상한 이하는 그대로 / per site: over cap → backoff, at cap → honoured ──

@pytest.mark.parametrize("site", _SITES)
async def test_call_site_does_not_sleep_past_cap(real_sdk, site):
    """🔴 429 + `retry-after: 120` — 수정 전 실측 [120.0] / [120.0, 120.0] (페이지 최대 240s 정지)."""
    real_sdk.script[:] = [(429, {"retry-after": "120"})]
    out = await _bounded(_RUN[site]())

    assert real_sdk.calls == _ATTEMPTS[site], "재시도 횟수가 바뀌었다 — 상한은 재시도를 없애지 않는다"
    assert real_sdk.sleeps, "대기가 한 번도 없었다 — 재시도 루프를 안 탔다(공허 초록)"
    _assert_backoff(real_sdk.sleeps, _ATTEMPTS[site] - 1)
    assert _status(site, out) == "api_error"
    if site == "ai_review":
        # 벤더 증거는 원문 그대로 — retry-after 는 절대 바꾸지 않는다.
        # Vendor evidence stays verbatim: retry-after itself is never rewritten.
        assert (out.error_status_code, out.error_type, out.error_retry_after) == (429, "RateLimitError", "120")


@pytest.mark.parametrize("site", _SITES)
async def test_retry_after_at_site_cap_is_honoured_exactly(real_sdk, site):
    """상한과 같은 값은 그대로 따른다 — 과잉 교정(재시도 제거·헤더 삭제)을 막는 반대 방향."""
    real_sdk.script[:] = [(429, {"retry-after": _CAP[site]}), (200, {})]
    await _bounded(_RUN[site]())

    assert real_sdk.sleeps == [float(_CAP[site])]
    assert real_sdk.calls == 2


@pytest.mark.parametrize("site", _SITES)
async def test_retry_after_just_above_site_cap_uses_backoff(real_sdk, site):
    """상한 바로 위(ai_review 61 · 페이지 16)는 SDK backoff 로 간다 — 호출부별 상한이 실제로 다르다."""
    real_sdk.script[:] = [(429, {"retry-after": _JUST_ABOVE[site]}), (200, {})]
    await _bounded(_RUN[site]())

    _assert_backoff(real_sdk.sleeps)


# ── 헤더 형태 표 (ai_review, 상한 60) / header-form table ──

def _http_date(seconds_from_now: float) -> str:
    return email.utils.formatdate(time.time() + seconds_from_now, usegmt=True)


@pytest.mark.parametrize("headers, expected", [
    ({"retry-after": "30"}, [30.0]),
    ({"retry-after": "60"}, [60.0]),
    ({"retry-after-ms": "30000", "retry-after": "120"}, [30.0]),   # ms 를 먼저 읽는다 / ms is read first
    # ms 파싱 실패 → retry-after 를 읽는다 / unparseable ms falls back to retry-after
    ({"retry-after-ms": "abc", "retry-after": "30"}, [30.0]),
    ({"retry-after": "61"}, "backoff"),
    ({"retry-after-ms": "90000"}, "backoff"),
    ({"retry-after-ms": "90000", "retry-after": "5"}, "backoff"),  # SDK 는 ms 만 본다 / SDK reads ms only
    ({"retry-after-ms": "abc", "retry-after": "120"}, "backoff"),
    ({"retry-after": "Fri, 31 Dec 2099 23:59:59 GMT"}, "backoff"),
    ({"retry-after": "inf"}, "backoff"),
    ({"retry-after": "nan"}, "backoff"),
])
async def test_retry_after_header_forms(real_sdk, headers, expected):
    real_sdk.script[:] = [(429, headers), (200, {})]
    await _bounded(_run_ai_review())

    if expected == "backoff":
        _assert_backoff(real_sdk.sleeps)
    else:
        assert real_sdk.sleeps == expected


async def test_http_date_within_cap_goes_to_backoff_not_honoured(real_sdk):
    """🔴 1.5.0 과 **정확히 같지는 않다** — 날짜 파서를 두지 않아(fail-closed) 30초 뒤 날짜도 backoff 다.
    대기가 짧아지는 쪽으로만 틀린다. Not exact 1.5.0 parity: every HTTP-date goes to backoff.
    """
    real_sdk.script[:] = [(429, {"retry-after": _http_date(30)}), (200, {})]
    await _bounded(_run_ai_review())

    _assert_backoff(real_sdk.sleeps)


# ── 부수 효과 / side effects ──

async def test_unparseable_retry_after_date_keeps_vendor_error_typed(real_sdk, caplog):
    """SDK 의 `mktime_tz` 가 `year 99999` 에서 try 밖 ValueError 를 던진다 — 수정 전 ValueError/internal_error.
    상한 경로(ms=0)는 날짜 분기에 닿지 않아 벤더 오류 타입이 남는다. 두 호출부 모두 전송을 실제로 탄다.
    The capped path never reaches the SDK's date branch; both sites really hit the transport.
    """
    real_sdk.script[:] = [(429, {"retry-after": "Fri, 31 Dec 99999 23:59:59 GMT"})]
    out = await _bounded(_run_ai_review())
    assert (out.error_type, out.error_status_code) == ("RateLimitError", 429)
    assert real_sdk.calls == 2

    real_sdk.calls, real_sdk.sleeps[:] = 0, []
    out = await _bounded(_run_repo_insight())
    assert out["status"] == "api_error"
    # 전송 0회(연결 오류)도 api_error 다 — 시도 수와 예외 타입까지 잰다.
    # Zero transport calls (a connection error) is api_error too; measure attempts and type.
    assert real_sdk.calls == 3
    assert type(_raised(caplog, "src.services.repo_insight_service")) is anthropic.RateLimitError


async def test_transient_5xx_with_long_retry_after_still_recovers(real_sdk):
    """529 + `retry-after: 120` 다음 200 — 재시도는 남기고 대기만 줄인다(fail-fast 가 아니다)."""
    real_sdk.script[:] = [(529, {"retry-after": "120"}), (200, {})]
    out = await _bounded(_run_repo_insight())

    assert out["status"] == "success"
    assert real_sdk.calls == 2
    _assert_backoff(real_sdk.sleeps)


@pytest.mark.parametrize("status", [408, 409, 500])
async def test_other_retryable_statuses_with_long_retry_after_use_backoff(real_sdk, caplog, status):
    """429·529 말고도 SDK 가 재시도하는 상태(408·409·500)에 상한이 걸린다 — 실제 SDK 루프로.
    Other statuses the SDK retries (408, 409, 500) are capped too, through the real loop.
    """
    caplog.set_level(logging.WARNING, logger="src.shared.claude_metrics")
    real_sdk.script[:] = [(status, {"retry-after": "120"}), (200, {})]
    out = await _bounded(_run_repo_insight())

    assert out["status"] == "success" and real_sdk.calls == 2
    _assert_backoff(real_sdk.sleeps)
    assert len(_cap_warnings(caplog)) == 1


@pytest.mark.parametrize("status", [529, 429])
async def test_missing_retry_after_is_left_alone(real_sdk, caplog, status):
    """Retry-After 가 없으면 상한을 넘은 것이 아니다 — 경고·헤더 위조 없이 SDK backoff 그대로.
    No Retry-After is not over the cap: no warning, no forged header, plain SDK backoff.
    """
    caplog.set_level(logging.WARNING, logger="src.shared.claude_metrics")
    real_sdk.script[:] = [(status, {}), (200, {})]
    out = await _bounded(_run_repo_insight())

    assert out["status"] == "success" and real_sdk.calls == 2
    _assert_backoff(real_sdk.sleeps)
    assert _cap_warnings(caplog) == []
    assert "retry-after-ms" not in real_sdk.responses[0].headers, "Retry-After 없는 응답에 헤더를 위조했다"


# ── 재시도 판정 = 실제 SDK `_should_retry` 오라클 / retry predicate vs the real SDK oracle ──
#
# 술어가 이름으로 부르는 상태(408·409·429·≥500)만 넣으면 초록은 아무것도 증명하지 않는다.
# 이름 밖 상태(200·4xx·413·422·502~529)와 `x-should-retry` 의 비정규 표기를 실제 SDK 판정과 겨룬다.
# Statuses the predicate never names, and off-spec x-should-retry spellings, against the real SDK.

# witness-corpus: 술어가 이름으로 부르지 않는 상태 코드 — 성공·4xx·413·422·5xx 변종이 같은 판정 부류다
_ORACLE_STATUSES = (200, 400, 401, 403, 404, 408, 409, 413, 422, 429, 500, 502, 503, 504, 529)
# witness-corpus: x-should-retry 의 비정규 표기 — 대문자·숫자·빈 값은 SDK 가 무시하고 상태로 간다
_ORACLE_FLAGS = (None, "true", "false", "TRUE", "False", "1", "")


def test_sdk_will_retry_matches_the_real_sdk_should_retry():
    """🔴 `_sdk_will_retry` 는 SDK 판정의 사본이다 — 상태 × 헤더 표 전체에서 실제 SDK 와 같아야 한다.
    SDK 가 판정을 바꾸면(또는 사본이 좁아지면) 여기가 red 가 된다.
    The copy must agree with the real SDK over the whole status x header table.
    """
    oracle = _REAL_CTOR(api_key="sk-test", base_url="http://anthropic.test")
    diffs = []
    for status in _ORACLE_STATUSES:
        for flag in _ORACLE_FLAGS:
            resp = httpx2.Response(status, headers={} if flag is None else {"x-should-retry": flag})
            if _sdk_will_retry(resp) != oracle._should_retry(resp):  # pylint: disable=protected-access
                diffs.append((status, flag))
    assert diffs == [], f"SDK `_should_retry` 와 다르다: {diffs}"


def test_sdk_backoff_constants_match_the_literal_bounds():
    """backoff 범위 리터럴(0.375·8.0)의 근거 — SDK 상수가 바뀌면 여기가 먼저 red.
    The literal backoff bounds come from these SDK constants.
    """
    assert (_sdk_constants.INITIAL_RETRY_DELAY, _sdk_constants.MAX_RETRY_DELAY) == (0.5, 8.0)


@pytest.mark.parametrize("headers, expected_ra", [
    ({"retry-after": "120"}, "120"),
    ({"retry-after-ms": "90000", "retry-after": "5"}, "5"),
])
async def test_raised_exception_keeps_vendor_retry_after(real_sdk, caplog, headers, expected_ra):
    """호출부가 받는 예외의 `retry-after` 는 벤더 원문이다 — 미들웨어는 `retry-after-ms` 만 쓴다."""
    real_sdk.script[:] = [(429, headers)]
    out = await _bounded(_run_ai_review())

    exc = _raised(caplog, "src.analyzer.io.ai_review")
    assert isinstance(exc, anthropic.RateLimitError)
    assert exc.response.headers.get("retry-after") == expected_ra
    assert out.error_retry_after == expected_ra


@pytest.mark.parametrize("status, headers", [
    (429, {"x-should-retry": "false", "retry-after": "120"}),
    (400, {"retry-after": "120"}),
])
async def test_sdk_will_not_retry_so_nothing_is_rewritten(real_sdk, caplog, status, headers):
    """SDK 가 재시도하지 않을 응답(`x-should-retry: false` · 400)은 건드리지도 경고하지도 않는다."""
    caplog.set_level(logging.WARNING, logger="src.shared.claude_metrics")
    real_sdk.script[:] = [(status, headers)]
    out = await _bounded(_run_repo_insight())

    assert out["status"] == "api_error"
    assert real_sdk.calls == 1 and real_sdk.sleeps == []
    exc = _raised(caplog, "src.services.repo_insight_service")
    assert exc.response.status_code == status
    assert "retry-after-ms" not in exc.response.headers, "재시도 없는 응답에 헤더를 위조했다"
    assert _cap_warnings(caplog) == [], "재시도하지 않는데 상한 경고를 남겼다"


async def test_should_retry_true_on_400_is_capped(real_sdk):
    """반대 방향 — `x-should-retry: true` 면 400 도 SDK 가 재시도하므로 상한을 건다."""
    real_sdk.script[:] = [(400, {"x-should-retry": "true", "retry-after": "120"}), (200, {})]
    out = await _bounded(_run_repo_insight())

    assert out["status"] == "success"
    _assert_backoff(real_sdk.sleeps)


# ── 관측성 / observability ──

async def test_capped_retry_logs_one_warning_per_attempt_with_evidence(real_sdk, caplog):
    caplog.set_level(logging.WARNING, logger="src.shared.claude_metrics")
    real_sdk.script[:] = [(429, {"retry-after": "9" * 100})]
    await _bounded(_run_repo_insight())

    msgs = [r.getMessage() for r in _cap_warnings(caplog)]
    assert len(msgs) == 3, msgs   # 시도마다 1건 / one per capped attempt
    for i, msg in enumerate(msgs):
        assert "caller=repo_insight" in msg and "status=429" in msg and f"request_id=req_{i}" in msg
        assert f"attempt={i + 1}" in msg and "cap=15" in msg
        # 헤더 값은 sanitize_for_log(max_len=64) 로 잘린다 / header values are truncated
        assert "retry_after=" + "9" * 64 + "…" in msg


async def test_honoured_retry_logs_nothing(real_sdk, caplog):
    caplog.set_level(logging.WARNING, logger="src.shared.claude_metrics")
    real_sdk.script[:] = [(429, {"retry-after": "15"}), (200, {})]
    await _bounded(_run_repo_insight())

    assert real_sdk.sleeps == [15.0]
    assert _cap_warnings(caplog) == []


# ── 페이지 전체 기한 (#1697) / total page deadline ──
#
# 상한(15s)은 대기 **한 번**을 묶을 뿐이다 — 시도 3회 × 읽기 60s + 대기 2 × 15s = 210s 가 남는다.
# 여기서는 대기를 가짜로 바꾸지 않는다: 응답 없는 전송과 **상한 안이라 따르는** 15s 대기 둘 다
# 실제 시간으로 흐르고, 기한(0.2s 로 줄인 모듈 속성)만이 그것을 끊는다.
# The per-wait cap leaves 210s; nothing is faked here but the transport, and only the deadline
# (the module attribute, shrunk to 0.2s) cuts a hung attempt or an honoured 15s wait.

_PAGE_MODULES = {"dashboard_insight": dashboard_service, "repo_insight": repo_insight_service}


@pytest.fixture
def live_sdk(monkeypatch):
    """실제 SDK + 실제 대기 — 전송만 가짜 / real SDK and real sleeps; only the transport is faked."""
    h = SimpleNamespace(mode="hang", calls=0, clients=[])

    async def handler(_req):
        h.calls += 1
        if h.mode == "hang":
            await asyncio.sleep(3600)
        return httpx2.Response(429, json=_ERR_BODY, headers={"retry-after": "15"})

    def ctor(*args, **kwargs):
        client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
        h.clients.append(client)
        return _REAL_CTOR(*args, base_url="http://anthropic.test", http_client=client, **kwargs)

    monkeypatch.setattr(anthropic, "AsyncAnthropic", ctor)
    monkeypatch.delenv("INSIGHT_DISABLED", raising=False)
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    return h


@pytest.mark.parametrize("mode", ["hang", "retry_after_15"])
@pytest.mark.parametrize("site", ["dashboard_insight", "repo_insight"])
async def test_page_call_stops_at_total_deadline(live_sdk, monkeypatch, site, mode):
    """🔴 수정 전: `hang` 은 읽기 타임아웃 60s × 3 까지, `retry_after_15` 는 실제 15s 를 잔다(5s 안에 red)."""
    module = _PAGE_MODULES[site]
    live_sdk.mode = mode
    log = MagicMock()
    monkeypatch.setattr(module, "log_claude_api_call", log)
    # raising=False — 수정 전엔 속성이 없다. 그래도 AttributeError 가 아니라 «행동» 으로 red 가 된다.
    # raising=False so the pre-fix run is red on behaviour, not on a missing attribute.
    monkeypatch.setattr(module, "ANTHROPIC_PAGE_DEADLINE_SECONDS", 0.2, raising=False)

    t0 = time.perf_counter()
    out = await _bounded(_RUN[site]())
    elapsed = time.perf_counter() - t0

    assert _status(site, out) == "api_error"
    assert elapsed < 2, f"기한이 끊지 않았다: {elapsed:.2f}s"
    assert live_sdk.calls == 1, "기한 안에 재시도가 돌았다 — 시도 1회에서 끊겨야 한다"
    assert live_sdk.clients and all(c.is_closed for c in live_sdk.clients), "httpx 풀을 닫지 않았다"
    assert log.call_count == 1, log.call_args_list
    kw = log.call_args.kwargs
    assert (kw["status"], kw["error_type"], kw["output_tokens"]) == ("error", "TimeoutError", 0)


async def test_page_deadline_is_45s_literal(real_sdk, monkeypatch):
    """기한은 리터럴 45.0 이고, 페이지 호출부가 넘기는 **시도당 타임아웃보다 짧다**.

    시도당 타임아웃이 기한 아래로 내려가면 멈춘 시도를 SDK 가 먼저 끊고 재시도해 기한이
    다시 여러 시도를 품는다. The deadline must stay below the per-attempt timeout the pages pass.
    """
    assert claude_metrics.ANTHROPIC_PAGE_DEADLINE_SECONDS == 45.0
    real_sdk.script[:] = [(200, {})]
    for site, module in _PAGE_MODULES.items():
        spy = MagicMock(wraps=module.new_async_anthropic)
        monkeypatch.setattr(module, "new_async_anthropic", spy)
        await _bounded(_RUN[site]())
        assert spy.call_count == 1, site
        assert module.ANTHROPIC_PAGE_DEADLINE_SECONDS < spy.call_args.kwargs["timeout"], site


# ── 생성 단일 지점 가드 (AST) / single-factory guard ──

_SRC = pathlib.Path(__file__).resolve().parents[3] / "src"
_FACTORY_FILE = "src/shared/claude_metrics.py"
_CTORS = {"AsyncAnthropic", "Anthropic"}
# 기존 클라이언트를 복제하며 미들웨어를 갈아끼울 수 있는 SDK 메서드 / SDK methods that copy a client
_CLIENT_COPIES = {"with_options", "copy"}


def _client_construction_sites(tree: ast.AST) -> list[int]:
    """SDK 클라이언트를 만들거나 미들웨어를 갈아끼울 수 있는 지점의 줄번호.

    잡는 것: `anthropic.AsyncAnthropic`/`Anthropic` 참조(호출·상속·변수 대입 전부),
    `from anthropic import AsyncAnthropic as AC` 별칭의 참조, `getattr(x, "AsyncAnthropic")`,
    `middleware=` 를 넘기는 `.with_options(...)`/`.copy(...)`(미들웨어를 떼는 경로).
    타입 주석 안의 참조와 docstring·주석 산문, 다른 라이브러리의 `middleware=`(`Starlette(...)`)는 세지 않는다.

    🔴 못 잡는 것(정적 판정의 한계 — 「전부 막는다」고 읽지 마라): `from anthropic import *`,
    계산된 문자열의 `getattr`, `importlib.import_module`, `exec`, `**kwargs` 로 넘긴 `middleware`,
    `anthropic` 모듈 자체를 다른 이름에 담아 속성 없이 넘기는 경로, 동기 `Anthropic` 에 쓸
    `handle` 미구현(현재 동기 클라이언트는 `src/` 에 없다).
    Catches ctor references (outside annotations), anthropic import aliases, literal getattr and
    `.with_options`/`.copy` calls passing `middleware=`; ignores other libraries' `middleware=`.
    Misses star imports, computed getattr, importlib/exec and **kwargs splats.
    """
    aliases: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] == "anthropic":
            aliases |= {a.asname or a.name for a in n.names if a.name in _CTORS}

    in_annotation: set[int] = set()
    for n in ast.walk(tree):
        anns = []
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            anns.append(n.returns)
        elif isinstance(n, ast.arg):
            anns.append(n.annotation)
        elif isinstance(n, ast.AnnAssign):
            anns.append(n.annotation)
        for ann in anns:
            if ann is not None:
                in_annotation |= {id(x) for x in ast.walk(ann)}

    hits = []
    for n in ast.walk(tree):
        if id(n) in in_annotation:
            continue
        if isinstance(n, ast.Attribute) and n.attr in _CTORS and isinstance(n.ctx, ast.Load):
            hits.append(n.lineno)
        elif isinstance(n, ast.Name) and n.id in aliases and isinstance(n.ctx, ast.Load):
            hits.append(n.lineno)
        elif isinstance(n, ast.Call):
            if (isinstance(n.func, ast.Name) and n.func.id == "getattr" and len(n.args) >= 2
                    and isinstance(n.args[1], ast.Constant) and n.args[1].value in _CTORS):
                hits.append(n.lineno)
            elif (isinstance(n.func, ast.Attribute) and n.func.attr in _CLIENT_COPIES
                  and any(kw.arg == "middleware" for kw in n.keywords)):
                hits.append(n.lineno)
    return hits


def _tracked_src_files() -> list[pathlib.Path]:
    """git 이 추적하는 `src/**.py` — `rglob` 는 `.gitignore` 를 무시해 로컬 잔재까지 센다.
    git-tracked files only; rglob ignores .gitignore and counts local leftovers. Dedupe (merge conflicts).
    """
    root = _SRC.parent
    proc = subprocess.run(["git", "ls-files", "-z", "--", "src"], cwd=root, capture_output=True, check=True)
    paths = {p for p in proc.stdout.decode("utf-8").split("\0") if p.endswith(".py")}
    return [root / p for p in sorted(paths) if (root / p).exists()]


def _offenders() -> set[str]:
    out = set()
    for f in _tracked_src_files():
        if _client_construction_sites(ast.parse(f.read_text(encoding="utf-8"))):
            out.add(f.relative_to(_SRC.parent).as_posix())
    return out


def test_scanner_catches_planted_ctor_and_ignores_prose():
    """계기 자기검증 — `claimed\\cheap`(별칭 생성·상속·getattr·미들웨어 제거)은 잡고,
    `cheap\\claimed`(docstring·주석·타입 주석의 이름 언급, 다른 라이브러리의 `middleware=`)는
    무시해야 한다. 같은 심음을 **손대지 않은 운영 파일**에 끼워 넣어도 뒤집혀야 한다.
    """
    must_catch = [
        "from anthropic import AsyncAnthropic as AC\nc = AC(api_key='k')\n",
        "import anthropic\nclass Mine(anthropic.AsyncAnthropic):\n    pass\n",
        "import anthropic\nctor = getattr(anthropic, 'AsyncAnthropic')\n",
        "def f(c):\n    return c.with_options(middleware=[])\n",
        "def f(c):\n    return c.copy(middleware=[])\n",
        "import anthropic\nmake = anthropic.Anthropic\n",
    ]
    must_ignore = (
        '"""절대 anthropic.AsyncAnthropic(api_key=k) 를 직접 부르지 마라."""\n'
        "# AsyncAnthropic(...) 금지\n"
        "import anthropic\n"
        "def g(client: anthropic.AsyncAnthropic) -> 'anthropic.AsyncAnthropic':\n"
        "    x: anthropic.AsyncAnthropic = client\n"
        "    return x\n"
        "from starlette.applications import Starlette\n"
        "from starlette.middleware import Middleware\n"
        "app = Starlette(middleware=[Middleware(object)])\n"
    )
    for src in must_catch:
        assert _client_construction_sites(ast.parse(src)), f"심은 생성 경로를 놓쳤다: {src!r}"
    assert not _client_construction_sites(ast.parse(must_ignore)), "산문·타입 주석을 생성으로 오판했다"

    host = (_SRC / "services" / "repo_insight_service.py").read_text(encoding="utf-8")
    base = len(_client_construction_sites(ast.parse(host)))
    assert len(_client_construction_sites(ast.parse(host + "\n" + must_ignore))) == base, \
        "운영 파일에 끼운 산문·타입 주석을 잡았다"
    assert len(_client_construction_sites(ast.parse(host + "\n" + must_catch[0]))) > base, \
        "운영 파일에 끼운 별칭 생성을 놓쳤다"


def test_only_the_factory_builds_anthropic_clients():
    """🔴 SDK ≥1.6 은 Retry-After 를 상한 없이 기다린다 — 생성은 `new_async_anthropic` 한 곳뿐이어야 한다."""
    offenders = _offenders()
    assert _FACTORY_FILE in offenders, "팩토리를 못 찾았다 — 스캐너가 공허하다"
    assert offenders == {_FACTORY_FILE}, (
        f"`new_async_anthropic` 밖에서 SDK 클라이언트를 만든다(상한 미들웨어 없음): {sorted(offenders - {_FACTORY_FILE})}"
    )
