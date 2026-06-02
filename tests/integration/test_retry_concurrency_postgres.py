"""Phase 12 T14 — Postgres 동시성 증명: claim_batch SKIP LOCKED 동작 검증.
Phase 12 T14 — Postgres concurrency proof: claim_batch SKIP LOCKED behaviour.

실행 조건: DATABASE_URL_TEST_POSTGRES 환경변수 설정 시에만 실행.
Execution guard: only runs when DATABASE_URL_TEST_POSTGRES env var is set.

세 가지 시나리오를 검증한다:
Three scenarios are verified:
  1. 동시 클레임 — 중복 처리 없음 (각 워커가 서로 다른 행 획득)
     Concurrent claim — no double-processing (each worker gets a distinct row)
  2. Stale 클레임 회복 — 크래시된 워커의 행 재획득
     Stale claim recovery — reclaim rows from a crashed worker
  3. SKIP LOCKED — 동일 행을 두 세션이 동시에 클레임할 때 한 쪽만 성공
     SKIP LOCKED — only one of two concurrent sessions claims the same row
"""
import os
import threading
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# DATABASE_URL_TEST_POSTGRES 는 테스트 실행 시점에 게으르게 읽는다.
# Read DATABASE_URL_TEST_POSTGRES lazily at test execution time.
_PG_URL = os.environ.get("DATABASE_URL_TEST_POSTGRES", "")

# 스킵 데코레이터 — Postgres URL 미설정 시 모든 테스트를 건너뜀.
# Skip decorator — skips all tests when Postgres URL is not configured.
_requires_postgres = pytest.mark.skipif(
    not _PG_URL,
    reason="Postgres concurrency test requires DATABASE_URL_TEST_POSTGRES",
)


def _make_engine():
    """테스트 전용 Postgres 엔진 생성 — StaticPool 사용 금지.
    Create a dedicated Postgres engine for tests — must NOT use StaticPool.
    """
    # pool_pre_ping: 끊긴 연결 자동 감지
    # pool_pre_ping: auto-detect stale connections.
    return create_engine(_PG_URL, pool_pre_ping=True)


def _seed_postgres_row(
    session,
    repo_name: str,
    pr_num: int,
    *,
    score: int = 80,
    threshold: int = 75,
) -> int:
    """Postgres 세션에 Repository + Analysis + MergeRetryQueue 시드 행 삽입.
    Insert a Repository + Analysis + MergeRetryQueue seed row into the Postgres session.

    반환값: 삽입된 MergeRetryQueue 행의 id.
    Returns: id of the inserted MergeRetryQueue row.
    """
    # 순환 import 방지를 위해 함수 내부에서 import
    # Import inside function to avoid circular imports.
    from src.models.analysis import Analysis
    from src.models.merge_retry import MergeRetryQueue
    from src.models.repository import Repository

    # 리포 생성 — 동일 full_name 이 이미 있으면 재사용
    # Create repo — reuse if full_name already exists.
    repo = session.query(Repository).filter_by(full_name=repo_name).first()
    if repo is None:
        repo = Repository(full_name=repo_name)
        session.add(repo)
        session.flush()

    # 분석 레코드 생성 (unique SHA: repo_name + pr_num 조합)
    # Create Analysis record (unique SHA: composite of repo_name + pr_num).
    sha = f"sha_{repo_name.replace('/', '_')}_{pr_num}"
    analysis = Analysis(
        repo_id=repo.id,
        commit_sha=sha,
        score=score,
        grade="B",
        result={},
        pr_number=pr_num,
    )
    session.add(analysis)
    session.flush()

    # 재시도 큐 행 삽입 — next_retry_at 을 과거로 설정해 즉시 처리 대상으로 만든다.
    # Insert retry queue row — set next_retry_at in the past so it is due immediately.
    row = MergeRetryQueue(
        repo_full_name=repo_name,
        pr_number=pr_num,
        analysis_id=analysis.id,
        commit_sha=sha,
        score=score,
        threshold_at_enqueue=threshold,
        status="pending",
        attempts_count=0,
        max_attempts=30,
        next_retry_at=datetime(2020, 1, 1),  # 항상 과거 — 즉시 처리 대상 / always past — due immediately
        notify_chat_id=None,
    )
    session.add(row)
    session.commit()
    return row.id


