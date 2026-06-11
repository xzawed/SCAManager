from src.gate import merge_reasons


def test_verifier_reason_tags_exist_and_terminal():
    assert merge_reasons.VERIFIER_BLOCKED == "verifier_blocked"
    assert merge_reasons.VERIFIER_ERROR == "verifier_error"
    # 검증자 차단은 재시도 대상 아님(터미널) — 재시도해도 같은 판정
    # Verifier block is not retriable (terminal) — retrying yields the same verdict
    assert merge_reasons.is_retriable_tag(merge_reasons.VERIFIER_BLOCKED) is False
    assert merge_reasons.is_retriable_tag(merge_reasons.VERIFIER_ERROR) is False
