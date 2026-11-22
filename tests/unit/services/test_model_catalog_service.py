"""모델 카탈로그 서비스 — 목록 동기화 · 재시작 기준 · 시험 호출 관문 · 운영자 알림 (Issue #1905 ①a Task 2).

Model catalog service: listing sync, restart baseline, probe gate and operator alerts.
가짜는 바깥 경계(Anthropic 클라이언트 · Telegram 전송 · 비용 행 기록)에만 둔다 — 목록 · 응답은 SDK 의 실제 타입으로 만든다.
Fakes sit only at the outer boundaries (Anthropic client, Telegram send, cost-row writer); listings and responses
are built from the SDK's real types.
"""
import asyncio
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import ANY

import anthropic
import httpx
import pytest
from anthropic.types import Message, ModelInfo
from anthropic.types.beta import BetaMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.config import Settings, settings
from src.database import Base
from src.models.claude_api_call import ClaudeApiCall
from src.models.repo_config import RepoConfig
from src.repositories import claude_api_cost_repo
from src.services import model_catalog_service as svc
from src.shared import model_catalog as mc

_TABLE_MODELS = (ClaudeApiCall, RepoConfig)
if any(m.__tablename__ not in Base.metadata.tables for m in _TABLE_MODELS):
    raise RuntimeError("side-effect ORM import 소실 — 테이블 미등록 / ORM import lost, table unregistered")

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _d(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


def _info(model_id, line, created, *, lifecycle="active", deprecated=None, retires=None,
          effort=True, structured=True, with_capabilities=True, fallbacks=None, effort_levels=None):
    fields = {"id": model_id, "type": "model", "display_name": model_id, "created_at": created, "line": line,
              "lifecycle": lifecycle, "deprecated_at": deprecated, "retires_at": retires}
    if fallbacks is not None:
        fields["allowed_fallback_models"] = fallbacks
    if with_capabilities:
        effort_node = {"supported": effort}
        if effort_levels is not None:
            effort_node.update({level: {"supported": level in effort_levels}
                                for level in ("low", "medium", "high", "xhigh", "max")})
        fields["capabilities"] = {"effort": effort_node, "structured_outputs": {"supported": structured}}
    return ModelInfo.construct(**fields)


_LISTING = [
    _info("claude-haiku-4-5", "haiku", _d(2025, 10, 1), effort=False),
    _info("claude-haiku-5-5", "haiku", _d(2026, 10, 1)),
    _info("claude-sonnet-5", "sonnet", _d(2026, 4, 1)),
    _info("claude-sonnet-5-5", "sonnet", _d(2026, 10, 1)),
    _info("claude-opus-5", "opus", _d(2026, 6, 1)),
    _info("claude-opus-5-5", "opus", _d(2026, 10, 1)),
]


def _usage(**extra) -> dict:
    return {"input_tokens": 12, "output_tokens": 5, "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0, **extra}


def _message(text='{"ok": true}', *, model="claude-haiku-5-5", stop_reason="end_turn"):
    content = [{"type": "text", "text": text}] if text is not None else []
    return Message.construct(id="msg_probe", type="message", role="assistant", model=model, content=content,
                             stop_reason=stop_reason, stop_sequence=None, usage=_usage())


def _beta_message(text='{"ok": true}', *, model="claude-sonnet-5-5", stop_reason="end_turn", fallback_ran=False):
    iterations = ([{"type": "fallback_message", "model": "claude-opus-5", "input_tokens": 6, "output_tokens": 3}]
                  if fallback_ran else None)
    content = [{"type": "text", "text": text}] if text is not None else []
    return BetaMessage.construct(id="msg_probe", type="message", role="assistant", model=model, content=content,
                                 stop_reason=stop_reason, stop_sequence=None, usage=_usage(iterations=iterations))


def _status_error(cls, code: int):
    return cls("probe failed", response=httpx.Response(code, request=_REQUEST), body=None)


def _entry(model_id: str, line: str, *, effort: bool = True, structured: bool = True,
           server_fallback: bool | None = None) -> mc.ModelEntry:
    return mc.ModelEntry(id=model_id, line=line, display_name=model_id, created_at=_d(2026, 10, 1),
                         deprecated_at=None, retires_at=None, supports_structured_outputs=structured,
                         supports_effort=effort, server_fallback=server_fallback)


class _AsyncListing:
    def __init__(self, items, error):
        self._items = list(items)
        self._error = error

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._error is not None:
            raise self._error
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


class _FakeCreate:
    """create() 호출을 적고 정해 둔 결과(응답 또는 예외)를 차례로 낸다 / records calls, plays scripted outcomes."""

    def __init__(self, outcomes):
        self.calls = []
        self._outcomes = list(outcomes)

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeClient:
    def __init__(self, *, listing=(), list_error=None, plain=(), beta=(), beta_list_error=None):
        self.messages = _FakeCreate(plain)
        self.listed_with = []

        def _list(**kwargs):
            self.listed_with.append(kwargs)
            if beta_list_error is not None:
                raise beta_list_error
            return _AsyncListing(listing, list_error)

        def _plain_list(**kwargs):
            self.listed_with.append({"plain": True, **kwargs})
            return _AsyncListing(listing, list_error)

        self.beta = SimpleNamespace(messages=_FakeCreate(beta), models=SimpleNamespace(list=_list))
        self.models = SimpleNamespace(list=_plain_list)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def world(monkeypatch):
    monkeypatch.setattr(svc, "_SVC", svc._ServiceState())
    clock = {"now": NOW}
    monkeypatch.setattr(svc, "_utcnow", lambda: clock["now"])
    monkeypatch.setattr(settings, "telegram_bot_token", "bot-token-for-tests")
    monkeypatch.setattr(settings, "telegram_chat_id", "42")
    monkeypatch.setattr(settings, "default_locale", "en")
    monkeypatch.setattr(settings, "claude_review_model", "claude-haiku-4-5")
    monkeypatch.setattr(settings, "claude_insight_model", "claude-haiku-4-5")
    alerts, cost_rows, holder = [], [], {}

    async def _telegram(_token, chat_id, payload):
        alerts.append((chat_id, payload["parse_mode"], payload["text"]))

    monkeypatch.setattr(svc, "telegram_post_message", _telegram)
    monkeypatch.setattr(svc, "log_claude_api_call", lambda **row: cost_rows.append(row))
    monkeypatch.setattr(svc, "new_async_anthropic", lambda **_kwargs: holder["client"])
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield SimpleNamespace(alerts=alerts, cost_rows=cost_rows, clock=clock, holder=holder,
                          session_factory=sessionmaker(bind=engine))
    engine.dispose()


def _use(world, client: _FakeClient) -> _FakeClient:
    world.holder["client"] = client
    return client


def _record(world, model: str, *, status: str = "success", error_type: str = "", hours_ago: int = 1) -> None:
    with world.session_factory() as db:
        claude_api_cost_repo.record(
            db, model=model, status=status, input_tokens=1, output_tokens=1, cache_read_tokens=0,
            cache_creation_tokens=0, cost_usd=0.0, duration_ms=1.0, error_type=error_type,
            now=NOW - timedelta(hours=hours_ago),
        )


def _repo(world, name: str, review_model: str | None, *, ai: bool = True) -> None:
    with world.session_factory() as db:
        db.add(RepoConfig(repo_full_name=name, review_model=review_model, ai_review_enabled=ai))
        db.commit()


async def _refresh(world) -> svc.RefreshReport:
    return await svc.refresh_catalog(api_key="k", session_factory=world.session_factory)


# ── 목록 동기화 / listing sync ──

async def test_sync_maps_model_info(world):
    _use(world, _FakeClient(listing=[
        _info("claude-haiku-4-5", "haiku", _d(2025, 10, 1), effort=False),
        _info("claude-sonnet-4-5", "sonnet", _d(2025, 9, 29), lifecycle="deprecated",
              deprecated=_d(2026, 8, 1), retires=_d(2026, 11, 30)),
        _info("claude-opus-4-1", "opus", _d(2025, 8, 5), lifecycle="retired"),
        _info("claude-opus-x", "opus", _d(2026, 1, 1), structured=False),
        _info("claude-fable-x", "fable", _d(2026, 2, 1), with_capabilities=False),
        _info("claude-opus-y", "opus", _d(2026, 3, 1), lifecycle="sunset"),
    ]))
    assert await svc.sync_models(api_key="k") is True
    got = {e.id: e for e in mc.snapshot_entries()}
    assert mc.snapshot_source() == "api"
    haiku = got["claude-haiku-4-5"]
    assert (haiku.supports_effort, haiku.supports_structured_outputs) == (False, True)
    assert (got["claude-sonnet-4-5"].lifecycle, got["claude-sonnet-4-5"].retires_at) == ("deprecated", _d(2026, 11, 30))
    # 내려감 판정은 lifecycle 로만 — 날짜는 받은 그대로 / lifecycle is the signal; dates are kept as given
    assert (got["claude-opus-4-1"].lifecycle, got["claude-opus-4-1"].retires_at) == ("retired", None)
    # 모르는 lifecycle 값은 후보에서 빼되 고정 판은 옮기지 않는 쪽(deprecated)으로 / unknown values become deprecated
    assert got["claude-opus-y"].lifecycle == "deprecated"
    assert got["claude-opus-x"].supports_structured_outputs is False
    # capabilities 가 없으면 구조화 출력은 시험 호출이 판정하고 effort 는 보내지 않는다
    # without capabilities the probe judges structured outputs and effort is not sent
    assert (got["claude-fable-x"].supports_structured_outputs, got["claude-fable-x"].supports_effort) == (True, False)


async def test_line_values_are_normalised(world):
    _use(world, _FakeClient(listing=[
        _info("claude-haiku-5-5", "claude-haiku", _d(2026, 10, 1)),
        _info("claude-sonnet-5-5", "Sonnet", _d(2026, 10, 1)),
        _info("claude-opus-9", None, _d(2026, 11, 1)),
        _info("claude-mythos-5-2", "mythos", _d(2026, 10, 1)),
    ]))
    await svc.sync_models(api_key="k")
    assert {e.id: e.line for e in mc.snapshot_entries()} == {
        "claude-haiku-5-5": "haiku", "claude-sonnet-5-5": "sonnet", "claude-opus-9": "", "claude-mythos-5-2": "",
    }
    # 계열 없이 온 판에 id 로 계열을 붙이지 않는다(SDK 계약) / no line is inferred from the id of a line-less model
    assert mc.latest_candidate("opus") is None
    assert mc.latest_candidate("haiku").id == "claude-haiku-5-5"


@pytest.mark.parametrize("second", ["error", "empty"])
async def test_sync_failure_keeps_previous_snapshot(world, second):
    _use(world, _FakeClient(listing=[_info("claude-haiku-4-5", "haiku", _d(2025, 10, 1))]))
    assert await svc.sync_models(api_key="k") is True
    failing = (_FakeClient(list_error=anthropic.APIConnectionError(message="down", request=_REQUEST))
               if second == "error" else _FakeClient(listing=[]))
    _use(world, failing)
    assert await svc.sync_models(api_key="k") is False
    assert [e.id for e in mc.snapshot_entries()] == ["claude-haiku-4-5"]
    assert mc.snapshot_source() == "api"


# ── 재시작 기준 / restart baseline ──

def test_bootstrap_sets_known_good_from_history(world):
    # 성공 시각이 아니라 판의 출시 순서로 최신을 정한다 / newest by release order, not by success time
    _record(world, "claude-sonnet-5-5", hours_ago=6)
    _record(world, "claude-sonnet-5", hours_ago=5)
    _record(world, "claude-haiku-4-5", hours_ago=3)
    _record(world, "claude-haiku-5-5", hours_ago=2)
    _record(world, "claude-haiku-5-5", status="error", error_type="model_rejected", hours_ago=1)
    with world.session_factory() as db:
        svc.bootstrap_from_history(db)
    assert mc.verified_latest("haiku") == "claude-haiku-4-5"
    assert mc.is_failed("claude-haiku-5-5")
    assert (mc.verified_latest("sonnet"), mc.previous_verified("sonnet")) == ("claude-sonnet-5-5", "claude-sonnet-5")


# ── 갱신 · 시험 호출 / refresh and probes ──

async def test_refresh_probes_only_lines_in_use(world):
    _record(world, "claude-haiku-4-5")
    _repo(world, "o/off", "auto:opus", ai=False)  # AI 를 끈 리포는 세지 않는다 / AI-off repos do not count
    _repo(world, "o/bad", "auto:gpt")  # 읽을 수 없는 저장값은 건너뛴다 / unreadable stored values are skipped
    client = _use(world, _FakeClient(listing=_LISTING, plain=[_message()]))
    report = await _refresh(world)
    assert [call["model"] for call in client.messages.calls] == ["claude-haiku-5-5"]
    assert not client.beta.messages.calls
    assert report.promoted == {"haiku": "claude-haiku-5-5"}


async def test_probe_pass_promotes_and_notifies(world):
    _record(world, "claude-haiku-4-5")
    _repo(world, "o/a", "auto:haiku")
    _repo(world, "o/b", "auto:haiku")
    _repo(world, "o/c", "claude-haiku-4-5")
    _use(world, _FakeClient(listing=_LISTING, plain=[_message()]))
    await _refresh(world)
    assert mc.resolve_model("auto:haiku", default_value="auto:sonnet") == "claude-haiku-5-5"
    assert mc.resolve_model("claude-haiku-4-5", default_value="auto:sonnet") == "claude-haiku-4-5"
    ((chat_id, parse_mode, text),) = world.alerts
    assert (chat_id, parse_mode) == ("42", "HTML")
    assert "claude-haiku-4-5" in text and "claude-haiku-5-5" in text
    assert "following this line: 2)" in text


async def test_probe_fail_keeps_previous_and_notifies(world):
    _record(world, "claude-haiku-4-5")
    _use(world, _FakeClient(listing=_LISTING, plain=[_message('{"ok": false}')]))
    report = await _refresh(world)
    assert mc.verified_latest("haiku") == "claude-haiku-4-5"
    assert mc.is_failed("claude-haiku-5-5")
    assert report.failed == {"haiku": "bad_output"}
    assert len(world.alerts) == 1 and "claude-haiku-5-5" in world.alerts[0][2]
    # 실패로 적힌 판은 다시 시험하지 않는다 / a failed model is not probed again
    again = _use(world, _FakeClient(listing=_LISTING))
    await _refresh(world)
    assert not again.messages.calls and len(world.alerts) == 1


@pytest.mark.parametrize("first", [
    _status_error(anthropic.RateLimitError, 429),
    _message(None, stop_reason="max_tokens"),
])
async def test_unfinished_probe_is_retried_next_cycle(world, first):
    _record(world, "claude-haiku-4-5")
    _use(world, _FakeClient(listing=_LISTING, plain=[first]))
    report = await _refresh(world)
    assert (mc.is_failed("claude-haiku-5-5"), report.failed, world.alerts) == (False, {}, [])
    _use(world, _FakeClient(listing=_LISTING, plain=[_message()]))
    await _refresh(world)
    assert mc.verified_latest("haiku") == "claude-haiku-5-5"


async def test_probe_adds_effort_only_when_supported(world, monkeypatch):
    monkeypatch.setattr(settings, "claude_call_effort", "low")
    client = _use(world, _FakeClient(plain=[_message(), _message(model="claude-haiku-4-5")]))
    assert (await svc.probe_model(_entry("claude-haiku-5-5", "haiku"), api_key="k")).ok
    assert (await svc.probe_model(_entry("claude-haiku-4-5", "haiku", effort=False), api_key="k")).ok
    assert len(client.messages.calls) == 2
    first, second = client.messages.calls[0], client.messages.calls[1]
    assert first["output_config"]["effort"] == "low"
    assert "effort" not in second["output_config"]
    assert second["output_config"]["format"]["type"] == "json_schema"
    assert second["model"] == "claude-haiku-4-5"


async def test_probe_sends_the_default_effort(world, monkeypatch):
    # 기본 설정으로도 시험 호출은 effort 를 보낸다 — 리포가 effort 를 비운 실제 리뷰가 보내는 값과 같다(설계 §2)
    # With the default setting the probe still sends effort, the value a review with no repo effort sends.
    monkeypatch.setattr(settings, "claude_call_effort", Settings.model_fields["claude_call_effort"].default)
    client = _use(world, _FakeClient(plain=[_message()]))
    assert (await svc.probe_model(_entry("claude-haiku-5-5", "haiku"), api_key="k")).ok
    assert client.messages.calls[0]["output_config"]["effort"] == "high"


async def test_probe_rejects_model_without_structured_outputs(world):
    client = _use(world, _FakeClient())
    result = await svc.probe_model(_entry("claude-opus-x", "opus", structured=False), api_key="k")
    assert (result.ok, result.reason) == (False, "no_structured_outputs")
    assert not client.messages.calls and not client.beta.messages.calls


async def test_probe_never_sends_server_fallback(world):
    # 시험 호출은 후보 판 하나가 답하는지 본다 — 대체가 답하면 그 판의 답이 아니다. 대체 인자의 꼴은 실제 호출이
    # 거부를 받으면 대체 없이 다시 부르는 길이 맡는다(claude_call).
    # The probe checks the candidate alone; the real calls' plain retry covers a rejected fallback shape.
    client = _use(world, _FakeClient(plain=[_message(model="claude-sonnet-5-5"), _message(model="claude-sonnet-5")]))
    assert (await svc.probe_model(_entry("claude-sonnet-5-5", "sonnet", server_fallback=True), api_key="k")).ok
    assert (await svc.probe_model(_entry("claude-sonnet-5", "sonnet", server_fallback=False), api_key="k")).ok
    assert not client.beta.messages.calls
    assert [call["model"] for call in client.messages.calls] == ["claude-sonnet-5-5", "claude-sonnet-5"]
    assert all("fallbacks" not in call for call in client.messages.calls)


async def test_sync_reads_the_plain_listing_when_the_beta_header_is_refused(world):
    # 베타 헤더를 받지 않는 계정 · 지역(400/403) — 일반 목록으로 계속 따른다(서버 대체 = 모름)
    # An account or region that refuses the beta header still follows models through the plain listing.
    client = _use(world, _FakeClient(listing=[_info("claude-sonnet-5-5", "sonnet", _d(2026, 10, 1))],
                                     beta_list_error=_status_error(anthropic.BadRequestError, 400)))
    assert await svc.sync_models(api_key="k")
    assert mc.snapshot_source() == "api"
    assert [(e.id, e.server_fallback) for e in mc.snapshot_entries()] == [("claude-sonnet-5-5", None)]
    assert client.listed_with == [{"betas": ["server-side-fallback-2026-07-01"]}, {"plain": True}]


async def test_sync_reads_server_fallback_support_from_the_listing(world):
    client = _use(world, _FakeClient(listing=[
        _info("claude-sonnet-5-5", "sonnet", _d(2026, 10, 1), fallbacks=["claude-opus-5"]),
        _info("claude-haiku-5-5", "haiku", _d(2026, 10, 1), fallbacks=[]),
        _info("claude-opus-5", "opus", _d(2026, 6, 1)),
    ]))
    await svc.sync_models(api_key="k")
    assert {e.id: e.server_fallback for e in mc.snapshot_entries()} == {
        "claude-sonnet-5-5": True, "claude-haiku-5-5": False, "claude-opus-5": None}
    # 판마다 allowed_fallback_models 가 오는 것은 서버 대체 헤더를 단 베타 목록뿐이다
    # Only the beta listing with the server-fallback header returns allowed_fallback_models per model.
    assert client.listed_with == [{"betas": ["server-side-fallback-2026-07-01"]}]


async def test_refused_probe_fails(world):
    _use(world, _FakeClient(plain=[_message(None, stop_reason="refusal")]))
    refused = await svc.probe_model(_entry("claude-haiku-5-5", "haiku"), api_key="k")
    assert (refused.ok, refused.reason) == (False, "refusal")


def test_a_fallback_served_answer_is_judged_a_refusal():
    # 시험 호출은 대체를 보내지 않지만, 대체가 답한 응답이 오더라도 시험한 판의 답이 아니다(방어)
    # Probes send no fallbacks; should a fallback-served answer arrive anyway, the probed model did not answer.
    judge = svc._judge  # pylint: disable=protected-access
    assert judge(_beta_message(model="claude-opus-5", fallback_ran=True)) == "refusal"


async def test_concurrent_refresh_probes_once(world):
    _record(world, "claude-haiku-4-5")
    client = _use(world, _FakeClient(listing=_LISTING, plain=[_message()]))
    await asyncio.gather(_refresh(world), _refresh(world))
    assert len(client.messages.calls) == 1
    assert len(world.alerts) == 1


async def test_probe_logs_one_cost_row(world):
    _use(world, _FakeClient(plain=[_message()]))
    await svc.probe_model(_entry("claude-haiku-5-5", "haiku"), api_key="k")
    assert world.cost_rows == [{
        "model": "claude-haiku-5-5", "duration_ms": ANY, "input_tokens": 12, "output_tokens": 5,
        "cache_read_tokens": 0, "cache_creation_tokens": 0, "status": "success", "error_type": "",
        "repo_id": None, "user_id": None,
    }]


async def test_probe_cost_row_is_written_off_the_event_loop(world, monkeypatch):
    # 비용 행 INSERT 는 동기 DB 다 — 루프 위에서 쓰면 그동안 프로세스의 모든 요청이 선다(#1701).
    # The cost-row INSERT is sync DB work; on the loop it would stall every request meanwhile (#1701).
    writer_threads = []
    monkeypatch.setattr(svc, "log_claude_api_call", lambda **_row: writer_threads.append(threading.get_ident()))
    _use(world, _FakeClient(plain=[_message()]))
    await svc.probe_model(_entry("claude-haiku-5-5", "haiku"), api_key="k")
    assert len(writer_threads) == 1 and writer_threads[0] != threading.get_ident()


async def test_refresh_reads_the_database_off_the_event_loop(world):
    # 세션 만들기 · 조회 · 닫기가 모두 워커 스레드에서 — 내부 크론 경로가 세션을 직접 열지 않는 근거.
    # Session create, queries and close all happen in a worker thread; why the cron route opens no session itself.
    opened_on = []

    def _factory():
        opened_on.append(threading.get_ident())
        return world.session_factory()

    _record(world, "claude-haiku-5-5")  # 검증판이 이미 최신 — 시험 호출이 끼지 않는다 / no probe
    _use(world, _FakeClient(listing=_LISTING))
    await svc.refresh_catalog(api_key="k", session_factory=_factory)
    assert opened_on and threading.get_ident() not in opened_on


@pytest.mark.parametrize(("control_outcome", "want_reason", "want_rows"), [
    # 지금 판은 통과 → 후보 탓 / the current model passes, so the candidate is to blame
    (_message(model="claude-haiku-4-5"), "rejected",
     [("claude-haiku-5-5", "error", "model_rejected"), ("claude-haiku-4-5", "success", "")]),
    # 지금 판도 400 → 계정 · 요청 쪽 문제(잔액 부족 등) — 후보를 실패로 적지 않는다
    # the current model 400s too: an account/request problem (e.g. low credit), not the candidate
    (_status_error(anthropic.BadRequestError, 400), "transient:BadRequestError",
     [("claude-haiku-5-5", "error", "BadRequestError"), ("claude-haiku-4-5", "error", "probe_control")]),
])
async def test_probe_400_is_settled_only_when_the_current_model_passes(world, control_outcome, want_reason, want_rows):
    client = _use(world, _FakeClient(plain=[_status_error(anthropic.BadRequestError, 400), control_outcome]))
    result = await svc.probe_model(_entry("claude-haiku-5-5", "haiku"), api_key="k", control="claude-haiku-4-5")
    assert (result.ok, result.reason) == (False, want_reason)
    assert [call["model"] for call in client.messages.calls] == ["claude-haiku-5-5", "claude-haiku-4-5"]
    assert sorted((row["model"], row["status"], row["error_type"]) for row in world.cost_rows) == sorted(want_rows)


async def test_account_level_400_does_not_fail_the_candidate(world):
    _record(world, "claude-haiku-4-5")
    _use(world, _FakeClient(listing=_LISTING, plain=[_status_error(anthropic.BadRequestError, 400),
                                                     _status_error(anthropic.BadRequestError, 400)]))
    report = await _refresh(world)
    assert (mc.is_failed("claude-haiku-5-5"), report.failed, world.alerts) == (False, {}, [])


async def test_rejected_probe_is_recorded_as_model_rejected(world):
    # 재시작 뒤 같은 판을 실패로 되살리는 근거 / what lets a restart restore the failure
    _record(world, "claude-haiku-4-5")
    _use(world, _FakeClient(listing=_LISTING, plain=[_status_error(anthropic.BadRequestError, 400),
                                                     _message(model="claude-haiku-4-5")]))
    report = await _refresh(world)
    assert report.failed == {"haiku": "rejected"}
    assert ("claude-haiku-5-5", "error", "model_rejected") in [
        (row["model"], row["status"], row["error_type"]) for row in world.cost_rows]


# ── 운영자 알림 / operator alerts ──

async def test_pinned_deprecation_alert_once(world):
    _record(world, "claude-haiku-4-5")
    _repo(world, "o/pin", "claude-sonnet-4-5")
    listing = [_info("claude-haiku-4-5", "haiku", _d(2025, 10, 1), effort=False),
               _info("claude-sonnet-4-5", "sonnet", _d(2025, 9, 29), lifecycle="deprecated",
                     deprecated=_d(2026, 8, 1), retires=_d(2026, 11, 30))]
    for _ in range(2):
        _use(world, _FakeClient(listing=listing))
        await _refresh(world)
    ((_, _, text),) = world.alerts
    assert "claude-sonnet-4-5" in text and "2026-11-30" in text


async def test_pinned_model_missing_from_listing_alerts_once(world):
    _record(world, "claude-haiku-4-5")
    _record(world, "claude-sonnet-5-5")
    _repo(world, "o/pin", "claude-sonnet-4-6")
    listing = [_info("claude-haiku-4-5", "haiku", _d(2025, 10, 1), effort=False),
               _info("claude-sonnet-5-5", "sonnet", _d(2026, 10, 1))]
    for _ in range(2):
        _use(world, _FakeClient(listing=listing))
        await _refresh(world)
    ((_, _, text),) = world.alerts
    assert "claude-sonnet-4-6" in text and "claude-sonnet-5-5" not in text
    assert mc.resolve_model("claude-sonnet-4-6", default_value="auto:haiku") == "claude-sonnet-4-6"


async def test_sync_failure_alert_at_most_daily(world):
    _record(world, "claude-haiku-5-5")  # 검증판이 이미 최신 — 시험 호출이 끼지 않는다 / already newest, no probes
    counts = []
    for hours, listing_up in ((0, False), (6, False), (12, False), (30, False), (31, False), (32, True), (33, False)):
        world.clock["now"] = NOW + timedelta(hours=hours)
        _use(world, _FakeClient(listing=_LISTING) if listing_up else _FakeClient(
            list_error=anthropic.APIConnectionError(message="down", request=_REQUEST)))
        await _refresh(world)
        counts.append(len(world.alerts))
    assert counts == [0, 1, 1, 2, 2, 2, 2]


async def test_alert_send_failure_does_not_stop_refresh(world, monkeypatch):
    async def _down(*_args):
        raise httpx.ConnectError("telegram down", request=httpx.Request("POST", "https://api.telegram.org"))

    monkeypatch.setattr(svc, "telegram_post_message", _down)
    _record(world, "claude-haiku-4-5")
    _use(world, _FakeClient(listing=_LISTING, plain=[_message()]))
    report = await _refresh(world)
    assert report.promoted == {"haiku": "claude-haiku-5-5"}


# ── 검토 반영(Final) / review fixes ──

async def test_dated_listing_keeps_alias_pins_and_history(world):
    # 목록 API 는 Haiku 4.5 를 날짜 붙은 전체 id 로 준다 — 저장값 · 기록은 별칭(마이그레이션 0050).
    # The listing names Haiku 4.5 by its dated full id; stored values and history use the alias.
    _record(world, "claude-haiku-4-5")
    _repo(world, "o/pin", "claude-haiku-4-5")
    listing = [_info("claude-haiku-4-5-20251001", "haiku", _d(2025, 10, 1), effort=False),
               _info("claude-haiku-5-5", "haiku", _d(2026, 10, 1))]
    _use(world, _FakeClient(listing=listing, plain=[_message()]))
    await _refresh(world)
    assert mc.resolve_model("claude-haiku-4-5", default_value="auto:sonnet") == "claude-haiku-4-5"
    assert (mc.verified_latest("haiku"), mc.previous_verified("haiku")) == ("claude-haiku-5-5", "claude-haiku-4-5")
    # 전환 알림 하나 — 고정 판 «목록 없음» 알림은 없다 / one promotion alert, no absent-pin alert
    ((_, _, text),) = world.alerts
    assert "claude-haiku-4-5</code> →" in text


async def test_retired_pin_is_rerouted_and_alerted(world):
    _record(world, "claude-haiku-4-5")
    _record(world, "claude-sonnet-5-5")
    _repo(world, "o/pin", "claude-sonnet-4-5")
    listing = [_info("claude-haiku-4-5", "haiku", _d(2025, 10, 1), effort=False),
               _info("claude-sonnet-4-5", "sonnet", _d(2025, 9, 29), lifecycle="retired"),
               _info("claude-sonnet-5-5", "sonnet", _d(2026, 10, 1))]
    for _ in range(2):
        _use(world, _FakeClient(listing=listing))
        await _refresh(world)
    assert mc.resolve_model("claude-sonnet-4-5", default_value="auto:haiku") == "claude-sonnet-5-5"
    ((_, _, text),) = world.alerts
    assert "claude-sonnet-4-5" in text and "claude-sonnet-5-5" in text


async def test_settled_probe_failures_survive_restart(world):
    # 거부(400)뿐 아니라 엉뚱한 답 · 거절 · 404 로 판정 난 판도 재시작 뒤 다시 시험 · 알림하지 않는다.
    # Not only rejections: bad output, refusals and 404s stay failed after a restart (no re-probe, no re-alert).
    _record(world, "claude-haiku-4-5", hours_ago=3)
    _record(world, "claude-haiku-5-5", status="error", error_type="probe_bad_output", hours_ago=2)
    client = _use(world, _FakeClient(listing=_LISTING))
    await _refresh(world)
    assert mc.is_failed("claude-haiku-5-5")
    assert (client.messages.calls, world.alerts) == ([], [])


async def test_unrecognised_line_values_are_warned(world, caplog):
    _use(world, _FakeClient(listing=[_info("claude-haiku-5-5", "haiku", _d(2026, 10, 1)),
                                     _info("claude-x-1", "Haiku-Next", _d(2026, 11, 1)),
                                     _info("claude-mythos-5-2", "mythos", _d(2026, 10, 1)),
                                     _info("claude-y-1", None, _d(2026, 11, 1))]))
    with caplog.at_level("WARNING", logger="src.services.model_catalog_service"):
        await svc.sync_models(api_key="k")
    warned = [r.getMessage() for r in caplog.records if "unrecognised line" in r.getMessage()]
    # 아는 다른 계열(mythos) · 계열 없음(null)은 경고하지 않는다 / known other lines and null are not warned
    assert len(warned) == 1 and "Haiku-Next" in warned[0] and "mythos" not in warned[0]


async def test_refresh_log_names_model_count_and_newest(world, caplog):
    _record(world, "claude-haiku-5-5")
    _use(world, _FakeClient(listing=_LISTING))
    with caplog.at_level("INFO", logger="src.services.model_catalog_service"):
        await _refresh(world)
    (line,) = [r.getMessage() for r in caplog.records if r.getMessage().startswith("claude model catalog")]
    assert "models=6" in line and "haiku=claude-haiku-5-5" in line and "newest=claude-haiku-5-5" in line


# witness-corpus: Anthropic 모델 지원 중단 문서의 상태 표기(대문자 Active · Retired 와 legacy 단계) — SDK 의 세 소문자 값 밖
_LIFECYCLE_SPELLINGS = [("Retired", "retired"), ("Active", "active"), ("legacy", "deprecated")]


@pytest.mark.parametrize(("raw", "want"), _LIFECYCLE_SPELLINGS)
async def test_lifecycle_spellings_map_to_catalog_states(world, raw, want):
    # 대소문자는 접어서 읽고, 모르는 단계는 «후보 아님 · 고정 판 그대로» 인 deprecated 로.
    # Case is folded; an unknown stage becomes deprecated (not a candidate, pins kept).
    _use(world, _FakeClient(listing=[_info("claude-opus-z", "opus", _d(2026, 3, 1), lifecycle=raw)]))
    await svc.sync_models(api_key="k")
    (entry,) = mc.snapshot_entries()
    assert entry.lifecycle == want


@pytest.mark.parametrize(("raw", "want"), [(None, "active"), ("", "active"), (" Retired ", "retired")])
async def test_blank_or_padded_lifecycle_values(world, raw, want):
    # 비어 오면 active(SDK 는 필수 값이라 빈 값은 우리 쪽 꼴) · 앞뒤 공백은 접는다 / blank means active; spaces fold
    _use(world, _FakeClient(listing=[_info("claude-opus-z", "opus", _d(2026, 3, 1), lifecycle=raw)]))
    await svc.sync_models(api_key="k")
    (entry,) = mc.snapshot_entries()
    assert entry.lifecycle == want


# ── 경계 동작 / edge behaviours ──

async def test_naive_listing_dates_are_read_as_utc(world):
    _use(world, _FakeClient(listing=[_info("claude-haiku-5-5", "haiku", datetime(2026, 10, 1))]))
    await svc.sync_models(api_key="k")
    (entry,) = mc.snapshot_entries()
    assert entry.created_at == _d(2026, 10, 1)


async def test_history_of_an_unlisted_model_is_not_verified(world):
    # 목록에 없는 판의 성공 기록은 검증판이 되지 않는다 / success rows of an unlisted model do not verify it
    _record(world, "claude-sonnet-4-6")
    _record(world, "claude-haiku-5-5")
    _use(world, _FakeClient(listing=_LISTING))
    await _refresh(world)
    assert (mc.verified_latest("sonnet"), mc.verified_latest("haiku")) == (None, "claude-haiku-5-5")


async def test_empty_or_unparsable_reply_is_bad_output(world):
    _use(world, _FakeClient(plain=[_message(None), _message("not json")]))
    for _ in range(2):
        assert (await svc.probe_model(_entry("claude-haiku-5-5", "haiku"), api_key="k")).reason == "bad_output"


async def test_probe_400_without_a_control_is_not_settled(world):
    _use(world, _FakeClient(plain=[_status_error(anthropic.BadRequestError, 400)]))
    result = await svc.probe_model(_entry("claude-haiku-5-5", "haiku"), api_key="k")
    assert result.reason == "transient:BadRequestError"


async def test_probe_404_settles_the_candidate(world):
    _record(world, "claude-haiku-4-5")
    _use(world, _FakeClient(listing=_LISTING, plain=[_status_error(anthropic.NotFoundError, 404)]))
    report = await _refresh(world)
    assert report.failed == {"haiku": "not_found"} and mc.is_failed("claude-haiku-5-5")


async def test_alerts_are_skipped_without_operator_telegram(world, monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    _record(world, "claude-haiku-4-5")
    _use(world, _FakeClient(listing=_LISTING, plain=[_message()]))
    report = await _refresh(world)
    assert report.promoted == {"haiku": "claude-haiku-5-5"} and not world.alerts


async def test_odd_pins_get_no_alert(world):
    # Claude 꼴이 아닌 고정 id · 계열을 모르는 내려간 판은 옮길 곳이 없어 알리지 않는다(그대로 부른다).
    # A non-Claude pin and a retired pin of an unknown line have nowhere to move, so no alert (kept as is).
    _record(world, "claude-haiku-4-5")
    _repo(world, "o/gpt", "gpt-4o")
    _repo(world, "o/mythos", "claude-mythos-5")
    listing = [_info("claude-haiku-4-5", "haiku", _d(2025, 10, 1), effort=False),
               _info("claude-mythos-5", "mythos", _d(2026, 5, 1), lifecycle="retired")]
    _use(world, _FakeClient(listing=listing))
    await _refresh(world)
    assert not world.alerts
    assert mc.resolve_model("claude-mythos-5", default_value="auto:haiku") == "claude-mythos-5"


async def test_control_for_an_unlisted_current_model_sends_no_effort(world):
    # 지금 판(계열 기본판)이 목록에 없으면 대조 호출은 구조화 출력만 · effort 없이 / unlisted current: no effort
    listing = [_info("claude-haiku-5-5", "haiku", _d(2026, 10, 1))]
    client = _use(world, _FakeClient(listing=listing, plain=[_status_error(anthropic.BadRequestError, 400),
                                                             _message(model="claude-haiku-4-5")]))
    report = await _refresh(world)
    assert report.failed == {"haiku": "rejected"}
    control_call = client.messages.calls[1]
    assert control_call["model"] == "claude-haiku-4-5" and "effort" not in control_call["output_config"]


async def test_a_newer_current_model_is_not_replaced_by_an_older_candidate(world):
    _record(world, "claude-haiku-6-preview")
    listing = [_info("claude-haiku-5-5", "haiku", _d(2026, 10, 1)),
               _info("claude-haiku-6-preview", "haiku", _d(2026, 11, 1), lifecycle="deprecated")]
    client = _use(world, _FakeClient(listing=listing))
    await _refresh(world)
    assert not client.messages.calls and mc.verified_latest("haiku") == "claude-haiku-6-preview"


async def test_sync_reads_the_effort_levels_each_model_takes(world):
    _use(world, _FakeClient(listing=[
        _info("claude-sonnet-5-5", "sonnet", _d(2026, 10, 1), effort_levels={"low", "medium", "high", "xhigh", "max"}),
        _info("claude-haiku-5-5", "haiku", _d(2026, 10, 1), effort_levels={"low", "medium"}),
        _info("claude-haiku-4-5", "haiku", _d(2025, 10, 1), effort=False),
        _info("claude-opus-5", "opus", _d(2026, 6, 1)),  # 단계별 표시 없음 / no per-level flags
    ]))
    await svc.sync_models(api_key="k")
    levels = {e.id: e.effort_levels for e in mc.snapshot_entries()}
    assert levels == {
        "claude-sonnet-5-5": frozenset({"low", "medium", "high", "xhigh", "max"}),
        "claude-haiku-5-5": frozenset({"low", "medium"}),
        "claude-haiku-4-5": frozenset(),
        # 지원만 적히고 단계가 없으면 화면이 고르는 세 단계를 받는다고 본다 / assume the three UI levels
        "claude-opus-5": frozenset({"low", "medium", "high"}),
    }
