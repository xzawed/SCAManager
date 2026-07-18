"""run_analysis_pipeline ↔ analysis_attempts 배선 단위 테스트 (분석 소실 탐지).

Unit tests for the run_analysis_pipeline ↔ analysis_attempts wiring (lost-analysis detection).

핵심 계약 / Core contract
------------------------
파이프라인은 **비싼 작업(GitHub 파일 수집 + Claude 리뷰) 전에** attempt 행을 남기고, 정상
종료 경로에서만 지운다. SIGTERM/OOM/크래시 시 핸들러가 아예 돌지 않으므로 행이 자동으로
남는다 = 소실 신호. 따라서:
  - begin 은 `_collect_files` 보다 **먼저** 호출돼야 한다 (늦으면 보호 창이 사라짐)
  - 터미널 `except` 에서는 **절대 지우면 안 된다** (실패 증거 보존)

The pipeline writes the attempt row *before* the expensive work and deletes it only on normal
exits. On SIGTERM/OOM the handler never runs, so the row survives = the loss signal. Hence begin
must precede `_collect_files`, and the terminal `except` must never delete.
"""
# pylint: disable=redefined-outer-name
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.worker.pipeline import run_analysis_pipeline

# begin/finish patch 대상 — string-path 우선 (testing.md: 이중 import 회피)
# Patch targets — string-path preferred (testing.md: avoid the import-and-import-from pair)
_BEGIN = "src.worker.pipeline.analysis_attempt_repo.begin_attempt"
_FINISH = "src.worker.pipeline.analysis_attempt_repo.finish_attempt"

PUSH_DATA = {
    "repository": {"full_name": "owner/repo"},
    "after": "abc123def456",
    "head_commit": {"id": "abc123def456", "message": "feat: add awesome feature"},
    "commits": [{"id": "abc123def456", "message": "feat: add awesome feature"}],
}

PR_DATA = {
    "repository": {"full_name": "owner/repo"},
    "number": 7,
    "pull_request": {"head": {"sha": "def456abc123"}, "title": "feat: new PR title"},
}


