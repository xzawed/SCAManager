"""메모리 모델 카탈로그 — 저장된 모델 값(계열 · 판 고정 · 기본값)을 부를 판 id 로 해석한다 (Issue #1905).

In-memory model catalog: resolves a stored model value (line, pinned id or default) to a callable model id.

상태는 불변 객체 하나(`_STATE`)다 — 읽기는 참조 하나를 집어 쓰고, 쓰기만 잠금 아래에서 새 객체로 바꿔 끼운다.
The state is one immutable object (`_STATE`): readers take a single reference; writers swap in a new one under a lock.
`auto:<line>` 은 그 계열에서 시험 호출을 통과한(검증된) 가장 새 판만 부른다 — 목록에 새로 보인 판은 검증 전까지 쓰지 않는다.
`auto:<line>` only calls the newest verified model of its line; a newly listed model waits until it passes the probe.
"""
from __future__ import annotations

import logging
import re
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Literal

logger = logging.getLogger(__name__)

KNOWN_LINES = frozenset({"haiku", "sonnet", "opus", "fable"})
# 판이 우리 요청을 거부했다(400 — 지금 판은 같은 요청에 답함)는 비용 행 표지 — 재시작 뒤 그 판을 다시 실패로 올린다.
# Cost-row label for a model that rejected our request (the current model answered the same one); a restart
# marks it failed again.
MODEL_REJECTED = "model_rejected"

_AUTO_PREFIX = "auto:"
_CLAUDE_PREFIX = "claude-"
# 판 id 꼴에서 계열을 읽는다 — 목록에 없는 id(내린 판 등)일 때만 쓴다.
# Reads the line from the id shape; used only for ids absent from the listing (e.g. retired ones).
_LINE_FROM_ID = re.compile(r"^claude-(" + "|".join(sorted(KNOWN_LINES)) + r")-")
# 날짜 붙은 전체 id(`claude-haiku-4-5-20251001`)의 별칭 = 접미사를 뗀 id — 저장값 · 기록은 별칭이다.
# The alias of a dated full id is the id without the date suffix; stored values and history use aliases.
_DATED_SUFFIX = re.compile(r"-\d{8}$")

# 목록 · 기록 · 검증이 모두 없을 때 계열마다 부르는 판 — 지금 선택지(`src/constants.py` CLAUDE_MODELS)의 판이다.
# Per-line model used only when listing, history and verification are all absent: today's selectable models.
FALLBACK_DEFAULT_BY_LINE: Mapping[str, str] = MappingProxyType({
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-5",
    "opus": "claude-opus-5",
    "fable": "claude-fable-5-1",
})


@dataclass(frozen=True)
class ModelEntry:  # pylint: disable=too-many-instance-attributes
    """목록 API 의 판 하나 — 해석과 시험 호출이 쓰는 필드만.

    One model from the listing API, with only the fields resolution and probing use.
    """

    id: str
    line: str
    display_name: str
    created_at: datetime
    deprecated_at: datetime | None
    retires_at: datetime | None
    supports_structured_outputs: bool
    supports_effort: bool
    # active · deprecated · retired — 내려감 판정은 이것으로만(SDK 계약) / the retirement signal (SDK contract)
    lifecycle: str = "active"
    # 서버 대체(fallbacks) 를 받는가 — 목록 API 의 allowed_fallback_models(빈 목록 = 안 받음) · None = 모름(보내지 않는다).
    # Whether the model takes server-side fallbacks: the listing's allowed_fallback_models (empty = no); None = unknown.
    server_fallback: bool | None = None


@dataclass(frozen=True)
class ModelChoice:
    """저장값을 읽은 결과 — 계열(auto) · 판 고정(pinned) · 기본값(default).

    A parsed stored value: a line (auto), a pinned id, or the default.
    """

    kind: Literal["auto", "pinned", "default"]
    line: str | None = None
    model_id: str | None = None


def _fallback(model_id: str, line: str, display_name: str, created: tuple[int, int, int], *,
              effort: bool) -> ModelEntry:
    return ModelEntry(
        id=model_id, line=line, display_name=display_name, created_at=datetime(*created, tzinfo=timezone.utc),
        deprecated_at=None, retires_at=None, supports_structured_outputs=True, supports_effort=effort,
    )


# 목록 API 를 못 읽을 때의 대체 목록. created_at 은 계열 안 순서만 정하는 자리값이다 — 실제 값은 목록 API 가 준다.
# Fallback listing for when the listing API is unreachable; created_at only orders a line (the API has real values).
# Haiku 4.5 는 effort 인자를 받지 않는다(보내면 400) — 나머지 판은 받는다.
# Haiku 4.5 takes no effort parameter (a 400 if sent); the other models do.
FALLBACK_CATALOG: tuple[ModelEntry, ...] = (
    _fallback("claude-haiku-4-5", "haiku", "Claude Haiku 4.5", (2025, 10, 1), effort=False),
    _fallback("claude-haiku-5-5", "haiku", "Claude Haiku 5.5", (2026, 10, 1), effort=True),
    _fallback("claude-sonnet-5", "sonnet", "Claude Sonnet 5", (2026, 4, 1), effort=True),
    _fallback("claude-sonnet-5-5", "sonnet", "Claude Sonnet 5.5", (2026, 10, 1), effort=True),
    _fallback("claude-opus-5", "opus", "Claude Opus 5", (2026, 6, 1), effort=True),
    _fallback("claude-opus-5-5", "opus", "Claude Opus 5.5", (2026, 10, 1), effort=True),
    _fallback("claude-fable-5-1", "fable", "Claude Fable 5.1", (2026, 7, 1), effort=True),
    _fallback("claude-fable-5-2", "fable", "Claude Fable 5.2", (2026, 10, 1), effort=True),
)


