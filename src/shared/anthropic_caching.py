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


def first_text_block(response: object) -> str:
    """Anthropic 응답에서 **첫 번째 text 블록**의 내용을 꺼낸다.

    🔴 왜 `response.content[0].text` 를 직접 쓰면 안 되는가 (2026-08-06 회고 P1 · R61):
    그 관용구는 **첫 블록이 항상 text 라고 가정**한다. 그러나 Messages API 의 `content` 는
    블록 **배열**이고, thinking(확장 사고)·tool_use 가 앞설 수 있다. 그러면
    `.text` 접근이 `AttributeError` 로 떨어지는데, 이 리포의 호출부 4곳은 전부
    `except Exception` 안에 있어 **조용히 삼켜진다** — 즉 모델이나 설정을 한 번 바꾸면
    AI 리뷰·인사이트가 **전량 사망**하고 원인은 로그에만 남는다.
    🔴 라벨은 호출부마다 다르다(#1458): `repo_insight_service` 는 이제 `internal_error`
    (벤더 아님이 드러난다), 나머지 3곳은 여전히 `api_error` 로 뭉뚱그린다.

    Do not use `response.content[0].text`: the first block is not guaranteed to be text
    (thinking / tool_use may precede it). All four call sites sit inside `except Exception`,
    so the AttributeError is swallowed silently; repo_insight_service now labels it
    `internal_error` (#1458) while the other three still collapse it into `api_error`.

    Args:
        response: Anthropic `Message` (또는 `.content` 를 갖는 동등 객체).

    Returns:
        첫 text 블록의 문자열.

    Raises:
        ValueError: text 블록이 하나도 없을 때. 🔴 조용히 `""` 를 반환하지 **않는다** —
            빈 문자열은 하류 `_parse_response` 에서 "빈 응답" 과 구별되지 않아
            *무엇이 잘못됐는지 모르는* 실패가 된다. 원인을 말하는 예외가 낫다.
    """
    blocks = getattr(response, "content", None) or []
    for block in blocks:
        # `type` 이 있으면 그것으로 판별(공식 계약), 없으면 `.text` 존재로 폴백(구 SDK·목).
        # Prefer the documented `type` discriminator; fall back to duck-typing for mocks.
        btype = getattr(block, "type", None)
        text = getattr(block, "text", None)
        # 🔴 판별 순서가 중요하다: **명시적으로 비-text 라고 선언한 블록만** 건너뛰고,
        #    나머지는 `.text` 가 문자열인지로 받는다. `btype is None` 만 허용하면
        #    `MagicMock` 목(`.type` 이 자동 생성돼 None 이 아니다)이 전부 탈락한다 —
        #    실제로 기존 테스트 20건이 이 과엄격을 잡았다.
        # Skip only blocks that explicitly declare a non-text type; otherwise duck-type on
        # `.text` being a str. A `btype is None` check alone would reject MagicMock stubs.
        if isinstance(btype, str) and btype != "text":
            continue
        if isinstance(text, str):
            return text
    kinds = [getattr(b, "type", type(b).__name__) for b in blocks]
    raise ValueError(
        f"Anthropic 응답에 text 블록이 없다 — 블록 구성: {kinds or '(빈 content)'}"
    )
