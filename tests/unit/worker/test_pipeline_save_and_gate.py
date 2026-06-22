import logging
from unittest.mock import MagicMock, patch, AsyncMock
from src.worker import pipeline as pipeline_mod
from src.worker.pipeline import _AnalysisSaveParams


async def test_save_and_gate_skips_on_concurrent_duplicate(caplog):
    """find_by_sha 가 이미 존재를 리턴하면 run_gate_check 는 건너뛰고 (config, None, None) 반환."""
    db = MagicMock()
    repo = MagicMock()
    repo.id = 1
    repo_config = MagicMock()

    score_result = MagicMock()
    score_result.total = 80
    score_result.grade = "B"

    params = _AnalysisSaveParams(
        repo_name="o/r",
        commit_sha="deadbeef",
        commit_message="feat: test",
        pr_number=7,
        owner_token="ghp_test",
        analysis_results=[],
        ai_review=MagicMock(),
        score_result=score_result,
    )

    with patch.object(pipeline_mod.repository_repo, "find_by_full_name", return_value=repo), \
         patch.object(pipeline_mod.analysis_repo, "find_by_sha", return_value=MagicMock(id=99)), \
         patch.object(pipeline_mod, "get_repo_config", return_value=repo_config), \
         patch.object(pipeline_mod, "run_gate_check", new=AsyncMock()) as run_gate, \
         caplog.at_level(logging.INFO, logger="src.worker.pipeline"):
        cfg, analysis_id, result_dict = await pipeline_mod._save_and_gate(db, params)

    assert analysis_id is None
    assert result_dict is None
    assert cfg is repo_config
    run_gate.assert_not_called()
    assert any("already saved" in r.message for r in caplog.records)


async def test_save_and_gate_race_recovery_runs_gate_when_pr_number_missing(caplog):
    """Phase 2 race fix: 동시 push+PR 도착으로 기존 Analysis 의 pr_number=None 일 때
    PR 이벤트 분기에서 pr_number 부여 + gate 재실행 (PR #105 silent skip 방지).
    """
    db = MagicMock()
    repo = MagicMock()
    repo.id = 1
    repo_config = MagicMock()

    # 기존 Analysis — pr_number=None (push 가 먼저 저장된 상태)
    existing = MagicMock()
    existing.id = 99
    existing.pr_number = None
    existing.result = {"score": 80}

    score_result = MagicMock()
    score_result.total = 80
    score_result.grade = "B"

    params = _AnalysisSaveParams(
        repo_name="o/r",
        commit_sha="deadbeef",
        commit_message="feat: test",
        pr_number=7,
        owner_token="ghp_test",
        analysis_results=[],
        ai_review=MagicMock(),
        score_result=score_result,
    )

    with patch.object(pipeline_mod.repository_repo, "find_by_full_name", return_value=repo), \
         patch.object(pipeline_mod.analysis_repo, "find_by_sha", return_value=existing), \
         patch.object(pipeline_mod, "get_repo_config", return_value=repo_config), \
         patch.object(pipeline_mod, "run_gate_check", new=AsyncMock()) as run_gate, \
         caplog.at_level(logging.INFO, logger="src.worker.pipeline"):
        cfg, analysis_id, result_dict = await pipeline_mod._save_and_gate(db, params)

    # 반환값: 신규 Analysis 미생성이므로 (config, None, None)
    assert analysis_id is None
    assert result_dict is None
    assert cfg is repo_config
    # pr_number 가 부여됐고 gate 가 재실행됨
    assert existing.pr_number == 7
    db.commit.assert_called()
    run_gate.assert_awaited_once()
    # gate 재실행 시 기존 result 사용
    call_kwargs = run_gate.await_args.kwargs
    assert call_kwargs["pr_number"] == 7
    assert call_kwargs["analysis_id"] == 99
    assert call_kwargs["result"] == {"score": 80}
    assert any("Race-recovered" in r.message for r in caplog.records)


