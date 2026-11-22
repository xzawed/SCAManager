"""모델 카탈로그 서비스 — 목록 동기화 · 재시작 기준 · 시험 호출 관문 · 운영자 알림 (Issue #1905).

Model catalog service: listing sync, restart baseline, probe gate and operator alerts.

새 판은 작은 JSON 시험 호출을 통과해야 계열의 «검증된 최신» 이 된다 — 그 전까지 auto 값은 이전 판을 부른다.
A new model becomes its line's verified latest only after a small JSON probe passes; until then auto values
keep calling the previous one.
재시작 직후의 기준은 비용 기록이다 — 최근 성공한 판은 검증판으로, 마지막 행이 판정 난 시험 실패인 판은 실패로 되살린다.
After a restart the cost log is the baseline: recently successful models come back verified, models whose last row is
a settled probe failure come back failed.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from html import escape

import anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.i18n.loader import get_text
from src.models.repo_config import RepoConfig
from src.notifier.telegram import telegram_post_message
from src.repositories import claude_api_cost_repo
from src.shared import claude_call as cc
from src.shared import model_catalog as mc
from src.shared.anthropic_caching import first_text_block
from src.shared.claude_metrics import (
    ANTHROPIC_RETRY_AFTER_CAP_PIPELINE_SECONDS,
    log_claude_api_call,
    new_async_anthropic,
)
from src.shared.http_client import HTTPX_SEND_ERRORS
from src.shared.off_loop import run_blocking

logger = logging.getLogger(__name__)

# 목록 API 의 계열 값 가운데 우리가 따르지 않지만 아는 것 — 경고하지 않는다 / known lines we do not follow
_OTHER_KNOWN_LINES = frozenset({"mythos"})
_LIFECYCLES = frozenset({"active", "deprecated", "retired"})
# 재시작 기준으로 읽는 비용 기록의 길이 / how far back the restart baseline reads the cost log
_HISTORY_WINDOW = timedelta(days=30)
# 목록 동기화가 이만큼 잇달아 실패하면 알린다 — 알림은 하루 한 번까지.
# Alert after this many straight listing failures, at most once a day.
_SYNC_ALERT_AFTER_FAILURES = 2
_SYNC_ALERT_INTERVAL = timedelta(hours=24)
_LIST_TIMEOUT_SECONDS = 30.0
_PROBE_TIMEOUT_SECONDS = 60.0
# 생각(thinking)을 켜 두는 판은 생각 토큰도 max_tokens 에 든다 — 짧은 답에도 여유를 둔다.
# Thinking-on models count thinking against max_tokens, so even a tiny answer gets headroom.
_PROBE_MAX_TOKENS = 1024
_PROBE_SYSTEM = [{"type": "text", "text": "Reply with JSON."}]
_PROBE_MESSAGES = [{"role": "user", "content": 'Return {"ok": true}.'}]
_PROBE_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}
# 판에 대한 답이 난 실패 — 다시 시험하지 않는다(그 밖은 다음 주기에 다시).
# Failures that settle the model, so it is not probed again (others are retried next cycle).
_SETTLED_FAILURES = frozenset({"rejected", "not_found", "refusal", "bad_output", "no_structured_outputs"})
# 대조 호출(지금 판)의 실패 표지 — 판정 난 실패로 세지 않아 재시작 뒤 지금 판을 실패로 되살리지 않는다.
# The control call's failure label; never a settled failure, so a restart never marks the current model failed.
_CONTROL_FAILED = "probe_control"


@dataclass(frozen=True)
class ProbeResult:
    """시험 호출 결과 / probe outcome.

    reason: ok · rejected · not_found · refusal · bad_output · truncated · no_structured_outputs · transient:<오류>.
    """

    ok: bool
    reason: str


@dataclass(frozen=True)
class RefreshReport:
    """한 번의 갱신 결과 — 계열별로 올린 판 · 실패 사유 / one refresh: promoted models and failure reasons per line."""

    source: str
    promoted: dict[str, str]
    failed: dict[str, str]


@dataclass
class _ServiceState:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    bootstrapped: bool = False
    # 고정 판 알림은 프로세스마다 한 번(곧 배포마다 한 번) — 따로 저장하지 않는 대가로 받아들인 한계.
    # Pin alerts go out once per process (so once per deploy); the accepted cost of not persisting them.
    alerted_pins: set[str] = field(default_factory=set)
    sync_failures: int = 0
    last_sync_alert_at: datetime | None = None


@dataclass(frozen=True)
class _Usage:
    lines: frozenset[str]
    followers: dict[str, int]
    pinned: tuple[str, ...]


_SVC = _ServiceState()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── 목록 동기화 / listing sync ──

def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def _supported(capabilities, name: str, *, default: bool) -> bool:
    node = capabilities.get(name) if isinstance(capabilities, dict) else getattr(capabilities, name, None)
    flag = node.get("supported") if isinstance(node, dict) else getattr(node, "supported", None)
    return default if flag is None else bool(flag)


_EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")


def _child(node, name: str):
    return node.get(name) if isinstance(node, dict) else getattr(node, name, None)


def _effort_levels(capabilities) -> frozenset[str]:
    """판이 받는 effort 단계 — 지원하지 않으면 빈 집합 · 단계별 표시가 없으면 화면이 고르는 세 단계로 본다.

    The effort levels a model takes: empty when unsupported; the three UI levels when no per-level flags are given.
    """
    if not _supported(capabilities, "effort", default=False):
        return frozenset()
    node = _child(capabilities, "effort")
    levels = frozenset(level for level in _EFFORT_LEVELS if _supported(node, level, default=False))
    return levels or mc.UI_EFFORT_LEVELS


def _to_entry(info, now: datetime) -> mc.ModelEntry:
    """목록 API 의 판 하나를 카탈로그 항목으로 — 내려감 판정은 lifecycle 로만, 날짜는 받은 그대로.

    Map one listed model to a catalog entry; lifecycle is the retirement signal and dates are kept as given.
    """
    # 계열 값처럼 대소문자 · 앞뒤 공백을 접는다 / fold case and surrounding spaces, as for line values
    lifecycle = str(getattr(info, "lifecycle", None) or "active").strip().lower()
    capabilities = getattr(info, "capabilities", None)
    # 서버 대체를 받는 판 = 목록이 받을 대체 판을 적어 둔 판(빈 목록 = 안 받음 · 필드 없음 = 모름).
    # A model takes server fallbacks when the listing names fallback models for it (empty = no; absent = unknown).
    allowed = getattr(info, "allowed_fallback_models", None)
    return mc.ModelEntry(
        id=info.id,
        # 계열이 없다고 온 판에 id 로 계열을 붙이지 않는다(SDK 계약: line 이 null 이면 id 로 짐작하지 말 것).
        # A model listed without a line gets none (SDK contract: do not infer a line from the id).
        line=mc.normalise_line(getattr(info, "line", None)) or "",
        display_name=getattr(info, "display_name", None) or info.id,
        created_at=_aware(getattr(info, "created_at", None)) or now,
        deprecated_at=_aware(getattr(info, "deprecated_at", None)),
        retires_at=_aware(getattr(info, "retires_at", None)),
        # 모르면 구조화 출력은 시험 호출이 판정하고, effort 는 보내지 않는다(받지 않는 판에 보내면 400).
        # When unknown, the probe judges structured outputs and effort is not sent (a 400 where unsupported).
        supports_structured_outputs=_supported(capabilities, "structured_outputs", default=True),
        supports_effort=_supported(capabilities, "effort", default=False),
        # 모르는 lifecycle 값은 후보에서 빼되(active 아님) 고정 판은 옮기지 않는다(retired 아님).
        # An unknown lifecycle value is not a candidate (not active) and does not move pins (not retired).
        lifecycle=lifecycle if lifecycle in _LIFECYCLES else "deprecated",
        server_fallback=None if allowed is None else bool(allowed),
        effort_levels=_effort_levels(capabilities),
    )


def _unrecognised_lines(infos: list) -> list[str]:
    raw_values = {str(raw) for info in infos if (raw := getattr(info, "line", None)) is not None}
    return sorted(raw for raw in raw_values
                  if mc.normalise_line(raw) is None and raw.strip().lower() not in _OTHER_KNOWN_LINES)


async def _list_models(client) -> list:
    """베타 목록(서버 대체 헤더 — 판마다 allowed_fallback_models) · 헤더를 거부하면(400/403) 일반 목록.

    The beta listing with the server-fallback header (allowed_fallback_models per model); the plain listing when
    the header is refused (400/403) — models are still followed and server fallback stays unknown.
    """
    try:
        return [info async for info in client.beta.models.list(betas=[cc.SERVER_FALLBACK_BETA])]
    except (anthropic.BadRequestError, anthropic.PermissionDeniedError) as exc:
        logger.warning("claude beta model listing refused (%s) — reading the plain listing; server fallback unknown",
                       type(exc).__name__)
        return [info async for info in client.models.list()]


async def sync_models(*, api_key: str) -> bool:
    """목록 API 를 읽어 스냅샷을 바꿔 끼운다 — 실패하거나 비어 오면 이전 스냅샷을 그대로 둔다.

    Read the listing API and swap in the snapshot; on failure or an empty listing keep the previous one.
    """
    now = _utcnow()
    try:
        async with new_async_anthropic(
            api_key=api_key, timeout=_LIST_TIMEOUT_SECONDS, max_retries=1, caller="model_catalog",
            retry_after_cap=ANTHROPIC_RETRY_AFTER_CAP_PIPELINE_SECONDS,
        ) as client:
            infos = await _list_models(client)
        entries = [_to_entry(info, now) for info in infos]
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        # 어떤 실패든 이전 목록으로 계속 부른다 — 목록 동기화가 호출 경로를 멈추면 안 된다.
        # Any failure keeps the previous listing; the sync must never stop the call paths.
        logger.warning("claude model listing failed — keeping the %s listing: %s",
                       mc.snapshot_source(), type(exc).__name__)
        return False
    if not entries:
        logger.warning("claude model listing came back empty — keeping the %s listing", mc.snapshot_source())
        return False
    unrecognised = _unrecognised_lines(infos)
    if unrecognised:
        # 정규화가 놓친 계열 값 — 그 판들은 따르지 않는다(값은 API 데이터라 repr 로 · 잘라서).
        # Line values normalisation missed; those models are not followed (API data: repr'd and truncated).
        logger.warning("claude model listing: unrecognised line values %r — those models are not followed",
                       [value[:30] for value in unrecognised[:10]])
    mc.install_snapshot(entries, source="api")
    return True


# ── 재시작 기준 · 쓰는 계열 / restart baseline and lines in use ──

def _error_type(reason: str) -> str:
    if reason == "ok":
        return ""
    if reason == "rejected":
        return mc.MODEL_REJECTED
    if reason.startswith("transient:"):
        return reason.split(":", 1)[1]
    return f"probe_{reason}"


# 재시작 뒤 실패로 되살리는 비용 행 표지 — 판정 난 실패에서 파생한다(행을 남기지 않는 구조화 출력 미지원은 빠진다).
# Cost-row labels restored as failed after a restart, derived from the settled failures (rowless ones drop out).
_SETTLED_ERROR_TYPES = frozenset(_error_type(reason) for reason in _SETTLED_FAILURES - {"no_structured_outputs"})


def bootstrap_from_history(db: Session) -> None:
    """비용 기록으로 검증판을 되살린다 — 계열마다 최근 성공한 판을 출시 순서대로, 판정 난 시험 실패가 마지막인 판은 실패로.

    Rebuild verified models from the cost log: each line's recently successful models in release order; models whose
    last row is a settled probe failure become failed. History keeps the id that was called (an alias, usually).
    """
    since = _utcnow() - _HISTORY_WINDOW
    by_line: dict[str, list[tuple[mc.ModelEntry, str]]] = {}
    for model_id, _last_success in claude_api_cost_repo.recent_success_models(db, since=since):
        entry = mc.entry_for(model_id)
        if entry is None or entry.line not in mc.KNOWN_LINES or entry.lifecycle == "retired":
            continue
        by_line.setdefault(entry.line, []).append((entry, model_id))
    for line, pairs in by_line.items():
        for _entry, model_id in sorted(pairs, key=lambda pair: pair[0].created_at):
            mc.set_verified(line, model_id)
    for model_id in claude_api_cost_repo.failed_models(db, since=since, error_types=_SETTLED_ERROR_TYPES):
        mc.mark_failed(model_id)


def _stored_review_values(db: Session) -> list[str]:
    """AI 를 켠 리포의 실효 리뷰 모델 값(비어 있으면 기본값) / effective review values of AI-enabled repos."""
    stored = db.scalars(select(RepoConfig.review_model).where(RepoConfig.ai_review_enabled.is_(True))).all()
    return [value or settings.claude_review_model for value in stored]


def _choice(value: str) -> mc.ModelChoice | None:
    try:
        return mc.parse_model_value(value)
    except ValueError:
        # 읽을 수 없는 저장값(모르는 계열)은 건너뛴다 — 호출 경로에서 따로 드러난다.
        # Skip an unreadable stored value (unknown line); the call path surfaces it on its own.
        return None


def _lines_of(values: list[str]) -> frozenset[str]:
    lines: set[str] = set()
    for value in values:
        choice = _choice(value)
        if choice is None or choice.kind == "default":
            continue
        line = choice.line if choice.kind == "auto" else mc.line_of(choice.model_id or "")
        if line in mc.KNOWN_LINES:
            lines.add(line)
    return frozenset(lines)


def _read_usage(session_factory) -> _Usage:
    """워커 스레드에서 — 처음 한 번 재시작 기준을 세우고, 쓰는 계열 · 따르는 리포 수 · 고정 판을 값으로 읽는다.

    Worker thread: build the restart baseline once, then read lines in use, follower counts and pins as values.
    """
    with session_factory() as db:
        if not _SVC.bootstrapped:
            bootstrap_from_history(db)
            _SVC.bootstrapped = True
        repo_values = _stored_review_values(db)
    values = repo_values + [settings.claude_review_model, settings.claude_insight_model]
    choices = [c for c in map(_choice, values) if c is not None]
    repo_choices = [c for c in map(_choice, repo_values) if c is not None]
    return _Usage(
        lines=_lines_of(values),
        followers=dict(Counter(c.line for c in repo_choices if c.kind == "auto" and c.line)),
        pinned=tuple(sorted({c.model_id for c in choices if c.kind == "pinned" and c.model_id})),
    )


# ── 시험 호출 / probe ──

def _fallback_served(response) -> bool:
    iterations = getattr(getattr(response, "usage", None), "iterations", None) or []
    return any(getattr(item, "type", None) == "fallback_message" for item in iterations)


def _judge(response) -> str:
    stop_reason = getattr(response, "stop_reason", None)
    # 대체 모델이 답했다 = 시험한 판은 거절했다 / a fallback answered, so the probed model declined
    if stop_reason == "refusal" or _fallback_served(response):
        return "refusal"
    if stop_reason == "max_tokens":
        return "truncated"
    try:
        payload = json.loads(first_text_block(response))
    except ValueError:
        return "bad_output"
    return "ok" if payload == {"ok": True} else "bad_output"


def _tokens(usage, name: str) -> int:
    return int(getattr(usage, name, 0) or 0)


async def _write_cost_row(model_id: str, response, *, ok: bool, error_type: str, started: float) -> None:
    usage = getattr(response, "usage", None)
    # 비용 행 INSERT 는 동기 DB 다 — 루프 밖에서(#1701). / The cost-row INSERT is sync DB work: off the loop.
    await run_blocking(
        log_claude_api_call,
        model=model_id,
        duration_ms=(time.monotonic() - started) * 1000.0,
        input_tokens=_tokens(usage, "input_tokens"),
        output_tokens=_tokens(usage, "output_tokens"),
        cache_read_tokens=_tokens(usage, "cache_read_input_tokens"),
        cache_creation_tokens=_tokens(usage, "cache_creation_input_tokens"),
        status="success" if ok else "error",
        error_type=error_type,
        repo_id=None,
        user_id=None,
    )


async def _send_probe(client, model: str, *, entry: mc.ModelEntry | None = None):
    return await cc.send_once(client, model, max_tokens=_PROBE_MAX_TOKENS, system=_PROBE_SYSTEM,
                              schema=_PROBE_SCHEMA, messages=_PROBE_MESSAGES, entry=entry,
                              effort=settings.claude_call_effort)


async def _control_passes(client, control: str | None) -> bool:
    """후보가 400 이면 지금 판에 같은 꼴을 보낸다 — 지금 판도 실패하면 판이 아니라 계정 · 요청 쪽 문제다(잔액 부족 등).

    When the candidate gets a 400, send the same shape to the current model; if that fails too, the cause is the
    account or request (e.g. low credit), not the candidate. The control call writes its own cost row.
    """
    if control is None:
        return False
    started = time.monotonic()
    response = None
    try:
        response = await _send_probe(client, control)
        ok = _judge(response) == "ok"
    except anthropic.APIError:
        ok = False
    await _write_cost_row(control, response, ok=ok, error_type="" if ok else _CONTROL_FAILED, started=started)
    return ok


async def probe_model(entry: mc.ModelEntry, *, api_key: str, control: str | None = None) -> ProbeResult:
    """판 하나에 작은 JSON 요청을 실제 호출과 같은 꼴(send_once)로 보낸다 — 호출마다 비용 행 1개.

    Send one small JSON request in the real calls' shape (send_once); one cost row per call.
    A 400 counts against the model only when the same shape passes on `control` (the current model's id).
    """
    if not entry.supports_structured_outputs:
        return ProbeResult(ok=False, reason="no_structured_outputs")
    started = time.monotonic()
    response = None
    try:
        async with new_async_anthropic(
            api_key=api_key, timeout=_PROBE_TIMEOUT_SECONDS, max_retries=1, caller="model_probe",
            retry_after_cap=ANTHROPIC_RETRY_AFTER_CAP_PIPELINE_SECONDS,
        ) as client:
            try:
                response = await _send_probe(client, entry.id, entry=entry)
                reason = _judge(response)
            except anthropic.BadRequestError:
                reason = "rejected" if await _control_passes(client, control) else "transient:BadRequestError"
    except anthropic.NotFoundError:
        reason = "not_found"
    except anthropic.APIError as exc:
        reason = f"transient:{type(exc).__name__}"
    await _write_cost_row(entry.id, response, ok=reason == "ok", error_type=_error_type(reason), started=started)
    return ProbeResult(ok=reason == "ok", reason=reason)


# ── 운영자 알림 / operator alerts ──

async def notify_operator(text: str) -> None:
    """운영자 Telegram 으로 보낸다 — 설정이 없거나 보내기가 실패해도 갱신은 계속된다.

    Send to the operator's Telegram; missing settings or a failed send never stop the refresh.
    """
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        logger.info("claude model catalog alert skipped — operator telegram is not configured")
        return
    try:
        await telegram_post_message(
            settings.telegram_bot_token, settings.telegram_chat_id, {"text": text, "parse_mode": "HTML"},
        )
    except (*HTTPX_SEND_ERRORS, KeyError, ValueError) as exc:
        logger.warning("claude model catalog telegram alert failed: %s", type(exc).__name__)


async def _note_sync_result(synced: bool) -> None:
    if synced:
        _SVC.sync_failures = 0
        return
    _SVC.sync_failures += 1
    now = _utcnow()
    last = _SVC.last_sync_alert_at
    if _SVC.sync_failures < _SYNC_ALERT_AFTER_FAILURES or (last is not None and now - last < _SYNC_ALERT_INTERVAL):
        return
    _SVC.last_sync_alert_at = now
    await notify_operator(get_text("notifier.models.sync_failed", settings.default_locale,
                                   count=_SVC.sync_failures, source=mc.snapshot_source()))


def _pin_alert_text(model_id: str, language: str) -> str | None:
    entry = mc.entry_for(model_id)
    if entry is None:
        # 목록에 없는 고정 판은 그대로 부른다 — 대체 목록만 있거나 Claude 꼴이 아닌 id 면 알리지 않는다.
        # An absent pin is kept as is; no alert with only the fallback listing or for a non-Claude-shaped id.
        if mc.snapshot_source() != "api" or mc.line_of(model_id) is None:
            return None
        return get_text("notifier.models.pinned_missing", language, model=escape(model_id))
    if entry.lifecycle == "retired":
        moved = mc.resolve_model(model_id, default_value=model_id)
        if moved == model_id:
            return None
        return get_text("notifier.models.pinned_retired", language, model=escape(model_id), moved=escape(moved))
    if entry.lifecycle == "deprecated":
        date = entry.retires_at.date().isoformat() if entry.retires_at else "—"
        return get_text("notifier.models.pinned_retiring", language, model=escape(model_id), date=date,
                        line=escape(entry.line or "—"))
    return None


async def _alert_pins(pinned: tuple[str, ...]) -> None:
    for model_id in pinned:
        if model_id in _SVC.alerted_pins:
            continue
        text = _pin_alert_text(model_id, settings.default_locale)
        if text is None:
            continue
        _SVC.alerted_pins.add(model_id)
        await notify_operator(text)


# ── 갱신 / refresh ──

def _current(line: str) -> str:
    return mc.verified_latest(line) or mc.FALLBACK_DEFAULT_BY_LINE[line]


async def _advance_line(line: str, *, api_key: str, followers: int) -> tuple[str, str] | None:
    """계열의 새 판이 지금 판보다 새면 시험하고, 통과하면 올린다 — (결과, 값) 또는 None.

    Probe the line's newer model and promote it on a pass; returns (outcome, value) or None.
    """
    candidate = mc.latest_candidate(line)
    current = _current(line)
    if candidate is None or candidate.id == current or mc.is_failed(candidate.id):
        return None
    current_entry = mc.entry_for(current)
    if current_entry is not None and current_entry.created_at >= candidate.created_at:
        return None
    result = await probe_model(candidate, api_key=api_key, control=current)
    language = settings.default_locale
    if result.ok:
        mc.set_verified(line, candidate.id)
        await notify_operator(get_text("notifier.models.promoted", language, line=line, old=escape(current),
                                       new=escape(candidate.id), count=followers))
        return "promoted", candidate.id
    if result.reason not in _SETTLED_FAILURES:
        logger.warning("claude model probe for %s did not settle (%s) — trying again next cycle",
                       candidate.id, result.reason)
        return None
    mc.mark_failed(candidate.id)
    await notify_operator(get_text("notifier.models.probe_failed", language, line=line, model=escape(candidate.id),
                                   reason=escape(result.reason), current=escape(current)))
    return "failed", result.reason


def _line_summary(line: str) -> str:
    newest = mc.latest_candidate(line)
    return f"{line}={_current(line)} newest={newest.id if newest else '-'}"


async def refresh_catalog(*, api_key: str, session_factory) -> RefreshReport:
    """목록을 읽고, 쓰는 계열마다 새 판을 시험해 통과하면 올린다 — 한 번에 하나만 돈다.

    Sync the listing, probe each in-use line's newer model and promote it on a pass; one run at a time.
    """
    async with _SVC.lock:
        await _note_sync_result(await sync_models(api_key=api_key))
        usage = await run_blocking(_read_usage, session_factory)
        promoted: dict[str, str] = {}
        failed: dict[str, str] = {}
        for line in sorted(usage.lines):
            outcome = await _advance_line(line, api_key=api_key, followers=usage.followers.get(line, 0))
            if outcome is None:
                continue
            kind, value = outcome
            if kind == "promoted":
                promoted[line] = value
            else:
                failed[line] = value
        await _alert_pins(usage.pinned)
        # 첫 동기화 뒤 이 한 줄로 목록의 꼴(모델 수 · 계열별 최신)을 확인한다 / the first sync is checked from this line
        logger.info("claude model catalog — source=%s models=%d %s", mc.snapshot_source(), len(mc.snapshot_entries()),
                    " ".join(_line_summary(line) for line in sorted(usage.lines)) or "(no lines in use)")
        return RefreshReport(source=mc.snapshot_source(), promoted=promoted, failed=failed)
