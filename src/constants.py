"""SCAManager 전역 상수 — 점수 체계, 분석 도구, 파이프라인 설정."""

# ── 점수 배점 ──────────────────────────────────────────────────────────────
CODE_QUALITY_MAX = 25       # pylint + flake8 기반
SECURITY_MAX = 20           # bandit 기반
COMMIT_MSG_MAX = 15         # Claude AI 0-20 → 0-15 스케일링
AI_REVIEW_MAX = 25          # Claude AI 0-20 → 0-25 스케일링
TEST_COVERAGE_MAX = 15      # Claude AI 0-10 → 0-15 스케일링

# ── 정적 분석 감점 가중치 ────────────────────────────────────────────────
PYLINT_ERROR_PENALTY = 3    # code_quality error 1건당 감점
PYLINT_WARNING_PENALTY = 1  # code_quality warning 1건당 감점
PYLINT_WARNING_CAP = 15     # (deprecated) 구 pylint warning 상한 — CQ_WARNING_CAP 사용 권장
FLAKE8_WARNING_PENALTY = 1  # (deprecated) 구 flake8 경고 감점 — PYLINT_WARNING_PENALTY와 동일
FLAKE8_WARNING_CAP = 10     # (deprecated) 구 flake8 상한 — CQ_WARNING_CAP 사용 권장
CQ_WARNING_CAP = 25         # code_quality warning 감점 상한 (PYLINT_WARNING_CAP+FLAKE8_WARNING_CAP 합산)
BANDIT_HIGH_PENALTY = 7     # security error 1건당 감점
BANDIT_LOW_PENALTY = 2      # security warning 1건당 감점

# ── AI 기본값 (API 미설정·실패·empty_diff 시) ─────────────────────────
AI_DEFAULT_COMMIT = 13      # commit_score 기본값 (스케일링 후)
AI_DEFAULT_DIRECTION = 21   # ai_score 기본값 (스케일링 후)
AI_DEFAULT_TEST = 10        # test_score 기본값 (스케일링 후)
# hook.py: AiReviewResult 생성 시 사용하는 raw 스케일 기본값 (스케일링 전)
# 스케일링 후 결과가 파이프라인 기본값(AI_DEFAULT_*)과 일치하도록 역산
AI_DEFAULT_COMMIT_RAW = 17  # raw 0-20 → round(17*15/20) = 13 = AI_DEFAULT_COMMIT
AI_DEFAULT_DIRECTION_RAW = 17  # raw 0-20 → round(17*25/20) = 21 = AI_DEFAULT_DIRECTION
AI_DEFAULT_TEST_RAW = 7     # raw 0-10 → round(7*15/10) = 10 = AI_DEFAULT_TEST

# ── 등급 임계값 ────────────────────────────────────────────────────────────
GRADE_THRESHOLDS: dict[str, int] = {"A": 90, "B": 75, "C": 60, "D": 45}
# F는 45 미만 (GRADE_THRESHOLDS 중 가장 낮은 값 미만)

# ── 등급 이모지 / 색상 (단일 출처 — notifier·CLI 모두 여기서 import) ──────
GRADE_EMOJI: dict[str, str] = {
    "A": "🟢", "B": "🔵", "C": "🟡", "D": "🟠", "F": "🔴",
}
# Discord embed color (integer)
GRADE_COLOR_DISCORD: dict[str, int] = {
    "A": 0x10B981, "B": 0x3B82F6, "C": 0xF59E0B, "D": 0xF97316, "F": 0xEF4444,
}
# CSS/HTML hex color
GRADE_COLOR_HTML: dict[str, str] = {
    "A": "#10b981", "B": "#3b82f6", "C": "#f59e0b", "D": "#f97316", "F": "#ef4444",
}
# ANSI terminal color code
GRADE_COLOR_ANSI: dict[str, int] = {
    "A": 32, "B": 34, "C": 33, "D": 33, "F": 31,
}

# ── 분석 도구 설정 ─────────────────────────────────────────────────────────
STATIC_ANALYSIS_TIMEOUT = 30  # subprocess 타임아웃 (초)

# ── 파이프라인 이벤트 필터 ─────────────────────────────────────────────────
HANDLED_EVENTS: frozenset[str] = frozenset({"push", "pull_request", "issues"})
PR_HANDLED_ACTIONS: frozenset[str] = frozenset({"opened", "synchronize", "reopened", "closed"})