async def test_save_and_gate_skips_race_recovery_when_existing_already_has_pr_number():
    """기존 Analysis 가 이미 pr_number 보유 — race 회복 분기 미발동, 단순 dedup skip."""
    db = MagicMock()
    repo = MagicMock()
    repo.id = 1
    repo_config = MagicMock()

    existing = MagicMock()
    existing.id = 99
    existing.pr_number = 7  # 이미 부여된 상태

    score_result = MagicMock()
    score_result.total = 80
    score_result.grade = "B"

    params = _AnalysisSaveParams(
        repo_name="o/r",
        commit_sha="deadbeef",
        commit_message="feat: test",
        pr_number=7,
        owner_token="ghp_test",
        analysis_results=[],
        ai_review=MagicMock(),
        score_result=score_result,
    )

    with patch.object(pipeline_mod.repository_repo, "find_by_full_name", return_value=repo), \
         patch.object(pipeline_mod.analysis_repo, "find_by_sha", return_value=existing), \
         patch.object(pipeline_mod, "get_repo_config", return_value=repo_config), \
         patch.object(pipeline_mod, "run_gate_check", new=AsyncMock()) as run_gate:
        cfg, analysis_id, _ = await pipeline_mod._save_and_gate(db, params)

    assert cfg is repo_config
    assert analysis_id is None
    # gate 재실행 안 함
    run_gate.assert_not_called()
    db.commit.assert_not_called()


async def test_save_and_gate_skips_race_recovery_for_push_event():
    """push 이벤트 (pr_number=None) — race 회복 분기 미발동 (PR 전용)."""
    db = MagicMock()
    repo = MagicMock()
    repo.id = 1

    existing = MagicMock()
    existing.id = 99
    existing.pr_number = None

    score_result = MagicMock()
    score_result.total = 80
    score_result.grade = "B"

    params = _AnalysisSaveParams(
        repo_name="o/r",
        commit_sha="deadbeef",
        commit_message="feat: test",
        pr_number=None,  # push 이벤트
        owner_token="ghp_test",
        analysis_results=[],
        ai_review=MagicMock(),
        score_result=score_result,
    )

    with patch.object(pipeline_mod.repository_repo, "find_by_full_name", return_value=repo), \
         patch.object(pipeline_mod.analysis_repo, "find_by_sha", return_value=existing), \
         patch.object(pipeline_mod, "get_repo_config", return_value=MagicMock()), \
         patch.object(pipeline_mod, "run_gate_check", new=AsyncMock()) as run_gate:
        await pipeline_mod._save_and_gate(db, params)

    run_gate.assert_not_called()


async def test_save_and_gate_race_recovery_handles_sqlalchemy_error_on_commit():
    """Race recovery 중 db.commit 이 SQLAlchemyError 발생 시 rollback + logger.error."""
    from sqlalchemy.exc import SQLAlchemyError as _SQLAlchemyError

    db = MagicMock()
    db.commit.side_effect = _SQLAlchemyError("commit failed")
    repo = MagicMock()
    repo.id = 1
    repo_config = MagicMock()

    existing = MagicMock()
    existing.id = 99
    existing.pr_number = None
    existing.result = {"score": 80}

    score_result = MagicMock()
    score_result.total = 80
    score_result.grade = "B"

    params = _AnalysisSaveParams(
        repo_name="o/r",
        commit_sha="deadbeef",
        commit_message="feat: test",
        pr_number=7,
        owner_token="ghp_test",
        analysis_results=[],
        ai_review=MagicMock(),
        score_result=score_result,
    )

    with patch.object(pipeline_mod.repository_repo, "find_by_full_name", return_value=repo), \
         patch.object(pipeline_mod.analysis_repo, "find_by_sha", return_value=existing), \
         patch.object(pipeline_mod, "get_repo_config", return_value=repo_config), \
         patch.object(pipeline_mod, "run_gate_check", new=AsyncMock()) as run_gate:
        cfg, analysis_id, _ = await pipeline_mod._save_and_gate(db, params)

    assert cfg is repo_config
    assert analysis_id is None
    db.rollback.assert_called_once()
    # commit 실패 → run_gate_check 까지 도달 안 함
    run_gate.assert_not_called()


