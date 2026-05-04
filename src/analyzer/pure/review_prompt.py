"""Build language-aware AI review prompts with token budget management.

Token budget strategy:
- Fixed overhead (headers + diff + filenames): ~3000 tokens estimated
- Remaining budget allocated to language guides
- N ≤ 3 languages  → all FULL guides
- 4 ≤ N ≤ 6        → Tier 1 languages FULL, others COMPACT
- 7 ≤ N ≤ 10       → top 3 languages FULL, rest COMPACT
- N > 10            → top 5 COMPACT only, remaining listed by name
"""
from __future__ import annotations

from src.analyzer.pure.language import detect_language, is_test_file
from src.analyzer.pure.review_guides import get_guide, get_tier
from src.constants import (
    LANG_GUIDE_ALL_FULL_MAX,
    LANG_GUIDE_TIER1_FULL_MAX,
    LANG_GUIDE_TOP3_FULL_MAX,
    LANG_GUIDE_COMPACT_LIMIT,
)

MAX_DIFF_CHARS = 16000
_FIXED_TOKEN_OVERHEAD = 3000
_CHARS_PER_TOKEN = 4  # rough approximation


_SYSTEM_PROMPT = """\
당신은 GitHub 코드 변경사항을 평가하는 시니어 코드 리뷰 시스템입니다.
사용자가 제공하는 커밋 메시지·파일 목록·diff 를 분석하고 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요.

채점 유의사항:
- 일반적으로 양호한 코드/커밋은 15~18점 범위에 해당합니다.
- 명확한 문제가 없다면 최소 12점 이상을 부여하세요.
- 0~5점은 명백히 잘못된 경우에만 부여하세요.
- 점수를 지나치게 보수적으로 낮추지 마세요.

응답 JSON 형식 (추가 텍스트 없이):
{
  "commit_message_score": <0~20 정수, 컨벤션 준수/명확성/변경범위 일치성>,
  "direction_score": <0~20 정수, 구현 방향성/패턴/설계 적합성>,
  "test_score": <0~10 정수, 아래 채점 기준 참고>,
  "summary": "<변경사항 2~3문장 요약: 무엇을 왜 변경했는지>",
  "suggestions": ["<구체적 개선 제안 (파일명:라인 포함)>"],
  "commit_message_feedback": "<커밋 메시지 평가: 컨벤션 준수 여부, 명확성, 변경범위 일치성에 대한 구체적 피드백>",
  "code_quality_feedback": "<코드 품질 평가: 가독성, 네이밍, 중복, 복잡도 등 구체적 피드백>",
  "security_feedback": "<보안 평가: 잠재적 보안 취약점, 입력 검증, 인증 등에 대한 피드백. 이슈 없으면 '보안 이슈 없음'>",
  "direction_feedback": "<구현 방향성 평가: 설계 패턴, 아키텍처 적합성, 확장성에 대한 피드백>",
  "test_feedback": "<테스트 평가: 테스트 존재 여부, 커버리지 충분성, 엣지케이스 포함 여부>",
  "file_feedbacks": [
    {"file": "<파일명>", "issues": ["<라인 N: 구체적 문제 설명과 수정 방법>"]}
  ]
}

test_score 채점 기준:
- 10: 테스트 불필요 파일만 변경됨(.md, .cfg, .toml, .yml, .html, .json, Dockerfile, LICENSE 등) 또는 충분한 테스트 포함
- 7~9: 테스트 코드 존재하나 커버리지가 부분적 (핵심 경로만 커버, 엣지케이스 부족 등)
- 4~6: 테스트 파일 수정이 있으나 새로운 코드에 대한 커버리지 부족
- 1~3: 테스트가 필요하지만 미포함 (단순한 변경이라 심각하지 않음)
- 0: 테스트가 반드시 필요한 코드 변경인데 테스트 전무"""


_USER_PROMPT_TEMPLATE = """\
커밋 메시지:
{commit_message}

변경된 파일 목록:
{filenames}

감지된 언어:
{detected_langs}

{lang_guides}
변경사항:
{diff_text}"""


def detect_languages_from_patches(
    patches: list[tuple[str, str]],
) -> list[str]:
    """패치 목록에서 등장 언어를 빈도순으로 반환 (중복 제거)."""
    freq: dict[str, int] = {}
    for fname, _ in patches:
        lang = detect_language(fname)
        if lang != "unknown":
            freq[lang] = freq.get(lang, 0) + 1
    return sorted(freq, key=lambda lang: -freq[lang])


def _select_guide_modes(languages: list[str]) -> dict[str, str]:
    """언어 목록에서 각 언어의 가이드 모드를 결정한다 (full / compact / __rest__)."""
    n = len(languages)
    if n <= LANG_GUIDE_ALL_FULL_MAX:
        return {lang: "full" for lang in languages}
    if n <= LANG_GUIDE_TIER1_FULL_MAX:
        return {lang: ("full" if get_tier(lang) == 1 else "compact") for lang in languages}
    if n <= LANG_GUIDE_TOP3_FULL_MAX:
        return {lang: ("full" if i < 3 else "compact") for i, lang in enumerate(languages)}
    modes = {lang: "compact" for lang in languages[:LANG_GUIDE_COMPACT_LIMIT]}
    rest = languages[LANG_GUIDE_COMPACT_LIMIT:]
    if rest:
        modes["__rest__"] = ", ".join(rest)
    return modes


