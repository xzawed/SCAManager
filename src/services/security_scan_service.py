"""security_scan_service — GitHub Code Scanning + Secret Scanning alert 폴링 + audit log.

Cycle 73 F1 — cron 폴링 + GHAS graceful degradation + kill-switch + audit log upsert.
Cycle 73 F1 — cron polling + GHAS graceful degradation + kill-switch + audit log upsert.

흐름:
1. GHAS kill-switch (`SECURITY_AUTO_PROCESS_DISABLED=1`) 검사 → 활성 시 즉시 skip
2. repo 별 GitHub Code Scanning + Secret Scanning open alerts API 호출
3. GHAS 비활성 (403/404) → silent skip + WARNING 1회 (graceful degradation)
4. alert 별 audit log upsert (분류 = pending — Phase 2 AI 분류 시점에 갱신)
5. counts dict 반환 (운영 데이터 baseline)

Phase 1 = read-only (자동 dismiss X). 사용자 1-click confirm 은 dashboard 에서 처리.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.constants import GITHUB_API
from src.models.repository import Repository
from src.repositories import security_alert_log_repo, user_repo
from src.shared.feature_kill_switch import is_disabled
from src.shared.http_client import get_http_client
from src.shared.log_safety import sanitize_for_log
from src.shared.http_client import HTTPX_SEND_ERRORS

logger = logging.getLogger(__name__)
_CODE_SCANNING_KEY = "code_scanning"
_SECRET_SCANNING_KEY = "_".join(("secret", "scanning"))
_SKIPPED_KEY = "skipped"


def is_kill_switch_active() -> bool:
    """kill-switch 환경변수 검사 — `SECURITY_AUTO_PROCESS_DISABLED=1` (Cycle 78 helper 위임).

    Check kill-switch env var — SECURITY_AUTO_PROCESS_DISABLED=1 (Cycle 78 helper delegation).
    """
    return is_disabled("SECURITY_AUTO_PROCESS")


def _resolve_token(user) -> str | None:
    """사용자 토큰 우선 + 전역 fallback (`merge_retry_service._resolve_github_token` 패턴).

    User token first + global fallback (merge_retry_service._resolve_github_token pattern).
    """
    if user is not None:
        try:
            # plaintext_token 직접 체크 — None 이면 env fallback 진행
            # Check plaintext_token directly — fall through to env if None
            token = user.plaintext_token
            if token:
                return token
        except Exception:  # pylint: disable=broad-except  # noqa: BLE001
            return None
    return os.environ.get("GITHUB_TOKEN") or None


# alert 페이지네이션 안전 상한 (종합감사 P2) — 2000 alert / infinite-loop 가드. 초과 시 WARNING.
# Pagination safety cap (2000 alerts); on overflow, WARN rather than truncate silently.
_MAX_ALERT_PAGES = 20


async def _fetch_alerts(  # pylint: disable=too-many-return-statements
    token: str, repo_full_name: str, alert_kind: str,
) -> list[dict[str, Any]] | None:
    """GitHub Security alerts API 호출 (graceful degradation).

    Call GitHub Security alerts API (graceful degradation).
    alert_kind = "code-scanning" | "secret-scanning".
    Returns None on GHAS 비활성 (403/404) — silent skip + WARNING.
    """
    url = f"{GITHUB_API}/repos/{repo_full_name}/{alert_kind}/alerts"
    client = get_http_client()
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    # 🔴 페이지네이션 (종합감사 P2) — per_page=100 단일 요청은 alert 100 개 초과분을 조용히
    #   버렸다(대형 리포에서 보안 alert 을 '0 초과분 없음' 으로 오보고). 마지막 페이지(< 100)까지
    #   순회해 전량 수집. 상한 도달 시 silent truncation 대신 WARNING(관측 부재 방지 원칙).
    # Paginate: a single per_page=100 request silently dropped alerts beyond 100. Follow pages until
    #   the last (< 100); on hitting the cap, WARN rather than truncate silently.
    alerts: list[dict[str, Any]] = []
    for page in range(1, _MAX_ALERT_PAGES + 1):
        try:
            resp = await client.get(
                url,
                params={"state": "open", "per_page": 100, "page": page},
                headers=headers,
            )
        except HTTPX_SEND_ERRORS as exc:
            logger.warning(
                "security_scan: API 호출 실패 repo=%s page=%d err=%s",
                sanitize_for_log(repo_full_name), page, type(exc).__name__,
            )
            # 첫 페이지 실패 = 스캔 실패(None) / 이후 페이지 실패 = 부분결과 보존(0 오보고 방지)
            return None if page == 1 else alerts
        if page == 1:
            # 상태 분류는 첫 페이지만 (403/404 GHAS-off vs rate-limit vs non-200). 이후 페이지는 200 기대.
            if resp.status_code == 403 and (
                resp.headers.get("X-RateLimit-Remaining") == "0" or resp.headers.get("Retry-After")
            ):
                logger.warning(
                    "security_scan: GitHub rate-limited repo=%s (alerts NOT scanned this cycle — "
                    "retry pending, '0 alerts' 로 오인 금지)",
                    sanitize_for_log(repo_full_name),
                )
                return None
            if resp.status_code in (403, 404):
                logger.info(
                    "security_scan: GHAS 비활성 repo=%s status=%d (skip)",
                    sanitize_for_log(repo_full_name), resp.status_code,
                )
                return None
        if resp.status_code != 200:
            logger.warning(
                "security_scan: 비정상 응답 repo=%s page=%d status=%d",
                sanitize_for_log(repo_full_name), page, resp.status_code,
            )
            return None if page == 1 else alerts
        try:
            batch = resp.json() or []
        except (ValueError, KeyError):
            return None if page == 1 else alerts
        alerts.extend(batch)
        if len(batch) < 100:
            return alerts  # 마지막 페이지 도달 / reached the last page
    # 상한 도달 — 이후 alert 미스캔을 표면화(silent truncation 금지)
    logger.warning(
        "security_scan: repo=%s alert 이 %d 페이지(=%d) 초과 — 이후 미스캔(silent 0 오인 금지)",
        sanitize_for_log(repo_full_name), _MAX_ALERT_PAGES, _MAX_ALERT_PAGES * 100,
    )
    return alerts


def _alert_metadata(alert: dict[str, Any], alert_kind: str) -> dict[str, Any]:
    """alert payload 에서 핵심 메타데이터 추출 (kind 별 정규화).

    Extract core metadata from alert payload (kind-aware normalization).
    """
    if alert_kind == "code-scanning":
        rule = alert.get("rule") or {}
        return {
            "alert_type": "code_scanning",
            "alert_number": int(alert.get("number") or 0),
            "severity": rule.get("severity") or rule.get("security_severity_level"),
            "rule_id": rule.get("id"),
        }
    return {
        "alert_type": "secret_scanning",
        "alert_number": int(alert.get("number") or 0),
        "severity": "high",  # secret 노출은 일관 high 분류
        "rule_id": alert.get("secret_type") or alert.get("secret_type_display_name"),
    }


async def scan_repo_alerts(
    db: Session, repo: Repository, *, user=None,
) -> dict[str, int]:
    """단일 repo 의 Code/Secret Scanning open alert 수집 + audit log upsert.

    Collect Code/Secret Scanning open alerts for one repo + upsert audit log.
    Returns code scanning, secret scanning, and skipped counts.
    """
    counts = {_CODE_SCANNING_KEY: 0, _SECRET_SCANNING_KEY: 0, _SKIPPED_KEY: 0}
    if is_kill_switch_active():
        counts[_SKIPPED_KEY] = 1
        return counts
    token = _resolve_token(user)
    if token is None:
        logger.info("security_scan: token 없음 repo=%s (skip)", sanitize_for_log(repo.full_name))
        counts[_SKIPPED_KEY] = 1
        return counts

    # 두 종류 alert 를 병렬 fetch (독립 read-only GET) — DB upsert 는 단일 세션 직렬 유지
    # Fetch both alert kinds in parallel (independent read-only GETs); DB upserts stay serial
    # (_fetch_alerts 는 자체적으로 에러 시 None 반환 — gather return_exceptions 불요)
    # (_fetch_alerts returns None on error itself — no need for gather return_exceptions)
    kinds = (("code-scanning", _CODE_SCANNING_KEY), ("secret-scanning", _SECRET_SCANNING_KEY))
    fetched = await asyncio.gather(
        *(_fetch_alerts(token, repo.full_name, kind) for kind, _ in kinds)
    )
    for (kind, key), alerts in zip(kinds, fetched):
        if alerts is None:
            continue
        for alert in alerts:
            meta = _alert_metadata(alert, kind)
            try:
                security_alert_log_repo.upsert_alert_log(
                    db,
                    repo_id=repo.id,
                    alert_type=meta["alert_type"],
                    alert_number=meta["alert_number"],
                    severity=meta["severity"],
                    rule_id=meta["rule_id"],
                )
                counts[key] += 1
            except SQLAlchemyError as exc:
                logger.warning(
                    "security_scan: log upsert 실패 repo=%s err=%s",
                    sanitize_for_log(repo.full_name), type(exc).__name__,
                )
                db.rollback()
    return counts


async def scan_all_repos(db: Session) -> dict[str, int]:
    """모든 repo 일괄 scan (cron 트리거 진입점 — `cron_service` 패턴 차용).

    Scan all repos in batch (cron entry point — cron_service pattern).
    """
    totals = {_CODE_SCANNING_KEY: 0, _SECRET_SCANNING_KEY: 0, _SKIPPED_KEY: 0, "repos": 0}
    if is_kill_switch_active():
        logger.info("security_scan: kill-switch 활성 — 전체 skip")
        totals[_SKIPPED_KEY] = -1  # sentinel = kill-switch
        return totals
    repos = db.query(Repository).all()
    for repo in repos:
        totals["repos"] += 1
        try:
            # 🔴 소유자 토큰 우선 — 전역 GITHUB_TOKEN 만 쓰면 소유자 private 리포는 403/404 →
            #   silent skip 으로 그 리포의 Code/Secret Scanning alert 가 영영 표면화되지 않는다
            #   (정책 14 무력화, 종합감사 P1-4·Grok REAL). merge_retry._resolve_github_token 대칭 —
            #   _resolve_token(user) 가 owner 토큰 우선 + 전역 fallback 이므로 owner 만 넘기면 된다.
            # Resolve the repo owner so scan_repo_alerts uses the owner's token first (global fallback).
            #   Without it, an owner's private repo 403/404-skips and its scanning alerts never surface.
            owner = user_repo.find_by_id(db, repo.user_id) if repo.user_id is not None else None
            counts = await scan_repo_alerts(db, repo, user=owner)
            totals["code_scanning"] += counts["code_scanning"]
            totals["secret_scanning"] += counts["secret_scanning"]
            totals["skipped"] += counts["skipped"]
        except (httpx.HTTPError, SQLAlchemyError, KeyError, ValueError) as exc:
            logger.warning(
                "security_scan: repo=%s 처리 실패 err=%s",
                sanitize_for_log(repo.full_name), type(exc).__name__,
            )
            # 세션 오염 방지 — repo 처리 중 에러로 세션이 failed 상태면 다음 repo 가
            # InvalidRequestError 로 연쇄 실패 (사이클 159 — 158 회고 P2, api.md 세션 격리 원칙).
            # 단일 repo 함수 내부 롤백은 upsert 실패만 커버하므로 그 밖의 전파 에러를 여기서 격리한다.
            # Roll back to avoid a poisoned session cascading into the next repo.
            db.rollback()
    return totals
