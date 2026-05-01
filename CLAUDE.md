# SCAManager

> **문서 작성 원칙**: 이 프로젝트의 모든 문서는 Claude가 가장 읽기 쉽고 이해하기 편한 구조로 작성한다.
> 새 문서를 작성하거나 기존 문서를 수정할 때 이 원칙을 반드시 따른다.

> **코드 주석 원칙 (이중 언어)**: 모든 코드 주석은 **한국어와 영어를 병행**하여 작성한다.
> 한국어를 먼저 쓰고, 바로 다음 줄에 영어를 추가한다.
> 신규 코드 작성 시 즉시 적용하고, 기존 파일은 해당 파일을 수정할 때 함께 갱신한다.
> 예외: `# TODO`, `# FIXME`, `# type: ignore` 등 단어 하나짜리 표준 태그는 영어 단독 사용 허용.
>
> ```python
> # 레이트 리밋 초과 시 재시도
> # Retry on rate limit exceeded
>
> # 같은 SHA가 이미 분석된 경우 건너뜀 (멱등성 보장)
> # Skip if the same SHA was already analyzed (idempotency guard)
> ```

GitHub Push/PR 이벤트 시 정적 분석 + AI 코드 리뷰를 자동 수행하고, 점수와 개선사항을 Telegram·GitHub PR Comment·Discord·Slack·Email·n8n으로 전달하며, 점수 기반 PR 자동/반자동 Gate(Approve + 자동 Merge 포함)와 웹 대시보드를 제공하는 서비스. `git push` 시 Claude Code CLI 기반 자동 코드리뷰(pre-push hook)도 지원한다.

---

## 🧭 이 문서 탐색 가이드

