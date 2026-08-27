"""issue_registration_service — Issue 등록 + GitHub 상태 동기화 로직.
issue_registration_service — Issue registration and GitHub state sync logic.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from src.github_client.issues import create_issue, get_issue_state
from src.models.issue_registration import IssueRegistration
from src.repositories import issue_registration_repo
from src.shared.http_client import HTTPX_SEND_ERRORS

logger = logging.getLogger(__name__)

# GitHub 상태 캐시 TTL (초) — 만료 시 재조회
# GitHub state cache TTL in seconds — refresh after expiry
_SYNC_TTL_SECONDS = 300


def make_ai_issue_key(suggestion_text: str) -> str:
    """AI 제안사항 중복 판별 키 생성 — suggestion_text[:500] SHA256.
    Generate dedup key for AI suggestions — SHA256 of first 500 chars.
    """
    return hashlib.sha256(suggestion_text[:500].encode()).hexdigest()[:64]


def make_static_issue_key(
    tool: str, category: str, message: str, *, file: str | None
) -> str:
    """정적 분석 이슈 중복 판별 키 — 라인은 빼고 **파일은 넣는다**.

    🔴 `file` 이 빠져 있어서 서로 다른 파일의 동일 메시지가 한 키로 붕괴했다(#1499).
    `register()` 는 dedup 슬롯 스쿼팅을 되돌릴 수 없으므로, A파일 이슈가 먼저 등록되면
    B파일의 진짜 finding 은 **영구히 등록 불가**가 된다. 운영 실측(2026-08-27): 키 630개
    중 200개(31.7%)가 2개 이상 파일을 삼켰고 최악은 파일 35개, 등록 불가가 될 findings
    519건(error 303 + warning 216).

    라인은 여전히 뺀다 — 커밋마다 흔들려 같은 결함이 매번 새 키가 된다. 파일명 변경은
    훨씬 드물고 결과도 다르다(중복 이슈 하나이지 **차단은 아니다**). 되돌릴 수 없는
    쪽만 닫는다.

    🔴 `file` 은 keyword-only **필수**다. 기본값을 주면 호출부가 조용히 빠뜨려
    「영원히 빈 file」이 되고, 위 붕괴가 그대로 남는다. `None` 은 허용한다 — 파일 키가
    없던 시절(2026-08-25 이전) 분석에서 등록할 때다.

    Include the file path; keep excluding the line number. `file` is keyword-only and
    required so a caller cannot silently fall back to the collapsing key.
    """
    # 🔴 콜론으로 잇지 않는다 — 필드 안의 콜론이 **경계를 위조**한다(Grok 01a0426a):
    #     ("ruff","F401","msg:src/b.py","src/a.py")  와
    #     ("ruff","F401","msg","src/b.py:src/a.py")  가 같은 문자열이 됐다.
    # JSON 은 각 필드를 따옴표로 감싸고 내부 따옴표를 이스케이프하므로 경계가 유일하고,
    # `None` 과 `""` 도 `null` / `""` 로 갈린다(예전엔 `file or ''` 로 뭉갰다).
    # Join via JSON: quoting makes field boundaries unforgeable and keeps None distinct from "".
    # 🔴 정규화는 **여기서만** 한다. 호출부가 각자 하면 같은 finding 이 서로 다른
    #    키를 얻는다 — 실측(Grok 01a042e5): 등록 경로는 빈 message 를 title 로 대체하고
    #    브라우저는 빈 file 을 null 로 보내는데, 렌더 경로는 둘 다 빈 문자열로 뒀다.
    #    「없음」의 표기가 두 가지(None / "")인 것이 그 드리프트의 재료였다.
    # Normalize here only; per-caller normalization is what made the two paths diverge.
    content = json.dumps(
        [tool or "", category or "", (message or "")[:200], file or None],
        ensure_ascii=False, separators=(",", ":"))
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
        # 🔴 방금 생성한 GitHub Issue 가 중복(orphan) 표면화 (종합감사 P2 — SQLAlchemyError orphan
        #   로깅과 대칭). GitHub Issue 를 먼저 만든 뒤 DB INSERT 하므로, 동시 요청이 GitHub Issue
        #   **2개**를 만든다 — 첫 승자만 DB 에 기록되고 방금 만든 것(gh_result)은 추적 안 되는 중복
        #   Issue 로 남는다. 첫 승자와 번호가 다르면 운영자가 수동 close 할 수 있게 WARNING 으로 남긴다.
        # Surface the just-created duplicate GitHub Issue (symmetric with the SQLAlchemyError orphan
        #   log). Concurrent requests each create a GitHub Issue; only the first is tracked in the DB.
        new_num = gh_result.get("number")
        if existing is not None and new_num is not None and existing.github_issue_number != new_num:
            logger.warning(
                "issue_registration duplicate — 방금 생성한 GitHub Issue #%s 는 중복(orphan), "
                "추적된 첫 승자=#%s. 수동 close 대상. repo_id=%s key=%s url=%s",
                new_num, existing.github_issue_number, repo_id, issue_key, gh_result.get("html_url"),
            )
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
    except (*HTTPX_SEND_ERRORS, KeyError, ValueError):
        # 동기화 실패 시 기존 상태 유지 — 사용자에게 오류 미노출.
        # 전송 오류(5xx/네트워크/InvalidURL) 외에 GitHub 응답이 malformed 면 get_issue_state 의
        # resp.json()["state"] 가 KeyError/JSONDecodeError(ValueError) 를 던질 수 있어 함께 포착
        # (동기화 실패가 API 라우트 500 으로 전파되지 않도록 — silent fallback 의도 일관, 감사 P2).
        # Keep existing state on sync failure — silent fallback. Besides transport errors
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
