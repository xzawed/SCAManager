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

from src.config import settings
from src.database import Base
from src.models.claude_api_call import ClaudeApiCall  # noqa: F401  (Base.metadata 등록 / register on metadata)
from src.models.repo_config import RepoConfig
from src.repositories import claude_api_cost_repo
from src.services import model_catalog_service as svc
from src.shared import model_catalog as mc

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _d(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


def _info(model_id, line, created, *, lifecycle="active", deprecated=None, retires=None,
          effort=True, structured=True, with_capabilities=True):
    fields = {"id": model_id, "type": "model", "display_name": model_id, "created_at": created, "line": line,
              "lifecycle": lifecycle, "deprecated_at": deprecated, "retires_at": retires}
    if with_capabilities:
        fields["capabilities"] = {"effort": {"supported": effort}, "structured_outputs": {"supported": structured}}
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


def _entry(model_id: str, line: str, *, effort: bool = True, structured: bool = True) -> mc.ModelEntry:
    return mc.ModelEntry(id=model_id, line=line, display_name=model_id, created_at=_d(2026, 10, 1),
                         deprecated_at=None, retires_at=None,
                         supports_structured_outputs=structured, supports_effort=effort)


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
    def __init__(self, *, listing=(), list_error=None, plain=(), beta=()):
        self.messages = _FakeCreate(plain)
        self.beta = SimpleNamespace(messages=_FakeCreate(beta))
        self.models = SimpleNamespace(list=lambda: _AsyncListing(listing, list_error))

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
    ]))
    assert await svc.sync_models(api_key="k") is True
    got = {e.id: e for e in mc.snapshot_entries()}
    assert mc.snapshot_source() == "api"
    assert (got["claude-haiku-4-5"].supports_effort, got["claude-haiku-4-5"].supports_structured_outputs) == (False, True)
    assert (got["claude-sonnet-4-5"].deprecated_at, got["claude-sonnet-4-5"].retires_at) == (_d(2026, 8, 1), _d(2026, 11, 30))
    # 날짜 없이 retired 로만 온 판도 내려간 판이다 / a model that is only marked retired counts as retired
    assert (got["claude-opus-4-1"].deprecated_at, got["claude-opus-4-1"].retires_at) == (NOW, NOW)
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
    assert mc.latest_candidate("opus", now=NOW) is None
    assert mc.latest_candidate("haiku", now=NOW).id == "claude-haiku-5-5"


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
    assert client.beta.messages.calls == []
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
    assert again.messages.calls == [] and len(world.alerts) == 1


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
    first, second = client.messages.calls
    assert first["output_config"]["effort"] == "low"
    assert "effort" not in second["output_config"]
    assert second["output_config"]["format"]["type"] == "json_schema"
    assert second["model"] == "claude-haiku-4-5"


async def test_probe_rejects_model_without_structured_outputs(world):
    client = _use(world, _FakeClient())
    result = await svc.probe_model(_entry("claude-opus-x", "opus", structured=False), api_key="k")
    assert (result.ok, result.reason) == (False, "no_structured_outputs")
    assert client.messages.calls == [] and client.beta.messages.calls == []


async def test_probe_server_fallback_400_retries_without_fallbacks(world):
    client = _use(world, _FakeClient(beta=[_status_error(anthropic.BadRequestError, 400)],
                                     plain=[_message(model="claude-sonnet-5")]))
    result = await svc.probe_model(_entry("claude-sonnet-5", "sonnet"), api_key="k")
    assert (result.ok, result.server_fallback_ok) == (True, False)
    (beta_call,) = client.beta.messages.calls
    assert (beta_call["betas"], beta_call["fallbacks"]) == (["server-side-fallback-2026-07-01"], "default")
    (plain_call,) = client.messages.calls
    assert "fallbacks" not in plain_call and plain_call["model"] == "claude-sonnet-5"
    assert len(world.cost_rows) == 1


async def test_refresh_records_accepted_server_fallback(world, monkeypatch):
    monkeypatch.setattr(settings, "claude_review_model", "claude-sonnet-5")
    monkeypatch.setattr(settings, "claude_insight_model", "claude-sonnet-5")
    _record(world, "claude-sonnet-5")
    _use(world, _FakeClient(listing=_LISTING, beta=[_beta_message()]))
    await _refresh(world)
    assert mc.verified_latest("sonnet") == "claude-sonnet-5-5"
    assert mc.server_fallback_supported("claude-sonnet-5-5") is True


async def test_refused_probe_fails_even_when_a_fallback_answered(world):
    _use(world, _FakeClient(beta=[_beta_message(model="claude-opus-5", fallback_ran=True)],
                            plain=[_message(None, stop_reason="refusal")]))
    served_by_fallback = await svc.probe_model(_entry("claude-sonnet-5-5", "sonnet"), api_key="k")
    assert (served_by_fallback.ok, served_by_fallback.reason, served_by_fallback.server_fallback_ok) == (False, "refusal", True)
    refused = await svc.probe_model(_entry("claude-haiku-5-5", "haiku"), api_key="k")
    assert (refused.ok, refused.reason) == (False, "refusal")


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


async def test_rejected_probe_is_recorded_as_model_rejected(world):
    # 재시작 뒤 rejected_models 가 같은 판을 실패로 되살리는 근거 / what lets a restart restore the failure
    _use(world, _FakeClient(plain=[_status_error(anthropic.BadRequestError, 400)]))
    result = await svc.probe_model(_entry("claude-haiku-5-5", "haiku"), api_key="k")
    assert (result.ok, result.reason) == (False, "rejected")
    assert [(row["status"], row["error_type"]) for row in world.cost_rows] == [("error", "model_rejected")]


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
    assert "claude-sonnet-4-6" in text and "claude-sonnet-5-5" in text


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
