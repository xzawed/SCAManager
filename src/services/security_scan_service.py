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

import logging
import os
from typing import Any

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.models.repository import Repository
from src.repositories import security_alert_log_repo
from src.shared.http_client import get_http_client
from src.shared.log_safety import sanitize_for_log

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_KILL_SWITCH_ENV = "SECURITY_AUTO_PROCESS_DISABLED"


def is_kill_switch_active() -> bool:
    """kill-switch 환경변수 검사 (Phase 9 패턴 차용 — `SCAMANAGER_SELF_ANALYSIS_DISABLED`).

    Check kill-switch env var (Phase 9 pattern — SCAMANAGER_SELF_ANALYSIS_DISABLED).
    """
    return os.environ.get(_KILL_SWITCH_ENV, "0") == "1"


def _resolve_token(user) -> str | None:
    """사용자 토큰 우선 + 전역 fallback (`merge_retry_service._resolve_github_token` 패턴).

    User token first + global fallback (merge_retry_service._resolve_github_token pattern).
    """
    if user is not None and getattr(user, "github_access_token", None):
        try:
            return user.plaintext_token
        except Exception:  # pylint: disable=broad-except  # noqa: BLE001
            return None
    return os.environ.get("GITHUB_TOKEN") or None


async def _fetch_alerts(
    token: str, repo_full_name: str, alert_kind: str,
) -> list[dict[str, Any]] | None:
    """GitHub Security alerts API 호출 (graceful degradation).

    Call GitHub Security alerts API (graceful degradation).
    alert_kind = "code-scanning" | "secret-scanning".
    Returns None on GHAS 비활성 (403/404) — silent skip + WARNING.
    """
    url = f"{_GITHUB_API}/repos/{repo_full_name}/{alert_kind}/alerts"
    client = get_http_client()
    try:
        resp = await client.get(
            url,
            params={"state": "open", "per_page": 100},
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
            },
        )
    except httpx.HTTPError as exc:
        logger.warning(
            "security_scan: API 호출 실패 repo=%s kind=%s err=%s",
            sanitize_for_log(repo_full_name), alert_kind, type(exc).__name__,
        )
        return None
    if resp.status_code in (403, 404):
        # GHAS 비활성 (private repo + Advanced Security off) — silent skip
        # GHAS inactive (private repo + Advanced Security off) — silent skip
        logger.info(
            "security_scan: GHAS 비활성 repo=%s kind=%s status=%d (skip)",
            sanitize_for_log(repo_full_name), alert_kind, resp.status_code,
        )
        return None
    if resp.status_code != 200:
        logger.warning(
            "security_scan: 비정상 응답 repo=%s kind=%s status=%d",
            sanitize_for_log(repo_full_name), alert_kind, resp.status_code,
        )
        return None
    try:
        return resp.json() or []
    except (ValueError, KeyError):
        return None


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
    Returns: {"code_scanning": N, "secret_scanning": M, "skipped": K}.
    """
    counts = {"code_scanning": 0, "secret_scanning": 0, "skipped": 0}
    if is_kill_switch_active():
        counts["skipped"] = 1
        return counts
    token = _resolve_token(user)
    if token is None:
        logger.info("security_scan: token 없음 repo=%s (skip)", sanitize_for_log(repo.full_name))
        counts["skipped"] = 1
        return counts

    for kind, key in (("code-scanning", "code_scanning"), ("secret-scanning", "secret_scanning")):
        alerts = await _fetch_alerts(token, repo.full_name, kind)
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
                    "security_scan: log upsert 실패 repo=%s kind=%s err=%s",
                    sanitize_for_log(repo.full_name), kind, type(exc).__name__,
                )
                db.rollback()
    return counts


async def scan_all_repos(db: Session) -> dict[str, int]:
    """모든 repo 일괄 scan (cron 트리거 진입점 — `cron_service` 패턴 차용).

    Scan all repos in batch (cron entry point — cron_service pattern).
    """
    totals = {"code_scanning": 0, "secret_scanning": 0, "skipped": 0, "repos": 0}
    if is_kill_switch_active():
        logger.info("security_scan: kill-switch 활성 — 전체 skip")
        totals["skipped"] = -1  # sentinel = kill-switch
        return totals
    repos = db.query(Repository).all()
    for repo in repos:
        totals["repos"] += 1
        try:
            counts = await scan_repo_alerts(db, repo)
            totals["code_scanning"] += counts["code_scanning"]
            totals["secret_scanning"] += counts["secret_scanning"]
            totals["skipped"] += counts["skipped"]
        except (httpx.HTTPError, SQLAlchemyError, KeyError, ValueError) as exc:
            logger.warning(
                "security_scan: repo=%s 처리 실패 err=%s",
                sanitize_for_log(repo.full_name), type(exc).__name__,
            )
    return totals