def _build_lang_guides(languages: list[str], budget_chars: int) -> str:
    """토큰 예산 내에서 언어별 가이드 섹션을 조립한다."""
    if not languages:
        return ""

    modes = _select_guide_modes(languages)
    parts: list[str] = []
    used_chars = 0

    for lang, mode in modes.items():
        if lang == "__rest__":
            snippet = f"추가 감지 언어 (간략 검토): {mode}\n"
        else:
            snippet = get_guide(lang, mode) + "\n"

        if used_chars + len(snippet) > budget_chars:
            if mode == "full":
                snippet = get_guide(lang, "compact") + "\n"
            if used_chars + len(snippet) > budget_chars:
                break

        parts.append(snippet)
        used_chars += len(snippet)

    if not parts:
        return ""
    return "## 언어별 검토 기준\n" + "".join(parts) + "\n"


def get_system_prompt() -> str:
    """캐시 가능한 시스템 프롬프트 (정적, 모든 요청에 동일).

    Anthropic prompt caching 의 cache_control 대상. ~600-800 tokens 으로
    1024 token 최소 캐시 한도에 미달할 수 있어 ai_review.py 에서
    cache_control 적용 시 길이 검증 권장 (현재는 시도 후 graceful fallback).
    """
    return _SYSTEM_PROMPT


def build_review_blocks(
    commit_message: str,
    patches: list[tuple[str, str]],
    budget_tokens: int = 8000,
) -> tuple[str, str, list[str]]:
    """Phase 2 a-B (사이클 74) — Multi-block 확장 인프라 (system + user 분리).

    Phase 2 a-B (Cycle 74) — multi-block infra (system + user split).

    `build_review_prompt` 와 동일 입력이지만 `lang_guides` 를 system block 으로
    분리해 Anthropic prompt caching 의 추가 cache_control 적용 가능하게 함.
    호출자 (`ai_review.py`) 가 `lang_guides_block` 을 system 영역에 cache_control
    포함시키면 단일 언어 PR 반복 시 cache hit rate ↑ (효과 = 운영 데이터 의존).

    Returns:
        (lang_guides_block, user_prompt, languages):
        - lang_guides_block = "## 언어별 검토 기준\\n..." (cacheable system 영역, 빈 string 가능)
        - user_prompt = commit_message + filenames + diff_text (PR 별 가변, 매번 새 토큰)
        - languages = detected languages list

    참고: 본 helper 는 인프라만 — `ai_review.py` 호출부 변경은 별도 PR (운영 데이터 후 결정).
    Note: this is infra only — caller migration is a separate PR (post-baseline).
    """
    diff_text = "\n".join(
        f"--- {fname}\n{patch}" for fname, patch in patches
    )[:MAX_DIFF_CHARS]
    filenames = "\n".join(fname for fname, _ in patches)
    languages = detect_languages_from_patches(patches)

    budget_chars = budget_tokens * _CHARS_PER_TOKEN - _FIXED_TOKEN_OVERHEAD * _CHARS_PER_TOKEN
    lang_guides_block = _build_lang_guides(languages, max(budget_chars, 0))

    detected_display = ", ".join(languages) if languages else "감지 안 됨"
    user_prompt = _USER_PROMPT_TEMPLATE.format(
        commit_message=commit_message or "(없음)",
        filenames=filenames or "(없음)",
        detected_langs=detected_display,
        lang_guides="",  # multi-block 시 user_prompt 안 lang_guides 비움 (system 영역으로 분리)
        diff_text=diff_text,
    )
    return lang_guides_block, user_prompt, languages


def build_review_prompt(
    commit_message: str,
    patches: list[tuple[str, str]],
    budget_tokens: int = 8000,
) -> tuple[str, list[str]]:
    """언어-aware AI 리뷰 사용자 프롬프트를 생성한다 (시스템 프롬프트 제외).

    Returns:
        (user_prompt_str, detected_languages)

    참고: 시스템 프롬프트(채점 가이드 + JSON 형식 명세)는 `get_system_prompt()` 로
    별도 조회. ai_review.py 가 system 파라미터에 cache_control 을 적용하면
    매 요청 시 ~600-800 tokens 의 입력 토큰 비용을 캐시 read 로 대체 가능
    (정가 대비 90% 절감, Anthropic 가격 정책 기준).
    Note: System prompt is fetched separately via `get_system_prompt()` so it
    can be sent with `cache_control`, replacing ~600-800 input tokens with
    cache reads at 1/10 the cost.
    """
    diff_text = "\n".join(
        f"--- {fname}\n{patch}" for fname, patch in patches
    )[:MAX_DIFF_CHARS]
    filenames = "\n".join(fname for fname, _ in patches)

    languages = detect_languages_from_patches(patches)

    budget_chars = budget_tokens * _CHARS_PER_TOKEN - _FIXED_TOKEN_OVERHEAD * _CHARS_PER_TOKEN
    lang_guides = _build_lang_guides(languages, max(budget_chars, 0))

    detected_display = ", ".join(languages) if languages else "감지 안 됨"

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        commit_message=commit_message or "(없음)",
        filenames=filenames or "(없음)",
        detected_langs=detected_display,
        lang_guides=lang_guides,
        diff_text=diff_text,
    )
    return user_prompt, languages


def has_test_files(patches: list[tuple[str, str]]) -> bool:
    """패치 목록에 테스트 파일이 포함되어 있는지 확인."""
    for fname, _ in patches:
        lang = detect_language(fname)
        if is_test_file(fname, lang):
            return True
    return False
