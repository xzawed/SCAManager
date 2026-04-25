"""analysis_feedback_repo — AnalysisFeedback ORM 쿼리 테스트 (Phase E.3-a).

TDD Red: src/repositories/analysis_feedback_repo.py 모듈은 아직 없음.
"""
# pylint: disable=redefined-outer-name
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.analysis import Analysis
from src.models.analysis_feedback import AnalysisFeedback
from src.models.repository import Repository
from src.models.user import User
from src.repositories import analysis_feedback_repo


@pytest.fixture
def db():
    """In-memory SQLite DB with all tables created."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine)
    session = session_local()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def fixture_data(db):
    """Create user + repo + analysis so feedback has valid FKs."""
    user = User(github_id=1, github_login="alice", email="a@x.com", display_name="Alice")
    db.add(user)
    db.commit()
    db.refresh(user)

    repo = Repository(full_name="owner/repo", user_id=user.id)
    db.add(repo)
    db.commit()
    db.refresh(repo)

    analysis = Analysis(
        repo_id=repo.id,
        commit_sha="abc123",
        score=85,
        grade="B",
        created_at=datetime.now(timezone.utc),
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    return {"user": user, "repo": repo, "analysis": analysis}


class TestUpsertFeedback:
    """upsert_feedback — 신규는 INSERT, 기존 있으면 UPDATE."""

    def test_insert_new_feedback(self, db, fixture_data):
        fb = analysis_feedback_repo.upsert_feedback(
            db,
            analysis_id=fixture_data["analysis"].id,
            user_id=fixture_data["user"].id,
            thumbs=1,
            comment="좋은 분석",
        )
        assert fb.id is not None
        assert fb.thumbs == 1
        assert fb.comment == "좋은 분석"
        assert db.query(AnalysisFeedback).count() == 1

    def test_update_existing_feedback(self, db, fixture_data):
        # 첫 번째 피드백 (up)
        # First feedback (up).
        analysis_feedback_repo.upsert_feedback(
            db,
            analysis_id=fixture_data["analysis"].id,
            user_id=fixture_data["user"].id,
            thumbs=1,
        )
        # 같은 user + analysis 에 재피드백 (down) → UPDATE
        fb2 = analysis_feedback_repo.upsert_feedback(
            db,
            analysis_id=fixture_data["analysis"].id,
            user_id=fixture_data["user"].id,
            thumbs=-1,
            comment="다시 생각해보니 아님",
        )
        assert fb2.thumbs == -1
        assert fb2.comment == "다시 생각해보니 아님"
        assert db.query(AnalysisFeedback).count() == 1  # 여전히 1개

    def test_thumbs_must_be_plus_or_minus_one(self, db, fixture_data):
        # 0 또는 다른 값은 ValueError
        with pytest.raises(ValueError, match="thumbs"):
            analysis_feedback_repo.upsert_feedback(
                db,
                analysis_id=fixture_data["analysis"].id,
                user_id=fixture_data["user"].id,
                thumbs=0,
            )


class TestFindByAnalysisAndUser:
    """find_by_analysis_and_user — 사용자의 기존 피드백 조회."""

    def test_returns_none_when_not_exists(self, db, fixture_data):
        fb = analysis_feedback_repo.find_by_analysis_and_user(
            db, analysis_id=fixture_data["analysis"].id, user_id=fixture_data["user"].id,
        )
        assert fb is None

    def test_returns_feedback_when_exists(self, db, fixture_data):
        analysis_feedback_repo.upsert_feedback(
            db,
            analysis_id=fixture_data["analysis"].id,
            user_id=fixture_data["user"].id,
            thumbs=1,
        )
        fb = analysis_feedback_repo.find_by_analysis_and_user(
            db, analysis_id=fixture_data["analysis"].id, user_id=fixture_data["user"].id,
        )
        assert fb is not None
        assert fb.thumbs == 1


class TestCalibrationByScoreRange:
    """get_calibration_by_score_range — 점수 범위별 thumbs up 비율."""

    def _create_analysis_with_feedback(self, db, score, thumbs_values, repo_id, user_id):
        """Helper: 지정된 점수로 analysis 를 만들고 여러 thumbs 값으로 feedback 부착."""
        # 각 feedback 은 다른 user 가 필요하지만 테스트 단순화를 위해 같은 user 에 여러
        # analysis 를 만들어 (user, analysis) 조합이 유일하도록 함.
        analyses = []
        for i, thumbs in enumerate(thumbs_values):
            analysis = Analysis(
                repo_id=repo_id,
                commit_sha=f"sha_{score}_{i}",
                score=score,
                grade="B",
                created_at=datetime.now(timezone.utc),
            )
            db.add(analysis)
            db.commit()
            db.refresh(analysis)
            analyses.append(analysis)

            analysis_feedback_repo.upsert_feedback(
                db, analysis_id=analysis.id, user_id=user_id, thumbs=thumbs,
            )
        return analyses

    def test_calibration_returns_ratio_per_range(self, db, fixture_data):
        user_id = fixture_data["user"].id
        repo_id = fixture_data["repo"].id

        # 45-59 범위: 3 up, 1 down → up_ratio = 0.75
        self._create_analysis_with_feedback(db, 50, [1, 1, 1, -1], repo_id, user_id)
        # 60-74 범위: 1 up, 1 down → 0.5
        self._create_analysis_with_feedback(db, 65, [1, -1], repo_id, user_id)
        # 75-89 범위: 2 up → 1.0
        # Score range 75-89: 2 up votes → 1.0.
        self._create_analysis_with_feedback(db, 80, [1, 1], repo_id, user_id)

        calibration = analysis_feedback_repo.get_calibration_by_score_range(db)

        # 반환 구조: {"45-59": {"count": N, "up_ratio": 0.0~1.0}, ...}
        assert "45-59" in calibration
        assert calibration["45-59"]["count"] == 4
        assert calibration["45-59"]["up_ratio"] == pytest.approx(0.75)
        assert calibration["60-74"]["count"] == 2
        assert calibration["60-74"]["up_ratio"] == pytest.approx(0.5)
        assert calibration["75-89"]["count"] == 2
        assert calibration["75-89"]["up_ratio"] == pytest.approx(1.0)

    def test_calibration_empty_when_no_feedback(self, db, fixture_data):
        # fixture_data 에는 analysis 만 있고 feedback 없음
        calibration = analysis_feedback_repo.get_calibration_by_score_range(db)
        # 모든 범위에 count=0 또는 키 자체 없음
        for range_key in ("0-44", "45-59", "60-74", "75-89", "90-100"):
            data = calibration.get(range_key, {"count": 0, "up_ratio": 0.0})
            assert data["count"] == 0
