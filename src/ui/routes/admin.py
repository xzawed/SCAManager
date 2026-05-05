"""SaaS admin UI routes — Cycle 79 PR 3a 신설.

`/admin/tenants` — tenant 인벤토리 dashboard (require_admin Depends).
`/admin/rls-audit` — RLS policy 적용 매트릭스 dashboard.

Phase 1 = read-only (자동 처리 X). Phase 2 영역 (결제 / 사용량 cap / API key) = 별도 PR.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.auth.session import CurrentUser, require_admin
from src.database import SessionLocal
from src.services import saas_service
from src.ui._helpers import templates

router = APIRouter()


def _get_db():
    """DB 세션 의존성 (FastAPI 패턴 — api/admin.py 와 동일)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/admin/tenants", response_class=HTMLResponse)
def admin_tenants(
    request: Request,
    admin: Annotated[CurrentUser, Depends(require_admin)],
    db: Annotated[Session, Depends(_get_db)],
) -> HTMLResponse:
    """tenant 인벤토리 admin dashboard.

    Tenant inventory admin dashboard.
    """
    inventory = saas_service.tenant_inventory(db)
    # starlette 신 시그니처 — request 첫 인자 의무 (구 버전 = TypeError: unhashable type: 'dict')
    # starlette new signature — request first arg required (old version raises TypeError)
    return templates.TemplateResponse(
        request,
        "admin_tenants.html",
        {
            "current_user": admin,
            "tenants": inventory,
            "total_tenants": len(inventory),
        },
    )


@router.get("/admin/rls-audit", response_class=HTMLResponse)
def admin_rls_audit(
    request: Request,
    admin: Annotated[CurrentUser, Depends(require_admin)],
) -> HTMLResponse:
    """RLS policy 적용 매트릭스 admin dashboard.

    RLS policy matrix admin dashboard.
    """
    return templates.TemplateResponse(
        request,
        "admin_rls_audit.html",
        {
            "current_user": admin,
            "matrix": saas_service.rls_audit_matrix(),
            "summary": saas_service.rls_coverage_summary(),
        },
    )
