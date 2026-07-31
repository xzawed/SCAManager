"""배치 소유권 토큰 스냅샷 — `expire_on_commit` 이 CAS 를 무력화하지 못하게 (2026-07-31 P1).

## 사고 (실측 재현)

`process_pending_retries` 는 배치의 각 행을 처리하며 **행마다 write-back 을 commit** 한다.
`src/database.py:122-124` 의 `sessionmaker` 는 `expire_on_commit` 을 지정하지 않아 기본값 True 이므로,
**첫 행의 commit 이 세션 전체를 만료**시킨다. 그래서 이전 판이 루프 안에서 읽던
`row.claim_token` 은 rows 2..N 에서 **캡처가 아니라 DB 재조회**였다.

그 사이 다른 워커가 stale(>300s) 재클레임했다면 재조회값 = **그 워커의 토큰**이다. 결과:

1. 이 워커(A)가 남의 행(B 소유)을 자기 것으로 알고 `release_claim` → **해제 성공**
2. 정당한 소유자 B 의 `mark_terminal(expected_claim_token=B_TOK)` 이 **CAS 0행 매치 → False**
3. B 의 종결 결과가 소실되고 행이 `pending` 으로 **부활** → 재시도·재알림

즉 CAS 가 막으려던 실패 모드(`merge_retry_repo` §CAS 존재 이유)가 **소유자 쪽으로 뒤집혔다**.
기본 batch=50 에서 **49/50 행이 무방비**였다.

## 이 파일이 기존 테스트와 다른 이유

`test_merge_retry_cas_wiring.py` 는 6건 전부 green 인 채로 이 결함을 통과시켰다 —
`SimpleNamespace` row(ORM 만료 없음) · **단일 행** 배치 · `MagicMock()` db 를 쓰기 때문이다.
그 셋 중 하나라도 있으면 이 축은 **원리적으로 관측 불가**하다. 그래서 여기서는
**실 ORM · 2행 배치 · 교차 세션 · 파일 SQLite** 를 쓴다.

Existing CAS wiring tests pass while this defect is live: SimpleNamespace rows never expire, a
single-row batch never crosses a commit boundary, and a MagicMock db has no identity map.
"""
# pylint: disable=redefined-outer-name
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.analysis import Analysis
from src.models.merge_retry import MergeRetryQueue
from src.models.repository import Repository
from src.repositories import merge_retry_repo
from src.services import merge_retry_service

