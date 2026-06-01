"""주간 리포트 + 트렌드 체크 cron 서비스.
Weekly report and trend-check cron service.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from html import escape

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.config import settings
from src.i18n.loader import get_text
from src.notifier._language import resolve_notification_language
from src.notifier.telegram import telegram_post_message
from src.repositories import repo_config_repo, repository_repo
from src.services.analytics_service import moving_average, resolve_chat_id, weekly_summary

logger = logging.getLogger(__name__)

# 7일 이동평균 하락 기준점 (점수) — 이 값 이상 하락 시 경고 발송
# Score drop threshold to trigger a trend alert
_TREND_DROP_THRESHOLD = 10.0


async def run_weekly_reports(db: Session, *, now: datetime | None = None) -> int:
    """모든 활성 리포에 대해 주간 요약을 Telegram으로 발송한다.
    Send weekly summary Telegram messages for all active repositories.

    Returns the number of successfully sent reports.
    """
    # now 기본값 설정 — 테스트에서 고정 시각 주입 가능
    # Default now — allows injecting a fixed time in tests
    _now = now or datetime.now(timezone.utc)
    week_start = _now - timedelta(days=7)
    sent = 0

    # 전체 리포 목록 조회
    # Fetch all repository records
    repos = repository_repo.find_all(db)

    for repo in repos:
        try:
            # 리포별 설정 조회 (없으면 None)
            # Fetch per-repo config (None if absent)
            config = repo_config_repo.find_by_full_name(db, repo.full_name)

            # chat_id 우선순위 라우팅 — None 이면 skip
            # Resolve chat_id with priority routing — skip if None
            chat_id = resolve_chat_id(repo, config)
            if not chat_id:
                logger.warning(
                    "weekly_report: no chat_id resolved for repo=%s", repo.full_name
                )
                continue

            # 주간 요약 집계 — 분석 없으면 None 반환
            # Aggregate weekly summary — returns None if no analyses exist
            summary = weekly_summary(db, repo.id, week_start, now=_now)
            if summary is None:
                continue

            # 발신 언어 결정 (config 기반 fallback) 후 메시지 포맷팅 및 Telegram 발송
            # Resolve notification language (config-based fallback), then format & send
            language = resolve_notification_language(db, config=config)
            text = _format_weekly_message(repo.full_name, summary, language)
            await telegram_post_message(
                settings.telegram_bot_token,
                chat_id,
                {"text": text, "parse_mode": "HTML"},
            )
            sent += 1

        except (httpx.HTTPError, SQLAlchemyError, KeyError, ValueError) as exc:
            # 리포별 예외 격리 — 한 리포 실패가 다른 리포 알림을 막지 않는다
            # Per-repo exception isolation — one failure does not block others
            logger.warning(
                "weekly_report: failed for repo=%s: %s", repo.full_name, exc
            )

    return sent


def _format_weekly_message(
    repo_full_name: str, summary: dict, language: str = "ko"
) -> str:
    """주간 요약 Telegram 메시지를 사용자 언어로 포맷팅한다.
    Format a weekly summary Telegram message in the user's language.

    Args:
        repo_full_name: 리포 전체 이름 (owner/repo) / Repository full name
        summary: weekly_summary() 반환 dict / Return value of weekly_summary()
        language: 발신 언어 코드 (ko/en/ja) / Notification language code

    Returns:
        HTML 포맷 메시지 문자열 / HTML-formatted message string
    """
    avg = summary["avg_score"]
    count = summary["count"]
    # HTML 태그(<b>/<code>)는 i18n 값에 포함되거나 직접 조합해 보존
    # HTML tags (<b>/<code>) preserved via i18n values or direct composition
    return (
        f"{get_text('notifier.cron.weekly_title', language)}\n"
        f"<code>{escape(repo_full_name)}</code>\n"
        f"{get_text('notifier.cron.weekly_analyses', language, count=count)}\n"
        f"{get_text('notifier.cron.weekly_avg', language, avg=f'{avg:.1f}')}"
    )


async def run_trend_check(db: Session, *, now: datetime | None = None) -> int:
    """7일 이동 평균이 10점 이상 하락한 리포에 트렌드 경고를 발송한다.
    Send trend alerts for repos whose 7-day moving average drops by 10+ points.

    Returns the number of alerts sent.
    """
    # now 기본값 설정 — 테스트에서 고정 시각 주입 가능
    # Default now — allows injecting a fixed time in tests
    _now = now or datetime.now(timezone.utc)
    alerted = 0

    # 전체 리포 목록 조회
    # Fetch all repository records
    repos = repository_repo.find_all(db)

    for repo in repos:
        try:
            # 리포별 설정 조회 (없으면 None)
            # Fetch per-repo config (None if absent)
            config = repo_config_repo.find_by_full_name(db, repo.full_name)

            # chat_id 우선순위 라우팅 — None 이면 skip
            # Resolve chat_id with priority routing — skip if None
            chat_id = resolve_chat_id(repo, config)
            if not chat_id:
                continue

            # 현재 7일 이동 평균
            # Current 7-day moving average
            current_avg = moving_average(db, repo.id, now=_now)
            if current_avg is None:
                # min_samples 미충족 — skip
                # Below min_samples — skip
                continue

            # 이전 주(7일 전 기준) 이동 평균 — 비교 기준
            # Previous week's moving average (baseline 7 days ago)
            prev_now = _now - timedelta(days=7)
            prev_avg = moving_average(db, repo.id, now=prev_now)
            if prev_avg is None:
                # 이전 기간 샘플 부족 — 비교 불가, skip
                # Insufficient samples for previous window — cannot compare, skip
                continue

            # 하락폭 계산 — 10점 이상이면 경고 발송
            # Calculate drop — send alert if >= threshold
            drop = prev_avg - current_avg
            if drop >= _TREND_DROP_THRESHOLD:
                # 발신 언어 결정 (config 기반 fallback)
                # Resolve notification language (config-based fallback)
                language = resolve_notification_language(db, config=config)
                text = _format_trend_alert(
                    repo.full_name, current_avg, prev_avg, drop, language
                )
                await telegram_post_message(
                    settings.telegram_bot_token,
                    chat_id,
                    {"text": text, "parse_mode": "HTML"},
                )
                alerted += 1

        except (httpx.HTTPError, SQLAlchemyError, KeyError, ValueError) as exc:
            # 리포별 예외 격리 — 한 리포 실패가 다른 리포 알림을 막지 않는다
            # Per-repo exception isolation — one failure does not block others
            logger.warning(
                "trend_check: failed for repo=%s: %s", repo.full_name, exc
            )

    return alerted


def _format_trend_alert(
    repo_full_name: str,
    current: float,
    prev: float,
    drop: float,
    language: str = "ko",
) -> str:
    """트렌드 경고 메시지를 사용자 언어로 포맷팅한다.
    Format a trend alert message in the user's language.

    Args:
        repo_full_name: 리포 전체 이름 (owner/repo) / Repository full name
        current: 현재 7일 이동 평균 / Current 7-day moving average
        prev: 이전 7일 이동 평균 / Previous 7-day moving average
        drop: 하락폭 (prev - current) / Score drop (prev - current)
        language: 발신 언어 코드 (ko/en/ja) / Notification language code

    Returns:
        HTML 포맷 경고 메시지 / HTML-formatted alert message
    """
    # HTML 태그(<b>/<code>)는 i18n 값에 포함되거나 직접 조합해 보존
    # HTML tags (<b>/<code>) preserved via i18n values or direct composition
    return (
        f"{get_text('notifier.cron.trend_title', language)}\n"
        f"<code>{escape(repo_full_name)}</code>\n"
        f"{get_text('notifier.cron.trend_prev', language, prev=f'{prev:.1f}')}\n"
        f"{get_text('notifier.cron.trend_current', language, current=f'{current:.1f}')}\n"
        f"{get_text('notifier.cron.trend_drop', language, drop=f'{drop:.1f}')}"
    )