@pytest.fixture
def pipeline_deps():
    """test_pipeline.py::mock_deps 와 동일 계열 fixture — 단, repo 는 **이미 존재**로 고정.

    Same family as test_pipeline.py::mock_deps, but the repo is pinned as *already existing*.
    🔴 test_pipeline.py 는 `find_by_full_name.side_effect = [None, mock_repo]` 를 쓰는데, 이때
    `_ensure_repo` 는 transient `Repository` (id=None) 를 반환한다 → `_review_repo_id` 가 None
    이라 repo_id 단언이 불가능하다. 여기서는 `return_value = mock_repo(id=1)` 로 고정해 repo_id
    가 실제로 전파되는지 검증한다.
    test_pipeline.py's side_effect list makes `_ensure_repo` return a *transient* Repository
    (id=None), so repo_id could not be asserted. Pinning return_value keeps id=1 observable.
    """
    with (
        patch("src.worker.pipeline.get_push_files") as mock_push,
        patch("src.worker.pipeline.get_pr_files") as mock_pr,
        patch("src.worker.pipeline.review_code", new_callable=AsyncMock) as mock_ai,
        patch("src.worker.pipeline.calculate_score") as mock_score,
        patch("src.notifier.telegram.send_analysis_result", new_callable=AsyncMock) as mock_telegram,
        patch("src.worker.pipeline.SessionLocal") as mock_session_cls,
        patch("src.worker.pipeline.settings") as mock_settings,
        # 정적분석 subprocess 실행 차단 — 테스트당 ~7s 절약
        # Block the static-analysis subprocesses — saves ~7s per test
        patch("src.worker.pipeline._run_static_analysis", new_callable=AsyncMock, return_value=[]),
        patch("src.worker.pipeline.repository_repo.find_by_full_name") as mock_find_repo,
        patch("src.worker.pipeline.analysis_repo.find_by_sha") as mock_find_analysis,
        patch("src.worker.pipeline.get_repo_config") as mock_get_config,
        patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate,
    ):
        from src.scorer.calculator import ScoreResult
        from src.github_client.diff import ChangedFile
        from src.analyzer.io.ai_review import AiReviewResult
        from src.config_manager.manager import RepoConfigData

        mock_settings.github_token = "ghp_test"
        mock_settings.telegram_bot_token = "123:ABC"
        mock_settings.telegram_chat_id = "-100123"
        mock_settings.anthropic_api_key = "sk-test"

        mock_push.return_value = [ChangedFile("app.py", "x = 1\n", "@@ +1 @@")]
        mock_pr.return_value = [ChangedFile("app.py", "x = 1\n", "@@ +1 @@")]
        mock_ai.return_value = AiReviewResult(
            commit_score=17, ai_score=16, test_score=10,
            summary="Good change", suggestions=[],
        )
        mock_score.return_value = ScoreResult(
            total=85, grade="B",
            code_quality_score=28, security_score=20,
            breakdown={
                "code_quality": 28, "security": 20,
                "commit_message": 17, "ai_review": 16, "test_coverage": 4,
            },
        )

        mock_repo = MagicMock(id=1)
        mock_repo.full_name = "owner/repo"
        # owner=None → owner_token 이 settings.github_token 으로 확정 (MagicMock 누수 방지)
        # owner=None pins owner_token to settings.github_token (avoids MagicMock leaking through)
        mock_repo.owner = None
        mock_find_repo.return_value = mock_repo
        mock_find_analysis.return_value = None
        mock_get_config.return_value = RepoConfigData(repo_full_name="owner/repo")

        mock_db = MagicMock()
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_session_cls.return_value = mock_db

        yield {
            "push": mock_push, "pr": mock_pr,
            "ai": mock_ai, "score": mock_score,
            "telegram": mock_telegram,
            "db": mock_db,
            "find_repo": mock_find_repo,
            "find_analysis": mock_find_analysis,
            "get_config": mock_get_config,
            "gate": mock_gate,
            "mock_repo": mock_repo,
        }


async def test_success_path_begins_and_finishes_attempt(pipeline_deps):
    """계약 6 — 정상 완료 시 begin + finish 가 모두 호출되고 식별자가 정확히 전파된다.

    Contract 6 — a successful run both begins and finishes the attempt, propagating the
    identifiers. finish 누락 시 정상 분석이 전부 orphan 으로 오탐돼 탐지 신호가 무용지물이 된다.
    A missing finish would report every successful analysis as an orphan, destroying the signal.
    """
    with patch(_BEGIN, return_value=True) as begin, patch(_FINISH) as finish:
        await run_analysis_pipeline("push", PUSH_DATA)

    # 실제 성공 경로를 탔음을 증명 — 조기 return 이었다면 알림이 나가지 않는다
    # Prove we really took the success path — an early return would skip notifications
    pipeline_deps["telegram"].assert_called_once()

    begin.assert_called_once()
    assert begin.call_args.kwargs["repo_id"] == 1
    assert begin.call_args.kwargs["commit_sha"] == "abc123def456"
    assert begin.call_args.kwargs["pr_number"] is None
    assert begin.call_args.kwargs["event"] == "push"

    finish.assert_called_once()
    assert finish.call_args.kwargs["repo_id"] == 1
    assert finish.call_args.kwargs["commit_sha"] == "abc123def456"


async def test_pr_event_begins_attempt_with_pr_number(pipeline_deps):
    """계약 6 — PR 이벤트는 pr_number + event='pull_request' 를 attempt 에 기록한다.

    Contract 6 — PR events record pr_number and event='pull_request' so an orphan row is
    actionable (운영자가 어느 PR 이 소실됐는지 즉시 식별 가능).
    """
    with patch(_BEGIN, return_value=True) as begin, patch(_FINISH) as finish:
        await run_analysis_pipeline("pull_request", PR_DATA)

    pipeline_deps["telegram"].assert_called_once()
    begin.assert_called_once()
    assert begin.call_args.kwargs["commit_sha"] == "def456abc123"
    assert begin.call_args.kwargs["pr_number"] == 7
    assert begin.call_args.kwargs["event"] == "pull_request"
    finish.assert_called_once()


