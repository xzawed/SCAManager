"""webhook secret 캐시 엔트리 상한 회귀 가드.

`get_webhook_secret` 는 서명 검증 *전* 위조 가능한 full_name 으로 호출되므로,
캐시가 무한히 증가하지 않도록 `_store_secret` 이 WEBHOOK_SECRET_CACHE_MAX 를 강제한다.
Regression guard for the webhook-secret cache entry cap — `get_webhook_secret` runs before
signature verification with a forgeable full_name, so `_store_secret` must enforce the cap.
"""
import time

from src.webhook import _helpers
from src.constants import WEBHOOK_SECRET_CACHE_MAX, WEBHOOK_SECRET_CACHE_TTL


def test_store_secret_caps_cache_size():
    """상한까지 채운 뒤 신규 저장 시 캐시 크기가 상한을 넘지 않는다 (메모리 고갈 차단)."""
    _helpers._webhook_secret_cache.clear()
    now = time.monotonic()
    # 상한까지 미래 만료 엔트리로 채움 (만료 정리로는 줄지 않음 → evict 경로 강제)
    for i in range(WEBHOOK_SECRET_CACHE_MAX):
        _helpers._webhook_secret_cache[f"o/r{i}"] = ("s", now + 10_000)

    _helpers._store_secret("o/forged", "sx", now)

    assert len(_helpers._webhook_secret_cache) <= WEBHOOK_SECRET_CACHE_MAX
    # 신규 엔트리는 저장됨 (가장 빨리 만료될 엔트리 1건이 evict 됨)
    assert _helpers._webhook_secret_cache["o/forged"] == ("sx", now + WEBHOOK_SECRET_CACHE_TTL)


def test_store_secret_purges_expired_before_evict():
    """상한 도달 시 만료된 엔트리를 먼저 정리한다 (미만료 엔트리는 보존, 불필요한 evict 회피)."""
    _helpers._webhook_secret_cache.clear()
    now = time.monotonic()
    # 절반은 만료(now-1), 절반은 미래(now+10000) — 상한까지 채움
    for i in range(WEBHOOK_SECRET_CACHE_MAX):
        exp = now - 1 if i % 2 == 0 else now + 10_000
        _helpers._webhook_secret_cache[f"o/r{i}"] = ("s", exp)

    _helpers._store_secret("o/new", "sx", now)

    # 만료분 정리로 상한 미만 + 신규 엔트리 존재
    assert len(_helpers._webhook_secret_cache) < WEBHOOK_SECRET_CACHE_MAX
    assert "o/new" in _helpers._webhook_secret_cache
    # 미만료 엔트리는 보존되어야 한다 (evict 까지 안 감)
    assert _helpers._webhook_secret_cache.get("o/r1") == ("s", now + 10_000)


def test_store_secret_no_eviction_under_cap():
    """상한 미만이면 evict/purge 없이 단순 저장 (정상 경로 회귀 가드)."""
    _helpers._webhook_secret_cache.clear()
    now = time.monotonic()
    _helpers._webhook_secret_cache["o/keep"] = ("s", now - 1)  # 만료됐지만 상한 미만이라 보존
    _helpers._store_secret("o/add", "sx", now)
    assert "o/add" in _helpers._webhook_secret_cache
    assert "o/keep" in _helpers._webhook_secret_cache  # 상한 미만 → purge 미발동


def test_get_webhook_secret_does_not_cache_fallback_on_db_error():
    """🔴 transient DB 에러 시 fallback(global) 시크릿을 캐시하지 않는다 (종합감사 P2 — poison 방지).

    캐시하면 일시적 DB 장애가 per-repo webhook 인증을 TTL(5분) 동안 poison 한다. 캐시 없이
    반환하면 다음 호출이 DB 를 재시도한다.
    """
    from unittest.mock import MagicMock, patch
    from sqlalchemy.exc import SQLAlchemyError

    _helpers._webhook_secret_cache.clear()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=MagicMock())
    ctx.__exit__ = MagicMock(return_value=False)
    with patch.object(_helpers, "SessionLocal", return_value=ctx), \
         patch.object(_helpers.repository_repo, "find_by_full_name",
                      side_effect=SQLAlchemyError("db down")):
        result = _helpers.get_webhook_secret("owner/poisontest")

    assert result == _helpers.settings.github_webhook_secret, "fallback global 시크릿을 반환해야"
    assert "owner/poisontest" not in _helpers._webhook_secret_cache, (
        "🔴 DB 에러 시 fallback 이 캐시됨 — per-repo 인증 5분 poison"
    )
