# SCAManager 아키텍처

> CLAUDE.md 분리본 (사이클 85 정리, 2026-05-06). 신규 파일 추가 시 이 문서 갱신 의무 (CLAUDE.md "동기화 체크리스트" 페어).

## src/ 디렉토리 구조

```
src/
├── main.py                     # FastAPI 앱, lifespan(DB 마이그레이션 + http_client), 전체 라우터 등록 + CachedStaticFiles `/static` mount (Cache-Control immutable 1년) + 미들웨어 LIFO 등록 (SecurityHeaders → RLSSessionMiddleware → SessionMiddleware → LocaleMiddleware)
├── static/
│   ├── vendor/chart.umd.min.js  # Chart.js 4.4.0 UMD min vendoring
│   ├── vendor/htmx.min.js       # HTMX 1.9.12 hx-boost 네비게이션 (전체 페이지 리로드 제거)
│   ├── manifest.json            # PWA manifest (Cycle 81 PR-A)
│   ├── icons/icon-{192,512}.svg # PWA maskable icons
│   ├── css/{tokens,themes}.css  # Foundation 디자인 토큰 + 4-테마 정의 (Cycle 93 Step 1, base.html 외부화)
│   ├── css/main.css             # Tailwind v4 소스 — @import tokens/themes + layout 유틸리티 (#376)
│   ├── css/dist/tailwind.css    # Tailwind v4 빌드 출력 (npm run build → Railway buildCommand, #376)
│   ├── css/illustrations.css    # 일러스트 배치 CSS — .illustration/--hero/--empty/--tutorial + 모바일 반응형 (#375)
│   ├── css/admin.css            # 관리자 페이지 공통 스타일 — .admin-* 글래스모피즘 컴포넌트 (admin_rls_audit, admin_tenants 공유)
│   ├── css/repo_insights.css    # 리포별 인사이트 페이지 전용 스타일 — .ri-* 클래스 (CPD 분리)
│   │                            # Repo insights page scoped styles (.ri-* classes, CPD prevention)
│   ├── mockup-polar.html        # 대시보드 KPI 레이아웃 목업 — SonarCloud sonar.exclusions 등재 (#399)
│   └── illustrations/           # DALL-E 3 생성 일러스트 5장 commit (#375 Step 2-B: login_hero/dashboard_empty/overview_onboarding/add_repo_hero/filter_empty)
├── scripts/                     # 로컬 도구 (production import X) — Cycle 93 Step 2
│   ├── illustration_prompts.py  # 5장 isometric prompt 정의 (login_hero/dashboard_empty/overview_onboarding/add_repo_hero/filter_empty)
│   ├── generate_illustrations.py # OpenAI DALL-E 3 CLI (--all/--name/--dry-run)
│   └── README.md                # 사용자 실행 가이드 + 비용 안내
├── config.py                    # pydantic-settings 환경변수 관리, postgres:// URL 자동 변환
├── constants.py                 # 전역 상수 단일 출처 — 점수배점/감점가중치/AI기본값/등급/알림한도/HTTP타임아웃/캐시TTL
├── crypto.py                    # encrypt_token()/decrypt_token() — TOKEN_ENCRYPTION_KEY
├── database.py                  # SQLAlchemy engine, Base, FailoverSessionFactory + RLS event listener
├── shared/
│   ├── http_client.py           # httpx.AsyncClient lifespan 싱글톤 (내부 신뢰 API)
│   ├── log_safety.py            # sanitize_for_log() — 로그 인젝션 방지
│   ├── claude_metrics.py        # Claude API 비용/latency 계측
│   ├── stage_metrics.py         # stage_timer context manager
│   ├── merge_metrics.py         # parse_reason_tag + log_merge_attempt
│   ├── anthropic_caching.py     # build_cached_system_param() — Anthropic prompt cache 5분 ephemeral
│   ├── rls_context.py           # contextvars 기반 request scope user_id (Phase 3 postlude)
│   ├── feature_kill_switch.py   # is_disabled(feature) helper (Cycle 78 NEW-P0-2)
│   └── alembic_dialect.py       # is_postgresql(bind_or_conn) (Cycle 82 PR 1 — 사용처 12)
├── middleware/
│   ├── rls_session.py           # RLSSessionMiddleware (ASGI, BaseHTTPMiddleware 우회)
│   └── locale.py                # LocaleMiddleware — 5단계 locale 감지 (Cookie > Accept-Language q-weight > User > settings > fallback)
├── i18n/                        # 다국어 지원 인프라 (Babel 미사용 JSON dict 자체 구현)
│   ├── loader.py                # TranslationLoader + LRU cache + 영문 fallback
│   ├── filters.py               # Jinja2 i18n / i18n_args 필터
│   └── translations/            # en.json / ko.json / ja.json (8 namespace × 3 언어)
├── services/
│   ├── analytics_service.py     # 집계 단일 출처 — weekly_summary, moving_average, resolve_chat_id
│   ├── cron_service.py          # 주기 실행 — run_weekly_reports, run_trend_check
│   ├── dashboard_service.py     # /dashboard 9 공개 함수 (KPI 4 + trend + frequent_issues + auto_merge_kpi + feedback_status + insight_narrative + dashboard_security + dashboard_usage + repo_insight_cards) + RLS 격리 헬퍼 2건 + N+1 배치 헬퍼 2건 (_fetch_analyses_for_window / _group_analyses_by_repo)
│   ├── repo_insight_service.py  # 리포별 집계 6 함수 (repo_kpi/recurring_issues/problem_files/ai_suggestions/category_breakdown/insight_narrative) + compute_score_kpi 공유 헬퍼 (dashboard_service CPD 제거)
│   │                            # Per-repo aggregation 6 functions + compute_score_kpi shared helper
│   ├── merge_retry_service.py   # process_pending_retries 워커 (CI-aware)
│   ├── security_scan_service.py # Code/Secret Scanning 폴링 + audit log + GHAS graceful degradation
│   ├── saas_service.py          # tenant_inventory + rls_audit_matrix (Cycle 79 PR 3a)
│   └── operations_service.py    # operations_kpi 7 카드 — admin 운영 모니터링
├── auth/
│   ├── session.py               # get_current_user() + require_login + require_admin (3-layer SaaS 검증)
│   └── github.py                # /login, /auth/github, /auth/callback, /auth/logout
├── models/                      # 10 ORM 모델 — repository, analysis, analysis_feedback, repo_config, gate_decision, merge_attempt, merge_retry, security_alert_log, insight_narrative_cache (0031: repo_id FK), user
├── webhook/
│   ├── _helpers.py              # get_webhook_secret() + cache (TTL 300s)
│   ├── validator.py             # HMAC-SHA256 서명 검증
│   ├── loop_guard.py            # is_bot_sender, is_whitelisted_bot, has_skip_marker, BotInteractionLimiter
│   ├── router.py                # aggregator
│   └── providers/               # github.py + telegram.py + railway.py
├── github_client/               # diff / issues / repos / checks (5분 TTL) / graphql (Tier 3 PR-A)
├── railway_client/              # 3-그룹 nested dataclass + parse_railway_payload + fetch_deployment_logs
├── analyzer/
│   ├── pure/                    # registry / language / review_prompt / review_guides (tier1~3 + generic, 50 언어)
│   ├── io/                      # static.py (Registry 위임) + ai_review.py (Claude API)
│   │   └── tools/               # 8 분석기 — python (pylint/flake8/bandit) + semgrep + eslint + shellcheck + cppcheck + slither + rubocop + golangci_lint
│   └── configs/                 # eslint.config.json 등 외부 도구 설정
├── scorer/calculator.py         # calculate_score(ai_review), ScoreResult, _grade
├── config_manager/manager.py    # get_repo_config(), upsert_repo_config(), RepoConfigData
├── gate/
│   ├── _common.py               # score_from_result()
│   ├── engine.py                # run_gate_check() — 3-옵션 독립 처리
│   ├── github_review.py         # post_github_review(), merge_pr() (REST 폴백)
│   ├── native_automerge.py      # enable_or_fallback() — GraphQL 우선 + REST 폴백
│   ├── merge_reasons.py         # 정규 태그 상수 (branch_protection_blocked, unstable_ci 등)
│   ├── telegram_gate.py         # send_gate_request() — 인라인 키보드
│   ├── merge_failure_advisor.py # get_advice(reason)
│   ├── retry_policy.py          # 순수 함수 — should_retry, compute_next_retry_at, is_expired
│   └── _merge_attempt_states.py # MergeAttempt.state lifecycle 정규 상수
├── notifier/                    # `__init__.py` 가 자동 로드 → REGISTRY 등록
│   ├── _common.py               # format_ref, get_all_issues, truncate_message
│   ├── _http.py                 # build_safe_client() — SSRF 방어
│   ├── _language.py             # resolve_notification_language() — 3-layer fallback (사이클 84 i18n)
│   ├── registry.py              # NotifyContext + Notifier Protocol + REGISTRY
│   ├── telegram.py / telegram_commands.py  # /stats, /settings, /connect OTP
│   ├── discord.py / slack.py / webhook.py / email.py / n8n.py  # 외부 채널
│   ├── github_comment.py / github_commit_comment.py / github_issue.py  # GitHub 채널
│   ├── railway_issue.py         # Railway 빌드 실패 Issue
│   └── merge_failure_issue.py   # auto-merge 실패 Issue (Phase F.3, dedup 24h)
├── api/
│   ├── auth.py                  # require_api_key Depends
│   ├── deps.py                  # get_repo_or_404
│   ├── repos.py / stats.py / hook.py / users.py
│   ├── internal_cron.py         # POST /api/internal/cron/{weekly,trend,scan-security,retry-pending-merges}
│   └── admin.py                 # GET /api/admin/{tenants,rls-audit,operations}
├── ui/
│   ├── _helpers.py              # get_accessible_repo, webhook_base_url, delete_repo_cascade, templates
│   ├── router.py                # aggregator
│   └── routes/                  # overview / dashboard (mode 4종) / add_repo / settings / actions / detail / admin / repo_insights
├── templates/                   # base, landing, login, overview, repo_detail, analysis_detail, settings, dashboard, admin_*, repo_insights, add_repo
├── cli/                         # python -m src.cli review (git_diff + formatter)
├── repositories/                # DB 접근 계층 10종
└── worker/pipeline.py           # run_analysis_pipeline, build_analysis_result_dict
```

