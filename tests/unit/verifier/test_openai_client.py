from types import SimpleNamespace

from src.shared import openai_metrics


def test_extract_openai_usage_reads_prompt_completion_tokens():
    resp = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=120, completion_tokens=30))
    assert openai_metrics.extract_openai_usage(resp) == (120, 30)


def test_extract_openai_usage_missing_usage_returns_zero():
    assert openai_metrics.extract_openai_usage(SimpleNamespace()) == (0, 0)


def test_log_openai_api_call_does_not_raise():
    openai_metrics.log_openai_api_call(
        model="gpt-5-mini", duration_ms=12.0,
        input_tokens=100, output_tokens=20, status="success",
    )