@_requires_postgres
def test_concurrent_claim_no_double_processing():
    """동시 클레임 시 중복 처리 없음을 검증.
    Verify no double-processing under concurrent claims.

    2개 스레드가 각각 limit=1 로 claim_batch 를 호출할 때,
    두 스레드가 합쳐서 정확히 2개의 서로 다른 행을 획득해야 한다.
    When 2 threads each call claim_batch with limit=1,
    together they must claim exactly 2 distinct rows with no overlap.
    """
    from src.database import Base
    from src.repositories.merge_retry_repo import claim_batch

    engine = _make_engine()

    try:
        # 테스트 전 테이블 재생성 — 이전 테스트 잔류 데이터 제거
        # Recreate tables — remove any data left from previous runs.
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

        Session = sessionmaker(bind=engine)

        # 시드 행 2개 삽입 (두 워커가 각각 1개씩 가져가야 함)
        # Insert 2 seed rows (each worker should get exactly one).
        with Session() as seed_session:
            row_id_1 = _seed_postgres_row(seed_session, "owner/repo-cc", 1)
            row_id_2 = _seed_postgres_row(seed_session, "owner/repo-cc", 2)

        # 결과 저장 공간 + 에러 수집기
        # Result storage and error collector.
        results: list = [None, None]
        errors: list = []
        # barrier — 두 워커의 claim_batch SELECT 가 동시에 실행되도록 동기화.
        # 미동반 시 SELECT 윈도우 비중첩으로 회귀(SKIP LOCKED 제거)조차 spurious-pass 가능.
        # timeout=30 — 한 워커가 barrier 도달 전 예외 시 다른 워커 무기한 block 방지 (deadlock guard).
        barrier = threading.Barrier(2, timeout=30)

        def worker(i: int) -> None:
            """스레드 워커 — 독립 세션으로 claim_batch 호출.
            Thread worker — calls claim_batch in an independent session.
            """
            try:
                with Session() as db:
                    barrier.wait()  # 두 워커 동시 진입 강제 / force concurrent entry
                    claimed = claim_batch(
                        db,
                        now=datetime.now(timezone.utc).replace(tzinfo=None),
                        limit=1,
                    )
                    db.commit()
                    # 클레임된 행 id 목록 저장
                    # Store list of claimed row ids.
                    results[i] = [r.id for r in claimed]
            except Exception as exc:  # pylint: disable=broad-except
                errors.append(exc)

        # 두 스레드 동시 실행
        # Run both threads concurrently.
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 에러 없이 완료되어야 함
        # Must complete without errors.
        assert not errors, f"Unexpected errors from worker threads: {errors}"

        # 각 스레드가 정확히 1개 행을 클레임했는지 확인 (limit=1, 2개 시드)
        # Confirm each thread claimed exactly 1 row (limit=1, 2 seeded rows).
        assert len(results[0]) == 1, (
            f"Worker 0 expected exactly 1 claimed row, got {results[0]}"
        )
        assert len(results[1]) == 1, (
            f"Worker 1 expected exactly 1 claimed row, got {results[1]}"
        )

        # 두 스레드가 획득한 행 id 를 합산
        # Aggregate claimed row ids from both threads.
        all_claimed_ids = results[0] + results[1]

        # 합산 수 = 2 (중복 없이 각 1개씩)
        # Total count must be 2 (one each, no duplicates).
        assert len(all_claimed_ids) == 2, (
            f"Expected 2 total claimed rows, got {len(all_claimed_ids)}: {all_claimed_ids}"
        )

        # 두 행 id 가 삽입한 행과 일치하고 서로 다름
        # The two row ids match the seeded rows and are distinct.
        assert set(all_claimed_ids) == {row_id_1, row_id_2}, (
            f"Expected claimed ids {{{row_id_1}, {row_id_2}}}, got {set(all_claimed_ids)}"
        )

    finally:
        # 테스트 후 정리 — 다른 테스트에 영향을 주지 않도록 테이블 삭제
        # Clean up after test — drop tables to avoid affecting other tests.
        Base.metadata.drop_all(engine)
        engine.dispose()