async def test_save_and_gate_race_recovery_handles_gate_check_exception(caplog):
    """Race recovery 중 run_gate_check 가 예외 발생 시 logger.exception 으로 traceback 보존."""
    db = MagicMock()
    repo = MagicMock()
    repo.id = 1
    repo_config = MagicMock()

    existing = MagicMock()
    existing.id = 99
    existing.pr_number = None
    existing.result = {"score": 80}

    score_result = MagicMock()
    score_result.total = 80
    score_result.grade = "B"

    params = _AnalysisSaveParams(
        repo_name="o/r",
        commit_sha="deadbeef" * 5,
        commit_message="feat: test",
        pr_number=7,
        owner_token="ghp_test",
        analysis_results=[],
        ai_review=MagicMock(),
        score_result=score_result,
    )

    with patch.object(pipeline_mod.repository_repo, "find_by_full_name", return_value=repo), \
         patch.object(pipeline_mod.analysis_repo, "find_by_sha", return_value=existing), \
         patch.object(pipeline_mod, "get_repo_config", return_value=repo_config), \
         patch.object(
             pipeline_mod, "run_gate_check",
             new=AsyncMock(side_effect=RuntimeError("gate failed")),
         ), \
         caplog.at_level(logging.ERROR, logger="src.worker.pipeline"):
        cfg, analysis_id, _ = await pipeline_mod._save_and_gate(db, params)

    # 예외가 함수 밖으로 전파되지 않음 — silent fail 회피
    assert cfg is repo_config
    assert analysis_id is None
    # logger.exception 호출 — Sentry/Railway 디버깅 가능
    assert any(
        "Race-recovery gate check failed" in r.message
        for r in caplog.records
    )


async def test_save_and_gate_race_recovery_with_repo_config_load_failure():
    """Race recovery 중 get_repo_config 가 KeyError 면 repo_config=None 으로 fallback."""
    db = MagicMock()
    repo = MagicMock()
    repo.id = 1

    existing = MagicMock()
    existing.id = 99
    existing.pr_number = None
    existing.result = {"score": 80}

    score_result = MagicMock()
    score_result.total = 80
    score_result.grade = "B"

    params = _AnalysisSaveParams(
        repo_name="o/r",
        commit_sha="deadbeef",
        commit_message="feat: test",
        pr_number=7,
        owner_token="ghp_test",
        analysis_results=[],
        ai_review=MagicMock(),
        score_result=score_result,
    )

    with patch.object(pipeline_mod.repository_repo, "find_by_full_name", return_value=repo), \
         patch.object(pipeline_mod.analysis_repo, "find_by_sha", return_value=existing), \
         patch.object(pipeline_mod, "get_repo_config", side_effect=KeyError("missing")), \
         patch.object(pipeline_mod, "run_gate_check", new=AsyncMock()) as run_gate:
        cfg, _, _ = await pipeline_mod._save_and_gate(db, params)

    # config load 실패 → None 으로 fallback, gate 는 여전히 호출됨 (config=None)
    assert cfg is None
    run_gate.assert_awaited_once()
    assert run_gate.await_args.kwargs["config"] is None


# ---------------------------------------------------------------------------
# #25/#814 미러 — AI 리뷰 genuine 실패 시 인플레 점수 NULL-persist (집계 오염 차단)
# Pipeline mirrors the hook NULL-persist so a failed AI review doesn't pollute aggregates.
# ---------------------------------------------------------------------------


def _new_save_params(ai_status: str, *, truncated: bool = False):
    """신규 저장 경로(find_by_sha=None)용 _AnalysisSaveParams + status 지정 ai_review.

    truncated: AI diff 절단 여부 (C22 — 절단 시 부분-diff 인플레 점수 → 집계 NULL 대상).
    truncated: whether the AI diff was truncated (C22 — partial-diff inflated score).
    MagicMock 의 .truncated 는 기본 truthy 라 명시 대입 필수 (미설정 시 전 테스트 오염).
    MagicMock auto-attrs are truthy → must set .truncated explicitly.
    """
    ai = MagicMock()
    ai.status = ai_status
    ai.truncated = truncated
    ai.used_model = None
    ai.input_tokens = None
    ai.output_tokens = None
    score_result = MagicMock()
    score_result.total = 89
    score_result.grade = "B"
    return _AnalysisSaveParams(
        repo_name="o/r",
        commit_sha="deadbeefcafe",
        commit_message="feat: test",
        pr_number=7,
        owner_token="ghp_test",
        analysis_results=[],
        ai_review=ai,
        score_result=score_result,
    )


