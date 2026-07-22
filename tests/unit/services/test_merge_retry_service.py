"""merge_retry_service 단위 테스트 — TDD Red 단계 (Phase 12 T9).
Unit tests for merge_retry_service — TDD Red phase (Phase 12 T9).

In-memory SQLite + real DB operations, HTTP calls mocked.
인메모리 SQLite + 실제 DB 작업, HTTP 호출은 모킹.
"""
# pylint: disable=redefined-outer-name,import-outside-toplevel,confusing-with-statement
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models.analysis import Analysis
from src.models.merge_retry import MergeRetryQueue
from src.models.repository import Repository
from src.services.merge_retry_service import process_pending_retries


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session():
    """인메모리 SQLite DB 세션 — 각 테스트 후 폐기.
    In-memory SQLite session — discarded after each test.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_cls = sessionmaker(bind=engine)
    session = session_cls()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# Seed helper
# ---------------------------------------------------------------------------


def _seed_queue_row(  # pylint: disable=too-many-arguments
    db_session,
    *,
    status: str = "pending",
    commit_sha: str = "abc123",
    score: int = 85,
    next_retry_delta_seconds: int = -10,
    attempts_count: int = 1,
) -> MergeRetryQueue:
    """테스트용 Repository + Analysis + MergeRetryQueue 행을 삽입한다.
    Insert a Repository + Analysis + MergeRetryQueue row for testing.
    """
    # 동일 리포 재사용 — full_name 중복 방지
    # Reuse same repo — prevent full_name duplicate.
    repo = db_session.query(Repository).filter_by(full_name="owner/repo").first()
    if repo is None:
        repo = Repository(full_name="owner/repo")
        db_session.add(repo)
        db_session.commit()
    analysis = Analysis(
        repo_id=repo.id,
        commit_sha=commit_sha,
        score=score,
        grade="B",
        result={},
    )
    db_session.add(analysis)
    db_session.commit()

    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    row = MergeRetryQueue(
        repo_full_name="owner/repo",
        pr_number=42,
        analysis_id=analysis.id,
        commit_sha=commit_sha,
        score=score,
        threshold_at_enqueue=75,
        status=status,
        attempts_count=attempts_count,
        max_attempts=30,
        next_retry_at=now_naive + timedelta(seconds=next_retry_delta_seconds),
        notify_chat_id="-100999",
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# 공통 mock context builder
# Common mock context builder
# ---------------------------------------------------------------------------

_DEFAULT_PR_DATA = {"merged": False, "head": {"sha": "abc123"}, "state": "open"}


def _make_fake_cfg(
    auto_merge: bool = True,
    merge_threshold: int = 75,
    notify_chat_id: str | None = None,
    auto_merge_issue_on_failure: bool = False,
) -> MagicMock:
    """테스트용 가짜 RepoConfigData 를 생성한다.
    Build a fake RepoConfigData for tests.
    """
    cfg = MagicMock()
    cfg.auto_merge = auto_merge
    cfg.merge_threshold = merge_threshold
    cfg.notify_chat_id = notify_chat_id
    cfg.auto_merge_issue_on_failure = auto_merge_issue_on_failure
    return cfg


def _standard_patches(
    token_return="ghp_test",
    pr_data=None,
    merge_return=(True, None, "abc123"),
    ci_return="passed",
    cfg=None,
):
    """표준 mock 패치 컨텍스트를 반환하는 헬퍼.
    Helper returning a standard set of mock patches.
    """
    _pr = pr_data if pr_data is not None else dict(_DEFAULT_PR_DATA)
    _cfg = cfg if cfg is not None else _make_fake_cfg()
    return {
        "token": patch(
            "src.services.merge_retry_service._resolve_github_token",
            return_value=token_return,
        ),
        "repo_config": patch(
            "src.services.merge_retry_service.get_repo_config",
            return_value=_cfg,
        ),
        "pr_data": patch(
            "src.services.merge_retry_service._get_pr_data",
            new_callable=AsyncMock,
            return_value=_pr,
        ),
        "merge_pr": patch(
            "src.services.merge_retry_service.merge_pr",
            new_callable=AsyncMock,
            return_value=merge_return,
        ),
        "ci": patch(
            "src.services.merge_retry_service._get_ci_status_safe",
            new_callable=AsyncMock,
            return_value=ci_return,
        ),
        "notify_succeeded": patch(
            "src.services.merge_retry_service._notify_merge_succeeded",
            new_callable=AsyncMock,
        ),
        "notify_terminal": patch(
            "src.services.merge_retry_service._notify_merge_terminal",
            new_callable=AsyncMock,
        ),
        "notify_config": patch(
            "src.services.merge_retry_service._notify_config_changed",
            new_callable=AsyncMock,
        ),
        "log_attempt": patch(
            "src.services.merge_retry_service.log_merge_attempt",
        ),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProcessPendingRetries:
    """process_pending_retries 전체 시나리오 테스트.
    Full scenario tests for process_pending_retries.
    """

    # T9-1: 빈 큐는 0 카운트를 반환해야 한다
    # T9-1: Empty queue returns zero counts
    async def test_process_empty_queue_returns_zero_counts(self, db_session):
        """pending 행 없을 때 모든 카운트가 0인 dict 반환.
        When no pending rows exist, returns dict with all zero counts.
        """
        result = await process_pending_retries(db_session)
        assert result["claimed"] == 0
        assert result["succeeded"] == 0
        assert result["terminal"] == 0
        assert result["abandoned"] == 0
        assert result["released"] == 0
        assert result["skipped"] == 0

    # T9-2: 토큰 없으면 클레임 해제
    # T9-2: No token → release claim
    async def test_process_no_token_releases_claim(self, db_session):
        """토큰을 가져올 수 없는 경우 클레임 해제하고 released 카운트 증가.
        When token cannot be resolved, releases claim and increments released count.
        """
        row = _seed_queue_row(db_session)

        with patch(
            "src.services.merge_retry_service._resolve_github_token",
            return_value=None,
        ):
            result = await process_pending_retries(db_session, only_ids=[row.id])

        assert result["claimed"] == 1
        assert result["released"] == 1
        assert result["abandoned"] == 0

        # 상태는 여전히 pending (release_claim 은 상태 변경 안 함)
        # Status remains pending (release_claim does not change status)
        db_session.refresh(row)
        assert row.status == "pending"
        # claimed_at 이 None 으로 초기화됐는지 확인
        # Check claimed_at was reset to None
        assert row.claimed_at is None

    async def test_no_token_row_at_max_attempts_abandons_not_loops(self, db_session):
        """🔴 P1-11 (종합감사): 토큰 없는 행이 max_attempts 도달 시 무한 release 루프가 아니라 abandon.

        소유자 GitHub 연결 해제 + 전역 토큰 없음 → 매 사이클 no_token release 로 return 하면
        max_attempts cap 에 영영 도달 못 해 30초 간격 무한 재시도. cap 을 토큰 조회 前으로 올려
        no_token 행도 소진 시 abandon. (수정 되돌리면 released=1·abandoned=0 으로 fail — 뮤테이션 실증.)
        """
        row = _seed_queue_row(db_session, attempts_count=30)  # == max_attempts=30

        with patch(
            "src.services.merge_retry_service._resolve_github_token",
            return_value=None,
        ):
            result = await process_pending_retries(db_session, only_ids=[row.id])

        # 🔴 abandon (released 아님) — cap 이 토큰 조회보다 먼저 걸린다
        assert result["abandoned"] == 1
        assert result["released"] == 0
        db_session.refresh(row)
        assert row.status == "abandoned"

    # C3: 단일 행 예상외 예외 격리 — 전체 배치 미중단
    async def test_unexpected_error_isolates_row_and_continues_batch(self, db_session):
        """🔴 C3: 한 행의 예상외 예외(ValueError 등)가 전체 배치를 중단하지 않고 격리된다.

        좁은 except (httpx/SQLAlchemy) 만 있으면 한 행의 KeyError/ValueError 가
        process_pending_retries 전체를 중단해 무고한 잔여 행이 처리 안 되고 claim 이 5분 stale 까지
        묶였다. broad-except 격리로 실패 행은 클레임 해제 + 나머지 행 계속 처리.
        """
        row1 = _seed_queue_row(db_session, commit_sha="aaa111")
        row2 = _seed_queue_row(db_session, commit_sha="bbb222")
        calls: list[int] = []

        async def _flaky(_db, row, _now, _counts):
            calls.append(row.id)
            if row.id == row1.id:
                raise ValueError("unexpected single-row defect")
            # row2 는 정상 (no-op)

        with patch(
            "src.services.merge_retry_service._process_single_retry",
            side_effect=_flaky,
        ):
            result = await process_pending_retries(
                db_session, only_ids=[row1.id, row2.id]
            )

        # 두 행 모두 처리 시도됨 (배치 미중단) + 예외 미전파 (함수 정상 반환)
        assert row1.id in calls and row2.id in calls
        # 실패 행은 격리되어 released 카운트 증가
        assert result["released"] >= 1
        # 실패 행 클레임 해제 확인 (다음 사이클 재시도 가능)
        db_session.refresh(row1)
        assert row1.claimed_at is None

    # C3 (Codex mutual): terminal 커밋 후 예외 → 완료 행 미오염 (release_claim skip)
    async def test_unexpected_error_after_terminal_commit_does_not_corrupt_row(self, db_session):
        """🔴 C3 Codex NG fix: 예외가 status 확정(succeeded) 커밋 후 부수효과에서 나면 완료 행을
        release_claim 으로 건드리지 않는다 (last_failure_reason 오염·재시도 부활 차단).

        broad-except 가 무조건 release_claim 하면 완료(succeeded)된 행의 last_failure_reason 을
        'unexpected_error'로 덮어써 감사 추적이 오염된다. status='pending' 가드로 방어.
        """
        row = _seed_queue_row(db_session, commit_sha="ccc333")

        async def _commit_then_raise(_db, r, _now, _counts):
            # status 확정 커밋(머지 성공 등) 후 알림 단계에서 예외 — 부분 진행 시나리오
            db_session.query(MergeRetryQueue).filter_by(id=r.id).update(
                {"status": "succeeded", "last_failure_reason": None}
            )
            db_session.commit()
            raise ValueError("notification failed after success commit")

        with patch(
            "src.services.merge_retry_service._process_single_retry",
            side_effect=_commit_then_raise,
        ):
            result = await process_pending_retries(db_session, only_ids=[row.id])

        db_session.refresh(row)
        # 완료 행 보존: status=succeeded 유지 + last_failure_reason 미오염
        assert row.status == "succeeded"
        assert row.last_failure_reason != "unexpected_error"
        # terminal 행은 released 카운트 미증가 (release_claim 미호출)
        assert result["released"] == 0

    # 🔴 좁은 except(infra_error) 대칭화 — rollback 선행 + status 가드 (준비도 감사 #10)
    # 넓은 except(unexpected_error, 위 2 테스트)만 rollback+가드를 가져 비대칭이었다.
    async def test_narrow_infra_except_rolls_back_before_release(self, db_session, monkeypatch):
        """🔴 좁은 except(httpx/SQLAlchemy)도 release_claim 전에 db.rollback() 선행.

        커밋 실패로 세션이 rollback-required 상태가 되면, rollback 없이 호출한 release_claim 의
        UPDATE 가 PendingRollbackError 로 for-loop 전체를 중단시켜 claimed 잔여 행이 5분 stale 까지
        묶였다(넓은 핸들러만 rollback 보유 = 비대칭). rollback→release 순서를 강제해 봉인.
        """
        row = _seed_queue_row(db_session, commit_sha="ddd444")
        order: list[str] = []
        orig_rollback = db_session.rollback

        def _spy_rollback():
            order.append("rollback")
            return orig_rollback()

        def _spy_release(_db, _row_id, **_kw):
            order.append("release")

        monkeypatch.setattr(db_session, "rollback", _spy_rollback)
        monkeypatch.setattr(
            "src.services.merge_retry_service.merge_retry_repo.release_claim", _spy_release
        )

        async def _raise_infra(_db, _row, _now, _counts):
            raise SQLAlchemyError("infra error on commit")

        with patch(
            "src.services.merge_retry_service._process_single_retry", side_effect=_raise_infra
        ):
            await process_pending_retries(db_session, only_ids=[row.id])

        assert "rollback" in order, "좁은 except 가 db.rollback() 을 호출하지 않음"
        assert "release" in order, "release_claim 미호출"
        assert order.index("rollback") < order.index("release"), \
            "rollback 이 release_claim 보다 뒤에 있음 (오염된 세션에서 release 쿼리 실패)"

    async def test_narrow_infra_except_skips_release_on_terminal_row(self, db_session):
        """🔴 좁은 except 도 terminal 커밋 후 예외 시 완료 행을 건드리지 않는다 (status 가드, 넓은 핸들러 대칭).

        infra 예외가 status 확정(succeeded) 커밋 뒤에 나면 release_claim 이 last_failure_reason 을
        'infra_error'로 덮어써 감사 추적 오염 + 완료 행 재시도 부활. status=='pending' 가드로 방어.
        """
        row = _seed_queue_row(db_session, commit_sha="eee555")

        async def _commit_terminal_then_infra(_db, r, _now, _counts):
            db_session.query(MergeRetryQueue).filter_by(id=r.id).update(
                {"status": "succeeded", "last_failure_reason": None}
            )
            db_session.commit()
            raise SQLAlchemyError("infra error after success commit")

        with patch(
            "src.services.merge_retry_service._process_single_retry",
            side_effect=_commit_terminal_then_infra,
        ):
            result = await process_pending_retries(db_session, only_ids=[row.id])

        db_session.refresh(row)
        assert row.status == "succeeded", "완료 행 status 가 변경됨"
        assert row.last_failure_reason != "infra_error", "완료 행이 infra_error 로 오염됨"
        assert result["released"] == 0, "terminal 행에 release_claim 이 잘못 호출됨"

    # T9-3: 설정 변경 시 abandoned 마킹
    # T9-3: Config changed → abandoned
    async def test_process_config_changed_abandons(self, db_session):
        """설정이 변경돼 auto_merge=False 면 abandoned 마킹.
        When config changes so auto_merge=False, marks as abandoned.
        """
        row = _seed_queue_row(db_session, score=85)

        # auto_merge=False 인 가짜 설정 생성
        # Build a fake config with auto_merge=False
        fake_cfg = MagicMock()
        fake_cfg.auto_merge = False
        fake_cfg.merge_threshold = 75
        fake_cfg.notify_chat_id = None

        with (
            patch(
                "src.services.merge_retry_service._resolve_github_token",
                return_value="ghp_test",
            ),
            patch(
                "src.services.merge_retry_service.get_repo_config",
                return_value=fake_cfg,
            ),
            patch(
                "src.services.merge_retry_service._notify_config_changed",
                new_callable=AsyncMock,
            ),
        ):
            result = await process_pending_retries(db_session, only_ids=[row.id])

        assert result["claimed"] == 1
        assert result["abandoned"] == 1
        assert result["released"] == 0

        db_session.refresh(row)
        assert row.status == "abandoned"
        assert row.last_failure_reason == "config_changed"

    # T9-4: 이미 머지된 PR → succeeded 마킹
    # T9-4: Already merged PR → mark succeeded
    async def test_process_already_merged_marks_succeeded(self, db_session):
        """PR 이 이미 merged=True 면 succeeded 마킹, counts['succeeded']==1.
        When PR is already merged, marks succeeded and increments succeeded count.
        """
        row = _seed_queue_row(db_session)

        patches = _standard_patches(
            pr_data={"merged": True, "head": {"sha": "abc123"}, "state": "closed"},
        )
        with (
            patches["token"],
            patches["repo_config"],
            patches["pr_data"] as mock_pr_data,
            patches["merge_pr"] as mock_merge,
            patches["ci"],
            patches["notify_succeeded"],
            patches["notify_terminal"],
            patches["notify_config"],
            patches["log_attempt"],
        ):
            result = await process_pending_retries(db_session, only_ids=[row.id])

        # merge_pr 는 호출되지 않아야 함 (이미 머지됨)
        # merge_pr should not be called (already merged)
        mock_merge.assert_not_called()
        assert mock_pr_data.call_count == 1
        assert result["succeeded"] == 1
        assert result["claimed"] == 1

        db_session.refresh(row)
        assert row.status == "succeeded"
        assert row.last_failure_reason == "already_merged"

    # T9-5: SHA drift → abandoned
    async def test_process_sha_drift_abandons(self, db_session):
        """PR head SHA 가 큐 행의 commit_sha 와 다르면 abandoned 마킹.
        When PR head SHA differs from queue row's commit_sha, marks abandoned.
        """
        row = _seed_queue_row(db_session, commit_sha="abc123")

        patches = _standard_patches(
            pr_data={
                "merged": False,
                "head": {"sha": "different_sha"},
                "state": "open",
            },
        )
        with (
            patches["token"],
            patches["repo_config"],
            patches["pr_data"],
            patches["merge_pr"] as mock_merge,
            patches["ci"],
            patches["notify_succeeded"],
            patches["notify_terminal"],
            patches["notify_config"],
            patches["log_attempt"],
        ):
            result = await process_pending_retries(db_session, only_ids=[row.id])

        mock_merge.assert_not_called()
        assert result["abandoned"] == 1
        assert result["claimed"] == 1

        db_session.refresh(row)
        assert row.status == "abandoned"
        assert row.last_failure_reason == "sha_drift"

    # PR #124 패턴: pr_data["head"] 가 present-but-None 일 때 AttributeError 없이 처리
    # PR #124 pattern: head present-but-None must not raise AttributeError
    async def test_process_head_present_but_none_no_attribute_error(self, db_session):
        """pr_data['head'] is None → head_sha 빈 문자열 fallback, sha_drift 건너뜀, 머지 진행.
        When pr_data['head'] is None, head_sha falls back to '' and merge proceeds (no crash).
        """
        row = _seed_queue_row(db_session, commit_sha="abc123")

        patches = _standard_patches(
            pr_data={"merged": False, "head": None, "state": "open"},
            merge_return=(True, None, "abc123"),
        )
        with (
            patches["token"],
            patches["repo_config"],
            patches["pr_data"],
            patches["merge_pr"] as mock_merge,
            patches["ci"],
            patches["notify_succeeded"],
            patches["notify_terminal"],
            patches["notify_config"],
            patches["log_attempt"],
        ):
            result = await process_pending_retries(db_session, only_ids=[row.id])

        # head_sha='' → sha_drift 미발동 → merge_pr 호출됨
        # head_sha='' → no sha_drift → merge_pr is called
        mock_merge.assert_called_once()
        assert result["succeeded"] == 1

    # PR #124 패턴: pr_data["base"] 가 present-but-None 일 때 base_ref 'main' fallback
    # PR #124 pattern: base present-but-None falls back to 'main' without crash
    async def test_process_base_present_but_none_falls_back_to_main(self, db_session):
        """머지 실패 경로에서 pr_data['base'] is None → base_ref='main' fallback (no crash)."""
        row = _seed_queue_row(db_session, commit_sha="abc123")

        ci_mock_holder = {}
        patches = _standard_patches(
            pr_data={"merged": False, "head": {"sha": "abc123"}, "base": None, "state": "open"},
            merge_return=(False, "unstable_ci: state=unstable", ""),
            ci_return="running",
        )
        with (
            patches["token"],
            patches["repo_config"],
            patches["pr_data"],
            patches["merge_pr"],
            patches["ci"] as mock_ci,
            patches["notify_succeeded"],
            patches["notify_terminal"],
            patches["notify_config"],
            patches["log_attempt"],
        ):
            ci_mock_holder["ci"] = mock_ci
            # AttributeError 없이 완료되어야 함
            # Must complete without AttributeError
            result = await process_pending_retries(db_session, only_ids=[row.id])

        # base_ref='main' 으로 _get_ci_status_safe 호출됨
        # _get_ci_status_safe called with base_ref='main'
        assert ci_mock_holder["ci"].call_args.kwargs["base_ref"] == "main"
        assert result["claimed"] == 1

    # T9-6: 머지 성공 → 알림 전송, log_merge_attempt 호출
    # T9-6: Merge succeeds → notify, log_merge_attempt called
    async def test_process_merge_succeeds_notifies(self, db_session):
        """머지 성공 시 mark_succeeded, log_merge_attempt, _notify_merge_succeeded 호출.
        On merge success, calls mark_succeeded, log_merge_attempt, _notify_merge_succeeded.
        """
        row = _seed_queue_row(db_session)

        patches = _standard_patches(merge_return=(True, None, "abc123"))
        with (
            patches["token"],
            patches["repo_config"],
            patches["pr_data"],
            patches["merge_pr"],
            patches["ci"],
            patches["notify_succeeded"] as mock_notify,
            patches["notify_terminal"],
            patches["notify_config"],
            patches["log_attempt"] as mock_log,
        ):
            result = await process_pending_retries(db_session, only_ids=[row.id])

        assert result["succeeded"] == 1
        assert result["claimed"] == 1
        mock_notify.assert_called_once()
        mock_log.assert_called_once()
        # log_merge_attempt 가 success=True 로 호출됐는지 확인
        # Check log_merge_attempt was called with success=True
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["success"] is True

        db_session.refresh(row)
        assert row.status == "succeeded"

    # 감사 ③ — retry 경로 SHA-bound 불변식 회귀 가드
    # audit ③ — retry path SHA-bound invariant regression guard
    async def test_retry_passes_expected_sha_binds_to_queued_commit(self, db_session):
        """🔴 감사 ③ sha-bound 불변식: retry 는 큐에 적재된 정확한 commit_sha 만 머지한다.

        retry 서비스는 2nd-LLM 검증자를 재실행하지 않지만(초기 머지 1회만), force-push 시
        sha_drift 로 abandon 하고 merge_pr 에 `expected_sha=row.commit_sha` 를 전달해 GitHub 가
        다른 SHA 머지를 차단한다(#962). 따라서 retry 는 '검증자가 승인한 동일 SHA' 만 머지 →
        검증자 staleness 가 실질적으로 발생할 수 없다. 이 불변식(expected_sha 바인딩)이
        회귀하면 검증자 우회 + 잘못된 코드 머지 위험이 생기므로 고정한다.
        """
        row = _seed_queue_row(db_session, commit_sha="abc123")

        patches = _standard_patches(merge_return=(True, None, "abc123"))
        with (
            patches["token"],
            patches["repo_config"],
            patches["pr_data"],
            patches["merge_pr"] as mock_merge,
            patches["ci"],
            patches["notify_succeeded"],
            patches["notify_terminal"],
            patches["notify_config"],
            patches["log_attempt"],
        ):
            await process_pending_retries(db_session, only_ids=[row.id])

        mock_merge.assert_called_once()
        # merge_pr 는 expected_sha=row.commit_sha 로 호출돼야 한다 (SHA 원자성 바인딩)
        # merge_pr must be called with expected_sha=row.commit_sha (SHA atomicity binding)
        assert mock_merge.call_args.kwargs.get("expected_sha") == "abc123"

    async def test_log_merge_attempt_uses_live_threshold_not_snapshot(self, db_session):
        """🔴 C11: 관측 로그의 threshold 가 게이팅에 쓴 live cfg.merge_threshold 와 일치해야 한다.

        게이트(:177)는 live cfg.merge_threshold 로 판정하나 이전엔 로그/Issue 가 enqueue 스냅샷
        (row.threshold_at_enqueue)을 기록 → '실제 머지를 가른 임계값'과 '관측 기록' 발산(감사 부정확).
        seed snapshot=75, 운영 config=85 일 때 로그 threshold=85(live) 여야 한다.
        """
        row = _seed_queue_row(db_session)             # threshold_at_enqueue=75 (스냅샷)
        live_cfg = _make_fake_cfg(merge_threshold=85)  # 운영 현재값 (스냅샷과 발산)

        patches = _standard_patches(cfg=live_cfg, merge_return=(True, None, "abc123"))
        with (
            patches["token"], patches["repo_config"], patches["pr_data"],
            patches["merge_pr"], patches["ci"], patches["notify_succeeded"],
            patches["notify_terminal"], patches["notify_config"],
            patches["log_attempt"] as mock_log,
        ):
            await process_pending_retries(db_session, only_ids=[row.id])

        mock_log.assert_called_once()
        # 로그 threshold = live(85), 스냅샷(75) 아님
        assert mock_log.call_args.kwargs["threshold"] == 85

    # ── P2#17: 종결 경로 MergeAttempt 미러링 (7일 GC 전 최종 결과 이력 보존) ──
    # 회고 2026-07-18 P2#17: 4 종결 경로(max_attempts·config_changed·already_merged·sha_drift)가
    # log_merge_attempt 없이 mark_* 만 해 merge_retry_queue GC(#1075) 후 최종 결과가 소실됐다.
    def _mirror_patches(self, **kw):
        p = _standard_patches(**kw)
        return (p["token"], p["repo_config"], p["pr_data"], p["merge_pr"], p["ci"],
                p["notify_succeeded"], p["notify_terminal"], p["notify_config"],
                p["log_attempt"])

    async def test_already_merged_mirrors_to_merge_attempt(self, db_session):
        """🔴 P2#17 — 이미-머지 종결이 GC 전 MergeAttempt(success=True)로 미러링."""
        row = _seed_queue_row(db_session)
        t, rc, pd, mp, ci, ns, nt, nc, la = self._mirror_patches(
            pr_data={"merged": True, "head": {"sha": "abc123"}},
        )
        with t, rc, pd, mp, ci, ns, nt, nc, la as mock_log:
            await process_pending_retries(db_session, only_ids=[row.id])
        mock_log.assert_called_once()
        assert mock_log.call_args.kwargs["success"] is True

    async def test_sha_drift_mirrors_to_merge_attempt(self, db_session):
        """🔴 P2#17 — SHA drift abandon 이 GC 전 MergeAttempt(success=False, sha_drift)로 미러링."""
        row = _seed_queue_row(db_session, commit_sha="abc123")
        t, rc, pd, mp, ci, ns, nt, nc, la = self._mirror_patches(
            pr_data={"merged": False, "head": {"sha": "force_pushed_sha"}},
        )
        with t, rc, pd, mp, ci, ns, nt, nc, la as mock_log:
            await process_pending_retries(db_session, only_ids=[row.id])
        mock_log.assert_called_once()
        assert mock_log.call_args.kwargs["success"] is False
        assert mock_log.call_args.kwargs["reason"] == "sha_drift"

    async def test_config_changed_mirrors_to_merge_attempt(self, db_session):
        """🔴 P2#17 — config 변경(auto_merge off) abandon 이 GC 전 MergeAttempt(success=False)로 미러링."""
        row = _seed_queue_row(db_session, score=80)
        t, rc, pd, mp, ci, ns, nt, nc, la = self._mirror_patches(cfg=_make_fake_cfg(auto_merge=False))
        with t, rc, pd, mp, ci, ns, nt, nc, la as mock_log:
            await process_pending_retries(db_session, only_ids=[row.id])
        mock_log.assert_called_once()
        assert mock_log.call_args.kwargs["success"] is False
        assert mock_log.call_args.kwargs["reason"] == "config_changed"

    async def test_max_attempts_mirrors_to_merge_attempt(self, db_session):
        """🔴 P2#17 — max_attempts 소진 abandon 이 GC 전 MergeAttempt(success=False)로 미러링.

        이 경로는 cfg 조회 전이라 threshold 는 enqueue 스냅샷(row.threshold_at_enqueue) 사용.
        """
        row = _seed_queue_row(db_session, score=80)
        row.attempts_count = row.max_attempts
        db_session.commit()
        with (
            patch("src.services.merge_retry_service._resolve_github_token", return_value="ghp"),
            patch("src.services.merge_retry_service.log_merge_attempt") as mock_log,
        ):
            await process_pending_retries(
                db_session, now=datetime(2030, 1, 1, tzinfo=timezone.utc), only_ids=[row.id],
            )
        mock_log.assert_called_once()
        assert mock_log.call_args.kwargs["success"] is False
        assert mock_log.call_args.kwargs["reason"] == "max_attempts_exceeded"
        assert mock_log.call_args.kwargs["threshold"] == row.threshold_at_enqueue

    # T9-7: CI 진행 중 → 일시적 실패, 클레임 해제
    # T9-7: CI running → transient, release claim
    async def test_process_transient_ci_running_releases(self, db_session):
        """CI 진행 중이면 release_claim 호출, terminal 아님.
        When CI is running, calls release_claim, not terminal.
        """
        row = _seed_queue_row(db_session)

        patches = _standard_patches(
            merge_return=(False, "unstable_ci: state=unstable, merged=False", ""),
            ci_return="running",
        )
        with (
            patches["token"],
            patches["repo_config"],
            patches["pr_data"],
            patches["merge_pr"],
            patches["ci"],
            patches["notify_succeeded"],
            patches["notify_terminal"],
            patches["notify_config"],
            patches["log_attempt"] as mock_log,
        ):
            result = await process_pending_retries(db_session, only_ids=[row.id])

        assert result["released"] == 1
        assert result["terminal"] == 0
        assert result["claimed"] == 1
        # 일시적 실패는 log_merge_attempt 호출 안 함
        # Transient failure does not call log_merge_attempt
        mock_log.assert_not_called()

        db_session.refresh(row)
        assert row.status == "pending"
        assert row.claimed_at is None

    # T9-8: CI 실패 → terminal 마킹
    # T9-8: CI failed → terminal
    async def test_process_terminal_ci_failed_marks_terminal(self, db_session):
        """CI 실패 시 mark_terminal 호출, log_merge_attempt(success=False) 호출.
        When CI fails, calls mark_terminal and log_merge_attempt with success=False.
        """
        row = _seed_queue_row(db_session)

        patches = _standard_patches(
            merge_return=(False, "unstable_ci: state=unstable, merged=False", ""),
            ci_return="failed",
        )
        with (
            patches["token"],
            patches["repo_config"],
            patches["pr_data"],
            patches["merge_pr"],
            patches["ci"],
            patches["notify_succeeded"],
            patches["notify_terminal"] as mock_notify_t,
            patches["notify_config"],
            patches["log_attempt"] as mock_log,
        ):
            result = await process_pending_retries(db_session, only_ids=[row.id])

        assert result["terminal"] == 1
        assert result["released"] == 0
        assert result["claimed"] == 1
        mock_notify_t.assert_called_once()
        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["success"] is False

        db_session.refresh(row)
        assert row.status == "failed_terminal"
        assert row.last_failure_reason == "unstable_ci"

    # T9-9: 만료된 행 → terminal 마킹
    # T9-9: Expired row → terminal
    async def test_process_expired_row_marks_expired(self, db_session):
        """만료(max_age 초과)된 retriable 행은 terminal 실패가 아니라 'expired' 로 기록.
        Age-expired retriable rows are recorded as 'expired', not a terminal CI failure.

        정합성 감사 P1: mark_expired(status='expired') 가 dead code 였고, 만료 행이
        mark_terminal(reason=CI태그)로 오기록돼 'expired' 상태가 운영에 발생하지 않던 결함.
        """
        row = _seed_queue_row(db_session)

        patches = _standard_patches(
            merge_return=(False, "unstable_ci: state=unstable, merged=False", ""),
            ci_return="running",  # 재시도 가능 상태이나 max_age 초과 → expired
        )
        with (
            patches["token"],
            patches["repo_config"],
            patches["pr_data"],
            patches["merge_pr"],
            patches["ci"],
            patches["notify_succeeded"],
            patches["notify_terminal"] as mock_notify_t,
            patches["notify_config"],
            patches["log_attempt"] as mock_log,
            patch(
                "src.services.merge_retry_service.is_expired",
                return_value=True,
            ),
        ):
            result = await process_pending_retries(db_session, only_ids=[row.id])

        assert result["expired"] == 1       # 만료는 expired 카운트
        assert result["terminal"] == 0      # terminal 실패 아님
        assert result["released"] == 0
        mock_notify_t.assert_called_once()  # 재시도 중단 알림은 유지
        mock_log.assert_called_once()

        db_session.refresh(row)
        assert row.status == "expired"      # failed_terminal 아님

    # T9-10: 인프라 에러 → 30초 백오프로 클레임 해제
    # T9-10: Infra error → release with 30s backoff
    async def test_process_infra_error_releases_with_30s_backoff(self, db_session):
        """httpx.HTTPError 발생 시 30초 백오프로 클레임 해제, released 증가.
        On httpx.HTTPError, releases claim with 30s backoff and increments released.
        """
        import httpx

        row = _seed_queue_row(db_session)

        fake_cfg = _make_fake_cfg()
        with (
            patch(
                "src.services.merge_retry_service._resolve_github_token",
                return_value="ghp_test",
            ),
            patch(
                "src.services.merge_retry_service.get_repo_config",
                return_value=fake_cfg,
            ),
            patch(
                "src.services.merge_retry_service._get_pr_data",
                new_callable=AsyncMock,
                return_value=_DEFAULT_PR_DATA,
            ),
            patch(
                "src.services.merge_retry_service.merge_pr",
                new_callable=AsyncMock,
                side_effect=httpx.HTTPError("connection failed"),
            ),
            patch(
                "src.services.merge_retry_service._get_ci_status_safe",
                new_callable=AsyncMock,
                return_value="unknown",
            ),
            patch(
                "src.services.merge_retry_service._notify_merge_succeeded",
                new_callable=AsyncMock,
            ),
            patch(
                "src.services.merge_retry_service._notify_merge_terminal",
                new_callable=AsyncMock,
            ),
            patch(
                "src.services.merge_retry_service._notify_config_changed",
                new_callable=AsyncMock,
            ),
            patch("src.services.merge_retry_service.log_merge_attempt"),
        ):
            now = datetime.now(timezone.utc)
            result = await process_pending_retries(
                db_session, now=now, only_ids=[row.id]
            )

        assert result["released"] == 1
        assert result["terminal"] == 0
        assert result["claimed"] == 1

        # claimed_at 이 None 으로 초기화됐는지 확인
        # Check claimed_at was reset to None
        db_session.refresh(row)
        assert row.claimed_at is None
        assert row.last_failure_reason == "infra_error"
        # 30초 백오프 확인 — 재시도 시각이 now + ~30초여야 함
        # Verify 30s backoff — retry time should be ~now + 30s
        expected = now.replace(tzinfo=None) + timedelta(seconds=30)
        delta = abs((row.next_retry_at - expected).total_seconds())
        assert delta < 5  # 5초 오차 허용 / 5s tolerance

    # T9-11: auto_merge_issue_on_failure=True 시 failure issue 생성
    # T9-11: auto_merge_issue_on_failure=True → creates failure issue
    async def test_process_terminal_creates_failure_issue_when_configured(
        self, db_session
    ):
        """cfg.auto_merge_issue_on_failure=True 이면 create_merge_failure_issue 호출.
        When cfg.auto_merge_issue_on_failure=True, calls create_merge_failure_issue.
        """
        row = _seed_queue_row(db_session)

        # auto_merge_issue_on_failure=True 로 설정 — _standard_patches cfg 파라미터 사용
        # Pass cfg with auto_merge_issue_on_failure=True via _standard_patches cfg param
        issue_cfg = _make_fake_cfg(auto_merge_issue_on_failure=True)
        patches = _standard_patches(
            merge_return=(False, "branch_protection_blocked: admin override required", ""),
            ci_return="failed",
            cfg=issue_cfg,
        )
        with (
            patches["token"],
            patches["repo_config"],
            patches["pr_data"],
            patches["merge_pr"],
            patches["ci"],
            patches["notify_succeeded"],
            patches["notify_terminal"],
            patches["notify_config"],
            patches["log_attempt"],
            patch(
                "src.services.merge_retry_service.create_merge_failure_issue",
                new_callable=AsyncMock,
            ) as mock_issue,
        ):
            result = await process_pending_retries(
                db_session, only_ids=[row.id]
            )

        assert result["terminal"] == 1
        mock_issue.assert_called_once()

    async def test_failure_log_and_issue_use_live_threshold(self, db_session):
        """🔴 C11 failure 경로: terminal 실패 로그(success=False)와 failure Issue 의 threshold 가
        enqueue 스냅샷이 아니라 live cfg.merge_threshold 와 일치해야 한다 (3곳 중 248·488 봉인)."""
        row = _seed_queue_row(db_session)                                   # 스냅샷=75
        live_cfg = _make_fake_cfg(auto_merge_issue_on_failure=True, merge_threshold=85)
        patches = _standard_patches(
            merge_return=(False, "branch_protection_blocked: admin override required", ""),
            ci_return="failed",
            cfg=live_cfg,
        )
        with (
            patches["token"], patches["repo_config"], patches["pr_data"],
            patches["merge_pr"], patches["ci"], patches["notify_succeeded"],
            patches["notify_terminal"], patches["notify_config"],
            patches["log_attempt"] as mock_log,
            patch("src.services.merge_retry_service.create_merge_failure_issue",
                  new_callable=AsyncMock) as mock_issue,
        ):
            await process_pending_retries(db_session, only_ids=[row.id])

        # 실패 로그(248) + failure Issue(488) 모두 live(85), 스냅샷(75) 아님
        assert mock_log.call_args.kwargs["success"] is False
        assert mock_log.call_args.kwargs["threshold"] == 85
        mock_issue.assert_called_once()
        assert mock_issue.call_args.kwargs["threshold"] == 85

    # T9-13: max_attempts 초과 행 → abandoned 처리
    # T9-13: Row exceeding max_attempts → abandoned
    async def test_process_max_attempts_exhausted_is_abandoned(self, db_session):
        """max_attempts 초과 시 abandoned 처리됨을 검증한다.
        Verify that rows exceeding max_attempts are marked abandoned.
        """
        row = _seed_queue_row(db_session, score=80)
        # 초과 상태 시뮬레이션 — attempts_count를 max_attempts와 같게 설정
        # Simulate exhaustion — set attempts_count equal to max_attempts
        row.attempts_count = row.max_attempts
        db_session.commit()

        with patch(
            "src.services.merge_retry_service._resolve_github_token",
            return_value="ghp_token",
        ):
            result = await process_pending_retries(
                db_session,
                now=datetime(2030, 1, 1, tzinfo=timezone.utc),
                only_ids=[row.id],
            )

        assert result["abandoned"] == 1
        assert result["succeeded"] == 0
        db_session.refresh(row)
        assert row.status == "abandoned"
        assert row.last_failure_reason == "max_attempts_exceeded"

    # T9-12: 여러 행 처리 — 1개 성공, 1개 terminal, 1개 released
    # T9-12: Multiple rows processed — 1 success, 1 terminal, 1 released
    async def test_process_multiple_rows_all_processed(self, db_session):
        """3개의 pending 행을 처리: 1 성공, 1 terminal, 1 released.
        Process 3 pending rows: 1 succeeds, 1 becomes terminal, 1 is released.
        """
        row1 = _seed_queue_row(db_session, commit_sha="sha_success")
        row2 = _seed_queue_row(db_session, commit_sha="sha_terminal")
        row3 = _seed_queue_row(db_session, commit_sha="sha_transient")

        # expected_sha 로 행 구분 — 각 행은 서로 다른 commit_sha 를 가짐
        # Distinguish rows by expected_sha — each row has a unique commit_sha
        def _merge_side_effect(*_args, **kwargs):
            sha = kwargs.get("expected_sha", "")
            if sha == "sha_success":
                return (True, None, sha)
            if sha == "sha_terminal":
                return (False, "branch_protection_blocked: admin required", "")
            # sha_transient
            return (False, "unstable_ci: state=unstable", "")

        # _get_pr_data 는 commit_sha 와 동일한 head.sha 를 반환해야 SHA drift 없음
        # _get_pr_data must return head.sha matching commit_sha to avoid SHA drift
        # AsyncMock side_effect 은 동기 함수도 허용 (값을 awaitable 로 감쌈)
        # AsyncMock side_effect accepts sync functions (wraps return value as awaitable)
        _call_counter = [0]  # 뮤터블 컨테이너로 클로저 변수 공유 / mutable container for closure sharing

        def _pr_data_side_effect(token, repo, pr):  # pylint: disable=unused-argument
            # 호출 순서로 SHA 결정 (순서: row1, row2, row3)
            # Determine SHA by call order (order: row1, row2, row3)
            count = _call_counter[0]
            _call_counter[0] += 1
            sha_map = {0: "sha_success", 1: "sha_terminal", 2: "sha_transient"}
            sha = sha_map.get(count, "sha_success")
            return {"merged": False, "head": {"sha": sha}, "state": "open"}

        multi_cfg = _make_fake_cfg()
        with (
            patch(
                "src.services.merge_retry_service._resolve_github_token",
                return_value="ghp_test",
            ),
            patch(
                "src.services.merge_retry_service.get_repo_config",
                return_value=multi_cfg,
            ),
            patch(
                "src.services.merge_retry_service._get_pr_data",
                new_callable=AsyncMock,
                side_effect=_pr_data_side_effect,
            ),
            patch(
                "src.services.merge_retry_service.merge_pr",
                new_callable=AsyncMock,
                side_effect=_merge_side_effect,
            ),
            patch(
                "src.services.merge_retry_service._get_ci_status_safe",
                new_callable=AsyncMock,
                return_value="running",
            ),
            patch(
                "src.services.merge_retry_service._notify_merge_succeeded",
                new_callable=AsyncMock,
            ),
            patch(
                "src.services.merge_retry_service._notify_merge_terminal",
                new_callable=AsyncMock,
            ),
            patch(
                "src.services.merge_retry_service._notify_config_changed",
                new_callable=AsyncMock,
            ),
            patch("src.services.merge_retry_service.log_merge_attempt"),
        ):
            result = await process_pending_retries(
                db_session,
                only_ids=[row1.id, row2.id, row3.id],
            )

        assert result["claimed"] == 3
        assert result["succeeded"] == 1
        assert result["terminal"] == 1
        assert result["released"] == 1
        assert result["abandoned"] == 0
        assert result["skipped"] == 0


# ---------------------------------------------------------------------------
# _get_ci_status_safe — 빈 set fallback 방어층 (engine.py 와 일관)
# _get_ci_status_safe — empty-set fallback defense layer (consistent with engine)
# ---------------------------------------------------------------------------


async def test_worker_get_ci_status_safe_converts_empty_set_to_none():
    """워커 측 _get_ci_status_safe 도 빈 set 을 None 으로 변환한다.

    Phase 12 — engine.py::_get_ci_status_safe 와 동일 패턴 적용.
    BPR Required Status Checks 미설정 시 빈 set 이 반환되는데, 그대로
    get_ci_status 에 전달하면 호출 측이 'failed' 라 오해할 위험이 있어
    None 으로 통일 (모든 체크 고려 의미).
    """
    from src.services.merge_retry_service import _get_ci_status_safe

    with patch(
        "src.services.merge_retry_service.get_required_check_contexts",
        new_callable=AsyncMock,
    ) as mock_required, patch(
        "src.services.merge_retry_service.get_ci_status",
        new_callable=AsyncMock,
    ) as mock_ci:
        mock_required.return_value = set()  # 빈 set — BPR 미설정 시나리오
        mock_ci.return_value = "running"

        result = await _get_ci_status_safe("token", "owner/repo", "sha123")

    assert result == "running"
    # 핵심 검증 — required_contexts 가 None 으로 전달되어야 함
    call_kwargs = mock_ci.call_args.kwargs
    assert call_kwargs.get("required_contexts") is None
