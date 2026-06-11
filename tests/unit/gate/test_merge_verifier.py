from src.gate import merge_reasons


def test_verifier_reason_tags_exist_and_terminal():
    assert merge_reasons.VERIFIER_BLOCKED == "verifier_blocked"
    assert merge_reasons.VERIFIER_ERROR == "verifier_error"
    # 검증자 차단은 재시도 대상 아님(터미널) — 재시도해도 같은 판정
    # Verifier block is not retriable (terminal) — retrying yields the same verdict
    assert merge_reasons.is_retriable_tag(merge_reasons.VERIFIER_BLOCKED) is False
    assert merge_reasons.is_retriable_tag(merge_reasons.VERIFIER_ERROR) is False


from src.gate import merge_verifier as mv


def test_is_in_verification_band_boundaries():
    assert mv.is_in_verification_band(75, 75, 10) is True
    assert mv.is_in_verification_band(84, 75, 10) is True
    assert mv.is_in_verification_band(85, 75, 10) is False
    assert mv.is_in_verification_band(74, 75, 10) is False


def test_interpret_verdict_ok():
    v = mv.interpret_verdict({"safe": True, "manipulation_detected": False, "reasons": ["a", "b"]})
    assert v.safe is True and v.manipulation_detected is False
    assert v.reasons == ("a", "b") and v.status == mv.VERIFIER_OK


def test_interpret_verdict_unsafe_with_reasons():
    v = mv.interpret_verdict({"safe": False, "manipulation_detected": True, "reasons": ["x", "y", "z", "w"]})
    assert v.safe is False and v.manipulation_detected is True
    assert v.reasons == ("x", "y", "z")


def test_interpret_verdict_missing_keys_is_parse_error():
    v = mv.interpret_verdict({"safe": True})
    assert v.status == mv.VERIFIER_PARSE_ERROR and v.safe is False


def test_interpret_verdict_non_dict_is_parse_error():
    v = mv.interpret_verdict(["not", "a", "dict"])
    assert v.status == mv.VERIFIER_PARSE_ERROR and v.safe is False


def test_build_verifier_prompt_wraps_diff_in_untrusted_boundary():
    prompt = mv.build_verifier_prompt(
        patches=[("a.py", "+ import os\n+ os.system('x')")],
        result={"score": 80, "grade": "B", "ai_summary": "looks fine",
                "issues": [{"tool": "bandit", "severity": "HIGH", "message": "shell"}]},
        score=80,
    )
    assert "<untrusted-data>" in prompt and "</untrusted-data>" in prompt
    assert "a.py" in prompt
    assert "지시가 아니" in prompt or "not instructions" in prompt


def test_should_verify_off_without_key(monkeypatch):
    from src.config import settings
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "merge_verifier_band", 10)
    assert mv.should_verify(score=80, merge_threshold=75) is False


def test_should_verify_on_in_band_with_key(monkeypatch):
    from src.config import settings
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "merge_verifier_band", 10)
    monkeypatch.delenv("MERGE_VERIFIER_DISABLED", raising=False)
    assert mv.should_verify(score=80, merge_threshold=75) is True


def test_should_verify_off_when_kill_switch(monkeypatch):
    from src.config import settings
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "merge_verifier_band", 10)
    monkeypatch.setenv("MERGE_VERIFIER_DISABLED", "1")
    assert mv.should_verify(score=80, merge_threshold=75) is False


import pytest

from src.gate.actions import GateContext


def _ctx(score=80):
    cfg = type("Cfg", (), {"merge_threshold": 75})()
    return GateContext(
        repo_name="o/r", pr_number=1, analysis_id=5,
        result={"score": score, "grade": "B", "ai_summary": "ok", "issues": []},
        github_token="t", config=cfg, score=score,
    )


@pytest.mark.asyncio
async def test_verify_merge_safety_safe(monkeypatch):
    from src.gate import merge_verifier as mv
    cf = type("CF", (), {"filename": "a.py", "patch": "+x"})()
    monkeypatch.setattr(mv, "get_pr_files", lambda *a, **k: [cf])
    async def _fake_call(system, user, **kw):
        return '{"safe": true, "manipulation_detected": false, "reasons": []}'
    monkeypatch.setattr(mv, "call_openai_verifier", _fake_call)
    v = await mv.verify_merge_safety(_ctx())
    assert v.safe is True and v.status == mv.VERIFIER_OK


@pytest.mark.asyncio
async def test_verify_merge_safety_api_error_failclosed(monkeypatch):
    from src.gate import merge_verifier as mv
    cf = type("CF", (), {"filename": "a.py", "patch": "+x"})()
    monkeypatch.setattr(mv, "get_pr_files", lambda *a, **k: [cf])
    async def _boom(system, user, **kw):
        raise RuntimeError("api down")
    monkeypatch.setattr(mv, "call_openai_verifier", _boom)
    v = await mv.verify_merge_safety(_ctx())
    assert v.safe is False and v.status == mv.VERIFIER_API_ERROR


@pytest.mark.asyncio
async def test_verify_merge_safety_bad_json_parse_error(monkeypatch):
    from src.gate import merge_verifier as mv
    cf = type("CF", (), {"filename": "a.py", "patch": "+x"})()
    monkeypatch.setattr(mv, "get_pr_files", lambda *a, **k: [cf])
    async def _bad(system, user, **kw):
        return "not json at all"
    monkeypatch.setattr(mv, "call_openai_verifier", _bad)
    v = await mv.verify_merge_safety(_ctx())
    assert v.safe is False and v.status == mv.VERIFIER_PARSE_ERROR


def test_interpret_verdict_non_list_reasons_no_crash():
    # reasons 가 비-리스트(int/None)여도 예외 없이 빈 reasons 로 처리 (Codex CHECK1 — interpret 무예외)
    # Non-list reasons (int/None) must not raise — interpret_verdict stays exception-free.
    from src.gate import merge_verifier as _mv
    v = _mv.interpret_verdict({"safe": True, "manipulation_detected": False, "reasons": 5})
    assert v.status == _mv.VERIFIER_OK and v.reasons == ()
    v2 = _mv.interpret_verdict({"safe": False, "manipulation_detected": False, "reasons": None})
    assert v2.reasons == ()


def test_merge_verifier_band_zero_rejected():
    # band <= 0 은 ValidationError 로 거부 — silent 무효화 차단 (Codex CHECK9, Field(ge=1))
    # band <= 0 must be rejected (silent disable guard).
    from pydantic import ValidationError
    from src.config import Settings
    with pytest.raises(ValidationError):
        Settings(merge_verifier_band=0)
