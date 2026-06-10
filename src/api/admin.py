"""SaaS admin REST API — Cycle 79 PR 3a 신설.

`/api/admin/tenants` — tenant 인벤토리 (require_admin Depends — Cycle 79 PR 2 #255).
`/api/admin/rls-audit` — RLS policy 적용 매트릭스.

Phase 1 = read-only — INSERT/UPDATE/DELETE 영역 미포함 (정책 12 부합).
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.auth.session import CurrentUser, require_admin
# SessionLocal = 웹 RLS 경로(rls-audit 진단 — app role 의 BYPASSRLS 여부 평가).
# WorkerSessionLocal = 시스템 컨텍스트(tenants/operations cross-tenant 집계 — Phase 4 RLS 우회).
# SessionLocal = web RLS path (rls-audit diagnosis). WorkerSessionLocal = system context (cross-tenant).
from src.database import SessionLocal, WorkerSessionLocal
from src.services import operations_service, saas_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _get_db():
    """웹 RLS 경로 세션 의존성 — rls-audit 진단 전용.

    rls-audit 의 `connection_bypasses_rls` 는 **현재 connection 의 rolbypassrls** 를 실측하므로
    반드시 운영 웹 app role(비-BYPASSRLS) 로 실행돼야 정확하다. worker(BYPASSRLS)로 돌리면
    항상 우회=TRUE 로 오진단된다.
    Web RLS-path session — rls-audit only. Its connection_bypasses_rls reads the CURRENT
    connection's rolbypassrls, so it must run as the web app role for an accurate reading.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_worker_db():
    """시스템 컨텍스트 세션 의존성 — tenants/operations cross-tenant 집계 전용 (RLS Phase 4).

    tenant_inventory(User/Repository/Analysis)·operations_kpi(MergeAttempt/User)는 전체 테넌트
    집계라, Phase 4 비-BYPASSRLS app role 전환 시 admin 세션 RLS(app.user_id=admin)가 admin 본인
    행만 남겨 under-report 한다. worker(BYPASSRLS) 경유로 cross-tenant 가시성을 보존한다.
    DATABASE_URL_WORKER 미설정 시 WorkerSessionLocal is SessionLocal — 현행 동작 동일.
    System-context session — cross-tenant tenants/operations aggregates only (RLS Phase 4).
    Routes through the BYPASSRLS worker so the admin dashboard keeps full cross-tenant visibility
    after the Phase 4 app-role switch. Unset DATABASE_URL_WORKER → WorkerSessionLocal is SessionLocal.
    """
    db = WorkerSessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/tenants")
def get_tenants(
    _admin: Annotated[CurrentUser, Depends(require_admin)],
    db: Annotated[Session, Depends(_get_worker_db)],
) -> dict[str, Any]:
    """tenant 인벤토리 — 사용자별 repo_count + analysis_count + last_active_at.

    Tenant inventory — per-user repo_count + analysis_count + last_active_at.
    """
    inventory = saas_service.tenant_inventory(db)
    return {
        "total_tenants": len(inventory),
        "tenants": inventory,
    }


@router.get("/rls-audit")
def get_rls_audit(
    _admin: Annotated[CurrentUser, Depends(require_admin)],
    db: Annotated[Session, Depends(_get_db)],
) -> dict[str, Any]:
    """RLS policy 적용 매트릭스 (정적) + FORCE 실측 요약 (RLS Phase 3).

    RLS policy matrix (static) + live FORCE summary (RLS Phase 3).
    """
    return {
        "summary": saas_service.rls_coverage_summary(db),
        "matrix": saas_service.rls_audit_matrix(),
    }


@router.get("/operations")
def get_operations(
    _admin: Annotated[CurrentUser, Depends(require_admin)],
    db: Annotated[Session, Depends(_get_worker_db)],
    days: int = 7,
) -> dict[str, Any]:
    """admin 운영 모니터링 KPI 5 카드 (Cycle 80 PR 2 — 영역 🅔).

    Admin operations dashboard KPI 5 cards (Cycle 80 PR 2).
    """
    return operations_service.operations_kpi(db, days=days)
