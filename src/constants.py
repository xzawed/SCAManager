"""SCAManager 전역 상수 — 점수 체계, 분석 도구, 파이프라인 설정."""

# ── 점수 배점 ──────────────────────────────────────────────────────────────
CODE_QUALITY_MAX = 25       # pylint + flake8 기반
SECURITY_MAX = 20           # bandit 기반
COMMIT_MSG_MAX = 15         # Claude AI 0-20 → 0-15 스케일링
AI_REVIEW_MAX = 25          # Claude AI 0-20 → 0-25 스케일링
TEST_COVERAGE_MAX = 15      # Claude AI 0-10 → 0-15 스케일링

# ── 정적 분석 감점 가중치 ────────────────────────────────────────────────
PYLINT_ERROR_PENALTY = 3    # pylint error 1건당 감점
PYLINT_WARNING_PENALTY = 1  # pylint warning 1건당 감점
PYLINT_WARNING_CAP = 15     # warning 감점 상한 (건수 기준)
FLAKE8_WARNING_PENALTY = 1  # flake8 경고 1건당 감점
FLAKE8_WARNING_CAP = 10     # flake8 감점 상한 (건수 기준)
BANDIT_HIGH_PENALTY = 7     # bandit HIGH severity 1건당 감점
BANDIT_LOW_PENALTY = 2      # bandit LOW/MEDIUM severity 1건당 감점

# ── AI 기본값 (API 미설정·실패·empty_diff 시) ─────────────────────────
AI_DEFAULT_COMMIT = 13      # commit_score 기본값 (스케일링 후)
AI_DEFAULT_DIRECTION = 21   # ai_score 기본값 (스케일링 후)
AI_DEFAULT_TEST = 10        # test_score 기본값 (스케일링 후)

# ── 등급 임계값 ────────────────────────────────────────────────────────────
GRADE_THRESHOLDS: dict[str, int] = {"A": 90, "B": 75, "C": 60, "D": 45}
# F는 45 미만 (GRADE_THRESHOLDS 중 가장 낮은 값 미만)

# ── 분석 도구 설정 ─────────────────────────────────────────────────────────
STATIC_ANALYSIS_TIMEOUT = 30  # subprocess 타임아웃 (초)

# ── 파이프라인 이벤트 필터 ─────────────────────────────────────────────────
HANDLED_EVENTS: frozenset[str] = frozenset({"push", "pull_request"})
PR_HANDLED_ACTIONS: frozenset[str] = frozenset({"opened", "synchronize", "reopened"})
