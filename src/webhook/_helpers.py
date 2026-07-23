"""Webhook 공용 헬퍼 — per-repo secret 조회 + TTL 캐시.

`src/webhook/providers/github.py::_get_webhook_secret` 에서 사용.
tests/conftest.py 가 매 테스트마다 캐시를 클리어 (autouse).
"""
from __future__ import annotations

import logging
import time

from sqlalchemy.exc import SQLAlchemyError

from src.config import settings
from src.constants import WEBHOOK_SECRET_CACHE_TTL, WEBHOOK_SECRET_CACHE_MAX
from src.database import WorkerSessionLocal as SessionLocal
from src.repositories import repository_repo

logger = logging.getLogger("src.webhook")

# {full_name: (secret, expiry_monotonic)} — tests/conftest.py autouse 가 클리어
_webhook_secret_cache: dict[str, tuple[str, float]] = {}


def _store_secret(full_name: str, secret: str, now: float) -> None:
    """캐시에 secret 을 저장하되 엔트리 상한을 강제한다 (pre-auth 무한 증가 차단).

    상한 초과 시: (1) 만료된 엔트리 정리 → (2) 여전히 상한이면 가장 빨리 만료될 엔트리 1건 evict.
    Stores the secret while enforcing the entry cap (blocks pre-auth unbounded growth):
    on overflow, purge expired entries, then evict the soonest-expiring one if still at the cap.
    """
    if len(_webhook_secret_cache) >= WEBHOOK_SECRET_CACHE_MAX:
        for key in [k for k, (_, exp) in _webhook_secret_cache.items() if exp <= now]:
            del _webhook_secret_cache[key]
        if len(_webhook_secret_cache) >= WEBHOOK_SECRET_CACHE_MAX:
            soonest = min(_webhook_secret_cache, key=lambda k: _webhook_secret_cache[k][1])
            del _webhook_secret_cache[soonest]
    _webhook_secret_cache[full_name] = (secret, now + WEBHOOK_SECRET_CACHE_TTL)


def get_webhook_secret(full_name: str) -> str:
    """per-repo webhook secret 을 DB 에서 조회 (TTL 캐시 적용).

    리포별 secret 이 없으면 전역 `settings.github_webhook_secret` fallback.
    🔴 본 함수는 서명 검증 *전*에 위조 가능한 `full_name` 으로 호출되므로 캐시는 상한이 강제된다
    (`_store_secret` — WEBHOOK_SECRET_CACHE_MAX). 미적용 시 위조 full_name 으로 메모리 고갈 가능.
    This runs *before* signature verification with a forgeable full_name, so the cache is capped.
    """
    now = time.monotonic()
    cached = _webhook_secret_cache.get(full_name)
    if cached and now < cached[1]:
        return cached[0]
    secret = settings.github_webhook_secret
    try:
        with SessionLocal() as db:
            repo = repository_repo.find_by_full_name(db, full_name)
            if repo and repo.webhook_secret:
                secret = repo.webhook_secret
    except (SQLAlchemyError, KeyError, AttributeError) as exc:
        # 🔴 transient DB 에러 시 fallback(global) 시크릿을 **캐시하지 않는다** (종합감사 P2).
        #   캐시하면 일시적 DB 장애가 per-repo webhook 인증을 TTL(5분) 동안 poison 한다 —
        #   repo 전용 시크릿 대신 global 로 서명 검증해 그 repo webhook 이 5분간 전부 401.
        #   캐시 없이 반환하면 다음 호출이 DB 를 재시도한다.
        # Do NOT cache the fallback on a transient DB error — caching would poison per-repo auth
        #   for the full TTL. Returning uncached lets the next call retry the DB.
        logger.warning(
            "Per-repo webhook secret lookup failed, using global (uncached): %s",
            type(exc).__name__,
        )
        return secret
    _store_secret(full_name, secret, now)
    return secret