async def test_begin_attempt_is_called_before_collect_files(pipeline_deps):
    """🔴 계약 7 — begin 이 `_collect_files` 보다 **먼저** 호출된다 (이 수정의 핵심).

    🔴 Contract 7 — begin must precede `_collect_files` (the whole point of the fix).
    `_collect_files` 는 GitHub API 왕복이고 그 뒤 Claude 리뷰가 60s+ 걸린다. begin 이 그 뒤로
    가면 보호하려던 창(수 분) 이 그대로 노출된 채 남는다 — 배선은 됐는데 결함은 그대로인
    상태를 이 순서 단언이 차단한다.
    `_collect_files` is a GitHub round-trip followed by a 60s+ Claude review. If begin lands
    after it, the multi-minute window this fix exists to cover stays fully exposed — wired but
    still broken. This ordering assertion is what blocks that.
    """
    order: list[str] = []

    def _record_begin(_db, **_kwargs):
        order.append("begin_attempt")
        return True

    def _record_collect(*_args, **_kwargs):
        from src.github_client.diff import ChangedFile
        order.append("_collect_files")
        return [ChangedFile("app.py", "x = 1\n", "@@ +1 @@")]

    with patch(_BEGIN, side_effect=_record_begin), \
         patch(_FINISH), \
         patch("src.worker.pipeline._collect_files", side_effect=_record_collect):
        await run_analysis_pipeline("push", PUSH_DATA)

    # 실제 실행 순서를 기록해 단언 — 두 호출이 모두 일어났고 begin 이 앞선다
    # Assert on the recorded execution order — both ran, and begin came first
    assert order == ["begin_attempt", "_collect_files"]


async def test_begin_attempt_is_called_before_ai_review(pipeline_deps):
    """계약 7 보강 — begin 이 Claude 리뷰(가장 긴 구간) 보다 먼저 호출된다.

    Contract 7 (reinforcement) — begin precedes the Claude review, the longest window.
    `_collect_files` 를 patch 하지 않는 경로로 순서를 재검증해 patch 배치에 의존하지 않음을 확인.
    Re-checks ordering on a path that does not patch `_collect_files`, so the guarantee does
    not depend on that particular seam being mocked.
    """
    order: list[str] = []

    def _record_begin(_db, **_kwargs):
        order.append("begin_attempt")
        return True

    async def _record_review(*_args, **_kwargs):
        from src.analyzer.io.ai_review import AiReviewResult
        order.append("review_code")
        return AiReviewResult(
            commit_score=17, ai_score=16, test_score=10, summary="ok", suggestions=[],
        )

    pipeline_deps["ai"].side_effect = _record_review

    with patch(_BEGIN, side_effect=_record_begin), patch(_FINISH):
        await run_analysis_pipeline("push", PUSH_DATA)

    assert order == ["begin_attempt", "review_code"]


async def test_pipeline_failure_preserves_attempt_row(pipeline_deps):
    """🔴 계약 8 — 파이프라인 도중 예외 시 finish 미호출 (행 = 소실 증거로 보존).

    🔴 Contract 8 — on a mid-pipeline exception finish must NOT run; the surviving row is the
    failure evidence. 터미널 `except Exception` 이 예외를 삼키므로 (파이프라인이 조용히 정상
    반환) 이 경로에서 finish 를 부르면 실패가 성공과 구별 불가능해진다 — 정확히 이 수정이
    없애려던 상태다.
    The terminal `except Exception` swallows the error and the pipeline returns quietly, so
    deleting the row here would make failure indistinguishable from success — exactly the state
    this fix removes.
    """
    pipeline_deps["ai"].side_effect = RuntimeError("claude exploded mid-review")

    with patch(_BEGIN, return_value=True) as begin, patch(_FINISH) as finish:
        # 터미널 except 가 삼키므로 예외는 전파되지 않는다
        # The terminal except swallows it, so nothing propagates
        await run_analysis_pipeline("push", PUSH_DATA)

    # 파이프라인이 실제로 중단됐음을 증명 (알림 미발송) — 그렇지 않으면 아래 단언이 무의미
    # Prove the pipeline actually aborted (no notification) — otherwise the assertion below
    # would be vacuous
    pipeline_deps["telegram"].assert_not_called()
    # begin 은 호출됐다 = 보존할 행이 실제로 존재한다 (finish 를 아예 배선 안 한
    # 구현이 이 테스트를 공짜로 통과하는 spurious pass 차단 — 계약 6 과 페어)
    # begin ran = there is a real row to preserve. This blocks the spurious pass where an
    # implementation that never calls finish at all would trivially satisfy the assertion
    # below (paired with contract 6).
    begin.assert_called_once()
    finish.assert_not_called()


