"""issue_registration_service — Issue 등록 + GitHub 상태 동기화 로직.
issue_registration_service — Issue registration and GitHub state sync logic.
"""
import hashlib
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from src.github_client.issues import create_issue, get_issue_state
from src.repositories import issue_registration_repo

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


async def register_issue(
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
    record = issue_registration_repo.create(
        db,
        analysis_id=analysis_id,
        repo_id=repo_id,
        issue_type=issue_type,
        issue_key=issue_key,
        github_issue_number=gh_result["number"],
    )
    return {
        "github_issue_number": record.github_issue_number,
        "github_issue_url": gh_result["html_url"],
        "state": "open",
    }


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
        # SQLite는 tzinfo 없이 저장 — 비교 시 UTC로 정규화
        # SQLite stores DateTime without tzinfo — normalize to UTC for comparison
        synced = rec.github_issue_synced_at
        if synced is not None and synced.tzinfo is None:
            synced = synced.replace(tzinfo=timezone.utc)
        stale = (
            synced is None
            or (now - synced).total_seconds() > _SYNC_TTL_SECONDS
        )
        if stale:
            try:
                state = await get_issue_state(
                    github_token, repo_full_name, rec.github_issue_number
                )
                issue_registration_repo.update_state(db, record=rec, state=state)
            except httpx.HTTPError:
                # 동기화 실패 시 기존 상태 유지 — 사용자에게 오류 미노출
                # Keep existing state on sync failure — silent fallback
                pass
        result.append({
            "issue_key": rec.issue_key,
            "github_issue_number": rec.github_issue_number,
            "github_issue_state": rec.github_issue_state,
            "github_issue_url": (
                f"https://github.com/{repo_full_name}/issues/{rec.github_issue_number}"
            ),
        })
    return result
