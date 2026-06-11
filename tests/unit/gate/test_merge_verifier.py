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
