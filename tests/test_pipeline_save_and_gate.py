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
