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
from src.database import SessionLocal
from src.services import operations_service, saas_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _get_db():
    """DB 세션 의존성 (FastAPI 패턴)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/tenants")
def get_tenants(
    _admin: Annotated[CurrentUser, Depends(require_admin)],
    db: Annotated[Session, Depends(_get_db)],
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
) -> dict[str, Any]:
    """RLS policy 적용 매트릭스 (정적).

    RLS policy matrix (static).
    """
    return {
        "summary": saas_service.rls_coverage_summary(),
        "matrix": saas_service.rls_audit_matrix(),
    }


@router.get("/operations")
def get_operations(
    _admin: Annotated[CurrentUser, Depends(require_admin)],
    db: Annotated[Session, Depends(_get_db)],
    days: int = 7,
) -> dict[str, Any]:
    """admin 운영 모니터링 KPI 5 카드 (Cycle 80 PR 2 — 영역 🅔).

    Admin operations dashboard KPI 5 cards (Cycle 80 PR 2).
    """
    return operations_service.operations_kpi(db, days=days)