@_requires_postgres
def test_stale_claim_recovery():
    """Stale 클레임 행 회복 — 크래시된 워커 시뮬레이션.
    Stale claim recovery — simulate a crashed worker.

    claimed_at 이 10분 전인 행은 stale_after_seconds=300 기준으로 재클레임 가능.
    A row with claimed_at 10 minutes ago is reclaimable with stale_after_seconds=300.
    """
    from src.database import Base
    from src.models.merge_retry import MergeRetryQueue
    from src.repositories.merge_retry_repo import claim_batch

    engine = _make_engine()

    try:
        # 테이블 재생성
        # Recreate tables.
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

        Session = sessionmaker(bind=engine)

        # 시드 행 삽입
        # Insert seed row.
        with Session() as seed_session:
            row_id = _seed_postgres_row(seed_session, "owner/repo-stale", 10)

        # claimed_at 을 10분 전으로 설정해 stale 상태 시뮬레이션
        # Set claimed_at to 10 minutes ago to simulate a crashed worker.
        from datetime import timedelta

        stale_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
        with Session() as update_session:
            row = update_session.query(MergeRetryQueue).filter_by(id=row_id).one()
            row.claimed_at = stale_time
            row.claim_token = "old-token-from-crashed-worker"
            update_session.commit()

        # stale_after_seconds=300(5분) — 10분 전 클레임은 stale 로 간주
        # stale_after_seconds=300 (5 min) — a 10-minute-old claim is considered stale.
        with Session() as db:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            claimed = claim_batch(db, now=now, stale_after_seconds=300)
            db.commit()
            # 세션 종료 전 필요한 속성 추출 — commit 후 expire 된 ORM 속성을 세션 밖에서
            # 접근하면 DetachedInstanceError (사이클 156 S3: CI 영구 skip 으로 가려져 있던 잠재 버그).
            # Capture attributes before the session closes; commit expires them and
            # accessing them after the session ends raises DetachedInstanceError.
            reclaimed_count = len(claimed)
            reclaimed_id = claimed[0].id if claimed else None
            reclaimed_token = claimed[0].claim_token if claimed else None
            reclaimed_attempts = claimed[0].attempts_count if claimed else None

        # stale 행이 재클레임되어야 함
        # The stale row must be reclaimed.
        assert reclaimed_count == 1, (
            f"Expected 1 reclaimed row, got {reclaimed_count}"
        )
        assert reclaimed_id == row_id, (
            f"Expected row id {row_id}, got {reclaimed_id}"
        )

        # claim_token 이 새 UUID 로 교체되었는지 확인
        # Confirm claim_token was replaced with a new UUID.
        assert reclaimed_token != "old-token-from-crashed-worker", (
            "claim_token must be updated when a stale claim is reclaimed"
        )

        # attempts_count 가 1 증가했는지 확인
        # Confirm attempts_count was incremented by 1.
        assert reclaimed_attempts == 1, (
            f"Expected attempts_count=1, got {reclaimed_attempts}"
        )

    finally:
        # 테스트 후 정리
        # Clean up after test.
        Base.metadata.drop_all(engine)
        engine.dispose()


