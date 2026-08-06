"""실패한 호출도 **실제로 쓴 토큰**을 기록해야 한다 (backlog R65 · R63 잔여).

## 왜 (2026-08-06)

R63 이 "API 호출 1건 = 비용 로그 1행" 을 세웠다. 그런데 그 1행이 **error 경로일 때
토큰을 0 으로 적었다** — 세 경로 중 둘이 `input_tokens=0, output_tokens=0` 리터럴이었고
`log_claude_api_call` 의 docstring 도 *"에러 시 0"* 이라고 그 관행을 처방하고 있었다.

🔴 **왜 틀렸나**: 실패의 대부분은 **응답을 받은 뒤** 추출·파싱에서 난다(R61·R63 이 고친
클래스가 정확히 그것이다). 그 시점의 토큰은 **이미 과금됐다**. 0 으로 적으면
`claude_api_calls.cost_usd` 가 0 이 되고, 그 테이블을 그대로 합산하는 `monthly_cost`
KPI 가 **과소**가 된다 — 실패가 잦을수록 오차가 커지는 방향이다(운영자는 비용이
줄어든 것처럼 본다).

**0 이 맞는 경우도 있다**: 호출 자체가 실패(네트워크·인증)하면 소비된 토큰이 없다.
그래서 "항상 0" 도 "항상 비-0" 도 아니고 — **응답을 받았으면 그 값**이 계약이다.

## 이 파일이 고정하는 것

1. 3경로 전부 — 응답 수신 후 실패 시 로그의 토큰이 **실측치**인가
2. 대조군 — 호출 자체가 실패하면 0 인가 (위 단언이 '무조건 비-0' 이 아님을 증명)
3. `log_claude_api_call` 의 실패 로그 줄이 토큰·비용을 **사람이 읽는 위치에** 싣는가
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

_REAL_IN, _REAL_OUT = 1234, 567

_VALID_REVIEW = json.dumps({
    "commit_message_score": 15, "direction_score": 18, "test_score": 8,
    "summary": "s", "suggestions": [],
    "commit_message_feedback": "a", "direction_feedback": "b", "test_feedback": "c",
    "code_quality_feedback": "d", "security_feedback": "e", "file_feedbacks": [],
})


def _run(value):
    return asyncio.run(value) if inspect.isawaitable(value) else value


def _response(blocks, *, cache_read: int = 0, cache_creation: int = 0):
    resp = MagicMock()
    resp.content = blocks
    resp.stop_reason = "end_turn"
    resp.usage = MagicMock(
        input_tokens=_REAL_IN, output_tokens=_REAL_OUT,
        cache_read_input_tokens=cache_read, cache_creation_input_tokens=cache_creation,
    )
    return resp


# ── ① ai_review ─────────────────────────────────────────────────────────


def _review_rows(blocks, *, create_raises: Exception | None = None) -> list[dict]:
    import src.analyzer.io.ai_review as m

    rows: list[dict] = []
    client = MagicMock()
    client.messages.create = AsyncMock(
        side_effect=create_raises) if create_raises else AsyncMock(
        return_value=_response(blocks))

    with patch.object(m, "log_claude_api_call", lambda **kw: rows.append(kw)), \
         patch.object(m.anthropic, "AsyncAnthropic", return_value=client):
        _run(m.review_code(api_key="k", commit_message="m", patches=[("a.py", "+1")]))
    return rows


def test_ai_review_success_reports_real_tokens():
    (row,) = _review_rows([MagicMock(text=_VALID_REVIEW)])
    assert (row["input_tokens"], row["output_tokens"]) == (_REAL_IN, _REAL_OUT)


def test_ai_review_extraction_failure_still_reports_real_tokens():
    """🔴 응답은 받았고 토큰은 과금됐다 — 실패했다고 0 으로 적으면 비용이 과소가 된다."""
    (row,) = _review_rows([MagicMock(spec=[])])  # `.text` 없는 블록 → 추출 실패
    assert row["status"] == "error"
    assert (row["input_tokens"], row["output_tokens"]) == (_REAL_IN, _REAL_OUT), (
        f"실패 행의 토큰이 {row['input_tokens']}/{row['output_tokens']} — "
        "응답을 받은 뒤 실패했는데 0 이면 monthly_cost 가 과소 계상된다."
    )


def test_ai_review_call_failure_reports_zero():
    """🔴 대조군 — 호출 자체가 실패하면 소비 토큰이 없으므로 0 이 **맞다**.

    이게 없으면 위 단언이 '무조건 비-0' 으로 오독될 수 있다(0 을 못 쓰게 만드는 건
    다른 방향의 거짓말이다).
    """
    (row,) = _review_rows([], create_raises=RuntimeError("network down"))
    assert row["status"] == "error"
    assert (row["input_tokens"], row["output_tokens"]) == (0, 0)


# ── ② dashboard_service ─────────────────────────────────────────────────


def _dashboard_rows(blocks, **resp_kw) -> list[dict]:
    import src.services.dashboard_service as m

    rows: list[dict] = []
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_response(blocks, **resp_kw))
    with patch.object(m, "log_claude_api_call", lambda **kw: rows.append(kw)):
        _run(m._call_insight_claude_api(client, "claude-haiku-4-5", "prompt"))  # noqa: SLF001
    return rows


def test_dashboard_extraction_failure_still_reports_real_tokens():
    (row,) = _dashboard_rows([MagicMock(spec=[])], cache_read=99, cache_creation=7)
    assert row["status"] == "error"
    assert (row["input_tokens"], row["output_tokens"]) == (_REAL_IN, _REAL_OUT)
    assert (row["cache_read_tokens"], row["cache_creation_tokens"]) == (99, 7), (
        "캐시 토큰도 과금 대상이다 — 실패 행에서 0 으로 지우면 비용이 어긋난다."
    )


def test_dashboard_success_reports_real_tokens():
    (row,) = _dashboard_rows([MagicMock(text="narrative")], cache_read=5)
    assert row["status"] == "success"
    assert (row["input_tokens"], row["output_tokens"]) == (_REAL_IN, _REAL_OUT)
    assert row["cache_read_tokens"] == 5


# ── ③ repo_insight_service ──────────────────────────────────────────────
#
# 그 경로는 모듈 지역 `db`/`repo`/`user` 픽스처(실 ORM)를 쓰므로
# `tests/unit/services/test_repo_insight_service.py::TestErrorPathTokens` 에 둔다.


# ── ④ 실패 로그 줄의 가시성 ──────────────────────────────────────────────


def test_error_log_line_carries_tokens_and_cost(caplog):
    """🔴 `extra` 에만 실으면 raw 로그를 읽는 운영자에게는 실패의 비용이 안 보인다.

    R65 이전의 실패 줄은 `model/duration/status/error_type` 뿐이었다 — 값을 고쳐 놓고도
    사람이 볼 수 있는 자리에 없으면 관측되지 않는 수정이다.
    """
    from src.shared.claude_metrics import log_claude_api_call

    with patch("src.shared.claude_metrics._persist_cost"), \
         caplog.at_level(logging.WARNING, logger="src.shared.claude_metrics"):
        log_claude_api_call(
            model="claude-haiku-4-5", duration_ms=12.0,
            input_tokens=_REAL_IN, output_tokens=_REAL_OUT,
            status="error", error_type="ValueError",
        )

    line = "\n".join(r.getMessage() for r in caplog.records)
    assert f"input_tokens={_REAL_IN}" in line, f"실패 로그 줄에 입력 토큰이 없다: {line!r}"
    assert f"output_tokens={_REAL_OUT}" in line, f"실패 로그 줄에 출력 토큰이 없다: {line!r}"
    assert "cost_usd=" in line, f"실패 로그 줄에 비용이 없다: {line!r}"


def test_reported_tokens_reach_the_persistence_helper():
    """`log_claude_api_call` 이 받은 값을 영속화 헬퍼로 **전달**하는지.

    ⚠️ `_persist_cost` 를 패치하므로 이것은 **전달 단언**이지 INSERT 증명이 아니다
    (Grok claim-review `019fd6e8` 지적 — 초판 docstring 이 "DB 로 가는 값" 이라 과대였다).
    실제 행 기록은 아래 `test_production_error_path_writes_a_real_row_with_real_tokens`.
    """
    from src.shared.claude_metrics import log_claude_api_call

    with patch("src.shared.claude_metrics._persist_cost") as persist:
        log_claude_api_call(
            model="claude-haiku-4-5", duration_ms=1.0,
            input_tokens=_REAL_IN, output_tokens=_REAL_OUT,
            status="error", error_type="ValueError",
        )
    kw = persist.call_args.kwargs
    assert (kw["input_tokens"], kw["output_tokens"]) == (_REAL_IN, _REAL_OUT)
    assert kw["cost_usd"] > 0, "실패 행의 비용이 0 이면 monthly_cost 가 그만큼 과소다"


def test_production_error_path_writes_a_real_row_with_real_tokens(monkeypatch):
    """🔴 **호출부 실패 → 실제 DB 행**까지 아무것도 패치하지 않고 관통한다.

    Grok claim-review `019fd6e8` 의 핵심 지적: 나머지 테스트는 전부
    `log_claude_api_call` 을 **스파이로 대체**하거나 `_persist_cost` 를 패치한다.
    그래서 *"실패해도 비용이 기록된다"* 는 주장은 **한 번도 관측된 적이 없었다** —
    호출부 kwargs 만 봤을 뿐이다. 이 테스트만이 `review_code` 의 추출 실패에서
    `claude_api_calls` 행까지를 한 번에 본다.

    관측 대상: 행 1개 · status=error · 토큰이 실측치 · **cost_usd > 0**
    (마지막 항목이 R65 의 실체다 — 0 이면 `monthly_cost` 가 그만큼 과소다).
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import src.analyzer.io.ai_review as m
    from src.database import Base
    from src.models.claude_api_call import ClaudeApiCall

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine)
    # `_persist_cost` 는 호출마다 `src.database` 에서 재-import 하므로 속성 patch 가 먹는다.
    monkeypatch.setattr("src.database.WorkerSessionLocal", session_local)

    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_response([MagicMock(spec=[])]))
    with patch.object(m.anthropic, "AsyncAnthropic", return_value=client):
        _run(m.review_code(api_key="k", commit_message="msg", patches=[("a.py", "+1")]))

    with session_local() as db:
        rows = db.query(ClaudeApiCall).all()
    assert len(rows) == 1, f"한 호출에 {len(rows)}행이 기록됐다 (R63 계약)"
    assert rows[0].status == "error"
    assert (rows[0].input_tokens, rows[0].output_tokens) == (_REAL_IN, _REAL_OUT), (
        "DB 에 기록된 실패 행의 토큰이 실측치가 아니다 — 이미 과금된 토큰이 지워졌다."
    )
    assert rows[0].cost_usd > 0, (
        "실패 행의 cost_usd 가 0 이다 — monthly_cost KPI 가 그만큼 과소 계상된다."
    )


# ── ⑤ 리터럴 0 재도입 차단 (AST) ────────────────────────────────────────


def test_no_call_site_hardcodes_zero_tokens_on_the_error_path():
    """🔴 `input_tokens=0` 리터럴이 다시 들어오면 red — 값이 아니라 **관행**을 막는다.

    실행 테스트만 두면 새 호출부가 생겼을 때 그 경로는 관측되지 않는다.
    """
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    offenders = []
    for rel in ("src/analyzer/io/ai_review.py",
                "src/services/dashboard_service.py",
                "src/services/repo_insight_service.py"):
        tree = ast.parse((root / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and getattr(node.func, "id", "") == "log_claude_api_call"):
                continue
            for kw in node.keywords:
                if kw.arg in ("input_tokens", "output_tokens") \
                        and isinstance(kw.value, ast.Constant) and kw.value.value == 0:
                    offenders.append(f"{rel}:{node.lineno} {kw.arg}=0")
    assert not offenders, (
        "비용 로그 호출부가 토큰을 0 리터럴로 넘긴다 — 응답을 받은 뒤 실패한 경우 "
        f"이미 과금된 토큰이 지워진다:\n  " + "\n  ".join(offenders)
    )
