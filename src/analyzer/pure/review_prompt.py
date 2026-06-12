"""Build language-aware AI review prompts with token budget management.

Phase 4 PR-12 (사이클 84) — i18n: language 인자 + system prompt 3 언어 분기 (출력 언어 지시).
Phase 4 PR-12 (Cycle 84) — i18n: language arg + system prompt 3-language branch (output dir).

핵심 결정 (key decisions):
- system prompt 본문 = 다국어 분기 (en/ko/ja) — AI 출력 언어 결정 영역
- user prompt template = 영문 라벨 통일 (토큰 절약, AI 응답 영향 0 — 정책 16 5번 원칙)
- review_guides Tier1/2/3 = 영문 보존 (PR-13/14/15 별도 진행 영역)
- caching cache key = system text hash 자동 분기 (language 별 독립 cache 자동 보장)

Token budget strategy:
- Fixed overhead (headers + diff + filenames): ~3000 tokens estimated
- Remaining budget allocated to language guides
- N ≤ 3 languages  → all FULL guides
- 4 ≤ N ≤ 6        → Tier 1 languages FULL, others COMPACT
- 7 ≤ N ≤ 10       → top 3 languages FULL, rest COMPACT
- N > 10            → top 5 COMPACT only, remaining listed by name
"""
from __future__ import annotations

from src.analyzer.pure.language import detect_language
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
_NONE_LABEL = "(none)"

# Phase 4 PR-12 — 출력 언어 지시 키 (system prompt 안 명시) — 3 언어 분기
# Phase 4 PR-12 — output language directive (in system prompt) — 3-language branch
_OUTPUT_LANGUAGE_DIRECTIVES: dict[str, str] = {
    "ko": "모든 응답 텍스트 (summary / suggestions / *_feedback / file_feedbacks 의 issues) 는 한국어로 작성하세요.",
    "en": "Write all response text (summary / suggestions / *_feedback / file_feedbacks issues) in English.",
    "ja": "全ての応答テキスト (summary / suggestions / *_feedback / file_feedbacks の issues) は日本語で記述してください。",
}


_SYSTEM_PROMPT_KO = """\
당신은 GitHub 코드 변경사항을 평가하는 시니어 코드 리뷰 시스템입니다.
사용자가 제공하는 커밋 메시지·파일 목록·diff 를 분석하고 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요.

{output_lang_directive}

채점 유의사항:
- 일반적으로 양호한 코드/커밋은 15~18점 범위에 해당합니다.
- 명확한 문제가 없다면 최소 12점 이상을 부여하세요.
- 0~5점은 명백히 잘못된 경우에만 부여하세요.
- 점수를 지나치게 보수적으로 낮추지 마세요.

응답 JSON 형식 (추가 텍스트 없이):
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

_SYSTEM_PROMPT_EN = """\
You are a senior code review system that evaluates GitHub code changes.
Analyze the provided commit message, file list, and diff, and respond ONLY in the JSON format below.
Do not include any other text.

{output_lang_directive}

Scoring guidelines:
- Generally good code/commits fall in the 15-18 point range.
- If there are no clear issues, award at least 12 points.
- 0-5 points only when clearly wrong.
- Do not be overly conservative.

Response JSON format (no extra text):
{{
  "commit_message_score": <0-20 integer, convention/clarity/scope alignment>,
  "direction_score": <0-20 integer, implementation direction/patterns/design fit>,
  "test_score": <0-10 integer, see scoring criteria below>,
  "summary": "<2-3 sentence change summary: what was changed and why>",
  "suggestions": ["<specific improvement (include filename:line)>"],
  "commit_message_feedback": "<commit message evaluation: convention adherence, clarity, scope alignment>",
  "code_quality_feedback": "<code quality: readability, naming, duplication, complexity>",
  "security_feedback": "<security: potential vulnerabilities, input validation, auth. If none: 'No security issues'>",
  "direction_feedback": "<implementation direction: design patterns, architecture fit, extensibility>",
  "test_feedback": "<test evaluation: existence, coverage adequacy, edge cases>",
  "file_feedbacks": [
    {{"file": "<filename>", "issues": ["<line N: specific issue description and fix>"]}}
  ]
}}

test_score criteria:
- 10: Only test-unnecessary files changed (.md, .cfg, .toml, .yml, .html, .json,
  Dockerfile, LICENSE, etc.) or sufficient tests included
