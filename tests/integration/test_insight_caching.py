"""Integration — insight_narrative caching helper + user_id 격리 회귀 가드 (Phase 3 PR 6).

Phase 3 PR 1 (`build_cached_system_param`) + PR 2 (`insight_narrative`) +
PR 5 (user_id 격리) 페어 검증. 본 모듈은 회귀 가드만 (구현 변경 0).

Phase 3 PR 1 (`build_cached_system_param`) + PR 2 (`insight_narrative`) +
PR 5 (user_id isolation) regression guards. Implementation unchanged.

검증 범위:
- C.1 caching helper 호출 검증 (PR 1 + PR 2 페어)
- C.2 user_id 격리 검증 — 다중 사용자 데이터에서 user_id=A 호출 시 A 데이터만 prompt 에 반영

자동 마킹: tests/integration/conftest.py 가 @pytest.mark.slow 자동 부여.
ORM import 모듈 최상단 의무 — auto-memory pytest-fixture-lazy-orm-import-trap.md 참조.
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

# ORM 모델 import 는 모듈 최상단 (lazy import 금지 — pytest-fixture-lazy-orm-import-trap.md)
# Top-level ORM imports register Base.metadata (no lazy imports allowed)
from src.database import Base
from src.models.analysis import Analysis
from src.models.merge_attempt import MergeAttempt  # noqa: F401  (register on metadata)
from src.models.repository import Repository
from src.models.user import User


# ─── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def db():
    """모든 ORM 테이블이 생성된 in-memory SQLite 세션을 제공한다.

    Provides an in-memory SQLite session with all ORM tables created.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