async def _run_new_save(params):
    """신규 Analysis 저장 경로를 실행하고 save_new 에 전달된 Analysis 를 캡처."""
    db = MagicMock()
    repo = MagicMock()
    repo.id = 1
    captured = {}

    def _capture_save(_db, analysis):
        analysis.id = 42
        captured["analysis"] = analysis
        return analysis, True  # created=True (신규)

    with patch.object(pipeline_mod.repository_repo, "find_by_full_name", return_value=repo), \
         patch.object(pipeline_mod.analysis_repo, "find_by_sha", return_value=None), \
         patch.object(pipeline_mod.analysis_repo, "save_new", side_effect=_capture_save), \
         patch.object(pipeline_mod, "get_repo_config", return_value=MagicMock()), \
         patch.object(pipeline_mod, "run_gate_check", new=AsyncMock()):
        await pipeline_mod._save_and_gate(db, params)
    return captured["analysis"]


async def test_save_and_gate_nulls_score_on_ai_api_error():
    """AI 리뷰 api_error(genuine 실패) 시 score/grade NULL 저장 — 대시보드/리더보드 집계 오염 차단."""
    analysis = await _run_new_save(_new_save_params("api_error"))
    assert analysis.score is None, "api_error 인데 인플레 점수가 저장됨 — 집계 오염"
    assert analysis.grade is None
    # 진단용 status·breakdown 은 result dict 에 보존 (컬럼=NULL / result=보존 비대칭)
    assert analysis.result["ai_review_status"] == "api_error"


async def test_save_and_gate_nulls_score_on_ai_parse_error():
    """AI 리뷰 parse_error 시에도 score/grade NULL 저장 (hook #25/#814 대칭)."""
    analysis = await _run_new_save(_new_save_params("parse_error"))
    assert analysis.score is None
    assert analysis.grade is None


async def test_save_and_gate_persists_score_on_ai_truncated():
    """🔴 입력-diff 절단(truncated)은 score/grade NULL 대상에서 제외 — 점수 유지 (C22 분리).

    절단 리뷰는 status="success" 이고 점수의 대부분(code_quality/security)은 전체 파일 정적분석
    기반이라 신뢰할 수 있다. 입력 diff 가 16,000자를 넘는 대형 commit/PR 의 절반이 절단되는데,
    이를 전부 NULL-persist 하면 운영 대시보드/리더보드에서 점수가 통째로 사라진다(운영 DB 실측:
    6월 NULL 256건 중 다수가 절단형). 따라서 NULL 은 genuine 실패(api_error/parse_error)에만 적용.
    🔴 절단 시 auto-merge/auto-approve 차단은 result dict 의 `ai_review_truncated` 마커를 직접
    읽는 #885 가드가 그대로 담당(점수 컬럼 NULL 여부와 무관) — 본 분리로 안전성 영향 0.
    Input-diff truncation no longer NULL-persists the score: the score is mostly full-file static
    analysis (reliable), and NULLing ~half of large-diff analyses wiped scores off the dashboard.
    Auto-merge/approve still blocks on the `ai_review_truncated` marker (#885), independent of column.
    """
    analysis = await _run_new_save(_new_save_params("success", truncated=True))
    assert analysis.score == 89, "절단(truncated)이어도 점수는 유지되어야 함 (NULL 분리)"
    assert analysis.grade == "B"
    # 🔴 절단 마커는 result dict 에 보존 — auto-merge/auto-approve 차단(#885) 가드가 직접 읽음.
    # The truncation marker stays in the result dict — the #885 auto-merge/approve guard reads it.
    assert analysis.result["ai_review_truncated"] is True


async def test_save_and_gate_persists_score_on_ai_success():
    """AI 리뷰 success 시 정상 점수 저장 (회귀 가드 — 실패 분기가 정상 경로를 침범하지 않음)."""
    analysis = await _run_new_save(_new_save_params("success"))
    assert analysis.score == 89
    assert analysis.grade == "B"