- 7-9: Test code exists but coverage is partial (core paths only, missing edge cases)
- 4-6: Test files were modified but coverage for new code is insufficient
- 1-3: Tests needed but missing (change is simple so not severe)
- 0: Code change clearly requires tests but none exist"""

_SYSTEM_PROMPT_JA = """\
あなたは GitHub のコード変更を評価するシニアコードレビューシステムです。
ユーザーが提供するコミットメッセージ・ファイル一覧・diff を分析し、下記の JSON 形式のみで応答してください。他のテキストは含めないでください。

{output_lang_directive}

採点上の注意:
- 一般的に良好なコード/コミットは 15〜18 点の範囲に該当します。
- 明らかな問題がなければ最低 12 点以上を付与してください。
- 0〜5 点は明らかに誤っている場合のみ付与してください。
- スコアを過度に保守的に低くしないでください。

応答 JSON 形式 (追加テキストなし):
{{
  "commit_message_score": <0〜20 整数、規約遵守/明確性/変更範囲一致性>,
  "direction_score": <0〜20 整数、実装方向性/パターン/設計適合性>,
  "test_score": <0〜10 整数、下記の採点基準参照>,
  "summary": "<変更内容 2〜3 文要約: 何を なぜ 変更したか>",
  "suggestions": ["<具体的な改善提案 (ファイル名:行を含む)>"],
  "commit_message_feedback": "<コミットメッセージ評価: 規約遵守、明確性、変更範囲一致性に関する具体的フィードバック>",
  "code_quality_feedback": "<コード品質評価: 可読性、命名、重複、複雑度などの具体的フィードバック>",
  "security_feedback": "<セキュリティ評価: 潜在的脆弱性、入力検証、認証等のフィードバック。問題なければ '問題なし'>",
  "direction_feedback": "<実装方向性評価: 設計パターン、アーキテクチャ適合性、拡張性のフィードバック>",
  "test_feedback": "<テスト評価: テストの有無、カバレッジ、エッジケースの含有>",
  "file_feedbacks": [
    {{"file": "<ファイル名>", "issues": ["<行 N: 具体的な問題説明と修正方法>"]}}
  ]
}}

test_score 採点基準:
- 10: テスト不要ファイルのみ変更 (.md, .cfg, .toml, .yml, .html, .json, Dockerfile, LICENSE 等) または十分なテスト含有
- 7〜9: テストコードあるがカバレッジが部分的 (コアパスのみ、エッジケース不足)
- 4〜6: テストファイル修正ありだが新規コードに対するカバレッジ不足
- 1〜3: テスト必要だが未含有 (単純な変更で重大ではない)
- 0: テストが必須のコード変更だがテストなし"""


_SYSTEM_PROMPTS: dict[str, str] = {
    "ko": _SYSTEM_PROMPT_KO,
    "en": _SYSTEM_PROMPT_EN,
    "ja": _SYSTEM_PROMPT_JA,
}


_USER_PROMPT_TEMPLATE = """\
Commit message:
{commit_message}

Changed files:
{filenames}

Detected languages:
{detected_langs}

{lang_guides}Diff:
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


def _build_lang_guides(
    languages: list[str], budget_chars: int, output_language: str = "en",
) -> str:
    """토큰 예산 내에서 언어별 가이드 섹션을 조립한다 (Phase 4 PR-13 — output_language 전달).

    Build per-language guide section within token budget (Phase 4 PR-13 — output_language).
    """
    if not languages:
        return ""

    modes = _select_guide_modes(languages)
    parts: list[str] = []
    used_chars = 0

    for lang, mode in modes.items():
        if lang == "__rest__":
            snippet = f"Additional languages (brief review): {mode}\n"
        else:
            snippet = get_guide(lang, mode, output_language=output_language) + "\n"

        if used_chars + len(snippet) > budget_chars:
            if mode == "full":
                snippet = get_guide(lang, "compact", output_language=output_language) + "\n"
            if used_chars + len(snippet) > budget_chars:
                break

        parts.append(snippet)
        used_chars += len(snippet)

    if not parts:
        return ""
    return "## Per-language review criteria\n" + "".join(parts) + "\n"


def get_system_prompt(language: str = "en") -> str:
    """캐시 가능한 시스템 프롬프트 (정적, 모든 요청에 동일).

    Phase 4 PR-12 (사이클 84) — language 인자 추가 (en/ko/ja). language 별 system text 다름
    → Anthropic prompt cache key (system text hash) 자동 분기 → 언어별 독립 cache 자동 보장.

    Phase 4 PR-12 (Cycle 84) — language arg added (en/ko/ja). Different system text per
    language → cache key (system text hash) auto-diverges → per-language cache isolation.

    Anthropic prompt caching 의 cache_control 대상. ~600-800 tokens 으로
    1024 token 최소 캐시 한도에 미달할 수 있어 ai_review.py 에서
    cache_control 적용 시 길이 검증 권장 (현재는 시도 후 graceful fallback).
    """
    lang = language if language in _SYSTEM_PROMPTS else "en"
    template = _SYSTEM_PROMPTS[lang]
    directive = _OUTPUT_LANGUAGE_DIRECTIVES.get(lang, _OUTPUT_LANGUAGE_DIRECTIVES["en"])
    return template.format(output_lang_directive=directive)


