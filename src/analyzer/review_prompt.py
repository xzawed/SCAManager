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

from src.analyzer.language import detect_language, is_test_file
from src.analyzer.review_guides import get_guide, get_tier

MAX_DIFF_CHARS = 16000
_FIXED_TOKEN_OVERHEAD = 3000
_CHARS_PER_TOKEN = 4  # rough approximation


_PROMPT_HEADER = """\
다음 변경사항(코드, 문서, 설정 파일 등)과 커밋 메시지를 분석하고 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요.

커밋 메시지:
{commit_message}

변경된 파일 목록:
{filenames}

감지된 언어:
{detected_langs}

{lang_guides}
변경사항:
{diff_text}

채점 유의사항:
- 일반적으로 양호한 코드/커밋은 15~18점 범위에 해당합니다.
- 명확한 문제가 없다면 최소 12점 이상을 부여하세요.
- 0~5점은 명백히 잘못된 경우에만 부여하세요.
- 점수를 지나치게 보수적으로 낮추지 마세요.

다음 JSON만 응답 (추가 텍스트 없이):
{{
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
    {{"file": "<파일명>", "issues": ["<라인 N: 구체적 문제 설명과 수정 방법>"]}}
  ]
}}

test_score 채점 기준:
- 10: 테스트 불필요 파일만 변경됨(.md, .cfg, .toml, .yml, .html, .json, Dockerfile, LICENSE 등) 또는 충분한 테스트 포함
- 7~9: 테스트 코드 존재하나 커버리지가 부분적 (핵심 경로만 커버, 엣지케이스 부족 등)
- 4~6: 테스트 파일 수정이 있으나 새로운 코드에 대한 커버리지 부족
- 1~3: 테스트가 필요하지만 미포함 (단순한 변경이라 심각하지 않음)
- 0: 테스트가 반드시 필요한 코드 변경인데 테스트 전무"""


def detect_languages_from_patches(
    patches: list[tuple[str, str]],
) -> list[str]:
    """패치 목록에서 등장 언어를 빈도순으로 반환 (중복 제거)."""
    freq: dict[str, int] = {}
    for fname, _ in patches:
        lang = detect_language(fname)
        if lang != "unknown":
            freq[lang] = freq.get(lang, 0) + 1
    return sorted(freq, key=lambda l: -freq[l])


def _build_lang_guides(languages: list[str], budget_chars: int) -> str:
    """토큰 예산 내에서 언어별 가이드 섹션을 조립한다."""
    n = len(languages)
    if n == 0:
        return ""

    if n <= 3:
        modes = {lang: "full" for lang in languages}
    elif n <= 6:
        modes = {}
        for lang in languages:
            modes[lang] = "full" if get_tier(lang) == 1 else "compact"
    elif n <= 10:
        modes = {}
        for i, lang in enumerate(languages):
            modes[lang] = "full" if i < 3 else "compact"
    else:
        # 상위 5개만 compact, 나머지는 이름만
        modes = {lang: "compact" for lang in languages[:5]}
        rest = languages[5:]
        if rest:
            modes["__rest__"] = ", ".join(rest)

    parts: list[str] = []
    used_chars = 0

    for lang, mode in modes.items():
        if lang == "__rest__":
            snippet = f"추가 감지 언어 (간략 검토): {mode}\n"
        else:
            snippet = get_guide(lang, mode) + "\n"

        if used_chars + len(snippet) > budget_chars:
            # 예산 초과 시 compact로 다운그레이드
            if mode == "full":
                snippet = get_guide(lang, "compact") + "\n"
            if used_chars + len(snippet) > budget_chars:
                break

        parts.append(snippet)
        used_chars += len(snippet)

    if not parts:
        return ""
    return "## 언어별 검토 기준\n" + "".join(parts) + "\n"


def build_review_prompt(
    commit_message: str,
    patches: list[tuple[str, str]],
    budget_tokens: int = 8000,
) -> tuple[str, list[str]]:
    """언어-aware AI 리뷰 프롬프트를 생성한다.

    Returns:
        (prompt_str, detected_languages)
    """
    diff_text = "\n".join(
        f"--- {fname}\n{patch}" for fname, patch in patches
    )[:MAX_DIFF_CHARS]
    filenames = "\n".join(fname for fname, _ in patches)

    languages = detect_languages_from_patches(patches)

    budget_chars = budget_tokens * _CHARS_PER_TOKEN - _FIXED_TOKEN_OVERHEAD * _CHARS_PER_TOKEN
    lang_guides = _build_lang_guides(languages, max(budget_chars, 0))

    detected_display = ", ".join(languages) if languages else "감지 안 됨"

    prompt = _PROMPT_HEADER.format(
        commit_message=commit_message or "(없음)",
        filenames=filenames or "(없음)",
        detected_langs=detected_display,
        lang_guides=lang_guides,
        diff_text=diff_text,
    )
    return prompt, languages


def has_test_files(patches: list[tuple[str, str]]) -> bool:
    """패치 목록에 테스트 파일이 포함되어 있는지 확인."""
    for fname, _ in patches:
        lang = detect_language(fname)
        if is_test_file(fname, lang):
            return True
    return False
