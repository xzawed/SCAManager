"""리포 인사이트 서술 — 출력 상한에서 잘린 응답을 파싱 전에 알아본다 (#1700).

운영 `claude_api_calls` 6건 중 5건이 출력 600 토큰(상한)에 정확히 닿았고 4건이 `JSONDecodeError` 였다.
잘림은 파서 버그처럼 기록됐다. 상한에서 멈췄어도 `{"text": 문자열}` 로 닫힌 본문은 success + 경고,
읽을 수 없으면 `max_tokens` 로 남긴다(ai_review 와 같은 관용). 여기서는 `AsyncAnthropic` 을 더블로 바꾸지 않고 **실제 SDK** 가
응답 본문을 `Message` 로 만든다 — 전송만 `httpx2.MockTransport` 다. 그래서 `stop_reason` 은
SDK 가 실제로 주는 모양 그대로이고, 요청 본문의 `max_tokens` 도 실제로 나간 값을 잰다.

At the cap a closed {"text": str} body is kept with a warning; an unreadable one is `max_tokens`.
Drives the real SDK (transport faked only) so stop_reason has the genuine response shape and the
request's max_tokens is what would actually be sent.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import json
import logging
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import anthropic
import httpx2
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.config import settings
from src.database import Base
from src.models.insight_narrative_cache import InsightNarrativeCache
from src.models.repository import Repository
from src.models.user import User
from src.services import repo_insight_service
from src.services.repo_insight_service import repo_insight_narrative

_REAL_CTOR = anthropic.AsyncAnthropic
_KPI = {"analysis_count": 3, "avg_score": 70, "grade": "C"}
# 스키마가 여는 `{"text": "` 뒤에서 끊긴 본문 — 운영 4건의 모양 / body cut after the schema's opening
_CUT_BODY = '{"text": "이 리포는 최근 30일 동안 점수가 안정적이었고, 반복 이슈는 주로'
# 상한에서 멈췄는데 닫힌 본문 — 스키마상 문자열을 끝낸 것이다 / closed at the cap: the string finished
_CUT_BUT_CLOSED = '{"text": "이 리포는 최근 30일 동안"}'
_FULL_BODY = '{"text": "점수가 안정적이다. 다음 단계는 테스트 보강이다."}'


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def owned_repo(db):
    user = User(github_id=77, github_login="t", email="t@x.com", display_name="T")
    db.add(user)
    db.commit()
    repo = Repository(full_name=f"o/r-{uuid.uuid4().hex[:6]}", user_id=user.id)
    db.add(repo)
    db.commit()
    return SimpleNamespace(user_id=user.id, repo_id=repo.id)


@pytest.fixture()
def sdk(monkeypatch):
    """실제 SDK — 응답 본문을 정하고 나간 요청 본문을 기록한다.
    Real SDK; the test sets the response and the sent request bodies are recorded.
    """
    h = SimpleNamespace(stop_reason="end_turn", text=_FULL_BODY, output_tokens=40, sent=[])

    def handler(req):
        h.sent.append(json.loads(req.content))
        return httpx2.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-haiku-4-5",
            "content": [{"type": "text", "text": h.text}],
            "stop_reason": h.stop_reason, "stop_sequence": None,
            "usage": {"input_tokens": 693, "output_tokens": h.output_tokens},
        })

    def ctor(*args, **kwargs):
        return _REAL_CTOR(*args, base_url="http://anthropic.test",
                          http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
                          **kwargs)

    monkeypatch.setattr(anthropic, "AsyncAnthropic", ctor)
    monkeypatch.delenv("INSIGHT_DISABLED", raising=False)
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    return h


async def _run(db, owned_repo):
    with patch.object(repo_insight_service, "log_claude_api_call") as log:
        out = await repo_insight_narrative(
            db, owned_repo.repo_id, 30, repo_full_name="o/r", kpi=_KPI, recurring=[],
            user_id=owned_repo.user_id, language="ko",
        )
    assert log.call_count == 1, f"호출 1회에 비용 행 {log.call_count}개 — 1개여야 한다"
    return out, log.call_args.kwargs


def _cached_error_type(db, owned_repo):
    row = db.query(InsightNarrativeCache).filter_by(
        user_id=owned_repo.user_id, repo_id=owned_repo.repo_id).one()
    return row.last_error_type


async def test_request_sends_output_limit_1500(db, owned_repo, sdk):
    """🔴 나간 요청의 `max_tokens` — 상수에서 뽑지 않은 리터럴 (수정 전 실측 600).
    The limit actually sent; a literal, not read from the constant.
    """
    await _run(db, owned_repo)

    assert [body["max_tokens"] for body in sdk.sent] == [1500]


async def test_max_tokens_stop_is_recorded_as_truncation(db, owned_repo, sdk, caplog):
    """🔴 SDK 가 `stop_reason="max_tokens"` 로 잘린 본문을 주면 파서 버그가 아니라 잘림으로 남긴다.

    수정 전: error_type `JSONDecodeError`(운영 4건과 같은 기록). status 는 그대로 `internal_error` 다.
    A max_tokens stop is recorded as truncation, not as our parser failing; status is unchanged.
    """
    sdk.stop_reason, sdk.text, sdk.output_tokens = "max_tokens", _CUT_BODY, 1500

    with caplog.at_level(logging.WARNING, logger=repo_insight_service.__name__):
        out, logged = await _run(db, owned_repo)

    assert out == {"text": "", "status": "internal_error"}
    assert (logged["status"], logged["error_type"]) == ("error", "max_tokens")
    # 잘려도 과금된 토큰은 그대로 보고한다 / billed tokens are still reported
    assert logged["output_tokens"] == 1500
    assert _cached_error_type(db, owned_repo) == "max_tokens"
    warned = [r for r in caplog.records
              if r.levelno == logging.WARNING and "max_tokens=1500" in r.getMessage()]
    assert len(warned) == 1, [r.getMessage() for r in caplog.records]
    assert "truncated" in warned[0].getMessage()


def _cap_warnings(caplog):
    return [r.getMessage() for r in caplog.records
            if r.levelno == logging.WARNING and "max_tokens=" in r.getMessage()]


async def test_max_tokens_stop_with_closed_body_is_kept_with_warning(db, owned_repo, sdk, caplog):
    """🔴 상한에서 멈췄어도 `{"text": 문자열}` 로 닫힌 본문은 success 로 받고 경고 1건을 남긴다.

    스키마가 문자열 하나라 닫혔다는 것은 모델이 문자열을 끝냈다는 뜻이다. 캐시에도 오류가 남지 않는다.
    A closed body at the cap is kept as success with exactly one cap warning, and is cached.
    """
    sdk.stop_reason, sdk.text, sdk.output_tokens = "max_tokens", _CUT_BUT_CLOSED, 1500

    with caplog.at_level(logging.WARNING, logger=repo_insight_service.__name__):
        out, logged = await _run(db, owned_repo)

    assert out == {"text": "이 리포는 최근 30일 동안", "status": "success"}
    assert logged["status"] == "success"
    assert _cached_error_type(db, owned_repo) is None
    warned = _cap_warnings(caplog)
    assert len(warned) == 1, warned
    assert "max_tokens=1500" in warned[0] and "output_tokens=1500" in warned[0], warned


async def test_max_tokens_stop_with_non_text_json_is_truncation(db, owned_repo, sdk):
    """상한에서 멈췄는데 기대한 `{"text": 문자열}` 모양이 아니면 폴백(raw)으로 받지 않고 `max_tokens` 다.
    At the cap, a parsable body without a string `text` is not kept via the raw fallback.
    """
    sdk.stop_reason, sdk.text, sdk.output_tokens = "max_tokens", '{"summary": "x"}', 1500

    out, logged = await _run(db, owned_repo)

    assert out == {"text": "", "status": "internal_error"}
    assert logged["error_type"] == "max_tokens"


async def test_end_turn_at_high_output_tokens_is_not_the_cap(db, owned_repo, sdk, caplog):
    """🔴 심은 것(무시돼야) — 출력 토큰이 상한과 같아도 `end_turn` 이면 상한 경고도 오류도 없다.
    stop_reason decides, not output_tokens: end_turn at 1500 tokens is a plain success with no cap warning.
    """
    sdk.stop_reason, sdk.text, sdk.output_tokens = "end_turn", _FULL_BODY, 1500

    with caplog.at_level(logging.WARNING, logger=repo_insight_service.__name__):
        out, logged = await _run(db, owned_repo)

    assert out["status"] == "success"
    assert logged["status"] == "success"
    assert _cap_warnings(caplog) == []


async def test_max_tokens_stop_at_low_output_tokens_is_still_the_cap(db, owned_repo, sdk):
    """🔴 심은 것(잡혀야) — 보고된 출력 토큰이 적어도 `max_tokens` 로 멈추고 본문이 깨졌으면 `max_tokens` 다.
    A max_tokens stop with a low token count and a broken body is still recorded as max_tokens.
    """
    sdk.stop_reason, sdk.text, sdk.output_tokens = "max_tokens", _CUT_BODY, 12

    out, logged = await _run(db, owned_repo)

    assert out == {"text": "", "status": "internal_error"}
    assert logged["error_type"] == "max_tokens"
    assert _cached_error_type(db, owned_repo) == "max_tokens"


@pytest.mark.parametrize("stop_reason", ["stop_sequence", "refusal"])
async def test_other_stop_reasons_are_not_the_cap(db, owned_repo, sdk, caplog, stop_reason):
    """🔴 심은 것(무시돼야) — `stop_sequence`·`refusal` 은 상한이 아니다. 닫힌 본문은 경고 없는 success.
    Other stop reasons are not the cap: a full body is a plain success with no cap warning.
    """
    sdk.stop_reason, sdk.text = stop_reason, _FULL_BODY

    with caplog.at_level(logging.WARNING, logger=repo_insight_service.__name__):
        out, logged = await _run(db, owned_repo)

    assert out["status"] == "success"
    assert logged["status"] == "success"
    assert _cap_warnings(caplog) == []


async def test_stop_sequence_with_broken_body_keeps_its_class(db, owned_repo, sdk):
    """`stop_sequence` 에서 깨진 본문은 상한이 아니라 파서 실패 그대로다.
    A broken body under stop_sequence stays a JSONDecodeError, not max_tokens.
    """
    sdk.stop_reason, sdk.text = "stop_sequence", _CUT_BODY

    _, logged = await _run(db, owned_repo)

    assert logged["error_type"] == "JSONDecodeError"


async def test_parse_failure_without_max_tokens_stop_keeps_its_class(db, owned_repo, sdk):
    """🔴 심은 것(무시돼야) — 같은 잘린 본문이라도 `end_turn` 이면 잘림이 아니다. 파서 실패 그대로.
    Same broken body with end_turn is not truncation: it stays a JSONDecodeError.
    """
    sdk.stop_reason, sdk.text = "end_turn", _CUT_BODY

    out, logged = await _run(db, owned_repo)

    assert out["status"] == "internal_error"
    assert logged["error_type"] == "JSONDecodeError"
    assert _cached_error_type(db, owned_repo) == "JSONDecodeError"


async def test_full_response_still_succeeds(db, owned_repo, sdk):
    """대조군 — 끝까지 쓴 응답(`end_turn`)은 그대로 success 이고 캐시에 오류가 남지 않는다.
    A complete response still succeeds and leaves no cached error.
    """
    out, logged = await _run(db, owned_repo)

    assert out == {"text": "점수가 안정적이다. 다음 단계는 테스트 보강이다.", "status": "success"}
    assert logged["status"] == "success"
    assert _cached_error_type(db, owned_repo) is None
