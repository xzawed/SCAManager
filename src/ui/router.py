"""Web UI router — Jinja2 dashboard pages for repos, analyses, and settings."""
import logging
import secrets
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from src.config import settings
from src.database import SessionLocal
from src.models.repository import Repository
from src.models.analysis import Analysis
from src.models.repo_config import RepoConfig
from src.models.gate_decision import GateDecision
from src.auth.session import require_login, CurrentUser
from src.repositories import repo_config_repo
from src.config_manager.manager import get_repo_config, upsert_repo_config, RepoConfigData
from src.scorer.calculator import calculate_grade
from src.github_client.repos import (
    list_user_repos,
    create_webhook,
    delete_webhook,
    list_webhooks,
    commit_scamanager_files,
)

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="src/templates")
router = APIRouter()


def _webhook_base_url(request: Request) -> str:
    """APP_BASE_URL 설정 시 해당 URL 우선 사용 (Railway HTTPS 보장)."""
    if settings.app_base_url:
        return settings.app_base_url.rstrip("/")
    return str(request.base_url).rstrip("/")


def _get_accessible_repo(db, repo_name: str, current_user: CurrentUser) -> Repository:
    """로그인 사용자가 접근 가능한 리포를 반환. 없거나 권한 없으면 404."""
    repo = db.query(Repository).filter(Repository.full_name == repo_name).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.user_id is not None and repo.user_id != current_user.id:
        raise HTTPException(status_code=404)
    return repo


async def _delete_repo_cascade(db, repo: Repository, github_token: str) -> None:
    """리포 + 연관 데이터(Webhook, GateDecision, Analysis, RepoConfig)를 모두 삭제한다.

    Webhook 삭제는 best-effort — GitHub API 실패 시에도 DB 정리는 계속 진행된다.
    """
    # 1. GitHub Webhook 삭제 (best-effort — httpx·네트워크·권한 등 모든 예외 무시)
    if repo.webhook_id:
        try:
            await delete_webhook(github_token, repo.full_name, repo.webhook_id)
        except Exception:  # nosec B110  # pylint: disable=broad-except
            pass

    # 2. GateDecision 삭제 (Analysis.id FK 참조)
    analysis_ids = [
        row.id for row in db.query(Analysis.id).filter(Analysis.repo_id == repo.id).all()
    ]
    if analysis_ids:
        db.query(GateDecision).filter(
            GateDecision.analysis_id.in_(analysis_ids)
        ).delete(synchronize_session=False)

    # 3. Analysis 삭제
    db.query(Analysis).filter(Analysis.repo_id == repo.id).delete(synchronize_session=False)

    # 4. RepoConfig 삭제 (FK 아님 — full_name 기반)
    repo_config_repo.delete_by_full_name(db, repo.full_name)

    # 5. Repository 삭제
    db.delete(repo)
    db.commit()


@router.get("/repos/add", response_class=HTMLResponse)
async def add_repo_page(request: Request, current_user: CurrentUser = Depends(require_login)):
    """리포 추가 페이지를 렌더링한다."""
    return templates.TemplateResponse(request, "add_repo.html", {"current_user": current_user})


@router.get("/api/github/repos")
async def github_repos_list(current_user: CurrentUser = Depends(require_login)):
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
async def add_repo(request: Request, current_user: CurrentUser = Depends(require_login)):
    """리포를 등록하고 GitHub Webhook을 생성한다."""
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

    # .scamanager/ 파일을 Repo에 커밋 (실패해도 등록 자체는 성공)
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


@router.get("/", response_class=HTMLResponse)
def overview(request: Request, current_user: CurrentUser = Depends(require_login)):
    """전체 리포 현황 대시보드를 렌더링한다."""
    with SessionLocal() as db:
        repos = db.query(Repository).filter(
            (Repository.user_id == current_user.id) | (Repository.user_id.is_(None))
        ).order_by(Repository.created_at.desc()).all()
        repo_data = []
        if repos:
            repo_ids = [r.id for r in repos]

            # 분석 수 배치 조회 (N+1 방지)
            count_map = dict(
                db.query(Analysis.repo_id, func.count(Analysis.id))  # pylint: disable=not-callable
                .filter(Analysis.repo_id.in_(repo_ids))
                .group_by(Analysis.repo_id)
                .all()
            )

            # 평균 점수 배치 조회
            avg_map = dict(
                db.query(Analysis.repo_id, func.avg(Analysis.score))  # pylint: disable=not-callable
                .filter(Analysis.repo_id.in_(repo_ids))
                .group_by(Analysis.repo_id)
                .all()
            )

            for r in repos:
                count = count_map.get(r.id, 0)
                avg = round(avg_map.get(r.id) or 0)
                repo_data.append({
                    "full_name": r.full_name,
                    "analysis_count": count,
                    "avg_score": avg,
                    "avg_grade": calculate_grade(avg) if count > 0 else None,
                })
    return templates.TemplateResponse(request, "overview.html", {
        "repos": repo_data,
        "current_user": current_user,
    })