@_requires_postgres
def test_skip_locked_prevents_concurrent_double_claim():
    """SKIP LOCKED — 두 세션이 동일 행을 동시에 클레임할 때 한 쪽만 성공.
    SKIP LOCKED — only one of two concurrent sessions can claim the same row.

    1개 행 + 2개 스레드 → 정확히 1개 스레드가 행을 획득, 나머지는 빈 목록 반환.
    1 row + 2 threads → exactly 1 thread gets the row, the other gets an empty list.
    """
    from src.database import Base
    from src.repositories.merge_retry_repo import claim_batch

    engine = _make_engine()

    try:
        # 테이블 재생성
        # Recreate tables.
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

        Session = sessionmaker(bind=engine)

        # 시드 행 1개만 삽입 — 두 스레드가 이 행을 두고 경쟁
        # Insert exactly 1 seed row — both threads race for this single row.
        with Session() as seed_session:
            row_id = _seed_postgres_row(seed_session, "owner/repo-skip", 20)

        # 결과 저장 공간 + 에러 수집기
        # Result storage and error collector.
        results: list = [None, None]
        errors: list = []
        # barrier — 두 세션이 동일 행을 두고 동시에 SELECT...FOR UPDATE SKIP LOCKED 를 치도록 강제.
        # 이 동시성이 SKIP LOCKED 의 non-blocking 획득(한 쪽만 성공)을 실제로 검증하는 핵심 조건.
        # timeout=30 — deadlock guard (한 워커 조기 예외 시 무기한 block 방지).
        barrier = threading.Barrier(2, timeout=30)

        def worker(i: int) -> None:
            """스레드 워커 — 독립 세션으로 동일 행 claim 시도.
            Thread worker — attempts to claim the same row in an independent session.
            """
            try:
                with Session() as db:
                    barrier.wait()  # 두 워커 동시 진입 강제 / force concurrent entry
                    claimed = claim_batch(
                        db,
                        now=datetime.now(timezone.utc).replace(tzinfo=None),
                        limit=1,
                    )
                    db.commit()
                    # 클레임된 행 id 목록 저장
                    # Store claimed row id list.
                    results[i] = [r.id for r in claimed]
            except Exception as exc:  # pylint: disable=broad-except
                errors.append(exc)

        # 두 스레드 동시 실행
        # Run both threads concurrently.
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 에러 없이 완료되어야 함
        # Must complete without errors.
        assert not errors, f"Unexpected errors from worker threads: {errors}"

        # 각 워커가 리스트를 반환했는지 확인 (SKIP LOCKED 로 한 워커는 0개 가능)
        # Confirm each worker returned a list (one may get 0 rows due to SKIP LOCKED).
        assert isinstance(results[0], list), (
            f"Worker 0 did not return a list: {results[0]}"
        )
        assert isinstance(results[1], list), (
            f"Worker 1 did not return a list: {results[1]}"
        )

        # 두 결과를 합산 — 정확히 1개 행만 클레임되어야 함
        # Aggregate results — exactly 1 row must be claimed in total.
        all_claimed_ids = results[0] + results[1]

        assert len(all_claimed_ids) == 1, (
            f"Expected exactly 1 claimed row (SKIP LOCKED prevents double-claim), "
            f"got {len(all_claimed_ids)}: {all_claimed_ids}"
        )

        # 클레임된 행이 삽입한 행 id 와 일치
        # The claimed row id must match the seeded row.
        assert all_claimed_ids[0] == row_id, (
            f"Expected claimed id {row_id}, got {all_claimed_ids[0]}"
        )

        # 한 쪽은 획득 성공, 다른 쪽은 빈 목록
        # One side succeeded, the other got an empty list.
        claimed_counts = (len(results[0]), len(results[1]))
        assert sorted(claimed_counts) == [0, 1], (
            f"Expected one thread to get 1 row and the other 0, got counts: {claimed_counts}"
        )

    finally:
        # 테스트 후 정리
        # Clean up after test.
        Base.metadata.drop_all(engine)
        engine.dispose()
