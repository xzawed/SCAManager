"""알림 채널 사용자 언어 결정 — 3-layer fallback (Phase 3 PR-9 — 사이클 84).

Notification channel user-language resolver — 3-layer fallback (Phase 3 PR-9 — Cycle 84).

3-layer 우선순위 (priority order):
1. RepoConfig.notification_language — repo 별 **명시 override**. NULL = 미설정 → next layer.
   repo 단위로 알림 언어를 따로 고를 수 있다 (예: 한국어 사용자가 글로벌 팀 위해 영문 알림).
   Explicit per-repo override; NULL means "not set".

   🔴 이 순서가 **1층인 이유**: `User.preferred_language` 는 `nullable=False, default="en"`
   이라 **항상 값이 있다**(실측). User 를 먼저 보면 repo override 가 영영 도달하지 못한다.
   `api/repos.py`·`config_manager/manager.py` 의 「NULL = 사용자 preferred_language
   fallback」 주석이 이 순서를 전제한다 (감사 A7, #1519 — 예전 순서 서술은 거짓이었다).

2. User.preferred_language — Telegram 연결 사용자 우선, 없으면 **리포 소유자**.
   소유자 해소는 `api/hook.py::_resolve_hook_locale` 과 같은 관용구다:
   `repo full_name -> Repository.user_id -> User.preferred_language`.
   미지원 언어는 무시한다.
   Telegram-linked user first, else the repo owner; unsupported codes ignored.

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
from typing import Any

from sqlalchemy.orm import Session

from src.config import settings

logger = logging.getLogger(__name__)


def _supported_locales() -> set[str]:
    return {code.strip() for code in settings.supported_locales.split(",")}


def _resolve_user_language(db, config, telegram_user_id: str | None) -> str | None:
    """Telegram 연결 사용자 → 없으면 리포 소유자의 `preferred_language`.

    미지원 언어는 무시한다(형제 `api/hook.py::_resolve_hook_locale` 과 같은 규율) —
    지원 목록 밖 값을 그대로 쓰면 템플릿 조회가 조용히 빈 문자열이 된다.

    Telegram-linked user first, then the repo owner; unsupported codes are ignored.
    """
    from src.models.repository import Repository  # noqa: PLC0415
    from src.models.user import User  # noqa: PLC0415
    from src.repositories import user_repo  # noqa: PLC0415

    supported = _supported_locales()

    if telegram_user_id:
        user = user_repo.find_by_telegram_user_id(db, telegram_user_id)
        if user and user.preferred_language in supported:
            return user.preferred_language

    repo_full_name = getattr(config, "repo_full_name", None)
    if not repo_full_name:
        return None

    repo = db.query(Repository).filter(Repository.full_name == repo_full_name).first()
    if not repo or not repo.user_id:
        return None
    owner = db.query(User).filter(User.id == repo.user_id).first()
    if owner and owner.preferred_language in supported:
        return owner.preferred_language
    return None


def resolve_notification_language(
    db: Session | None = None,
    *,
    _repo_full_name: str | None = None,
    config: Any = None,
    telegram_user_id: str | None = None,
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
    # Layer 1: RepoConfig.notification_language (repo 단위 명시 override)
    # Layer 1: RepoConfig.notification_language (explicit per-repo override)
    if config is not None:
        repo_lang = getattr(config, "notification_language", None)
        if repo_lang:
            return repo_lang

    # Layer 2: User.preferred_language — Telegram 연결 사용자 우선, 없으면 **리포 소유자**.
    #
    # 🔴 예전 구현은 `telegram_user_id` 가 있어야만 이 층에 들어갔는데, 프로덕션 호출부
    # 20곳 중 **0곳**이 그것을 넘기지 않았다(AST 전수 실측). 그래서 사용자가 설정한
    # 언어가 6개 알림 채널·게이트·재시도·railway webhook 전부에서 무시됐고,
    # 20곳이 넘기던 `db` 는 읽히지 않는 인자였다 (감사 A7, #1519).
    #
    # 소유자 해소는 형제 `src/api/hook.py::_resolve_hook_locale` 과 같은 관용구다:
    #   repo full_name -> Repository.user_id -> User.preferred_language
    #
    # Layer 2: telegram-linked user first, else the repo owner (mirrors api/hook.py).
    if db is not None:
        try:
            user_lang = _resolve_user_language(db, config, telegram_user_id)
            if user_lang:
                return user_lang
        except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
            logger.warning(
                "Layer 2 (User.preferred_language) lookup failed: %s — fall through to Layer 3",
                exc,
            )

    # Layer 3: settings.default_locale (env 기반 fallback)
    # Layer 3: settings.default_locale (env-based fallback)
    return settings.default_locale
