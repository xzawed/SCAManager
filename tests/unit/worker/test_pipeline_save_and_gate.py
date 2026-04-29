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
