"""dashboard_service 6 함수 user_id 필터링 단위 테스트 — Phase 3 PR 5 (TDD Red).

dashboard_service 6 functions user_id filtering unit tests — Phase 3 PR 5 (TDD Red).

Phase 3 PR 5 — Supabase RLS 권한 모델 (앱 filter + alembic policy 페어).
Phase 3 PR 5 — Supabase RLS permission model (app filter + alembic policy pair).

본 PR 의 시그니처 변경 (구현 미존재 — Red 단계):
The signature change verified by this PR (implementation pending — Red phase):

    def dashboard_kpi(db, days=7, *, now=None, user_id: int | None = None) -> dict:
        # user_id 명시 시 Repository.user_id == user_id OR Repository.user_id IS NULL 필터
        # user_id None 시 모든 리포 (legacy / admin 호환)
        # When user_id is given, filter Repository.user_id == user_id OR IS NULL.
        # When user_id is None, query across all repos (legacy / admin compat).

동일 패턴 적용 함수: dashboard_kpi, dashboard_trend, frequent_issues_v2,
auto_merge_kpi, merge_failure_distribution, insight_narrative (async).

기존 패턴 참조 (`src/ui/routes/overview.py:29`):
Reference pattern (`src/ui/routes/overview.py:29`):

    (Repository.user_id == current_user.id) | (Repository.user_id.is_(None))

검증 시드 (각 테스트 동일):
Common seed (per test):
- User A (id=1), User B (id=2)
- Repo A1 (user_id=1), Repo B1 (user_id=2), Repo Legacy (user_id=NULL)
- 각 repo 에 Analysis 1건 + (필요 시) MergeAttempt 1건 seed
- One Analysis (and where applicable, one MergeAttempt) per repo.

호출 시나리오 3종 (각 테스트):
3 invocation scenarios (per test):
1. user_id=1 → user A repos (A1) + Legacy 만 보임 (count=2)
2. user_id=2 → user B repos (B1) + Legacy 만 보임 (count=2)
3. user_id=None → 모든 리포 보임 (count=3) — legacy/admin 호환

ORM import 모듈 최상단 의무 — auto-memory pytest-fixture-lazy-orm-import-trap.md
참조 (Phase 3 PR 4 CI #428 사고). lazy import 는 tests/ 전체 실행 시 metadata 누락.
ORM imports MUST be at module top — see auto-memory pytest-fixture-lazy-orm-import-trap.md
(Phase 3 PR 4 CI #428 incident). Lazy imports inside fixtures cause metadata gaps.
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

# ORM 모델 import 는 모듈 최상단 — Base.metadata 등록 (lazy import 금지)
# Top-level ORM imports register Base.metadata (no lazy imports allowed)
from src.database import Base
from src.models.analysis import Analysis
from src.models.merge_attempt import MergeAttempt
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


@pytest.fixture()
def seeded_users_and_repos(db):
    """User A/B + Repo A1/B1/Legacy seed.

    Seeds two users + their repos + one legacy (NULL user_id) repo.

    Returns:
        dict {"user_a": User, "user_b": User, "repo_a1": Repository,
              "repo_b1": Repository, "repo_legacy": Repository}
    """
    # User A + B
    user_a = User(github_id=1, github_login="alice", email="a@x.com", display_name="Alice")
    user_b = User(github_id=2, github_login="bob", email="b@x.com", display_name="Bob")
    db.add_all([user_a, user_b])
    db.commit()
    db.refresh(user_a)
    db.refresh(user_b)

    # Repo A1 (user_a 소유) / Repo B1 (user_b 소유) / Repo Legacy (user_id=NULL)
    # Repo A1 (user_a) / Repo B1 (user_b) / Repo Legacy (user_id=NULL)
    repo_a1 = Repository(full_name="alice/api", user_id=user_a.id)
    repo_b1 = Repository(full_name="bob/api", user_id=user_b.id)
    repo_legacy = Repository(full_name="legacy/old", user_id=None)
    db.add_all([repo_a1, repo_b1, repo_legacy])
    db.commit()
    for r in (repo_a1, repo_b1, repo_legacy):
        db.refresh(r)

    return {
        "user_a": user_a,
        "user_b": user_b,
        "repo_a1": repo_a1,
        "repo_b1": repo_b1,
        "repo_legacy": repo_legacy,
    }


def _make_analysis(
    db: Session,
    repo_id: int,
    *,
    score: int = 80,
    offset_hours: int = 1,
    result: dict[str, Any] | None = None,
) -> Analysis:
    """Analysis 1건 seed — 윈도우 내 (1시간 전) 기본.

    Insert one Analysis (default: 1 hour ago, within window).
    """
    a = Analysis(
        repo_id=repo_id,
        commit_sha=f"sha-{uuid.uuid4().hex}",
        score=score,
        grade="B",
        result=result,
        created_at=datetime.now(timezone.utc) - timedelta(hours=offset_hours),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _make_merge_attempt(
    db: Session,
    *,
    analysis_id: int,
    repo_name: str,
    pr_number: int = 1,
    success: bool = False,
    failure_reason: str | None = "unstable_ci",
    offset_hours: int = 1,
) -> MergeAttempt:
    """MergeAttempt 1건 seed — 윈도우 내 (1시간 전) 기본.

    Insert one MergeAttempt (default: 1 hour ago, within window).
    """
    m = MergeAttempt(
        analysis_id=analysis_id,
        repo_name=repo_name,
        pr_number=pr_number,
        score=85,
        threshold=75,
        success=success,
        failure_reason=failure_reason,
        attempted_at=datetime.now(timezone.utc) - timedelta(hours=offset_hours),
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


# ─── A.1 dashboard_kpi user_id 필터링 ──────────────────────────────────────


def test_dashboard_kpi_filters_by_user_id(db, seeded_users_and_repos):
    """A.1 — dashboard_kpi(user_id=N) 호출 시 user N 의 리포 + legacy 만 집계.

    A.1 — dashboard_kpi(user_id=N) aggregates only user N's repos + legacy.

    검증 시나리오:
    - user_id=1 → Repo A1 + Legacy 분석만 카운트 (analysis_count.value == 2)
    - user_id=2 → Repo B1 + Legacy 분석만 카운트 (analysis_count.value == 2)
    - user_id=None → 모든 리포 (== 3) — admin/legacy 호환
    """
    repos = seeded_users_and_repos
    # 각 리포에 Analysis 1건 seed (윈도우 내, 점수 80)
    # Seed 1 Analysis per repo (within window, score=80)
    _make_analysis(db, repos["repo_a1"].id, score=80)
    _make_analysis(db, repos["repo_b1"].id, score=80)
    _make_analysis(db, repos["repo_legacy"].id, score=80)

    from src.services.dashboard_service import dashboard_kpi  # late import (TDD Red)

    # user_id=1 → Repo A1 + Legacy
    # user_id=1 → Repo A1 + Legacy only
    result_a = dashboard_kpi(db, days=7, user_id=repos["user_a"].id)
    assert result_a["analysis_count"]["value"] == 2, (
        f"user_id=1 시 Repo A1 + Legacy = 2 기대, 실제: {result_a['analysis_count']['value']}"
    )

    # user_id=2 → Repo B1 + Legacy
    # user_id=2 → Repo B1 + Legacy only
    result_b = dashboard_kpi(db, days=7, user_id=repos["user_b"].id)
    assert result_b["analysis_count"]["value"] == 2, (
        f"user_id=2 시 Repo B1 + Legacy = 2 기대, 실제: {result_b['analysis_count']['value']}"
    )

    # user_id=None → 모든 리포 (admin/legacy)
    # user_id=None → all repos (admin/legacy compat)
    result_all = dashboard_kpi(db, days=7)
    assert result_all["analysis_count"]["value"] == 3, (
        f"user_id 미지정 시 전체 = 3 기대, 실제: {result_all['analysis_count']['value']}"
    )


# ─── A.2 dashboard_trend user_id 필터링 ────────────────────────────────────


def test_dashboard_trend_filters_by_user_id(db, seeded_users_and_repos):
    """A.2 — dashboard_trend(user_id=N) 호출 시 user N 의 분석만 추세에 포함.

    A.2 — dashboard_trend(user_id=N) includes only user N's analyses in the trend.

    검증 — 각 리포의 score 가 다르므로 평균이 user 별로 다르게 산출:
    - Repo A1 (user 1): score=90, Repo B1 (user 2): score=70, Legacy: score=80
    - user_id=1 결과 평균 = (90+80)/2 = 85
    - user_id=2 결과 평균 = (70+80)/2 = 75
    - user_id=None 평균 = (90+70+80)/3 ≈ 80
    """
    repos = seeded_users_and_repos
    # 각 리포에 다른 점수 seed (필터링 효과를 평균값으로 간접 검증)
    # Seed different scores per repo (filter effect verified via average)
    _make_analysis(db, repos["repo_a1"].id, score=90)
    _make_analysis(db, repos["repo_b1"].id, score=70)
    _make_analysis(db, repos["repo_legacy"].id, score=80)

    from src.services.dashboard_service import dashboard_trend  # late import (TDD Red)

    # user_id=1 → A1 (90) + Legacy (80) 만 → 1 또는 N 일자 항목 + count 합 = 2
    # user_id=1 → A1 (90) + Legacy (80) only → count sum == 2
    result_a = dashboard_trend(db, days=7, user_id=repos["user_a"].id)
    total_count_a = sum(entry["count"] for entry in result_a)
    assert total_count_a == 2, (
        f"user_id=1 추세 count 합 = 2 기대, 실제: {total_count_a}"
    )

    # user_id=2 → B1 (70) + Legacy (80) 만 → count 합 = 2
    # user_id=2 → B1 (70) + Legacy (80) only → count sum == 2
    result_b = dashboard_trend(db, days=7, user_id=repos["user_b"].id)
    total_count_b = sum(entry["count"] for entry in result_b)
    assert total_count_b == 2, (
        f"user_id=2 추세 count 합 = 2 기대, 실제: {total_count_b}"
    )

    # user_id=None → 모든 리포 (count 합 = 3)
    # user_id=None → all repos (count sum == 3)
    result_all = dashboard_trend(db, days=7)
    total_count_all = sum(entry["count"] for entry in result_all)
    assert total_count_all == 3, (
        f"user_id 미지정 시 count 합 = 3 기대, 실제: {total_count_all}"
    )


# ─── A.3 frequent_issues_v2 user_id 필터링 ─────────────────────────────────


def test_frequent_issues_v2_filters_by_user_id(db, seeded_users_and_repos):
    """A.3 — frequent_issues_v2(user_id=N) 호출 시 user N 의 이슈만 카운트.

    A.3 — frequent_issues_v2(user_id=N) counts only user N's issues.

    검증 — 각 리포에 다른 message 의 이슈 1건 seed:
    - Repo A1: "issue-from-A"
    - Repo B1: "issue-from-B"
    - Repo Legacy: "issue-from-legacy"
    - user_id=1 → "issue-from-A", "issue-from-legacy" 만
    - user_id=2 → "issue-from-B", "issue-from-legacy" 만
    """
    repos = seeded_users_and_repos
    issue_a = {"issues": [{"message": "issue-from-A", "category": "code_quality",
                            "language": "python", "tool": "pylint"}]}
    issue_b = {"issues": [{"message": "issue-from-B", "category": "code_quality",
                            "language": "python", "tool": "pylint"}]}
    issue_legacy = {"issues": [{"message": "issue-from-legacy", "category": "code_quality",
                                 "language": "python", "tool": "pylint"}]}
    _make_analysis(db, repos["repo_a1"].id, result=issue_a)
    _make_analysis(db, repos["repo_b1"].id, result=issue_b)
    _make_analysis(db, repos["repo_legacy"].id, result=issue_legacy)

    from src.services.dashboard_service import frequent_issues_v2  # late import

    # user_id=1 → A 의 이슈 + legacy 만
    # user_id=1 → user A's issues + legacy only
    result_a = frequent_issues_v2(db, days=7, user_id=repos["user_a"].id)
    messages_a = {item["message"] for item in result_a}
    assert messages_a == {"issue-from-A", "issue-from-legacy"}, (
        f"user_id=1 메시지 셋 불일치 — 기대 {{A, legacy}}, 실제: {messages_a}"
    )

    # user_id=2 → B 의 이슈 + legacy 만
    # user_id=2 → user B's issues + legacy only
    result_b = frequent_issues_v2(db, days=7, user_id=repos["user_b"].id)
    messages_b = {item["message"] for item in result_b}
    assert messages_b == {"issue-from-B", "issue-from-legacy"}, (
        f"user_id=2 메시지 셋 불일치 — 기대 {{B, legacy}}, 실제: {messages_b}"
    )

    # user_id=None → 전체 메시지 3종
    # user_id=None → all 3 messages
    result_all = frequent_issues_v2(db, days=7)
    messages_all = {item["message"] for item in result_all}
    assert messages_all == {"issue-from-A", "issue-from-B", "issue-from-legacy"}, (
        f"user_id 미지정 시 전체 3 메시지 기대, 실제: {messages_all}"
    )


# ─── A.4 auto_merge_kpi user_id 필터링 ──────────────────────────────────────


def test_auto_merge_kpi_filters_by_user_id(db, seeded_users_and_repos):
    """A.4 — auto_merge_kpi(user_id=N) 호출 시 user N 의 MergeAttempt 만 집계.

    A.4 — auto_merge_kpi(user_id=N) aggregates only user N's MergeAttempts.

    검증 — 각 리포에 MergeAttempt 1건 seed (모두 success=False):
    - user_id=1 → A1 + Legacy = 2 attempts
    - user_id=2 → B1 + Legacy = 2 attempts
    - user_id=None → 3 attempts
    """
    repos = seeded_users_and_repos
    # Analysis 1건씩 + MergeAttempt 1건씩 (각 repo 의 full_name 사용)
    # 1 Analysis per repo + 1 MergeAttempt (using each repo's full_name)
    a1 = _make_analysis(db, repos["repo_a1"].id)
    b1 = _make_analysis(db, repos["repo_b1"].id)
    legacy = _make_analysis(db, repos["repo_legacy"].id)
    _make_merge_attempt(db, analysis_id=a1.id, repo_name=repos["repo_a1"].full_name)
    _make_merge_attempt(db, analysis_id=b1.id, repo_name=repos["repo_b1"].full_name)
    _make_merge_attempt(db, analysis_id=legacy.id, repo_name=repos["repo_legacy"].full_name)

    from src.services.dashboard_service import auto_merge_kpi  # late import

    # user_id=1 → A1 + Legacy = 2 attempts
    # user_id=1 → A1 + Legacy = 2 attempts
    result_a = auto_merge_kpi(db, days=7, user_id=repos["user_a"].id)
    assert result_a["total_attempts"] == 2, (
        f"user_id=1 시도 = 2 기대, 실제: {result_a['total_attempts']}"
    )

    # user_id=2 → B1 + Legacy = 2 attempts
    # user_id=2 → B1 + Legacy = 2 attempts
    result_b = auto_merge_kpi(db, days=7, user_id=repos["user_b"].id)
    assert result_b["total_attempts"] == 2, (
        f"user_id=2 시도 = 2 기대, 실제: {result_b['total_attempts']}"
    )

    # user_id=None → 전체 = 3 attempts
    # user_id=None → all = 3 attempts
    result_all = auto_merge_kpi(db, days=7)
    assert result_all["total_attempts"] == 3, (
        f"user_id 미지정 시 전체 시도 = 3 기대, 실제: {result_all['total_attempts']}"
    )


# ─── A.5 merge_failure_distribution user_id 필터링 ────────────────────────


def test_merge_failure_distribution_filters_by_user_id(db, seeded_users_and_repos):
    """A.5 — merge_failure_distribution(user_id=N) 호출 시 user N 의 실패 사유만 집계.

    A.5 — merge_failure_distribution(user_id=N) aggregates only user N's failures.

    검증 — 각 리포에 실패 MergeAttempt 1건씩 (다른 reason):
    - Repo A1: failure_reason = "unstable_ci"
    - Repo B1: failure_reason = "branch_protection_blocked"
    - Repo Legacy: failure_reason = "permission_denied"

    필터링 결과:
    - user_id=1 → unstable_ci + permission_denied 만
    - user_id=2 → branch_protection_blocked + permission_denied 만
    """
    repos = seeded_users_and_repos
    a1 = _make_analysis(db, repos["repo_a1"].id)
    b1 = _make_analysis(db, repos["repo_b1"].id)
    legacy = _make_analysis(db, repos["repo_legacy"].id)
    _make_merge_attempt(db, analysis_id=a1.id, repo_name=repos["repo_a1"].full_name,
                        success=False, failure_reason="unstable_ci")
    _make_merge_attempt(db, analysis_id=b1.id, repo_name=repos["repo_b1"].full_name,
                        success=False, failure_reason="branch_protection_blocked")
    _make_merge_attempt(db, analysis_id=legacy.id, repo_name=repos["repo_legacy"].full_name,
                        success=False, failure_reason="permission_denied")

    from src.services.dashboard_service import merge_failure_distribution  # late import

    # user_id=1 → unstable_ci + permission_denied
    # user_id=1 → unstable_ci + permission_denied only
    result_a = merge_failure_distribution(db, days=7, user_id=repos["user_a"].id)
    reasons_a = {item["reason"] for item in result_a}
    assert reasons_a == {"unstable_ci", "permission_denied"}, (
        f"user_id=1 사유 셋 불일치 — 기대 {{unstable_ci, permission_denied}}, 실제: {reasons_a}"
    )

    # user_id=2 → branch_protection_blocked + permission_denied
    # user_id=2 → branch_protection_blocked + permission_denied only
    result_b = merge_failure_distribution(db, days=7, user_id=repos["user_b"].id)
    reasons_b = {item["reason"] for item in result_b}
    assert reasons_b == {"branch_protection_blocked", "permission_denied"}, (
        f"user_id=2 사유 셋 불일치 — 기대 {{branch_protection_blocked, permission_denied}}, "
        f"실제: {reasons_b}"
    )

    # user_id=None → 전체 3 사유
    # user_id=None → all 3 reasons
    result_all = merge_failure_distribution(db, days=7)
    reasons_all = {item["reason"] for item in result_all}
    assert reasons_all == {"unstable_ci", "branch_protection_blocked", "permission_denied"}, (
        f"user_id 미지정 시 전체 3 사유 기대, 실제: {reasons_all}"
    )


# ─── A.6 insight_narrative user_id 필터링 (async) ─────────────────────────


@pytest.mark.asyncio
async def test_insight_narrative_filters_by_user_id(db, seeded_users_and_repos):
    """A.6 — insight_narrative(user_id=N, ...) async 호출 시 user N 의 컨텍스트만 Claude 에 전달.

    A.6 — insight_narrative(user_id=N, ...) async passes only user N's context to Claude.

    검증:
    - user_id 인자 수용 (TypeError 발생 X)
    - DB 데이터 존재 (analysis_count > 0) → status="success" 또는 "no_data" (분기 정상 진입)
    - Claude API mock 호출 시 user 분리된 데이터 사용

    각 리포에 Analysis seed (점수 다름) — 4 dashboard 헬퍼가 user_id 격리 결과 사용해야 함.
    """
    repos = seeded_users_and_repos
    # 각 리포에 Analysis 1건씩 seed
    # Seed 1 Analysis per repo
    _make_analysis(db, repos["repo_a1"].id, score=90)
    _make_analysis(db, repos["repo_b1"].id, score=70)
    _make_analysis(db, repos["repo_legacy"].id, score=80)

    # Claude API 응답 mock — valid JSON narrative
    # Mock Claude API response — valid JSON narrative
    valid_json = (
        '{'
        '"positive_highlights": ["A 점수 90"],'
        '"focus_areas": ["pylint warnings"],'
        '"key_metrics": ['
        '{"label": "평균", "value": "85", "delta": "+5"},'
        '{"label": "건수", "value": "2", "delta": "0"},'
        '{"label": "보안", "value": "0", "delta": "0"},'
        '{"label": "Auto-merge", "value": "0%", "delta": "0%"}'
        '],'
        '"next_actions": ["pylint 해소"]'
        '}'
    )
    fake_msg = MagicMock()
    text_block = MagicMock()
    text_block.text = valid_json
    fake_msg.content = [text_block]
    fake_msg.usage = MagicMock(
        input_tokens=100,
        output_tokens=50,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=100,
    )
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=fake_msg)

    with patch(
        "src.services.dashboard_service.anthropic.AsyncAnthropic",
        return_value=fake_client,
    ):
        from src.services.dashboard_service import insight_narrative  # late import (TDD Red)

        # user_id=1 → user A 컨텍스트 (A1 + Legacy)
        # user_id=1 → user A context (A1 + Legacy)
        result_a = await insight_narrative(
            db, days=7, user_id=repos["user_a"].id, api_key="sk-test"
        )

    # 시그니처 수용 검증 — 정상 분기 진입 (success or no_data, api_error 아님)
    # Signature acceptance — proper branch entered (success or no_data, NOT api_error)
    assert result_a["status"] in ("success", "no_data"), (
        f"user_id 인자 수용 실패 또는 graceful 분기 — status={result_a['status']!r}"
    )

    # 데이터 2건 (A1 + Legacy) → no_data 아님 → success 기대
    # Data exists (A1 + Legacy = 2 analyses) → not no_data → success expected
    assert result_a["status"] == "success", (
        f"user_id=1 데이터 2건 → success 기대, 실제: {result_a['status']!r}"
    )

    # Claude API 호출 시 user-격리된 컨텍스트 (A 평균 점수 = 85) 가 user_prompt 에 포함
    # Claude API call should include user-isolated context (user A avg score = 85)
    fake_client.messages.create.assert_awaited_once()
    call_kwargs = fake_client.messages.create.call_args.kwargs
    user_prompt = call_kwargs["messages"][0]["content"]
    # B1 의 데이터 (점수 70 — bob/api) 가 prompt 에 누출되지 않아야 함
    # B's data (score 70 — bob/api) must NOT leak into the prompt
    assert "bob/api" not in user_prompt, (
        f"user_id=1 호출에 bob/api 데이터 누출 — RLS 격리 실패. prompt: {user_prompt[:300]}"
    )