## 핵심 데이터 흐름

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
      → calculate_score(ai_review) (코드품질25 + 보안20 + 커밋15 + AI방향성25 + 테스트15)
      → DB 저장 (Analysis 레코드)
      → run_gate_check() [PR 이벤트만] — 3-옵션 완전 독립 처리
          [pr_review_comment=on] → post_pr_comment_from_result()
          [approve_mode=auto]    → score ≥ approve_threshold → GitHub APPROVE
                                   score < reject_threshold → GitHub REQUEST_CHANGES
          [approve_mode=semi]    → Telegram 인라인 키보드 → POST /api/webhook/telegram 콜백
          [auto_merge=on, score ≥ merge_threshold] → native_enable_or_fallback()
              ├─ enable_pull_request_auto_merge GraphQL mutation (우선)
              ├─ ENABLE_DISABLED_IN_REPO / ENABLE_PERMISSION_DENIED → REST merge_pr 폴백
              └─ ENABLE_API_ERROR (분류 외) → REST merge_pr 폴백
          [auto_merge=on, mergeable_state=unstable/unknown] → merge_retry_queue 큐잉
              → check_suite.completed 웹훅 즉각 트리거 OR 1분 cron fallback
              → process_pending_retries() → 최대 30회, 24h
      → _build_notify_tasks() — RepoConfig 기반 채널 디스패처
      → asyncio.gather(return_exceptions=True):
          ├─ send_analysis_result()        (Telegram)
          ├─ send_discord_notification()
          ├─ send_slack_notification()
          ├─ send_webhook_notification()
          ├─ send_email_notification()
          └─ notify_n8n()

