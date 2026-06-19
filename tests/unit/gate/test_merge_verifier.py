import pytest

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


# fail-closed 엄격 파싱 회귀 가드 (#859 회고 P2) — bool() truthy 함정 차단
# Strict fail-closed parse regression guards — block the bool() truthiness trap


@pytest.mark.parametrize("bad_safe", ["false", "False", "true", 1, 0, None, "0"])
def test_interpret_verdict_non_bool_safe_is_unsafe(bad_safe):
    # 명시적 True 가 아닌 모든 safe 값(특히 문자열 "false")은 unsafe 로 차단해야 함(fail-closed)
    # Any non-literal-True 'safe' (esp. string "false") must be treated unsafe (fail-closed)
    v = mv.interpret_verdict({"safe": bad_safe, "manipulation_detected": False, "reasons": []})
    assert v.safe is False
    assert v.status == mv.VERIFIER_OK  # 키는 존재하므로 parse_error 아님 (값 해석만 보수적)


@pytest.mark.parametrize("bad_manip", ["false", "true", 1, 0, None, "0"])
def test_interpret_verdict_non_false_manipulation_blocks(bad_manip):
    # 명시적 False 가 아닌 모든 manipulation 값은 조작 의심으로 차단해야 함(fail-closed)
    # Any non-literal-False 'manipulation_detected' must be treated as detected (fail-closed)
    v = mv.interpret_verdict({"safe": True, "manipulation_detected": bad_manip, "reasons": []})
    assert v.manipulation_detected is True


def test_interpret_verdict_literal_bools_unchanged():
    # 정상 real-bool 경로는 회귀 없이 보존
    # Real-bool happy path preserved (no regression)
    ok = mv.interpret_verdict({"safe": True, "manipulation_detected": False, "reasons": []})
    assert ok.safe is True and ok.manipulation_detected is False


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


# diff cap 회귀 가드 (#859 회고 P1-4, Codex mutual Option A) — cap 초과 시 fail-closed 차단(절단 없음)
# diff cap regression guards (#859 retro P1-4, Codex mutual Option A) — over cap → fail-closed block (no truncation)


def test_diff_exceeds_cap_true_for_oversized():
    from src.constants import VERIFIER_DIFF_CHAR_CAP
    huge = "+x\n" * VERIFIER_DIFF_CHAR_CAP  # 캡의 약 3배 / ~3x the cap
    assert mv.diff_exceeds_cap([("big.py", huge)]) is True


def test_diff_exceeds_cap_false_for_small():
    assert mv.diff_exceeds_cap([("a.py", "+ small change")]) is False


def test_build_verifier_prompt_keeps_diff_intact_no_truncation():
    # Option A: 프롬프트는 절단하지 않음 — oversized 는 verify_merge_safety 가 호출 전 차단
    # Option A: prompt never truncates — oversized diffs are blocked upstream by verify_merge_safety
    prompt = mv.build_verifier_prompt(
        patches=[("a.py", "+ small change")],
        result={"score": 80, "grade": "B", "ai_summary": "s", "issues": []},
        score=80,
    )
    assert "+ small change" in prompt
    assert "truncated" not in prompt
    assert "<untrusted-data>" in prompt and "</untrusted-data>" in prompt


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
async def test_verify_merge_safety_propagates_base_url(monkeypatch):
    """verify_merge_safety 가 settings.verifier_base_url 을 call_openai_verifier 에 전달해야 한다.

    공급자 전환(무료/저가 OpenAI-호환 — GitHub Models 등) 지원의 핵심 배선 회귀 가드.
    """
    from src.config import settings
    from src.gate import merge_verifier as mv
    monkeypatch.setattr(settings, "verifier_base_url", "https://models.github.ai/inference", raising=False)
    cf = type("CF", (), {"filename": "a.py", "patch": "+x"})()
    monkeypatch.setattr(mv, "get_pr_files", lambda *a, **k: [cf])
    seen = {}

    async def _fake_call(system, user, **kw):
        seen.update(kw)
        return '{"safe": true, "manipulation_detected": false, "reasons": []}'

    monkeypatch.setattr(mv, "call_openai_verifier", _fake_call)
    await mv.verify_merge_safety(_ctx())
    assert seen.get("base_url") == "https://models.github.ai/inference"


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


@pytest.mark.asyncio
async def test_verify_merge_safety_oversized_diff_failclosed_no_openai_call(monkeypatch):
    # Codex mutual Option A: cap 초과 diff 는 OpenAI 미호출 + fail-closed 차단
    # safe=False + status=OK → 게이트가 VERIFIER_BLOCKED(정상 차단 결정)로 매핑 / no OpenAI call (cost 0)
    from src.constants import VERIFIER_DIFF_CHAR_CAP
    from src.gate import merge_verifier as mv
    huge = "+x\n" * VERIFIER_DIFF_CHAR_CAP
    cf = type("CF", (), {"filename": "big.py", "patch": huge})()
    monkeypatch.setattr(mv, "get_pr_files", lambda *a, **k: [cf])
    called = {"n": 0}
    async def _must_not_call(system, user, **kw):
        called["n"] += 1
        return '{"safe": true, "manipulation_detected": false, "reasons": []}'
    monkeypatch.setattr(mv, "call_openai_verifier", _must_not_call)
    v = await mv.verify_merge_safety(_ctx())
    assert v.safe is False               # fail-closed 차단 / fail-closed block
    assert v.status == mv.VERIFIER_OK     # 정상 차단 결정 → VERIFIER_BLOCKED 매핑 / decided block
    assert called["n"] == 0               # OpenAI 미호출 / OpenAI not called


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
