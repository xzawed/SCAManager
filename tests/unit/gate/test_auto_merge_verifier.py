import pytest

from src.gate.actions import GateContext
from src.gate.actions.auto_merge import AutoMergeAction
from src.gate import merge_verifier as mv


def _ctx(score=80):
    cfg = type("Cfg", (), {"auto_merge": True, "merge_threshold": 75})()
    return GateContext(
        repo_name="o/r", pr_number=1, analysis_id=5,
        result={"score": score, "grade": "B", "ai_summary": "ok", "issues": []},
        github_token="t", config=cfg, score=score,
    )


@pytest.mark.asyncio
async def test_unsafe_verdict_blocks_merge_and_comments(monkeypatch):
    monkeypatch.setattr("src.gate.actions.auto_merge.should_verify", lambda **k: True)
    async def _unsafe(ctx):
        return mv.VerifierVerdict(False, False, ("risky migration",), mv.VERIFIER_OK)
    monkeypatch.setattr("src.gate.actions.auto_merge.verify_merge_safety", _unsafe)
    posted = {}
    async def _comment(tok, repo, pr, body):
        posted["body"] = body
    monkeypatch.setattr("src.gate.actions.auto_merge.post_plain_pr_comment", _comment)
    merged = {"called": False}
    async def _merge(*a, **k):
        merged["called"] = True
    monkeypatch.setattr("src.gate.engine._run_auto_merge", _merge)

    await AutoMergeAction().execute(_ctx())
    assert merged["called"] is False
    assert "risky migration" in posted["body"]


@pytest.mark.asyncio
async def test_safe_verdict_proceeds_to_merge(monkeypatch):
    monkeypatch.setattr("src.gate.actions.auto_merge.should_verify", lambda **k: True)
    async def _safe(ctx):
        return mv.VerifierVerdict(True, False, (), mv.VERIFIER_OK)
    monkeypatch.setattr("src.gate.actions.auto_merge.verify_merge_safety", _safe)
    merged = {"called": False}
    async def _merge(*a, **k):
        merged["called"] = True
    monkeypatch.setattr("src.gate.engine._run_auto_merge", _merge)

    await AutoMergeAction().execute(_ctx())
    assert merged["called"] is True


@pytest.mark.asyncio
async def test_outside_band_skips_verifier(monkeypatch):
    monkeypatch.setattr("src.gate.actions.auto_merge.should_verify", lambda **k: False)
    called = {"verify": False}
    async def _v(ctx):
        called["verify"] = True
        return mv.VerifierVerdict(True, False, (), mv.VERIFIER_OK)
    monkeypatch.setattr("src.gate.actions.auto_merge.verify_merge_safety", _v)
    merged = {"called": False}
    async def _merge(*a, **k):
        merged["called"] = True
    monkeypatch.setattr("src.gate.engine._run_auto_merge", _merge)

    await AutoMergeAction().execute(_ctx(score=95))
    assert called["verify"] is False
    assert merged["called"] is True


@pytest.mark.asyncio
async def test_api_error_failclosed_blocks(monkeypatch):
    monkeypatch.setattr("src.gate.actions.auto_merge.should_verify", lambda **k: True)
    async def _err(ctx):
        return mv.VerifierVerdict(False, False, ("verifier call failed",), mv.VERIFIER_API_ERROR)
    monkeypatch.setattr("src.gate.actions.auto_merge.verify_merge_safety", _err)
    async def _comment(tok, repo, pr, body):
        pass
    monkeypatch.setattr("src.gate.actions.auto_merge.post_plain_pr_comment", _comment)
    merged = {"called": False}
    async def _merge(*a, **k):
        merged["called"] = True
    monkeypatch.setattr("src.gate.engine._run_auto_merge", _merge)

    await AutoMergeAction().execute(_ctx())
    assert merged["called"] is False