Telegram 반자동 콜백:
  → POST /api/webhook/telegram
  → gate:{decision}:{id}:{token} 파싱 (HMAC 인증)
  → post_github_review() + GateDecision DB 저장
  → auto_merge=on, score ≥ merge_threshold → native_enable_or_fallback()

대시보드:
  → GET /                              (리포 현황)
  → GET /dashboard?days=&mode={overview|insight|security|usage}
  → GET /insights, /insights/me        (301 redirect → /dashboard)
  → GET /repos/{repo}                  (점수 차트 + 이력)
  → GET /repos/{repo}/insights         (리포별 KPI + 반복 이슈 + 문제 파일 + AI 제안 + 카테고리 분석)
  → GET /repos/{repo}/analyses/{id}    (분석 상세)
  → GET /api/repos, /api/repos/{repo}/stats

CLI Hook (로컬 pre-push 자동 코드리뷰):
  Repo 등록 시 (POST /repos/add):
    → hook_token = secrets.token_hex(32) → RepoConfig 저장
    → GitHub Contents API로 .scamanager/config.json + install-hook.sh 커밋
  git push 시 (.git/hooks/pre-push):
    → GET /api/hook/verify?repo=&token= (미등록 시 silent skip)
    → git diff → claude -p "프롬프트+diff" → 터미널 출력
    → POST /api/hook/result → Analysis DB 저장
    → exit 0 (push 항상 진행)
```

## 신규 파일 추가 시 갱신 체크리스트

| 위치 | 확인 사항 |
|------|----------|
| 본 파일 src/ 트리 | 신규 파일 한 줄 항목(경로 + 짧은 역할) 추가 |
| `src/templates/` 한 줄 | 신규 템플릿 파일명 목록에 추가 |
| `src/repositories/` 한 줄 | 신규 repo 파일 "N종" 카운트 + 목록 갱신 |
| `src/services/` 한 줄 | 신규 service 함수 목록 갱신 |
| 본 파일 핵심 데이터 흐름 | 신규 경로가 흐름도에 포함되어야 하면 추가 |
| `docs/reference/env-vars.md` | 신규 환경변수 추가 시 적정 섹션 등재 의무 |

**전례** (역사 자산): Phase 11에서 6개 파일 추가 후 CLAUDE.md에 5개 누락 → 3-에이전트 감사에서 발견 (PR #73). 2026-05-01 UI 감사 cleanup PR-D1 — `_merge_attempt_states.py` + `static/vendor/chart.umd.min.js` 트리 누락 → 5-에이전트 정합성 감사 발견. 2026-05-05 사이클 78~82 5+1 cross-verify — 사이클 79/80/82 신규 환경변수 4건 `env-vars.md` 미등재 → 6차 cross-verify 발견.
