"""Hook API — pre-push 훅 인증 및 결과 저장 엔드포인트.

X-API-Key 없이 hook_token으로 인증 (훅은 일반 개발자 터미널에서 실행됨).
"""
import hmac
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel

from src.middleware.rate_limiter import limiter, RATE_LIMIT_API
from src.config import settings
from src.database import SessionLocal
from src.i18n.loader import get_text
from src.shared.log_safety import sanitize_for_log
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User
from src.repositories import repo_config_repo
from src.analyzer.io.ai_review import AiReviewResult
from src.scorer.calculator import calculate_score
from src.worker.pipeline import build_analysis_result_dict
from src.constants import (
    AI_DEFAULT_COMMIT_RAW,
    AI_DEFAULT_DIRECTION_RAW,
    AI_DEFAULT_TEST_RAW,
    AI_RAW_COMMIT_MAX,
    AI_RAW_DIRECTION_MAX,
    AI_RAW_TEST_MAX,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hook")


def _resolve_hook_locale(db, repo_name: str) -> str:
    """hook 엔드포인트용 — repo 소유자 preferred_language 해소. 없으면 default.

    Resolve repo owner's preferred_language for hook endpoints; default otherwise.

    hook 토큰 인증은 per-user 세션 locale 이 없으므로, repo full_name 으로
    소유자(User.preferred_language) 언어를 해소한다. 미지원 언어/소유자 부재 시 default.
    Hook token auth has no per-user session locale, so resolve the owner's
    language via repo full_name. Falls back to default for unsupported/missing owner.
    """
    repo = db.query(Repository).filter(Repository.full_name == repo_name).first()
    if repo and repo.user_id:
        user = db.query(User).filter(User.id == repo.user_id).first()
        if user and user.preferred_language:
            lang = user.preferred_language
            supported = {code.strip() for code in settings.supported_locales.split(",")}
            if lang in supported:
                return lang
    return settings.default_locale


def _coerce_raw_score(raw: Any, max_val: int, default: int) -> tuple[int, bool]:
    """raw 점수를 [0, max_val] 정수로 안전 클램프. 비숫자 타입/값은 default 로 폴백.
    Safely clamp a raw score to [0, max_val]; fall back to default on non-numeric type/value.

    오작동·악성 CLI 가 점수 필드에 문자열·None 등을 보내면 int() 가 ValueError/TypeError 를
    던져 500 이 된다. 이를 흡수해 default 폴백 + parse_error 분류로 graceful 처리한다.
    A malfunctioning/malicious CLI may send a string/None for a score field, making int() raise
    ValueError/TypeError → 500. Absorb it: fall back to the default and signal parse_error.

    반환 (clamped, ok) — ok=False 시 호출자가 ai_review_status='parse_error' 로 분류.
    Returns (clamped, ok) — ok=False signals the caller to mark ai_review_status='parse_error'.
    """
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return max(0, min(max_val, default)), False
    return max(0, min(max_val, value)), True


def _coerce_ai_scores(ar: dict) -> tuple[int, int, int, bool]:
    """ai_result 의 3개 raw 점수를 안전 클램프하고 'success' 적격 여부를 함께 반환한다.
    Coerce the three raw scores from ai_result and report whether they qualify as 'success'.

    각 필드가 (키 존재 AND 숫자 변환 가능)일 때만 status_ok=True — 누락 또는 비숫자 시 False.
    status_ok=True only when every field is present AND numeric — False if any is missing/non-numeric.

    반환 (commit, direction, test, status_ok).
    Returns (commit, direction, test, status_ok).
    """
    commit, commit_ok = _coerce_raw_score(
        ar.get("commit_message_score", AI_DEFAULT_COMMIT_RAW), AI_RAW_COMMIT_MAX, AI_DEFAULT_COMMIT_RAW)
    direction, direction_ok = _coerce_raw_score(
        ar.get("direction_score", AI_DEFAULT_DIRECTION_RAW), AI_RAW_DIRECTION_MAX, AI_DEFAULT_DIRECTION_RAW)
    test, test_ok = _coerce_raw_score(
        ar.get("test_score", AI_DEFAULT_TEST_RAW), AI_RAW_TEST_MAX, AI_DEFAULT_TEST_RAW)
    keys_present = all(k in ar for k in ("commit_message_score", "direction_score", "test_score"))
    return commit, direction, test, (keys_present and commit_ok and direction_ok and test_ok)


# ---------------------------------------------------------------------------
# GET /api/hook/verify
# ---------------------------------------------------------------------------

@router.get("/verify")
@limiter.limit(RATE_LIMIT_API)
def verify_hook(
    request: Request,  # pylint: disable=unused-argument
    repo: str,
    token: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
):
    """pre-push 훅이 Repo 등록 여부를 확인하는 엔드포인트.

    hook_token 일치 → 200 {"status": "active"}
    불일치 또는 미등록 → 404

    토큰 전달 방식 (우선순위 순):
    Token delivery methods (in priority order):
    1. Authorization: Bearer <token> 헤더 (권장 — 서버/프록시 로그 미노출)
       Authorization: Bearer <token> header (preferred — not logged by servers/proxies)
    2. ?token=<token> query param (하위 호환 — deprecated, 향후 제거 예정)
       ?token=<token> query param (backward-compat — deprecated, will be removed later)
    """
    # Authorization: Bearer <token> 헤더 우선, 없으면 query param fallback
    # Prefer Authorization: Bearer header; fall back to query param for backward compat.
    bearer_token: str | None = None
    if authorization and authorization.startswith("Bearer "):
        bearer_token = authorization[7:]

    effective_token = bearer_token or token

    # locale 해소는 에러 발생 시에만 (정상 경로 쿼리 순서 불변 — 토큰 검증 로직 보존)
    # Resolve locale only on error (keep happy-path query order intact — preserve token check)
    with SessionLocal() as db:
        if not effective_token:
            locale = _resolve_hook_locale(db, repo)
            raise HTTPException(
                status_code=401,
                detail=get_text("errors.hook_token_required", locale),
            )

        config = repo_config_repo.find_by_full_name(db, repo)
        if config is None or not hmac.compare_digest(config.hook_token or "", effective_token):
            locale = _resolve_hook_locale(db, repo)
            raise HTTPException(
                status_code=404,
                detail=get_text("errors.hook_invalid_repo_or_token", locale),
            )

    return {"status": "active"}


# ---------------------------------------------------------------------------
# POST /api/hook/result
# ---------------------------------------------------------------------------

class HookResultRequest(BaseModel):
    """pre-push 훅이 POST /api/hook/result 에 전송하는 요청 바디."""
    repo: str
    token: str
    commit_sha: str
    commit_message: str = ""
    ai_result: dict[str, Any]


@router.post("/result")
@limiter.limit(RATE_LIMIT_API)
def save_hook_result(request: Request, body: HookResultRequest):  # pylint: disable=unused-argument
    """pre-push 훅이 코드리뷰 결과를 전송하는 엔드포인트.

    토큰 검증 후 Analysis 레코드를 저장하고 점수를 반환한다.
    """
    with SessionLocal() as db:
        config = repo_config_repo.find_by_full_name(db, body.repo)

        if config is None or not hmac.compare_digest(config.hook_token or "", body.token):
            # locale 해소는 에러 시에만 (정상 경로 쿼리 순서 불변)
            # Resolve locale only on error (keep happy-path query order intact)
            locale = _resolve_hook_locale(db, body.repo)
            raise HTTPException(
                status_code=403,
                detail=get_text("errors.hook_invalid_token", locale),
            )

        repo = db.query(Repository).filter(
            Repository.full_name == body.repo
        ).first()

        if repo is None:
            locale = _resolve_hook_locale(db, body.repo)
            raise HTTPException(
                status_code=404,
                detail=get_text("errors.hook_repo_not_found", locale),
            )

        existing = db.query(Analysis).filter_by(
            commit_sha=body.commit_sha, repo_id=repo.id
        ).first()
        if existing:
            return {
                "status": "duplicate",
                "score": existing.score,
                "grade": existing.grade,
                "analysis_id": existing.id,
            }

        # ai_result → AiReviewResult 변환
        # 필수 score 필드 누락 또는 비숫자 타입 시 status="parse_error" 표시 (대시보드 fallback 배너 노출).
        # raw 점수는 0~MAX 클램프 + 안전 변환 — 범위 밖/비숫자 값이 500 또는 cap 초과를 유발하지 않게.
        # Mark status="parse_error" on missing OR non-numeric score fields (dashboard fallback banner).
        # Raw scores are clamped to 0~MAX with safe coercion — out-of-range/non-numeric never 500 or exceed cap.
        ar = body.ai_result
        commit_raw, direction_raw, test_raw, scores_ok = _coerce_ai_scores(ar)
        ai_review = AiReviewResult(
            commit_score=commit_raw,
            ai_score=direction_raw,
            test_score=test_raw,
            summary=ar.get("summary", ""),
            suggestions=ar.get("suggestions", []),
            commit_message_feedback=ar.get("commit_message_feedback", ""),
            code_quality_feedback=ar.get("code_quality_feedback", ""),
            security_feedback=ar.get("security_feedback", ""),
            direction_feedback=ar.get("direction_feedback", ""),
            test_feedback=ar.get("test_feedback", ""),
            file_feedbacks=ar.get("file_feedbacks", []),
            status="success" if scores_ok else "parse_error",
        )

        # CLI 훅은 정적 분석 없음 → 빈 리스트 (code_quality=25, security=20 만점)
        score_result = calculate_score([], ai_review=ai_review)

        analysis = Analysis(
            repo_id=repo.id,
            commit_sha=body.commit_sha,
            commit_message=body.commit_message,
            pr_number=None,
            score=score_result.total,
            grade=score_result.grade,
            result=build_analysis_result_dict(ai_review, score_result, [], "cli"),
        )

        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        # 로그 인젝션 방지: sanitize_for_log() 로 사용자 입력 정제
        # NOSONAR 이유: SonarCloud taint analysis 가 str.replace 기반 커스텀
        # sanitizer 를 인식하지 못함 — log_safety 모듈에서 실제 방어 완료.
        logger.info(  # NOSONAR python:S5145 — sanitized via log_safety
            "CLI hook result saved: repo=%s sha=%s score=%d",
            sanitize_for_log(body.repo),
            sanitize_for_log(body.commit_sha),
            score_result.total,
        )

        return {
            "status": "saved",
            "score": score_result.total,
            "grade": score_result.grade,
            "analysis_id": analysis.id,
        }
