"""모듈 레벨 캐시 상한 회귀 가드 (종합감사 P2, services.md 메모리 캐시 상한 규약).

Regression guards for module-level cache bounds (comprehensive audit P2).

상한이 없으면 두 캐시는 프로세스 수명 동안 단조 증가한다:
- github_client.checks._required_contexts_cache: (repo, branch) 쌍마다 누적 (TTL 은 신선도만 관리)
- webhook.loop_guard.BotInteractionLimiter._events: 이벤트 받은 모든 repo 키가 빈 deque 로 잔존
Both caches grow monotonically without a cap; these guards pin the eviction behavior.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")

# pylint: disable=wrong-import-position,protected-access
from unittest.mock import patch

import src.github_client.checks as checks
from src.webhook.loop_guard import BotInteractionLimiter


# ---------------------------------------------------------------------------
# checks._required_contexts_cache — 엔트리 상한
# ---------------------------------------------------------------------------


def test_required_contexts_cache_caps_size():
    """상한까지 채운 뒤 신규 저장 시 캐시 크기가 상한을 넘지 않는다.
    Filling to the cap then storing a new key must not exceed the cap.
    """
    checks._required_contexts_cache.clear()
    now = 1000.0
    # 상한까지 신선한(미만료) 엔트리로 채움 → 만료 정리로는 안 줄어 evict 경로 강제
    for i in range(checks._REQUIRED_CONTEXTS_CACHE_MAX):
        checks._required_contexts_cache[("o", f"b{i}")] = (set(), now)

    checks._store_required_contexts(("o", "new-branch"), {"ci"}, now)

    assert len(checks._required_contexts_cache) <= checks._REQUIRED_CONTEXTS_CACHE_MAX
    assert checks._required_contexts_cache[("o", "new-branch")] == ({"ci"}, now)
    checks._required_contexts_cache.clear()


def test_required_contexts_cache_purges_expired_first():
    """상한 도달 시 만료(TTL 초과) 엔트리를 먼저 정리한다 — 미만료 엔트리 보존.
    On overflow, purge TTL-expired entries first, preserving fresh ones.
    """
    checks._required_contexts_cache.clear()
    fresh_at = 10_000.0
    expired_at = fresh_at - checks._REQUIRED_CONTEXTS_TTL - 1  # TTL 초과 / past TTL
    for i in range(checks._REQUIRED_CONTEXTS_CACHE_MAX):
        at = expired_at if i % 2 == 0 else fresh_at
        checks._required_contexts_cache[("o", f"b{i}")] = (set(), at)

    checks._store_required_contexts(("o", "new-branch"), {"ci"}, fresh_at)

    assert len(checks._required_contexts_cache) < checks._REQUIRED_CONTEXTS_CACHE_MAX
    assert ("o", "new-branch") in checks._required_contexts_cache
    # 미만료 엔트리는 보존 / fresh entries preserved
    assert ("o", "b1") in checks._required_contexts_cache
    checks._required_contexts_cache.clear()


def test_required_contexts_cache_no_eviction_under_cap():
    """상한 미만이면 evict 없이 단순 저장 (정상 경로 회귀 가드).
    Below the cap, store without any eviction.
    """
    checks._required_contexts_cache.clear()
    checks._required_contexts_cache[("o", "b0")] = (set(), 1.0)
    checks._store_required_contexts(("o", "b1"), {"ci"}, 2.0)
    assert ("o", "b0") in checks._required_contexts_cache
    assert ("o", "b1") in checks._required_contexts_cache
    checks._required_contexts_cache.clear()


# ---------------------------------------------------------------------------
# loop_guard.BotInteractionLimiter._events — 키 수 상한
# ---------------------------------------------------------------------------


def test_limiter_prunes_stale_keys_over_cap():
    """상한 초과 + 신규 repo 시, 윈도우 밖(만료) 키를 정리해 상한을 넘지 않는다.
    Over the cap with a new repo, prune expired keys so the map stays bounded.
    """
    limiter = BotInteractionLimiter()
    with patch("src.webhook.loop_guard._MAX_TRACKED_REPOS", 3), \
         patch("src.webhook.loop_guard.time.time") as mock_time:
        # t=100 에 3개 리포 이벤트 → 3 키 (상한 도달)
        mock_time.return_value = 100.0
        for i in range(3):
            assert limiter.allow(f"o/r{i}") is True
        assert len(limiter._events) == 3

        # 윈도우(3600s) 밖으로 시간 이동 → 기존 3개 키는 stale
        # 신규 리포 추가 시 상한 점검 → stale 정리 후 신규만 남는다
        mock_time.return_value = 100.0 + 3601
        assert limiter.allow("o/r-new") is True
        assert len(limiter._events) <= 3, f"stale 키 미정리: {list(limiter._events)}"
        assert "o/r-new" in limiter._events


def test_limiter_caps_keys_when_all_active():
    """모든 리포가 활성(만료 아님)이어도 키 수가 상한 아래로 유지된다 (최고령 evict).
    Even when every repo is active, the key count stays bounded (oldest evicted).
    """
    limiter = BotInteractionLimiter()
    with patch("src.webhook.loop_guard._MAX_TRACKED_REPOS", 3), \
         patch("src.webhook.loop_guard.time.time") as mock_time:
        mock_time.return_value = 500.0
        for i in range(10):  # 상한(3) 훨씬 초과하는 활성 리포
            assert limiter.allow(f"o/active{i}") is True
        assert len(limiter._events) <= 3, f"활성 키 상한 미준수: {len(limiter._events)}"


def test_limiter_no_prune_under_cap():
    """상한 미만이면 정리 없이 정상 추적 (정상 경로 회귀 가드).
    Below the cap, track normally without pruning.
    """
    limiter = BotInteractionLimiter()
    with patch("src.webhook.loop_guard.time.time") as mock_time:
        mock_time.return_value = 1.0
        limiter.allow("o/a")
        limiter.allow("o/b")
    assert "o/a" in limiter._events and "o/b" in limiter._events
