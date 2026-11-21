"""내부 Cron 엔드포인트 — Railway native cron 트리거용.
Internal cron endpoints — triggered by Railway native cron jobs.

🔴 인앱 스케줄러(`src/scheduler.py`)와 같은 작업의 HTTP 쌍둥이다 — 세션 만들기 · 닫기와 동기 작업은 스케줄러와
같이 워커 스레드에서(`session_off_loop` · `run_blocking`). 루프 위의 동기 DB 는 왕복마다 프로세스의 모든 요청을
세운다(회고 원장 L17 P2-34).
The HTTP twin of the in-app scheduler jobs: session create/close and sync work run off the loop, as there.

인증: INTERNAL_CRON_API_KEY 헤더 (admin api_key와 분리).
Auth: INTERNAL_CRON_API_KEY header (separate from admin api_key).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from src.config import settings
from src.database import WorkerSessionLocal as SessionLocal
from src.shared.secure_compare import secure_str_compare
from src.services.cron_service import (
    run_retention_sweep,
    run_trend_check,
    run_weekly_reports,
    sweep_analysis_attempts,
)
from src.services.db_heartbeat_service import run_db_heartbeat
from src.services.merge_retry_service import process_pending_retries
from src.services.model_catalog_service import refresh_catalog
from src.services.security_scan_service import scan_all_repos
from src.shared.off_loop import run_blocking, session_off_loop

logger = logging.getLogger(__name__)

# cron 전용 API 키 헤더 스키마 — admin X-API-Key와 동일 헤더명이지만 별도 검증 로직
# Cron-specific API key header — same header name as admin but validated separately
_cron_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _require_cron_key(
    api_key: str | None = Security(_cron_key_header),
) -> None:
    """INTERNAL_CRON_API_KEY 검증.
    Validate the INTERNAL_CRON_API_KEY.

    - 키 미설정 시 503 반환 (운영 환경에서 미설정 차단)
    - 키 불일치 시 401 반환 (타이밍 안전 비교)
    - Returns 503 if key is not configured (blocks accidental open access)
    - Returns 401 on mismatch (timing-safe comparison)
    """
    expected = settings.internal_cron_api_key
    # 키 미설정 시 503 — 실수로 빈 설정에서 노출 방지
    # Return 503 if unconfigured — prevents accidental open access
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Cron API key not configured",
        )
    # 타이밍 공격 방지 + 비-ASCII TypeError 방지를 위해 secure_str_compare 사용 (Task9 #9/#10)
    # Use secure_str_compare for timing-safety + non-ASCII TypeError protection
    if api_key is None or not secure_str_compare(expected, api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid cron API key",
        )


router = APIRouter(
    prefix="/api/internal/cron",
    # 라우터 레벨 인증 — 모든 cron 엔드포인트에 일괄 적용
    # Router-level auth dependency — applied to all cron endpoints uniformly
    dependencies=[Depends(_require_cron_key)],
)


@router.post("/weekly", status_code=200)
async def trigger_weekly_reports() -> dict:
    """주간 리포트 cron 트리거.
    Trigger weekly report sending for all repositories.

    Returns:
        {"status": "ok", "sent": <int>} — 발송된 리포트 수
        {"status": "ok", "sent": <int>} — number of reports sent
    """
    # 세션 만들기 · 닫기는 워커 스레드에서 — 스케줄러 job 과 같은 도우미
    # Session create/close off the loop — the same helper as the scheduler job
    async with session_off_loop(SessionLocal) as db:
        sent = await run_weekly_reports(db)
    logger.info("weekly_reports: sent=%d", sent)
    return {"status": "ok", "sent": sent}


@router.post("/trend", status_code=200)
async def trigger_trend_check() -> dict:
    """트렌드 체크 cron 트리거.
    Trigger trend-check alerts for all repositories.

    Returns:
        {"status": "ok", "alerted": <int>} — 경고 발송된 리포 수
        {"status": "ok", "alerted": <int>} — number of repos that received an alert
    """
    # 세션 만들기 · 닫기는 워커 스레드에서 — 스케줄러 job 과 같은 도우미
    # Session create/close off the loop — the same helper as the scheduler job
    async with session_off_loop(SessionLocal) as db:
        alerted = await run_trend_check(db)
    logger.info("trend_check: alerted=%d", alerted)
    return {"status": "ok", "alerted": alerted}


@router.post("/scan-security", status_code=200)
async def trigger_security_scan() -> dict:
    """Cycle 73 F1 — GitHub Code Scanning + Secret Scanning alert 폴링 cron 트리거.

    Cycle 73 F1 — trigger GitHub Code/Secret Scanning alert polling (cron).

    Returns:
        {"status": "ok", "totals": {"code_scanning": N, "secret_scanning": M, "skipped": K, "repos": R}}
    """
    # F1 read-only (audit log upsert 만, dismiss X) — 세션 만들기 · 닫기는 워커 스레드에서
    # F1 read-only (audit log upsert only, no dismiss); session create/close off the loop
    async with session_off_loop(SessionLocal) as db:
        totals = await scan_all_repos(db)
    logger.info("security_scan: totals=%s", totals)
    return {"status": "ok", "totals": totals}


@router.post("/retry-pending-merges", status_code=200)
async def trigger_retry_pending_merges() -> dict:
    """CI-aware Auto Merge 재시도 큐 처리 cron 트리거.
    Trigger processing of the pending CI-aware auto-merge retry queue.

    Returns:
        {"status": "ok", "counts": {...}} — 처리 결과 카운트
        {"status": "ok", "counts": {...}} — processing result counts
    """
    # 세션 만들기 · 닫기는 워커 스레드에서 — 스케줄러 job 과 같은 도우미
    # Session create/close off the loop — the same helper as the scheduler job
    async with session_off_loop(SessionLocal) as db:
        counts = await process_pending_retries(
            db, limit=settings.merge_retry_worker_batch_size
        )
    logger.info("retry_pending_merges: counts=%s", counts)
    return {"status": "ok", "counts": counts}


@router.post("/db-heartbeat", status_code=200)
async def trigger_db_heartbeat() -> dict:
    """DB 쓰기 하트비트 1회 — 웹 · 워커 풀마다 세션 READ ONLY 를 되돌리거나 쓰기 경로를 잰다(회고 원장 L02).
    Run the DB write heartbeat once for the web and worker pools.

    Returns:
        {"status": "ok", "results": {"web": "ok", "worker": "healed", ...}}
    """
    results = await run_db_heartbeat()
    logger.info("db_heartbeat: results=%s", results)
    return {"status": "ok", "results": results}


@router.post("/sweep-orphans", status_code=200)
async def trigger_sweep_orphans() -> dict:
    """분석 소실 탐지 흔적(analysis_attempts) sweep cron 트리거 — #1060 find_orphaned 배선.

    Trigger the analysis-attempts orphan sweep (wires up #1060's loss detection).

    SIGTERM/OOM 로 증발한 분석의 흔적을 로그+운영자 Telegram 으로 표면화하고 정리한다(준비도 감사 #11).
    """
    async with session_off_loop(SessionLocal) as db:
        surfaced = await sweep_analysis_attempts(db)
    logger.info("sweep_orphans: surfaced=%d", surfaced)
    return {"status": "ok", "orphans_surfaced": surfaced}


@router.post("/retention-sweep", status_code=200)
async def trigger_retention_sweep() -> dict:
    """데이터 보존 sweep cron 트리거 — 만료 캐시 + 종결 큐 행 GC (준비도 감사 #12·#20).

    Trigger the retention sweep — GC expired cache + terminal queue rows.
    """
    # 🔴 sweep 은 동기 함수다 — 통째로 워커 스레드에서(스케줄러와 같다). 루프에서 돌면 DELETE 왕복마다 선다.
    # The sweep is synchronous: run it whole in a worker thread, as the scheduler does.
    async with session_off_loop(SessionLocal) as db:
        counts = await run_blocking(run_retention_sweep, db)
    logger.info("retention_sweep: counts=%s", counts)
    return {"status": "ok", "counts": counts}


@router.post("/sync-claude-models", status_code=200)
async def trigger_sync_claude_models() -> dict:
    """Claude 모델 목록 동기화 · 쓰는 계열의 새 판 시험 1회 — 스케줄러 `sync-claude-models` 의 HTTP 쌍둥이(#1905).

    Run the Claude model listing sync and probes once; the HTTP twin of the scheduler job (#1905).
    🔴 새 판 시험은 유료 호출이다(작은 JSON 요청 · 판마다 한 번). / Probes are small paid calls, once per new model.

    Returns:
        {"status": "ok", "source": "api", "promoted": {...}, "failed": {...}} · 키가 없으면 {"status": "skipped", ...}
    """
    if not settings.anthropic_api_key:
        logger.info("sync_claude_models: skipped — ANTHROPIC_API_KEY is not set")
        return {"status": "skipped", "reason": "anthropic_api_key_missing"}
    report = await refresh_catalog(api_key=settings.anthropic_api_key, session_factory=SessionLocal)
    logger.info("sync_claude_models: source=%s promoted=%s failed=%s", report.source, report.promoted, report.failed)
    return {"status": "ok", "source": report.source, "promoted": report.promoted, "failed": report.failed}
