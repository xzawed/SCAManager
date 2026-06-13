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
CQ_WARNING_CAP = 25         # code_quality warning 감점 상한 (구 PYLINT+FLAKE8 합산)
BANDIT_HIGH_PENALTY = 7     # security error 1건당 감점
BANDIT_LOW_PENALTY = 2      # security warning 1건당 감점

# ── AI 기본값 (API 미설정·실패·empty_diff 시) ─────────────────────────
# ── AI defaults (when API key missing / call failure / empty diff) ───────
AI_DEFAULT_COMMIT = 13      # commit_score 기본값 (스케일링 후)
AI_DEFAULT_DIRECTION = 21   # ai_score 기본값 (스케일링 후)
AI_DEFAULT_TEST = 10        # test_score 기본값 (스케일링 후)
# AiReviewResult 생성 시 사용하는 raw 스케일 기본값 (스케일링 전) — hook.py(_coerce_ai_scores 폴백) +
# analyzer/io/ai_review.py(_default_result) 양쪽 사용.
# Raw-scale defaults for constructing AiReviewResult (before scaling) — used by both
# hook.py (_coerce_ai_scores fallback) and analyzer/io/ai_review.py (_default_result).
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

# ── Gate 기본 임계값 (단일 출처 — config_manager·api·models·ui 공유) ─────────
# ── Gate default thresholds (single source — shared by config_manager/api/models/ui) ──
GATE_DEFAULT_APPROVE_THRESHOLD = 75   # approve_threshold 기본값
GATE_DEFAULT_REJECT_THRESHOLD = 50    # reject_threshold 기본값
GATE_DEFAULT_MERGE_THRESHOLD = 75     # merge_threshold 기본값

# ── 언어 가이드 임계값 (review_prompt._select_guide_modes) ─────────────────
LANG_GUIDE_ALL_FULL_MAX = 3    # N<=3: 모든 언어 full 모드
LANG_GUIDE_TIER1_FULL_MAX = 6  # 4<=N<=6: Tier1 full, 나머지 compact
LANG_GUIDE_TOP3_FULL_MAX = 10  # 7<=N<=10: 상위 3개 full, 나머지 compact
LANG_GUIDE_COMPACT_LIMIT = 5   # N>10: 상위 5개만 compact, 나머지 이름만

# ── 머지 검증자 (2nd-LLM cross-vendor 거버넌스 가드) ─────────────────────
# ── Merge verifier (2nd-LLM cross-vendor governance guard) ────────────────
OPENAI_VERIFIER_TIMEOUT = 60.0      # OpenAI 검증 호출 타임아웃(초) — Claude review 60s 와 대칭
# OpenAI verifier call timeout (seconds) — symmetric with Claude review 60s
MERGE_VERIFIER_BAND_DEFAULT = 10    # 경계 밴드 폭(점) — merge_threshold ~ +10 점만 검증
# Band width in points — only verify scores within merge_threshold ~ +10
VERIFIER_DIFF_CHAR_CAP = 60000      # 검증자 diff 상한(문자, ~15k 토큰) — 초과 시 OpenAI 미호출 + fail-closed 차단(대형 PR 수동 머지)
# Verifier diff cap (chars, ~15k tokens) — over cap → skip OpenAI + fail-closed block (large PRs go to manual merge)
VERIFIER_MAX_OUTPUT_TOKENS = 8192   # 검증자 응답 토큰 상한 — 소형 JSON + (gpt-5 계열) reasoning 여유 (2048 은 소진 위험, Codex mutual)
# Verifier response token cap — small JSON + headroom for (gpt-5-class) reasoning (2048 risked exhaustion)

# ── 분석 도구 설정 ─────────────────────────────────────────────────────────
# ── Analysis tool configuration ───────────────────────────────────────────
STATIC_ANALYSIS_TIMEOUT = 30    # 도구 1개당 subprocess 타임아웃 (초)
# PIPELINE_ANALYSIS_TIMEOUT 단일 출처는 src/worker/pipeline.py (정합성 감사 — 미사용 중복 상수 제거)
# Single source for PIPELINE_ANALYSIS_TIMEOUT is src/worker/pipeline.py (integrity-audit — removed unused duplicate)

# ── Webhook 시크릿 캐시 설정 ─────────────────────────────────────────────────
WEBHOOK_SECRET_CACHE_TTL = 300  # per-repo webhook secret 캐시 TTL (초, 5분)
# 🔴 캐시 엔트리 상한 — 서명 검증 전(pre-auth) 위조 repository.full_name 으로 캐시가
# 무한 증가하는 메모리 고갈을 차단 (초과 시 만료분 정리 후 가장 빨리 만료될 엔트리 evict).
# Cache entry cap — bounds memory against pre-auth unbounded growth from forged
# repository.full_name (on overflow, purge expired then evict the soonest-expiring entry).
WEBHOOK_SECRET_CACHE_MAX = 2048

