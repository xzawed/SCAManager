"""분석된 SHA(Analysis.commit_sha) 를 auto-merge 전 구간에 관통시키는 결속 가드.
Guards that bind the analyzed SHA (Analysis.commit_sha) through the whole auto-merge path.

🔴 결함 (확정 P1): auto-merge 가 "분석이 끝난 시점의 PR head" 를 새로 조회해 그 SHA 로 머지한다.
커밋 A 분석 중(정적 60s + AI 리뷰) 커밋 B 가 push 되면, A 의 점수로 게이트를 통과한 뒤
head 조회가 B 를 반환해 **분석된 적 없는 B 가 A 의 점수로 머지**된다.
semi-auto(Telegram) 경로는 레이스조차 불필요 — analysis 행을 이미 로드해 commit_sha 를 쥐고도
버리고, 승인 버튼 HMAC 은 만료가 없어 몇 시간 뒤 눌러도 그때의 head 를 머지한다.

🔴 Defect (confirmed P1): auto-merge re-queries the PR head *after* analysis finishes and merges
that SHA. If commit B lands while commit A is being analyzed, A's score passes the gate but the
head lookup returns B — merging never-analyzed code under A's score. The semi-auto (Telegram) path
needs no race at all: it already holds analysis.commit_sha and discards it, and the approval
button's HMAC never expires.

수정 계약 / Fix contract:
  analyzed SHA 를 게이트 전 구간에 관통시키고 drift(head != analyzed) 시 fail-closed.
  Thread the analyzed SHA through the gate and fail closed on drift (head != analyzed).

하위 호환 / Backward compatibility:
  analyzed_sha=None(미전달) 이면 기존 동작과 완전히 동일해야 한다.
  When analyzed_sha is None (not passed), behavior must be identical to before.
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from src.config_manager.manager import RepoConfigData
from src.gate.actions import GateContext
from src.gate.actions.auto_merge import AutoMergeAction
from src.gate.engine import _run_auto_merge, _run_auto_merge_legacy, run_gate_check
from src.gate.native_automerge import MergeOutcome, PATH_REST_FALLBACK
from src.repositories.merge_retry_repo import EnqueueResult


# ---------------------------------------------------------------------------
# 상수 / Constants
# ---------------------------------------------------------------------------

# 실제로 분석된 커밋 A / The commit that was actually analyzed (commit A)
_ANALYZED_SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
# 분석 도중 push 된 커밋 B — 분석된 적 없음 / Commit B pushed mid-analysis — never analyzed
_DRIFTED_HEAD_SHA = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


# ---------------------------------------------------------------------------
# 공용 픽스처 헬퍼 / Shared fixture helpers
# (tests/unit/gate/test_auto_merge_enqueue.py 의 기존 패턴을 그대로 따른다)
# (mirrors the existing pattern in tests/unit/gate/test_auto_merge_enqueue.py)
# ---------------------------------------------------------------------------

def _config(**kwargs) -> RepoConfigData:
    """테스트용 RepoConfigData 생성 / Create a RepoConfigData instance for testing."""
    defaults = dict(
        repo_full_name="owner/repo",
        pr_review_comment=False,
        approve_mode="disabled",
        approve_threshold=75,
        reject_threshold=50,
        auto_merge=True,
        merge_threshold=75,
        notify_chat_id="-100999",
        auto_merge_issue_on_failure=False,
    )
    defaults.update(kwargs)
    return RepoConfigData(**defaults)


def _mock_session_local(mock_db: MagicMock):
    """SessionLocal 컨텍스트 매니저 mock 생성.
    Create a mock context manager for SessionLocal that yields mock_db.

    P0-H: _run_auto_merge 가 독립 SessionLocal() 을 열므로 직접 호출 테스트는 patch 필요.
    P0-H: _run_auto_merge opens its own SessionLocal, so direct-call tests must patch it.
    """
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=mock_db)
    cm.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=cm)


def _make_enqueue_result(*, is_first_deferral: bool) -> EnqueueResult:
    """EnqueueResult 모의 객체 생성 / Create a mock EnqueueResult."""
    row = MagicMock()
    row.id = 1
    return EnqueueResult(row=row, is_first_deferral=is_first_deferral)


# ---------------------------------------------------------------------------
# 계약 1 + 9: drift → 머지 금지 + 큐 등록 금지 (fail-closed)
# Contract 1 + 9: drift → no merge, no enqueue (fail-closed)
# ---------------------------------------------------------------------------

async def test_retry_path_drift_blocks_merge_entirely():
    """🔴 핵심 회귀 가드: head(B) != analyzed(A) → native 머지 호출 자체가 없어야 한다.

    분석된 적 없는 커밋 B 가 커밋 A 의 점수로 머지되는 것이 본 결함의 본질.
    Core regression guard: when head (B) != analyzed (A), the native merge must never be called —
    merging never-analyzed commit B under commit A's score is the essence of this defect.
    """
    mock_db = MagicMock()
    config = _config()

    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine.SessionLocal", _mock_session_local(mock_db)), \
         patch("src.gate.engine.native_enable_with_path", new_callable=AsyncMock) as mock_merge, \
         patch("src.gate.engine.get_pr_mergeable_state", new_callable=AsyncMock) as mock_state, \
         patch("src.gate.engine.get_pr_base_ref", new_callable=AsyncMock, return_value="main"), \
         patch("src.gate.engine.merge_retry_repo"), \
         patch("src.gate.engine.log_merge_attempt"):

        mock_settings.merge_retry_enabled = True
        mock_settings.telegram_chat_id = "-100123"
        # 분석 도중 커밋 B 가 push 됨 → head 조회가 B 반환
        # Commit B landed mid-analysis → the head lookup returns B
        mock_state.return_value = ("clean", _DRIFTED_HEAD_SHA)
        # 가드가 없으면 native 가 B 로 머지에 성공한다 — 정확히 이 사고를 재현.
        # Without the guard, native succeeds in merging B — exactly the incident being reproduced.
        mock_merge.return_value = MergeOutcome(
            ok=True, reason=None, head_sha=_DRIFTED_HEAD_SHA, path=PATH_REST_FALLBACK,
        )

        await _run_auto_merge(
            config, "ghp_token", "owner/repo", 42, 95,
            analysis_id=1,
            analyzed_sha=_ANALYZED_SHA,
        )

        # drift → 머지 시도 자체가 없어야 함 / drift → merge must not even be attempted
        mock_merge.assert_not_awaited()


async def test_retry_path_drift_does_not_enqueue_retry():
    """🔴 계약 9: drift 시 재시도 큐 등록도 없어야 한다.

    큐에 잘못된(분석 안 된) SHA 가 들어가면 나중에 cron 재시도가 그 SHA 를 머지해버린다 —
    가드를 우회하는 지연 폭탄. 계약 1과 별도로 명시 단언.
    Contract 9: drift must not enqueue either. A wrong (unanalyzed) SHA in the queue would be
    merged later by the retry cron — a delayed bypass of the guard. Asserted separately from #1.
    """
    mock_db = MagicMock()
    config = _config()

    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine.SessionLocal", _mock_session_local(mock_db)), \
         patch("src.gate.engine.native_enable_with_path", new_callable=AsyncMock) as mock_merge, \
         patch("src.gate.engine.get_pr_mergeable_state", new_callable=AsyncMock) as mock_state, \
         patch("src.gate.engine.get_pr_base_ref", new_callable=AsyncMock, return_value="main"), \
         patch("src.gate.engine.get_required_check_contexts", new_callable=AsyncMock) as mock_required, \
         patch("src.gate.engine.get_ci_status", new_callable=AsyncMock) as mock_ci, \
         patch("src.gate.engine.merge_retry_repo") as mock_repo, \
         patch("src.gate.engine._notify_merge_deferred", new_callable=AsyncMock), \
         patch("src.gate.engine.log_merge_attempt"):

        mock_settings.merge_retry_enabled = True
        mock_settings.merge_retry_max_attempts = 30
        mock_settings.merge_retry_initial_backoff_seconds = 60
        mock_settings.telegram_chat_id = "-100123"
        mock_state.return_value = ("clean", _DRIFTED_HEAD_SHA)
        # 🔴 가드가 없으면 이 시나리오는 실제로 enqueue 에 도달한다 (unstable_ci + CI running →
        # retriable → 큐 등록). 즉 본 테스트는 가드 부재를 실제로 검출한다 — mock 기본값
        # (truthy ok) 로 조기 return 되어 spurious-pass 하지 않도록 실패 outcome 을 명시.
        # Without the guard this scenario genuinely reaches enqueue (unstable_ci + CI running →
        # retriable). An explicit failing outcome prevents a spurious pass via the default mock's
        # truthy `ok` short-circuiting before the enqueue path.
        mock_merge.return_value = MergeOutcome(
            ok=False, reason="unstable_ci: state=unstable",
            head_sha=_DRIFTED_HEAD_SHA, path=PATH_REST_FALLBACK,
        )
        mock_required.return_value = {"ci/test"}
        mock_ci.return_value = "running"
        mock_repo.enqueue_or_bump.return_value = _make_enqueue_result(is_first_deferral=True)

        await _run_auto_merge(
            config, "ghp_token", "owner/repo", 42, 95,
            analysis_id=1,
            analyzed_sha=_ANALYZED_SHA,
        )

        mock_repo.enqueue_or_bump.assert_not_called()


# ---------------------------------------------------------------------------
# 계약 2: 일치 → analyzed SHA 로 결속
# Contract 2: match → bind the merge to the analyzed SHA
# ---------------------------------------------------------------------------

async def test_retry_path_binds_expected_sha_to_analyzed_sha_when_head_matches():
    """head == analyzed → native 호출이 expected_sha=analyzed_sha 로 결속되어야 한다.

    값 단언(mock 호출 사실이 아니라 실제 전달된 SHA) — GitHub 이 SHA 원자성을 검증한다.
    Value assertion (the actual SHA passed, not merely that the mock was called) — GitHub
    enforces SHA atomicity from this parameter.
    """
    mock_db = MagicMock()
    config = _config()

    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine.SessionLocal", _mock_session_local(mock_db)), \
         patch("src.gate.engine.native_enable_with_path", new_callable=AsyncMock) as mock_merge, \
         patch("src.gate.engine.get_pr_mergeable_state", new_callable=AsyncMock) as mock_state, \
         patch("src.gate.engine.get_pr_base_ref", new_callable=AsyncMock, return_value="main"), \
         patch("src.gate.engine.merge_retry_repo"), \
         patch("src.gate.engine.log_merge_attempt"):

        mock_settings.merge_retry_enabled = True
        mock_settings.telegram_chat_id = "-100123"
        # head == analyzed — 레이스 없음 / head == analyzed — no race
        mock_state.return_value = ("clean", _ANALYZED_SHA)
        mock_merge.return_value = MergeOutcome(
            ok=True, reason=None, head_sha=_ANALYZED_SHA, path=PATH_REST_FALLBACK,
        )

        await _run_auto_merge(
            config, "ghp_token", "owner/repo", 42, 95,
            analysis_id=1,
            analyzed_sha=_ANALYZED_SHA,
        )

        mock_merge.assert_awaited_once()
        assert mock_merge.await_args.kwargs["expected_sha"] == _ANALYZED_SHA


# ---------------------------------------------------------------------------
# 계약 3: head 조회 실패 → 비교 불가지만 analyzed SHA 로 결속
# Contract 3: head lookup fails → cannot compare, but still bind to the analyzed SHA
# ---------------------------------------------------------------------------

async def test_retry_path_head_lookup_failure_still_binds_analyzed_sha():
    """head 조회 실패(head_sha="") + analyzed_sha 설정 → drift 가드 통과 + expected_sha=analyzed_sha.

    비교는 불가능하지만 SHA 를 넘기면 GitHub 가 원자성을 검증해준다 — 조회 실패가
    "아무 SHA 나 머지" 로 퇴화하면 안 된다.
    The comparison is impossible, but passing the SHA lets GitHub enforce atomicity — a failed
    lookup must not degrade into "merge whatever head is now".
    """
    mock_db = MagicMock()
    config = _config()

    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine.SessionLocal", _mock_session_local(mock_db)), \
         patch("src.gate.engine.native_enable_with_path", new_callable=AsyncMock) as mock_merge, \
         patch("src.gate.engine.get_pr_mergeable_state", new_callable=AsyncMock) as mock_state, \
         patch("src.gate.engine.get_pr_base_ref", new_callable=AsyncMock, return_value="main"), \
         patch("src.gate.engine.merge_retry_repo"), \
         patch("src.gate.engine.log_merge_attempt"):

        mock_settings.merge_retry_enabled = True
        mock_settings.telegram_chat_id = "-100123"
        # get_pr_mergeable_state 실패 → engine 내부에서 head_sha = ""
        # get_pr_mergeable_state fails → engine sets head_sha = "" internally
        mock_state.side_effect = httpx.ConnectError("boom")
        mock_merge.return_value = MergeOutcome(
            ok=True, reason=None, head_sha=_ANALYZED_SHA, path=PATH_REST_FALLBACK,
        )

        await _run_auto_merge(
            config, "ghp_token", "owner/repo", 42, 95,
            analysis_id=1,
            analyzed_sha=_ANALYZED_SHA,
        )

        # 조회 실패는 drift 가 아니다 — 머지는 진행하되 analyzed SHA 로 결속
        # A failed lookup is not drift — proceed, but bound to the analyzed SHA
        mock_merge.assert_awaited_once()
        assert mock_merge.await_args.kwargs["expected_sha"] == _ANALYZED_SHA


# ---------------------------------------------------------------------------
# 계약 4: 하위 호환 — analyzed_sha 미전달 시 기존 동작 유지
# Contract 4: backward compatibility — unchanged behavior when analyzed_sha is not passed
# ---------------------------------------------------------------------------

async def test_retry_path_without_analyzed_sha_keeps_head_sha_behavior():
    """analyzed_sha=None → 기존대로 expected_sha=head_sha (하위 호환).

    기존 호출부/테스트가 깨지면 안 된다 — 가드는 analyzed_sha 가 있을 때만 작동.
    Existing callers/tests must not break — the guard only engages when analyzed_sha is given.
    """
    mock_db = MagicMock()
    config = _config()

    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine.SessionLocal", _mock_session_local(mock_db)), \
         patch("src.gate.engine.native_enable_with_path", new_callable=AsyncMock) as mock_merge, \
         patch("src.gate.engine.get_pr_mergeable_state", new_callable=AsyncMock) as mock_state, \
         patch("src.gate.engine.get_pr_base_ref", new_callable=AsyncMock, return_value="main"), \
         patch("src.gate.engine.merge_retry_repo"), \
         patch("src.gate.engine.log_merge_attempt"):

        mock_settings.merge_retry_enabled = True
        mock_settings.telegram_chat_id = "-100123"
        mock_state.return_value = ("clean", _DRIFTED_HEAD_SHA)
        mock_merge.return_value = MergeOutcome(
            ok=True, reason=None, head_sha=_DRIFTED_HEAD_SHA, path=PATH_REST_FALLBACK,
        )

        # analyzed_sha 미전달 — 기존 호출 형태 / analyzed_sha omitted — legacy call shape
        await _run_auto_merge(
            config, "ghp_token", "owner/repo", 42, 95,
            analysis_id=1,
        )

        # 가드 미작동 → 기존대로 head_sha 로 머지 / guard inactive → merge with head_sha as before
        mock_merge.assert_awaited_once()
        assert mock_merge.await_args.kwargs["expected_sha"] == _DRIFTED_HEAD_SHA


# ---------------------------------------------------------------------------
# 계약 5: legacy 경로 (merge_retry_enabled=False) 도 analyzed SHA 로 결속
# Contract 5: the legacy path (merge_retry_enabled=False) must bind the analyzed SHA too
# ---------------------------------------------------------------------------

async def test_legacy_path_binds_expected_sha_to_analyzed_sha():
    """🔴 legacy 경로는 expected_sha 를 아예 전달하지 않아 native 가 스스로 head 를 재조회한다
    (native_automerge.py:145 `head_sha = expected_sha or ""` → 미전달 시 자체 조회) = 동일 결함.
    → analyzed_sha 전달 시 expected_sha=analyzed_sha 로 결속되어야 한다.

    The legacy path passes no expected_sha at all, so native re-queries the head itself
    (native_automerge.py:145) — the same defect. With analyzed_sha it must bind expected_sha.
    """
    mock_db = MagicMock()
    config = _config()

    with patch("src.gate.engine.native_enable_with_path", new_callable=AsyncMock) as mock_merge, \
         patch("src.gate.engine.log_merge_attempt"):

        mock_merge.return_value = MergeOutcome(
            ok=True, reason=None, head_sha=_ANALYZED_SHA, path=PATH_REST_FALLBACK,
        )

        await _run_auto_merge_legacy(
            config, "ghp_token", "owner/repo", 42, 95,
            analysis_id=1, db=mock_db,
            analyzed_sha=_ANALYZED_SHA,
        )

        mock_merge.assert_awaited_once()
        assert mock_merge.await_args.kwargs["expected_sha"] == _ANALYZED_SHA


async def test_run_auto_merge_forwards_analyzed_sha_to_legacy_path():
    """merge_retry_enabled=False → _run_auto_merge 가 legacy 에 analyzed_sha 를 전달해야 한다.
    merge_retry_enabled=False → _run_auto_merge must forward analyzed_sha to the legacy path.
    """
    mock_db = MagicMock()
    config = _config()

    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine.SessionLocal", _mock_session_local(mock_db)), \
         patch("src.gate.engine._run_auto_merge_legacy", new_callable=AsyncMock) as mock_legacy:

        mock_settings.merge_retry_enabled = False

        await _run_auto_merge(
            config, "ghp_token", "owner/repo", 42, 95,
            analysis_id=1,
            analyzed_sha=_ANALYZED_SHA,
        )

        mock_legacy.assert_awaited_once()
        assert mock_legacy.await_args.kwargs["analyzed_sha"] == _ANALYZED_SHA


# ---------------------------------------------------------------------------
# 계약 6: AutoMergeAction 배선 — ctx.commit_sha → _run_auto_merge(analyzed_sha=)
# Contract 6: AutoMergeAction wiring — ctx.commit_sha → _run_auto_merge(analyzed_sha=)
# ---------------------------------------------------------------------------

async def test_auto_merge_action_forwards_ctx_commit_sha_as_analyzed_sha():
    """AutoMergeAction 이 ctx.commit_sha 를 engine._run_auto_merge 의 analyzed_sha 로 전달한다.
    AutoMergeAction forwards ctx.commit_sha as engine._run_auto_merge's analyzed_sha.
    """
    config = _config()
    ctx = GateContext(
        repo_name="owner/repo",
        pr_number=42,
        analysis_id=1,
        result={"score": 95},
        github_token="ghp_token",
        config=config,
        score=95,
        commit_sha=_ANALYZED_SHA,
    )

    with patch("src.gate.engine._run_auto_merge", new_callable=AsyncMock) as mock_am:
        await AutoMergeAction().execute(ctx)

        mock_am.assert_awaited_once()
        assert mock_am.await_args.kwargs["analyzed_sha"] == _ANALYZED_SHA


async def test_gate_context_commit_sha_defaults_to_none():
    """하위 호환: commit_sha 미전달 GateContext 생성이 여전히 가능하고 기본값은 None.
    Backward compatibility: GateContext can still be built without commit_sha; it defaults to None.
    """
    ctx = GateContext(
        repo_name="owner/repo",
        pr_number=42,
        analysis_id=1,
        result={"score": 95},
        github_token="ghp_token",
        config=_config(),
        score=95,
    )
    assert ctx.commit_sha is None


# ---------------------------------------------------------------------------
# 계약 7: run_gate_check 배선 — commit_sha= 인자 → GateContext.commit_sha
# Contract 7: run_gate_check wiring — commit_sha= arg → GateContext.commit_sha
# ---------------------------------------------------------------------------

async def test_run_gate_check_passes_commit_sha_into_gate_context():
    """run_gate_check(commit_sha=...) 가 GateContext.commit_sha 로 들어가야 한다.
    run_gate_check(commit_sha=...) must land in GateContext.commit_sha.
    """
    mock_db = MagicMock()
    config = _config(auto_merge=True, pr_review_comment=False, approve_mode="disabled")

    with patch("src.gate.engine.get_repo_config", return_value=config), \
         patch("src.gate.actions.auto_merge.AutoMergeAction.execute",
               new_callable=AsyncMock) as mock_execute:
        await run_gate_check(
            repo_name="owner/repo",
            pr_number=42,
            analysis_id=1,
            result={"score": 95, "grade": "A"},
            github_token="ghp_token",
            db=mock_db,
            commit_sha=_ANALYZED_SHA,
        )

        mock_execute.assert_awaited_once()
        ctx = mock_execute.await_args.args[0]
        assert ctx.commit_sha == _ANALYZED_SHA


async def test_run_gate_check_without_commit_sha_yields_none_context():
    """하위 호환: commit_sha 미전달 시 GateContext.commit_sha 는 None (기존 호출부 보호).
    Backward compatibility: omitting commit_sha yields GateContext.commit_sha=None.
    """
    mock_db = MagicMock()
    config = _config(auto_merge=True, pr_review_comment=False, approve_mode="disabled")

    with patch("src.gate.engine.get_repo_config", return_value=config), \
         patch("src.gate.actions.auto_merge.AutoMergeAction.execute",
               new_callable=AsyncMock) as mock_execute:
        await run_gate_check(
            repo_name="owner/repo",
            pr_number=42,
            analysis_id=1,
            result={"score": 95, "grade": "A"},
            github_token="ghp_token",
            db=mock_db,
        )

        mock_execute.assert_awaited_once()
        assert mock_execute.await_args.args[0].commit_sha is None
