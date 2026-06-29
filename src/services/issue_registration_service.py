"""issue_registration_service — Issue 등록 + GitHub 상태 동기화 로직.
issue_registration_service — Issue registration and GitHub state sync logic.
"""
import hashlib
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from src.github_client.issues import create_issue, get_issue_state
from src.models.issue_registration import IssueRegistration
from src.repositories import issue_registration_repo

logger = logging.getLogger(__name__)

# GitHub 상태 캐시 TTL (초) — 만료 시 재조회
# GitHub state cache TTL in seconds — refresh after expiry
_SYNC_TTL_SECONDS = 300


def make_ai_issue_key(suggestion_text: str) -> str:
    """AI 제안사항 중복 판별 키 생성 — suggestion_text[:500] SHA256.
    Generate dedup key for AI suggestions — SHA256 of first 500 chars.
    """
    return hashlib.sha256(suggestion_text[:500].encode()).hexdigest()[:64]


def make_static_issue_key(tool: str, category: str, message: str) -> str:
    """정적 분석 이슈 중복 판별 키 생성 — 라인 번호 제외 (커밋 간 drift 방지).
    Generate dedup key for static issues — excludes line number to prevent cross-commit drift.
    """
    content = f"{tool}:{category}:{message[:200]}"
    return hashlib.sha256(content.encode()).hexdigest()[:64]


async def register_issue(  # pylint: disable=too-many-arguments
    db: Session,
    *,
    analysis_id: int,
    repo_id: int,
    repo_full_name: str,
    github_token: str,
    issue_type: str,
    issue_key: str,
    title: str,
    body: str,
    labels: list[str],
) -> dict:
    """Issue를 등록한다. 중복이면 ValueError("DUPLICATE:<number>") 발생.
    Register an Issue. Raises ValueError("DUPLICATE:<number>") on duplicate.
    """
    existing = issue_registration_repo.find_by_key(db, repo_id=repo_id, issue_key=issue_key)
    if existing:
        raise ValueError(f"DUPLICATE:{existing.github_issue_number}")

    gh_result = await create_issue(
        github_token,
        repo_full_name,
        title=title,
        body=body,
        labels=labels,
    )
    try:
        record = issue_registration_repo.create(
            db,
            analysis_id=analysis_id,
            repo_id=repo_id,
            issue_type=issue_type,
            issue_key=issue_key,
            github_issue_number=gh_result["number"],
        )
    except IntegrityError:
        # TOCTOU 경쟁 조건 처리 — 동시 요청이 UniqueConstraint 위반 시 기존 레코드 조회
        # TOCTOU race condition — concurrent insert hit UniqueConstraint, find existing record
        db.rollback()
        existing = issue_registration_repo.find_by_key(db, repo_id=repo_id, issue_key=issue_key)
        issue_num = existing.github_issue_number if existing else gh_result["number"]
        raise ValueError(f"DUPLICATE:{issue_num}") from None
    except SQLAlchemyError:
        # GitHub Issue 는 이미 생성됐는데 DB 기록이 비-IntegrityError(연결 끊김 등)로 실패 →
        # 추적되지 않는 orphan Issue 가 남는다. 운영자가 수동 보정할 수 있도록 식별자
        # (issue number/url/repo)를 ERROR 로그로 남기고 예외를 그대로 전파한다.
        # GitHub Issue was already created but the DB write failed with a non-IntegrityError
        # (e.g. dropped connection), leaving an untracked orphan Issue. Emit an ERROR log with
        # the reconciliation identifiers (issue number/url/repo) and re-raise.
        db.rollback()
        logger.error(
            "issue_registration orphan — GitHub Issue created but DB persist failed: "
            "repo=%s issue_number=%s url=%s issue_key=%s",
            repo_full_name,
            gh_result["number"],
            gh_result["html_url"],
            issue_key,
        )
        raise
    return {
        "github_issue_number": record.github_issue_number,
        "github_issue_url": gh_result["html_url"],
        "state": "open",
    }


