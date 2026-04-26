"""SCAManager 전역 상수 — 점수 체계, 분석 도구, 파이프라인 설정.
SCAManager global constants — scoring system, analysis tools, pipeline configuration.
"""

# ── 점수 배점 ──────────────────────────────────────────────────────────────
# ── Scoring weights ────────────────────────────────────────────────────────
CODE_QUALITY_MAX = 25       # pylint + flake8 기반
SECURITY_MAX = 20           # bandit 기반
COMMIT_MSG_MAX = 15         # Claude AI 0-20 → 0-15 스케일링
AI_REVIEW_MAX = 25          # Claude AI 0-20 → 0-25 스케일링
TEST_COVERAGE_MAX = 15      # Claude AI 0-10 → 0-15 스케일링

# ── 정적 분석 감점 가중치 ────────────────────────────────────────────────
# ── Static analysis deduction weights ────────────────────────────────────
PYLINT_ERROR_PENALTY = 3    # code_quality error 1건당 감점
PYLINT_WARNING_PENALTY = 1  # code_quality warning 1건당 감점
PYLINT_WARNING_CAP = 15     # (deprecated) 구 pylint warning 상한 — CQ_WARNING_CAP 사용 권장
FLAKE8_WARNING_PENALTY = 1  # (deprecated) 구 flake8 경고 감점 — PYLINT_WARNING_PENALTY와 동일
FLAKE8_WARNING_CAP = 10     # (deprecated) 구 flake8 상한 — CQ_WARNING_CAP 사용 권장
CQ_WARNING_CAP = 25         # code_quality warning 감점 상한 (PYLINT_WARNING_CAP+FLAKE8_WARNING_CAP 합산)
BANDIT_HIGH_PENALTY = 7     # security error 1건당 감점
BANDIT_LOW_PENALTY = 2      # security warning 1건당 감점

# ── AI 기본값 (API 미설정·실패·empty_diff 시) ─────────────────────────
# ── AI defaults (when API key missing / call failure / empty diff) ───────
AI_DEFAULT_COMMIT = 13      # commit_score 기본값 (스케일링 후)
AI_DEFAULT_DIRECTION = 21   # ai_score 기본값 (스케일링 후)
AI_DEFAULT_TEST = 10        # test_score 기본값 (스케일링 후)
# hook.py: AiReviewResult 생성 시 사용하는 raw 스케일 기본값 (스케일링 전)
# hook.py: Raw-scale defaults used when constructing AiReviewResult (before scaling)
# 스케일링 후 결과가 파이프라인 기본값(AI_DEFAULT_*)과 일치하도록 역산
# Back-calculated so post-scaling values equal pipeline defaults (AI_DEFAULT_*)
AI_DEFAULT_COMMIT_RAW = 17  # raw 0-20 → round(17*15/20) = 13 = AI_DEFAULT_COMMIT
AI_DEFAULT_DIRECTION_RAW = 17  # raw 0-20 → round(17*25/20) = 21 = AI_DEFAULT_DIRECTION
AI_DEFAULT_TEST_RAW = 7     # raw 0-10 → round(7*15/10) = 10 = AI_DEFAULT_TEST

# ── 등급 임계값 ────────────────────────────────────────────────────────────
# ── Grade thresholds ────────────────────────────────────────────────────────
GRADE_THRESHOLDS: dict[str, int] = {"A": 90, "B": 75, "C": 60, "D": 45}
# F는 45 미만 (GRADE_THRESHOLDS 중 가장 낮은 값 미만)
# F is below 45 (below the lowest value in GRADE_THRESHOLDS)

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

# ── AI 스코어 raw 범위 (Claude 반환 범위 — 스케일링 기준) ──────────────────
AI_RAW_COMMIT_MAX = 20      # commit_score raw 범위 상한 (0-20)
AI_RAW_DIRECTION_MAX = 20   # ai_score raw 범위 상한 (0-20)
AI_RAW_TEST_MAX = 10        # test_score raw 범위 상한 (0-10)

