"""리포 추가 페이지 + GitHub 리포 목록 + `POST /repos/add`."""
from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.auth.session import CurrentUser, require_login
from src.database import SessionLocal
from src.github_client.repos import (
    commit_scamanager_files,
    create_webhook,
    list_user_repos,
)
from src.models.repo_config import RepoConfig
from src.models.repository import Repository
from src.repositories import repo_config_repo, repository_repo
from src.ui._helpers import GITHUB_WEBHOOK_PATH, templates, webhook_base_url

router = APIRouter()


@router.get("/repos/add", response_class=HTMLResponse)
async def add_repo_page(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_login)],
):
    """리포 추가 페이지를 렌더링한다."""
    return templates.TemplateResponse(request, "add_repo.html", {"current_user": current_user})


@router.get("/api/github/repos")
async def github_repos_list(
    current_user: Annotated[CurrentUser, Depends(require_login)],
):
    """사용자의 GitHub 리포 목록 중 미등록 리포만 반환한다."""
    with SessionLocal() as db:
        existing_names = {
            r.full_name for r in db.query(Repository).filter(
                Repository.user_id == current_user.id
            ).all()
        }
    repos = await list_user_repos(current_user.plaintext_token or "")
    return [r for r in repos if r["full_name"] not in existing_names]


@router.post("/repos/add")
async def add_repo(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_login)],
):
    """리포를 등록하고 GitHub Webhook을 생성한다."""
    form = await request.form()
    repo_full_name = (form.get("repo_full_name") or "").strip()
    if not repo_full_name:
        raise HTTPException(status_code=400, detail="리포 이름이 필요합니다")

    with SessionLocal() as db:
        existing = repository_repo.find_by_full_name(db, repo_full_name)
        if existing:
            if existing.user_id is not None:
                return RedirectResponse(
                    url="/repos/add?error=이미+다른+사용자가+등록한+리포입니다",
                    status_code=303,
                )
            existing.user_id = current_user.id
            db.commit()
            return RedirectResponse(url=f"/repos/{repo_full_name}", status_code=303)

    webhook_secret = secrets.token_hex(32)
    hook_token = secrets.token_hex(32)
    webhook_url = webhook_base_url(request) + GITHUB_WEBHOOK_PATH
    webhook_id = await create_webhook(
        current_user.plaintext_token or "",
        repo_full_name,
        webhook_url,
        webhook_secret,
    )

    with SessionLocal() as db:
        repo = Repository(
            full_name=repo_full_name,
            user_id=current_user.id,
            webhook_secret=webhook_secret,
            webhook_id=webhook_id,
        )
        db.add(repo)
        db.commit()

        config = repo_config_repo.find_by_full_name(db, repo_full_name)
        if config is None:
            config = RepoConfig(repo_full_name=repo_full_name, hook_token=hook_token)
            db.add(config)
        else:
            config.hook_token = hook_token
        db.commit()

    server_url = str(request.base_url).rstrip("/")
    await commit_scamanager_files(
        current_user.plaintext_token or "",
        repo_full_name,
        server_url,
        hook_token,
    )

    return RedirectResponse(
        url=f"/repos/{repo_full_name}?hook_installed=1",
        status_code=303,
    )
