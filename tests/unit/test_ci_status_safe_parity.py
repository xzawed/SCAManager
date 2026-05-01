"""Phase H PR-5A — `_get_ci_status_safe` 양쪽 구현 PARITY 회귀 가드.

12-에이전트 감사 (2026-04-30) Critical C8 + 미래 트랩 검증 — `src/gate/engine.py`
와 `src/services/merge_retry_service.py` 양쪽에 동일 함수가 의도적 중복 구현됨
(단일/워커 경로 일관성). 한쪽만 수정 시 두 경로의 CI 상태 판정이 발산해 운영
사고 발생 가능. 본 테스트가 차이를 즉시 잡는다.

PR-5A-2 에서 `src/shared/ci_utils.py` 로 통합 예정. 그 전까지 본 parity 테스트
가 회귀 차단 단일 출처.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

# pylint: disable=wrong-import-position
import inspect
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.gate.engine import _get_ci_status_safe as engine_get_ci_status_safe
from src.services.merge_retry_service import (
    _get_ci_status_safe as worker_get_ci_status_safe,
)


# ──────────────────────────────────────────────────────────────────────────
# 시그니처 동일성 — 인자 이름은 다를 수 있으나 위치/keyword/타입 일치
# ──────────────────────────────────────────────────────────────────────────


def test_signatures_have_same_arity_and_kwargs():
    """두 함수의 시그니처 구조 동일 — positional 3 + keyword 1 (base_ref)."""
    engine_sig = inspect.signature(engine_get_ci_status_safe)
    worker_sig = inspect.signature(worker_get_ci_status_safe)

    # 파라미터 개수 동일
    assert len(engine_sig.parameters) == len(worker_sig.parameters), (
        f"파라미터 개수 불일치: engine={list(engine_sig.parameters)}, "
        f"worker={list(worker_sig.parameters)}"
    )
    # base_ref keyword-only 가 양쪽 다 존재
    assert "base_ref" in engine_sig.parameters
    assert "base_ref" in worker_sig.parameters
    # base_ref default = "main" 양쪽 동일
    assert engine_sig.parameters["base_ref"].default == "main"
    assert worker_sig.parameters["base_ref"].default == "main"
    # base_ref 가 KEYWORD_ONLY 양쪽 동일
    assert engine_sig.parameters["base_ref"].kind == inspect.Parameter.KEYWORD_ONLY
    assert worker_sig.parameters["base_ref"].kind == inspect.Parameter.KEYWORD_ONLY


# ──────────────────────────────────────────────────────────────────────────
# 행동 PARITY — 입력에 대해 동일한 출력 반환
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("required_value,ci_value,expected", [
    ({"ci/test"}, "passed", "passed"),
    (set(), "running", "running"),       # 빈 set → None 변환 후 그대로 전달
    (None, "failed", "failed"),
    ({"ci/test", "ci/lint"}, "neutral", "neutral"),
])
async def test_behavior_parity_happy_path(required_value, ci_value, expected):
    """동일 입력 → 양쪽 함수 동일 출력 (행동 동등성)."""
    with patch("src.gate.engine.get_required_check_contexts",
               new_callable=AsyncMock, return_value=required_value), \
         patch("src.gate.engine.get_ci_status",
               new_callable=AsyncMock, return_value=ci_value), \
         patch("src.services.merge_retry_service.get_required_check_contexts",
               new_callable=AsyncMock, return_value=required_value), \
         patch("src.services.merge_retry_service.get_ci_status",
               new_callable=AsyncMock, return_value=ci_value):
        engine_result = await engine_get_ci_status_safe("tok", "owner/repo", "sha")
        worker_result = await worker_get_ci_status_safe("tok", "owner/repo", "sha")

    assert engine_result == worker_result == expected, (
        f"PARITY 위반: engine={engine_result!r} vs worker={worker_result!r} "
        f"(input: required={required_value}, ci={ci_value})"
    )


async def test_behavior_parity_required_httperror_falls_back_to_none():
    """get_required_check_contexts HTTPError → 양쪽 모두 required=None 으로 처리."""
    captured_engine = {}
    captured_worker = {}

    async def _engine_ci(*_args, **kwargs):
        captured_engine["required"] = kwargs.get("required_contexts")
        return "passed"

    async def _worker_ci(*_args, **kwargs):
        captured_worker["required"] = kwargs.get("required_contexts")
        return "passed"

    with patch("src.gate.engine.get_required_check_contexts",
               new_callable=AsyncMock, side_effect=httpx.ConnectError("net")), \
         patch("src.gate.engine.get_ci_status", new=_engine_ci), \
         patch("src.services.merge_retry_service.get_required_check_contexts",
               new_callable=AsyncMock, side_effect=httpx.ConnectError("net")), \
         patch("src.services.merge_retry_service.get_ci_status", new=_worker_ci):
        engine_result = await engine_get_ci_status_safe("tok", "owner/repo", "sha")
        worker_result = await worker_get_ci_status_safe("tok", "owner/repo", "sha")

    assert engine_result == worker_result == "passed"
    assert captured_engine["required"] is None
    assert captured_worker["required"] is None


async def test_behavior_parity_get_ci_httperror_returns_unknown():
    """get_ci_status HTTPError → 양쪽 모두 'unknown' 반환."""
    with patch("src.gate.engine.get_required_check_contexts",
               new_callable=AsyncMock, return_value={"ci/test"}), \
         patch("src.gate.engine.get_ci_status",
               new_callable=AsyncMock, side_effect=httpx.ConnectError("net")), \
         patch("src.services.merge_retry_service.get_required_check_contexts",
               new_callable=AsyncMock, return_value={"ci/test"}), \
         patch("src.services.merge_retry_service.get_ci_status",
               new_callable=AsyncMock, side_effect=httpx.ConnectError("net")):
        engine_result = await engine_get_ci_status_safe("tok", "owner/repo", "sha")
        worker_result = await worker_get_ci_status_safe("tok", "owner/repo", "sha")

    assert engine_result == worker_result == "unknown"


async def test_behavior_parity_base_ref_propagated():
    """base_ref 파라미터가 양쪽 모두 get_required_check_contexts 로 전달."""
    captured_engine = []
    captured_worker = []

    async def _engine_required(_token, _repo, base_ref):
        captured_engine.append(base_ref)
        return {"ci/test"}

    async def _worker_required(_token, _repo, base_ref):
        captured_worker.append(base_ref)
        return {"ci/test"}

    with patch("src.gate.engine.get_required_check_contexts", new=_engine_required), \
         patch("src.gate.engine.get_ci_status",
               new_callable=AsyncMock, return_value="passed"), \
         patch("src.services.merge_retry_service.get_required_check_contexts",
               new=_worker_required), \
         patch("src.services.merge_retry_service.get_ci_status",
               new_callable=AsyncMock, return_value="passed"):
        await engine_get_ci_status_safe("tok", "owner/repo", "sha", base_ref="develop")
        await worker_get_ci_status_safe("tok", "owner/repo", "sha", base_ref="develop")

    assert captured_engine == ["develop"]
    assert captured_worker == ["develop"]
