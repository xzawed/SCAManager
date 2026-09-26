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
import functools
import logging
import pathlib
import time
from types import SimpleNamespace
from unittest.mock import patch

import anthropic
import anthropic._base_client as _sdk_base
import httpx2
import pytest

from src.analyzer.io.ai_review import review_code
from src.config import settings
from src.services import dashboard_service
from src.services.repo_insight_service import repo_insight_narrative

_REAL_CTOR = anthropic.AsyncAnthropic
# SDK 자체 backoff 의 최댓값(MAX_RETRY_DELAY) — 이 이하면 상한 경로로 본다.
# The SDK's own backoff ceiling; a sleep at or below it means the capped path was taken.
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
    h = SimpleNamespace(script=[], calls=0, sleeps=[])

    def handler(_req):
        i = h.calls
        h.calls += 1
        status, headers = h.script[min(i, len(h.script) - 1)]
        body = _OK_BODY if status == 200 else _ERR_BODY
        return httpx2.Response(status, json=body, headers={"request-id": f"req_{i}", **headers})

    async def fake_sleep(seconds, *_a, **_k):
        h.sleeps.append(seconds)

    monkeypatch.setattr(_sdk_base.anyio, "sleep", fake_sleep)
    # 전역 속성을 바꾼다 — 호출부가 어떤 경로로 생성하든 이 전송을 탄다.
    # Patch the global attribute so every construction path uses this transport.
    monkeypatch.setattr(anthropic, "AsyncAnthropic", functools.partial(
        _REAL_CTOR, base_url="http://anthropic.test",
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    ))
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
    # user_id=None skips the cache; KPI helpers report data so the no_data early return is defeated.
    with patch.object(dashboard_service, "dashboard_kpi", return_value={"analysis_count": {"value": 3}}), \
         patch.object(dashboard_service, "dashboard_trend", return_value={}), \
         patch.object(dashboard_service, "frequent_issues_v2", return_value=[]), \
         patch.object(dashboard_service, "auto_merge_kpi", return_value={}), \
         patch.object(dashboard_service, "_build_insight_user_prompt", return_value="prompt"):
        return await dashboard_service.insight_narrative(None, 7, api_key="sk-test", user_id=None)


async def _run_repo_insight():
    return await repo_insight_narrative(
        None, 1, 30, repo_full_name="o/r", kpi={"analysis_count": 3}, recurring=[], user_id=None,
    )


_RUN = {"ai_review": _run_ai_review, "dashboard_insight": _run_dashboard, "repo_insight": _run_repo_insight}


def _status(site, out):
    return out.status if site == "ai_review" else out["status"]


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
    assert max(real_sdk.sleeps) <= _BACKOFF_MAX, f"상한 초과 Retry-After 를 그대로 기다렸다: {real_sdk.sleeps}"
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

    assert len(real_sdk.sleeps) == 1 and real_sdk.sleeps[0] <= _BACKOFF_MAX, real_sdk.sleeps


# ── 헤더 형태 표 (ai_review, 상한 60) / header-form table ──

def _http_date(seconds_from_now: float) -> str:
    return email.utils.formatdate(time.time() + seconds_from_now, usegmt=True)


