"""대시보드 인사이트 서술 — 출력 상한에서 멈춘 응답을 알아본다 (#1702, 리포 쪽 #1700 과 같은 처리).

수정 전: `max_tokens=1500` 으로 부르고 `stop_reason` 을 보지 않았다. 잘린 본문은 `parse_error` 카드가
됐지만 비용 행은 `success` 였고 경고도 없었다 — 상한에 닿았다는 신호가 어디에도 남지 않았다.
상한에서 멈췄어도 4 카드로 닫힌 본문은 success + 경고 1건, 읽을 수 없으면 비용 행에 `max_tokens`.
카드 status 는 새로 만들지 않고 기존 `parse_error` 그대로다. 리포 쪽처럼 **실제 SDK** 가 응답을
`Message` 로 만든다 — 전송만 `httpx2.MockTransport` 다.

A max_tokens stop with a closed 4-card body is kept with one warning; an unreadable one logs
`max_tokens` on the cost row while the card stays `parse_error`. Real SDK, faked transport only.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import anthropic
import httpx2
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models.analysis import Analysis
from src.models.claude_api_call import ClaudeApiCall
from src.models.insight_narrative_cache import InsightNarrativeCache
from src.models.repository import Repository
from src.models.user import User
from src.services import dashboard_service

# KPI 비용 집계가 claude_api_calls 를 읽는다 — 단독 실행에서도 테이블이 있도록 등록을 확인한다.
# The KPI cost aggregate reads claude_api_calls; assert registration so a lone run has the table.
_TABLE_MODELS = (ClaudeApiCall, InsightNarrativeCache, Repository, User, Analysis)
if any(m.__tablename__ not in Base.metadata.tables for m in _TABLE_MODELS):
    raise RuntimeError("ORM import 소실 — 테이블 미등록 / ORM import lost, table unregistered")

_REAL_CTOR = anthropic.AsyncAnthropic
_CARDS = {
    "positive_highlights": ["점수가 안정적이다"],
    "focus_areas": ["보안 이슈 1건"],
    "key_metrics": [{"label": "평균 점수", "value": "82", "delta": "+3"}],
    "next_actions": ["테스트 보강"],
}
_FULL_BODY = json.dumps(_CARDS, ensure_ascii=False)
# `next_actions` 문자열 중간에서 끊긴 본문 — 루트 객체가 닫히지 않았다 / root object never closed
_CUT_BODY = (
    '{"positive_highlights": ["점수가 안정적이다"], "focus_areas": ["보안 이슈 1건"], '
    '"key_metrics": [{"label": "평균 점수", "value": "82", "delta": "+3"}], "next_actions": ["테스트 보'
)
# text 블록 없이 사고 블록만 — 상한까지 사고만 하다 멈춘 모양 / only a thinking block, no text block
_THINKING_ONLY = [{"type": "thinking", "thinking": "카드를 고르는 중", "signature": "sig"}]


@pytest.fixture()
def db():
    # 서비스가 동기 DB 를 워커 스레드로 넘긴다(#1701) — 스레드가 같은 인메모리 DB 를 보게 한다.
    # The services run sync DB work in worker threads; share one in-memory DB across threads.
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def owner(db):
    """사용자 1 + 소유 리포 1 + 창 안의 분석 2건 — 데이터 0건 조기 반환을 넘긴다."""
    user = User(github_id=f"dash-cap-{uuid.uuid4().hex[:6]}", github_login="t", email="t@x.com",
                display_name="T")
    db.add(user)
    db.commit()
    repo = Repository(full_name=f"o/r-{uuid.uuid4().hex[:6]}", user_id=user.id)
    db.add(repo)
    db.commit()
    now = datetime.now(timezone.utc)
    for i, score in enumerate((80, 85)):
        db.add(Analysis(repo_id=repo.id, commit_sha=f"cap{uuid.uuid4().hex}", score=score, grade="B",
                        result={}, created_at=(now - timedelta(hours=i + 1)).replace(tzinfo=None)))
    db.commit()
    return SimpleNamespace(user_id=user.id, now=now)


@pytest.fixture()
def sdk(monkeypatch):
    """실제 SDK — 응답 본문을 정하고 나간 요청 본문을 기록한다.
    Real SDK; the test sets the response and the sent request bodies are recorded.
    """
    h = SimpleNamespace(stop_reason="end_turn", text=_FULL_BODY, content=None, output_tokens=40,
                        sent=[])

    def handler(req):
        h.sent.append(json.loads(req.content))
        content = h.content if h.content is not None else [{"type": "text", "text": h.text}]
        return httpx2.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-haiku-4-5",
            "content": content, "stop_reason": h.stop_reason, "stop_sequence": None,
            "usage": {"input_tokens": 900, "output_tokens": h.output_tokens},
        })

    def ctor(*args, **kwargs):
        return _REAL_CTOR(*args, base_url="http://anthropic.test",
                          http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
                          **kwargs)

    monkeypatch.setattr(anthropic, "AsyncAnthropic", ctor)
    monkeypatch.delenv("INSIGHT_DISABLED", raising=False)
    return h


async def _run(db, owner):
    with patch.object(dashboard_service, "log_claude_api_call") as log:
        out = await dashboard_service.insight_narrative(
            db, days=7, now=owner.now, api_key="sk-test", user_id=owner.user_id, language="ko",
        )
    assert log.call_count == 1, f"호출 1회에 비용 행 {log.call_count}개 — 1개여야 한다"
    return out, log.call_args.kwargs


def _cached_error_type(db, owner):
    row = db.query(InsightNarrativeCache).filter_by(user_id=owner.user_id, repo_id=None).one()
    return row.last_error_type


def _cap_warnings(caplog):
    return [r.getMessage() for r in caplog.records
            if r.levelno == logging.WARNING and "max_tokens=" in r.getMessage()]


async def test_request_sends_output_limit_1500(db, owner, sdk):
    """나간 요청의 `max_tokens` — 상수에서 뽑지 않은 리터럴이다.
    The limit actually sent; a literal, not read from the constant.
    """
    await _run(db, owner)

    assert [body["max_tokens"] for body in sdk.sent] == [1500]


async def test_max_tokens_stop_is_recorded_as_truncation(db, owner, sdk, caplog):
    """🔴 SDK 가 `stop_reason="max_tokens"` 로 잘린 본문을 주면 비용 행이 `max_tokens` 다.

    수정 전: 비용 행 `success` · 경고 0건 · 카드만 `parse_error`. 카드 status 는 그대로 `parse_error`.
    The cost row says max_tokens (it said success); the card keeps the existing parse_error.
    """
    sdk.stop_reason, sdk.text, sdk.output_tokens = "max_tokens", _CUT_BODY, 1500

    with caplog.at_level(logging.WARNING, logger=dashboard_service.__name__):
        out, logged = await _run(db, owner)

    assert out["status"] == "parse_error"
    assert (logged["status"], logged["error_type"]) == ("error", "max_tokens")
    # 잘려도 과금된 토큰은 그대로 보고한다 / billed tokens are still reported
    assert logged["output_tokens"] == 1500
    assert _cached_error_type(db, owner) == "parse_error"
    warned = _cap_warnings(caplog)
    assert len(warned) == 1, warned
    assert "truncated" in warned[0] and "output_tokens=1500" in warned[0], warned


async def test_max_tokens_stop_without_text_block_is_truncation(db, owner, sdk):
    """🔴 상한에서 멈췄는데 text 블록이 아예 없으면 `ValueError`(→ api_error 카드)가 아니라 잘림이다.
    At the cap with no text block at all, it is truncation, not a ValueError mapped to api_error.
    """
    sdk.stop_reason, sdk.content, sdk.output_tokens = "max_tokens", _THINKING_ONLY, 1500

    out, logged = await _run(db, owner)

    assert out["status"] == "parse_error"
    assert (logged["status"], logged["error_type"]) == ("error", "max_tokens")


async def test_no_text_block_without_max_tokens_stop_keeps_its_class(db, owner, sdk):
    """🔴 심은 것(무시돼야) — text 블록이 없어도 `end_turn` 이면 잘림이 아니다. 기존 ValueError 경로 그대로.
    No text block under end_turn is not truncation: the existing ValueError path stays.
    """
    sdk.stop_reason, sdk.content = "end_turn", _THINKING_ONLY

    out, logged = await _run(db, owner)

    assert out["status"] == "api_error"
    assert logged["error_type"] == "ValueError"


async def test_max_tokens_stop_with_closed_body_is_kept_with_warning(db, owner, sdk, caplog):
    """🔴 상한에서 멈췄어도 4 카드로 닫힌 본문은 success 로 받고 경고 1건을 남긴다.
    A closed 4-card body at the cap is a success with exactly one cap warning, and is cached.
    """
    sdk.stop_reason, sdk.text, sdk.output_tokens = "max_tokens", _FULL_BODY, 1500

    with caplog.at_level(logging.WARNING, logger=dashboard_service.__name__):
        out, logged = await _run(db, owner)

    assert out["status"] == "success"
    assert out["positive_highlights"] == _CARDS["positive_highlights"]
    assert logged["status"] == "success"
    assert _cached_error_type(db, owner) is None
    warned = _cap_warnings(caplog)
    assert len(warned) == 1, warned
    assert "max_tokens=1500" in warned[0] and "output_tokens=1500" in warned[0], warned


async def test_end_turn_at_high_output_tokens_is_not_the_cap(db, owner, sdk, caplog):
    """🔴 심은 것(무시돼야) — 출력 토큰이 상한과 같아도 `end_turn` 이면 상한 경고가 없다.
    stop_reason decides, not output_tokens: end_turn at 1500 tokens has no cap warning.
    """
    sdk.stop_reason, sdk.text, sdk.output_tokens = "end_turn", _FULL_BODY, 1500

    with caplog.at_level(logging.WARNING, logger=dashboard_service.__name__):
        out, logged = await _run(db, owner)

    assert out["status"] == "success"
    assert logged["status"] == "success"
    assert _cap_warnings(caplog) == []


async def test_parse_failure_without_max_tokens_stop_is_not_truncation(db, owner, sdk, caplog):
    """🔴 심은 것(무시돼야) — 같은 잘린 본문이라도 `end_turn` 이면 잘림이 아니다(경고 없음, max_tokens 아님).
    Same broken body under end_turn is not truncation: no cap warning, not labelled max_tokens.
    """
    sdk.stop_reason, sdk.text = "end_turn", _CUT_BODY

    with caplog.at_level(logging.WARNING, logger=dashboard_service.__name__):
        out, logged = await _run(db, owner)

    assert out["status"] == "parse_error"
    assert logged.get("error_type") != "max_tokens"
    assert _cap_warnings(caplog) == []


@pytest.mark.parametrize("stop_reason", ["stop_sequence", "refusal"])
async def test_other_stop_reasons_are_not_the_cap(db, owner, sdk, caplog, stop_reason):
    """🔴 심은 것(무시돼야) — `stop_sequence`·`refusal` 은 상한이 아니다. 닫힌 본문은 경고 없는 success.
    Other stop reasons are not the cap: a full body is a plain success with no cap warning.
    """
    sdk.stop_reason = stop_reason

    with caplog.at_level(logging.WARNING, logger=dashboard_service.__name__):
        out, logged = await _run(db, owner)

    assert out["status"] == "success"
    assert logged["status"] == "success"
    assert _cap_warnings(caplog) == []


async def test_max_tokens_stop_with_non_list_card_value_is_not_api_error(db, owner, sdk):
    """🔴 상한에서 닫힌 본문의 카드 값이 목록이 아니어도 api_error(TypeError)로 새지 않는다 (Grok `caa22077`).
    A closed body at the cap with a non-list card value must not leak into api_error via TypeError.
    """
    sdk.stop_reason, sdk.output_tokens = "max_tokens", 1500
    sdk.text = json.dumps({**_CARDS, "positive_highlights": True}, ensure_ascii=False)

    out, logged = await _run(db, owner)

    assert out["status"] == "success"
    assert out["positive_highlights"] == []
    assert logged["status"] == "success"
