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


# httpx fallback 경로 (#859 회고 P2) — openai SDK 미설치 시 _call_via_http 강제
# httpx fallback path — force ImportError so _call_via_http is exercised (SDK-less env)


class _FakeHttpResp:
    def __init__(self, payload, *, boom=False):
        self._payload = payload
        self._boom = boom

    def raise_for_status(self):
        if self._boom:
            raise RuntimeError("http 500")

    def json(self):
        return self._payload


def _force_sdk_absent(monkeypatch):
    import sys
    # sys.modules["openai"] = None → `import openai` 가 ImportError 발생 (SDK 미설치 모사)
    # None in sys.modules makes `import openai` raise ImportError (simulates SDK absence)
    monkeypatch.setitem(sys.modules, "openai", None)


@pytest.mark.asyncio
async def test_call_openai_verifier_falls_back_to_http_when_sdk_absent(monkeypatch):
    _force_sdk_absent(monkeypatch)
    payload = {"choices": [{"message": {"content": json.dumps({"safe": True})}}],
               "usage": {"prompt_tokens": 11, "completion_tokens": 3}}

    class _FakeHttpClient:
        async def post(self, url, **kwargs):
            # 정확한 엔드포인트 URL 비교 — 부분 문자열 검사(`"openai.com" in url`)는
            # CodeQL py/incomplete-url-substring-sanitization(우회 가능) 이라 정확 비교 사용
            # Exact endpoint comparison — substring checks trip CodeQL's URL sanitization rule
            assert url == openai_client._OPENAI_CHAT_URL
            assert kwargs["json"]["response_format"] == {"type": "json_object"}
            assert kwargs["headers"]["Authorization"] == "Bearer k"
            return _FakeHttpResp(payload)

    monkeypatch.setattr(openai_client, "get_http_client", lambda: _FakeHttpClient())
    text = await openai_client.call_openai_verifier(
        "SYS", "USER", api_key="k", model="gpt-5-mini", timeout=5.0)
    assert json.loads(text)["safe"] is True


# max_completion_tokens 상한 회귀 가드 (#859 회고 P1-4) — 응답 토큰 폭증 방어 (SDK + httpx 양 경로)
# max_completion_tokens cap regression guards (#859 retro P1-4) — bound response tokens on both SDK + httpx paths


@pytest.mark.asyncio
async def test_call_openai_verifier_passes_max_completion_tokens(monkeypatch):
    from src.constants import VERIFIER_MAX_OUTPUT_TOKENS
    seen = {}

    class _CapCompletions:
        async def create(self, **kwargs):
            seen.update(kwargs)
            return _FakeResp(json.dumps({"safe": True, "manipulation_detected": False, "reasons": []}))

    class _CapChat:
        completions = _CapCompletions()

    class _CapClient:
        def __init__(self, **kwargs):
            self.chat = _CapChat()
        async def aclose(self):
            pass

    import openai as _openai
    monkeypatch.setattr(_openai, "AsyncOpenAI", _CapClient)
    await openai_client.call_openai_verifier(
        "SYS", "USER", api_key="k", model="gpt-5-mini", timeout=5.0)
    assert seen.get("max_completion_tokens") == VERIFIER_MAX_OUTPUT_TOKENS


@pytest.mark.asyncio
async def test_http_fallback_passes_max_completion_tokens(monkeypatch):
    from src.constants import VERIFIER_MAX_OUTPUT_TOKENS
    _force_sdk_absent(monkeypatch)
    payload = {"choices": [{"message": {"content": json.dumps({"safe": True})}}],
               "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
    seen = {}

    class _CapHttpClient:
        async def post(self, url, **kwargs):
            seen.update(kwargs.get("json", {}))
            return _FakeHttpResp(payload)

    monkeypatch.setattr(openai_client, "get_http_client", lambda: _CapHttpClient())
    await openai_client.call_openai_verifier(
        "SYS", "USER", api_key="k", model="gpt-5-mini", timeout=5.0)
    assert seen.get("max_completion_tokens") == VERIFIER_MAX_OUTPUT_TOKENS


@pytest.mark.asyncio
async def test_http_fallback_reraises_on_api_error_fail_closed(monkeypatch):
    # fallback 경로도 API 오류를 re-raise 해야 호출자가 fail-closed 처리 가능
    # The fallback path must also re-raise so the caller can fail closed
    _force_sdk_absent(monkeypatch)

    class _BoomHttpClient:
        async def post(self, url, **kwargs):
            return _FakeHttpResp({}, boom=True)

    monkeypatch.setattr(openai_client, "get_http_client", lambda: _BoomHttpClient())
    with pytest.raises(RuntimeError):
        await openai_client.call_openai_verifier(
            "SYS", "USER", api_key="k", model="gpt-5-mini", timeout=5.0)