async def test_gate_failure_still_finishes_attempt_because_analysis_persisted(pipeline_deps):
    """🔴 gate 예외는 흔적을 **보존하지 않는다** — Analysis 는 이미 저장됐으므로 소실이 아니다.

    이 테이블의 계약은 "**분석이 증발했는가**"이지 "모든 단계가 성공했는가"가 아니다.
    `_save_and_gate` 는 `save_new`(영속화) **후에** gate 를 돌리고 gate 예외를 의도적으로
    내부에서 삼킨다(`pipeline.py` "Gate check unexpected error"). 따라서 gate 가 터져도
    Analysis 행은 DB 에 남아 있고 — 분석 결과는 대시보드·알림에 그대로 보인다 — 소실이 아니다.
    여기서 행을 보존하면 **정상 분석이 orphan 으로 오탐**돼 소실 신호가 노이즈에 묻힌다.

    (gate 부수효과 자체가 유실되는 문제는 별개 관심사 — Grok PIPE-P1-4 "successful analysis +
    failed gate is never re-driven", 검증에서 P2 로 하향. 이 테이블이 다룰 영역이 아니다.)

    🔴 A gate exception does NOT preserve the breadcrumb — the Analysis is already persisted, so
    nothing was lost. This table's contract is "did the analysis vanish?", not "did every stage
    succeed?". `_save_and_gate` runs the gate *after* `save_new` and deliberately swallows gate
    exceptions, so the Analysis row survives and the result is visible in the dashboard/notifications.
    Preserving the row here would misreport a healthy analysis as an orphan and bury the real signal.
    (The lost gate side-effect is a separate concern — Grok PIPE-P1-4, downgraded to P2.)
    """
    pipeline_deps["gate"].side_effect = RuntimeError("gate exploded")

    with patch(_BEGIN, return_value=True) as begin, patch(_FINISH) as finish:
        await run_analysis_pipeline("pull_request", PR_DATA)

    begin.assert_called_once()
    # 소실 아님 → 흔적 제거. 이 단언이 뒤집히면 정상 분석이 orphan 으로 오탐된다.
    # Not a loss → clear the breadcrumb. Flipping this assertion would misreport healthy analyses.
    finish.assert_called_once()


async def test_notify_failure_after_persist_finishes_attempt(pipeline_deps):
    """🔴 notify 단계 실패는 오탐 orphan 을 남기지 않는다 — Analysis 는 이미 영속화됨 (준비도 감사 #21).

    `_save_and_gate` 가 Analysis 를 save_new 로 영속화한 **뒤** notify 단계
    (`build_notification_tasks`/`_send_notifications`)가 예외를 던지면, 터미널 `except` 가 이를
    삼키지만 흔적 행은 남아 **정상 분석이 orphan 으로 오탐**됐다(finish 가 notify 뒤에 있었으므로).
    finish 를 영속화 직후·notify 앞으로 옮겨 봉인 — gate 실패(위 테스트)와 동일한 "영속화 후 실패는
    소실 아님" 원칙의 notify 판.
    🔴 A notify-stage failure must NOT leave a false orphan — the Analysis is already persisted.
    """
    with patch(_BEGIN, return_value=True) as begin, patch(_FINISH) as finish, \
         patch("src.worker.pipeline.build_notification_tasks",
               side_effect=RuntimeError("notify boom")):
        # 터미널 except 가 삼키므로 예외는 전파되지 않는다
        await run_analysis_pipeline("push", PUSH_DATA)

    begin.assert_called_once()
    # Analysis 영속화됨 → 소실 아님 → finish 호출 (오탐 orphan 방지)
    finish.assert_called_once()


