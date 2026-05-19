"""insight_narrative — httpx/asyncio 네트워크 레벨 예외 api_error 경로 단위 테스트.

검증 대상:
    src/services/dashboard_service.py::insight_narrative (→ _call_insight_claude_api)

검증 케이스 (3종):
    1. httpx.ConnectError("Connection refused") — 연결 거부
    2. httpx.ReadTimeout()                     — 읽기 타임아웃
    3. asyncio.TimeoutError()                  — asyncio 타임아웃

`_call_insight_claude_api` 의 `except Exception` 범위는 httpx.ConnectError /
httpx.ReadTimeout / asyncio.TimeoutError 를 모두 포함 → 각 케이스에서
status="api_error" + 4 카드 빈 list 를 반환하고 예외를 propagate 하지 않아야 한다.

Network-level exception api_error path tests for insight_narrative.
The broad `except Exception` in `_call_insight_claude_api` must catch all three
exception types and map them to status="api_error" without propagating.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database import Base
from src.models.analysis import Analysis  # noqa: F401  (Base.metadata 등록 / register on metadata)
from src.models.repository import Repository  # noqa: F401
from src.models.user import User  # noqa: F401


# ─── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def db():
    """모든 ORM 테이블이 생성된 in-memory SQLite 세션.

    Provides an in-memory SQLite session with all ORM tables created.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def seeded_repo(db):
    """user + repo 1건 seed — Analysis FK 충족용.

    Seeds one user + one repo so Analysis rows have valid FKs.
    """
    user = User(github_id=99, github_login="nettest", email="net@x.com", display_name="NetTest")
    db.add(user)
    db.commit()
    db.refresh(user)
    repo = Repository(full_name="nettest/repo", user_id=user.id)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


def _make_analysis(
    db: Session,
    repo_id: int,
    score: int,
    *,
    offset_hours: int = 0,
    result: dict[str, Any] | None = None,
) -> Analysis:
    """Analysis 레코드 헬퍼 — 점수 / created_at offset / result dict 주입 가능.

    Helper to insert an Analysis row with score / created_at offset / result dict.
    """
    created = datetime.now(timezone.utc) - timedelta(hours=offset_hours)
    a = Analysis(
        repo_id=repo_id,
        commit_sha=f"sha-{uuid.uuid4().hex}",
        score=score,
        grade="B",
        result=result or {},
        created_at=created,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _seed_two_analyses(db: Session, repo_id: int) -> None:
    """API 호출 도달에 필요한 최소 Analysis 2건 seed (analysis_count > 0 조건 충족).

    Seeds 2 Analysis rows so kpi["analysis_count"]["value"] > 0
    and the function reaches the Claude API call.
    """
    _make_analysis(db, repo_id, 80, offset_hours=1)
    _make_analysis(db, repo_id, 85, offset_hours=2)


# ─── 공통 assertion 헬퍼 ────────────────────────────────────────────────────


def _assert_api_error_response(result: dict[str, Any]) -> None:
    """api_error status + 4 카드 빈 list 공통 검증.

    Asserts the standard api_error response shape: status + empty 4 cards.
    """
    assert result["status"] == "api_error", (
        f"Expected status='api_error' but got '{result['status']}'"
    )
    assert result["positive_highlights"] == [], (
        f"Expected empty positive_highlights, got: {result['positive_highlights']}"
    )
    assert result["focus_areas"] == [], (
        f"Expected empty focus_areas, got: {result['focus_areas']}"
    )
    assert result["key_metrics"] == [], (
        f"Expected empty key_metrics, got: {result['key_metrics']}"
    )
    assert result["next_actions"] == [], (
        f"Expected empty next_actions, got: {result['next_actions']}"
    )


# ─── Tests ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_error_on_connect_error(db, seeded_repo):
    """httpx.ConnectError("Connection refused") → status=api_error + 4 카드 빈 list.

    ConnectError 는 네트워크 수준 연결 거부 — `except Exception` 범위 포함 검증.
    ConnectError is a network-level connection refusal — must be caught by `except Exception`.
    """
    _seed_two_analyses(db, seeded_repo.id)

    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    with patch(
        "src.services.dashboard_service.anthropic.AsyncAnthropic",
        return_value=fake_client,
    ):
        from src.services.dashboard_service import insight_narrative  # noqa: PLC0415

        # 예외가 호출자에게 propagate 되면 안 됨
        # Exception must NOT propagate to the caller
        result = await insight_narrative(db, days=7, api_key="sk-test")

    _assert_api_error_response(result)


@pytest.mark.asyncio
async def test_api_error_on_read_timeout(db, seeded_repo):
    """httpx.ReadTimeout() → status=api_error + 4 카드 빈 list.

    ReadTimeout 은 응답 수신 중 타임아웃 — `except Exception` 범위 포함 검증.
    ReadTimeout is a receive-side timeout — must be caught by `except Exception`.
    """
    _seed_two_analyses(db, seeded_repo.id)

    fake_client = MagicMock()
    # httpx.ReadTimeout 생성자 시그니처: ReadTimeout(message, *, request=None)
    # httpx.ReadTimeout constructor signature: ReadTimeout(message, *, request=None)
    fake_client.messages.create = AsyncMock(
        side_effect=httpx.ReadTimeout("Read timeout")
    )

    with patch(
        "src.services.dashboard_service.anthropic.AsyncAnthropic",
        return_value=fake_client,
    ):
        from src.services.dashboard_service import insight_narrative  # noqa: PLC0415

        result = await insight_narrative(db, days=7, api_key="sk-test")

    _assert_api_error_response(result)


@pytest.mark.asyncio
async def test_api_error_on_asyncio_timeout(db, seeded_repo):
    """asyncio.TimeoutError() → status=api_error + 4 카드 빈 list.

    asyncio.TimeoutError 는 asyncio.wait_for 또는 anyio 타임아웃 경로 — `except Exception` 범위 포함 검증.
    asyncio.TimeoutError arises from asyncio.wait_for / anyio timeout — must be caught by `except Exception`.
    """
    _seed_two_analyses(db, seeded_repo.id)

    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(
        side_effect=asyncio.TimeoutError()
    )

    with patch(
        "src.services.dashboard_service.anthropic.AsyncAnthropic",
        return_value=fake_client,
    ):
        from src.services.dashboard_service import insight_narrative  # noqa: PLC0415

        result = await insight_narrative(db, days=7, api_key="sk-test")

    _assert_api_error_response(result)
