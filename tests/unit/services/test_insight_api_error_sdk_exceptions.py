"""insight_narrative — Anthropic SDK 예외 타입별 api_error 경로 검증.

Verifies that each Anthropic SDK exception type results in status='api_error'.

검증 대상:
    src/services/dashboard_service.py::insight_narrative()
    src/services/dashboard_service.py::_call_insight_claude_api()

담당 케이스 (5종):
    1. anthropic.APITimeoutError       — 타임아웃
    2. anthropic.RateLimitError        — rate limit 429
    3. anthropic.APIConnectionError    — 네트워크 연결 실패
    4. anthropic.InternalServerError   — Anthropic 5xx
    5. anthropic.AuthenticationError   — 잘못된 API key
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database import Base
from src.models.analysis import Analysis  # noqa: F401  (Base.metadata 등록 / register on metadata)
from src.models.repository import Repository  # noqa: F401
from src.models.user import User  # noqa: F401


# ─── httpx 객체 헬퍼 ─────────────────────────────────────────────────────────


def _fake_request() -> httpx.Request:
    """Anthropic SDK 예외 생성자에 필요한 dummy httpx.Request.

    Dummy httpx.Request required by Anthropic SDK exception constructors.
    """
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _fake_response(status_code: int) -> httpx.Response:
    """Anthropic SDK 예외 생성자에 필요한 dummy httpx.Response.

    Dummy httpx.Response required by Anthropic SDK exception constructors.
    """
    return httpx.Response(
        status_code,
        request=_fake_request(),
        json={"error": {"type": "test_error", "message": "test"}},
    )


# ─── Anthropic SDK 예외 인스턴스 팩토리 ────────────────────────────────────────


def _make_timeout_error() -> anthropic.APITimeoutError:
    """anthropic.APITimeoutError 인스턴스 생성.

    Instantiate anthropic.APITimeoutError.
    """
    return anthropic.APITimeoutError(request=_fake_request())


def _make_rate_limit_error() -> anthropic.RateLimitError:
    """anthropic.RateLimitError (HTTP 429) 인스턴스 생성.

    Instantiate anthropic.RateLimitError (HTTP 429).
    """
    return anthropic.RateLimitError(
        "Rate limit exceeded",
        response=_fake_response(429),
        body={"error": {"type": "rate_limit_error"}},
    )


def _make_connection_error() -> anthropic.APIConnectionError:
    """anthropic.APIConnectionError (네트워크 연결 실패) 인스턴스 생성.

    Instantiate anthropic.APIConnectionError (network connection failure).
    """
    return anthropic.APIConnectionError(
        message="Connection error.",
        request=_fake_request(),
    )


def _make_internal_server_error() -> anthropic.InternalServerError:
    """anthropic.InternalServerError (5xx) 인스턴스 생성.

    Instantiate anthropic.InternalServerError (5xx).
    """
    return anthropic.InternalServerError(
        "Internal server error",
        response=_fake_response(500),
        body={"error": {"type": "internal_server_error"}},
    )


def _make_authentication_error() -> anthropic.AuthenticationError:
    """anthropic.AuthenticationError (잘못된 API key) 인스턴스 생성.

    Instantiate anthropic.AuthenticationError (invalid API key).
    """
    return anthropic.AuthenticationError(
        "Invalid API key",
        response=_fake_response(401),
        body={"error": {"type": "authentication_error"}},
    )


# ─── DB Fixtures ─────────────────────────────────────────────────────────────


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
    """Analysis FK 충족을 위한 user + repo 1건 seed.

    Seeds one user + one repo so Analysis rows have valid FKs.
    """
    user = User(github_id=42, github_login="tester", email="tester@x.com", display_name="Tester")
    db.add(user)
    db.commit()
    db.refresh(user)

    repo = Repository(full_name="tester/sdk-exc-repo", user_id=user.id)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


def _seed_analyses(db: Session, repo_id: int, count: int = 2) -> None:
    """Claude API 호출 경로에 도달하도록 Analysis rows를 최소 2건 seed.

    Seeds Analysis rows so the no_data early return is bypassed and
    the code reaches the Claude API call path.
    """
    for i in range(count):
        created = datetime.now(timezone.utc) - timedelta(hours=i * 6)
        a = Analysis(
            repo_id=repo_id,
            commit_sha=f"sha-{uuid.uuid4().hex}",
            score=80 + i,
            grade="B",
            result={"issues": []},
            created_at=created,
        )
        db.add(a)
    db.commit()


# ─── 공용 assertion 헬퍼 ───────────────────────────────────────────────────


def _assert_api_error_response(result: dict) -> None:
    """api_error status + 4 카드 모두 빈 list 검증.

    Asserts status=='api_error' and all 4 card lists are empty.
    """
    assert result["status"] == "api_error", (
        f"Expected status='api_error' but got '{result['status']}'"
    )
    assert result["positive_highlights"] == [], f"positive_highlights should be empty: {result['positive_highlights']}"
    assert result["focus_areas"] == [], f"focus_areas should be empty: {result['focus_areas']}"
    assert result["key_metrics"] == [], f"key_metrics should be empty: {result['key_metrics']}"
    assert result["next_actions"] == [], f"next_actions should be empty: {result['next_actions']}"


# ─── 공용 테스트 헬퍼 ─────────────────────────────────────────────────────────


async def _run_insight_with_sdk_exc(db: Session, repo_id: int, exc: Exception) -> dict:
    """Analysis seed + SDK 예외 side_effect → insight_narrative 실행.

    Seeds data, patches AsyncAnthropic so messages.create raises exc,
    then calls insight_narrative and returns the result.
    """
    _seed_analyses(db, repo_id)

    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(side_effect=exc)

    with patch(
        "src.services.dashboard_service.anthropic.AsyncAnthropic",
        return_value=fake_client,
    ):
        from src.services.dashboard_service import insight_narrative  # noqa: PLC0415
        result = await insight_narrative(db, days=7, api_key="sk-test-key")

    return result


# ─── 케이스 1: APITimeoutError ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_timeout_error_returns_api_error(db, seeded_repo):
    """anthropic.APITimeoutError 발생 시 status='api_error' + 4 카드 빈 list.

    When messages.create raises APITimeoutError, insight_narrative must return
    status='api_error' with all 4 card lists empty (no exception propagation).
    """
    exc = _make_timeout_error()
    result = await _run_insight_with_sdk_exc(db, seeded_repo.id, exc)
    _assert_api_error_response(result)


# ─── 케이스 2: RateLimitError ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rate_limit_error_returns_api_error(db, seeded_repo):
    """anthropic.RateLimitError (429) 발생 시 status='api_error' + 4 카드 빈 list.

    When messages.create raises RateLimitError (HTTP 429), insight_narrative must
    return status='api_error' with all 4 card lists empty.
    """
    exc = _make_rate_limit_error()
    result = await _run_insight_with_sdk_exc(db, seeded_repo.id, exc)
    _assert_api_error_response(result)


# ─── 케이스 3: APIConnectionError ────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_connection_error_returns_api_error(db, seeded_repo):
    """anthropic.APIConnectionError (네트워크 실패) 발생 시 status='api_error' + 4 카드 빈 list.

    When messages.create raises APIConnectionError (network failure), insight_narrative
    must return status='api_error' with all 4 card lists empty.
    """
    exc = _make_connection_error()
    result = await _run_insight_with_sdk_exc(db, seeded_repo.id, exc)
    _assert_api_error_response(result)


# ─── 케이스 4: InternalServerError ──────────────────────────────────────


@pytest.mark.asyncio
async def test_internal_server_error_returns_api_error(db, seeded_repo):
    """anthropic.InternalServerError (5xx) 발생 시 status='api_error' + 4 카드 빈 list.

    When messages.create raises InternalServerError (HTTP 5xx), insight_narrative
    must return status='api_error' with all 4 card lists empty.
    """
    exc = _make_internal_server_error()
    result = await _run_insight_with_sdk_exc(db, seeded_repo.id, exc)
    _assert_api_error_response(result)


# ─── 케이스 5: AuthenticationError ──────────────────────────────────────


@pytest.mark.asyncio
async def test_authentication_error_returns_api_error(db, seeded_repo):
    """anthropic.AuthenticationError (잘못된 API key) 발생 시 status 확인.

    When messages.create raises AuthenticationError (invalid API key), verifies
    the returned status. Per the implementation, _call_insight_claude_api catches ALL
    exceptions and returns None → insight_narrative maps None to 'api_error'.
    AuthenticationError would only return 'no_api_key' if caught BEFORE the API call
    (i.e. at the key presence check), but here the key is non-empty, so the
    exception occurs at call-time and must yield 'api_error'.
    """
    exc = _make_authentication_error()
    result = await _run_insight_with_sdk_exc(db, seeded_repo.id, exc)
    # AuthenticationError at call-time (non-empty key supplied) → api_error path
    # AuthenticationError 가 call-time 에 발생하면 (비어있지 않은 key) → api_error 경로
    _assert_api_error_response(result)
