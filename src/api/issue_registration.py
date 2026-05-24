"""issue_registration API — GitHub Issue 등록 + 상태 조회 엔드포인트.
issue_registration API — endpoints for registering GitHub Issues and querying state.
"""
import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.auth.session import get_current_user
from src.database import SessionLocal
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.services.issue_registration_service import (
    get_analysis_issue_status,
    get_repo_issue_summary,
    make_ai_issue_key,
    make_static_issue_key,
    register_issue,
)

router = APIRouter(prefix="/api/issues")


class RegisterRequest(BaseModel):
    analysis_id: int
    issue_type: str  # "ai_suggestion" | "static_issue"
    # AI 제안사항용 — issue_key 서버 생성에 사용
    # For AI suggestions — used to generate issue_key server-side
    suggestion_text: str | None = None
    # 정적 분석 이슈용 — issue_key 서버 생성에 사용
    # For static issues — used to generate issue_key server-side
    tool: str | None = None
    category: str | None = None
    message: str | None = None
    title: str
    body: str
    labels: list[str]


def _get_analysis_and_repo(db: Session, analysis_id: int) -> tuple:
    """analysis_id로 Analysis + Repository를 조회한다. 없으면 404 raise.
    Look up Analysis and Repository by analysis_id. Raises 404 if not found.
    """
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    repo = db.query(Repository).filter(Repository.id == analysis.repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return analysis, repo


def _make_issue_key(req: RegisterRequest) -> str:
    """요청에서 issue_key를 생성한다.
    Generate issue_key from the request payload.
    """
    if req.issue_type == "ai_suggestion":
        text = req.suggestion_text or req.title
        return make_ai_issue_key(text)
    tool = req.tool or ""
    category = req.category or ""
    message = req.message or req.title
    return make_static_issue_key(tool, category, message)


@router.post("/register", status_code=201)
async def register(request: Request, req: RegisterRequest):
    """AI 분석 이슈를 GitHub Issue로 등록한다.
    Register an AI analysis issue as a GitHub Issue.
    """
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required")

    issue_key = _make_issue_key(req)

    with SessionLocal() as db:
        analysis, repo = _get_analysis_and_repo(db, req.analysis_id)
        try:
            result = await register_issue(
                db,
                analysis_id=req.analysis_id,
                repo_id=repo.id,
                repo_full_name=repo.full_name,
                github_token=current_user.plaintext_token,
                issue_type=req.issue_type,
                issue_key=issue_key,
                title=req.title,
                body=req.body,
                labels=req.labels,
            )
        except ValueError as exc:
            # "DUPLICATE:<number>" 형식
            # "DUPLICATE:<number>" format
            if str(exc).startswith("DUPLICATE:"):
                issue_num = str(exc).split(":")[1]
                raise HTTPException(
                    status_code=409,
                    detail=f"이미 등록된 이슈입니다 (#{issue_num})",
                ) from exc
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                raise HTTPException(
                    status_code=403,
                    detail="Issues 쓰기 권한이 없습니다. GitHub 토큰을 확인해 주세요.",
                ) from exc
            raise HTTPException(status_code=502, detail="GitHub API 오류") from exc

    return result


@router.get("/status")
async def get_status(request: Request, analysis_id: int):
    """analysis_detail용 등록 이력 + GitHub 상태 동기화 결과를 반환한다.
    Return registration history and synced GitHub state for analysis_detail.
    """
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required")

    with SessionLocal() as db:
        analysis, repo = _get_analysis_and_repo(db, analysis_id)
        statuses = await get_analysis_issue_status(
            db,
            analysis_id=analysis_id,
            repo_full_name=repo.full_name,
            github_token=current_user.plaintext_token,
        )

    return {"registrations": statuses}


def _get_repo_or_404(db: Session, repo_id: int) -> Repository:
    """repo_id로 Repository를 조회한다. 없으면 404 raise.
    Look up Repository by repo_id. Raises 404 if not found.
    """
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo


@router.get("/repo-summary")
async def repo_summary(request: Request, repo_id: int):
    """repo_detail용 등록 이력 + GitHub 상태를 반환한다.
    Return registration history and GitHub state for repo_detail.
    """
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required")

    with SessionLocal() as db:
        repo = _get_repo_or_404(db, repo_id)
        registrations = await get_repo_issue_summary(
            db,
            repo_id=repo_id,
            repo_full_name=repo.full_name,
            github_token=current_user.plaintext_token,
        )

    return {"registrations": registrations}
