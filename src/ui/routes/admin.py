"""SaaS admin UI routes — Cycle 79 PR 3a 신설.

`/admin/tenants` — tenant 인벤토리 dashboard (require_admin Depends).
`/admin/rls-audit` — RLS policy 적용 매트릭스 dashboard.

Phase 1 = read-only (자동 처리 X). Phase 2 영역 (결제 / 사용량 cap / API key) = 별도 PR.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.auth.session import CurrentUser, require_admin
from src.shared.feature_kill_switch import is_disabled
# SessionLocal = 웹 RLS 경로(rls-audit 진단). WorkerSessionLocal = 시스템 컨텍스트(tenants/operations).
# 분기 사유 상세: src/api/admin.py 주석 (UI 라우트도 동일 계약).
# SessionLocal = web RLS path (rls-audit). WorkerSessionLocal = system context (tenants/operations).
# Rationale detail: src/api/admin.py (the UI routes share the same contract).
from src.database import SessionLocal, WorkerSessionLocal
from src.services import operations_service, saas_service
from src.ui._helpers import get_locale, templates

router = APIRouter()


def _get_db():
    """웹 RLS 경로 세션 의존성 — rls-audit 진단 전용 (api/admin.py::_get_db 와 동일 계약).

    rls-audit 의 connection_bypasses_rls 실측이 웹 app role 로 평가돼야 정확 (worker = 항상 우회 오진단).
    Web RLS-path session — rls-audit only; must run as web app role for accurate bypass diagnosis.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_worker_db():
    """시스템 컨텍스트 세션 의존성 — tenants/operations cross-tenant 집계 전용 (RLS Phase 4).

    api/admin.py::_get_worker_db 와 동일 계약 — Phase 4 admin 세션 RLS under-report 방어.
    Same contract as api/admin.py::_get_worker_db — avoids Phase 4 admin-session-RLS under-report.
    """
    db = WorkerSessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/admin/tenants", response_class=HTMLResponse)
def admin_tenants(
    request: Request,
    admin: Annotated[CurrentUser, Depends(require_admin)],
    db: Annotated[Session, Depends(_get_worker_db)],
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
            "locale": get_locale(request),
        },
    )


@router.get("/admin/rls-audit", response_class=HTMLResponse)
def admin_rls_audit(
    request: Request,
    admin: Annotated[CurrentUser, Depends(require_admin)],
    db: Annotated[Session, Depends(_get_db)],
) -> HTMLResponse:
    """RLS policy 적용 매트릭스 admin dashboard + FORCE 실측 (RLS Phase 3).

    RLS policy matrix admin dashboard + live FORCE check (RLS Phase 3).
    """
    return templates.TemplateResponse(
        request,
        "admin_rls_audit.html",
        {
            "current_user": admin,
            "matrix": saas_service.rls_audit_matrix(),
            "summary": saas_service.rls_coverage_summary(db),
            "locale": get_locale(request),
        },
    )


@router.get("/admin/operations", response_class=HTMLResponse)
def admin_operations(
    request: Request,
    admin: Annotated[CurrentUser, Depends(require_admin)],
    db: Annotated[Session, Depends(_get_worker_db)],
    days: Annotated[int, Query(ge=1, le=365)] = 7,
) -> HTMLResponse:
    """운영 모니터링 KPI 5 카드 admin dashboard (Cycle 80 PR 2 — 영역 🅔).

    days 는 1~365 범위 강제 (API /api/admin/operations 대칭) — 상한 없으면 거대값이
    operations_service timedelta(days=...) 에서 OverflowError → HTTP 500.
    days is clamped to 1~365 (mirrors the API route); an unbounded huge value overflows
    timedelta(days=...) in operations_service → HTTP 500.

    Operations dashboard admin (Cycle 80 PR 2 — area 🅔).
    """
    # OPERATIONS_DASHBOARD_DISABLED=1 시 운영 대시보드 즉시 503 반환
    # Return 503 immediately when OPERATIONS_DASHBOARD_DISABLED=1
    if is_disabled("OPERATIONS_DASHBOARD"):
        raise HTTPException(status_code=503, detail="Operations dashboard is disabled")
    kpi = operations_service.operations_kpi(db, days=days)
    return templates.TemplateResponse(
        request,
        "admin_operations.html",
        {
            "current_user": admin,
            "kpi": kpi,
            "days": days,
            "locale": get_locale(request),
        },
    )