@dataclass(frozen=True, eq=False)
class _CatalogState:
    entries: tuple[ModelEntry, ...]
    by_id: Mapping[str, ModelEntry]
    source: str
    # 계열 → 검증된 순서(오래된 것 → 새것) / line -> verification order (oldest -> newest)
    verified: Mapping[str, tuple[str, ...]]
    failed: frozenset[str]
    # 서버 대체 인자를 실제 호출에서 400 으로 거부한 판 — 이 프로세스 동안 대체 없이 부른다(목록을 다시 읽어도 유지).
    # Models that 400'd on the fallback arguments in a real call; called plainly for the rest of the process.
    no_fallbacks: frozenset[str] = frozenset()


def _index(entries: tuple[ModelEntry, ...]) -> Mapping[str, ModelEntry]:
    """id 와 별칭(날짜 접미사를 뗀 id) 둘 다로 찾게 — 같은 글자의 실제 id 가 있으면 그것이 이긴다.

    Index by id and by alias (id without the date suffix); an entry whose real id is that string wins.
    """
    index = {e.id: e for e in entries}
    for entry in entries:
        index.setdefault(_DATED_SUFFIX.sub("", entry.id), entry)
    return MappingProxyType(index)


def _initial_state() -> _CatalogState:
    return _CatalogState(
        entries=FALLBACK_CATALOG, by_id=_index(FALLBACK_CATALOG), source="fallback",
        verified=MappingProxyType({}), failed=frozenset(),
    )


_STATE = _initial_state()
_WRITE_LOCK = threading.Lock()


def normalise_line(raw: str | None) -> str | None:
    """계열 이름을 정규화한다 — 소문자 · 앞 `claude-` 제거 · 아는 계열이 아니면 None.

    Normalise a line name: lowercase, strip a leading `claude-`, None unless it is a known line.
    """
    if raw is None:
        return None
    text = raw.strip().lower()
    if text.startswith(_CLAUDE_PREFIX):
        text = text[len(_CLAUDE_PREFIX):]
    return text if text in KNOWN_LINES else None


def parse_model_value(value: str | None) -> ModelChoice:
    """저장값을 읽는다 — 빈 값은 기본값, `auto:<line>` 은 계열(모르는 계열이면 ValueError), 그 밖은 판 고정.

    Parse a stored value: blank is the default, `auto:<line>` a line (ValueError if unknown), anything else a pin.
    """
    text = (value or "").strip()
    if not text:
        return ModelChoice("default")
    if text.lower().startswith(_AUTO_PREFIX):
        line = normalise_line(text[len(_AUTO_PREFIX):])
        if line is None:
            raise ValueError(f"unknown model line in {text!r}")
        return ModelChoice("auto", line=line)
    return ModelChoice("pinned", model_id=text)


def _line_from_id(model_id: str) -> str | None:
    match = _LINE_FROM_ID.match(model_id)
    return match.group(1) if match else None


def line_of(model_id: str) -> str | None:
    """판의 계열 — 목록에 있으면 목록 값, 없으면 id 꼴로 읽는다.

    A model's line: the listing's value when listed, otherwise read from the id shape.
    """
    entry = _STATE.by_id.get(model_id)
    return entry.line if entry is not None else _line_from_id(model_id)


def install_snapshot(entries: Sequence[ModelEntry], *, source: Literal["api", "fallback"]) -> None:
    """목록을 통째로 바꿔 끼운다.

    Swap in a whole new listing.
    """
    global _STATE  # pylint: disable=global-statement
    snapshot = tuple(entries)
    with _WRITE_LOCK:
        _STATE = replace(_STATE, entries=snapshot, by_id=_index(snapshot), source=source)


def snapshot_entries() -> tuple[ModelEntry, ...]:
    """지금 목록 / the current listing."""
    return _STATE.entries


def entry_for(model_id: str) -> ModelEntry | None:
    """지금 목록의 그 판(없으면 None) / the listed entry for an id, or None."""
    return _STATE.by_id.get(model_id)


def snapshot_source() -> str:
    """지금 목록의 출처(api · fallback) / where the current listing came from."""
    return _STATE.source


