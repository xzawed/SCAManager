"""Hook API — pre-push 훅 인증 및 결과 저장 엔드포인트.

X-API-Key 없이 hook_token으로 인증 (훅은 일반 개발자 터미널에서 실행됨).
"""
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel

from src.middleware.rate_limiter import limiter, RATE_LIMIT_API
from src.config import settings
from src.shared.secure_compare import secure_str_compare
from src.database import WorkerSessionLocal as SessionLocal
from src.i18n.loader import get_text
from src.shared.log_safety import sanitize_for_log
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User
from src.repositories import repo_config_repo, analysis_repo
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

    오작동·악성 CLI 가 점수 필드에 문자열·None·Infinity 등을 보내면 int() 가
    TypeError/ValueError/OverflowError 를 던져 500 이 된다 (Infinity 는 json.loads 가
    float('inf') 로 파싱 → int(float('inf')) OverflowError). 이를 흡수해 default 폴백 +
    parse_error 분류로 graceful 처리한다.
    A malfunctioning/malicious CLI may send a string/None/Infinity for a score field, making int()
    raise TypeError/ValueError/OverflowError → 500 (json.loads parses Infinity to float('inf'),
    and int(float('inf')) raises OverflowError). Absorb it: fall back to the default and signal parse_error.

    반환 (clamped, ok) — ok=False 시 호출자가 ai_review_status='parse_error' 로 분류.
    Returns (clamped, ok) — ok=False signals the caller to mark ai_review_status='parse_error'.

    유효한 float(예: 8.9)은 int() 가 0 방향 절삭(양수=floor, 반올림 X) → 8 — 점수 보수적 하향(인플레 방지), ok=True.
    A valid float (e.g. 8.9) is truncated toward zero by int() (floor for positives, no rounding) → 8 (ok=True).
    """
    try:
        value = int(raw)
    except (TypeError, ValueError, OverflowError):
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
        if config is None or not secure_str_compare(config.hook_token, effective_token):
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
def save_hook_result(  # pylint: disable=unused-argument,too-many-locals
    request: Request, body: HookResultRequest,
):
    # too-many-locals: race-safe save_new 도입(#5)으로 created 지역변수 1개 추가(16/15).
    # 함수 응집 단위(토큰검증→파싱→점수→저장)를 깨지 않기 위해 헬퍼 추출 대신 inline disable
    # (testing.md R0914 결정 트리 — 기존 함수 시그니처 확장 경로).
    # too-many-locals: +1 local (created) from the race-safe save_new (#5); inline-disabled per the
    # testing.md R0914 tree (existing-function expansion) to keep the function cohesive.
    """pre-push 훅이 코드리뷰 결과를 전송하는 엔드포인트.

    토큰 검증 후 Analysis 레코드를 저장하고 점수를 반환한다.
    """
    with SessionLocal() as db:
        config = repo_config_repo.find_by_full_name(db, body.repo)

        # 🔴 빈/NULL 토큰 인증 우회 차단 (보안 P0): secure_str_compare 는 None·"" 를 모두
        # b"" 로 인코딩하므로 secure_str_compare(None, "") == True → hook_token 미설정(NULL)
        # 행에 body.token="" 로 인증 통과 가능. verify 엔드포인트(L139 `if not effective_token`)
        # 와 대칭으로, 제출 토큰 또는 저장된 hook_token 이 비면 비교 전에 거부한다.
        # Block empty/NULL-token auth bypass (security P0): secure_str_compare encodes both None and
        # "" to b"", so secure_str_compare(None, "") == True — a NULL-hook_token row would authenticate
        # with body.token="". Mirroring the verify endpoint (L139), reject before the compare when
        # either the submitted token or the stored hook_token is empty.
        if (
            not body.token
            or config is None
            or not config.hook_token
            or not secure_str_compare(config.hook_token, body.token)
        ):
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

        # 🔴 #25: parse_error(비숫자/누락 점수) 시 인플레 fallback 점수(89/B)를 score/grade 컬럼에
        # 저장하지 않는다(NULL). score/grade 는 nullable 이고 모든 집계(_kpi_avg·func.avg·leaderboard)
        # 가 NULL 을 자연 제외하므로, NULL 저장만으로 대시보드/리더보드 오염을 차단한다(쿼리 변경 0).
        # result dict 의 breakdown·ai_review_status='parse_error' 는 보존 → 대시보드 fallback 배너·
        # 정성 정보 유지(컬럼=집계용 NULL / result=진단용 보존, 의도적 비대칭).
        # #25: on parse_error don't persist the inflated fallback score (89/B) — store NULL. score/grade
        # are nullable and every aggregation already excludes NULL, so NULL alone stops dashboard/
        # leaderboard pollution (0 query change). The result dict keeps breakdown + ai_review_status for
        # the fallback banner (column = NULL for aggregation / result = preserved for diagnostics).
        persisted_score = score_result.total if scores_ok else None
        persisted_grade = score_result.grade if scores_ok else None

        analysis = Analysis(
            repo_id=repo.id,
            commit_sha=body.commit_sha,
            commit_message=body.commit_message,
            pr_number=None,
            score=persisted_score,
            grade=persisted_grade,
            result=build_analysis_result_dict(ai_review, score_result, [], "cli"),
        )

        # 동시 동일 SHA insert race 안전 저장 — 두 hook 이 위 existing 체크(멱등성)를 동시에
        # 통과한 뒤 DB unique 제약(uq_analyses_repo_sha)에 막히는 TOCTOU 를 흡수한다(#5).
        # save_new 가 IntegrityError 를 rollback+재조회로 처리해 500 대신 기존 레코드를 반환.
        # Race-safe save — absorbs the TOCTOU where two hooks pass the idempotency check and then
        # collide on the unique constraint; save_new returns the existing row instead of a 500 (#5).
        analysis, created = analysis_repo.save_new(db, analysis)
        if not created:
            logger.info(
                "CLI hook concurrent insert blocked — returning existing (repo=%s sha=%s)",
                sanitize_for_log(body.repo), sanitize_for_log(body.commit_sha),
            )
            return {
                "status": "duplicate",
                "score": analysis.score,
                "grade": analysis.grade,
                "analysis_id": analysis.id,
            }

        # 로그 인젝션 방지: sanitize_for_log() 로 사용자 입력 정제
        # NOSONAR 이유: SonarCloud taint analysis 가 str.replace 기반 커스텀
        # sanitizer 를 인식하지 못함 — log_safety 모듈에서 실제 방어 완료.
        logger.info(  # NOSONAR python:S5145 — sanitized via log_safety
            "CLI hook result saved: repo=%s sha=%s score=%s",  # %s — parse_error 시 None 안전
            sanitize_for_log(body.repo),
            sanitize_for_log(body.commit_sha),
            persisted_score,
        )

        return {
            "status": "saved",
            "score": persisted_score,
            "grade": persisted_grade,
            "analysis_id": analysis.id,
        }
