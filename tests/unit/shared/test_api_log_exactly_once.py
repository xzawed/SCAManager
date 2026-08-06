"""비용 로그 = **API 호출당 정확히 1행** 회귀 가드 (backlog R63 · Grok 71bd2d6c 파생).

## 왜 (2026-08-06)

세 경로가 `log_claude_api_call(status="success")` 를 **응답 파싱보다 먼저** 불렀다.
그래서 추출·파싱이 실패하면 except 절이 `status="error"` 를 **또** 남겨 —
**한 번의 API 호출이 비용 테이블에 2행**이 됐다.

🔴 실측(수정 전): 추출 실패를 강제하니 status 시퀀스가 `['success', 'error']`.

**무엇이 망가지나**: `claude_api_calls` 는 비용 집계(`monthly_cost` KPI)와 성공률의
원천이다. 실패한 호출이 success 행을 남기면 **성공률이 과대**하고 **비용이 이중 계상**된다.
운영자는 *"성공했다는데 왜 결과가 없지"* 를 보게 된다.

## 이 테스트가 고정하는 것

1. **성공 경로** — 정확히 1행, status=success
2. **추출 실패** — 정확히 1행, status=**error** (success 가 섞이면 안 된다)
3. **AST 순서** — success 로그가 추출보다 **뒤**에 있는지(순서가 계약이다)

🔴 순서 단언만으로는 부족하다 — 코드가 재배치돼도 의미가 유지될 수 있고, 반대로
순서가 맞아도 다른 경로로 2행이 날 수 있다. 그래서 **실행 관측**을 함께 둔다.
"""
from __future__ import annotations

import ast
import asyncio
import inspect
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_ROOT = Path(__file__).resolve().parents[3]

_VALID_REVIEW = json.dumps({
    "commit_message_score": 15, "direction_score": 18, "test_score": 8,
    "summary": "s", "suggestions": [],
    "commit_message_feedback": "a", "direction_feedback": "b", "test_feedback": "c",
    "code_quality_feedback": "d", "security_feedback": "e", "file_feedbacks": [],
})


def _run(value):
    return asyncio.run(value) if inspect.isawaitable(value) else value


def _review_with(content_blocks) -> list[str]:
    """`review_code` 를 실행하고 기록된 status 시퀀스를 돌려준다."""
    import src.analyzer.io.ai_review as m

    statuses: list[str] = []
    resp = MagicMock()
    resp.content = content_blocks
    resp.stop_reason = "end_turn"
    resp.usage = MagicMock(cache_read_input_tokens=0, cache_creation_input_tokens=0)
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=resp)

    with patch.object(m, "log_claude_api_call", lambda **kw: statuses.append(kw.get("status"))), \
         patch.object(m.anthropic, "AsyncAnthropic", return_value=client), \
         patch.object(m, "extract_anthropic_usage", return_value=(10, 20)):
        _run(m.review_code(api_key="k", commit_message="m", patches=[("a.py", "+1")]))
    return statuses


def test_success_path_logs_exactly_one_row():
    assert _review_with([MagicMock(text=_VALID_REVIEW)]) == ["success"]


def test_extraction_failure_logs_exactly_one_error_row():
    """🔴 핵심 — 수정 전에는 `['success', 'error']` 였다(실측)."""
    statuses = _review_with([MagicMock(spec=[])])  # `.text` 없는 블록 → 추출 실패
    assert statuses == ["error"], (
        f"추출 실패인데 status 시퀀스가 {statuses} — 한 호출이 여러 행을 남긴다.\n"
        "→ success 로그는 파싱이 끝난 **뒤에만** 찍혀야 한다."
    )


def test_parse_failure_logs_exactly_one_row():
    """JSON 이 깨진 경우도 1행 — 다만 `_parse_response` 가 파싱 실패를 결과로 흡수하므로
    status 는 success 일 수 있다. **행 수가 1인지**가 이 테스트의 계약이다."""
    statuses = _review_with([MagicMock(text="not json at all")])
    assert len(statuses) == 1, f"한 호출에 {len(statuses)}행이 기록됐다: {statuses}"


# ── 순서 계약 (AST) ──────────────────────────────────────────────────────

_ORDERED = (
    ("src/services/dashboard_service.py", "_call_insight_claude_api"),
    ("src/services/repo_insight_service.py", "repo_insight_narrative"),
)


@pytest.mark.parametrize(("rel", "func"), _ORDERED)
def test_success_log_comes_after_extraction(rel: str, func: str):
    """success 로그가 추출보다 **뒤**여야 한다 — 순서가 곧 계약이다.

    (`ai_review` 는 `finally` 단일 기록이라 이 축이 적용되지 않아 제외 — 대신 위
    실행 테스트가 그 경로를 직접 관측한다.)
    """
    tree = ast.parse((_ROOT / rel).read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func), None)
    assert fn is not None, f"{rel}::{func} 를 못 찾았다 — 이름이 바뀌었으면 가드도 갱신할 것"

    logs = [n.lineno for n in ast.walk(fn)
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "log_claude_api_call"]
    extracts = [n.lineno for n in ast.walk(fn)
                if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "first_text_block"]
    assert logs and extracts, f"{rel}::{func} 에서 로그/추출 호출을 못 찾았다"
    assert min(extracts) < min(logs), (
        f"{rel}::{func} — success 로그(line {min(logs)})가 추출(line {min(extracts)})보다 앞이다.\n"
        "→ 추출이 실패하면 success 가 이미 기록돼 한 호출이 2행이 된다."
    )


def test_ai_review_logs_from_a_single_site():
    """`ai_review` 는 `finally` 에서 **한 곳**만 기록해야 한다 — 호출부가 늘면 2행 위험."""
    tree = ast.parse((_ROOT / "src/analyzer/io/ai_review.py").read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "review_code")
    logs = [n for n in ast.walk(fn)
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "log_claude_api_call"]
    assert len(logs) == 1, (
        f"`review_code` 에 log_claude_api_call 호출이 {len(logs)}곳이다 — "
        "경로마다 찍으면 한 호출이 여러 행을 남긴다(R63 이 고친 결함)."
    )
