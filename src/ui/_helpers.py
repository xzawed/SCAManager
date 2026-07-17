"""UI 공용 헬퍼 — templates, logger, 접근 제어, delete cascade.

각 `src/ui/routes/*.py` 가 본 모듈의 함수·상수를 import 해서 사용한다.
mock 전략: helper 자체를 patch 하려면 `src.ui._helpers.<name>` 경로 사용.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.auth.session import CurrentUser
from src.config import settings
from src.github_client.repos import delete_webhook
from src.i18n.loader import get_text
from src.models.analysis import Analysis
from src.models.gate_decision import GateDecision
from src.models.repository import Repository
from src.repositories import repo_config_repo, repository_repo
from src.shared.log_safety import sanitize_for_log

logger = logging.getLogger("src.ui")
templates = Jinja2Templates(directory="src/templates")

# Phase 2 PR-5 (사이클 84) — Jinja2 i18n 필터 등록 (i18n + i18n_args 사용 가능)
# Phase 2 PR-5 (Cycle 84) — Register Jinja2 i18n filters (i18n + i18n_args available)
from src.i18n.filters import register_i18n_filters  # noqa: E402  # pylint: disable=wrong-import-position

register_i18n_filters(templates.env)

# GitHub Webhook 수신 경로 — add_repo + settings 에서 사용 (상수화)
GITHUB_WEBHOOK_PATH = "/webhooks/github"


def get_locale(request: Request) -> str:
    """LocaleMiddleware 가 scope.state.locale 에 주입한 locale 반환.

    Return locale injected by LocaleMiddleware into scope.state.locale.

    LocaleMiddleware (src/middleware/locale.py) 가 매 request 시 5단계 감지
    (Cookie > Accept-Language > default > fallback) 후 scope["state"]["locale"]
    에 주입. 본 helper 가 모든 TemplateResponse 호출에서 동일 영역 사용 의무
    (정책 16 4번 원칙 — 사용처 ≥ 12 도달).

    LocaleMiddleware injects locale via 5-tier detection per request.
    This helper unifies access across all TemplateResponse calls (policy 16 #4).
    """
    try:
        return request.scope.get("state", {}).get("locale") or settings.default_locale
    except (AttributeError, KeyError):
        return settings.default_locale


def webhook_base_url(request: Request) -> str:
    """APP_BASE_URL 설정 시 해당 URL 우선 사용 (Railway HTTPS 보장)."""
    if settings.app_base_url:
        return settings.app_base_url.rstrip("/")
    return str(request.base_url).rstrip("/")


def get_accessible_repo(
    db: Session,
    repo_name: str,
    current_user: CurrentUser,
    *,
    require_write: bool = False,
    locale: str | None = None,
) -> Repository:
    """로그인 사용자가 접근 가능한 리포를 반환. 없거나 권한 없으면 404.

    Return a repo the logged-in user may access; 404 when missing or not theirs.

    🔴 `require_write=True` 는 **쓰기 라우트 전용** — `user_id IS NULL`(소유자 미등록) 리포에
    403 을 던진다. NULL-owner 리포는 `worker/pipeline.py:425` 가 미등록 저장소 웹훅마다 계속
    만들고, `models/repository.py:18` 의 `ondelete="SET NULL"` 로 사용자 삭제 시에도 생긴다.
    이 리포는 **모든 인증 사용자에게 보이므로**(0026 RLS 가 `user_id IS NULL` 을 명시적으로
    whitelist — 조회 노출은 의도된 설계) 쓰기까지 열어두면 아무나 타인 리포의 알림 채널을
    탈취하고 auto_merge 를 강제할 수 있다.

    🔴 default `False` 가 핵심 — 조회 라우트는 호출부를 건드리지 않아 "조회 현행 유지"가
    **구조적으로** 보장된다. keyword-only 라 위치 인자로 실수 주입되지 않는다.

    🔴 `require_write=True` is for write routes only: it 403s repos with no owner. Such repos are
    visible to every authenticated user by design (RLS 0026 whitelists `user_id IS NULL`), so
    leaving writes open lets anyone hijack another repo's notification channels and force
    auto-merge. The `False` default structurally preserves read behaviour at untouched call sites.

    복구 경로: `/repos/add` 재등록 → GitHub 멤버십 검증(`add_repo.py:124`) 후 소유권 이전.
    Recovery: re-register via `/repos/add`, which verifies GitHub membership before transfer.
    """
    repo = repository_repo.find_by_full_name(db, repo_name)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.user_id is not None and repo.user_id != current_user.id:
        raise HTTPException(status_code=404)
    if require_write and repo.user_id is None:
        # 404 가 아니라 403 — 이 리포는 목록·상세에서 이미 보인다(조회 허용). 404 로 숨기면
        # "저장소가 사라졌다"는 버그로 읽힌다. 403 + 복구 안내가 정확한 의미다.
        # 403, not 404 — the repo is already visible via list/detail, so hiding it would read as
        # "the repo vanished". 403 plus a recovery hint conveys the actual state.
        raise HTTPException(
            status_code=403,
            detail=get_text("errors.repo_unclaimed", locale or settings.default_locale),
        )
    return repo


async def delete_repo_cascade(db: Session, repo: Repository, github_token: str) -> None:
    """리포 + 연관 데이터(Webhook, GateDecision, Analysis, RepoConfig)를 모두 삭제한다.

    Webhook 삭제는 best-effort — GitHub API 실패 시에도 DB 정리는 계속 진행된다.
    """
    if repo.webhook_id:
        try:
            await delete_webhook(github_token, repo.full_name, repo.webhook_id)
        except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-except
            # best-effort: GitHub API 실패 시 운영 관측 위해 logger.warning (Railway 로그)
            # best-effort: log warning on GitHub API failure for observability (Railway logs)
            logger.warning(
                "delete_repo_cascade: webhook delete failed for %s: %s",
                sanitize_for_log(repo.full_name), type(exc).__name__,
            )

    analysis_ids = [
        row.id for row in db.query(Analysis.id).filter(Analysis.repo_id == repo.id).all()
    ]
    if analysis_ids:
        db.query(GateDecision).filter(
            GateDecision.analysis_id.in_(analysis_ids)
        ).delete(synchronize_session=False)

    db.query(Analysis).filter(Analysis.repo_id == repo.id).delete(synchronize_session=False)
    repo_config_repo.delete_by_full_name(db, repo.full_name)
    db.delete(repo)
    db.commit()