_NOW = datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def make_session(tmp_path):
    """운영과 동일 설정의 세션 팩토리 — 파일 SQLite 라 세션 간 격리가 실재한다.

    🔴 `:memory:` 는 연결마다 별개 DB 라 교차 세션을 재현할 수 없고,
    🔴 `expire_on_commit` 을 지정하지 않아야 운영(`src/database.py:122-124`)과 같다 —
       여기서 False 로 두면 이 테스트가 검증하려는 축 자체가 사라진다.
    File-backed SQLite for real cross-session isolation; expire_on_commit left at its default
    exactly as production does — pinning it False here would erase the axis under test.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'retry.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _seed(db, count: int) -> list[int]:
    """분석 + 재시도 큐 행 N개. / N analyses with queued retries."""
    repo = Repository(full_name="owner/repo")
    db.add(repo)
    db.flush()
    ids = []
    for i in range(count):
        analysis = Analysis(
            repo_id=repo.id, commit_sha=f"sha{i}", pr_number=i + 1, score=90, grade="A",
            result={"score": 90, "grade": "A", "source": "pr"},
        )
        db.add(analysis)
        db.flush()
        row = MergeRetryQueue(
            analysis_id=analysis.id, repo_full_name="owner/repo", pr_number=i + 1,
            commit_sha=f"sha{i}", status="pending", attempts_count=0,
            score=90, threshold_at_enqueue=60,
            next_retry_at=_NOW.replace(tzinfo=None) - timedelta(seconds=10),
        )
        db.add(row)
        db.flush()
        ids.append(row.id)
    db.commit()
    return ids


def test_snapshot_survives_expire_on_commit_and_protects_other_workers_claim(make_session):
    """🔴 배치 2번째 행에서 **남의 claim 을 해제하지 않는다** — 그리고 소유자의 종결이 살아남는다.

    이전 판(루프 안 `row.claim_token`)에서는 (1) A 가 B 의 행을 해제하고 (2) B 의
    `mark_terminal` 이 CAS 거부돼 종결이 소실되며 (3) 행이 `pending` 으로 부활했다.
    """
    setup = make_session()
    ids = _seed(setup, 2)
    setup.close()

    # ── A 워커: 2행 배치 클레임 → 토큰을 **값으로** 스냅샷 (수정의 핵심) ──
    worker_a = make_session()
    claimed = merge_retry_repo.claim_batch(worker_a, now=_NOW, limit=10)
    assert len(claimed) == 2, "전제 붕괴 — 2행 배치가 필요하다(단일 행은 commit 경계를 넘지 않는다)"
    snapshot = {r.id: r.claim_token for r in claimed}
    a_token = snapshot[ids[1]]

    # ── B 워커: stale 임계를 넘겨 2번째 행만 재클레임 (다른 세션) ──
    worker_b = make_session()
    reclaimed = merge_retry_repo.claim_batch(
        worker_b, now=_NOW + timedelta(seconds=400), limit=10, only_ids=[ids[1]],
    )
    assert len(reclaimed) == 1, "stale 재클레임 전제 붕괴"
    b_token = reclaimed[0].claim_token
    assert b_token != a_token, "재클레임이 새 토큰을 부여해야 한다"

    # ── A 가 1번째 행을 종결(commit) — 이 commit 이 A 세션 전체를 만료시킨다 ──
    assert merge_retry_repo.mark_succeeded(
        worker_a, ids[0], now=_NOW, expected_claim_token=snapshot[ids[0]],
    )

    # 🔴 만료 실증 — 이제 `row.claim_token` 을 읽으면 **B 의 토큰**이 돌아온다.
    #    스냅샷이 없으면 A 는 이것을 자기 토큰으로 착각한다.
    row2 = next(r for r in claimed if r.id == ids[1])
    assert row2.claim_token == b_token, "전제 붕괴 — expire_on_commit 재조회가 일어나야 한다"
    assert snapshot[ids[1]] == a_token, "스냅샷은 값이라 만료 영향을 받지 않아야 한다"

    # ── A 가 2번째 행을 해제 시도 — 스냅샷 토큰이므로 CAS 가 막아야 한다 ──
    released = merge_retry_repo.release_claim(
        worker_a, ids[1],
        next_retry_at=_NOW.replace(tzinfo=None) + timedelta(seconds=30),
        last_failure_reason="infra_error",
        expected_claim_token=snapshot[ids[1]],
        now=_NOW,
    )
    worker_a.close()
    assert released is False, (
        "A 가 B 소유 행의 claim 을 해제했다 — 스냅샷이 아니라 만료 후 재조회값을 쓰고 있다"
    )

    # ── 정당한 소유자 B 의 종결이 살아남아야 한다 (원 finding 이 놓친 피해) ──
    ok = merge_retry_repo.mark_terminal(
        worker_b, ids[1], reason="max_attempts", now=_NOW + timedelta(seconds=400),
        expected_claim_token=b_token,
    )
    worker_b.close()
    assert ok is True, "소유자의 종결이 CAS 거부됐다 — 결과 소실"

    verify = make_session()
    final = verify.get(MergeRetryQueue, ids[1])
    assert final.status != "pending", (
        f"행이 pending 으로 부활했다(status={final.status}) — 종결 소실 + 재시도·재알림 반복"
    )
    verify.close()


def test_snapshot_is_taken_before_any_per_row_commit(make_session):
    """대조군 — 스냅샷 시점이 `claim_batch` 의 commit+refresh **직후**여야 유효하다.

    `claim_batch` 자체가 commit 후 각 행을 `refresh` 하므로, 반환 직후의 값은 이 워커의 토큰이다.
    루프가 시작돼 첫 write-back 이 commit 되는 순간부터는 더 이상 그렇지 않다.
    """
    setup = make_session()
    ids = _seed(setup, 2)
    setup.close()

    worker = make_session()
    claimed = merge_retry_repo.claim_batch(worker, now=_NOW, limit=10)
    snapshot = {r.id: r.claim_token for r in claimed}
    assert all(v for v in snapshot.values()), "클레임 직후 토큰이 비어 있다"
    assert len(set(snapshot.values())) == 1, (
        "현 구현은 배치 전체에 단일 UUID 를 쓴다 — 이 전제가 깨지면 dict 스냅샷이 더 중요해진다"
    )
    worker.close()


def test_service_loop_never_reads_claim_token_off_the_row():
    """🔴 루프 **안에서** `row.claim_token` 을 읽지 않는지 — AST 관측.

    🔴 초판은 "스냅샷이 루프보다 앞에 있는가" 만 봤다. 그건 **존재**만 보고 **사용**은 보지 않아,
    `claim_tokens = {...}` 대입을 남긴 채 `_orig_tok = row.claim_token` 으로 되돌리는 뮤테이션이
    **GREEN** 이었다(실측). 결함을 통과시키는 가드는 가드가 아니다.
    The first version asserted the snapshot merely *existed* before the loop, so restoring the
    in-loop re-read stayed green. Assert the re-read is absent instead.
    """
    import ast
    import inspect

    fn = ast.parse(inspect.getsource(merge_retry_service.process_pending_retries).lstrip()).body[0]
    loop = next(
        (n for n in ast.walk(fn) if isinstance(n, ast.For) and getattr(n.iter, "id", "") == "claimed"),
        None,
    )
    assert loop is not None, "`for row in claimed:` 루프를 찾지 못했다"

    offenders = [
        n.lineno for n in ast.walk(loop)
        if isinstance(n, ast.Attribute) and n.attr == "claim_token"
        and getattr(n.value, "id", "") == "row"
    ]
    assert not offenders, (
        f"루프 안에서 `row.claim_token` 을 읽는다 (line {offenders}) — "
        "직전 행의 commit 이 세션을 만료시킨 뒤라 이것은 캡처가 아니라 DB 재조회다."
    )

    # 🔴 `_process_single_retry` 에 토큰을 **실제로 전달**하는지 (kwarg 배선 관측).
    #   그 함수 내부의 `_claim_tok` 은 `claim_token=None` 시 `row.claim_token` 으로 폴백하므로,
    #   kwarg 를 빼면 함수 안의 모든 write-back 이 다시 만료 후 재조회 토큰을 쓴다.
    #   실측: kwarg 제거 뮤테이션이 행동 테스트만으로는 **GREEN** 이었다(테스트가 그 함수를 대체하므로).
    # Observe the kwarg wiring: without it the callee falls back to the expired re-read.
    call = next(
        (n for n in ast.walk(loop)
         if isinstance(n, ast.Call)
         and getattr(n.func, "id", "") == "_process_single_retry"),
        None,
    )
    assert call is not None, "`_process_single_retry` 호출을 찾지 못했다"
    assert any(kw.arg == "claim_token" for kw in call.keywords), (
        "`_process_single_retry(..., claim_token=...)` 전달이 사라졌다 — "
        "함수 안의 write-back 들이 만료 후 재조회 토큰으로 되돌아간다."
    )


@pytest.mark.asyncio
async def test_loop_does_not_release_a_row_reclaimed_mid_batch(make_session, monkeypatch):
    """🔴 **실제 루프**를 태워, 배치 중간에 재클레임된 행의 claim 을 해제하지 않는지 확인한다.

    🔴 위 교차세션 테스트는 시나리오를 손으로 재현할 뿐 `process_pending_retries` 를 호출하지
    않아, 서비스 코드를 되돌려도 GREEN 이었다(실측). 회귀를 잡으려면 루프를 실제로 타야 한다.

    시나리오: A 가 2행 배치를 클레임 → 1번째 행 처리가 commit(세션 만료) 하는 사이 B 가 2번째 행을
    stale 재클레임 → A 의 2번째 행 처리가 인프라 에러로 `_recover_and_release` 진입.
    스냅샷 토큰을 쓰면 CAS 가 막고, 만료 후 재조회를 쓰면 **B 의 행을 해제해 버린다**.
    Drives the real loop: without the snapshot, worker A releases the row B now owns.
    """
    import httpx

    setup = make_session()
    ids = _seed(setup, 2)
    setup.close()

    reclaimed_token: dict[str, str] = {}

    async def fake_process(db, row, now, counts, *, claim_token=None):
        if row.id == ids[0]:
            # 1번째 행 종결 — 이 commit 이 A 세션 전체를 만료시킨다.
            merge_retry_repo.mark_succeeded(db, row.id, now=now, expected_claim_token=claim_token)
            counts["succeeded"] += 1
            # 그 사이 B 가 2번째 행을 stale 재클레임 (별도 세션).
            worker_b = make_session()
            got = merge_retry_repo.claim_batch(
                worker_b, now=now + timedelta(seconds=400), limit=10, only_ids=[ids[1]],
            )
            reclaimed_token["b"] = got[0].claim_token
            worker_b.close()
            return
        raise httpx.HTTPError("boom")   # 2번째 행 — 인프라 에러 → _recover_and_release

    monkeypatch.setattr(merge_retry_service, "_process_single_retry", fake_process)

    worker_a = make_session()
    await merge_retry_service.process_pending_retries(worker_a, now=_NOW)
    worker_a.close()

    verify = make_session()
    row2 = verify.get(MergeRetryQueue, ids[1])
    token_after = row2.claim_token
    verify.close()

    assert token_after == reclaimed_token["b"], (
        "A 가 B 소유 행의 claim 을 해제했다 — 루프가 스냅샷이 아니라 만료 후 재조회를 쓰고 있다.\n"
        f"  기대(B 토큰)={reclaimed_token['b']!r}  실제={token_after!r}"
    )