async def test_no_changed_files_finishes_attempt(pipeline_deps):
    """계약 9 — 변경 파일 0 은 정상 종료 → finish 호출 (orphan 오탐 방지).

    Contract 9 — zero changed files is a *normal* exit, so finish must run. 미호출 시 문서-only
    push 등이 매번 orphan 으로 쌓여 탐지 신호가 노이즈에 묻힌다.
    Otherwise docs-only pushes pile up as orphans and drown the signal in noise.
    """
    pipeline_deps["push"].return_value = []

    with patch(_BEGIN, return_value=True) as begin, patch(_FINISH) as finish:
        await run_analysis_pipeline("push", PUSH_DATA)

    # 실제로 "파일 0" 조기 종료 경로를 탔는지 확인 (AI 리뷰 미진입)
    # Confirm we really took the zero-files early exit (no AI review)
    pipeline_deps["ai"].assert_not_called()
    begin.assert_called_once()
    finish.assert_called_once()
    assert finish.call_args.kwargs["repo_id"] == 1
    assert finish.call_args.kwargs["commit_sha"] == "abc123def456"


async def test_race_recovery_finishes_attempt(pipeline_deps):
    """계약 9 — `_save_and_gate` 가 result_dict=None(race-recovery) 을 반환해도 정상 종료 →
    finish 호출.

    Contract 9 — the race-recovery early return (result_dict is None) is a normal exit and must
    finish the attempt. 동시 webhook 이 이미 저장·알림을 마친 상태라 소실이 아니다.
    A concurrent webhook already saved and notified — nothing was lost.
    """
    # `_save_and_gate` 내부의 find_by_sha 는 기존 Analysis 를 발견 → race-recovery 분기.
    # `_ensure_repo` 의 find_by_sha(1회차) 는 None 이어야 파이프라인이 진입하므로 side_effect
    # 로 호출 순서를 분리한다.
    # find_by_sha returns None first (so _ensure_repo lets us in) then an existing Analysis
    # inside _save_and_gate (triggering race-recovery).
    existing = MagicMock(id=99)
    existing.pr_number = 7
    existing.result = {"score": 80}
    pipeline_deps["find_analysis"].side_effect = [None, existing]

    with patch(_BEGIN, return_value=True) as begin, patch(_FINISH) as finish:
        await run_analysis_pipeline("pull_request", PR_DATA)

    # race-recovery 경로 확인 — 알림 미발송(중복 방지)이지만 소실은 아님
    # Confirm the race-recovery path — no notification (dedup), but nothing was lost
    pipeline_deps["telegram"].assert_not_called()
    begin.assert_called_once()
    finish.assert_called_once()


async def test_duplicate_sha_never_begins_attempt(pipeline_deps):
    """계약 10 — `_ensure_repo` 가 None(SHA 중복) 이면 begin 미호출.

    Contract 10 — when `_ensure_repo` returns None (SHA already analyzed) no attempt is begun.
    비싼 작업에 진입하지 않으므로 보호할 창이 없다. 여기서 begin 하면 기존 Analysis 가 있는
    SHA 에 대해 orphan 행이 생겨 탐지 리포트가 오염된다.
    No expensive work is entered, so there is no window to protect. Beginning here would create
    an orphan row for an already-analyzed SHA and pollute the detection report.
    """
    pipeline_deps["find_analysis"].return_value = MagicMock(id=99)

    with patch(_BEGIN) as begin, patch(_FINISH) as finish:
        await run_analysis_pipeline("push", PUSH_DATA)

    # 실제로 조기 반환했는지 확인 — 파일 수집조차 하지 않는다
    # Confirm the early return really happened — no file collection at all
    pipeline_deps["push"].assert_not_called()
    begin.assert_not_called()
    finish.assert_not_called()