def build_review_blocks(
    commit_message: str,
    patches: list[tuple[str, str]],
    budget_tokens: int = 8000,
    language: str = "en",
) -> tuple[str, str, list[str]]:
    """Phase 2 a-B (사이클 74) — Multi-block 확장 인프라 (system + user 분리).

    Phase 2 a-B (Cycle 74) — multi-block infra (system + user split).
    Phase 4 PR-12 — language 인자 추가 (현재는 lang_guides 영문 보존 — Tier1/2/3 다국어는 PR-13~15 영역).

    `build_review_prompt` 와 동일 입력이지만 `lang_guides` 를 system block 으로
    분리해 Anthropic prompt caching 의 추가 cache_control 적용 가능하게 함.
    호출자 (`ai_review.py`) 가 `lang_guides_block` 을 system 영역에 cache_control
    포함시키면 단일 언어 PR 반복 시 cache hit rate ↑ (효과 = 운영 데이터 의존).

    Returns:
        (lang_guides_block, user_prompt, languages):
        - lang_guides_block = "## Per-language review criteria\\n..." (cacheable system 영역, 빈 string 가능)
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
    # Phase 4 PR-13 — language 인자 전달 (Tier1 10 가이드 다국어, Tier2/3 영문 fallback)
    lang_guides_block = _build_lang_guides(languages, max(budget_chars, 0), output_language=language)

    detected_display = ", ".join(languages) if languages else "none"
    user_prompt = _USER_PROMPT_TEMPLATE.format(
        commit_message=commit_message or _NONE_LABEL,
        filenames=filenames or _NONE_LABEL,
        detected_langs=detected_display,
        lang_guides="",  # multi-block 시 user_prompt 안 lang_guides 비움 (system 영역으로 분리)
        diff_text=diff_text,
    )
    return lang_guides_block, user_prompt, languages


def build_review_prompt(
    commit_message: str,
    patches: list[tuple[str, str]],
    budget_tokens: int = 8000,
    language: str = "en",
) -> tuple[str, list[str]]:
    """언어-aware AI 리뷰 사용자 프롬프트를 생성한다 (시스템 프롬프트 제외).

    Phase 4 PR-12 (사이클 84) — language 인자 추가. 현재 user prompt template 은 영문 라벨 통일
    (정책 16 5번 원칙 — 토큰 절약 + AI 응답 영향 0). lang_guides Tier1/2/3 다국어는 PR-13~15 영역.

    Returns:
        (user_prompt_str, detected_languages)

    참고: 시스템 프롬프트(채점 가이드 + JSON 형식 명세)는 `get_system_prompt(language)` 로
    별도 조회. ai_review.py 가 system 파라미터에 cache_control 을 적용하면
    매 요청 시 ~600-800 tokens 의 입력 토큰 비용을 캐시 read 로 대체 가능
    (정가 대비 90% 절감, Anthropic 가격 정책 기준).
    Note: System prompt is fetched separately via `get_system_prompt(language)` so it
    can be sent with `cache_control`, replacing ~600-800 input tokens with
    cache reads at 1/10 the cost. Per-language system text auto-diverges cache key.
    """
    diff_text = "\n".join(
        f"--- {fname}\n{patch}" for fname, patch in patches
    )[:MAX_DIFF_CHARS]
    filenames = "\n".join(fname for fname, _ in patches)

    languages = detect_languages_from_patches(patches)

    budget_chars = budget_tokens * _CHARS_PER_TOKEN - _FIXED_TOKEN_OVERHEAD * _CHARS_PER_TOKEN
    # Phase 4 PR-13 — language 인자 전달 (Tier1 10 가이드 다국어)
    lang_guides = _build_lang_guides(languages, max(budget_chars, 0), output_language=language)

    detected_display = ", ".join(languages) if languages else "none"

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        commit_message=commit_message or _NONE_LABEL,
        filenames=filenames or _NONE_LABEL,
        detected_langs=detected_display,
        lang_guides=lang_guides,
        diff_text=diff_text,
    )
    return user_prompt, languages
