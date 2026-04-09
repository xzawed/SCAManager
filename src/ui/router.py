"""Web UI router — Jinja2 dashboard pages for repos, analyses, and settings."""
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from src.config import settings
from src.database import SessionLocal
from src.models.repository import Repository
from src.models.analysis import Analysis
from src.models.repo_config import RepoConfig
from src.models.user import User
from src.auth.session import require_login
from src.config_manager.manager import get_repo_config, upsert_repo_config, RepoConfigData
from src.github_client.repos import list_user_repos, create_webhook, delete_webhook, commit_scamanager_files

templates = Jinja2Templates(directory="src/templates")
router = APIRouter()


def _webhook_base_url(request: Request) -> str:
    """APP_BASE_URL 설정 시 해당 URL 우선 사용 (Railway HTTPS 보장)."""
    if settings.app_base_url:
        return settings.app_base_url.rstrip("/")
    return str(request.base_url).rstrip("/")


@router.get("/repos/add", response_class=HTMLResponse)
async def add_repo_page(request: Request, current_user: User = Depends(require_login)):
    return templates.TemplateResponse(request, "add_repo.html", {"current_user": current_user})


@router.get("/api/github/repos")
async def github_repos_list(current_user: User = Depends(require_login)):
    with SessionLocal() as db:
        existing_names = {
            r.full_name for r in db.query(Repository).filter(
                Repository.user_id == current_user.id
            ).all()
        }
    repos = await list_user_repos(current_user.github_access_token or "")
    return [r for r in repos if r["full_name"] not in existing_names]