@router.get("/repos/{repo_name:path}/settings", response_class=HTMLResponse)
def repo_settings(  # pylint: disable=too-many-positional-arguments
    request: Request,
    repo_name: str,
    hook_ok: int = 0,
    hook_fail: int = 0,
    saved: int = 0,
    save_error: int = 0,
    current_user: CurrentUser = Depends(require_login),
):
    """리포 Gate·알림 설정 페이지를 렌더링한다."""
    with SessionLocal() as db:
        _get_accessible_repo(db, repo_name, current_user)
        config = get_repo_config(db, repo_name)
        config_orm = repo_config_repo.find_by_full_name(db, repo_name)
        railway_webhook_token = config_orm.railway_webhook_token if config_orm else None
        railway_api_token_set = bool(config_orm and config_orm.railway_api_token)
    railway_webhook_url = ""
    if railway_webhook_token:
        base = _webhook_base_url(request)
        railway_webhook_url = f"{base}/webhooks/railway/{railway_webhook_token}"
    return templates.TemplateResponse(request, "settings.html", {
        "repo_name": repo_name, "config": config,
        "hook_ok": bool(hook_ok), "hook_fail": bool(hook_fail),
        "saved": bool(saved), "save_error": bool(save_error),
        "current_user": current_user,
        "railway_webhook_url": railway_webhook_url,
        "railway_api_token_set": railway_api_token_set,
    })


@router.post("/repos/{repo_name:path}/settings")
async def update_repo_settings(
    request: Request,
    repo_name: str,
    current_user: CurrentUser = Depends(require_login),  # pylint: disable=unused-argument
):
    """폼 데이터로 리포 Gate·알림 설정을 저장한다."""
    form = await request.form()
    with SessionLocal() as db:
        _get_accessible_repo(db, repo_name, current_user)
        try:
            upsert_repo_config(db, RepoConfigData(
                repo_full_name=repo_name,
                pr_review_comment=form.get("pr_review_comment") == "on",
                approve_mode=form.get("approve_mode", "disabled"),
                approve_threshold=int(form.get("approve_threshold", 75)),
                reject_threshold=int(form.get("reject_threshold", 50)),
                notify_chat_id=form.get("notify_chat_id") or None,
                n8n_webhook_url=form.get("n8n_webhook_url") or None,
                discord_webhook_url=form.get("discord_webhook_url", "") or None,
                slack_webhook_url=form.get("slack_webhook_url", "") or None,
                custom_webhook_url=form.get("custom_webhook_url", "") or None,
                email_recipients=form.get("email_recipients", "") or None,
                auto_merge=form.get("auto_merge") == "on",
                merge_threshold=int(form.get("merge_threshold", 75)),
                commit_comment=form.get("commit_comment") == "on",
                create_issue=form.get("create_issue") == "on",
                railway_deploy_alerts=form.get("railway_deploy_alerts") == "on",
            ))
            # railway_webhook_token, railway_api_token — RepoConfigData 외부 관리 (hook_token 동일 패턴)
            config_orm = repo_config_repo.find_by_full_name(db, repo_name)
            if config_orm and not config_orm.railway_webhook_token:
                config_orm.railway_webhook_token = secrets.token_hex(32)
            new_api_token = form.get("railway_api_token", "")
            if config_orm and new_api_token and new_api_token != "****":
                from src.crypto import encrypt_token  # pylint: disable=import-outside-toplevel
                config_orm.railway_api_token = encrypt_token(new_api_token)
            if config_orm:
                db.commit()
        except ValueError:
            # 로그 인젝션 방지: %r 로 repr 변환 (CR/LF 등 특수문자 이스케이프)
            logger.warning("Invalid threshold values for %r, settings not saved", repo_name)
            return RedirectResponse(
                url=f"/repos/{repo_name}/settings?save_error=1", status_code=303
            )
    return RedirectResponse(url=f"/repos/{repo_name}/settings?saved=1", status_code=303)


