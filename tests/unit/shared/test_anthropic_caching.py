"""Anthropic prompt caching 헬퍼 단위 테스트.

Unit tests for Anthropic prompt caching helper.

Phase 3 PR 1 — TDD Red.
- 신설 모듈 src/shared/anthropic_caching.py 의 build_cached_system_param() 검증
- Validate build_cached_system_param() in the new src/shared/anthropic_caching.py module
- 6 테스트: 정상 cache / 빈 문자열 / disable_cache=True / disable_cache=False / settings.disable_prompt_cache=True / settings.disable_prompt_cache=False
- 6 tests: normal cache / empty string / disable_cache=True / disable_cache=False / settings.disable_prompt_cache=True / settings.disable_prompt_cache=False

패턴:
- settings 직접 mock 우선 (auto memory `test-env-setup.md` — 환경변수 stash 는 fallback)
- Direct settings mock pattern (auto memory `test-env-setup.md` — env-var stash is fallback)
"""
from unittest.mock import patch

# 구현 모듈 import — Red 단계에서 ModuleNotFoundError 예상
# Import implementation module — ModuleNotFoundError expected during Red phase
from src.shared import anthropic_caching


# 정상 cache 적용 — 평문 입력에 cache_control ephemeral 키가 자동 부여되어야 함
# Normal cache application — plain input must auto-receive cache_control ephemeral key
def test_build_cached_system_param_applies_ephemeral_cache_control():
    result = anthropic_caching.build_cached_system_param("hello world")
    assert result == [
        {
            "type": "text",
            "text": "hello world",
            "cache_control": {"type": "ephemeral"},
        }
    ]


# 빈 문자열 입력 — 길이 검증 책임은 caller, 헬퍼는 graceful 통과
# Empty string input — length validation is caller's responsibility, helper passes through gracefully
def test_build_cached_system_param_handles_empty_string():
    result = anthropic_caching.build_cached_system_param("")
    assert result == [
        {
            "type": "text",
            "text": "",
            "cache_control": {"type": "ephemeral"},
        }
    ]


# disable_cache=True 인자 명시 시 cache_control 키 미존재 (opt-out 운영 분기)
# When disable_cache=True is explicit, cache_control key must be absent (opt-out branch)
def test_build_cached_system_param_disable_cache_true_omits_cache_control():
    result = anthropic_caching.build_cached_system_param("hello", disable_cache=True)
    assert result == [{"type": "text", "text": "hello"}]
    # cache_control 키 자체가 없어야 함 (None 값도 안 됨)
    # cache_control key must be wholly absent (None value not acceptable)
    assert "cache_control" not in result[0]


# disable_cache=False 인자 명시 시 settings 무관하게 cache_control 적용
# When disable_cache=False is explicit, cache_control applies regardless of settings
def test_build_cached_system_param_disable_cache_false_applies_cache_control():
    # settings.disable_prompt_cache=True 여도 인자 우선
    # Even if settings.disable_prompt_cache=True, the explicit arg wins
    with patch.object(anthropic_caching, "settings") as mock_settings:
        mock_settings.disable_prompt_cache = True
        result = anthropic_caching.build_cached_system_param(
            "hello", disable_cache=False
        )
    assert result == [
        {
            "type": "text",
            "text": "hello",
            "cache_control": {"type": "ephemeral"},
        }
    ]


# disable_cache=None (default) + settings.disable_prompt_cache=True → opt-out
# disable_cache=None (default) + settings.disable_prompt_cache=True → opt-out
def test_build_cached_system_param_settings_disable_overrides_default():
    with patch.object(anthropic_caching, "settings") as mock_settings:
        mock_settings.disable_prompt_cache = True
        result = anthropic_caching.build_cached_system_param("hello")
    assert result == [{"type": "text", "text": "hello"}]
    assert "cache_control" not in result[0]


# disable_cache=None (default) + settings.disable_prompt_cache=False (default) → cache 적용
# disable_cache=None (default) + settings.disable_prompt_cache=False (default) → cache applies
def test_build_cached_system_param_default_path_applies_cache_control():
    with patch.object(anthropic_caching, "settings") as mock_settings:
        mock_settings.disable_prompt_cache = False
        result = anthropic_caching.build_cached_system_param("hello")
    assert result == [
        {
            "type": "text",
            "text": "hello",
            "cache_control": {"type": "ephemeral"},
        }
    ]
