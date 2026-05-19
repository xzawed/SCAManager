"""insight_narrative 캐시 레이어 + api_error 상호작용 단위 테스트.

Unit tests for insight_narrative cache layer + api_error interaction.

검증 케이스 (2종):
    케이스 1 — api_error 발생 시 cache upsert 호출 안 됨
        : API → RuntimeError → api_error 반환, upsert 0회
        : 두 번째 호출도 cache miss → API 다시 호출됨 (upsert 여전히 0회)

    케이스 2 — api_error 후 재시도 시 success 복구
        : 첫 번째 API → RuntimeError → api_error
        : 두 번째 API → valid JSON → success 반환 + upsert 1회

두 케이스 모두:
    - in-memory SQLite + User / Repository / Analysis / InsightNarrativeCache ORM 테이블
    - `insight_narrative_cache_repo.upsert` mock 으로 호출 횟수 검증
    - `_call_insight_claude_api` 를 직접 patch 해 `side_effect` 로 순서 제어
      (anthropic.AsyncAnthropic 생성 우회)

Both test cases use:
    - in-memory SQLite with User / Repository / Analysis / InsightNarrativeCache ORM tables
    - Mocked `insight_narrative_cache_repo.upsert` to assert call count
    - Direct patch of `_call_insight_claude_api` with `side_effect` for sequence control
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models.analysis import Analysis  # noqa: F401  (Base.metadata 등록 / register on metadata)
from src.models.insight_narrative_cache import InsightNarrativeCache  # noqa: F401
from src.models.repository import Repository  # noqa: F401
from src.models.user import User  # noqa: F401
from src.services import dashboard_service


# ─── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def db():
    """모든 ORM 테이블이 생성된 in-memory SQLite 세션.

    Provides an in-memory SQLite session with all ORM tables created.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def seeded_user_and_repo(db):
    """user + repo 1건 seed — user_id 명시 케이스의 FK 충족용.

    Seeds one user + one repo for user_id-scoped test cases.
    """
    user = User(
        github_id="cache_error_uid_1",
        github_login="cache_error_user",
        email="cache_error@x.com",
        display_name="CacheErrorUser",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    repo = Repository(full_name="cache_error_user/repo", user_id=user.id)
    db.add(repo)
    db.commit()
    db.refresh(repo)

    return user, repo


def _make_analysis(
    db: Session,
    repo_id: int,
    score: int,
    *,
    offset_hours: int = 0,
    result: dict[str, Any] | None = None,
) -> Analysis:
    """Analysis 레코드 헬퍼 — 점수 / created_at offset / result dict 주입 가능.

    Helper to insert an Analysis row with configurable score / created_at / result.
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
    """kpi["analysis_count"]["value"] > 0 조건 충족을 위한 최소 Analysis 2건 seed.

    Seeds 2 Analysis rows so the function passes the no_data guard and reaches
    the Claude API call.
    """
    _make_analysis(db, repo_id, 80, offset_hours=1)
    _make_analysis(db, repo_id, 85, offset_hours=2)


def _make_valid_json() -> str:
    """유효한 4 카드 JSON 문자열 반환 (parse_insight_cards 통과).

    Returns a valid 4-card JSON string that passes _parse_insight_cards.
    """
    return (
        '{"positive_highlights":["강점 항목 1","강점 항목 2","강점 항목 3"],'
        '"focus_areas":["개선 항목 1","개선 항목 2","개선 항목 3"],'
        '"key_metrics":['
        '{"label":"평균 점수","value":"82.5","delta":"+2.5"},'
        '{"label":"분석 건수","value":"2","delta":"0"},'
        '{"label":"보안 HIGH","value":"0","delta":"0"},'
        '{"label":"활성 리포","value":"1","delta":"0"}],'
        '"next_actions":["다음 액션 1","다음 액션 2"]}'
    )


# ─── 케이스 1: api_error 발생 시 cache upsert 호출 안 됨 ────────────────────


@pytest.mark.asyncio
async def test_api_error_does_not_call_upsert(db, seeded_user_and_repo):
    """api_error 반환 시 insight_narrative_cache_repo.upsert 가 호출되지 않음.

    When _call_insight_claude_api returns None (mapped to api_error),
    the cache upsert must NOT be called — error responses must never be cached.

    Code-level guard (dashboard_service.py line 861-867):
        if text is None:
            return _build_insight_response(status="api_error", days=days)  # upsert 도달 X
        ...
        if user_id is not None:
            insight_narrative_cache_repo.upsert(...)  # 이 줄에 도달하지 않음
    """
    user, repo = seeded_user_and_repo
    _seed_two_analyses(db, repo.id)

    # _call_insight_claude_api 가 None 을 반환하도록 mock
    # Mock _call_insight_claude_api to return None (simulates RuntimeError caught internally)
    with patch.object(
        dashboard_service, "_call_insight_claude_api",
        new=AsyncMock(return_value=None),
    ) as mock_api, \
         patch(
             "src.repositories.insight_narrative_cache_repo.upsert",
         ) as mock_upsert:
        result = await dashboard_service.insight_narrative(
            db, days=7, user_id=user.id, api_key="sk-test",
        )

    # api_error 반환 확인
    # Assert api_error is returned
    assert result["status"] == "api_error", (
        f"Expected status='api_error', got '{result['status']}'"
    )
    assert result["positive_highlights"] == []
    assert result["focus_areas"] == []
    assert result["key_metrics"] == []
    assert result["next_actions"] == []

    # upsert 가 한 번도 호출되지 않았는지 확인
    # Assert upsert was NOT called
    mock_upsert.assert_not_called()

    # _call_insight_claude_api 는 1회 호출됨 (캐시 없으므로 API 도달)
    # _call_insight_claude_api was called exactly once (no cache hit)
    mock_api.assert_awaited_once()


@pytest.mark.asyncio
async def test_api_error_second_call_retries_api_not_cached(db, seeded_user_and_repo):
    """api_error 후 두 번째 호출 시 캐시 없으므로 API 다시 호출됨.

    After an api_error, there is no cached entry, so the second call must
    invoke the Claude API again (no stale cache served).

    케이스 1 연장: 1차 api_error → 캐시 row 0개 → 2차 호출 시 API 재호출 확인.
    Case 1 extension: first api_error → 0 cache rows → second call hits API again.
    """
    user, repo = seeded_user_and_repo
    _seed_two_analyses(db, repo.id)

    # 두 번 모두 None 반환 (api_error 지속)
    # Both calls return None (persistent api_error)
    with patch.object(
        dashboard_service, "_call_insight_claude_api",
        new=AsyncMock(return_value=None),
    ) as mock_api, \
         patch(
             "src.repositories.insight_narrative_cache_repo.upsert",
         ) as mock_upsert:
        result1 = await dashboard_service.insight_narrative(
            db, days=7, user_id=user.id, api_key="sk-test",
        )
        result2 = await dashboard_service.insight_narrative(
            db, days=7, user_id=user.id, api_key="sk-test",
        )

    # 두 결과 모두 api_error
    # Both results should be api_error
    assert result1["status"] == "api_error"
    assert result2["status"] == "api_error"

    # upsert 전혀 호출 안 됨 (두 호출 합산)
    # upsert never called across both invocations
    mock_upsert.assert_not_called()

    # API 는 두 번 호출됨 — 캐시가 없어 매번 도달
    # API called twice — no cache entry means each call reaches the API
    assert mock_api.await_count == 2, (
        f"Expected 2 API calls (no cache between retries), got {mock_api.await_count}"
    )

    # DB 에 에러 추적 row 1개 존재 (0033 — record_error 신설)
    # After 0033: record_error creates 1 immediately-expired error-tracking row
    rows = db.query(InsightNarrativeCache).filter(
        InsightNarrativeCache.user_id == user.id,
    ).all()
    assert len(rows) == 1, f"Expected 1 error-tracking row after api_error, found {len(rows)}"
    row = rows[0]
    # 에러 추적 row 는 즉시 만료 상태여야 함 (get_fresh 차단 없음)
    # Error-tracking row must be immediately expired (never blocks fresh retry)
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    assert expires <= datetime.now(timezone.utc) + timedelta(seconds=2), (
        "Error-tracking row must be immediately expired"
    )
    assert row.error_count >= 2, "Both api_error calls should be counted"


# ─── 케이스 2: api_error 후 재시도 시 success 복구 ─────────────────────────


@pytest.mark.asyncio
async def test_api_error_then_success_recovery(db, seeded_user_and_repo):
    """첫 번째 api_error 후 두 번째 호출이 success 로 복구됨.

    First call: _call_insight_claude_api returns None → api_error (no cache write).
    Second call: _call_insight_claude_api returns valid JSON → success + cache upsert.

    side_effect=[None, valid_json] 패턴으로 순서 제어.
    Uses side_effect=[None, valid_json] to control the call sequence.

    Code-level trace:
        1st call: text=None → return api_error (upsert 건너뜀)
        2nd call: get_fresh → None (캐시 없음) → text=valid_json → parse → upsert 호출
    """
    user, repo = seeded_user_and_repo
    _seed_two_analyses(db, repo.id)

    valid_json = _make_valid_json()

    # side_effect 순서: 1차=None(api_error), 2차=valid JSON(success)
    # side_effect order: 1st=None (api_error), 2nd=valid JSON (success)
    with patch.object(
        dashboard_service, "_call_insight_claude_api",
        new=AsyncMock(side_effect=[None, valid_json]),
    ) as mock_api:
        # 1차 호출 — api_error 예상
        # First call — expect api_error
        result1 = await dashboard_service.insight_narrative(
            db, days=7, user_id=user.id, api_key="sk-test",
        )

        # 2차 호출 — success 예상
        # Second call — expect success
        result2 = await dashboard_service.insight_narrative(
            db, days=7, user_id=user.id, api_key="sk-test",
        )

    # 1차 결과: api_error + 4 카드 빈 list
    # First result: api_error + empty 4 cards
    assert result1["status"] == "api_error", (
        f"Expected 1st call status='api_error', got '{result1['status']}'"
    )
    assert result1["positive_highlights"] == []
    assert result1["focus_areas"] == []
    assert result1["key_metrics"] == []
    assert result1["next_actions"] == []

    # 2차 결과: success + 내용 있는 카드
    # Second result: success + populated cards
    assert result2["status"] == "success", (
        f"Expected 2nd call status='success', got '{result2['status']}'"
    )
    assert len(result2["positive_highlights"]) > 0, (
        "Expected non-empty positive_highlights on success recovery"
    )
    assert len(result2["focus_areas"]) > 0
    assert len(result2["key_metrics"]) == 4
    assert len(result2["next_actions"]) > 0

    # API 정확히 2회 호출 확인 (side_effect 소진)
    # Confirm exactly 2 API calls (side_effect exhausted)
    assert mock_api.await_count == 2, (
        f"Expected 2 API calls total, got {mock_api.await_count}"
    )

    # 2차 success 후 DB 에 캐시 row 1개 저장됨
    # After 2nd success, exactly 1 cache row should exist in DB
    rows = db.query(InsightNarrativeCache).filter(
        InsightNarrativeCache.user_id == user.id,
        InsightNarrativeCache.days == 7,
    ).all()
    assert len(rows) == 1, (
        f"Expected 1 cache row after success recovery, found {len(rows)}"
    )
    cached_response = rows[0].response_json
    assert cached_response["status"] == "success"
    assert len(cached_response["positive_highlights"]) > 0
