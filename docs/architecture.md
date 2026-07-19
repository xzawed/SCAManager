# SCAManager 아키텍처

> CLAUDE.md 분리본 (사이클 85 정리, 2026-05-06). 신규 파일 추가 시 이 문서 갱신 의무 (CLAUDE.md "동기화 체크리스트" 페어).

## src/ 디렉토리 구조

```
src/
├── main.py                     # FastAPI 앱, lifespan(DB 마이그레이션 + http_client), 전체 라우터 등록 + CachedStaticFiles `/static` mount (Cache-Control `no-cache` ETag 재검증 — 무버전 자산 stale 방지) + 미들웨어 LIFO 등록 (add_middleware 순서 = SecurityHeaders → LimitBodySize → Locale → RLSSession → Session → CORS; 마지막 CORS = outermost·request 먼저 처리 → 요청 흐름 Session → RLS → route)
├── static/
│   ├── vendor/chart.umd.min.js  # Chart.js 4.4.0 UMD min vendoring
│   ├── vendor/htmx.min.js       # HTMX 1.9.12 hx-boost 네비게이션 (전체 페이지 리로드 제거)
│   ├── manifest.json            # PWA manifest (Cycle 81 PR-A)
│   ├── icons/icon-{192,512}.svg # PWA maskable icons
│   ├── css/{tokens,themes}.css  # Foundation 디자인 토큰 + 4-테마 정의 (Cycle 93 Step 1, base.html 외부화)
│   ├── css/main.css             # Tailwind v4 소스 — @import tokens/themes + layout 유틸리티 (#376)
│   ├── css/dist/tailwind.css    # Tailwind v4 빌드 출력 — Railway buildCommand 자동 생성, git 미포함 (.gitkeep 마커만 커밋)
│   ├── css/illustrations.css    # 일러스트 배치 CSS — .illustration/--hero/--empty/--tutorial + 모바일 반응형 (#375)
│   ├── css/admin.css            # 관리자 페이지 공통 스타일 — .admin-* 글래스모피즘 컴포넌트 (admin_rls_audit, admin_tenants 공유)
│   ├── css/repo_insights.css    # 리포별 인사이트 페이지 전용 스타일 — .ri-* 클래스 (CPD 분리)
│   │                            # Repo insights page scoped styles (.ri-* classes, CPD prevention)
│   ├── css/components.css        # 공통 컴포넌트 스타일 (.aurora/.orb 등 — base.html 정본, 품질감사 2026-06-25 트리 등재)
│   ├── css/pages.css             # 페이지별 스타일 (base.html/landing.html 로드)
│   ├── js/{effects,tweaks}.js    # base.html 로드 인터랙션 스크립트 (#605 핸들러 누적 가드 대상)
│   ├── mockup-polar.html        # 대시보드 KPI 레이아웃 목업 — SonarCloud sonar.exclusions 등재 (#399)
│   └── illustrations/           # DALL-E 3 생성 일러스트 4장 commit (#375 Step 2-B: dashboard_empty/overview_onboarding/add_repo_hero/filter_empty; login_hero.png 사이클 118 #584 삭제)
├── scripts/                     # src/scripts/ — DALL-E 3 일러스트 생성 도구 (production import X; 최상위 scripts/ 와 별도)
│   ├── illustration_prompts.py  # 5장 isometric prompt 정의 (login_hero/dashboard_empty/overview_onboarding/add_repo_hero/filter_empty)
│   └── generate_illustrations.py # OpenAI DALL-E 3 CLI (--all/--name/--dry-run)
├── config.py                    # pydantic-settings 환경변수 관리, postgres:// URL 자동 변환 + effective_migration_url(= MIGRATION_DATABASE_URL or DATABASE_URL — alembic 마이그레이션 owner credential 게이트, RLS Phase 4 "두 번째 벽")
├── constants.py                 # 전역 상수 단일 출처 — 점수배점/감점가중치/AI기본값/등급/알림한도/HTTP타임아웃/캐시TTL
├── crypto.py                    # encrypt_token()/decrypt_token() — TOKEN_ENCRYPTION_KEY
├── database.py                  # SQLAlchemy engine, Base, FailoverSessionFactory + RLS event listener + WorkerSessionLocal (background/시스템 컨텍스트 BYPASSRLS 라우팅, RLS Phase 2~4)
├── logging_config.py            # 🔴 앱 로깅 단일 설정 지점 — configure_logging()(stdout·INFO·멱등) + is_configured() + _RedactSecretsFilter(시크릿 마스킹). 2026-07-19 P0 2건: (1) `alembic/env.py` 의 `fileConfig` 가 lifespan 내 마이그레이션에서 앱 로깅을 파괴(root→WARN·`uvicorn.access` disable) → `is_configured()` 가드로 봉인(#1102) (2) httpx INFO 요청 URL 로깅이 Telegram 봇 토큰을 평문 기록 → httpx WARNING + 리댁션 필터 2계층(#1104). 가드 = `tests/unit/test_logging_config.py` · `tests/unit/migrations/test_alembic_env_logging_guard.py`
├── scheduler.py                 # 🔴 인앱 주기 작업 스케줄러 (lifespan 기동·운영 전용·stdlib only) — JOBS 5종(retry-pending-merges 1분 · sweep-orphans 10분 · trend 03:00 UTC · retention-sweep 20:00 UTC · weekly-reports 월 00:00 UTC)이 `cron_service` 함수를 직접 호출. 2026-07-19 P0 대체: `railway.toml [[deploy.cronJobs]]` 는 Railway 스키마에 없는 키라 무시돼 5종이 한 번도 실행되지 않았음. `SCHEDULER_DISABLED` kill-switch. 배선 단언 = `tests/unit/test_scheduler.py`
├── shared/
│   ├── http_client.py           # httpx.AsyncClient lifespan 싱글톤 (내부 신뢰 API)
│   ├── log_safety.py            # sanitize_for_log() — 로그 인젝션 방지
│   ├── claude_metrics.py        # Claude API 비용/latency 계측
│   ├── stage_metrics.py         # stage_timer context manager
│   ├── merge_metrics.py         # parse_reason_tag + log_merge_attempt
│   ├── anthropic_caching.py     # build_cached_system_param() — Anthropic prompt cache 5분 ephemeral
│   ├── rls_context.py           # contextvars 기반 request scope user_id (Phase 3 postlude)
│   ├── feature_kill_switch.py   # is_disabled(feature) helper (Cycle 78 NEW-P0-2)
│   ├── alembic_dialect.py       # is_postgresql(bind_or_conn) (Cycle 82 PR 1 — 사용처 12)
│   ├── lang_names.py            # LANG_NAMES dict — locale 코드 → Claude 프롬프트 언어명 (단일 출처)
│   ├── ssrf.py                  # is_dangerous_ip() — SSRF IP 분류 단일 출처 (_http.py 발신 가드 + settings.py 폼 검증)
│   ├── secure_compare.py        # secure_str_compare() — hmac.compare_digest 타이밍 안전 비교 (hook/webhook HMAC 인증 단일출처)
│   └── openai_metrics.py        # OpenAI 토큰/비용 계측 + aclose_openai_client (2nd-LLM 검증자, claude_metrics 대칭)
├── middleware/
│   ├── rls_session.py           # RLSSessionMiddleware (ASGI, BaseHTTPMiddleware 우회)
│   ├── rate_limiter.py          # slowapi limiter — RATE_LIMIT_API(60/min)/RATE_LIMIT_HEAVY(10/min) DoS 방어
│   └── locale.py                # LocaleMiddleware — 5단계 locale 감지 (Cookie > Accept-Language q-weight > User > settings > fallback)
├── i18n/                        # 다국어 지원 인프라 (Babel 미사용 JSON dict 자체 구현)
│   ├── loader.py                # TranslationLoader + LRU cache + 영문 fallback
│   ├── filters.py               # Jinja2 i18n / i18n_args 필터
│   └── translations/            # en.json / ko.json / ja.json (15 namespace × 3 언어)
├── services/
│   ├── analytics_service.py     # 집계 단일 출처 — weekly_summary, moving_average, resolve_chat_id
│   ├── cron_service.py          # 주기 실행 — run_weekly_reports, run_trend_check, sweep_analysis_attempts(소실 탐지, 0045), run_retention_sweep(만료캐시+종결큐 GC)
│   ├── dashboard_service.py     # /dashboard 10 공개 함수 (dashboard_kpi + dashboard_trend + frequent_issues_v2 + auto_merge_kpi + merge_failure_distribution + feedback_status + repo_insight_cards + insight_narrative + dashboard_security + dashboard_usage) + RLS 격리 헬퍼 2건 + N+1 배치 헬퍼 2건 (_fetch_analyses_for_window / _group_analyses_by_repo) — insight_narrative 는 `INSIGHT_DISABLED` kill-switch 전역 차단 대상
│   ├── repo_insight_service.py  # 리포별 집계 7 함수 (repo_kpi/repo_score_trend/recurring_issues/problem_files/ai_suggestions/category_breakdown/insight_narrative) + compute_score_kpi 공유 헬퍼 (dashboard_service CPD 제거) — insight_narrative 는 `INSIGHT_DISABLED` kill-switch 전역 차단 대상(dashboard_service 와 동일)
│   │                            # Per-repo aggregation 7 functions (repo_score_trend added cycle 99) + compute_score_kpi shared helper
│   ├── issue_registration_service.py  # make_ai/static_issue_key + register_issue(IntegrityError TOCTOU 처리) + get_analysis_issue_status + get_repo_issue_summary (TTL 300초 캐시)
│   ├── merge_retry_service.py   # process_pending_retries 워커 (CI-aware)
│   ├── security_scan_service.py # Code/Secret Scanning 폴링 + audit log + GHAS graceful degradation
│   ├── saas_service.py          # tenant_inventory + rls_audit_matrix + rls_coverage_summary(db) FORCE 실측 (0041, RLS Phase 3)
│   ├── operations_service.py    # operations_kpi 7 카드 — admin 운영 모니터링
│   └── cost_metrics_service.py  # user_cost_summary — Anthropic 비용 집계 진입점, claude_api_cost_repo 위임 (C1 Phase 2, dashboard_kpi monthly_cost 소비)
├── auth/
│   ├── session.py               # get_current_user() + require_login + require_admin (3-layer SaaS 검증)
│   └── github.py                # /login (301→/auth/github, 하위호환), /auth/github, /auth/callback, /auth/logout
├── models/                      # 13 ORM 모델 — repository (0039: user_id→users.id FK ondelete=SET NULL), analysis (0038: repo_id FK ondelete=CASCADE; 0032 토큰 부분 인덱스 ORM 선언), analysis_feedback, repo_config (0036: disabled_tools JSON 컬럼; 0042: ai_review_enabled Boolean 컬럼 — 리포별 AI 코드리뷰 kill-switch, 기본 True, 비용 제어), gate_decision (0034: analysis_id UNIQUE constraint), merge_attempt, merge_retry, security_alert_log, insight_narrative_cache (0031: repo_id FK + 부분유일 인덱스 ORM 선언; 0033: last_error_at/error_count/last_error_type), user (0040: github_id 인덱스명 정합 rename), issue_registration (0035: repo_id+issue_key UniqueConstraint + CASCADE FK; 0037: RLS policy — repo_id→repositories.user_id 1-hop, PG 전용), claude_api_call (0043: Anthropic API 호출 비용/토큰 메트릭 — repo_id/user_id 귀속 CASCADE FK, RLS policy PG 전용), analysis_attempt (0045: 진행 중 분석 흔적 — 비싼 작업 전 INSERT/정상 종료 시 DELETE, 남은 오래된 행 = 파이프라인 소실 신호. repo_id CASCADE FK + (repo_id, commit_sha) UNIQUE, RLS policy PG 전용)
├── webhook/
│   ├── _helpers.py              # get_webhook_secret() + cache (TTL 300s)
│   ├── validator.py             # HMAC-SHA256 서명 검증
│   ├── loop_guard.py            # is_bot_sender, is_whitelisted_bot, has_skip_marker, BotInteractionLimiter
│   ├── router.py                # aggregator
│   └── providers/               # github.py + telegram.py + railway.py
├── github_client/               # diff / issues (create_issue, get_issue_state, close_issue) / repos / checks (5분 TTL) / graphql (Tier 3 PR-A) / helpers (github_api_headers, ChangedFile) / models (ChangedFile 정의)
├── railway_client/              # models (RailwayDeployEvent 3-그룹 nested dataclass) / logs (fetch_deployment_logs) / webhook (parse_railway_payload)
├── analyzer/
│   ├── pure/                    # registry / language / review_prompt / review_guides (tier1~3 + generic, 49 언어)
│   ├── io/                      # static.py (Registry 위임) + ai_review.py (Claude API)
│   │   └── tools/               # 23 분석기 모듈 (Tier1 25종 — python 모듈이 pylint/flake8/bandit 3종 번들): python·semgrep·eslint·shellcheck·cppcheck·slither·rubocop·golangci_lint·hadolint·ktlint·tflint·tsc·sqlfluff·yamllint·phpstan·swiftlint·stylelint·htmlhint·buf_lint·dart_analyze·psscriptanalyzer·dotnet_format·clippy (STATE.md 정적분석 도구 단일출처)
│   └── configs/                 # eslint.config.json 등 외부 도구 설정
├── scorer/calculator.py         # calculate_score(ai_review), ScoreResult, _grade
├── config_manager/manager.py    # get_repo_config(), upsert_repo_config(), RepoConfigData
├── gate/
│   ├── actions/                 # Gate 실행 액션 패키지 — engine 이 GATE_ACTIONS Registry 로 디스패치
│   │   ├── __init__.py          # GateAction(ABC) + GateContext(frozen) + GATE_ACTIONS + register()
│   │   ├── approve.py           # ApproveAction — auto/semi-auto approve·reject (GitHub Review / Telegram)
│   │   ├── auto_merge.py        # AutoMergeAction — score>=merge_threshold 시 squash merge (engine 위임)
│   │   └── review_comment.py    # ReviewCommentAction — PR 에 AI 리뷰 상세 댓글
│   ├── _common.py               # score_from_result()
│   ├── engine.py                # run_gate_check() — 3-옵션 독립 처리
│   ├── github_review.py         # post_github_review(), merge_pr() (REST 폴백)
│   ├── native_automerge.py      # enable_or_fallback() — GraphQL 우선 + REST 폴백
│   ├── merge_reasons.py         # 정규 태그 상수 (branch_protection_blocked, unstable_ci 등)
│   ├── telegram_gate.py         # send_gate_request() — 인라인 키보드
│   ├── merge_failure_advisor.py # get_advice(reason, language) — i18n (사이클 149)
│   ├── retry_policy.py          # 순수 함수 — should_retry, compute_next_retry_at, is_expired
│   ├── _merge_attempt_states.py # MergeAttempt.state lifecycle 정규 상수
│   └── merge_verifier.py        # 2nd-LLM 머지 검증자 (cross-vendor) — is_in_verification_band/should_verify/diff_exceeds_cap/build_verifier_prompt/interpret_verdict/verify_merge_safety/verifier_blocks_merge (자동·반자동 단일출처 가드 #859 P1-1, diff cap fail-closed #863)
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
│   ├── repos.py / stats.py / hook.py (_resolve_hook_locale — repo owner 언어 해소, 사이클 151) / users.py
│   ├── repo_report.py           # Repo별 분석 레포트 JSON API (list + detail)
│   ├── internal_cron.py         # POST /api/internal/cron/{weekly,trend,scan-security,retry-pending-merges,sweep-orphans,retention-sweep}
│   ├── issue_registration.py    # POST /api/issues/register + GET /api/issues/status + GET /api/issues/repo-summary (소유권 검증 포함)
│   └── admin.py                 # GET /api/admin/{tenants,rls-audit,operations}
├── ui/
│   ├── _helpers.py              # get_accessible_repo, webhook_base_url, delete_repo_cascade, templates
│   ├── router.py                # aggregator
│   └── routes/                  # overview / dashboard (mode 5종) / add_repo / settings / actions / detail / admin / repo_insights
├── templates/                   # base, landing, overview, repo_detail, analysis_detail, settings, dashboard, admin_*, repo_insights, add_repo
├── mcp/
│   ├── __init__.py              # MCP tool 선언 패키지
│   └── repo_report_tools.py     # list_repo_reports / get_repo_report tool 스키마
├── cli/                         # python -m src.cli review (git_diff + formatter)
├── verifier/                    # 2nd-LLM 머지 검증자 (cross-vendor 거버넌스) — openai_client.py (SDK 우선 + httpx fallback)
├── repositories/                # DB 접근 계층 13종 — repository_repo (`find_by_full_name` + `find_all_by_user` shared+owned repos + Phase H `find_by_full_name_with_owner`), issue_registration_repo (find_by_key/create/list_by_analysis/list_by_repo/update_state), claude_api_cost_repo (record + user_cost_summary — Anthropic 비용 영속화/집계 단일 출처, 0043), analysis_attempt_repo (begin_attempt/finish_attempt/find_orphaned/purge_orphaned — 파이프라인 소실 탐지 단일 출처, 0045; sweep cron 이 find_orphaned→표면화→purge)
└── worker/pipeline.py           # run_analysis_pipeline, build_analysis_result_dict
```

