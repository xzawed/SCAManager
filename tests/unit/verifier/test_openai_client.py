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


import json

import pytest

from src.verifier import openai_client


class _FakeUsage:
    prompt_tokens = 50
    completion_tokens = 10


class _FakeChoice:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class _FakeResp:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage()


@pytest.mark.asyncio
async def test_call_openai_verifier_returns_content_text(monkeypatch):
    payload = json.dumps({"safe": True, "manipulation_detected": False, "reasons": []})

    class _FakeCompletions:
        async def create(self, **kwargs):
            assert kwargs["response_format"] == {"type": "json_object"}
            return _FakeResp(payload)

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        def __init__(self, **kwargs):
            self.chat = _FakeChat()
        async def aclose(self):
            pass

    import openai as _openai
    monkeypatch.setattr(_openai, "AsyncOpenAI", _FakeClient)
    text = await openai_client.call_openai_verifier(
        "SYS", "USER", api_key="k", model="gpt-5-mini", timeout=5.0)
    assert json.loads(text)["safe"] is True


@pytest.mark.asyncio
async def test_call_openai_verifier_raises_on_api_error(monkeypatch):
    class _BoomCompletions:
        async def create(self, **kwargs):
            raise RuntimeError("boom")

    class _BoomChat:
        completions = _BoomCompletions()

    class _BoomClient:
        def __init__(self, **kwargs):
            self.chat = _BoomChat()
        async def aclose(self):
            pass

    import openai as _openai
    monkeypatch.setattr(_openai, "AsyncOpenAI", _BoomClient)
    with pytest.raises(RuntimeError):
        await openai_client.call_openai_verifier(
            "SYS", "USER", api_key="k", model="gpt-5-mini", timeout=5.0)
