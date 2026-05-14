"""알림 채널 사용자 언어 결정 — 3-layer fallback (Phase 3 PR-9 — 사이클 84).

Notification channel user-language resolver — 3-layer fallback (Phase 3 PR-9 — Cycle 84).

3-layer 우선순위 (priority order):
1. User.preferred_language — Telegram 연결된 사용자 (`user_repo.find_by_telegram_user_id`).
   가장 정확 (사용자 명시 선택). NULL/empty → next layer.
   Most accurate (user-explicit choice). NULL/empty → next layer.

2. RepoConfig.notification_language — repo 별 알림 언어 (Phase 3 PR-9 페어, Phase 1 PR-1c #285 도입).
   repo 단위로 알림 언어 별도 설정 가능 (예: 한국어 사용자가 글로벌 팀 위해 영문 알림 선택).
   Per-repo notification language (introduced in Phase 1 PR-1c).

3. settings.default_locale — 환경변수 `DEFAULT_LOCALE` (default 'en').
   Final fallback — 환경변수 + SUPPORTED_LOCALES 검증 (config.py field_validator).
   Final fallback — env var + SUPPORTED_LOCALES validated.

사용 패턴 (usage):
    from src.notifier._language import resolve_notification_language
    lang = resolve_notification_language(db, config=ctx.config)
    # → "ko" / "en" / "ja"
    msg = get_text("notifier.telegram.title", lang)

DI 패턴 (dependency injection): db 와 user_repo 는 Optional — 단위 테스트 시 mock 가능.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.config import settings

logger = logging.getLogger(__name__)


def resolve_notification_language(
    db: Optional[Session] = None,
    *,
    _repo_full_name: Optional[str] = None,
    config: Any = None,
    telegram_user_id: Optional[str] = None,
) -> str:
    """알림 채널 사용자 언어 결정 — 3-layer fallback.

    Resolve notification channel user language via 3-layer fallback.

    Args:
        db: SQLAlchemy 세션 — User 조회 시 의무. None 시 layer 1 skip.
        _repo_full_name: 리포 full name (현재 unused — Layer 2 는 config 인자 직접 사용).
        config: RepoConfigData (notification_language 필드 보유). None 시 layer 2 skip.
        telegram_user_id: Telegram 사용자 ID — User.preferred_language 조회 키.
            None 시 layer 1 skip (Telegram 미연결 사용자 — Discord/Slack/Email 등).

    Returns:
        언어 코드 (예: 'ko', 'en', 'ja'). SUPPORTED_LOCALES 영역 내.
        Language code (e.g. 'ko', 'en', 'ja'). Within SUPPORTED_LOCALES.

    Examples:
        >>> # Telegram 연결 사용자 (Layer 1)
        >>> resolve_notification_language(db, telegram_user_id="123456789")
        "ko"

        >>> # repo 별 강제 (Layer 2 — Telegram 미연결 영역)
        >>> resolve_notification_language(config=RepoConfigData(notification_language="ja"))
        "ja"

        >>> # default fallback (Layer 3)
        >>> resolve_notification_language()
        "en"  # settings.default_locale
    """
    # Layer 1: User.preferred_language (Telegram 연결 사용자)
    # Layer 1: User.preferred_language (Telegram-linked user)
    if db is not None and telegram_user_id:
        try:
            from src.repositories import user_repo  # noqa: WPS433  # pylint: disable=import-outside-toplevel
            user = user_repo.find_by_telegram_user_id(db, telegram_user_id)
            if user and user.preferred_language:
                return user.preferred_language
        except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
            logger.warning(
                "Layer 1 (User.preferred_language) lookup failed: %s — fall through to Layer 2",
                exc,
            )

    # Layer 2: RepoConfig.notification_language (repo 단위 강제)
    # Layer 2: RepoConfig.notification_language (per-repo override)
    if config is not None:
        repo_lang = getattr(config, "notification_language", None)
        if repo_lang:
            return repo_lang

    # Layer 3: settings.default_locale (env 기반 fallback)
    # Layer 3: settings.default_locale (env-based fallback)
    return settings.default_locale
