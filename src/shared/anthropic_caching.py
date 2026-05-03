"""Anthropic prompt caching 헬퍼 — 공용 모듈.

Anthropic Messages API 의 system 인자에 5분 ephemeral cache_control 을 적용해
input 토큰 비용을 1/10 로 절감 (cache hit 시). 동일 system prompt 가 5분 내
재사용되면 cache_read_input_tokens 로 카운트.

Anthropic prompt caching helper — shared module.
Applies 5-minute ephemeral `cache_control` to the Anthropic Messages API system
parameter so input cost drops 10× on cache hit. Reuse within 5 min reads from cache.

Phase 3 PR 1 — `src/analyzer/io/ai_review.py` 와 향후 `dashboard_service.py`
(insight_narrative — Phase 3 PR 2) 양쪽이 본 헬퍼를 재사용한다. 운영 opt-out 은
환경변수 DISABLE_PROMPT_CACHE=1 (또는 settings.disable_prompt_cache=True) 로 제어.

기획 근거: docs/design/2026-05-02-insight-dashboard-rework.md §5.3 Phase 3 PR 1.
"""
from src.config import settings


def build_cached_system_param(
    text: str, *, disable_cache: bool | None = None
) -> list[dict]:
    """Anthropic Messages API system 인자용 list 빌더 (선택적 cache_control 적용).

    Build a list for the Anthropic Messages API `system` parameter with optional
    `cache_control` (ephemeral, 5-min TTL).

    🔴 system text 는 user-invariant 의무 — Anthropic prompt cache key = system text hash.
    `f"user {uid} 데이터..."` 같은 사용자별 변수 삽입 시 cache hit rate 0% 폭락 (사이클 64
    회고 P1 학습). 사용자별 데이터는 `messages` user role 에 전달, system 은 task 명세 + 형식만.
    🔴 system text MUST be user-invariant — Anthropic cache key = system text hash.
    Embedding `f"user {uid} ..."` collapses cache hit rate to 0%. Put per-user data
    into `messages` user role; keep system to task spec + output format only.

    Args:
        text: system prompt 본문 (caller 가 길이 검증 책임 — Anthropic 권장 ≥1024 토큰).
              system prompt body (caller validates length — Anthropic recommends ≥1024 tokens).
              **user-invariant 의무 (위 docstring 참조)**.
        disable_cache: True 시 cache_control 미적용 (인자 우선).
                       None (default) 시 settings.disable_prompt_cache 따름.
                       True omits cache_control (arg wins).
                       None falls back to settings.disable_prompt_cache.

    Returns:
        cache 적용: [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]
        cache 미적용 (opt-out): [{"type": "text", "text": text}]
    """
    # 인자가 명시되면 settings 무관하게 인자 우선
    # Explicit arg overrides settings
    if disable_cache is None:
        disable_cache = bool(settings.disable_prompt_cache)

    block: dict = {"type": "text", "text": text}
    if not disable_cache:
        block["cache_control"] = {"type": "ephemeral"}
    return [block]
