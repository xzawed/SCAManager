"""merge_metrics — auto-merge 시도 기록 + 구조화 로깅 (Phase F.1).

Phase F.1 목표: 모든 auto-merge 시도(성공·실패)를 DB 에 기록 + structured log
emit. Phase F.3 의 merge_failure_advisor, Phase F.4 의 대시보드가 이 데이터를
소비한다.

공개 API:
  - parse_reason_tag(reason) → 정규 태그 추출 (':' 구분자 기반)
  - log_merge_attempt(db, ...) → MergeAttempt INSERT + INFO 구조화 로그

DB 오류 내성: `log_merge_attempt` 는 어떤 예외도 파이프라인 밖으로 전파하지
않는다 — WARNING 로그만 남기고 None 반환. auto-merge 파이프라인이 관측 실패로
중단되는 것을 방지.
"""
import logging

from sqlalchemy.orm import Session

from src.models.merge_attempt import MergeAttempt
from src.repositories import merge_attempt_repo

logger = logging.getLogger(__name__)


def parse_reason_tag(reason: str | None) -> str | None:
    """reason 문자열에서 정규 태그만 추출.

    - None / 빈 문자열 → None
    - "tag: detail" → "tag"
    - "tag" (콜론 없음) → "tag"
    """
    if not reason:
        return None
    head = reason.split(":", 1)[0].strip()
    return head or None


def log_merge_attempt(
    db: Session,
    *,
    analysis_id: int,
    repo_name: str,
    pr_number: int,
    score: int,
    threshold: int,
    success: bool,
    reason: str | None = None,
) -> MergeAttempt | None:
    """MergeAttempt 를 DB 에 기록하고 구조화된 INFO 로그를 낸다.

    - success=True 면 failure_reason/detail_message 는 None 으로 저장
    - success=False 면 reason 을 파싱해 태그만 failure_reason 에, 전체를 detail_message 에
    - DB 오류 시 WARNING 로그만 남기고 None 반환 (파이프라인 중단 금지)
    """
    failure_reason: str | None = None
    detail_message: str | None = None
    if not success:
        failure_reason = parse_reason_tag(reason)
        detail_message = reason or None

    record: MergeAttempt | None = None
    try:
        record = merge_attempt_repo.create(
            db,
            analysis_id=analysis_id,
            repo_name=repo_name,
            pr_number=pr_number,
            score=score,
            threshold=threshold,
            success=success,
            failure_reason=failure_reason,
            detail_message=detail_message,
        )
    except Exception as exc:  # pylint: disable=broad-except
        # SQLAlchemy 는 commit 실패 후 세션을 invalid 로 표시 — rollback 하지 않으면
        # 동일 세션을 재사용하는 후속 쿼리가 PendingRollbackError 로 실패한다.
        try:
            db.rollback()
        except Exception:  # nosec B110 — pylint: disable=broad-except
            # rollback 실패는 의도적으로 무시: 이미 commit 단계에서 세션이
            # 손상됐고, 후속 로그·반환값이 최우선이므로 2차 예외로 덮이면 안 됨.
            pass
        logger.warning(
            "merge_attempt DB 기록 실패 (repo=%s, pr=%d): %s",
            repo_name, pr_number, exc,
        )
        return None

    merge_result = "success" if success else "failure"
    extra = {
        "merge_result": merge_result,
        "failure_reason": failure_reason,
        "score": score,
        "threshold": threshold,
        "repo_name": repo_name,
        "pr_number": pr_number,
        "analysis_id": analysis_id,
    }
    logger.info(
        "merge_attempt repo=%s pr=%d result=%s reason=%s score=%d threshold=%d",
        repo_name, pr_number, merge_result, failure_reason or "-", score, threshold,
        extra=extra,
    )
    return record
