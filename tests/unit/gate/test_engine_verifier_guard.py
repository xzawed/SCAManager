"""engine._run_auto_merge 단일출처 검증 가드 테스트 (P1-1 반자동 parity).
engine._run_auto_merge single-source verifier guard tests (P1-1 semi-auto parity).

검증 가드가 AutoMergeAction 이 아닌 engine._run_auto_merge 진입부(threshold 체크 직후,
SessionLocal 진입 전)에 단일출처화되므로 자동/반자동 양 경로가 동일 가드를 공유한다.
이 파일은 가드가 머지 실행(retry/legacy)을 정확히 차단/허용하는지 + result 전파를 봉인.

The verifier guard is single-sourced into engine._run_auto_merge (right after the threshold
check, before SessionLocal) so both auto and semi-auto paths share it. This file seals that the
guard blocks/allows the actual merge (retry/legacy) correctly and propagates `result`.

🔴 seam: _run_auto_merge 가 verifier_blocks_merge 를 deferred import 하므로 패치 대상은
src.gate.merge_verifier.verifier_blocks_merge (deferred `from X import Y` 는 호출 시점에
모듈 attribute 를 재조회 → 모듈 네임스페이스 패치가 적용됨).
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest
from unittest.mock import AsyncMock, patch

from src.gate.engine import _run_auto_merge
from src.config_manager.manager import RepoConfigData


def _config(**kwargs):
    """auto_merge 활성 + merge_threshold 기본 픽스처."""
    defaults = dict(
        repo_full_name="owner/repo",
        pr_review_comment=False,
        approve_mode="disabled",
        approve_threshold=75,
        reject_threshold=50,
        auto_merge=True,
        merge_threshold=75,
        notify_chat_id=None,
    )
    defaults.update(kwargs)
    return RepoConfigData(**defaults)


async def test_verifier_blocks_merge_true_skips_merge():
    # verifier_blocks_merge=True → retry/legacy 둘 다 미호출 (머지 미진행)
    config = _config(merge_threshold=75)
    with patch("src.gate.merge_verifier.verifier_blocks_merge",
               new=AsyncMock(return_value=True)) as mock_guard:
        with patch("src.gate.engine._run_auto_merge_retry", new_callable=AsyncMock) as mock_retry:
            with patch("src.gate.engine._run_auto_merge_legacy", new_callable=AsyncMock) as mock_legacy:
                await _run_auto_merge(
                    config, "tok", "owner/repo", 1, 80,
                    analysis_id=1, result={"score": 80},
                )
    mock_guard.assert_awaited_once()
    mock_retry.assert_not_awaited()    # 가드 차단 → 재시도 경로 미진입
    mock_legacy.assert_not_awaited()   # 가드 차단 → 레거시 경로 미진입


async def test_verifier_blocks_merge_false_proceeds_to_merge():
    # verifier_blocks_merge=False → 정상 머지 경로(retry 또는 legacy) 진입
    config = _config(merge_threshold=75)
    with patch("src.gate.merge_verifier.verifier_blocks_merge",
               new=AsyncMock(return_value=False)) as mock_guard:
        with patch("src.gate.engine.settings") as mock_settings:
            mock_settings.merge_retry_enabled = True
            with patch("src.gate.engine._run_auto_merge_retry", new_callable=AsyncMock) as mock_retry:
                with patch("src.gate.engine._run_auto_merge_legacy", new_callable=AsyncMock) as mock_legacy:
                    await _run_auto_merge(
                        config, "tok", "owner/repo", 1, 80,
                        analysis_id=1, result={"score": 80},
                    )
    mock_guard.assert_awaited_once()
    # retry_enabled=True → retry 경로 진입, legacy 미진입
    mock_retry.assert_awaited_once()
    mock_legacy.assert_not_awaited()


async def test_below_threshold_skips_verifier_guard():
    # score < merge_threshold → 조기 return, verifier_blocks_merge 미호출 (불필요한 검증 비용 0)
    config = _config(merge_threshold=90)  # 80 < 90
    with patch("src.gate.merge_verifier.verifier_blocks_merge",
               new=AsyncMock(return_value=False)) as mock_guard:
        with patch("src.gate.engine._run_auto_merge_retry", new_callable=AsyncMock) as mock_retry:
            with patch("src.gate.engine._run_auto_merge_legacy", new_callable=AsyncMock) as mock_legacy:
                await _run_auto_merge(
                    config, "tok", "owner/repo", 1, 80,
                    analysis_id=1, result={"score": 80},
                )
    mock_guard.assert_not_awaited()    # 임계 미달 → 검증 가드 미호출
    mock_retry.assert_not_awaited()
    mock_legacy.assert_not_awaited()


async def test_auto_merge_disabled_skips_verifier_guard():
    # config.auto_merge=False → 조기 return, verifier_blocks_merge 미호출
    config = _config(auto_merge=False, merge_threshold=75)
    with patch("src.gate.merge_verifier.verifier_blocks_merge",
               new=AsyncMock(return_value=False)) as mock_guard:
        with patch("src.gate.engine._run_auto_merge_retry", new_callable=AsyncMock):
            with patch("src.gate.engine._run_auto_merge_legacy", new_callable=AsyncMock):
                await _run_auto_merge(
                    config, "tok", "owner/repo", 1, 80,
                    analysis_id=1, result={"score": 80},
                )
    mock_guard.assert_not_awaited()


async def test_verifier_guard_receives_caller_result_dict():
    # 호출자가 넘긴 result dict 가 verifier_blocks_merge 에 그대로 전파되는지 (spy)
    config = _config(merge_threshold=75)
    caller_result = {"score": 80, "grade": "B", "ai_summary": "spy-marker", "issues": []}
    with patch("src.gate.merge_verifier.verifier_blocks_merge",
               new=AsyncMock(return_value=True)) as mock_guard:
        with patch("src.gate.engine._run_auto_merge_retry", new_callable=AsyncMock):
            with patch("src.gate.engine._run_auto_merge_legacy", new_callable=AsyncMock):
                await _run_auto_merge(
                    config, "tok", "owner/repo", 1, 80,
                    analysis_id=1, result=caller_result,
                )
    mock_guard.assert_awaited_once()
    kw = mock_guard.await_args.kwargs
    # 호출자 result 가 동일 객체로 전달 (가드가 진짜 diff/요약을 검증할 수 있어야 함)
    assert kw["result"] is caller_result
    assert kw["score"] == 80
    assert kw["merge_threshold"] == 75
    assert kw["repo_name"] == "owner/repo"
    assert kw["pr_number"] == 1


async def test_verifier_guard_result_defaults_to_empty_dict():
    # result 미전달(None) 시 verifier_blocks_merge 에 빈 dict 가 전달되어야 한다 (NPE 방지)
    config = _config(merge_threshold=75)
    with patch("src.gate.merge_verifier.verifier_blocks_merge",
               new=AsyncMock(return_value=True)) as mock_guard:
        with patch("src.gate.engine._run_auto_merge_retry", new_callable=AsyncMock):
            with patch("src.gate.engine._run_auto_merge_legacy", new_callable=AsyncMock):
                await _run_auto_merge(
                    config, "tok", "owner/repo", 1, 80, analysis_id=1,
                )
    mock_guard.assert_awaited_once()
    assert mock_guard.await_args.kwargs["result"] == {}