# ── 알림 채널 표시 한도 ─────────────────────────────────────────────────────
# ── Notification channel display limits ──────────────────────────────────────
COMMIT_SHA_DISPLAY_LENGTH = 7    # 커밋 SHA 표시 자릿수 (short hash)
NOTIFIER_MAX_ISSUES_SHORT = 5    # Telegram·Discord·Slack 이슈 표시 상한
NOTIFIER_MAX_ISSUES_LONG = 10    # Email·GitHub Comment 이슈 표시 상한
NOTIFIER_MESSAGE_TRUNCATE = 80   # 이슈 메시지 1건 최대 길이 (문자 수)

# ── 채널별 메시지 크기 한도 ─────────────────────────────────────────────────
# ── Per-channel message size limits ──────────────────────────────────────────
TELEGRAM_MAX_MESSAGE_LENGTH = 4096    # Telegram API sendMessage text 최대 길이
DISCORD_EMBED_DESC_MAX_LENGTH = 4096  # Discord embed description 최대 길이
N8N_BODY_MAX_BYTES = 8192            # n8n relay 시 issue body 최대 바이트

# ── HTTP 클라이언트 설정 ─────────────────────────────────────────────────────
# ── HTTP client configuration ────────────────────────────────────────────────
HTTP_CLIENT_TIMEOUT = 10.0  # 외부 API 호출 타임아웃 (초)
GITHUB_API = "https://api.github.com"  # GitHub REST API 기본 URL (단일 출처)

# ── 언어 가이드 임계값 (review_prompt._select_guide_modes) ─────────────────
LANG_GUIDE_ALL_FULL_MAX = 3    # N<=3: 모든 언어 full 모드
LANG_GUIDE_TIER1_FULL_MAX = 6  # 4<=N<=6: Tier1 full, 나머지 compact
LANG_GUIDE_TOP3_FULL_MAX = 10  # 7<=N<=10: 상위 3개 full, 나머지 compact
LANG_GUIDE_COMPACT_LIMIT = 5   # N>10: 상위 5개만 compact, 나머지 이름만

# ── 분석 도구 설정 ─────────────────────────────────────────────────────────
# ── Analysis tool configuration ───────────────────────────────────────────
STATIC_ANALYSIS_TIMEOUT = 30  # subprocess 타임아웃 (초)

# ── Webhook 시크릿 캐시 설정 ─────────────────────────────────────────────────
WEBHOOK_SECRET_CACHE_TTL = 300  # per-repo webhook secret 캐시 TTL (초, 5분)

# ── 파이프라인 이벤트 필터 ─────────────────────────────────────────────────
# ── Pipeline event filter ─────────────────────────────────────────────────
HANDLED_EVENTS: frozenset[str] = frozenset({"push", "pull_request", "issues", "check_suite"})
# check_suite: CI-aware Auto Merge 재시도 트리거 (Phase 12)
# check_suite: Trigger for CI-aware Auto Merge retry (Phase 12)
PR_HANDLED_ACTIONS: frozenset[str] = frozenset({"opened", "synchronize", "reopened", "closed"})

# ── 봇 발신 / 자기 분석 루프 방지 상수 ────────────────────────────────────
# ── Bot sender / self-analysis loop guard constants ────────────────────────
BOT_LOGIN_WHITELIST: frozenset[str] = frozenset({"github-actions[bot]", "dependabot[bot]"})
# 허용 봇 로그인 목록 — 분석 skip 제외 (CI/CD 봇은 정상 동작)
# Whitelisted bot logins — exempt from analysis skip (CI/CD bots operate normally)

MAX_BOT_EVENTS_PER_HOUR: int = 6
# 리포당 1시간 내 최대 허용 봇 이벤트 수 — 초과 시 분석 skip
# Max bot events per repo per hour — exceeded events are skipped

SKIP_CI_MARKERS: tuple[str, ...] = ("[skip ci]", "[skip-sca]", "[ci skip]")
# 커밋 메시지에 이 문자열이 포함되면 분석 skip
# If any of these strings appear in a commit message, analysis is skipped
