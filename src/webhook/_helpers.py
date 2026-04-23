"""Webhook 공용 헬퍼 — per-repo secret 조회 + TTL 캐시.

`src/webhook/providers/github.py::_get_webhook_secret` 에서 사용.
tests/conftest.py 가 매 테스트마다 캐시를 클리어 (autouse).
"""
from __future__ import annotations

import logging
import time

from sqlalchemy.exc import SQLAlchemyError

from src.config import settings
from src.constants import WEBHOOK_SECRET_CACHE_TTL
from src.database import SessionLocal
from src.repositories import repository_repo

logger = logging.getLogger("src.webhook")

# {full_name: (secret, expiry_monotonic)} — tests/conftest.py autouse 가 클리어
_webhook_secret_cache: dict[str, tuple[str, float]] = {}


def get_webhook_secret(full_name: str) -> str:
    """per-repo webhook secret 을 DB 에서 조회 (TTL 캐시 적용).

    리포별 secret 이 없으면 전역 `settings.github_webhook_secret` fallback.
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
        logger.warning("Per-repo webhook secret lookup failed, using global secret: %s", exc)
    _webhook_secret_cache[full_name] = (secret, now + WEBHOOK_SECRET_CACHE_TTL)
    return secret
