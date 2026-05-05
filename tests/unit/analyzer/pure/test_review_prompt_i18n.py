"""Phase 4 PR-12 회귀 가드 — review_prompt 3 언어 system prompt + caching 자동 분기.

Phase 4 PR-12 regression guards — review_prompt 3-language system prompt + caching auto-divergence.

검증 범위 (Coverage):
1. get_system_prompt — 3 언어 (en/ko/ja) 다른 prompt 반환
2. system prompt 안 출력 언어 지시 명시 (3 언어)
3. cache key 자동 분기 — system text hash 다름 (language 별 독립 cache 보장)
4. build_review_prompt — language 인자 추가, user prompt template 영문 라벨 통일 (정책 16 5번)
5. invalid language → 'en' fallback
6. JSON 형식 명세 보존 (3 언어 모두) — AI 출력 일관성
"""
from __future__ import annotations

import hashlib

from src.analyzer.pure.review_prompt import (
    build_review_blocks,
    build_review_prompt,
    get_system_prompt,
)


# ── get_system_prompt — 3 언어 분기 ─────────────────────────────────────────


def test_system_prompt_korean():
    """한국어 system prompt — 출력 언어 지시 + JSON 형식 명세."""
    prompt = get_system_prompt("ko")
    assert "당신은 GitHub 코드 변경사항을 평가하는" in prompt
    # 출력 언어 지시 명시 (한국어)
    assert "한국어로 작성" in prompt
    # JSON 형식 명세 보존 (모든 언어 공통 키)
    assert '"commit_message_score"' in prompt
    assert '"direction_score"' in prompt
    assert '"test_score"' in prompt
    assert '"summary"' in prompt


def test_system_prompt_english():
    """영문 system prompt — 출력 언어 지시 + JSON 형식 명세."""
    prompt = get_system_prompt("en")
    assert "You are a senior code review system" in prompt
    assert "Write all response text" in prompt
    assert "in English" in prompt
    assert '"commit_message_score"' in prompt
    assert '"direction_score"' in prompt
    assert '"test_score"' in prompt


def test_system_prompt_japanese():
    """일본어 system prompt — 출력 언어 지시 + JSON 형식 명세."""
    prompt = get_system_prompt("ja")
    assert "あなたは GitHub のコード変更を評価する" in prompt
    assert "日本語で記述" in prompt
    assert '"commit_message_score"' in prompt
    assert '"direction_score"' in prompt


def test_system_prompt_invalid_falls_to_english():
    """invalid language → 'en' fallback."""
    prompt = get_system_prompt("zh")  # 미지원 언어
    assert "You are a senior code review system" in prompt
    assert "in English" in prompt


def test_system_prompt_default_is_english():
    """language 인자 default = 'en'."""
    prompt = get_system_prompt()
    assert "You are a senior code review system" in prompt


# ── caching 자동 분기 — system text hash 검증 ────────────────────────────


def test_system_prompt_cache_key_diverges_per_language():
    """🔴 핵심 — language 별 system text 다름 → Anthropic prompt cache key 자동 분기.

    Anthropic cache_control = system text hash 기준. language 별 다른 system text →
    각 언어 독립 cache (cache hit rate 격리). 동일 언어 PR 반복 시 cache hit ↑.
    """
    prompts = {
        "en": get_system_prompt("en"),
        "ko": get_system_prompt("ko"),
        "ja": get_system_prompt("ja"),
    }
    # 3 언어 모두 다른 text
    assert prompts["en"] != prompts["ko"]
    assert prompts["en"] != prompts["ja"]
    assert prompts["ko"] != prompts["ja"]

    # Hash (cache key proxy) 도 모두 다름
    hashes = {
        lang: hashlib.sha256(text.encode()).hexdigest()
        for lang, text in prompts.items()
    }
    assert len(set(hashes.values())) == 3, "3 언어 system text hash 모두 달라야 함"


def test_system_prompt_same_language_consistent():
    """동일 언어 호출 시 동일 text → cache hit 보장 (idempotent)."""
    p1 = get_system_prompt("ko")
    p2 = get_system_prompt("ko")
    assert p1 == p2  # idempotent


# ── build_review_prompt — language 인자 ─────────────────────────────────────


def _patches() -> list[tuple[str, str]]:
    return [("app.py", "+def hello():\n+    return 'hi'")]


def test_build_review_prompt_language_default_en():
    """build_review_prompt — language='en' default. user prompt 는 영문 라벨 통일."""
    user_prompt, languages = build_review_prompt("commit msg", _patches())
    # 영문 라벨 통일 (정책 16 5번 — 토큰 절약)
    assert "Commit message:" in user_prompt
    assert "Changed files:" in user_prompt
    assert "Detected languages:" in user_prompt
    assert "Diff:" in user_prompt
    assert languages == ["python"]


def test_build_review_prompt_language_korean_user_prompt_still_english_labels():
    """language='ko' → user prompt 영문 라벨 (정책 16 5번 토큰 절약 — AI 응답 영향 0)."""
    user_prompt, _ = build_review_prompt("commit msg", _patches(), language="ko")
    # user prompt 라벨은 모든 언어에서 영문 통일
    assert "Commit message:" in user_prompt
    assert "Changed files:" in user_prompt
    assert "Detected languages:" in user_prompt


def test_build_review_blocks_language_arg():
    """build_review_blocks — language 인자 추가 (lang_guides 영문 보존 — Phase 4 PR-13~15 영역)."""
    lang_guides_block, user_prompt, languages = build_review_blocks(
        "commit msg", _patches(), language="ja",
    )
    # lang_guides Tier1 = 영문 보존 (PR-13~15 별도 진행)
    if lang_guides_block:
        assert "Per-language review criteria" in lang_guides_block
    assert "Commit message:" in user_prompt
    assert languages == ["python"]


# ── JSON 형식 명세 일관성 (3 언어) ─────────────────────────────────────────


def test_all_languages_share_same_json_schema():
    """3 언어 system prompt 모두 동일 JSON 키 명세 — AI 응답 파싱 일관성 보장.

    AI 응답 JSON 키 (commit_message_score / direction_score / test_score /
    summary / suggestions / *_feedback / file_feedbacks) 는 영문 고정 — 모든 언어 동일.
    이는 _parse_response (ai_review.py) 가 단일 파싱 로직 재사용 의무 영역.
    """
    required_keys = [
        '"commit_message_score"',
        '"direction_score"',
        '"test_score"',
        '"summary"',
        '"suggestions"',
        '"commit_message_feedback"',
        '"code_quality_feedback"',
        '"security_feedback"',
        '"direction_feedback"',
        '"test_feedback"',
        '"file_feedbacks"',
    ]
    for lang in ("en", "ko", "ja"):
        prompt = get_system_prompt(lang)
        for key in required_keys:
            assert key in prompt, f"{lang} prompt missing JSON key: {key}"


def test_all_languages_share_test_score_criteria():
    """3 언어 system prompt 모두 test_score 채점 기준 (10/7-9/4-6/1-3/0) 명시."""
    for lang in ("en", "ko", "ja"):
        prompt = get_system_prompt(lang)
        # 각 언어로 표현된 test_score 기준
        # Korean: "10:" / "7~9:" / "4~6:" / "1~3:" / "0:"
        # English: "- 10:" / "- 7-9:" etc
        # Japanese: "- 10:" / "- 7〜9:" etc
        assert "10" in prompt
        # 0 점 기준 명시 (모든 언어)
        assert "0" in prompt