# ── Telegram OTP brute-force 방어 (C12) ──────────────────────────────────────
# per-telegram_user_id 슬라이딩 윈도우 — 잘못된 /connect 시도만 카운트한다.
# 6자리 숫자 OTP(공간 10^6) + TTL 5분이라 무제한 추측 시 brute-force 가능 → 한도 차단.
# Per-telegram_user_id sliding window — counts only failed /connect attempts.
# A 6-digit OTP (10^6 space) with a 5-min TTL is brute-forceable without a cap.
OTP_MAX_FAILED_ATTEMPTS = 5          # 윈도우 내 허용 실패 횟수 / allowed failures per window
OTP_ATTEMPT_WINDOW_SECONDS = 300     # 슬라이딩 윈도우(초) — OTP TTL(5분)과 동일 / window = OTP TTL
# 🔴 추적 키 상한 — telegram_user_id 가 많아져도 dict 무한 증가를 막는다(메모리 고갈 방지).
# Tracked-key cap — bounds dict growth across many telegram_user_ids (memory guard).
OTP_LIMITER_MAX_KEYS = 2048

# ── 파이프라인 이벤트 필터 ─────────────────────────────────────────────────
# ── Pipeline event filter ─────────────────────────────────────────────────
HANDLED_EVENTS: frozenset[str] = frozenset({"push", "pull_request", "issues", "check_suite"})
# check_suite: CI-aware Auto Merge 재시도 트리거 (Phase 12)
# check_suite: Trigger for CI-aware Auto Merge retry (Phase 12)
PR_HANDLED_ACTIONS: frozenset[str] = frozenset({
    "opened", "synchronize", "reopened", "closed",
    # Phase 3 PR-B1 — Tier 3 native auto-merge lifecycle 추적용
    # GitHub 가 force-push, required check 실패, 사용자 수동 해제 시 발사
    # Phase 3 PR-B1 — for tracking Tier 3 native auto-merge lifecycle
    # GitHub fires this on force-push, required check failure, or manual disable
    "auto_merge_disabled",
})

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

# ── 점수 breakdown dict 키 (단일 출처 — 현재 calculator 전용, notifier·gate 확장 예정) ─────
# ── Score breakdown dict keys (single source — currently calculator only; notifier/gate extension planned) ──
BREAKDOWN_KEY_CODE_QUALITY = "code_quality"
BREAKDOWN_KEY_SECURITY = "security"
BREAKDOWN_KEY_COMMIT_MESSAGE = "commit_message"
BREAKDOWN_KEY_AI_REVIEW = "ai_review"
BREAKDOWN_KEY_TEST_COVERAGE = "test_coverage"

# ── Claude AI 모델 목록 + 요금 (Anthropic 공식 기준, USD/1M 토큰) ─────────
# ── Claude AI model catalog + pricing (Anthropic official, USD per 1M tokens) ─
# 출처: https://www.anthropic.com/pricing (2025-05 기준 — 실제 청구와 다를 수 있음)
# Source: https://www.anthropic.com/pricing (as of 2025-05 — actual billing may differ)
CLAUDE_MODELS: list[dict] = [
    {
        "id": "claude-haiku-4-5-20251001",
        "label": "Claude Haiku 4.5 (빠름/저렴 · Fast/Cheap)",
        "input_price": 0.80,
        "output_price": 4.00,
    },
    {
        "id": "claude-sonnet-4-6",
        "label": "Claude Sonnet 4.6 (균형 · Balanced) ★기본 · Default",
        "input_price": 3.00,
        "output_price": 15.00,
    },
    {
        "id": "claude-opus-4-7",
        "label": "Claude Opus 4.7 (고품질 · High Quality)",
        "input_price": 15.00,
        "output_price": 75.00,
    },
]

# 모델 ID → 가격 딕셔너리 (빠른 조회용)
# Model ID → pricing dict (for fast lookup)
CLAUDE_MODEL_PRICING: dict[str, dict[str, float]] = {
    m["id"]: {"input": m["input_price"], "output": m["output_price"]}
    for m in CLAUDE_MODELS
}

# 모델 미등록 시 fallback (Sonnet 기준)
# Fallback pricing when model not in registry (Sonnet tier)
CLAUDE_PRICING_FALLBACK: dict[str, float] = {"input": 3.00, "output": 15.00}