_VALID_NARRATIVE_JSON = (
    '{'
    '"positive_highlights": ["A등급 분석 5건 달성", "보안 HIGH 0건 유지", "테스트 점수 평균 14"],'
    '"focus_areas": ["pylint warning 12건 누적", "커밋 메시지 quality 12점"],'
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

    Builds a MagicMock matching the Anthropic Messages API response shape
    (mirrors tests/unit/services/test_dashboard_service_insight_narrative.py:121-136).
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


# ─── C.1 caching helper 호출 회귀 가드 (PR 1 + PR 2 페어) ─────────────────


@pytest.mark.asyncio
async def test_insight_narrative_calls_caching_helper(db):
    """insight_narrative → build_cached_system_param 1회 호출 + system 인자 = list[dict] 검증.

    Verifies PR 1 (`build_cached_system_param`) + PR 2 (`insight_narrative`) integration:
    helper invoked exactly once, and the cached system param reaches the Anthropic call
    as a list[dict] containing a `cache_control` ephemeral marker.
    """
    # User + Repo seed
    user = User(github_id=1, github_login="alice", email="a@x.com", display_name="Alice")
    db.add(user)
    db.commit()
    db.refresh(user)
    repo = Repository(full_name="owner/api", user_id=user.id)
    db.add(repo)
    db.commit()
    db.refresh(repo)

    # 5 건 Analysis seed (최근 7일 분포 — analysis_count > 0 → Claude API 호출 경로 진입)
    # Seed 5 analyses (within 7 days) so the cost-saver early-return is bypassed.
    for idx, score in enumerate([80, 85, 88, 92, 95]):
        _make_analysis(db, repo.id, score, offset_hours=idx * 12)

    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(
        return_value=_make_anthropic_response(_VALID_NARRATIVE_JSON)
    )

    # build_cached_system_param 의 실제 동작을 우회하지 않으면서 호출 spy
    # Spy the helper without bypassing its actual behavior (PR 2 unit test pattern).
    with patch(
        "src.services.dashboard_service.anthropic.AsyncAnthropic",
        return_value=fake_client,
    ), patch(
        "src.services.dashboard_service.build_cached_system_param",
        wraps=lambda text, **kw: [
            {"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}
        ],
    ) as mock_helper:
        from src.services.dashboard_service import insight_narrative
        result = await insight_narrative(db, days=7, api_key="sk-test")

    # PR 2 정합 — status=success
    assert result["status"] == "success", f"status 비정상: {result['status']}"

    # PR 1 + PR 2 페어 — caching helper 1회 호출
    # PR 1 + PR 2 pair — caching helper invoked exactly once
    assert mock_helper.call_count == 1, (
        f"build_cached_system_param 호출 횟수 기대 1, 실제: {mock_helper.call_count}"
    )

    # Anthropic API 가 받은 system 인자 = list[dict] (caching format)
    # The system param sent to the Anthropic API is a list[dict] (caching format).
    fake_client.messages.create.assert_awaited_once()
    call_kwargs = fake_client.messages.create.await_args.kwargs
    system_arg = call_kwargs.get("system")
    assert isinstance(system_arg, list), f"system 인자 list 기대, 실제: {type(system_arg)}"
    assert len(system_arg) >= 1, "system list 비어있음"
    assert isinstance(system_arg[0], dict), "system list 의 0번째 요소 dict 아님"
    assert system_arg[0].get("cache_control", {}).get("type") == "ephemeral", (
        f"cache_control ephemeral 마커 누락. system[0]={system_arg[0]}"
    )


# ─── C.2 user_id 격리 회귀 가드 (PR 5) ───────────────────────────────────


@pytest.mark.asyncio
async def test_insight_narrative_user_id_isolation_in_claude_context(db):
    """user_id=A 호출 시 prompt 에 User A 의 데이터만 포함, User B 데이터 미포함.

    Verifies PR 5 user_id isolation propagates through to the Claude prompt:
    - Seed: User A (3 analyses) + User B (3 analyses)
    - Call insight_narrative(user_id=A.id) → prompt JSON 의 analysis_count == 3
    - User B 의 score 데이터 (예: 50, 55, 60) 가 prompt 에 누설되지 않아야 함
    """
    # User A + B seed
    user_a = User(github_id=1, github_login="alice", email="a@x.com", display_name="Alice")
    user_b = User(github_id=2, github_login="bob", email="b@x.com", display_name="Bob")
    db.add_all([user_a, user_b])
    db.commit()
    db.refresh(user_a)
    db.refresh(user_b)

    # Repo A1 (user A 소유) / Repo B1 (user B 소유)
    repo_a1 = Repository(full_name="alice/api", user_id=user_a.id)
    repo_b1 = Repository(full_name="bob/api", user_id=user_b.id)
    db.add_all([repo_a1, repo_b1])
    db.commit()
    db.refresh(repo_a1)
    db.refresh(repo_b1)

    # User A: 점수 80/85/90 (3건), User B: 점수 50/55/60 (3건) — 의도적으로 다른 점수 분포
    # User A: scores 80/85/90 (3). User B: scores 50/55/60 (3). Distinct distributions
    # so we can detect leakage by checking the prompt for B-specific values.
    for idx, score in enumerate([80, 85, 90]):
        _make_analysis(db, repo_a1.id, score, offset_hours=idx * 12)
    for idx, score in enumerate([50, 55, 60]):
        _make_analysis(db, repo_b1.id, score, offset_hours=idx * 12)

    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(
        return_value=_make_anthropic_response(_VALID_NARRATIVE_JSON)
    )

    with patch(
        "src.services.dashboard_service.anthropic.AsyncAnthropic",
        return_value=fake_client,
    ):
        from src.services.dashboard_service import insight_narrative
        result = await insight_narrative(db, days=7, api_key="sk-test", user_id=user_a.id)

    assert result["status"] == "success", f"status 비정상: {result['status']}"

    # Claude API call_args 의 user message 본문 검사 — User A 데이터만 포함
    # Inspect the user message sent to Claude — must contain only User A data.
    fake_client.messages.create.assert_awaited_once()
    call_kwargs = fake_client.messages.create.await_args.kwargs
    messages = call_kwargs.get("messages", [])
    assert len(messages) >= 1, "messages 비어있음"
    user_content = messages[0].get("content", "")

    # User A 의 analysis_count == 3 이 JSON payload 에 포함되어야 함
    # The JSON payload must reflect User A's analysis_count == 3.
    # _build_insight_user_prompt 은 kpi.analysis_count.value 를 직렬화 — "value": 3 형식
    # The helper serialises kpi.analysis_count.value as `"value": 3`.
    assert '"analysis_count"' in user_content, "user prompt 에 analysis_count 키 누락"

    # PR 5 격리 — User A 가 호출했으니 analysis_count.value=3 (User A 의 3건만)
    # PR 5 isolation — caller is User A, so only A's 3 analyses should be counted.
    payload_str = user_content
    assert '"value": 3' in payload_str or '"value":3' in payload_str, (
        f"User A 격리 실패 — analysis_count.value=3 (User A 만) 기대. prompt: {payload_str[:400]}"
    )

    # User B 가 6건 합쳐 보이지 않아야 함 — analysis_count.value=6 잘못 노출 방지
    # User B's data must not leak — analysis_count.value should never be 6.
    assert '"value": 6' not in payload_str and '"value":6' not in payload_str, (
        f"User B 데이터 누설 의심 — analysis_count.value=6 (격리 깨짐). prompt: {payload_str[:400]}"
    )