async def test_save_and_gate_persists_score_on_intentional_skip():
    """no_api_key/empty_diff(의도적 미수행)는 ai_review_failed=False — 점수 유지 (회귀 방지)."""
    for skip_status in ("no_api_key", "empty_diff"):
        analysis = await _run_new_save(_new_save_params(skip_status))
        assert analysis.score == 89, f"{skip_status} 는 의도적 미수행 — 점수 유지여야 함"
        assert analysis.grade == "B"


async def test_regate_pr_if_needed_logs_exception_with_traceback(caplog):
    """Phase 2: _regate_pr_if_needed 의 except 가 logger.exception 으로 stack 보존."""
    db = MagicMock()
    repo = MagicMock()
    repo.id = 1
    repo.owner = None  # owner_token 결정 분기 — settings.github_token fallback

    existing = MagicMock()
    existing.id = 99
    existing.pr_number = None
    existing.result = {"score": 80}

    with patch.object(pipeline_mod.repository_repo, "find_by_full_name", return_value=repo), \
         patch.object(pipeline_mod.analysis_repo, "find_by_sha", return_value=existing), \
         patch.object(
             pipeline_mod, "run_gate_check",
             new=AsyncMock(side_effect=RuntimeError("gate boom")),
         ), \
         caplog.at_level(logging.ERROR, logger="src.worker.pipeline"):
        await pipeline_mod._regate_pr_if_needed(
            db, "o/r", "abc1234567890", pr_number=7
        )

    # logger.exception → 로그 레벨 ERROR + exc_info 포함
    error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("Re-gate check failed" in r.message for r in error_records)
    re_gate_record = next(
        r for r in error_records if "Re-gate check failed" in r.message
    )
    assert re_gate_record.exc_info is not None


# ---------------------------------------------------------------------------
# Phase H PR-2A — race-recovery 시 run_analysis_pipeline 의 notify 단계 skip
# 12-에이전트 감사 Critical C2 — race-recovery 가 (cfg, None, None) 반환 시
# build_notification_tasks 가 result_dict=None 으로 호출돼 silent KeyError 위험.
# 호출자 측에서 analysis_id is None 을 race-recovery 시그널로 인식하고 notify skip.
# ---------------------------------------------------------------------------


async def test_pipeline_skips_notify_when_save_returns_no_analysis_id(caplog):
    """_save_and_gate 가 (cfg, None, None) 반환 시 run_analysis_pipeline 은
    notify 단계를 건너뛴다 — 원본 webhook 이 이미 알림을 발송했음을 가정.
    """
    push_data = {
        "repository": {"full_name": "owner/repo"},
        "after": "racesha000000",
        "head_commit": {"id": "racesha000000", "message": "feat: race"},
        "commits": [{"id": "racesha000000", "message": "feat: race"}],
        "sender": {"login": "alice", "type": "User"},
    }
    repo_config = MagicMock()

    # _save_and_gate 가 race-recovery 반환 (cfg, None, None) 시뮬레이션
    save_mock = AsyncMock(return_value=(repo_config, None, None))

    with patch.object(pipeline_mod, "_extract_event_metadata",
                      return_value=("owner/repo", "racesha000000", "feat: race", None)), \
         patch.object(pipeline_mod, "_ensure_repo", return_value=(MagicMock(), "ghp_test")), \
         patch.object(pipeline_mod, "_collect_files",
                      return_value=[MagicMock(filename="a.py", patch="+x=1")]), \
         patch.object(pipeline_mod, "_run_static_analysis",
                      new=AsyncMock(return_value=[])), \
         patch.object(pipeline_mod, "review_code", new=AsyncMock()), \
         patch.object(pipeline_mod, "calculate_score", return_value=MagicMock(total=80, grade="B")), \
         patch.object(pipeline_mod, "_save_and_gate", new=save_mock), \
         patch.object(pipeline_mod, "build_notification_tasks") as mock_notify_build, \
         caplog.at_level(logging.INFO, logger="src.worker.pipeline"):
        await pipeline_mod.run_analysis_pipeline("push", push_data)

    # 핵심 검증: race-recovery 시 build_notification_tasks 는 호출되지 않아야 함
    mock_notify_build.assert_not_called()