| 상황 | 바로 가기 |
|------|----------|
| **작업 착수 전 (항상 30초)** | → [작업 시작 전 필수 체크리스트](#작업-시작-전-필수-체크리스트-매-작업마다) |
| **src/ 수정 후** | → [필수 원칙 — Hook 신뢰](#필수-원칙) |
| **Phase 완료 직전** | → [필수 원칙 — 완료 5-step · CLAUDE.md 동기화](#필수-원칙) |
| **ORM 컬럼 추가 시** | → [DB/마이그레이션 주의사항](#db--마이그레이션) |
| **새 파일 추가 시** | → [CLAUDE.md 아키텍처 동기화 체크리스트](#필수-원칙) |
| **아키텍처 파악** | → [src/ 트리](#아키텍처) · [핵심 데이터 흐름](#핵심-데이터-흐름) |
| **규칙 전체 열람** | → [주의사항 카테고리별](#주의사항-카테고리별) |

> **🔴 가장 빈번하게 놓치는 규칙 3가지**
> 1. ORM 컬럼 추가 후 `make revision` 마이그레이션 파일 미생성 → 운영 500 에러 (DB/마이그레이션 참조)
> 2. Phase 완료 후 CLAUDE.md 아키텍처 섹션 미갱신 → 다음 Claude 세션 혼란 (필수 원칙 참조)
> 3. 경로 없이 `python -m pytest` 실행 시 e2e 혼입 → 446건 false failure (testpaths=tests로 방어됨)

---

## 핵심 명령

```bash
cp .env.example .env   # 최초 설정
make install           # 의존성 설치 (requirements-dev.txt)
make run               # 개발 서버 (port 8000, DB 마이그레이션 자동)
```

| 명령 | 동작 |
|------|------|
| `make install` | 의존성 설치 |
| `make test` | 전체 테스트 (빠른 출력) |
| `make test-v` | 전체 테스트 (상세 출력) |
| `make test-fast` | 빠른 단위 테스트만 (`tests/integration/` 제외, `-m "not slow"`) |
| `make test-slow` | 통합 테스트만 (`tests/integration/` — 실 subprocess 실행) |
| `make test-cov` | 테스트 + 커버리지 |
| `make test-file f=tests/test_pipeline.py` | 특정 파일 테스트 |
| `make lint` | pylint + flake8 + bandit 검사 |
| `make review` | 로컬 코드리뷰 CLI 실행 (HEAD~1 기준) |
| `make run` | 개발 서버 실행 (port 8000) |
| `make migrate` | DB 마이그레이션 실행 |
| `make revision m="설명"` | 새 마이그레이션 파일 생성 |
| `make install-playwright` | Playwright + Chromium 설치 |
| `make test-e2e` | E2E 테스트 실행 (headless) |
| `make test-e2e-headed` | E2E 테스트 실행 (브라우저 표시) |

## 아키텍처

```
src/
├── main.py                     # FastAPI 앱, lifespan(DB 마이그레이션 + http_client), 전체 라우터 등록 + StaticFiles `/static` mount (UI 감사 Step C)
├── static/
│   └── vendor/
│       └── chart.umd.min.js    # Chart.js 4.4.0 UMD min vendoring — CDN 차단/오프라인 환경 호환 (UI 감사 Step C). 사용처: repo_detail / analysis_detail / insights_me
├── config.py                   # pydantic-settings 환경변수 관리, postgres:// URL 자동 변환
├── constants.py                # 전역 상수 단일 출처 — 점수배점/감점가중치/AI기본값/등급/알림한도/HTTP타임아웃/캐시TTL
├── crypto.py                   # encrypt_token()/decrypt_token() — TOKEN_ENCRYPTION_KEY
├── database.py                 # SQLAlchemy engine, Base, FailoverSessionFactory
├── shared/
│   ├── http_client.py          # httpx.AsyncClient lifespan 싱글톤 (내부 신뢰 API 용)
│   ├── log_safety.py           # sanitize_for_log() — 로그 인젝션 방지
│   ├── observability.py        # init_sentry() — Sentry SDK (Phase E.2a), before_send 로 PII 스크러빙
│   ├── claude_metrics.py       # Claude API 비용/latency 계측 — log_claude_api_call (Phase E.2b)
│   ├── stage_metrics.py        # stage_timer context manager — pipeline 단계 타이밍 (Phase E.2c)
│   └── merge_metrics.py        # parse_reason_tag + log_merge_attempt — auto-merge 관측 (Phase F.1)
├── services/                   # use case 계층 — 신규 오케스트레이션 모듈의 배치 장소 (기존 pipeline/engine/manager 는 도메인 위치 유지)
│   ├── analytics_service.py    # 집계 단일 출처 — weekly_summary, moving_average, top_issues, resolve_chat_id, author_trend, repo_comparison, leaderboard
│   ├── cron_service.py         # 주기적 실행 — run_weekly_reports, run_trend_check
│   └── merge_retry_service.py  # process_pending_retries 워커 (CI-aware Auto Merge 재시도)
├── auth/
│   ├── session.py              # get_current_user() + require_login Depends
│   └── github.py               # /login, /auth/github, /auth/callback, /auth/logout
├── models/
│   ├── repository.py           # Repository ORM (user_id FK nullable)
│   ├── analysis.py             # Analysis ORM (commit_message 포함)
│   ├── analysis_feedback.py    # AnalysisFeedback ORM (thumbs +1/-1, comment, Phase E.3)
│   ├── repo_config.py          # RepoConfig ORM (pr_review_comment, approve_mode, approve/reject_threshold, auto_merge, merge_threshold, hook_token)
│   ├── gate_decision.py        # GateDecision ORM
│   ├── merge_attempt.py        # MergeAttempt ORM — score/threshold 스냅샷 + failure_reason 정규 태그 (Phase F.1, append-only)
│   ├── merge_retry.py          # MergeRetryQueue ORM (재시도 큐, append-only claim 패턴)
│   └── user.py                 # User ORM (github_id, github_login, github_access_token, email, display_name)
├── webhook/
│   ├── _helpers.py             # get_webhook_secret() + _webhook_secret_cache (TTL 300초)
│   ├── validator.py            # HMAC-SHA256 서명 검증
│   ├── loop_guard.py           # is_bot_sender, is_whitelisted_bot (PR #100), has_skip_marker, BotInteractionLimiter
│   ├── router.py               # aggregator — providers 3개 include (+ 하위 호환 re-export)
│   └── providers/
│       ├── github.py           # POST /webhooks/github + merged-PR / issues 핸들러
│       ├── telegram.py         # POST /api/webhook/telegram + gate callback
│       └── railway.py          # POST /webhooks/railway/{token}
├── github_client/
│   ├── models.py               # ChangedFile dataclass 단일 출처
│   ├── helpers.py              # github_api_headers() 공용 헬퍼
│   ├── diff.py                 # get_pr_files, get_push_files
│   ├── issues.py               # close_issue() — Issue 종료 API
│   ├── repos.py                # list_user_repos(), create_webhook(), delete_webhook(), commit_scamanager_files()
│   ├── checks.py               # get_ci_status, get_required_check_contexts (5분 TTL 캐시, D2+D8 페이지네이션)
│   └── graphql.py              # GraphQL POST 래퍼 + enablePullRequestAutoMerge mutation + EnableAutoMergeResult 분류 (Tier 3 PR-A)
├── railway_client/
│   ├── models.py               # RailwayDeployEvent (3-그룹 nested) + RailwayProjectInfo + RailwayCommitInfo
│   ├── webhook.py              # parse_railway_payload() — deploy 실패 이벤트 파싱
│   └── logs.py                 # fetch_deployment_logs() — Railway GraphQL 로그 조회
├── analyzer/
│   ├── pure/                   # 순수 함수·데이터 (DB/HTTP 의존 없음 — 단위 테스트 고속)
│   │   ├── registry.py         # AnalyzeContext + Analyzer Protocol + REGISTRY + register() + Category/Severity StrEnum
│   │   ├── language.py         # detect_language(filename, content) — 50개 언어 감지. is_test_file()
│   │   ├── review_prompt.py    # build_review_prompt() — 언어별 가이드 조립 + 토큰 예산 관리(8000)
│   │   └── review_guides/      # 언어별 리뷰 체크리스트 (get_guide(lang, mode))
│   │       ├── tier1/          # python/js/ts/java/go/rust/c/cpp/csharp/ruby (상세)
│   │       ├── tier2/          # php/swift/kotlin/scala/shell ... fsharp (20개)
│   │       ├── tier3/          # erlang/ocaml/.../json_schema (20개 경량)
│   │       └── generic.py      # 알 수 없는 언어 fallback
│   ├── io/                     # I/O 바운드 (tempfile·subprocess·Claude API)
│   │   ├── static.py           # analyze_file — Registry 위임. AnalysisIssue(category/language 필드)
│   │   ├── ai_review.py        # review_code() — Claude API, AiReviewResult (detected_languages 포함)
│   │   └── tools/
│   │       ├── python.py       # _PylintAnalyzer, _Flake8Analyzer, _BanditAnalyzer (모듈 로드 시 자동 등록)
│   │       ├── semgrep.py      # _SemgrepAnalyzer — 22개 언어, graceful degradation
│   │       ├── eslint.py       # _ESLintAnalyzer — JS/TS, flat config
│   │       ├── shellcheck.py   # _ShellCheckAnalyzer — shell 스크립트
│   │       ├── cppcheck.py     # _CppCheckAnalyzer — C/C++, XML v2 stderr 파싱
│   │       ├── slither.py      # _SlitherAnalyzer — Solidity, stdout JSON, mixed-category
│   │       ├── rubocop.py      # _RuboCopAnalyzer — Ruby, Security/ cop → security
│   │       └── golangci_lint.py # _GolangciLintAnalyzer — Go, go.mod 자동생성, gosec → security
│   └── configs/                # eslint.config.json 등 외부 도구 설정 파일 (런타임 리소스)
├── scorer/
│   └── calculator.py           # calculate_score(ai_review), ScoreResult, _grade
├── config_manager/
│   └── manager.py              # get_repo_config(), upsert_repo_config(), RepoConfigData
├── gate/
│   ├── _common.py              # score_from_result() 공용 헬퍼 (engine 과 향후 actions 공유)
│   ├── engine.py               # run_gate_check() — 3-옵션 독립 처리 (직접 구현)
│   ├── github_review.py        # post_github_review(), merge_pr() (REST 폴백 경로)
│   ├── native_automerge.py     # enable_or_fallback() — GraphQL enablePullRequestAutoMerge 우선 + REST merge_pr 폴백 (Tier 3 PR-A)
│   ├── merge_reasons.py        # auto-merge 실패 사유 정규 태그 상수 (Phase F QW5) — branch_protection_blocked, unstable_ci, permission_denied 등
│   ├── telegram_gate.py        # send_gate_request() — 인라인 키보드 메시지
│   ├── merge_failure_advisor.py # get_advice(reason) — reason tag → 권장 조치 텍스트 (Phase F.3 + Tier 3 PR-A enable reason 4종)
│   ├── retry_policy.py         # 순수 함수: parse_reason_tag, should_retry, compute_next_retry_at, is_expired, mergeable_state_terminality
│   └── _merge_attempt_states.py # MergeAttempt.state lifecycle 정규 상수 (LEGACY/ENABLED_PENDING_MERGE/ACTUALLY_MERGED/DISABLED_EXTERNALLY) — Phase 3 PR-B1 도입
├── notifier/                   # `__init__.py` 가 import 시 각 채널 모듈 자동 로드 → REGISTRY 등록 (Phase S.3-E)
│   ├── __init__.py             # 8개 notifier 모듈 import (등록 순서 = 발송 우선순위)
│   ├── _common.py              # 공통 헬퍼 — format_ref, get_all_issues, get_issue_samples, truncate_message, truncate_issue_msg
│   ├── telegram_commands.py    # Telegram 인라인 명령 처리 — /stats, /settings, /connect OTP 흐름
│   ├── _http.py                # build_safe_client() — HTTP_CLIENT_TIMEOUT + follow_redirects=False (SSRF 방어)
│   ├── registry.py             # NotifyContext + Notifier Protocol + REGISTRY + register() (채널 확장)
│   ├── telegram.py             # send_analysis_result() + _TelegramNotifier (항상 활성, global chat_id fallback)
│   ├── discord.py              # send_discord_notification() + _DiscordNotifier (discord_webhook_url 설정 시)
│   ├── slack.py                # send_slack_notification() + _SlackNotifier (slack_webhook_url 설정 시)
│   ├── webhook.py              # send_webhook_notification() + _WebhookNotifier (custom_webhook_url 설정 시)
│   ├── email.py                # send_email_notification() + _EmailNotifier (SMTP 설정 시)
│   ├── n8n.py                  # notify_n8n() + _N8nNotifier (n8n_webhook_url 설정 시)
│   ├── github_comment.py       # post_pr_comment_from_result() — result dict 기반 (PR 전용, gate/engine 에서 호출)
│   ├── github_commit_comment.py # post_commit_comment() + _CommitCommentNotifier (Push 전용)
│   ├── github_issue.py         # create_low_score_issue() + _IssueNotifier (저점 OR bandit HIGH 시)
│   ├── railway_issue.py        # create_deploy_failure_issue() — Railway 빌드 실패 Issue (dedup, webhook 경유)
│   └── merge_failure_issue.py  # create_merge_failure_issue() — auto-merge 실패 GitHub Issue (Phase F.3, dedup 24h)
├── api/
│   ├── auth.py                 # require_api_key Depends (X-API-Key 헤더)
│   ├── deps.py                 # get_repo_or_404(repo_name, db) 공용 헬퍼
│   ├── repos.py                # GET/PUT /api/repos, /api/repos/{repo}/analyses, /config
│   ├── stats.py                # GET /api/analyses/{id}, /api/repos/{repo}/stats
│   ├── hook.py                 # GET /api/hook/verify, POST /api/hook/result (hook_token 인증)
│   ├── users.py                # POST /api/users/me/telegram-otp — 6자리 OTP 발급 (5분 만료)
│   ├── internal_cron.py        # POST /api/internal/cron/weekly|trend — INTERNAL_CRON_API_KEY 전용
│   └── insights.py             # GET /api/insights/authors/{login}/trend, /repos/compare, /leaderboard — require_api_key
├── ui/
│   ├── _helpers.py             # get_accessible_repo · webhook_base_url · delete_repo_cascade · templates
│   ├── router.py               # aggregator — routes 6개 include (catch-all `/repos/{name}` 마지막)
│   └── routes/
│       ├── overview.py         # GET /
│       ├── insights.py         # GET /insights (멀티 리포 비교), GET /insights/me (개인 추세)
│       ├── add_repo.py         # /repos/add (GET/POST) · /api/github/repos
│       ├── settings.py         # /repos/{name}/settings · reinstall-hook · reinstall-webhook
│       ├── actions.py          # /repos/{name}/delete
│       └── detail.py           # /repos/{name}/analyses/{id} · /repos/{name}
├── templates/                  # add_repo, base, login, overview, repo_detail, analysis_detail, settings, insights, insights_me
├── cli/
│   ├── __main__.py             # python -m src.cli review
│   ├── git_diff.py             # 로컬 git diff 수집
│   └── formatter.py            # 터미널 출력 포맷 (ANSI 색상)
├── repositories/               # DB 접근 계층 8종 — repository_repo (find_by_full_name + Phase H 신규 find_by_full_name_with_owner opt-in joinedload), analysis_repo, analysis_feedback_repo, merge_attempt_repo, gate_decision_repo, repo_config_repo, user_repo, merge_retry_repo
└── worker/
    └── pipeline.py             # run_analysis_pipeline, build_analysis_result_dict
```

### 핵심 데이터 흐름

```
GitHub Push/PR
  → POST /webhooks/github (HMAC 서명 검증)
  → PR action 필터링 (opened/synchronize/reopened만 처리)
  → BackgroundTasks 비동기 등록
  → run_analysis_pipeline()
      → Repository DB 등록 (API 호출 전, 실패해도 목록 노출 보장)
      → _extract_commit_message() — PR: title+body, Push: head_commit 우선
      → get_pr_files / get_push_files (모든 변경 파일 수집)
      → asyncio.gather() 병렬 실행:
          ├─ analyze_file() × N  (.py만 정적 분석, 테스트 파일은 bandit 제외)
          └─ review_code()       (Claude AI — 50개 언어 체크리스트 + 토큰 예산 관리)
      → calculate_score(ai_review)
          (코드품질25 + 보안20 + 커밋15 + AI방향성25 + 테스트15)
      → DB 저장 (Analysis 레코드)
      → run_gate_check() [PR 이벤트만] — 3-옵션 완전 독립 처리
          [pr_review_comment=on] → post_pr_comment_from_result() — PR에 AI 코드리뷰 댓글 발송
          [approve_mode=auto]    → score ≥ approve_threshold → GitHub APPROVE
                                   score < reject_threshold → GitHub REQUEST_CHANGES
          [approve_mode=semi]    → Telegram 인라인 키보드 전송 → POST /api/webhook/telegram 콜백 수신
          [auto_merge=on, score ≥ merge_threshold] → native_enable_or_fallback() (Tier 3 PR-A)
              ├─ enable_pull_request_auto_merge GraphQL mutation (우선 시도)
              │     → 성공 시 GitHub 가 CI 통과 후 자동 squash merge 수행
              │     → ENABLE_FORCE_PUSHED → 즉시 실패 (폴백 X)
              ├─ ENABLE_DISABLED_IN_REPO / ENABLE_PERMISSION_DENIED → REST merge_pr 폴백
              └─ ENABLE_API_ERROR (분류 외) → REST merge_pr 폴백
          [auto_merge=on, mergeable_state=unstable/unknown] → merge_retry_queue 큐잉
              → check_suite.completed 웹훅 즉각 트리거 OR 1분 cron fallback
              → process_pending_retries() → 조건 충족 시 재시도 (최대 30회, 24h)
      → _build_notify_tasks() — RepoConfig 기반 채널 디스패처
      → asyncio.gather(return_exceptions=True):
          ├─ send_analysis_result()        (Telegram — notify_chat_id 또는 global fallback)
          ├─ send_discord_notification()   (discord_webhook_url 설정 시)
          ├─ send_slack_notification()     (slack_webhook_url 설정 시)
          ├─ send_webhook_notification()   (custom_webhook_url 설정 시)
          ├─ send_email_notification()     (email_recipients + SMTP 설정 시)
          └─ notify_n8n()                  (n8n_webhook_url 설정 시)

Telegram 반자동 콜백:
  → POST /api/webhook/telegram
  → gate:{decision}:{id}:{token} 파싱 (HMAC 인증 포함)
  → post_github_review() + GateDecision DB 저장
  → auto_merge=on, score ≥ merge_threshold → native_enable_or_fallback() (approve_mode 무관하게 독립 동작)

대시보드:
  → GET /                              (리포 현황 Web UI)
  → GET /repos/{repo}                  (점수 차트 + 이력 Web UI)
  → GET /repos/{repo}/analyses/{id}    (분석 상세 — AI 리뷰·피드백·이슈)
  → GET /api/repos                     (REST API)
  → GET /api/repos/{repo}/stats        (통계 API)

CLI Hook (로컬 pre-push 자동 코드리뷰):
  Repo 등록 시 (POST /repos/add):
    → hook_token = secrets.token_hex(32) 생성 → RepoConfig 저장
    → GitHub Contents API로 .scamanager/config.json + install-hook.sh 커밋
    → 개발자: git pull && bash .scamanager/install-hook.sh (1회)
  git push 시 (.git/hooks/pre-push 자동 실행):
    → GET /api/hook/verify?repo=...&token=... (미등록 시 조용히 skip)
    → git diff로 push 대상 diff 수집
    → claude -p "[프롬프트+diff]" 실행 (Claude Code CLI — ANTHROPIC_API_KEY 불필요)
    → 터미널에 결과 출력
    → POST /api/hook/result → Analysis DB 저장 + 대시보드 반영
    → exit 0 (push 항상 진행)
```

### 점수 체계

| 항목 | 배점 | 도구 | 감점 규칙 |
|------|------|------|----------|
| 코드 품질 | 25점 | pylint + flake8 + semgrep(code_quality) | error -3, warning -1 (CQ_WARNING_CAP=25 통합 cap) |
| 보안 | 20점 | bandit + semgrep(security) | HIGH -7, LOW/MED -2 |
| 커밋 메시지 품질 | 15점 | Claude AI (0-20 → 0-15 스케일링) | — |
| 구현 방향성 | 25점 | Claude AI (0-20 → 0-25 스케일링) | — |
| 테스트 | 15점 | Claude AI (0-10 → 0-15 스케일링, 비-코드 파일 면제) | — |

등급: A(90+), B(75+), C(60+), D(45+), F(44-)

> `ANTHROPIC_API_KEY` 미설정 시 AI 항목은 중립적 기본값(커밋13 + 방향21 + 테스트10 = 44/55)으로 fallback, AI 없이도 최대 89점(B등급) 가능

## 환경변수 (필수만)

| 변수 | 설명 |
|------|------|
| `DATABASE_URL` | PostgreSQL 연결 URL (`postgres://`는 `postgresql://`로 자동 변환) |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API 토큰 |
| `TELEGRAM_CHAT_ID` | Telegram 알림 수신 Chat ID |
| `GITHUB_CLIENT_ID` | GitHub OAuth 앱 클라이언트 ID |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth 앱 클라이언트 시크릿 |
| `SESSION_SECRET` | 세션 쿠키 서명 키 (32자 이상 랜덤 문자열 필수) |
| `APP_BASE_URL` | Railway 배포 시 HTTPS URL 강제 (OAuth + Webhook 양쪽 적용) — Railway 필수 |
| `ANTHROPIC_API_KEY` | Claude AI 리뷰 (없으면 기본값 fallback) |

전체 환경변수 목록: `docs/reference/env-vars.md`

## Railway 배포

```bash
# 시작 명령 (railway.toml에 설정됨 — --proxy-headers 포함)
uvicorn src.main:app --host 0.0.0.0 --port $PORT --proxy-headers
# DB 마이그레이션은 앱 lifespan에서 자동 실행
```

Railway 대시보드 설정:
- **PostgreSQL 플러그인** 추가 (`DATABASE_URL` 자동 생성)
- **Variables** 탭에서 나머지 환경변수 설정 (`${{Postgres.DATABASE_URL}}`)
- `APP_BASE_URL` 반드시 설정 — OAuth redirect_uri HTTPS 보장

헬스체크: `GET /health` → `{"status":"ok"}` (timeout: 60초). **`active_db` 등 내부 상태는 의도적으로 미노출** — 정보 노출 방지 (`tests/unit/test_main.py::test_health_returns_status_ok` 가 회귀 보장). DB failover 모니터링이 필요하면 별도 인증 엔드포인트 (`INTERNAL_CRON_API_KEY` 또는 admin key 기반) 신설 권장.

### NIXPACKS 빌드 설정 우선순위

| 우선순위 | 설정 위치 | 적용 범위 |
|---------|----------|---------|
| 1 | `railway.toml`의 `buildCommand` | 빌드 명령 최상위 오버라이드 |
| 2 | `nixpacks.toml`의 `[phases.build]` | NIXPACKS 빌드 단계 설정 |
| 3 | `nixpacks.toml`의 `providers` | NIXPACKS 언어 감지 오버라이드 |
| 4 | NIXPACKS 자동 감지 | `requirements.txt`, `package.json` 등 파일 기반 |

현재: `railway.toml`에 `buildCommand = "npm install -g eslint@9 @typescript-eslint/parser @typescript-eslint/eslint-plugin"` 설정됨.
Node.js는 `nixpacks.toml` aptPkgs로 설치, eslint 전역 설치는 buildCommand에서 수행.

```
requirements.txt      ← Railway(프로덕션) 전용 — pytest/playwright 제외
requirements-dev.txt  ← 로컬 개발 환경 — pytest, playwright 포함 (-r requirements.txt 포함)
```

## Agent 작업 규칙

모든 AI 에이전트(Claude Code 및 서브에이전트)는 SCAManager 작업 시 아래 규칙을 **반드시** 따른다.
`.claude/` 디렉토리에 정의된 스킬과 에이전트는 선택이 아닌 의무적 도구다.

### 작업 시작 전 필수 체크리스트 (매 작업마다)

모든 작업 착수 전 아래 세 가지를 순서대로 확인한다. 30초면 충분하다.

```bash
gh run list --limit 3        # CI 현재 상태 — 기존 실패와 신규 실패 구분
git status                   # 미커밋 변경 없는지 확인
git checkout -b <브랜치명>   # 브랜치 생성 (main 직접 커밋 금지)
```

**브랜치 명명 규칙**

| 접두사 | 사용 시점 |
|--------|----------|
| `feat/` | 새 기능 구현 |
| `fix/` | 버그 수정 |
| `chore/` | 설정·문서·툴링 변경 |
| `docs/` | 문서 전용 변경 |

**예외 없음** — `.claude/` 내부 파일(Hook·에이전트·스킬), `CLAUDE.md`, `docs/` 변경도 모두 브랜치 + PR 방식으로 진행한다.

### 필수 원칙

- **TDD 우선**: 구현 코드 작성 전 반드시 `test-writer` 에이전트로 테스트를 먼저 작성한다.
- **Hook 신뢰**: `src/` 파일 편집 후 PostToolUse Hook이 자동 실행하는 pytest 결과를 확인한다. 실패 시 다음 단계로 진행하지 않는다.
- **Phase 완료 조건**: 테스트 전체 통과 + `/lint` 통과 + (파이프라인 변경 시 `pipeline-reviewer` 승인) 세 조건이 모두 충족될 때만 Phase 완료를 선언한다.
- **완료 시 필수 5-step**: 작업이 완료되면 반드시 ① 커밋 → ② PR 생성(`gh pr create`) → ③ `git push` → ④ `docs/STATE.md` 수치 갱신 → ⑤ **CLAUDE.md 아키텍처 섹션 동기화** (신규 파일 추가·삭제·이름 변경 시 `src/` 트리와 `### 핵심 데이터 흐름` 내 언급 갱신) 를 순서대로 수행한다. 예외 없음.
- **README.md 배지 동기화**: 테스트 수·pylint·커버리지 수치가 바뀌면 `README.md` 14~18줄 배지도 함께 갱신한다. 수치 출처는 항상 `docs/STATE.md`.
- **CLAUDE.md 아키텍처 동기화 체크리스트**: `src/` 하위에 파일 추가 시 아래 항목을 순서대로 확인한다. 누락 시 다음 Phase 착수 전 반드시 보완한다. (전례: Phase 11에서 6개 파일 추가 후 CLAUDE.md에 5개 누락 → 3-에이전트 감사에서 발견, PR #73)

  | 위치 | 확인 사항 |
  |------|----------|
  | `src/` 트리 블록 | 신규 파일 한 줄 항목(경로 + 짧은 역할 설명) 추가 |
  | `templates/` 한 줄 | 신규 템플릿 파일명 목록에 추가 |
  | `repositories/` 한 줄 | 신규 repo 파일 "N종" 카운트 + 목록 갱신 |
  | `services/` 한 줄 | 신규 service 함수 목록 갱신 |
  | `### 핵심 데이터 흐름` | 신규 경로가 흐름도에 포함되어야 하면 추가 |

### 모바일 환경 보호 — 수정 금지 파일

아래 파일들은 자동화 테스트로 검증이 불가능한 고위험 영역이다.
**`pytest, fastapi, sqlalchemy`가 import 불가능한 환경(테스트 환경 미구성)에서는 절대 수정하지 않는다.**
PreToolUse Hook(`.claude/hooks/check_edit_allowed.py`)이 자동으로 차단한다.

| 파일/경로 | 위험 유형 | 차단 조건 |
|-----------|----------|----------|
| `alembic/versions/` | DB 스키마 손상, 데이터 손실 | 테스트 환경 없을 때 |
| `src/templates/*.html` | Jinja2 렌더링 오류 (pytest 미감지) | 테스트 환경 없을 때 |
| `railway.toml` | 프로덕션 배포 실패 | 테스트 환경 없을 때 |
| `Procfile` | 프로덕션 시작 명령 오류 | 테스트 환경 없을 때 |
| `alembic.ini` | Alembic 경로 설정 오류 | 테스트 환경 없을 때 |

**예외:** `make test` 가 정상 실행되는 환경(로컬 PC, GitHub Codespaces)에서는 모든 파일 수정이 허용된다.

### 작업 유형별 필수 실행 순서

**1. 새 기능 구현 시**
1. `test-writer` 에이전트 → 테스트 파일 작성 (Red)
2. Hook 자동 실행 → 실패 확인 (Red 검증)
3. 구현 코드 작성
4. Hook 자동 실행 → 통과 확인 (Green)
5. `/lint` → 코드 품질 검사 (Refactor)
6. `/test coverage` → 커버리지 확인

**2. 파이프라인 수정 시** (`src/worker/`, `src/analyzer/`, `src/scorer/`)
1. `test-writer` 에이전트 → 변경 대상 테스트 선작성
2. 구현 후 Hook 자동 실행 결과 확인
3. `pipeline-reviewer` 에이전트 → 멱등성·오류 처리·성능 검토
4. `/lint` → 보안(bandit) 포함 전체 검사

**3. Webhook/API 수정 시** (`src/webhook/`, `src/notifier/`, `src/main.py`)
1. `test-writer` 에이전트 → 엔드포인트 테스트 선작성
2. 구현 후 `/test webhook` 또는 `/test pipeline`으로 모듈 테스트
3. `/webhook-test` → 로컬 서버에서 실제 엔드-투-엔드 검증
4. 서명 검증 로직 변경 시 401/202 응답 코드 직접 확인

**4. 다음 Phase 착수 시**
1. 현행 Phase 완료 조건 모두 충족 확인 (`/test`, `/lint`)
2. `/phase-next` → 브레인스토밍 및 설계 시작
3. 설계 문서 작성 후 `test-writer` 에이전트로 Phase 첫 테스트 작성

### 병렬 에이전트 — 브랜치 충돌 방지

독립 브랜치 + PR이 필요한 병렬 에이전트를 디스패치할 때 아래 세 가지를 반드시 지킨다.
(전례: 2026-04-27 PR-A·B·C 병렬 작업에서 3개 에이전트 모두 같은 브랜치에 커밋 → PR 3개 대신 1개 생성)

1. **`isolation: worktree` 전원 적용** — 독립 브랜치가 필요한 모든 에이전트에 예외 없이 적용.
2. **프롬프트 첫 단계에서 고유 브랜치명 명시** — 아래 형식을 프롬프트 Step 1로 고정.
   ```
   1. git checkout -b docs/phase12-state-readme  (이미 있으면 switch)
   ```
3. **완료 기준에 "PR URL 반환" 포함** — 에이전트가 분석만 하고 멈추는 사고 방지.
   ```
   완료 조건: gh pr create 성공 후 PR URL 반환
   ```

> **나쁜 방식** → 에이전트 프롬프트: "PR-B 작업을 수행해주세요"
> **좋은 방식** → 프롬프트 Step 1에 `git checkout -b docs/<고유-이름>` 명시 + `isolation: worktree` 설정

### 도구 사용 시점 요약

| 도구 | 사용 시점 | 통과 기준 |
|------|----------|----------|
| PostToolUse Hook | `src/` 파일 편집 직후 자동 실행 | 0 failed |
| `/test` | Hook 실패 시 상세 분석, PR 생성 전 | 전체 통과 |
| `/test coverage` | Phase 완료 전 커버리지 확인 | 커버리지 유지 또는 향상 |
| `/lint` | 테스트 통과 후 (Refactor 단계), Phase 완료 전 | pylint 8.0+, bandit HIGH 0 |
| `/webhook-test` | Webhook·파이프라인·알림 경로 변경 후 | 202 Accepted 응답 |
| `/phase-next` | Phase 완료 조건 충족 후, 다음 Phase 착수 전 | — |
| `test-writer` 에이전트 | 모든 신규 기능·모듈 구현 착수 전 | 테스트 파일 먼저 생성 |
| `pipeline-reviewer` 에이전트 | 파이프라인 핵심 파일 변경 후 | 전 항목 ✅ |

## 주의사항 (카테고리별)

> 아래 섹션은 카테고리별 상세 규칙이다. 전체를 매번 읽을 필요는 없다 — **상황에 맞는 섹션만 열람**한다. 🔴 표시는 과거 사고로 검증된 고위험 규칙이다.

### 테스트

- 🔴 **asyncio_mode = auto**: `pytest.ini`의 `asyncio_mode = auto` 필수 — 없으면 모든 async 테스트가 경고 없이 실패.
- **테스트 환경 변수**: `tests/conftest.py`가 `os.environ.setdefault`로 환경변수를 주입함. src 모듈은 import 시점에 `Settings()`를 인스턴스화하므로 conftest가 반드시 먼저 실행되어야 함.
- **E2E 격리**: `e2e/`를 최상위 별도 디렉토리로 분리 (`tests/` 아래 금지) — `tests/e2e/`가 있으면 `asyncio_mode=auto`와 `sys.modules` 삭제가 충돌해 단위 테스트 98개 실패. E2E 서버는 `uvicorn.Server.serve()`를 `asyncio.new_event_loop()` + `loop.run_until_complete()`로 실행.
- **require_login 우회**: `tests/test_ui_router.py`는 `app.dependency_overrides[require_login] = lambda: _test_user`로 의존성 override. 신규 UI 라우트 테스트 작성 시 동일 패턴 사용.
- **Mock side_effect 재귀**: `mock.add.side_effect = fn` 설정 후 fn 내에서 `original_add(obj)` 호출 시 재귀 발생. side_effect 함수에서는 원본 mock을 호출하지 말 것 — 캡처만 하고 return None.
- **모듈 레벨 캐시 격리**: `src/webhook/_helpers.py`의 `_webhook_secret_cache`는 모듈 레벨 dict. `tests/conftest.py`의 `_clear_webhook_secret_cache` autouse fixture가 테스트마다 자동 클리어. 신규 모듈 레벨 캐시 추가 시 동일한 autouse fixture 패턴 적용 필수 — 미적용 시 테스트 순서 의존성 버그 발생.
- **`services/analytics_service.py` 테스트 패턴**: `db: Session` 인자 + `now: datetime | None = None` 의존성 주입(freezegun 미사용). 각 테스트 파일은 자체 in-memory SQLite engine fixture (`tests/unit/repositories/test_analysis_feedback_repo.py:20-58` 참조). `func.count/avg/min/max` 호출 시 `# pylint: disable=not-callable` 인라인 주석 필수 (E1102 false positive).
- 🔴 **감사 식별 Critical 항목은 단순 hardening 단정 금지 (Phase H PR-5C 교훈)**: 12-에이전트 감사 등이 식별한 Critical 항목을 처리할 때 단위 테스트 통과만으로 검증 완료 단정 금지. `_TOKEN_42` 같은 하드코딩 fixture 가 receiver pattern 을 받아쓰기 (사이드웨이) 로 우회해 functional bug 를 가릴 수 있음 — PR-5C 사례 (모든 semi-auto Telegram 콜백이 실제 운영에서 401 거부됐으나 테스트는 통과). TDD Red 단계에서 "기존 테스트가 왜 통과하는가" 자문 의무.
- 🔴 **`find_by_full_name` 같은 hot-path repository 함수 시그니처 변경 금지 (Phase H PR-3B)**: 70+ 단위 테스트가 `db.query.return_value.filter.return_value.first` mock chain 사용. `.options(joinedload(...))` 같은 메서드 추가 시 chain 깨짐 → 70+ 회귀 (Phase S.4 트랩 재발견). 신규 옵션은 별도 함수 (`find_by_full_name_with_owner` 패턴) 로 분리 — 기존 시그니처 불변.
- 🔴 **의도적 중복 코드의 PARITY GUARD 패턴 (Phase H PR-5A)**: 두 모듈에 의도적으로 동일 함수가 있는 경우 (예: `_get_ci_status_safe` engine + service), 양쪽 docstring 에 `🔴 **PARITY GUARD**` 표지 + 변경 시 동시 수정 의무 명시 + parity 회귀 가드 테스트 (시그니처 + 행동 동등성) 의무. drift 즉시 검출. 통합 PR 은 mock patch 경로 마이그레이션 동반 필요로 별도 진행 권장.

### DB / 마이그레이션

- 🔴 **Alembic batch_alter_table 금지**: SQLite 전용 패턴. PostgreSQL에서는 `op.create_unique_constraint('이름', '테이블', ['컬럼'])` 직접 사용. 잘못 사용 시 lifespan 마이그레이션 실패 → Railway 헬스체크 실패. **예외**: `0005_add_users_and_user_id.py`, `0006_phase8b_github_oauth.py`는 이미 프로덕션에 적용된 이력 마이그레이션이므로 수정 금지 — `alembic downgrade` 경로 파괴 위험. 신규 마이그레이션(0007 이후)에만 이 규칙을 적용한다.
- **FailoverSessionFactory**: `DATABASE_URL_FALLBACK` 설정 시 Primary `OperationalError` → Fallback DB 자동 전환. `_probe_primary_loop` daemon 스레드가 복구 확인 후 자동 복귀. 미설정 시 단일 엔진 모드(probe 스레드 없음). 소비자 코드(`SessionLocal()`)는 변경 없이 그대로 사용. `engine = SessionLocal._primary_engine`으로 alembic/env.py 호환성 유지.
- **DB 세션 expunge**: `get_current_user()`는 `db.expunge(user)` 후 세션 반환 — 세션 종료 후에도 컬럼 속성 안전하게 접근 가능. 관계 lazy-load 사용 금지.
- **ThreadPoolExecutor with 블록 금지**: `with` 문은 `shutdown(wait=True)` 호출 → DNS hang 시 무기한 블록. `try/finally` + `executor.shutdown(wait=False)` 패턴 사용 (database.py 참조).
- **SQLite hostaddr 제외**: `_ipv4_connect_args`는 hostname이 None(SQLite URL)이면 빈 dict 반환 — 그렇지 않으면 `sqlite3.connect(hostaddr=...)` TypeError 발생.
- **`Analysis.author_login` NULL 정책**: 신규 컬럼은 backfill 없이 NULL 허용. 모든 집계는 `WHERE author_login IS NOT NULL` 적용. backfill 필요 시 `scripts/backfill_author.py` 별도 실행. PR 이벤트 = `pull_request.user.login`, Push 이벤트 = `head_commit.author.username`.
- 🔴 **ORM 컬럼 추가 시 마이그레이션 필수 동반**: `models/*.py`에 `Column(...)` 추가 후 반드시 `make revision m="설명"` 으로 마이그레이션 파일을 함께 생성해야 한다. 단위 테스트는 in-memory SQLite(`Base.metadata.create_all`)로 ORM 정의 그대로 테이블을 만들기 때문에 마이그레이션 파일이 없어도 테스트가 통과한다. 그러나 실제 DB(PostgreSQL/Railway)에는 컬럼이 생성되지 않아 운영 환경에서 500 에러가 발생한다. 전례: `leaderboard_opt_in` 컬럼 (PR #72·#74, 2026-04-26).
- **`merge_retry_queue` 클레임 패턴**: `claim_batch` 은 단일 SQL `UPDATE … WHERE claimed_at IS NULL RETURNING (attempts_count = 1) AS is_first` 로 원자적 클레임 + 첫-지연 알림 결정 동시 수행. Postgres 는 `FOR UPDATE SKIP LOCKED`, SQLite 는 dialect 분기. 재배포 중 stale claim 은 5분 후 재클레임. 신규 큐 도입 시 동일 패턴 권장.
- 🔴 **DB 인덱스 정의 — ORM `__table_args__` + alembic 양쪽 의무 (Phase H PR-4A)**: 신규 인덱스 추가 시 `models/*.py` 의 `__table_args__ = (Index(...), ...)` 와 `alembic/versions/NNNN_*.py` 의 `op.create_index(...)` 양쪽 정의 필수. ORM-only 정의는 단위 테스트 (in-memory SQLite `create_all`) 에서는 인식되지만 운영 PG 에 미반영 → 인덱스 활용 실패. 회귀 가드 테스트는 SQLAlchemy `inspect()` 로 인덱스 컬럼 검증 (`tests/unit/migrations/test_0023_composite_indexes.py` 참조).
- 🔴 **FK ondelete CASCADE 일관성 매트릭스 (Phase H C7)**: child 테이블의 `ForeignKey("parent.id")` 추가 시 다른 child 모델의 `ondelete` 정책 일관성 검토 의무. 현재 `analyses.id` 를 참조하는 child 4종 모두 CASCADE 통일:

  | child 모델 | FK 컬럼 | ondelete | 도입 시점 |
  |------|------|------|------|
  | `MergeAttempt.analysis_id` | analyses.id | **CASCADE** | Phase F.1 |
  | `MergeRetryQueue.analysis_id` | analyses.id | **CASCADE** | Phase 12 |
  | `AnalysisFeedback.analysis_id` | analyses.id | **CASCADE** | Phase E.3 |
  | `GateDecision.analysis_id` | analyses.id | **CASCADE** | Phase H C7 (alembic 0024) |

  신규 child 추가 시 동일 CASCADE 적용 (default), 다른 정책 (RESTRICT/SET NULL) 채택 시 회고에 사유 명시. application-level `delete_repo_cascade` (`ui/_helpers.py`) 는 admin script 우회 경로 보완 — DB 레벨 CASCADE 가 1차 안전망.

### 파이프라인 / 비즈니스 로직

- **멱등성**: `run_analysis_pipeline`은 commit SHA로 중복 체크 — 같은 SHA는 재분석 건너뜀. 단, push 이벤트 먼저 처리 후 PR 이벤트 도착 시(`pr_number=None` Analysis 존재) `_regate_pr_if_needed()`가 `pr_number`만 업데이트하고 `run_gate_check` 재실행 — 알림 재발송 없음.
- **PR action 필터링**: `pull_request` 이벤트 중 `opened`/`synchronize`/`reopened`만 처리, `closed`/`labeled` 등은 무시.
- **AI 점수 스케일링**: Claude는 commit 0-20, direction 0-20, test 0-10으로 반환 → calculator가 commit 0-15, direction 0-25, test 0-15로 스케일링. `round()` 사용으로 banker's rounding 적용.
- **commit_scamanager_files**: GitHub Contents API `PUT /repos/{owner}/{repo}/contents/{path}` 사용. 파일 이미 있으면 GET으로 sha 조회 후 body에 포함해야 200 성공 (sha 누락 시 422 에러).
- **다언어 AI 리뷰**: `language.py`가 50개 언어를 감지(확장자·shebang·파일명), `review_prompt.py`가 언어별 체크리스트를 토큰 예산(8000 토큰) 내에서 조립. 비-코드 파일만 변경 시 테스트 점수 면제(test_score=10 → 15/15).
- **Analyzer Registry**: `src/analyzer/pure/registry.py` 의 REGISTRY 전역 목록 + `register()` (동일 name 중복 등록 방지). `src/analyzer/io/static.py` 가 `import src.analyzer.io.tools.{python,semgrep,eslint,shellcheck,cppcheck,slither,rubocop,golangci_lint}` 로 각 Analyzer 모듈 로드 → 모듈 import 시점에 자동 `register()` 호출. Phase S.3-B 이후 `pure/` vs `io/` 분리 구조.
- **category 기반 점수 집계**: `AnalysisIssue.category`("code_quality"|"security") 기준으로 점수 계산. tool 이름 무관 — 새 정적분석 도구 추가 시 category만 올바르게 설정하면 점수에 자동 반영. `CQ_WARNING_CAP=25` 단일 cap (구 pylint 15 + flake8 10 통합).
- **review_guides 구조**: `get_guide(lang, "full"|"compact")` — Tier1 full ~500토큰, compact 1줄. N≤3 전체 full, N≤6 Tier1 full+나머지 compact, N>10 상위 5개 compact만.
- **AI 리뷰 JSON 파싱**: Claude가 JSON 앞에 설명 텍스트를 붙이는 경우 `re.search`로 코드 블록 내 JSON만 추출.
- **봇 PR `create_issue` 루프 방지**: `pr_head_ref`가 `_BOT_PR_PREFIXES` (`claude-fix/`, `bot/`, `renovate/`, `dependabot/`) 중 하나로 시작하면 `create_issue`를 건너뜀 — n8n 자동 생성 PR이 저점을 받을 때 Issue 재생성 → 무한 루프 방지.
- **봇 발신 / 자기 분석 루프 방지**: `src/webhook/providers/github.py::_loop_guard_check()`가 3-layer 체크 적용 — (1) Kill-switch `SCAMANAGER_SELF_ANALYSIS_DISABLED=1`, (2) `loop_guard.is_bot_sender()` + BOT_LOGIN_WHITELIST 비포함 → 즉시 차단, (3) skip marker (`[skip ci]`, `[skip-sca]`, `[ci skip]`) + `BotInteractionLimiter` **화이트리스트 봇 한정** 시간당 6회 상한 (PR #100 — `is_whitelisted_bot()` 분기, **사람 발신 / 비-화이트리스트 봇 / sender 누락은 limiter 미적용 = 무제한 통과**). `github-actions[bot]`, `dependabot[bot]`은 whitelist로 분석 진행. 새 자동화 봇 추가 시 `BOT_LOGIN_WHITELIST` 갱신 검토. 운영 runbook: `docs/runbooks/self-analysis.md`.
- **stage_metrics 필드 규약**: `issue_count` = 전체 이슈 합계 (`sum(len(r.issues))`), `file_count` = 분석 파일 수. 두 필드를 혼동하지 말 것 (2026-04-24 P1-1 정정).
- **커밋 메시지 추출**: `_extract_commit_message()`는 PR 이벤트 시 `title + "\n\n" + body`, Push 이벤트 시 `head_commit["message"]` 우선 사용.
- 🔴 **GitHub 페이로드의 None-able 키 정규화**: GitHub 가 `head_commit` / `pull_request` 키 값을 **`None` 으로 보낼 수 있다** (예: 브랜치 삭제 push, 일부 이벤트 종류). `data.get("head_commit", {}).get(...)` 체이닝은 default 가 적용되지 않아 NPE 발생 — 항상 `(data.get("head_commit") or {}).get(...)` 패턴으로 정규화. `_extract_commit_message`(pipeline.py)는 `if head:` 가드, `_loop_guard_check`(webhook/providers/github.py)는 `or {}` 패턴 사용. 신규 webhook 핸들러 추가 시 동일 규칙 적용. (PR #124 회귀 사고로 도입)
- **CLI Hook 인증/점수**: `GET /api/hook/verify`, `POST /api/hook/result`는 `hook_token` 파라미터로 인증(X-API-Key 불필요). pre-push 훅은 정적 분석 없이 AI 리뷰만 실행 → `calculate_score([], ai_review)` 호출 (code_quality=25, security=20 만점 적용).
- **분석 source 필드**: `pipeline.py`가 result JSON에 `"source": "pr"|"push"` 저장. 기존 레코드 대응으로 `result.get("source") or ("pr" if pr_number else "push")` fallback 파생.
- **GateDecision upsert**: `save_gate_decision()`은 동일 `analysis_id`로 이미 레코드가 있으면 UPDATE, 없으면 INSERT. 재시도·반자동 재승인 시 중복 INSERT가 없다.
- **Analyzer tools 자동 등록**: `tools/semgrep.py`, `tools/eslint.py`, `tools/shellcheck.py`, `tools/cppcheck.py`, `tools/slither.py`, `tools/rubocop.py`, `tools/golangci_lint.py`는 `analyze_file()`에서 해당 모듈을 import할 때 자동으로 `register()` 호출. 새 도구 추가 시 (1) `tools/` 아래 클래스 작성 + `register()` 호출, (2) `analyze_file()`에서 import, (3) SUPPORTED_LANGUAGES에 지원 언어 선언 세 단계 필수.
- **golangci-lint go.mod 자동생성**: `_GolangciLintAnalyzer.run()` 은 tmp_path 디렉토리에 `go.mod` 가 없으면 `_ensure_go_mod()` 로 최소 모듈 정의 (`module tempmod\ngo 1.21\n`) 를 자동 생성. 단일 `.go` 파일 분석 시 "no Go files" 오류 회피.
- **`_build_issue_body()` 시그니처**: `high_issues: list[dict]` 파라미터가 추가되어 있음 — 호출처(`create_low_score_issue`)에서 `_bandit_high_issues(result)`를 1회만 계산한 뒤 전달. 직접 호출 시 반드시 high_issues 인자 포함.
- **Railway Webhook 토큰 인증**: `POST /webhooks/railway/{token}` 엔드포인트는 DB에서 `railway_webhook_token == token` 조회 후 `config is None → 404` 처리. `railway_api_token`은 Fernet 암호화 저장 — `decrypt_token()`으로 백그라운드 핸들러에 전달.
- **5-way 동기화 Railway 확장**: `railway_deploy_alerts`가 ORM/RepoConfigData/API body/settings 폼/PRESETS 5-way 동기화 적용 대상. `railway_webhook_token`·`railway_api_token`은 `hook_token` 동일 패턴으로 ORM 직접 관리 (RepoConfigData 미포함).
- **RailwayDeployEvent nested 구조**: `src/railway_client/models.py`의 `RailwayDeployEvent`는 3-그룹 nested dataclass — `event.project.project_id`, `event.commit.commit_sha` 등 sub-dataclass 경로로 접근. 평면(`event.project_id`) 접근은 2026-04-22 이후 제거됨. 신규 필드 추가 시 `RailwayProjectInfo`(project_id/project_name/environment_name) 또는 `RailwayCommitInfo`(commit_sha/commit_message/repo_full_name)에 삽입. `parse_railway_payload` 외부 시그니처 불변.

### API / 알림 채널

- **keyword-only 강제 (`*`)**: 모든 `send_*` notifier 함수와 `run_gate_check()` 등은 `def fn(*, arg1, arg2)` 형태. 테스트에서 positional 호출 시 TypeError — 반드시 키워드 인자로 호출.
- **RepoConfig 필드명**: `approve_mode`(구 `gate_mode`), `approve_threshold`(구 `auto_approve_threshold`), `reject_threshold`(구 `auto_reject_threshold`) — 구 필드명 사용 시 AttributeError.
- **알림 채널 추가 체크리스트**: `RepoConfig` ORM → `RepoConfigData` dataclass → `RepoConfigUpdate` API body → UI 폼 4곳 반드시 동기화. 누락 시 REST API 업데이트 시 해당 필드가 NULL로 덮어써지는 버그 발생.
- **Webhook 서명**: `X-Hub-Signature-256` 헤더 없거나 서명 불일치 시 401 반환 — 로컬 테스트 시 서명 생성 필요. 빈 시크릿(`GITHUB_WEBHOOK_SECRET` 미설정)이면 즉시 401.
- **Webhook 서명 실패 일관성**: GitHub / Telegram webhook 모두 서명 불일치 시 `HTTPException(401)` 반환. 200 OK 반환 금지 — 공격자에게 성공 응답 노출 방지 (2026-04-24 P1-4 정정).
- **알림 독립성**: `_build_notify_tasks()` 디스패처, `asyncio.gather(return_exceptions=True)`로 실행 — 한 채널 실패해도 나머지 채널은 정상 전송. `repo_config` 로드 실패 시에도 Telegram은 global fallback으로 항상 발송.
- **PR Gate 3-옵션 독립**: `pr_review_comment`·`approve_mode`·`auto_merge+merge_threshold` 완전 독립. `post_pr_comment_from_result(result: dict, ...)` 사용 — `AiReviewResult` 객체 불필요. `run_gate_check` 시그니처: `(repo_name, pr_number, analysis_id, result, github_token, db, config: RepoConfigData | None = None)`.
- **build_analysis_result_dict**: `src/worker/pipeline.py` 모듈 레벨 함수. pipeline과 hook.py 두 곳에서 Analysis.result dict를 생성할 때 사용. `score`·`grade` 필드 포함 — gate engine이 이를 기반으로 결정.
- **GRADE 상수 단일 출처**: `src/constants.py`에 `GRADE_EMOJI`, `GRADE_COLOR_DISCORD`, `GRADE_COLOR_HTML`, `GRADE_COLOR_ANSI` 정의. 각 모듈에 로컬 정의 금지.
- **ChangedFile / github_api_headers 단일 출처**: `src/github_client/models.py`가 ChangedFile 정의 출처. `src/github_client/helpers.py`의 `github_api_headers(token)` 사용 — 새 GitHub API 호출 시 직접 dict를 만들지 말 것.
- **telegram_post_message**: `src/notifier/telegram.py`의 공용 헬퍼. `src/gate/telegram_gate.py`도 이 헬퍼 사용 — `httpx` 직접 import 금지.
- **get_repo_or_404**: `src/api/deps.py`의 `get_repo_or_404(repo_name, db)` 사용. 신규 API 엔드포인트에서 Repository 조회 시 동일 패턴 사용.
- **auto_merge GitHub 권한**: `merge_pr()`은 `repo` 스코프 또는 Fine-grained `pull_requests: write` 권한 필요 — 권한 부족 시 False 반환(파이프라인 미중단). Branch Protection Rules가 있으면 APPROVE 후에도 Merge 실패 가능.
- **http_client 싱글톤 원칙**: 신뢰 API (GitHub/Telegram/Railway) 호출은 `src/shared/http_client.py::get_http_client()` 를 통해 연결 풀 재사용. 외부 untrusted URL (Discord/Slack/custom_webhook/n8n) 은 `src/notifier/_http.py::build_safe_client()` 사용. `async with httpx.AsyncClient()` 매번 생성 금지 (2026-04-24 P1-3).
- **MergeAttempt 관측 (Phase F.1+F.2)**: `src/gate/engine.py::_run_auto_merge`(자동) 및 `src/webhook/providers/telegram.py::handle_gate_callback`(반자동) 양쪽에서 `merge_pr` 직후 `log_merge_attempt()`(`src/shared/merge_metrics.py`)로 모든 시도(성공·실패)를 DB에 기록. `failure_reason`은 `src/gate/merge_reasons.py`의 정규 태그(`branch_protection_blocked`, `unstable_ci`, `permission_denied` 등). 관측 실패는 notify 경로를 막지 않도록 nested try/except로 격리 — DB 오류 시 rollback 후 WARNING + None. **Phase F.3**: `engine.py::_run_auto_merge` 실패 시 `get_advice(reason)` + 조건부 `create_merge_failure_issue()` 호출 — `auto_merge_issue_on_failure` 필드(5-way sync 적용)로 Issue 생성 제어.
- **notifier 공통 헬퍼**: `src/notifier/_common.py`의 `format_ref()`, `get_all_issues()`, `get_issue_samples()`, `truncate_message()`, `truncate_issue_msg()`를 사용. 각 notifier 모듈에 이슈 수집 루프나 메시지 절단 로직 직접 작성 금지.
- **webhook secret TTL 캐시**: `get_webhook_secret(full_name)` 함수가 `_webhook_secret_cache` dict에 5분(WEBHOOK_SECRET_CACHE_TTL=300초) TTL로 per-repo 시크릿을 캐시. 리포 시크릿 변경 후 최대 5분간 구 시크릿으로 검증 — 인지하고 있을 것.
- **Telegram 콜백 도메인 분리**: `_make_callback_token(bot_token, scope, payload_id)`이 `scope ∈ {"gate","cmd"}`별 다른 HMAC 생성. 신규 명령 추가 시 `cmd:<verb>:<id>:<token>` 준수, 64-byte 한도 검증 (numeric id). `_gate_callback_token()`은 `_make_callback_token(..., "gate", analysis_id)` thin wrapper. `test_callback_data_within_64_bytes_all_commands` 단위 테스트 강제.
- **Cron 엔드포인트 인증**: `POST /api/internal/cron/*`는 `INTERNAL_CRON_API_KEY` 전용 (admin key와 분리). Railway `[[deploy.cronJobs]]` 트리거. `hmac.compare_digest` 타이밍 안전 비교. `INTERNAL_CRON_API_KEY` 미설정 시 503 반환.
- **Telegram chat_id 라우팅 우선순위**: cron 알림의 chat_id 결정은 `analytics_service.resolve_chat_id(repo, config)` 단일 헬퍼 — `RepoConfig.notify_chat_id` → `Repository.telegram_chat_id` → `settings.telegram_chat_id` → None(skip + WARNING).
- **CI-aware Auto Merge 재시도**: `mergeable_state=unstable`+CI running 또는 `unknown` 상태일 때 단일 실패가 아닌 `merge_retry_queue` 큐잉. `check_suite.completed` 웹훅 또는 1분 cron 으로 재시도. 트리거: `src/services/merge_retry_service.py::process_pending_retries`. 첫 지연 시 Telegram 1회, 최종 성공/실패 시 1회. 중간 재시도는 무음.
- **`merge_pr` SHA atomicity**: `merge_pr(..., expected_sha=...)` 는 `PUT /pulls/{n}/merge` 에 `sha` 파라미터를 포함해 force-push 된 코드의 의도치 않은 머지를 GitHub 측에서 차단. 신규 호출 시 항상 head SHA 전달.
- **Webhook 이벤트 구독 갱신**: `create_webhook` 이벤트 목록은 `["push","pull_request","issues","check_suite"]`. 기존 등록 리포는 settings 페이지의 "Webhook 재등록" 버튼으로 갱신 — 미갱신 시 자동 재시도 기능 미동작 (cron fallback 으로 5분 지연 동작).
- 🔴 **외부 SDK timeout/max_retries 명시 의무 (Phase H PR-1A/1B-1)**: 새 외부 SDK (Anthropic/aiosmtplib/유사) 클라이언트 인스턴스화 시 `timeout` 명시 (60s 권장, `HTTP_CLIENT_TIMEOUT` 정렬), `max_retries` 명시 (SDK 기본값과 동일 값이라도 명시). SDK 업그레이드로 default 변경 시 silent regression 차단. 회귀 가드 테스트 동반.
- 🔴 **5xx 자동 재시도 — 신뢰 API 한정 (Phase H PR-1B-2/2B)**: GitHub/Telegram/Anthropic/Railway 등 신뢰 API 의 일시 5xx + transient network error 는 자동 재시도 (exponential backoff, max 3회). Telegram 429 는 `retry_after` 파싱 + cap 30s. **외부 untrusted webhook (Discord/Slack/n8n/custom_webhook) 는 재시도 금지** — idempotency 보장 불가, 중복 발송 부작용. 재시도 helper 통합 검토 — 현재 `src/shared/retry_helper.py` **미존재**, 채널별 (Telegram L80~ / GitHub graphql `_GRAPHQL_*` / Anthropic SDK `max_retries`) 인라인 구현. 신규 채널 추가 시 해당 채널 모듈 안에 동일 패턴 (exponential backoff + transient 분류) 직접 구현 또는 신규 helper 모듈 신설 결정 필요.
- 🔴 **PyGithub 등 sync I/O 는 `asyncio.to_thread` wrap 의무 (Phase H PR-3A)**: async 컨텍스트(BackgroundTask, lifespan 등) 내부에서 sync HTTP 클라이언트 (PyGithub, requests) 호출 시 반드시 `asyncio.to_thread(fn, ...)` 로 wrap. 직접 호출 시 이벤트 루프 블록 → 다른 webhook/cron 정체 (월 5-10건 Sentry "sync hang" 사고 차단 — PR-3A 결과).
- 🔴 **race-recovery 시그널 컨벤션 (Phase H PR-2A)**: 파이프라인 내 race recovery 분기는 `result_dict is None` 을 시그널로 사용. 호출자는 `if result_dict is None: skip notify` 로 명시적 처리 — 중복 알림 + silent KeyError 동시 차단.

### 보안

- 🔴 **hook_token 비교**: `!=` 연산자는 타이밍 공격에 취약. `hmac.compare_digest(config.hook_token or "", token)` 사용 필수.
- 🔴 **Telegram 게이트 콜백 HMAC 인증 (Phase H PR-5C 후 정정)**: 콜백 데이터 형식 `gate:{decision}:{id}:{token}` — token 은 `hmac(bot_token, f"gate:{analysis_id}", sha256).hexdigest()[:32]` (128-bit). 발신측 (`telegram_gate._make_callback_token(scope="gate", id)`) 과 수신측 (`webhook/providers/telegram._parse_gate_callback`) 모두 동일 msg 형식 (`f"gate:{id}"`) 사용 의무 — 한쪽만 수정 시 모든 semi-auto 콜백 401 거부 (PR-5C 직전 functional bug 사례). 신규 HMAC 토큰 도입 시 발신/수신 동일 msg 형식 + scope prefix 단위 테스트 강제.
- 🔴 **`/health` 응답 내부 상태 미노출 (Phase H PR-5B)**: liveness probe 전용 — `active_db` / DB 연결 정보 등 내부 상태 추가 금지. `tests/unit/test_main.py::test_health_returns_status_ok` 가 회귀 차단. failover 모니터링은 logger 로그 (Sentry/Railway) 경유. 인증된 운영 대시보드 필요 시 별도 엔드포인트 (`INTERNAL_CRON_API_KEY` 기반) 신설.
- **GitHub Access Token 암호화**: `src/crypto.py`의 `encrypt_token()`/`decrypt_token()` — `TOKEN_ENCRYPTION_KEY` 미설정 시 평문 저장. `User.plaintext_token` property가 DB 읽기 시 자동 복호화. `user.github_access_token` 직접 사용 금지 — `user.plaintext_token` 사용.
- **SESSION_SECRET 강도**: `validate_session_secret` validator (`src/config.py`) 가 32자 미만 또는 기본값이면 WARNING 출력. 프로덕션에서는 32자 이상 랜덤 문자열 필수.
- **TOKEN_ENCRYPTION_KEY prod 감지**: lifespan startup 에서 `APP_BASE_URL` 이 https:// 로 시작하고 키가 비어있으면 WARNING 배너 출력. dev 환경(http 또는 빈 URL)에서는 침묵. 키 생성 명령은 로그 메시지에 포함 (2026-04-24 P1-5).
- **Jinja2 autoescape**: `Jinja2Templates`는 `.html` 파일에 대해 autoescape=True(기본값). 템플릿 변수는 자동 이스케이프됨 — `| safe` 필터 사용 금지. notifier HTML 출력엔 `html.escape()` 직접 적용 필수.
- **OAuth CSRF state**: Authlib `authorize_access_token()`이 session state 검증을 내부 처리. `/auth/github`를 거치지 않은 직접 콜백(`/auth/callback`) 접근은 에러(500)로 차단됨 — 정상 동작.
- **로그 인젝션 방어 (`sanitize_for_log`)**: `src/shared/log_safety.py`의 `sanitize_for_log(value, max_len=200)` 헬퍼로 user-controlled 입력을 logger 에 전달하기 전 반드시 경유. CR/LF/TAB/NUL 제거 + 길이 제한. `%r` 포맷만으로는 SonarCloud `pythonsecurity:S5145` taint analysis 를 통과 못 함 — 명시적 함수 호출 필요. 예: `logger.info("...%s...", sanitize_for_log(body.repo))`.
- **URL Path 방어적 인코딩 (`_repo_path`)**: `src/github_client/repos.py::_repo_path(full_name)` 으로 `urllib.parse.quote(safe='/')` 적용. GitHub API URL 에 `repo_full_name`/path 변수 삽입 시 반드시 경유 — SonarCloud `pythonsecurity:S7044` 경고 회피 + 실질적 path injection 차단.
- **FastAPI Annotated 패턴 강제**: `Depends(...)`/`Header(...)` 는 `Annotated[Type, Depends(require_login)]` / `Annotated[str | None, Header()] = None` 형식으로 작성. `python:S8410` 규칙. `default 있는 param 뒤에 Annotated (default 없음)` 오면 SyntaxError — 함수 시그니처에서 `Annotated` 를 앞으로 이동 필요.
- **SonarCloud FP suppress 규약**: `sonar-project.properties` 의 `sonar.issue.ignore.multicriteria` 에 규칙별 예외 추가. 개별 라인 예외는 `# NOSONAR <ruleKey> — 이유` 주석. 커스텀 sanitizer 를 SonarCloud taint analysis 가 인식 못 할 때 NOSONAR 주석 + 이유 명시가 표준.

### UI / 템플릿

- **Telegram HTML 파싱**: `parse_mode: "HTML"` 사용 — 모든 동적 콘텐츠에 `html.escape()` 적용 필수. `_build_message()`가 4096자 초과 시 자동 절단.
- **analysis_detail 템플릿 context**: `current_user`를 반드시 포함해야 함 — 누락 시 nav 사용자명·로그아웃 버튼 미표시. `analysis.result or {}` 패턴은 None → `{}` 변환으로 `{% if r %}` falsy 평가 → 모든 AI 섹션 숨김 버그 — `{% else %}` 분기로 fallback 처리 필수.
- **settings.html 구조 규약**: 의도 기반 6 카드 구성 — ① 빠른 설정(프리셋 3종 diff 미리보기) / ② PR 들어왔을 때(pr_review_comment·approve_mode·approve/reject_threshold·auto_merge·merge_threshold) / ③ 이벤트 후 피드백(commit_comment·create_issue·railway_deploy_alerts, 트리거별 소제목 + toggle-switch 통일) / ④ 알림 채널(masked-field 6종) / ⑤ 시스템 & 토큰(CLI Hook + Webhook 재등록 + Railway API 토큰 + Railway Webhook URL) / ⑥ 위험 구역(리포 삭제, 기본 접힘). Progressive Disclosure 기존 JS 헬퍼 5종(`setApproveMode`·`toggleMergeThreshold`·`applyPreset`·`_setPair`·`_showPresetToast`) 시그니처 불변 + 신규 헬퍼 4종(`onPresetToggle`·`renderPresetDiff`·`flashPresetChanges`·`toggleMergeIssueOption`). 프리셋 P1 = 펼침 diff 미리보기, P2 = 적용 하이라이트(@keyframes preset-flash 2.5s). 메인 `<form id="settingsForm">` + Railway API 토큰은 form 바깥에서 `form="settingsForm"` 속성으로 메인 폼에 포함. 알림 채널 URL은 프리셋이 건드리지 않음. 저장 오류 시 `?save_error=1` 쿼리 감지 → 고급설정 `<details open>` 자동 토글. 백엔드 필드명(pr_review_comment, approve_mode 등 14개) 및 PRESETS 9개 필드 구성 불변 원칙 — 5-way 동기화 체크리스트(ORM → dataclass → API body → 폼 → PRESETS) 적용 대상.
- **overview 등급 산출**: `calculate_grade(avg_score)` 사용 (`src/scorer/calculator.py`). 최신 분석 grade가 아닌 평균 점수 기반 — 평균 점수 컬럼과 등급 컬럼이 항상 동일 기준. `latest_id_subq`/`latest_map` 배치 조회는 제거됨.
- **analysis_detail trend_data**: `trend_data`·`prev_id`·`next_id`를 template context에 추가 전달. `trend_data`는 같은 리포 최근 30건 `{id, score, label}` 리스트. `trend_data|length > 1`일 때만 차트 렌더링. `analysis_detail.html`은 Chart.js CDN을 직접 로드.
- **repo_detail 차트 동기화**: `buildChart(data)` 함수는 `data` 인자가 있으면 `_chartData`에 캐시, 없으면 캐시된 데이터 재사용. `applyFilters()` 호출마다 차트를 필터 결과와 동기화. `themechange` 이벤트는 `buildChart()` (인자 없음)으로 색상만 재빌드.
- **리포 추가 Webhook URL**: `_webhook_base_url(request)` 헬퍼가 `APP_BASE_URL` 설정 시 HTTPS URL 강제. Railway 배포 시 반드시 `APP_BASE_URL` 설정 — 미설정 시 `http://`로 등록되어 Webhook 전달 실패.
- **기존 Webhook 등록 리포**: `user_id = NULL` 리포는 모든 로그인 사용자에게 표시됨. `/repos/add`로 동일 리포 재등록 시 `user_id=NULL`이면 현재 사용자 소유 이전, 이미 소유자 있으면 에러.
- **insights 차트 재사용**: `insights_me.html`은 `analysis_detail.html`과 동일한 Chart.js vendoring 패턴 사용 (UI 감사 Step C 이후 `/static/vendor/chart.umd.min.js` 로컬 호스팅). `leaderboard_opt_in`은 PRESETS 9개 필드에 포함하지 않음 — 사용자가 명시 옵트인해야 하는 선택적 기능.
- 🔴 **환각(phantom) 토큰 alias 패턴 (UI 감사 Step A + cleanup PR #169)**: 컴포넌트 CSS 가 정의되지 않은 토큰 (`var(--bg-hover)`, `var(--card-bg)`, `var(--text)`, `var(--accent-blue)`, `var(--c-warning)` 등) 을 참조하면 브라우저는 fallback 없으면 invalid → 다크 테마 시각 깨짐 (예: filter-bar 배경 투명, 피드백 버튼 hover 안 보임). 발견 시 사용처 치환 대신 `base.html` 의 `:root` 블록에 alias (`--bg-hover: var(--table-row-hover)` 등) 흡수 — consumer 코드 변경 0 으로 4-테마 일괄 해결. 신규 토큰은 항상 `var(--*)` 경유, `#hex` 직접 사용 금지. 새 환각 토큰 발견 시 `:root` alias 블록에 추가가 1순위.
- 🔴 **WCAG 2.5.5 모바일 클릭 영역 ≥44px 의무 (UI 감사 Step A/B/E)**: 모바일 인터랙티브 요소 (`.btn`, `.btn--sm`, `.nav-link`, `.nav-hamburger`, `.gate-mode-btn`, `.filter-btn`, `.page-btn`, `.chip-label`, `.day-selector a`, `.settings-link` 등) 는 `@media (max-width: 768px)` 분기에 `min-height: 44px` (또는 sm: 40px) + `box-sizing: border-box` 적용 필수. 신규 인터랙티브 컴포넌트 추가 시 동일 규칙 자동 적용. iOS Safari focus zoom 회피 위해 input/select font-size 모바일 분기 ≥16px 필수.
- 🔴 **safe-area-inset 적용 의무 (UI 감사 Step A)**: notch (iPhone 12+) / 홈 인디케이터 디바이스 호환 위해 sticky/fixed 요소 (nav, .save-bar, .nav-links.open 모바일 메뉴) 는 `padding-{top,bottom,left,right}: max(*, env(safe-area-inset-*))` 또는 `calc(* + env(safe-area-inset-*, 0px))` 패턴. `<meta name="viewport">` 의 `viewport-fit=cover` (base.html L7) 와 페어. 새 sticky 요소 추가 시 동일 패턴 적용.
- **Chart.js vendoring + StaticFiles mount (UI 감사 Step C — PR #166)**: 외부 CDN 차단 (사내망/방화벽/오프라인) 환경 호환 위해 `src/static/vendor/chart.umd.min.js` (4.4.0 UMD min, 204KB) 로컬 호스팅. `src/main.py` 가 `_STATIC_DIR` 존재 시 `app.mount("/static", StaticFiles(directory=...), name="static")` 조건부 mount. 사용 페이지 (`repo_detail`/`analysis_detail`/`insights_me`) 는 `<script src="/static/vendor/chart.umd.min.js">` 직접 참조. 신규 정적 자원은 `src/static/vendor/` 하위 배치 → 자동 노출. 디렉토리 추가 시 CLAUDE.md `src/` 트리 동기화 의무.
- **claude-dark 테마 차트 색 동기화 (UI 감사 Step C)**: Chart.js JS 는 CSS 변수 직접 못 읽으므로 `getComputedStyle(document.documentElement).getPropertyValue('--grade-a')` 등 동적 추출 → Chart 옵션에 주입. 테마 전환 시 `document.addEventListener('themechange', buildChart)` 로 chart 재빌드 (chart.destroy() → new Chart()). `repo_detail.html`/`analysis_detail.html`/`insights_me.html` 동일 패턴. 새 차트 추가 시 동일 패턴 의무.
- **색 의미(semantic) 토큰 통일 (UI 감사 Step D — PR #167 + cleanup #169)**: 시각적 의미는 항상 `--success` (A등급/성공/머지/conn-dot ON) / `--warning` (C등급/경고/대기) / `--danger` (F등급/실패/거부) 3종 토큰 사용. `#10b981`, `#ef4444`, `#f59e0b` 등 hex 직접 사용 금지. 등급 색 (`--grade-a/b/c/d/f`) 과 시맨틱 색 혼용 금지. claude-dark 테마는 모든 시맨틱/등급 색을 sage/sand/muted-red/terracotta 톤으로 자동 alias — 새 의미 토큰 추가 시 4-테마 모두 정의 + claude-dark alias 의무.
- **claude-dark 테마 토큰 매트릭스 (cleanup PR #169)**: settings 페이지가 사용하는 토큰 8종 (`--grad-gate/merge/notify/hook`, `--title-gradient`, `--btn-gate-active-*`, `--save-btn-*`, `--hint-*`, `--hook-btn-*`) 은 claude-dark 에도 정의 의무 — 미정의 시 invalid var() → 카드 헤더 흰색/투명 등 시각 깨짐. 새 페이지가 다른 토큰 도입 시 4-테마 모두에 정의 추가 의무.

### 배포

- **NIXPACKS npm run build 자동 추가**: npm이 환경에 존재하면 `nixpacks.toml [phases.build] cmds` 명시 여부와 무관하게 `npm run build`를 자동 추가. 억제 유일 수단: `railway.toml`의 `buildCommand` (최상위 오버라이드). eslint 등 npm 전역 설치가 필요하면 buildCommand에 직접 작성.
- **slither + solc 빌드타임 준비**: `slither-analyzer` (pip) 설치만으로는 부족 — solc 컴파일러 바이너리가 있어야 실제 `.sol` 분석 가능. `railway.toml`의 `buildCommand`에 `solc-select install 0.8.20 && solc-select use 0.8.20` 체인으로 빌드 이미지에 solc 0.8.20 사전 포함 → 런타임 첫 분석에서 `STATIC_ANALYSIS_TIMEOUT=30` 내 완료 보장. pragma 가 다른 버전이면 slither 가 자동 fallback 다운로드 시도(네트워크 있으면 성공, 없으면 `success=false` → `[]` graceful degradation). solc 버전 변경 필요 시 `railway.toml` buildCommand 의 두 번 solc 버전 문자열만 교체.
- **NIXPACKS nixPkgs 오버라이드 함정**: `nixpacks.toml`에 `nixPkgs = ["nodejs"]` 등을 명시하면 Python provider의 nix 자동 설치(python3 + pip 포함)를 **완전히 교체**한다. Python+Node.js 공존 패턴: `nixPkgs` 사용 금지, `aptPkgs = ["nodejs", "npm"]`으로 Node.js 설치, pip install은 Python provider 자동 처리.
- **APP_BASE_URL**: Railway 리버스 프록시 환경 필수 설정. **OAuth redirect_uri**와 **GitHub Webhook 등록 URL** 양쪽에 HTTPS URL 강제 적용 — 미설정 시 `http://`로 등록.
- **Railway 빌드 검증 필수**: `git push` 성공 ≠ Railway 빌드 성공. `railway.toml`, `nixpacks.toml`, `requirements.txt` 변경 후 Railway 대시보드 빌드 로그 직접 확인 후 완료 선언.
- **빌드 실패는 로그 우선, 추측 수정 금지**: Railway/CI 빌드 실패 보고를 받으면 즉각 수정 PR 을 작성하지 말 것. 전체 빌드 로그(실패 구간 위아래 30줄)를 먼저 받아 근본 원인을 특정한 뒤 수정. 2026-04-23 rubocop/prism 사건에서 "추측 기반 1차 수정 → 2차 재실패 → 로그 분석 후 3차 성공" 패턴으로 1시간 낭비 실적 있음. 상세: [회고](docs/reports/2026-04-23-railway-rubocop-prism-retrospective.md).
- **gem/npm transitive 의존성 핀**: Ruby gem 또는 npm 패키지의 **직접 의존성만 버전 고정해도 transitive 의존성은 시간에 따라 바뀐다**. rubocop 1.57.2 는 pure Ruby 지만 transitive `rubocop-ast` 가 2024년 이후 prism 네이티브 확장을 필수로 요구하게 변경됨 → Railway 빌드 실패. 해결책은 `gem install rubocop-ast -v 1.36.2` (prism-free 마지막 버전) 를 rubocop 설치 **이전에** 명시 핀. 새 Ruby 도구 추가 시 동일 패턴 주의.
- **requirements.txt 분리**: `requirements.txt`(프로덕션 — Railway 자동 감지)와 `requirements-dev.txt`(개발 — `-r requirements.txt` 포함 + pytest/playwright) 분리. `pytest`, `playwright`는 `requirements-dev.txt`에만 유지.
- **SMTP_PORT 빈 문자열**: Railway 환경에서 `SMTP_PORT=""`로 설정 시 pydantic ValidationError 크래시. Railway Variables에서 SMTP_PORT 값을 삭제하거나 숫자로 설정.
- **postgres:// URL**: Railway PostgreSQL이 `postgres://`로 제공하는 경우 `config.py`에서 `postgresql://`로 자동 변환.

## 현재 상태

최신 수치는 [docs/STATE.md](docs/STATE.md) 참조 — 단위 테스트 1980개 | 통합 72개 | E2E 53개 | pylint 10.00 | 커버리지 95% | SonarCloud QG OK · Security A · Reliability A · Maintainability A · Tier1 정적분석 10종 · Observability (Sentry + Claude metrics + stage timing + MergeAttempt) · AI 점수 피드백 루프 · Settings Minimal Mode · Onboarding 3단계 튜토리얼 · 5-렌즈 감사 95+ 통과 · Phase F Quick Win + F.1/F.3 완료 · Phase G 완료 (P1-5건 수정) · Phase 9 자기 분석 루프 방지 완료 · Phase 10 Telegram 확장 완료 (cron + /stats·/connect 명령) · Phase 11 팀/멀티 리포 인사이트 완료 (author_trend + leaderboard + /insights 대시보드) · 툴링 안전장치 (testpaths + ORM-마이그레이션 완전성 검사 67개) · Phase 12 CI-aware Auto Merge 재시도 완료 (merge_retry_queue + check_suite 웹훅 + 1분 cron) · Settings UI/UX 리디자인 완료 (수신/발신 웹훅 분리 + 온보딩 배너) → Phase 2A Progressive 재설계 완료 (PR #152, #153) — `<details>` 아코디언 제거 + `.adv-only` 평탄화 + W2 분리 5 카드 + 단순 모드 5 핵심 필드 + 사용자 신호 기반 첫 진입 (`_detect_initial_mode`) + ●○ 점 상태 표시 8종 → **UI 감사 사이클 12 PR (#156, #159, #160, #163~#168) + 5-에이전트 정합성 cleanup 5 PR (#169, #170, #172, #173 + 본 sync PR) 완료** — Settings P0 핫픽스 (5건) + 7-페이지 4-에이전트 감사 (P0 32+P1 18+P2 15=65건) → Step A~E 시리즈로 root cause 처리 (환각 토큰 alias / safe-area-inset / WCAG 2.5.5 / Chart.js vendoring `src/static/vendor/` + StaticFiles `/static` mount / claude-dark 차트 색 동적 read / 색 의미 토큰 통일 `--warning` 신규 / nav 비로그인 가드 / chip a11y) → cleanup 4 PR 로 코드 결함 (claude-dark 토큰 8종 + 환각 alias 2종 + Step B/D 누락) + 문서 동기화 + P1 polish (chart-wrap clamp + .btn:disabled 확장 + tooltip 토큰화) + 회귀 가드 12건 · Loop Guard Layer 3-b 화이트리스트 봇 한정 (PR #100 — `is_whitelisted_bot()` 헬퍼 + 사람 발신 무제한 통과) · Tier 3 PR-A 완료 (PR #103) — `enablePullRequestAutoMerge` GraphQL mutation + REST 폴백 · Phase 4 Critical 테스트 갭 5 PR 완료 (PR-T1~T5, +197 tests) — analyzer/tools, ai_review_errors, scorer_edges, engine_guards, pipeline_helpers, merge_retry_helpers, pr_a_scenarios, e2e_pipeline_scenarios · **Phase H+I 15 PR 완료 + 회고/문서 동기화 1 PR = 16 PR 머지 (12-에이전트 감사 Critical 10건 100% 처리) — timeout/race-recovery/Telegram 429/gate parallel/PyGithub async/joinedload opt-in/parity guard/HMAC parity (이전 모든 semi-auto 콜백 401 거부 functional bug 해소)/composite indexes/cascade ; 외부 의존성 추가 0**