## scripts/ 디렉토리 구조 (최상위 — src/ 외부)

> **주의**: `src/scripts/` (DALL-E 3 생성 도구 2건) 와 별도. 아래는 최상위 `scripts/` 로컬 도구 목록 (production import X).
> **Note**: Separate from `src/scripts/` (2 DALL-E generation scripts). Below are top-level `scripts/` local tools (not imported in production).

```
scripts/
├── perf_measure.py              # 페이지 성능 측정 독립 스크립트 — 로컬 SQLite 서버 자동 시작·종료 + 운영 Railway TTFB, Markdown 리포트 (사이클 106 #500)
│                                # Standalone page perf script — local SQLite server auto-start/stop + prod Railway TTFB, Markdown report
├── parse_bandit.py              # bandit 보안 결과 파싱 — JSON 출력 → 이슈 목록 변환
│                                # Parse bandit security results — JSON output → issue list conversion
├── parse_coverage.py            # 커버리지 결과 파싱 — coverage.py XML → 요약 통계
│                                # Parse coverage results — coverage.py XML → summary stats
├── benchmark_static_analysis.py # 정적 분석 벤치마크 — 도구별 실행 시간 측정
│                                # Static analysis benchmark — measure per-tool execution time
├── backfill_repository_user_id.py # repository user_id 백필 — 마이그레이션 보조 스크립트
│                                # Backfill repository user_id — migration helper script
├── check_memory_refs.py         # 메모리 참조 유효성 검사 — CLAUDE.md/active.md/history.md 슬러그 ↔ 실제 파일 비교 (사이클 101 #469)
│                                # Memory reference validator — slug ↔ actual file cross-check
├── check_docs_sync.py           # docs 수치 정합 — STATE.md 종합/추적셀 헤더 ↔ README/README.ko 배지 drift 차단 (repo-integrity pre-commit, #967/#968)
│                                # docs count-sync — STATE totals/header ↔ README badges; blocks drift at pre-commit
├── check_toc_anchors.py         # cycle-history TOC 앵커 정합 — 목차 `](#anchor)` 링크 ↔ 실제 헤딩 slug (GitHub slug 모사, #958)
│                                # cycle-history TOC anchor checker — TOC links ↔ heading slugs
├── check_env_vars_sync.py       # env-vars 싱크 — src/config.py Settings 필드 ↔ env-vars.md 등재 정합 (사이클 82/119 반복 적발 차단)
│                                # env-vars sync — Settings fields ↔ env-vars.md entries (AST)
├── check_config_5way_sync.py    # config 싱크 — RepoConfig ORM ↔ Data ↔ Update 3-레이어 필드 정합 (NULL 덮어쓰기 차단, api.md 5-way 규칙)
│                                # config sync — 3-layer RepoConfig field parity via AST
├── check_bilingual_comments.py  # 이중언어 주석 점검 — staged 신규 주석 한글-only 탐지 (CLAUDE.md 한+영 규칙 보조, pre-commit only)
│                                # bilingual-comment checker — flag Korean-only added comment lines
├── check_dual_import.py         # 신규 이중 import PR 가드 — diff ADDED `from X import` + 기존 `import X` 공존 검출 (self-inflicted CodeQL py/import-and-import-from 봉인, 회고 C2, ci.yml lint-changed-tests)
│                                # new dual-import guard — diff-scoped `from X import` + coexisting `import X` (retro C2, CI)
├── capture_design_screenshots.py # 디자인 스크린샷 자동 캡처 — 12페이지 × 4테마 (Claude Design 브리프 패키지용, 사이클 131)
│                                # Auto-capture design screenshots — 12 pages × 4 themes (Claude Design brief)
├── extract_design_tokens.py     # 디자인 토큰 추출 — tokens.css/themes.css → Claude Design 입력 JSON
│                                # Extract design tokens — tokens.css/themes.css → structured JSON
└── README.md                    # 사용자 실행 가이드 + 비용 안내
```

## e2e/ 디렉토리 구조

```
e2e/
├── conftest.py                    # live_server / page / seeded_page / browser_instance / seeded_analysis fixtures (session-scope)
├── pytest.ini                     # E2E 전용 pytest 설정 (asyncio_mode 미설정 — src/ 단위 테스트 충돌 방지)
├── _perf_helpers.py               # LCP_INIT_JS + measure_one/page 공통 헬퍼 — test_performance.py + scripts/perf_measure.py 공유 (사이클 111 #536)
├── test_performance.py            # 12개 @pytest.mark.perf 성능 테스트 — TTFB/FCP/LCP/DCL/Load (3회 avg/min/max)
├── test_dashboard.py              # /dashboard 페이지 E2E — 4 모드(overview/insight/usage/security) 전환 흐름
├── test_dashboard_insight.py      # /dashboard?mode=insight E2E — AI narrative 카드 렌더링
├── test_i18n_visual_regression.py # 3-언어 × 4-페이지 i18n 시각 회귀 테스트 (Cycle 84 PR-16)
├── test_navigation.py             # hx-boost 네비게이션 + 뒤로가기 흐름 E2E
├── test_overview_score.py         # 개요 score count-up "0/100" 고착 회귀 — IO 미발동/이중 init 안전망·실제 네비 (#936/#939, 2026-06-18~19)
├── test_repos_mode.py             # /repos/add + /repos/{name} 기능 흐름 E2E (Cycle 94)
├── test_settings.py               # /repos/{name}/settings 저장 흐름 E2E
├── test_theme.py                  # 4-테마 토글 E2E (desktop)
└── test_theme_mobile_guards.py    # 모바일 테마 토글 + 44px 터치 영역 E2E
```

## 핵심 데이터 흐름

```
GitHub Push/PR
  → POST /webhooks/github (HMAC 서명 검증)
  → PR action 필터링 (opened/synchronize/reopened만 처리)
  → BackgroundTasks 비동기 등록
  → run_analysis_pipeline()
      → Repository DB 등록 (API 호출 전, 실패해도 목록 노출 보장)
      → 🔴 analysis_attempt_repo.begin_attempt() — **비싼 작업 전** 소실 탐지 흔적 기록 (0045)
        파이프라인은 내구 큐 없는 in-process BackgroundTask 이고 GitHub 에 200 이 이미 반환된 상태다.
        여기부터 Analysis 저장까지의 수 분 창에서 SIGTERM(재배포)/OOM/크래시가 나면 분석이 조용히
        증발하므로, 이 행이 유일한 증거가 된다. dedup 게이트 아님(중복 차단은 find_by_sha 단독).
      → _extract_commit_message() — PR: title+body, Push: head_commit 우선
      → get_pr_files / get_push_files (모든 변경 파일 수집)
      → asyncio.gather() 병렬 실행:
          ├─ analyze_file() × N  (.py만 정적 분석, 테스트 파일은 bandit 제외)
          └─ review_code()       (Claude AI — 49개 언어 체크리스트 + 토큰 예산 관리)
              🔴 비용 제어 kill-switch — 전역 `AI_REVIEW_DISABLED` OR 리포별 `RepoConfig.ai_review_enabled=False` 시
              API 호출 없이 disabled 반환(정적분석은 계속 진행). 상세: `docs/runbooks/cost-controls.md`
              → log_claude_api_call() → claude_api_cost_repo.record() — `claude_api_calls` 테이블(0043, RLS) 영속화
                cost_metrics_service.user_cost_summary 가 대시보드 monthly_cost KPI 로 재소비 (C1 Phase 1-4)
      → calculate_score(ai_review) (코드품질25 + 보안20 + 커밋15 + AI방향성25 + 테스트15)
      → DB 저장 (Analysis 레코드) — **파이프라인 최초의 내구 기록**
      → run_gate_check() [PR 이벤트만] — 3-옵션 완전 독립 처리
          [pr_review_comment=on] → post_pr_comment_from_result()
          [approve_mode=auto]    → score ≥ approve_threshold → GitHub APPROVE
                                   score < reject_threshold → GitHub REQUEST_CHANGES
          [approve_mode=semi]    → Telegram 인라인 키보드 → POST /api/webhook/telegram 콜백
          [auto_merge=on, score ≥ merge_threshold]
              → (경계밴드 merge_threshold~+MERGE_VERIFIER_BAND & OPENAI_API_KEY 설정 시) 2nd-LLM 검증자(GPT cross-vendor)
                  → unsafe / 조작 의심 / 검증자 오류 시 자동머지 차단 + PR 코멘트 (fail-closed)
              → enable_or_fallback()
              ├─ enable_pull_request_auto_merge GraphQL mutation (우선)
              ├─ ENABLE_DISABLED_IN_REPO / ENABLE_PERMISSION_DENIED → REST merge_pr 폴백
              └─ ENABLE_API_ERROR (분류 외) → REST merge_pr 폴백
          [auto_merge=on, mergeable_state=unstable/unknown] → merge_retry_queue 큐잉
              → check_suite.completed 웹훅 즉각 트리거 OR 1분 cron fallback
              → process_pending_retries() → 최대 30회, 24h
      → build_notification_tasks() — RepoConfig 기반 채널 디스패처
      → asyncio.gather(return_exceptions=True):
          ├─ send_analysis_result()        (Telegram)
          ├─ send_discord_notification()
          ├─ send_slack_notification()
          ├─ send_webhook_notification()
          ├─ send_email_notification()
          └─ notify_n8n()

Telegram 반자동 콜백:
  → POST /api/webhook/telegram (본문 robustness: malformed/비-dict → 400, #13)
  → gate:{decision}:{id}:{token} 파싱 (HMAC 인증) + 리포 소유권 authz (#1)
  → gate_decision_repo.claim_decision() — 결정 원자적 claim (first-writer-wins, 리플레이/더블클릭 패자 skip, #11)
  → post_github_review() (GitHub PR 리뷰 게시)
  → decision=approve & auto_merge=on & not static_analysis_incomplete & not ai_review_failed
      → engine._run_auto_merge() 위임 — 자동 경로와 완전 대칭 (사이클 164 Q1):
        retry 큐잉 · SHA 원자성 가드 · CI 재판별 · terminal/deferred 알림 · 관측(log_merge_attempt) 공유

대시보드:
  → GET /                              (리포 현황)
  → GET /dashboard?days=&mode={overview|insight|security|usage|repos}
  → GET /dashboard?mode=repos&repo=owner/repo  (repos 모드 — 전체 Repo 포트폴리오 요약 + 개별 Repo 상세 레포트)
  → GET /insights, /insights/me        (301 redirect → /dashboard)
  → GET /repos/{repo}                  (점수 차트 + 이력)
  → GET /repos/{repo}/insights         (리포별 KPI + 반복 이슈 + 문제 파일 + AI 제안 + 카테고리 분석)
  → GET /repos/{repo}/analyses/{id}    (분석 상세)
  → GET /api/repos, /api/repos/{repo}/stats
  → GET /api/repos/report?days=N           (전체 Repo 포트폴리오 요약 — JSON API)
  → GET /api/repos/{name:path}/report?days=N  (개별 Repo 상세 레포트 — JSON API)

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
