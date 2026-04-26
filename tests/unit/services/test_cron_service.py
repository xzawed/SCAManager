"""cron_service 단위 테스트 — TDD Red 단계.
Unit tests for cron_service — TDD Red phase.

In-memory SQLite + Base.metadata.create_all 자체 fixture 사용.
Uses in-memory SQLite with Base.metadata.create_all — no conftest dependency.
telegram_post_message 는 AsyncMock 으로 격리 (실제 HTTP 호출 방지).
telegram_post_message is isolated via AsyncMock to prevent real HTTP calls.
"""
# pylint: disable=redefined-outer-name
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database import Base
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User


# ---------------------------------------------------------------------------
# Fixtures — in-memory SQLite DB
# ---------------------------------------------------------------------------


@pytest.fixture()
def db():
    """모든 ORM 테이블이 생성된 in-memory SQLite 세션을 제공한다.
    Provide an in-memory SQLite session with all ORM tables created.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def repo(db):
    """테스트용 Repository 레코드(chat_id 있음)를 생성하고 반환한다.
    Create and return a test Repository record with a chat_id.
    """
    user = User(github_id=1, github_login="tester", email="t@x.com", display_name="Tester")
    db.add(user)
    db.commit()
    db.refresh(user)

    repository = Repository(
        full_name="owner/testrepo",
        user_id=user.id,
        telegram_chat_id="-100111222",
    )
    db.add(repository)
    db.commit()
    db.refresh(repository)
    return repository


@pytest.fixture()
def repo_no_chat(db):
    """chat_id 없는 Repository 레코드를 생성하고 반환한다.
    Create and return a Repository record without any chat_id.
    """
    user = User(github_id=2, github_login="nochat", email="nc@x.com", display_name="NoChat")
    db.add(user)
    db.commit()
    db.refresh(user)

    repository = Repository(
        full_name="owner/nochatrepo",
        user_id=user.id,
        telegram_chat_id=None,
    )
    db.add(repository)
    db.commit()
    db.refresh(repository)
    return repository


def _make_analysis(
    db: Session,
    repo_id: int,
    score: int | None,
    offset_hours: int = 0,
) -> Analysis:
    """테스트용 Analysis 레코드를 생성하는 헬퍼 함수.
    Helper to create a test Analysis record.
    """
    created = datetime.now(timezone.utc) - timedelta(hours=offset_hours)
    analysis = Analysis(
        repo_id=repo_id,
        commit_sha=f"sha-{score}-{offset_hours}-{id(object())}",
        score=score,
        grade="B",
        created_at=created,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


# ---------------------------------------------------------------------------
# Test: run_weekly_reports
# ---------------------------------------------------------------------------


class TestRunWeeklyReports:
    """run_weekly_reports — 주간 요약 전송 함수 테스트."""

    @patch("src.services.cron_service.telegram_post_message", new_callable=AsyncMock)
    async def test_run_weekly_reports_sends_for_repos_with_analyses(
        self, mock_tg, db, repo, monkeypatch
    ):
        """분석이 있는 리포 → telegram_post_message 가 1회 이상 호출된다.
        Repo with analyses → telegram_post_message is called at least once.
        """
        # 전역 chat_id fallback 을 비워 repo.telegram_chat_id 가 사용되도록 한다
        # Clear global chat_id fallback so repo.telegram_chat_id is used
        import src.services.cron_service as cs
        monkeypatch.setattr(cs.settings, "telegram_chat_id", "")

        now = datetime.now(timezone.utc)

        # 7일 이내 분석 5개 삽입 (min_samples 충족)
        # Insert 5 analyses within 7 days (satisfies min_samples)
        for i in range(5):
            _make_analysis(db, repo.id, score=75, offset_hours=i * 10)

        sent = await cs.run_weekly_reports(db, now=now)

        # telegram_post_message 가 호출되어야 한다
        # telegram_post_message must have been called
        assert mock_tg.called
        assert sent == 1

    @patch("src.services.cron_service.telegram_post_message", new_callable=AsyncMock)
    async def test_run_weekly_reports_skips_repo_without_chat_id(
        self, mock_tg, db, repo_no_chat, monkeypatch
    ):
        """chat_id 없는 리포 → 전송 skip, 반환값 0.
        Repo without chat_id → skip sending, returns 0.
        """
        import src.services.cron_service as cs

        # 전역 fallback 도 비움 → resolve_chat_id 가 None 반환
        # Clear global fallback too → resolve_chat_id returns None
        monkeypatch.setattr(cs.settings, "telegram_chat_id", "")

        now = datetime.now(timezone.utc)

        # 분석 삽입 (chat_id 없이도 weekly_summary 는 실행됨을 검증)
        # Insert analyses (weekly_summary runs even without chat_id — skipped after resolve)
        for i in range(5):
            _make_analysis(db, repo_no_chat.id, score=80, offset_hours=i * 5)

        sent = await cs.run_weekly_reports(db, now=now)

        # chat_id 없으므로 전송하지 않아야 한다
        # Must not send since chat_id is absent
        mock_tg.assert_not_called()
        assert sent == 0

    @patch("src.services.cron_service.telegram_post_message", new_callable=AsyncMock)
    async def test_run_weekly_reports_isolates_per_repo_failure(
        self, mock_tg, db, monkeypatch
    ):
        """첫 번째 리포에서 HTTPError → 두 번째 리포는 정상 전송된다.
        HTTPError on first repo → second repo is still sent successfully.
        """
        import src.services.cron_service as cs
        monkeypatch.setattr(cs.settings, "telegram_chat_id", "")

        # 두 번째 repo 를 User 1로 만든다
        # Create two distinct repositories with chat_ids
        user1 = User(github_id=10, github_login="u1", email="u1@x.com", display_name="U1")
        user2 = User(github_id=11, github_login="u2", email="u2@x.com", display_name="U2")
        db.add_all([user1, user2])
        db.commit()

        repo1 = Repository(
            full_name="owner/repo-fail",
            user_id=user1.id,
            telegram_chat_id="-100aaa",
        )
        repo2 = Repository(
            full_name="owner/repo-ok",
            user_id=user2.id,
            telegram_chat_id="-100bbb",
        )
        db.add_all([repo1, repo2])
        db.commit()
        db.refresh(repo1)
        db.refresh(repo2)

        now = datetime.now(timezone.utc)

        # 두 리포 모두 분석 데이터 삽입
        # Insert analyses for both repos
        for i in range(5):
            _make_analysis(db, repo1.id, score=70, offset_hours=i * 5)
            _make_analysis(db, repo2.id, score=80, offset_hours=i * 5)

        # 첫 번째 호출에서 HTTPError, 두 번째는 정상
        # HTTPError on first call, second call succeeds
        mock_tg.side_effect = [
            httpx.HTTPError("timeout"),
            None,
        ]

        sent = await cs.run_weekly_reports(db, now=now)

        # 두 번 호출 — 첫 번째 실패, 두 번째 성공 → sent=1
        # Called twice — first fails, second succeeds → sent=1
        assert mock_tg.call_count == 2
        assert sent == 1


# ---------------------------------------------------------------------------
# Test: run_trend_check
# ---------------------------------------------------------------------------


class TestRunTrendCheck:
    """run_trend_check — 트렌드 경고 전송 함수 테스트.

    moving_average 를 mock 으로 대체한다. 실제 DB 집계 로직은
    TestMovingAverage(analytics_service) 에서 검증하므로 이 테스트는
    cron_service 의 제어 흐름(임계값 판정, 알림 발송, skip 조건)만 검증한다.
    moving_average is mocked. Actual DB aggregation logic is covered by
    TestMovingAverage in analytics_service tests. These tests only verify
    cron_service control flow: threshold judgment, alert dispatch, skip conditions.
    """

    @patch("src.services.cron_service.telegram_post_message", new_callable=AsyncMock)
    @patch("src.services.cron_service.moving_average")
    async def test_run_trend_check_triggers_on_drop_10_points(
        self, mock_ma, mock_tg, db, repo, monkeypatch
    ):
        """prev_avg=80, current_avg=70 → drop=10 ≥ threshold → 알림 발송.
        prev_avg=80, current_avg=70 → drop=10 >= threshold → alert sent.
        """
        import src.services.cron_service as cs
        monkeypatch.setattr(cs.settings, "telegram_chat_id", "")

        now = datetime.now(timezone.utc)

        # moving_average 반환값: 첫 호출=current(70), 두 번째=prev(80)
        # moving_average return values: first call=current(70), second=prev(80)
        mock_ma.side_effect = [70.0, 80.0]

        alerted = await cs.run_trend_check(db, now=now)

        # drop=80-70=10 ≥ _TREND_DROP_THRESHOLD=10 → 알림 발송
        # drop=80-70=10 >= _TREND_DROP_THRESHOLD=10 → alert sent
        assert mock_tg.called
        assert alerted == 1

    @patch("src.services.cron_service.telegram_post_message", new_callable=AsyncMock)
    @patch("src.services.cron_service.moving_average")
    async def test_run_trend_check_skips_below_min_samples(
        self, mock_ma, mock_tg, db, repo, monkeypatch
    ):
        """current moving_average=None (min_samples 미충족) → skip.
        current moving_average=None (below min_samples) → skip.
        """
        import src.services.cron_service as cs
        monkeypatch.setattr(cs.settings, "telegram_chat_id", "")

        now = datetime.now(timezone.utc)

        # current_avg=None → min_samples 미충족 분기
        # current_avg=None → triggers the min_samples insufficient branch
        mock_ma.return_value = None

        alerted = await cs.run_trend_check(db, now=now)

        # min_samples 미충족 → Telegram 호출 없음
        # Below min_samples → no Telegram call
        mock_tg.assert_not_called()
        assert alerted == 0

    @patch("src.services.cron_service.telegram_post_message", new_callable=AsyncMock)
    @patch("src.services.cron_service.moving_average")
    async def test_run_trend_check_no_trigger_on_small_drop(
        self, mock_ma, mock_tg, db, repo, monkeypatch
    ):
        """prev_avg=80, current_avg=71 → drop=9 < 10 → 알림 미발송.
        prev_avg=80, current_avg=71 → drop=9 < 10 → no alert sent.
        """
        import src.services.cron_service as cs
        monkeypatch.setattr(cs.settings, "telegram_chat_id", "")

        now = datetime.now(timezone.utc)

        # moving_average 반환값: current=71, prev=80 → drop=9
        # moving_average return values: current=71, prev=80 → drop=9
        mock_ma.side_effect = [71.0, 80.0]

        alerted = await cs.run_trend_check(db, now=now)

        # drop=9 < _TREND_DROP_THRESHOLD=10 → 알림 없음
        # drop=9 < _TREND_DROP_THRESHOLD=10 → no alert
        mock_tg.assert_not_called()
        assert alerted == 0
