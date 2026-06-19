"""OpenAI 검증자 클라이언트 — SDK 우선, 미설치 환경은 httpx raw API fallback.
OpenAI verifier client — SDK-first, httpx raw-API fallback for SDK-less environments.

Claude 의 anthropic.AsyncAnthropic 패턴 미러 (timeout/max_retries 명시, 호출당 client + aclose).
Mirrors the anthropic.AsyncAnthropic pattern (explicit timeout/max_retries, per-call client + aclose).
"""
import logging
import time

from src.constants import VERIFIER_MAX_OUTPUT_TOKENS
from src.shared.http_client import get_http_client
from src.shared.openai_metrics import aclose_openai_client, extract_openai_usage, log_openai_api_call

logger = logging.getLogger(__name__)

# OpenAI Chat Completions 엔드포인트 URL
# OpenAI Chat Completions endpoint URL
_OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"


async def call_openai_verifier(
    system_prompt: str, user_prompt: str, *, api_key: str, model: str, timeout: float,
    max_output_tokens: int = VERIFIER_MAX_OUTPUT_TOKENS, base_url: str = "",
) -> str:
    """OpenAI Chat Completions 로 검증 호출 -> 응답 텍스트(JSON 문자열) 반환.
    Call OpenAI Chat Completions for verification -> return response text (JSON string).

    네트워크/API 오류는 raise (호출자가 fail-closed 처리). SDK 미설치 시 httpx fallback.
    Network/API errors are re-raised (caller handles fail-closed). Falls back to httpx if SDK absent.

    max_output_tokens: 응답 토큰 상한(비용 폭증 방어, #859 회고 P1-4) — gpt-5 계열 reasoning 포함.
    max_output_tokens: response token cap (cost-blowup guard, #859 retro P1-4) — incl. gpt-5 reasoning.

    base_url: 빈 값이면 OpenAI 기본 엔드포인트. OpenAI-호환 무료/저가 공급자(GitHub Models 등) 전환용.
    base_url: empty = OpenAI default endpoint; set to switch to an OpenAI-compatible provider.
    """
    start = time.perf_counter()
    client = None
    try:
        import openai  # pylint: disable=import-outside-toplevel
        # 호출당 클라이언트 생성 — anthropic.AsyncAnthropic 패턴 미러. base_url 빈 값이면 None → OpenAI 기본.
        # Per-call client creation — mirrors anthropic.AsyncAnthropic pattern. Empty base_url → None → OpenAI default.
        client = openai.AsyncOpenAI(
            api_key=api_key, base_url=(base_url or None), timeout=timeout, max_retries=2)
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=max_output_tokens,
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
            system_prompt, user_prompt, api_key=api_key, model=model, timeout=timeout,
            start=start, max_output_tokens=max_output_tokens, base_url=base_url)
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
    max_output_tokens: int = VERIFIER_MAX_OUTPUT_TOKENS, base_url: str = "",
) -> str:
    """openai SDK 미설치 fallback — 신뢰 API httpx 풀로 직접 호출.
    Fallback when openai SDK is absent — calls the API directly via the shared httpx pool.

    base_url 지정 시 {base_url}/chat/completions 로 POST(후행 슬래시 정규화), 빈 값이면 OpenAI 기본.
    With base_url set, POST to {base_url}/chat/completions (trailing-slash normalized); empty = OpenAI default.
    """
    chat_url = (base_url.rstrip("/") + "/chat/completions") if base_url else _OPENAI_CHAT_URL
    client = get_http_client()
    try:
        resp = await client.post(
            chat_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
                "max_completion_tokens": max_output_tokens,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # pylint: disable=broad-exception-caught  # noqa: BLE001
        # SDK 경로(call_openai_verifier except Exception)와 대칭 — fallback 실패도 메트릭 기록 후 re-raise.
        # 이 try/except 가 없으면 예외가 부모의 `except ImportError` 안에서 발생해 형제
        # `except Exception` 메트릭 로깅을 우회 → 관측성 비대칭(status=error 소실).
        # Mirrors the SDK path: log status=error then re-raise. Without this, the exception raised
        # inside the parent's ImportError handler would bypass the sibling except Exception logger.
        log_openai_api_call(
            model=model, duration_ms=(time.perf_counter() - start) * 1000,
            input_tokens=0, output_tokens=0, status="error", error_type=type(exc).__name__,
        )
        raise
    usage = data.get("usage") or {}
    log_openai_api_call(
        model=model, duration_ms=(time.perf_counter() - start) * 1000,
        input_tokens=int(usage.get("prompt_tokens", 0) or 0),
        output_tokens=int(usage.get("completion_tokens", 0) or 0), status="success",
    )
    # 응답 텍스트 추출 — choices[0].message.content, 없으면 빈 문자열
    # Extract response text — choices[0].message.content, empty string if absent
    return (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