def latest_candidate(line: str) -> ModelEntry | None:
    """계열에서 active 이고 구조화 출력을 받는(우리 호출 꼴로 부를 수 있는) 가장 새 판 — 아직 검증 전일 수 있다.

    The newest active model of a line that takes structured outputs (our call shape); it may not be verified yet.
    """
    candidates = [
        e for e in _STATE.entries
        if e.line == line and e.lifecycle == "active" and e.supports_structured_outputs
    ]
    return max(candidates, key=lambda e: e.created_at, default=None)


def _good_history(state: _CatalogState, line: str) -> list[str]:
    return [m for m in state.verified.get(line, ()) if m not in state.failed]


def verified_latest(line: str) -> str | None:
    """계열의 가장 최근 검증판(실패 제외) / the line's most recently verified model, failures excluded."""
    good = _good_history(_STATE, line)
    return good[-1] if good else None


def previous_verified(line: str) -> str | None:
    """그 바로 앞 검증판 / the verified model before that."""
    good = _good_history(_STATE, line)
    return good[-2] if len(good) >= 2 else None


def set_verified(line: str, model_id: str) -> None:
    """판을 그 계열의 가장 최근 검증판으로 올린다(이미 있으면 맨 뒤로 옮긴다).

    Record a model as its line's most recently verified one (moved to the end if already present).
    """
    global _STATE  # pylint: disable=global-statement
    with _WRITE_LOCK:
        verified = dict(_STATE.verified)
        verified[line] = tuple(m for m in verified.get(line, ()) if m != model_id) + (model_id,)
        _STATE = replace(_STATE, verified=MappingProxyType(verified))


def mark_failed(model_id: str) -> None:
    """판을 실패로 적는다 — 이 프로세스에서 다시는 auto 로 부르지 않는다.

    Mark a model as failed: auto resolution never returns it again in this process.
    """
    global _STATE  # pylint: disable=global-statement
    with _WRITE_LOCK:
        _STATE = replace(_STATE, failed=_STATE.failed | {model_id})


def is_failed(model_id: str) -> bool:
    """실패로 적힌 판인가 / whether the model is marked failed."""
    return model_id in _STATE.failed


def refuse_fallbacks(model_id: str) -> None:
    """판이 서버 대체 인자를 거부했다 — 이 프로세스에서는 그 판에 대체를 보내지 않는다.

    The model rejected the server-fallback arguments; send it none for the rest of this process.
    """
    global _STATE  # pylint: disable=global-statement
    with _WRITE_LOCK:
        _STATE = replace(_STATE, no_fallbacks=_STATE.no_fallbacks | {model_id})


def takes_fallbacks(model_id: str) -> bool:
    """서버 대체를 보낼 판인가 — 목록이 받을 대체 판을 적어 두었고(빈 목록 · 모름이 아니고) 여기서 거부한 적이 없다.

    Whether to send server fallbacks: the listing names fallback models for it and it has not refused them here.
    """
    state = _STATE
    entry = state.by_id.get(model_id)
    return entry is not None and bool(entry.server_fallback) and model_id not in state.no_fallbacks


def _resolve_line(state: _CatalogState, line: str) -> str:
    good = _good_history(state, line)
    return good[-1] if good else FALLBACK_DEFAULT_BY_LINE[line]


def _resolve_pinned(state: _CatalogState, model_id: str) -> str:
    # 목록에 없다 ≠ 내려갔다(내려간 판도 기록으로 목록에 남는다) — 그대로 부른다. 내려감 판정은 lifecycle 로만
    # (SDK 계약: 폐기 예정 판의 지난 retires_at 은 «늦어진 은퇴» 다).
    # Absent is not retired (retired models stay listed), so keep it; only lifecycle says retired (SDK contract).
    entry = state.by_id.get(model_id)
    if entry is None or entry.lifecycle != "retired" or entry.line not in KNOWN_LINES:
        return model_id
    return _resolve_line(state, entry.line)


def resolve_model(value: str | None, *, default_value: str) -> str:
    """저장값을 부를 판 id 로 바꾼다 — 빈 값은 default_value 로, 내려간 고정 판은 그 계열의 검증판으로.

    Turn a stored value into a model id: blank uses default_value; a retired pin moves to its line's verified model.
    날짜 붙은 전체 id 로 목록에 오른 판은 별칭으로도 찾는다. / Dated listed ids are also found by their alias.
    읽을 수 없는 저장값(모르는 계열)은 경고 한 줄 뒤 기본값으로 — 호출을 깨지 않는다. default_value 가 그렇다면 설정
    오류라 ValueError 를 올린다(설정은 기동에서 검증된다).
    An unreadable stored value (unknown line) logs a warning and uses the default instead of breaking the call;
    an unreadable default_value is a configuration error and raises (settings are validated at startup).
    """
    state = _STATE
    try:
        choice = parse_model_value(value)
    except ValueError:
        logger.warning("unreadable stored model value %r — using the default", (value or "")[:40])
        choice = ModelChoice("default")
    if choice.kind == "default":
        choice = parse_model_value(default_value)
        if choice.kind == "default":
            raise ValueError("default_value is empty")
    if choice.kind == "auto":
        return _resolve_line(state, choice.line or "")
    return _resolve_pinned(state, choice.model_id or "")
