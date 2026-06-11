"""OpenAI 검증자 클라이언트 — SDK 우선, 미설치 환경은 httpx raw API fallback.
OpenAI verifier client — SDK-first, httpx raw-API fallback for SDK-less environments.

Claude 의 anthropic.AsyncAnthropic 패턴 미러 (timeout/max_retries 명시, 호출당 client + aclose).
Mirrors the anthropic.AsyncAnthropic pattern (explicit timeout/max_retries, per-call client + aclose).
"""
import logging
import time

from src.shared.http_client import get_http_client
from src.shared.openai_metrics import aclose_openai_client, extract_openai_usage, log_openai_api_call

logger = logging.getLogger(__name__)

# OpenAI Chat Completions 엔드포인트 URL
# OpenAI Chat Completions endpoint URL
_OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"


async def call_openai_verifier(
    system_prompt: str, user_prompt: str, *, api_key: str, model: str, timeout: float,
) -> str:
    """OpenAI Chat Completions 로 검증 호출 -> 응답 텍스트(JSON 문자열) 반환.
    Call OpenAI Chat Completions for verification -> return response text (JSON string).

    네트워크/API 오류는 raise (호출자가 fail-closed 처리). SDK 미설치 시 httpx fallback.
    Network/API errors are re-raised (caller handles fail-closed). Falls back to httpx if SDK absent.
    """
    start = time.perf_counter()
    client = None
    try:
        import openai  # pylint: disable=import-outside-toplevel
        # 호출당 클라이언트 생성 — anthropic.AsyncAnthropic 패턴 미러
        # Per-call client creation — mirrors anthropic.AsyncAnthropic pattern
        client = openai.AsyncOpenAI(api_key=api_key, timeout=timeout, max_retries=2)
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        in_tok, out_tok = extract_openai_usage(resp)
        log_openai_api_call(
            model=model, duration_ms=(time.perf_counter() - start) * 1000,
            input_tokens=in_tok, output_tokens=out_tok, status="success",
        )
        return resp.choices[0].message.content or ""
    except ImportError:
        # SDK 미설치 → httpx 직접 호출 fallback
        # SDK not installed → fall back to direct httpx call
        return await _call_via_http(
            system_prompt, user_prompt, api_key=api_key, model=model, timeout=timeout, start=start)
    except Exception as exc:  # pylint: disable=broad-exception-caught  # noqa: BLE001
        # 오류 메트릭 기록 후 재 raise — 호출자 fail-closed 처리
        # Log error metrics then re-raise — caller performs fail-closed handling
        log_openai_api_call(
            model=model, duration_ms=(time.perf_counter() - start) * 1000,
            input_tokens=0, output_tokens=0, status="error", error_type=type(exc).__name__,
        )
        raise
    finally:
        if client is not None:
            await aclose_openai_client(client)


async def _call_via_http(
    system_prompt: str, user_prompt: str, *, api_key: str, model: str, timeout: float, start: float,
) -> str:
    """openai SDK 미설치 fallback — 신뢰 API httpx 풀로 직접 호출.
    Fallback when openai SDK is absent — calls the API directly via the shared httpx pool.
    """
    client = get_http_client()
    resp = await client.post(
        _OPENAI_CHAT_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    usage = data.get("usage") or {}
    log_openai_api_call(
        model=model, duration_ms=(time.perf_counter() - start) * 1000,
        input_tokens=int(usage.get("prompt_tokens", 0) or 0),
        output_tokens=int(usage.get("completion_tokens", 0) or 0), status="success",
    )
    # 응답 텍스트 추출 — choices[0].message.content, 없으면 빈 문자열
    # Extract response text — choices[0].message.content, empty string if absent
    return (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
