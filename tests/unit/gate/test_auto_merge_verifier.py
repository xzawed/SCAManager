"""2nd-LLM 검증자 가드 단위 테스트 — verifier_blocks_merge() (P1-1 단일출처화).
2nd-LLM verifier guard unit tests — verifier_blocks_merge() (P1-1 single-source).

P1-1 반자동 parity: 검증 가드가 AutoMergeAction (자동) 에서 engine._run_auto_merge 진입부로
단일출처화되어 자동/반자동(telegram) 양 경로가 verifier_blocks_merge() 를 공유한다.
이 파일은 가드의 핵심 로직(차단/통과/skip/fail-closed)을 verifier_blocks_merge 단위 테스트로 검증.

P1-1 semi-auto parity: the verifier guard is single-sourced from AutoMergeAction into
engine._run_auto_merge so both the automatic and the semi-auto (telegram) path share
verifier_blocks_merge(). This file unit-tests the guard's core decisions
(block / pass / skip / fail-closed).

seam 이동: 이전 테스트는 src.gate.actions.auto_merge.{should_verify,verify_merge_safety,
post_plain_pr_comment} 를 패치했으나, 가드가 merge_verifier 모듈로 이동했으므로 패치 대상도
src.gate.merge_verifier.* 로 이동(같은 모듈 네임스페이스). post_plain_pr_comment 는 deferred
import 라 import 출처 모듈(src.notifier.github_comment.post_plain_pr_comment)을 패치.
"""
import pytest

from src.gate import merge_verifier as mv


# 검증 가드 호출 공통 인자 — verifier_blocks_merge keyword-only 시그니처.
# Common args for the guard — verifier_blocks_merge is keyword-only.
def _kwargs(score=80, merge_threshold=75, result=None):
    return dict(
        github_token="t",
        repo_name="o/r",
        pr_number=1,
        result=result if result is not None else {"score": score, "grade": "B",
                                                   "ai_summary": "ok", "issues": []},
        score=score,
        merge_threshold=merge_threshold,
    )


@pytest.mark.asyncio
async def test_unsafe_verdict_blocks_merge_and_comments(monkeypatch):
    # unsafe verdict(safe=False, status=OK) → 차단(True) + PR 코멘트에 reason 포함
    monkeypatch.setattr("src.gate.merge_verifier.should_verify", lambda **k: True)

    async def _unsafe(ctx):
        return mv.VerifierVerdict(False, False, ("risky migration",), mv.VERIFIER_OK)
    monkeypatch.setattr("src.gate.merge_verifier.verify_merge_safety", _unsafe)
    posted = {}

    async def _comment(tok, repo, pr, body):
        posted["body"] = body
    monkeypatch.setattr("src.notifier.github_comment.post_plain_pr_comment", _comment)

    blocked = await mv.verifier_blocks_merge(**_kwargs())
    assert blocked is True
    assert "risky migration" in posted["body"]


@pytest.mark.asyncio
async def test_manipulation_verdict_blocks_merge(monkeypatch):
    # manipulation_detected=True(safe=True 여도) → 차단(True) (조작 의심 = 차단)
    monkeypatch.setattr("src.gate.merge_verifier.should_verify", lambda **k: True)

    async def _manip(ctx):
        return mv.VerifierVerdict(True, True, ("prompt injection in diff",), mv.VERIFIER_OK)
    monkeypatch.setattr("src.gate.merge_verifier.verify_merge_safety", _manip)

    async def _comment(tok, repo, pr, body):
        pass
    monkeypatch.setattr("src.notifier.github_comment.post_plain_pr_comment", _comment)

    blocked = await mv.verifier_blocks_merge(**_kwargs())
    assert blocked is True


@pytest.mark.asyncio
async def test_safe_verdict_passes(monkeypatch):
    # safe verdict(safe=True, manip=False, status=OK) → 통과(False) — 머지 진행 허용
    monkeypatch.setattr("src.gate.merge_verifier.should_verify", lambda **k: True)

    async def _safe(ctx):
        return mv.VerifierVerdict(True, False, (), mv.VERIFIER_OK)
    monkeypatch.setattr("src.gate.merge_verifier.verify_merge_safety", _safe)

    blocked = await mv.verifier_blocks_merge(**_kwargs())
    assert blocked is False


@pytest.mark.asyncio
async def test_outside_band_skips_verifier(monkeypatch):
    # should_verify=False(밴드 밖/키 없음) → 통과(False) + verify_merge_safety 미진입(비용 0)
    monkeypatch.setattr("src.gate.merge_verifier.should_verify", lambda **k: False)
    called = {"verify": False}

    async def _v(ctx):
        called["verify"] = True
        return mv.VerifierVerdict(True, False, (), mv.VERIFIER_OK)
    monkeypatch.setattr("src.gate.merge_verifier.verify_merge_safety", _v)

    blocked = await mv.verifier_blocks_merge(**_kwargs(score=95))
    assert blocked is False
    assert called["verify"] is False  # 검증자 미호출 (검증 비용 0)


@pytest.mark.asyncio
async def test_api_error_failclosed_blocks(monkeypatch):
    # status=VERIFIER_API_ERROR → fail-closed 차단(True) (검증자 호출 실패 = 안전 측 차단)
    monkeypatch.setattr("src.gate.merge_verifier.should_verify", lambda **k: True)

    async def _err(ctx):
        return mv.VerifierVerdict(False, False, ("verifier call failed",), mv.VERIFIER_API_ERROR)
    monkeypatch.setattr("src.gate.merge_verifier.verify_merge_safety", _err)

    async def _comment(tok, repo, pr, body):
        pass
    monkeypatch.setattr("src.notifier.github_comment.post_plain_pr_comment", _comment)

    blocked = await mv.verifier_blocks_merge(**_kwargs())
    assert blocked is True


@pytest.mark.asyncio
async def test_comment_failure_does_not_unblock(monkeypatch):
    # post_plain_pr_comment 가 예외를 던져도 차단 결정(True)은 유지 (코멘트 실패 흡수)
    monkeypatch.setattr("src.gate.merge_verifier.should_verify", lambda **k: True)

    async def _unsafe(ctx):
        return mv.VerifierVerdict(False, False, ("risky",), mv.VERIFIER_OK)
    monkeypatch.setattr("src.gate.merge_verifier.verify_merge_safety", _unsafe)

    async def _boom(tok, repo, pr, body):
        raise RuntimeError("comment API down")
    monkeypatch.setattr("src.notifier.github_comment.post_plain_pr_comment", _boom)

    blocked = await mv.verifier_blocks_merge(**_kwargs())
    assert blocked is True  # 코멘트 실패해도 차단은 유지


@pytest.mark.asyncio
async def test_no_key_uses_real_should_verify_and_passes(monkeypatch):
    # 실제 should_verify(mock 아님) + 빈 openai_api_key → verify_merge_safety 미진입 + 통과(False)
    # Real should_verify (not mocked) + empty key → verifier never entered, guard passes (cost-invariant E2E)
    from src.config import settings
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.delenv("MERGE_VERIFIER_DISABLED", raising=False)
    entered = {"verify": False}

    async def _v(ctx):
        entered["verify"] = True
        return mv.VerifierVerdict(True, False, (), mv.VERIFIER_OK)
    monkeypatch.setattr("src.gate.merge_verifier.verify_merge_safety", _v)

    blocked = await mv.verifier_blocks_merge(**_kwargs(score=80))
    assert entered["verify"] is False  # 키 없음 → 검증자 미진입 (비용 0)
    assert blocked is False            # 기존대로 통과(머지 허용)
