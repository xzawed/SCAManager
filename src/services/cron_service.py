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
from src.repositories import analysis_attempt_repo, repo_config_repo, repository_repo
from src.services.analytics_service import moving_average, resolve_chat_id, weekly_summary

logger = logging.getLogger(__name__)

# 7일 이동평균 하락 기준점 (점수) — 이 값 이상 하락 시 경고 발송
# Score drop threshold to trigger a trend alert
_TREND_DROP_THRESHOLD = 10.0

# 소실 판정 임계 — 정상 분석은 수 분 내 finish_attempt 로 지워지므로, 30분 초과 잔존 = 증발.
# Loss threshold — a healthy analysis clears within minutes, so >30 min surviving = vanished.
_ORPHAN_SWEEP_THRESHOLD_MINUTES = 30


async def sweep_analysis_attempts(db: Session) -> int:
    """소실 탐지 흔적(analysis_attempts)을 판독·표면화하고 정리한다 (#1060 find_orphaned 배선, 준비도 감사 #11).

    Read, surface, and clean up the loss-detection breadcrumbs (wires up #1060's find_orphaned).

    `#1060` 은 흔적을 **남기는** 데까지만 했고 판독 경로가 없었다 — `find_orphaned` 호출자 0. 그래서
    SIGTERM/OOM 로 증발한 분석의 흔적이 (a) 아무도 안 읽어 소실이 미인지되고 (b) 상한 없이 무한
    누적됐다. 이 sweep 이 orphan(=증발한 분석)을 **로그 + 운영자 Telegram** 으로 표면화한 뒤
    **삭제**한다 — 표면화가 durable 기록(Railway 로그)이므로 삭제해도 소실 사실은 남고, 재알림·
    무한 누적을 막는다. 반환 = 표면화한 orphan 수.
    """
    orphans = analysis_attempt_repo.find_orphaned(
        db, older_than_minutes=_ORPHAN_SWEEP_THRESHOLD_MINUTES
    )
    if not orphans:
        return 0
    # durable 표면화 — Railway 로그. Telegram 실패해도 이 로그로 소실은 조회된다.
    # Durable surfacing via logs; the loss is recorded even if the Telegram alert fails.
    logger.warning(
        "analysis_attempts orphan sweep — %d vanished analyses (older than %d min)",
        len(orphans), _ORPHAN_SWEEP_THRESHOLD_MINUTES,
    )
    if settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            await telegram_post_message(
                settings.telegram_bot_token,
                settings.telegram_chat_id,
                {"text": _format_orphan_alert(orphans), "parse_mode": "HTML"},
            )
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning("orphan sweep telegram alert failed: %s", type(exc).__name__)
    # 표면화 완료 → **표면화한 행 id 만** 삭제 (재알림·무한 누적 방지 + TOCTOU 봉인 — pipeline-reviewer P2).
    # Surfaced → delete exactly the surfaced ids (prevents re-alert/growth; closes the TOCTOU window).
    analysis_attempt_repo.purge_by_ids(db, [o.id for o in orphans])
    return len(orphans)


def _format_orphan_alert(orphans: list) -> str:
    """운영자 Telegram 알림 본문 — 전역 알림이라 default_locale 사용 (repo 소유자 언어 아님)."""
    language = settings.default_locale
    lines = [get_text("notifier.cron.orphan_sweep_title", language, count=len(orphans))]
    for o in orphans[:5]:
        lines.append(f"<code>repo#{o.repo_id} {escape((o.commit_sha or '')[:8])}</code>")
    lines.append(get_text("notifier.cron.orphan_sweep_hint", language))
    return "\n".join(lines)


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

    # N+1 방지 — 전체 repo config 를 단일 IN 쿼리로 batch 조회
    # Avoid N+1 — batch-fetch all repo configs in one IN query
    configs = repo_config_repo.find_by_full_names(db, [r.full_name for r in repos])

    for repo in repos:
        try:
            # 리포별 설정 조회 (없으면 None)
            # Fetch per-repo config (None if absent)
            config = configs.get(repo.full_name)

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
            # 세션 오염 방지 — DB 에러로 세션이 failed 상태면 다음 repo 가 연쇄 실패
            # (security_scan_service.scan_all_repos 와 동일 패턴, #745 / api.md 세션 격리)
            # Roll back so a poisoned session doesn't cascade into the next repo
            db.rollback()

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


# N+1 방지용 configs batch 지역변수 추가로 16/15 — 함수 응집 보호 위해 inline disable (testing.md R0914)
# configs batch local for N+1 fix pushes to 16/15 — inline disable to keep function cohesion
async def run_trend_check(  # pylint: disable=too-many-locals
    db: Session, *, now: datetime | None = None
) -> int:
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

    # N+1 방지 — 전체 repo config 를 단일 IN 쿼리로 batch 조회
    # Avoid N+1 — batch-fetch all repo configs in one IN query
    configs = repo_config_repo.find_by_full_names(db, [r.full_name for r in repos])

    for repo in repos:
        try:
            # 리포별 설정 조회 (없으면 None)
            # Fetch per-repo config (None if absent)
            config = configs.get(repo.full_name)

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
            # 세션 오염 방지 — DB 에러로 세션이 failed 상태면 다음 repo 가 연쇄 실패
            # (security_scan_service.scan_all_repos 와 동일 패턴, #745 / api.md 세션 격리)
            # Roll back so a poisoned session doesn't cascade into the next repo
            db.rollback()

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