async def test_blank_sha_never_begins_attempt(pipeline_deps):
    """계약 10 확장 — 브랜치 삭제 push(zero-SHA) 는 `_ensure_repo` 이전에 종료 → begin 미호출.

    Contract 10 (extension) — a branch-delete push (zero-SHA) exits before `_ensure_repo`, so
    no attempt is begun and no orphan is created for a non-existent commit.
    """
    delete_push = {
        "repository": {"full_name": "owner/repo"},
        "after": "0" * 40,
        "head_commit": None,
        "commits": [],
    }

    with patch(_BEGIN) as begin, patch(_FINISH) as finish:
        await run_analysis_pipeline("push", delete_push)

    begin.assert_not_called()
    finish.assert_not_called()


async def test_lost_begin_race_still_runs_pipeline(pipeline_deps):
    """begin 이 False(동시 웹훅 패배) 여도 파이프라인은 계속 진행돼야 한다.

    A False begin (a concurrent webhook won the race) must NOT abort the pipeline. attempt 는
    관측용 tombstone 일 뿐 dedup 게이트가 아니다 — 기존 dedup 불변식은 `Analysis.find_by_sha`
    (`_ensure_repo`/`_save_and_gate`) 가 단독 담당한다(#794·#780 first-writer-wins 무손상).
    The attempt table is an observability tombstone, not a dedup gate — dedup stays solely with
    `Analysis.find_by_sha`, leaving the #794/#780 first-writer-wins invariants untouched.
    """
    with patch(_BEGIN, return_value=False), patch(_FINISH) as finish:
        await run_analysis_pipeline("push", PUSH_DATA)

    # 분석이 정상 수행됨 — begin False 가 조기 반환을 유발하지 않는다
    # The analysis still runs — a False begin must not cause an early return
    pipeline_deps["ai"].assert_called_once()
    pipeline_deps["telegram"].assert_called_once()
    finish.assert_called_once()


async def test_begin_attempt_failure_does_not_abort_pipeline(pipeline_deps):
    """🔴 P2#18 — begin(흔적 기록)이 DB 오류로 실패해도 정상 분석은 계속돼야 한다.

    소실 탐지 흔적은 best-effort observability — 그 write 실패(IntegrityError 외 DB 오류)가
    정상 분석을 중단시키면 **관측용 흔적이 관측 대상을 죽이는 자기모순**이다. `_begin_attempt`
    가 `_finish_attempt` 와 대칭으로 예외를 삼켜(로그만) 파이프라인을 계속 진행한다.
    A breadcrumb-write failure must not abort a healthy analysis (the observability aid killing the
    thing it observes). Symmetric to `_finish_attempt`'s swallow-and-log.

    수정 전: begin 예외가 터미널 `except` 로 전파돼 조용히 abort → 알림·finish 미발생.
    Before the fix, the exception propagated to the terminal `except` and the pipeline aborted
    silently (no notification, no finish).
    """
    from sqlalchemy.exc import OperationalError  # pylint: disable=import-outside-toplevel

    boom = OperationalError("INSERT analysis_attempts", {}, Exception("db connection lost"))
    with patch(_BEGIN, side_effect=boom) as begin, patch(_FINISH) as finish:
        await run_analysis_pipeline("push", PUSH_DATA)

    begin.assert_called_once()  # 흔적 기록이 실제로 시도됐다 (spurious pass 차단)
    # 파이프라인이 begin 실패를 넘어 계속 진행 = 분석·알림·정상 종료 도달
    # The pipeline proceeds past the begin failure — analysis, notification, and normal finish run.
    pipeline_deps["ai"].assert_called_once()
    pipeline_deps["telegram"].assert_called_once()
    finish.assert_called_once()
