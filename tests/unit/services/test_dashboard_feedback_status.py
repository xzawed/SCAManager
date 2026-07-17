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


# ─── owner 필터 parity — 타 테넌트 저장소/피드백 유출 차단 (준비도 감사 #9) ──────
#
# feedback_status 는 overview 7 집계 중 유일하게 user_id 를 안 받아, recent_analysis 쿼리가
# owner 무관 전역 최신 1건을 뽑았다 → 테넌트 A 대시보드 CTA 에 B 의 private repo full_name +
# analysis id 노출(방어심층 갭 — RLS 2차가 prod 에서 막으나 6 형제 집계와 불일치).

class TestFeedbackStatusOwnerFilter:
    def test_recent_excludes_other_tenant_repo(self, db):
        """🔴 user_id 전달 시 타 테넌트 소유 저장소의 최신 분석은 recent 로 노출되지 않는다."""
        from src.services.dashboard_service import feedback_status

        a = User(github_id=10, github_login="a", email="a@x.com", display_name="A")
        b = User(github_id=20, github_login="b", email="b@x.com", display_name="B")
        db.add_all([a, b])
        db.commit()
        repo_a = Repository(full_name="a/app", user_id=a.id)
        repo_b = Repository(full_name="b/secret-billing", user_id=b.id)
        db.add_all([repo_a, repo_b])
        db.commit()
        _make_analysis(db, repo_a.id, offset_hours=24)   # A 소유, 오래됨
        _make_analysis(db, repo_b.id, offset_hours=1)    # B 소유, 전역 최신

        # A 관점 — B 의 최신 분석이 아니라 A 소유 저장소의 분석이 나와야 한다
        result = feedback_status(db, user_id=a.id)
        assert result["recent_analysis"] is not None
        assert result["recent_analysis"]["repo_full_name"] == "a/app", \
            "타 테넌트(B) private repo full_name 이 A 에게 노출됨 (IDOR-인접)"

    def test_recent_includes_legacy_null_owner(self, db):
        """legacy(user_id=NULL) 저장소는 노출 유지 — 6 형제 집계와 동일 컨벤션(== user OR IS NULL)."""
        from src.services.dashboard_service import feedback_status

        a = User(github_id=11, github_login="a2", email="a2@x.com", display_name="A2")
        db.add(a)
        db.commit()
        repo_legacy = Repository(full_name="legacy/repo", user_id=None)
        db.add(repo_legacy)
        db.commit()
        _make_analysis(db, repo_legacy.id, offset_hours=1)

        result = feedback_status(db, user_id=a.id)
        assert result["recent_analysis"] is not None
        assert result["recent_analysis"]["repo_full_name"] == "legacy/repo"

    def test_count_owner_scoped(self, db):
        """🔴 count 도 owner 스코프 — 타 테넌트 피드백이 CTA show/hide 판정에 섞이지 않는다."""
        from src.services.dashboard_service import feedback_status

        a = User(github_id=12, github_login="a3", email="a3@x.com", display_name="A3")
        b = User(github_id=22, github_login="b3", email="b3@x.com", display_name="B3")
        db.add_all([a, b])
        db.commit()
        repo_a = Repository(full_name="a3/app", user_id=a.id)
        repo_b = Repository(full_name="b3/app", user_id=b.id)
        db.add_all([repo_a, repo_b])
        db.commit()
        an_a = _make_analysis(db, repo_a.id)
        an_b = _make_analysis(db, repo_b.id)
        _make_feedback(db, analysis_id=an_a.id, user_id=a.id)   # A 소유 repo 피드백 1
        _make_feedback(db, analysis_id=an_b.id, user_id=b.id)   # B 소유 repo 피드백 1

        # A 관점 count = 1 (A 소유 repo 분석 피드백만), 전역 2 아님
        result = feedback_status(db, user_id=a.id)
        assert result["count"] == 1, "count 에 타 테넌트 피드백이 섞임"

    def test_user_id_none_preserves_global_behavior(self, db, repo):
        """user_id=None(admin/기존 호출) → 전역 동작 유지 (하위 호환)."""
        from src.services.dashboard_service import feedback_status

        _make_analysis(db, repo.id, offset_hours=1)
        result = feedback_status(db, user_id=None)
        assert result["recent_analysis"]["repo_full_name"] == "owner/repo"