async def _sync_state_if_stale(
    db: Session,
    rec: IssueRegistration,
    *,
    now: datetime,
    repo_full_name: str,
    github_token: str,
) -> None:
    """TTL 만료 시 GitHub 상태를 재조회하여 DB에 갱신한다.
    Re-fetch GitHub state if stale and update DB; silently ignore network errors.

    SQLite는 tzinfo 없이 저장하므로 naive datetime을 UTC로 정규화 후 비교.
    SQLite stores DateTime without tzinfo — normalize naive datetime to UTC before comparing.
    """
    synced = rec.github_issue_synced_at
    if synced is not None and synced.tzinfo is None:
        synced = synced.replace(tzinfo=timezone.utc)
    stale = synced is None or (now - synced).total_seconds() > _SYNC_TTL_SECONDS
    if not stale:
        return
    try:
        state = await get_issue_state(github_token, repo_full_name, rec.github_issue_number)
        issue_registration_repo.update_state(db, record=rec, state=state)
    except (httpx.HTTPError, KeyError, ValueError):
        # 동기화 실패 시 기존 상태 유지 — 사용자에게 오류 미노출.
        # httpx.HTTPError(5xx/네트워크) 외에 GitHub 응답이 malformed 면 get_issue_state 의
        # resp.json()["state"] 가 KeyError/JSONDecodeError(ValueError) 를 던질 수 있어 함께 포착
        # (동기화 실패가 API 라우트 500 으로 전파되지 않도록 — silent fallback 의도 일관, 감사 P2).
        # Keep existing state on sync failure — silent fallback. Besides httpx.HTTPError
        # (5xx/network), a malformed GitHub response makes get_issue_state's
        # resp.json()["state"] raise KeyError/JSONDecodeError(ValueError); catch those too
        # so a sync failure never surfaces as a 500 from the API route.
        pass


async def get_analysis_issue_status(
    db: Session,
    *,
    analysis_id: int,
    repo_full_name: str,
    github_token: str,
) -> list[dict]:
    """analysis_detail용 등록 이력 + TTL 만료 항목 GitHub 상태 동기화.
    Return registration records for analysis_detail; sync stale GitHub states.
    """
    records = issue_registration_repo.list_by_analysis(db, analysis_id=analysis_id)
    now = datetime.now(timezone.utc)
    result = []
    for rec in records:
        await _sync_state_if_stale(db, rec, now=now, repo_full_name=repo_full_name, github_token=github_token)
        result.append({
            "issue_key": rec.issue_key,
            "github_issue_number": rec.github_issue_number,
            "github_issue_state": rec.github_issue_state,
            "github_issue_url": (
                f"https://github.com/{repo_full_name}/issues/{rec.github_issue_number}"
            ),
        })
    return result


async def get_repo_issue_summary(
    db: Session,
    *,
    repo_id: int,
    repo_full_name: str,
    github_token: str,
) -> list[dict]:
    """repo_detail용 등록 이력 + TTL 만료 항목 일괄 GitHub 상태 동기화.
    Return all repo registrations for repo_detail; bulk-sync stale GitHub states.
    """
    records = issue_registration_repo.list_by_repo(db, repo_id=repo_id)
    now = datetime.now(timezone.utc)
    result = []
    for rec in records:
        await _sync_state_if_stale(db, rec, now=now, repo_full_name=repo_full_name, github_token=github_token)
        result.append({
            "issue_key": rec.issue_key,
            "issue_type": rec.issue_type,
            "github_issue_number": rec.github_issue_number,
            "github_issue_state": rec.github_issue_state,
            "github_issue_url": (
                f"https://github.com/{repo_full_name}/issues/{rec.github_issue_number}"
            ),
            "created_at": rec.created_at.isoformat() if rec.created_at else None,
        })
    return result