@pytest.mark.parametrize("headers, expected", [
    ({"retry-after": "30"}, [30.0]),
    ({"retry-after": "60"}, [60.0]),
    ({"retry-after-ms": "30000", "retry-after": "120"}, [30.0]),   # ms 를 먼저 읽는다 / ms is read first
    ({"retry-after-ms": "abc", "retry-after": "30"}, [30.0]),      # ms 파싱 실패 → retry-after
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
        assert len(real_sdk.sleeps) == 1 and real_sdk.sleeps[0] <= _BACKOFF_MAX, real_sdk.sleeps
    else:
        assert real_sdk.sleeps == expected


async def test_http_date_within_cap_goes_to_backoff_not_honoured(real_sdk):
    """🔴 1.5.0 과 **정확히 같지는 않다** — 날짜 파서를 두지 않아(fail-closed) 30초 뒤 날짜도 backoff 다.
    대기가 짧아지는 쪽으로만 틀린다. Not exact 1.5.0 parity: every HTTP-date goes to backoff.
    """
    real_sdk.script[:] = [(429, {"retry-after": _http_date(30)}), (200, {})]
    await _bounded(_run_ai_review())

    assert len(real_sdk.sleeps) == 1 and real_sdk.sleeps[0] <= _BACKOFF_MAX, real_sdk.sleeps


# ── 부수 효과 / side effects ──

async def test_unparseable_retry_after_date_keeps_vendor_error_typed(real_sdk):
    """SDK 의 `mktime_tz` 가 `year 99999` 에서 try 밖 ValueError 를 던진다 — 수정 전 ValueError/internal_error.
    상한 경로(ms=0)는 날짜 분기에 닿지 않아 벤더 오류 타입이 남는다.
    """
    real_sdk.script[:] = [(429, {"retry-after": "Fri, 31 Dec 99999 23:59:59 GMT"})]
    out = await _bounded(_run_ai_review())
    assert (out.error_type, out.error_status_code) == ("RateLimitError", 429)

    real_sdk.calls, real_sdk.sleeps[:] = 0, []
    out = await _bounded(_run_repo_insight())
    assert out["status"] == "api_error"


async def test_transient_5xx_with_long_retry_after_still_recovers(real_sdk):
    """529 + `retry-after: 120` 다음 200 — 재시도는 남기고 대기만 줄인다(fail-fast 가 아니다)."""
    real_sdk.script[:] = [(529, {"retry-after": "120"}), (200, {})]
    out = await _bounded(_run_repo_insight())

    assert out["status"] == "success"
    assert real_sdk.calls == 2 and max(real_sdk.sleeps) <= _BACKOFF_MAX, real_sdk.sleeps


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
    assert len(real_sdk.sleeps) == 1 and real_sdk.sleeps[0] <= _BACKOFF_MAX, real_sdk.sleeps


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


# ── 생성 단일 지점 가드 (AST) / single-factory guard ──

_SRC = pathlib.Path(__file__).resolve().parents[3] / "src"
_FACTORY_FILE = "src/shared/claude_metrics.py"
_CTORS = {"AsyncAnthropic", "Anthropic"}


def _client_construction_sites(tree: ast.AST) -> list[int]:
    """SDK 클라이언트를 만들거나 미들웨어를 갈아끼울 수 있는 지점의 줄번호.

    잡는 것: `anthropic.AsyncAnthropic`/`Anthropic` 참조(호출·상속·변수 대입 전부),
    `from anthropic import AsyncAnthropic as AC` 별칭의 참조, `getattr(x, "AsyncAnthropic")`,
    `middleware=` 키워드를 넘기는 모든 호출(`with_options`/`copy` 로 미들웨어를 떼는 경로).
    타입 주석 안의 참조와 docstring·주석 산문은 세지 않는다.

    🔴 못 잡는 것(정적 판정의 한계 — 「전부 막는다」고 읽지 마라): `from anthropic import *`,
    계산된 문자열의 `getattr`, `importlib.import_module`, `exec`, `**kwargs` 로 넘긴 `middleware`,
    `anthropic` 모듈 자체를 다른 이름에 담아 속성 없이 넘기는 경로, 동기 `Anthropic` 에 쓸
    `handle` 미구현(현재 동기 클라이언트는 `src/` 에 없다).
    Catches ctor references (outside annotations), anthropic import aliases, literal getattr and any
    `middleware=` call; misses star imports, computed getattr, importlib/exec and **kwargs splats.
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
            elif any(kw.arg == "middleware" for kw in n.keywords):
                hits.append(n.lineno)
    return hits


def _offenders() -> set[str]:
    out = set()
    for f in sorted(_SRC.rglob("*.py")):
        if _client_construction_sites(ast.parse(f.read_text(encoding="utf-8"))):
            out.add(f.relative_to(_SRC.parent).as_posix())
    return out


def test_scanner_catches_planted_ctor_and_ignores_prose():
    """계기 자기검증 — `claimed\\cheap`(별칭 생성·상속·getattr·미들웨어 제거)은 잡고,
    `cheap\\claimed`(docstring·주석·타입 주석의 이름 언급)는 무시해야 한다.
    같은 심음을 **손대지 않은 운영 파일**에 끼워 넣어도 뒤집혀야 한다.
    """
    must_catch = [
        "from anthropic import AsyncAnthropic as AC\nc = AC(api_key='k')\n",
        "import anthropic\nclass Mine(anthropic.AsyncAnthropic):\n    pass\n",
        "import anthropic\nctor = getattr(anthropic, 'AsyncAnthropic')\n",
        "def f(c):\n    return c.with_options(middleware=[])\n",
        "import anthropic\nmake = anthropic.Anthropic\n",
    ]
    must_ignore = (
        '"""절대 anthropic.AsyncAnthropic(api_key=k) 를 직접 부르지 마라."""\n'
        "# AsyncAnthropic(...) 금지\n"
        "import anthropic\n"
        "def g(client: anthropic.AsyncAnthropic) -> 'anthropic.AsyncAnthropic':\n"
        "    x: anthropic.AsyncAnthropic = client\n"
        "    return x\n"
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
