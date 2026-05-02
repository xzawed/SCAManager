"""dashboard_service.feedback_status 단위 테스트.

Phase 2 PR 2 (2026-05-02): MCP 운영 데이터 (analysis_feedbacks row=0) 기반 CTA.
사용자 참여 유도 → AI 정합도 카드 데이터 누적 (Phase 3 진입 토대).

함수: feedback_status(db, *, threshold=10) -> dict
- show_cta: bool — CTA 카드 표시 여부 (count < threshold)
- count: int — 전체 feedback row 수
- recent_analysis: dict|None — 최근 분석 (CTA 링크 대상)
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database import Base
from src.models.analysis import Analysis
from src.models.analysis_feedback import AnalysisFeedback
from src.models.repository import Repository
from src.models.user import User


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def user(db):
    u = User(github_id=1, github_login="tester", email="t@x.com", display_name="Tester")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture()
def repo(db, user):
    r = Repository(full_name="owner/repo", user_id=user.id)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _make_analysis(db: Session, repo_id: int, *, offset_hours: int = 0) -> Analysis:
    a = Analysis(
        repo_id=repo_id,
        commit_sha=f"sha-{uuid.uuid4().hex}",
        score=80,
        grade="B",
        created_at=datetime.now(timezone.utc) - timedelta(hours=offset_hours),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _make_feedback(db: Session, *, analysis_id: int, user_id: int, thumbs: int = 1) -> None:
    fb = AnalysisFeedback(
        analysis_id=analysis_id,
        user_id=user_id,
        thumbs=thumbs,
    )
    db.add(fb)
    db.commit()


# ─── feedback_status ──────────────────────────────────────────────────────


class TestFeedbackStatus:
    """feedback_status — dashboard CTA 카드 데이터."""

    def test_returns_required_keys(self, db):
        from src.services.dashboard_service import feedback_status

        result = feedback_status(db)
        for key in ("show_cta", "count", "recent_analysis"):
            assert key in result, f"key 누락: {key}"

    def test_show_cta_when_count_below_threshold(self, db, repo, user):
        """feedback row 수가 threshold 미만이면 CTA 표시."""
        from src.services.dashboard_service import feedback_status

        a = _make_analysis(db, repo.id)
        _make_feedback(db, analysis_id=a.id, user_id=user.id)

        result = feedback_status(db, threshold=10)
        assert result["show_cta"] is True
        assert result["count"] == 1

    def test_hide_cta_when_count_meets_threshold(self, db, repo, user):
        """feedback row 수가 threshold 이상이면 CTA 숨김 (충분히 누적).

        UNIQUE (analysis_id, user_id) 제약 → 10 distinct analysis × 1 feedback 패턴.
        """
        from src.services.dashboard_service import feedback_status

        # 10 distinct analysis 각각 1 feedback (UNIQUE 제약 회피)
        for i in range(10):
            a = _make_analysis(db, repo.id, offset_hours=i)
            fb = AnalysisFeedback(analysis_id=a.id, user_id=user.id, thumbs=1 if i % 2 == 0 else -1)
            db.add(fb)
        db.commit()

        result = feedback_status(db, threshold=10)
        assert result["show_cta"] is False
        assert result["count"] == 10

    def test_show_cta_when_empty(self, db):
        """feedback 0건 (운영 데이터 패턴) → CTA 표시 + recent_analysis None."""
        from src.services.dashboard_service import feedback_status

        result = feedback_status(db, threshold=10)
        assert result["show_cta"] is True
        assert result["count"] == 0
        assert result["recent_analysis"] is None

    def test_recent_analysis_includes_repo_full_name_and_id(self, db, repo):
        """CTA 링크 대상 = 가장 최근 분석 (id + repo.full_name)."""
        from src.services.dashboard_service import feedback_status

        # 오래된 + 최근 분석 2건
        old = _make_analysis(db, repo.id, offset_hours=24)
        new = _make_analysis(db, repo.id, offset_hours=1)

        result = feedback_status(db)
        assert result["recent_analysis"] is not None
        assert result["recent_analysis"]["id"] == new.id
        assert result["recent_analysis"]["repo_full_name"] == "owner/repo"
        # old 가 아닌 new 가 반환됨
        assert result["recent_analysis"]["id"] != old.id

    def test_recent_analysis_none_when_no_analyses(self, db):
        from src.services.dashboard_service import feedback_status

        result = feedback_status(db)
        assert result["recent_analysis"] is None
