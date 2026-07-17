"""리포 쓰기 액션 — `POST /repos/{name}/delete`."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from src.auth.session import CurrentUser, require_login
from src.database import SessionLocal
from src.ui._helpers import delete_repo_cascade, get_accessible_repo, get_locale

router = APIRouter()


@router.post("/repos/{repo_name:path}/delete")
async def delete_repo(
    request: Request,
    repo_name: str,
    current_user: Annotated[CurrentUser, Depends(require_login)],
):
    """리포지토리 + 연관 데이터(Webhook, Analysis, GateDecision, RepoConfig)를 삭제한다."""
    with SessionLocal() as db:
        repo = get_accessible_repo(
            db, repo_name, current_user, require_write=True, locale=get_locale(request),
        )
        await delete_repo_cascade(db, repo, current_user.plaintext_token or "")
    return RedirectResponse(url="/?deleted=1", status_code=303)