@router.post("/repos/{repo_name:path}/reinstall-hook")
async def reinstall_hook(
    request: Request,
    repo_name: str,
    current_user: CurrentUser = Depends(require_login),
):
    """기존 등록 리포에 .scamanager/ 파일을 재커밋한다."""
    with SessionLocal() as db:
        _get_accessible_repo(db, repo_name, current_user)
        config = repo_config_repo.find_by_full_name(db, repo_name)
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
        current_user.plaintext_token or "",
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
    current_user: CurrentUser = Depends(require_login),
):
    """GitHub Webhook을 삭제하고 새 URL(HTTPS)로 재등록한다. 중복 웹훅도 모두 정리한다."""
    with SessionLocal() as db:
        repo = _get_accessible_repo(db, repo_name, current_user)
        token = current_user.plaintext_token or ""

        webhook_url = _webhook_base_url(request) + "/webhooks/github"

        # GitHub에서 전체 웹훅 목록 조회 후 동일 URL 웹훅 전부 삭제 (중복 제거)
        try:
            all_hooks = await list_webhooks(token, repo_name)
            for hook in all_hooks:
                hook_url = hook.get("config", {}).get("url", "")
                if "/webhooks/github" in hook_url:
                    await delete_webhook(token, repo_name, hook["id"])
                    logger.info("Deleted duplicate webhook id=%d url=%s", hook["id"], hook_url)
        except (httpx.HTTPError, KeyError, ValueError, OSError) as exc:
            logger.warning("Webhook cleanup failed, proceeding with reinstall: %s", exc)

        new_secret = secrets.token_hex(32)
        new_id = await create_webhook(token, repo_name, webhook_url, new_secret)

        repo.webhook_id = new_id
        repo.webhook_secret = new_secret
        db.commit()

    return RedirectResponse(
        url=f"/repos/{repo_name}/settings?hook_ok=1",
        status_code=303,
    )


@router.post("/repos/{repo_name:path}/delete")
async def delete_repo(
    repo_name: str,
    current_user: CurrentUser = Depends(require_login),
):
    """리포지토리 + 연관 데이터(Webhook, Analysis, GateDecision, RepoConfig)를 삭제한다."""
    with SessionLocal() as db:
        repo = _get_accessible_repo(db, repo_name, current_user)
        await _delete_repo_cascade(db, repo, current_user.plaintext_token or "")
    return RedirectResponse(url="/?deleted=1", status_code=303)


@router.get("/repos/{repo_name:path}/analyses/{analysis_id}", response_class=HTMLResponse)
def analysis_detail(
    request: Request, repo_name: str, analysis_id: int,
    current_user: CurrentUser = Depends(require_login),
):
    """분석 상세 페이지(AI 리뷰·점수·피드백)를 렌더링한다."""
    with SessionLocal() as db:
        repo = _get_accessible_repo(db, repo_name, current_user)
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
        # 트렌드 차트: 같은 리포 최근 30건 (시간 오름차순)
        siblings = (db.query(Analysis.id, Analysis.score, Analysis.created_at)
                    .filter(Analysis.repo_id == repo.id)
                    .order_by(Analysis.created_at.desc()).limit(30).all())
        trend_data = [
            {"id": s.id, "score": s.score,
             "label": s.created_at.strftime("%m/%d") if s.created_at else ""}
            for s in reversed(siblings)
        ]
        # 이전/다음 분석 내비게이션
        prev_id = (db.query(Analysis.id)
                   .filter(Analysis.repo_id == repo.id, Analysis.id < analysis_id)
                   .order_by(Analysis.id.desc()).limit(1).scalar())
        next_id = (db.query(Analysis.id)
                   .filter(Analysis.repo_id == repo.id, Analysis.id > analysis_id)
                   .order_by(Analysis.id.asc()).limit(1).scalar())
    return templates.TemplateResponse(request, "analysis_detail.html", {
        "repo_name": repo_name, "analysis": data, "current_user": current_user,
        "trend_data": trend_data, "prev_id": prev_id, "next_id": next_id,
    })


@router.get("/repos/{repo_name:path}", response_class=HTMLResponse)
def repo_detail(  # pylint: disable=too-many-positional-arguments
    request: Request,
    repo_name: str,
    hook_installed: int = 0,
    current_user: CurrentUser = Depends(require_login),
):
    """리포 분석 이력 및 점수 차트 페이지를 렌더링한다."""
    with SessionLocal() as db:
        repo = _get_accessible_repo(db, repo_name, current_user)
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