@router.post("/repos/add")
async def add_repo(request: Request, current_user: User = Depends(require_login)):
    form = await request.form()
    repo_full_name = (form.get("repo_full_name") or "").strip()
    if not repo_full_name:
        raise HTTPException(status_code=400, detail="리포 이름이 필요합니다")

    with SessionLocal() as db:
        existing = db.query(Repository).filter(
            Repository.full_name == repo_full_name
        ).first()
        if existing:
            if existing.user_id is not None:
                return RedirectResponse(
                    url="/repos/add?error=이미+다른+사용자가+등록한+리포입니다",
                    status_code=303,
                )
            # user_id=NULL인 기존 리포 → 현재 사용자가 소유권 획득
            existing.user_id = current_user.id
            db.commit()
            return RedirectResponse(url=f"/repos/{repo_full_name}", status_code=303)

    webhook_secret = secrets.token_hex(32)
    hook_token = secrets.token_hex(32)
    webhook_url = _webhook_base_url(request) + "/webhooks/github"
    webhook_id = await create_webhook(
        current_user.github_access_token or "",
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

        config = db.query(RepoConfig).filter(
            RepoConfig.repo_full_name == repo_full_name
        ).first()
        if config is None:
            config = RepoConfig(repo_full_name=repo_full_name, hook_token=hook_token)
            db.add(config)
        else:
            config.hook_token = hook_token
        db.commit()

    # .scamanager/ 파일을 Repo에 커밋 (실패해도 등록 자체는 성공)
    server_url = str(request.base_url).rstrip("/")
    await commit_scamanager_files(
        current_user.github_access_token or "",
        repo_full_name,
        server_url,
        hook_token,
    )

    return RedirectResponse(
        url=f"/repos/{repo_full_name}?hook_installed=1",
        status_code=303,
    )


@router.get("/", response_class=HTMLResponse)
def overview(request: Request, current_user: User = Depends(require_login)):
    with SessionLocal() as db:
        repos = db.query(Repository).filter(
            (Repository.user_id == current_user.id) | (Repository.user_id.is_(None))
        ).order_by(Repository.created_at.desc()).all()
        repo_data = []
        if repos:
            repo_ids = [r.id for r in repos]

            # 분석 수 배치 조회 (N+1 방지)
            count_map = dict(
                db.query(Analysis.repo_id, func.count(Analysis.id))
                .filter(Analysis.repo_id.in_(repo_ids))
                .group_by(Analysis.repo_id)
                .all()
            )

            # 평균 점수 배치 조회
            avg_map = dict(
                db.query(Analysis.repo_id, func.avg(Analysis.score))
                .filter(Analysis.repo_id.in_(repo_ids))
                .group_by(Analysis.repo_id)
                .all()
            )

            # 리포별 최신 분석 배치 조회
            latest_id_subq = (
                db.query(func.max(Analysis.id))
                .filter(Analysis.repo_id.in_(repo_ids))
                .group_by(Analysis.repo_id)
                .subquery()
            )
            latest_map = {
                a.repo_id: a
                for a in db.query(Analysis).filter(Analysis.id.in_(latest_id_subq)).all()
            }

            for r in repos:
                latest = latest_map.get(r.id)
                repo_data.append({
                    "full_name": r.full_name,
                    "analysis_count": count_map.get(r.id, 0),
                    "avg_score": round(avg_map.get(r.id) or 0),
                    "latest_score": latest.score if latest else None,
                    "latest_grade": latest.grade if latest else None,
                })
    return templates.TemplateResponse(request, "overview.html", {
        "repos": repo_data,
        "current_user": current_user,
    })


@router.get("/repos/{repo_name:path}/settings", response_class=HTMLResponse)
def repo_settings(
    request: Request,
    repo_name: str,
    hook_ok: int = 0,
    hook_fail: int = 0,
    current_user: User = Depends(require_login),
):
    with SessionLocal() as db:
        repo = db.query(Repository).filter(Repository.full_name == repo_name).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        if repo.user_id is not None and repo.user_id != current_user.id:
            raise HTTPException(status_code=404)
        config = get_repo_config(db, repo_name)
    return templates.TemplateResponse(request, "settings.html", {
        "repo_name": repo_name, "config": config,
        "hook_ok": bool(hook_ok), "hook_fail": bool(hook_fail),
        "current_user": current_user,
    })


@router.post("/repos/{repo_name:path}/settings")
async def update_repo_settings(
    request: Request,
    repo_name: str,
    current_user: User = Depends(require_login),  # pylint: disable=unused-argument
):
    form = await request.form()
    with SessionLocal() as db:
        repo = db.query(Repository).filter(Repository.full_name == repo_name).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        if repo.user_id is not None and repo.user_id != current_user.id:
            raise HTTPException(status_code=403)
        upsert_repo_config(db, RepoConfigData(
            repo_full_name=repo_name,
            gate_mode=form.get("gate_mode", "disabled"),
            auto_approve_threshold=int(form.get("auto_approve_threshold", 75)),
            auto_reject_threshold=int(form.get("auto_reject_threshold", 50)),
            notify_chat_id=form.get("notify_chat_id") or None,
            n8n_webhook_url=form.get("n8n_webhook_url", ""),
            discord_webhook_url=form.get("discord_webhook_url", "") or None,
            slack_webhook_url=form.get("slack_webhook_url", "") or None,
            custom_webhook_url=form.get("custom_webhook_url", "") or None,
            email_recipients=form.get("email_recipients", "") or None,
            auto_merge=form.get("auto_merge") == "on",
        ))
    return RedirectResponse(url=f"/repos/{repo_name}/settings", status_code=303)


@router.post("/repos/{repo_name:path}/reinstall-hook")
async def reinstall_hook(
    request: Request,
    repo_name: str,
    current_user: User = Depends(require_login),
):
    """기존 등록 리포에 .scamanager/ 파일을 재커밋한다."""
    with SessionLocal() as db:
        repo = db.query(Repository).filter(Repository.full_name == repo_name).first()
        if not repo or (repo.user_id is not None and repo.user_id != current_user.id):
            raise HTTPException(status_code=404)

        config = db.query(RepoConfig).filter(
            RepoConfig.repo_full_name == repo_name
        ).first()
        if config is None:
            config = RepoConfig(
                repo_full_name=repo_name,
                hook_token=secrets.token_hex(32),
            )
            db.add(config)
        elif not config.hook_token:
            config.hook_token = secrets.token_hex(32)
        db.commit()
        hook_token = config.hook_token

    server_url = _webhook_base_url(request)
    ok = await commit_scamanager_files(
        current_user.github_access_token or "",
        repo_name,
        server_url,
        hook_token,
    )

    status = "hook_ok" if ok else "hook_fail"
    return RedirectResponse(
        url=f"/repos/{repo_name}/settings?{status}=1",
        status_code=303,
    )


@router.post("/repos/{repo_name:path}/reinstall-webhook")
async def reinstall_webhook(
    request: Request,
    repo_name: str,
    current_user: User = Depends(require_login),
):
    """GitHub Webhook을 삭제하고 새 URL(HTTPS)로 재등록한다."""
    with SessionLocal() as db:
        repo = db.query(Repository).filter(Repository.full_name == repo_name).first()
        if not repo or (repo.user_id is not None and repo.user_id != current_user.id):
            raise HTTPException(status_code=404)

        token = current_user.github_access_token or ""

        if repo.webhook_id:
            await delete_webhook(token, repo_name, repo.webhook_id)

        new_secret = secrets.token_hex(32)
        webhook_url = _webhook_base_url(request) + "/webhooks/github"
        new_id = await create_webhook(token, repo_name, webhook_url, new_secret)

        repo.webhook_id = new_id
        repo.webhook_secret = new_secret
        db.commit()

    return RedirectResponse(
        url=f"/repos/{repo_name}/settings?hook_ok=1",
        status_code=303,
    )


@router.get("/repos/{repo_name:path}/analyses/{analysis_id}", response_class=HTMLResponse)
def analysis_detail(
    request: Request, repo_name: str, analysis_id: int,
    current_user: User = Depends(require_login),
):
    with SessionLocal() as db:
        repo = db.query(Repository).filter(Repository.full_name == repo_name).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        if repo.user_id is not None and repo.user_id != current_user.id:
            raise HTTPException(status_code=404)
        analysis = db.query(Analysis).filter(
            Analysis.id == analysis_id, Analysis.repo_id == repo.id
        ).first()
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        result = analysis.result or {}
        source = result.get("source") or ("pr" if analysis.pr_number else "push")
        data = {
            "id": analysis.id,
            "commit_sha": analysis.commit_sha,
            "commit_message": analysis.commit_message,
            "pr_number": analysis.pr_number,
            "score": analysis.score,
            "grade": analysis.grade,
            "result": result,
            "source": source,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        }
    return templates.TemplateResponse(request, "analysis_detail.html", {
        "repo_name": repo_name, "analysis": data, "current_user": current_user,
    })


@router.get("/repos/{repo_name:path}", response_class=HTMLResponse)
def repo_detail(
    request: Request,
    repo_name: str,
    hook_installed: int = 0,
    current_user: User = Depends(require_login),
):
    with SessionLocal() as db:
        repo = db.query(Repository).filter(Repository.full_name == repo_name).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        if repo.user_id is not None and repo.user_id != current_user.id:
            raise HTTPException(status_code=404)
        analyses = (db.query(Analysis).filter(Analysis.repo_id == repo.id)
                    .order_by(Analysis.created_at.desc()).limit(100).all())
        analyses_data = [
            {"id": a.id, "commit_sha": a.commit_sha, "pr_number": a.pr_number,
             "commit_message": a.commit_message,
             "score": a.score, "grade": a.grade,
             "source": (a.result or {}).get("source") or ("pr" if a.pr_number else "push"),
             "created_at": a.created_at.isoformat() if a.created_at else None}
            for a in analyses
        ]
        rev = list(reversed(analyses_data))
    return templates.TemplateResponse(request, "repo_detail.html", {
        "repo_name": repo_name, "analyses": analyses_data,
        "chart_labels": [a["created_at"][:10] if a["created_at"] else "" for a in rev],
        "chart_scores": [a["score"] for a in rev],
        "hook_installed": bool(hook_installed),
        "current_user": current_user,
    })
