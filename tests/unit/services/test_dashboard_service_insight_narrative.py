"""dashboard_service.insight_narrative 단위 테스트 — Phase 3 PR 2 (TDD Red).

본 파일이 검증하는 함수 (구현 미존재 단계 — Red):
    src/services/dashboard_service.py::insight_narrative(db, days, *, now, api_key) -> dict

핵심 동작:
- DB seed (Analysis) → 4 개 dashboard 헬퍼 (kpi/trend/frequent/auto_merge) 호출 →
  Claude AI 가 4 카드 narrative 생성 (positive_highlights / focus_areas / key_metrics / next_actions).
- system prompt 는 PR 1 의 `build_cached_system_param` 헬퍼 경유 (5분 ephemeral cache).
- API key 없음 / 데이터 없음 / API 오류 / 파싱 오류 모두 graceful — status 필드로 시그널.

This module verifies the new `insight_narrative` async service function (TDD Red — not yet implemented).
The function reads dashboard context from DB, calls Claude AI (with prompt caching), and returns
a 4-card narrative dict. Failures are surfaced via the `status` field, never raised.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

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
    user = User(github_id=1, github_login="alice", email="a@x.com", display_name="Alice")
    db.add(user)
    db.commit()
    db.refresh(user)
    repo = Repository(full_name="owner/api", user_id=user.id)
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


def _seed_recent_analyses(db: Session, repo_id: int, scores: list[int]) -> None:
    """최근 7일 분포로 Analysis 여러 건 seed.

    Seeds multiple Analysis rows distributed across the last 7 days.
    """
    for idx, score in enumerate(scores):
        _make_analysis(db, repo_id, score, offset_hours=idx * 12)


# ─── Anthropic mock 헬퍼 ────────────────────────────────────────────────────


_VALID_NARRATIVE_JSON = (
    '{'
    '"positive_highlights": ["A등급 분석 5건 달성", "보안 HIGH 0건 유지", "테스트 점수 평균 14.2"],'
    '"focus_areas": ["pylint warning 12건 누적", "커밋 메시지 quality 12점 (스케일링 전)"],'
    '"key_metrics": ['
    '{"label": "평균 점수", "value": "84.2", "delta": "+3.1"},'
    '{"label": "분석 건수", "value": "5", "delta": "+2"},'
    '{"label": "보안 HIGH", "value": "0", "delta": "0"},'
    '{"label": "Auto-merge 성공", "value": "100%", "delta": "+10%"}'
    '],'
    '"next_actions": ["pylint 경고 해소", "커밋 메시지 가이드 공유"]'
    '}'
)


def _make_anthropic_response(text: str) -> MagicMock:
    """Anthropic Messages API 응답 객체 mock — content[0].text + usage.

    Builds a MagicMock matching the Anthropic Messages API response shape.
    """
    fake_msg = MagicMock()
    text_block = MagicMock()
    text_block.text = text
    fake_msg.content = [text_block]
    fake_msg.usage = MagicMock(
        input_tokens=100,
        output_tokens=50,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=100,
    )
    return fake_msg


# ─── Tests (TDD Red) ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_insight_narrative_returns_4_cards_on_success(db, seeded_repo):
    """정상 경로 — DB seed + Claude 응답 valid JSON → 4 카드 narrative + status=success."""
    # 데이터 seed (5건, 80~95 점수 분포, 최근 7일)
    # Seed 5 analyses (scores 80-95, distributed in last 7 days)
    _seed_recent_analyses(db, seeded_repo.id, [80, 85, 88, 92, 95])

    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(
        return_value=_make_anthropic_response(_VALID_NARRATIVE_JSON)
    )

    # 구현부에서 anthropic.AsyncAnthropic 을 사용한다고 가정
    # Assumes the implementation uses anthropic.AsyncAnthropic
    with patch(
        "src.services.dashboard_service.anthropic.AsyncAnthropic",
        return_value=fake_client,
    ):
        from src.services.dashboard_service import insight_narrative  # late import (TDD Red)
        result = await insight_narrative(db, days=7, api_key="sk-test")

    assert result["status"] == "success"
    assert len(result["positive_highlights"]) == 3
    assert len(result["focus_areas"]) == 2
    assert len(result["key_metrics"]) == 4
    assert len(result["next_actions"]) == 2
    assert result["days"] == 7
    # ISO 8601 형식 검증 — fromisoformat 으로 round-trip 가능해야 함
    # Verify ISO 8601 format — must round-trip through fromisoformat
    assert result["generated_at"] is not None
    datetime.fromisoformat(result["generated_at"].replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_insight_narrative_no_api_key_returns_empty_cards(db, seeded_repo):
    """API key 미설정 (빈 문자열) → status=no_api_key + 4 카드 빈 list, Claude 호출 X."""
    _seed_recent_analyses(db, seeded_repo.id, [85, 90])

    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(
        return_value=_make_anthropic_response(_VALID_NARRATIVE_JSON)
    )

    with patch(
        "src.services.dashboard_service.anthropic.AsyncAnthropic",
        return_value=fake_client,
    ):
        from src.services.dashboard_service import insight_narrative
        result = await insight_narrative(db, days=7, api_key="")

    assert result["status"] == "no_api_key"
    assert result["positive_highlights"] == []
    assert result["focus_areas"] == []
    assert result["key_metrics"] == []
    assert result["next_actions"] == []
    # Claude API 호출이 일어나면 안 됨 (early return)
    # Claude API must NOT be called (early return on missing key)
    fake_client.messages.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_insight_narrative_no_data_returns_no_data_status(db):
    """DB 빈 (Analysis 0건) → status=no_data + 4 카드 빈 list, Claude 호출 X."""
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(
        return_value=_make_anthropic_response(_VALID_NARRATIVE_JSON)
    )

    with patch(
        "src.services.dashboard_service.anthropic.AsyncAnthropic",
        return_value=fake_client,
    ):
        from src.services.dashboard_service import insight_narrative
        result = await insight_narrative(db, days=7, api_key="sk-test")

    assert result["status"] == "no_data"
    assert result["positive_highlights"] == []
    assert result["focus_areas"] == []
    assert result["key_metrics"] == []
    assert result["next_actions"] == []
    # 데이터 0건이면 Claude API 호출 비용 발생 안 시킴
    # Skip the Claude API call when there is no data (cost-saver)
    fake_client.messages.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_insight_narrative_uses_caching_helper(db, seeded_repo):
    """system prompt 가 PR 1 의 build_cached_system_param 헬퍼 경유 — 1회 호출 + str 인자."""
    _seed_recent_analyses(db, seeded_repo.id, [80, 85, 90])

    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(
        return_value=_make_anthropic_response(_VALID_NARRATIVE_JSON)
    )

    # build_cached_system_param 의 실제 동작을 우회하지 않으면서 호출 카운트만 spy
    # Spy the helper without bypassing its actual behavior
    with patch(
        "src.services.dashboard_service.anthropic.AsyncAnthropic",
        return_value=fake_client,
    ), patch(
        "src.services.dashboard_service.build_cached_system_param",
        wraps=lambda text, **kw: [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}],
    ) as mock_helper:
        from src.services.dashboard_service import insight_narrative
        await insight_narrative(db, days=7, api_key="sk-test")

    # 1 회 호출
    # Called exactly once
    assert mock_helper.call_count == 1
    # 첫 위치 인자가 str 인지 검증 (system prompt 본문)
    # First positional arg must be the system prompt string
    args, _kwargs = mock_helper.call_args
    assert isinstance(args[0], str)
    assert len(args[0]) > 0


@pytest.mark.asyncio
async def test_insight_narrative_api_error_graceful(db, seeded_repo):
    """Claude API 호출이 예외 raise → status=api_error + 4 카드 빈 list, 예외 propagate X."""
    _seed_recent_analyses(db, seeded_repo.id, [85, 90])

    fake_client = MagicMock()
    # generic Exception 으로 검증 (anthropic.APIError 도 동일 graceful 경로)
    # Use a generic Exception (anthropic.APIError follows the same graceful path)
    fake_client.messages.create = AsyncMock(side_effect=RuntimeError("simulated API failure"))

    with patch(
        "src.services.dashboard_service.anthropic.AsyncAnthropic",
        return_value=fake_client,
    ):
        from src.services.dashboard_service import insight_narrative
        # 예외가 호출자에게 전파되면 안 됨
        # Exception must NOT propagate to the caller
        result = await insight_narrative(db, days=7, api_key="sk-test")

    assert result["status"] == "api_error"
    assert result["positive_highlights"] == []
    assert result["focus_areas"] == []
    assert result["key_metrics"] == []
    assert result["next_actions"] == []


@pytest.mark.asyncio
async def test_insight_narrative_parse_error_returns_parse_error_status(db, seeded_repo):
    """Claude 응답이 invalid JSON → status=parse_error + 4 카드 빈 list."""
    _seed_recent_analyses(db, seeded_repo.id, [85, 90])

    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(
        return_value=_make_anthropic_response("not a json text — Claude returned prose only")
    )

    with patch(
        "src.services.dashboard_service.anthropic.AsyncAnthropic",
        return_value=fake_client,
    ):
        from src.services.dashboard_service import insight_narrative
        result = await insight_narrative(db, days=7, api_key="sk-test")

    assert result["status"] == "parse_error"
    assert result["positive_highlights"] == []
    assert result["focus_areas"] == []
    assert result["key_metrics"] == []
    assert result["next_actions"] == []
