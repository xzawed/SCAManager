# SCAManager 프로젝트 상태

> 이 파일이 단일 진실 소스(Single Source of Truth)다. Phase 완료·주요 변경 시 여기를 먼저 갱신한다.

## 현재 수치 (2026-05-18 기준 — **사이클 103**: auto-merge 재시도 안정성 개선 (#479) — cron fallback + has_hooks retriable + unknown ci_status retriable): 130+ PR #188~#479 — 누적 정책 본문 19건 + 메모리 19건. 전체 2968 수집 (2964 passed, 4 skipped, 단위 2814 + 통합 154) / E2E 99 / pylint **10.00/10**

| 지표 | 값 | 비고 |
|------|-----|------|
| 전체 테스트 | **2968개 수집** | `pytest tests/` — 단위 2814 + 통합 154 = **2964 passed, 4 skipped** (4 skip = test_settings_mobile.py Windows cp949 인코딩 오류 제외). 추적 이력: 사이클 73~75 +67 + 사이클 78~82 +114 (2122→2236) + 사이클 84 i18n 18 PR +473 누적 + **사이클 85 Sentry 완전 제거 -40** + **#375 일러스트 회귀 가드 +13** + **#397 UI 리디자인 +26** (form/mobile/sweep) + **사이클 96 #415 pylint +0** + **사이클 97 #423 +4** (CachedStaticFiles 2 + recurring_count 회귀가드 2) + **#428 랜딩 페이지 +2** (test_overview_landing.py) + **사이클 98 #434 +3** (test_htmx_vendor.py) + **사이클 99 #441~#443 +22** (repo_report API 9 + 통합 3 + repository_repo 4 + dashboard repos 5 + mcp 5) + **PR #453 CI수정** + **PR #454 gate/engine 에러경로 +8** + **PR #455/457 auth보안 +5** + **PR #459 보안심층 +8** (Telegram HTML injection 4 + 세션 변조 4) + **사이클 101 #460~#464 +3** (test_main TELEGRAM_WEBHOOK_SECRET 3 + test_calculator 1 + test_semgrep 2 — dead assert fix·main 경고). |
| 통합 테스트 | **154개** | tests/integration/ — 사이클 81 영역 🅑 모바일 Phase 1 MVP +34 + **사이클 84 i18n PR-18 smoke +11** + **PR #400 repo insights +22** + **사이클 99 #441 +3** (repo_report_api auth·list·404) + **사이클 100~101 누적** (test_retry_concurrency_postgres assertion 강화). 기존 test_settings_mobile.py 일부 Windows cp949 인코딩 오류 제외. **= 154 passed** |
| E2E 테스트 | **99개** | `make test-e2e` (Chromium Playwright) — Phase 3 PR 6 +7 + **사이클 84 i18n PR-16 +14** (3 언어 × 4 페이지 — login/overview/dashboard/settings + Cookie fallback + locale switch). 사이클 94 #372: test_save_success ordering 트랩 차단 (`_reset_repo_config()` 헬퍼) + test_two_column 보류 (`@pytest.mark.skip`). **= 99 collected**. ⚠️ e2e ↔ tests/integration 동시 실행 금지 — `e2e/pytest.ini` 의도적 asyncio_mode 미설정, 분리 실행 default (`make test-e2e` vs CI command `pytest tests/`) |
| SonarCloud Quality Gate | **OK** | #399 머지 후 복원 — CPD 14%→<3%, mockup 제외, _NONE_LABEL 상수화 |
| SonarCloud Security Rating | **A** | Vuln 0, Hotspots 0 |
| SonarCloud Reliability Rating | **A** | Bugs 0 |
| SonarCloud Maintainability Rating | **A** | Code Smells 58 (-20 from 78) |
| SonarCloud BLOCKER / CRITICAL | **0 / 0** | Phase Q.7 완료 — 5건 Cognitive Complexity 전부 해소 |
| pylint | **10.00/10** | `python -m pylint src/` — #415 잔여 21건 전체 해소 (C0415 17 lazy import inline disable + C0301 1 + R0913/R0917 3 + W0718/W0613 2 + E0401 1). **10.00 달성** |
| 커버리지 | **95%** | `make test-cov` — 신규 파일 100% (analytics_service, api/insights, ui/routes/insights) |
| bandit HIGH | **0개** | bandit 1.9.4 (Python 3.14 대응) |
| flake8 | **0건** | `flake8 src/` |
| 지원 언어 (AI 리뷰) | **50개** | language.py — Tier1/2/3 가이드 |
| 지원 언어 (정적분석) | **37개+** | Semgrep 22 + ESLint 2 + ShellCheck 1 + cppcheck 1 + slither 1 + rubocop 1 + golangci-lint 1 + Python 3 도구 |
| Tier1 정적분석 도구 | **10종** | pylint·flake8·bandit·semgrep·eslint·shellcheck·cppcheck·slither·**rubocop**·**golangci-lint** |
| pytest-asyncio | **1.3.0** | Python 3.14 DeprecationWarning 제거 완료 |
| CodeQL | **✅ pass** | `.github/workflows/codeql.yml` — 주 1회 실행. 본 README 배지 (L15) 와 페어 |

## 주요 파일 역할 (빠른 참조)

| 파일 | 역할 |
|------|------|
| `src/constants.py` | 전역 상수 단일 출처 — 점수배점·감점·AI기본값·등급·알림한도·TTL·타임아웃 |
| `src/analyzer/pure/registry.py` | Analyzer Protocol + REGISTRY + register() + AnalyzeContext + AnalysisIssue + Category/Severity StrEnum |
| `src/analyzer/io/tools/*.py` | 개별 분석기 — 모듈 로드 시 자동 register() 호출 (Phase S.3-B 이후 `pure/` vs `io/` 분리) |
| `src/notifier/_common.py` | notifier 공통 헬퍼 — format_ref, get_all_issues, truncate_message |
| `src/notifier/_http.py` | HTTP_CLIENT_TIMEOUT 적용 httpx 클라이언트 빌더 |
| `src/webhook/_helpers.py` | `get_webhook_secret()` + `_webhook_secret_cache` per-repo TTL 캐시(5분) |
| `src/webhook/loop_guard.py` | 자기 분석 루프 방지 3-layer (kill switch / bot sender / skip marker + rate limit). `is_whitelisted_bot()` 헬퍼로 화이트리스트 봇만 BotInteractionLimiter 적용 |
| `src/webhook/router.py` | Webhook 라우터 aggregator — providers 3개 include |
| `src/gate/engine.py` | 3-옵션 Gate + GateDecision upsert (중복 INSERT 방지) + MergeAttempt 관측(Phase F.1) |
| `src/gate/merge_reasons.py` | auto-merge 실패 사유 정규 태그 상수 (Phase F QW5) |
| `src/gate/merge_failure_advisor.py` | `get_advice(reason)` — reason tag → 권장 조치 텍스트 (Phase F.3, 순수 함수) |
| `src/notifier/merge_failure_issue.py` | `create_merge_failure_issue()` — auto-merge 실패 GitHub Issue (Phase F.3, dedup 24h) |
| `src/models/merge_attempt.py` | MergeAttempt ORM — score/threshold 스냅샷 + failure_reason 태그 (Phase F.1, append-only) |
| `src/shared/merge_metrics.py` | parse_reason_tag + log_merge_attempt — DB INSERT + 구조화 로그 (Phase F.1) |
| `src/repositories/` | DB 접근 계층 10종 — repository_repo (`find_by_full_name` + Phase H 신규 `find_by_full_name_with_owner` opt-in joinedload), analysis_repo, analysis_feedback_repo, merge_attempt_repo, gate_decision_repo, repo_config_repo, user_repo, merge_retry_repo, insight_narrative_cache_repo, security_alert_log_repo |
| `src/worker/pipeline.py` | 분석 파이프라인 + build_analysis_result_dict |
| `src/models/merge_retry.py` | MergeRetryQueue ORM — 재시도 큐 (append-only claim 패턴) |
| `src/repositories/merge_retry_repo.py` | enqueue_or_bump · claim_batch · mark_succeeded/terminal/expired — 원자적 SKIP LOCKED 클레임 |
| `src/gate/retry_policy.py` | 순수 함수: should_retry · compute_next_retry_at · is_expired · mergeable_state_terminality |
| `src/github_client/checks.py` | get_ci_status · get_required_check_contexts (5분 TTL 캐시) |
| `src/services/merge_retry_service.py` | process_pending_retries — CI-aware 재시도 워커 |
| `src/gate/native_automerge.py` | enable_or_fallback() — GraphQL `enablePullRequestAutoMerge` 우선 + REST `merge_pr` 폴백 (Tier 3 PR-A, 그룹 52) |
| `src/gate/_merge_attempt_states.py` | MergeAttempt.state lifecycle 정규 상수 (LEGACY/ENABLED_PENDING_MERGE/ACTUALLY_MERGED/DISABLED_EXTERNALLY) — Phase 3 PR-B1 도입 |
| `src/github_client/graphql.py` | GraphQL POST 래퍼 + `enablePullRequestAutoMerge` mutation + `EnableAutoMergeResult` 분류 + 5xx 자동 재시도 (Phase H PR-1B-2, `_GRAPHQL_*` 상수) |
| `src/static/vendor/chart.umd.min.js` | Chart.js 4.4.0 UMD min vendoring (UI 감사 Step C) — CDN 차단/오프라인 환경에서 빈 차트 회피. `src/main.py` 의 CachedStaticFiles (`Cache-Control: public, max-age=31536000, immutable`) mount 로 노출. 사용 페이지: repo_detail / analysis_detail / dashboard. 운영 가이드: `docs/runbooks/static-assets.md` (PR-D4) |
| `src/main.py` `CachedStaticFiles` | `StaticFiles` 서브클래스 — HTTP 200 응답에 `Cache-Control: public, max-age=31536000, immutable` 자동 주입 (사이클 97 #423) |
| `src/services/repo_insight_service.py` `compute_score_kpi` | 공유 헬퍼 — cur/prev 분석 리스트 → avg_score/score_delta/grade 계산. `repo_kpi` + `dashboard_service.repo_insight_cards` 양쪽에서 재사용 (CPD 제거 목적, 사이클 97 #423) |
| `src/services/dashboard_service.py` `_fetch_analyses_for_window` / `_group_analyses_by_repo` | N+1 제거 배치 헬퍼 — repo_ids IN 절 단일 쿼리 + per-repo cap 그룹화 (사이클 97 #423) |
| `tests/conftest.py` | 환경변수 주입 + _webhook_secret_cache autouse 클리어 |

## 작업 이력

- **그룹 13~61** (2026-04 ~ 2026-05-02): [docs/_archive/STATE-groups-13-61-2026-05.md](_archive/STATE-groups-13-61-2026-05.md)
- **사이클 62~92** (2026-05-03 ~ 2026-05-11): [docs/cycle-history.md](cycle-history.md)
- **사이클 103** (2026-05-18): MCP Supabase 직접 조회로 auto-merge 실패 원인 분석 → 3건 코드 수정 + Codex mutual 검증 OK 후 머지 (#479) — **P0-fix**: `_trigger_retry_for_sha`의 `if not rows: return` 조기 반환 제거 + overdue sweep 무조건 실행 (cron failure fallback 보장) + `has_hooks` terminality `terminal` → `retriable` (CI hook 대기 → CI 완료 자동 해소) + `should_retry(UNSTABLE_CI, "unknown")` → `True` (transient GitHub API 오류 시 영구 terminal 방지). 테스트 3파일 갱신 (test_retry_policy · test_check_suite_handler · test_auto_merge_enqueue) + 신규 `test_trigger_retry_for_sha_sweeps_overdue_when_no_sha_rows` 추가. 단위 2813→2814.
- **사이클 102** (2026-05-17): 잔여 작업 확인 + `.codex/rules/ui.md` 테마명 정정 (`glass/claude-dark` → `pastel/catppuccin` — #462 CLAUDE.md 정정과 동기화, Codex 규칙 drift 해소, #475). CLAUDE.md P2-1 압축 완료 — **#476 Phase 1** (~10줄: 정책 8 관점 분리 목록·사이클 67 조건·단일관점 ROI·정책 18 하단) + **#477 Phase 2** (~7줄: 정책 1 서문·중복 cross-ref·cross-verify 에이전트 설명 1줄 합침·진화 요약 heading 제거) + `docs/policies/history.md` 이전 3건 (정책 1 Q4 회귀 가드 전체 · 사이클 67 생략 조건 폐기 이력 · 단일관점 ROI 삭제 배경). 5+1 에이전트 검증 + Codex mutual OK. 총 절감 ~17줄.
- **사이클 95** (2026-05-14): 문서 정비 P2 (#410~#413) — testing.md SessionLocal 경고 추가 / architecture.md mockup-polar.html 항목 / AGENTS.md 중복 표 → 링크 3건 / STATE.md 그룹 13-61 아카이브 / CLAUDE.md HTML 주석 7블록 + line 361 압축 (59줄 절감).
- **사이클 96** (2026-05-14): pylint 10.00/10 달성 (#415) — C0415 17건 inline disable + C0301/R0913/R0917/W0718/W0613/E0401 처리. PR-D5 (#417): CLAUDE.md HTML 블록 3·5 → docs/policies/active.md 이전 (#정책-17-why-how + #정책-5-phase-종료-cross-reference 신설).
- **사이클 97** (2026-05-14): P0 경로 하드코딩 수정 (#420) — `.codex/hooks.json` + `doc_review_gate.py` × 2 + `.claude/settings.json` + `CLAUDE.md` `f:/` → `d:/` 전수 교체. 문서 정비 (#421) — AGENTS.md 완료 6-step 정정 + `.codex/rules/deploy.md` nixpacks exit127 경고 추가. Issue #408 기능 구현 (#423) — MPA 네비게이션 진행 바 (`#page-progress` CSS+JS IIFE, 같은 경로 앵커 가드) + `CachedStaticFiles` (1년 캐시 immutable) + `dashboard_service.repo_insight_cards` N+1 → 배치 IN 쿼리 2건 (`_fetch_analyses_for_window` + `_group_analyses_by_repo`) + `compute_score_kpi` 공유 헬퍼 추출 (CPD 5.5%→0.0%) + `recurring_issue_count` count≥2 수정. 단위 테스트 2912→2914. scripts 하드코딩 경로 제거 + dashboard async 블로킹 수정 (#426) — `scripts/i18n_comments/` 4 파일 `f:/…` → `Path(__file__).resolve().parents[2]` 동적 경로 + `dashboard.py` security/usage/overview `run_in_threadpool` 래핑 (이벤트 루프 블로킹 방지) + `_DASHBOARD_TEMPLATE` 상수 추출 (SonarCloud S1192 해소). STATE.md 갱신 (#427). 랜딩 페이지 추가 (#428) — `src/templates/landing.html` Vercel+Stripe 스타일 프리미엄 랜딩 (애니메이션 메시 그라데이션 + 4-orb float + fadeUp stagger + 미인증 분기 `overview.py` → `get_current_user` Optional 교체) + `test_overview_landing.py` 2건 (미인증→landing / 인증→overview). 랜딩 phantom token 수정 (#429) — `--bg-base-rgb` → `var(--bg-nav)` (4-테마 정의 token) + `docs/architecture.md` templates 목록 `landing` 추가. CodeQL unused import 해소 (#431) — `test_0031_repo_insights_cache.py` 미사용 `from-import` 제거 (alerts #387+#389) + side-effect import #386/#384 false-positive dismiss.
- **사이클 99 CodeQL 정비** (2026-05-15): PR #445 머지 — `tests/unit/ui/test_dashboard_repos_mode.py` `import pytest` 삭제 (알림 #397 실제 수정) + `tests/integration/test_repo_report_api.py` side-effect import `# noqa: F401` 알림 #395/#396 false-positive dismiss. CodeQL open alert 0건.
- **사이클 99 후속** (2026-05-15): 회고 문서 정비 (#docs/cycle99-retro-followup) — `.claude/rules/testing.md` settings 싱글톤 mock 패턴 추가 + `.claude/rules/ui.md` Jinja2 `lower+default` None 함정 경고 추가 + `docs/architecture.md` `/api/repos/report` 엔드포인트 2건 + repo_insight_service 7 함수 + find_all_by_user + repositories 설명 갱신 + `docs/policies/active.md` PR 템플릿 Codex 검증 의뢰 섹션 추가 (정책 18 강화). ⚠️ cherry-pick 경위: PR #442/443은 feat 브랜치를 base로 생성 → GitHub MERGED 표시됐으나 main 미반영 → `git cherry-pick 2cf0bf4 78fd6de b7b1b07 df54294` + `git push origin main` 으로 사용자(xzawed)가 직접 수습.
- **사이클 101 회고 자유 발언 이행** (2026-05-17): 메모리 슬러그 자동 검증 + 에이전트 도메인 분리 (#469~#470) — **#469**: `scripts/check_memory_refs.py` 신설 (CLAUDE.md/active.md/history.md 참조 슬러그 ↔ 실제 파일 비교, 스테일 `(현재 미생성)` 어노테이션 탐지, UTF-8 강제, S3776 CC ≤ 15) + `Makefile` `check-memory-refs` 타깃 추가 + `active.md` 스테일 어노테이션 8건 제거. **#470**: `docs/policies/active.md` `#정책-8-doc-audit-agent-domain` 신설 — 5+1 문서 감사 에이전트 비중복 5 도메인 분리 표 (Agent-1: CLAUDE.md/.claude / Agent-2: policies/ / Agent-3: architecture+STATE / Agent-4: .claude/rules/ / Agent-5: reference+runbooks / Agent-6: cross-verify). 메모리 18건 실측 확인 (이전 35건 = 산정 오류 정정).
- **사이클 101 문서 감사 후속** (2026-05-17): 5+1 cross-verify 식별 항목 정리 (#466~#467) — **#466**: `.claude/rules/testing.md` `tests/test_ui_router.py` → `tests/unit/ui/test_router.py` 경로 + `.claude/rules/api.md` SDK timeout 명확화 (Anthropic 60s / httpx 10s) + `.claude/rules/deploy.md` SMTP_PORT coerce_smtp_port 자동처리 정정. **#467**: `docs/reference/env-vars.md` `STRICT_TOKEN_ENCRYPTION` 누락 항목 추가 + SMTP_PORT 설명 정정 + `docs/STATE.md` "2967 passed" → "2963 passed, 4 skipped" 실측 반영. 누락 메모리 파일 4개 생성 (P0 — feedback-architecture-decision-pre-confirm / feedback-codex-post-validation-mandatory / feedback-fixture-model-sync-discipline / feedback-pr-scoped-ci). 허위 양성 6건 제거 (architecture.md 분석기 수 / Policy 13 smoke 카운트 / DB_FORCE_IPV4 / MERGE_UNKNOWN_RETRY_LIMIT / CLAUDE.md 줄수 / api.md timeout 평면 불일치).
- **사이클 101** (2026-05-17): 5+1 멀티에이전트 감사 전 항목 수정 (#460~#464) — **#460 P0**: `test_grade_a_for_score_90_plus` dead assertion 수정 (AI 최대점 강제로 total=100 보장) + `_extract_event_metadata` 브랜치 삭제 push KeyError 방어 (`or {}` 패턴) + README 배지 갱신 (2917→2964). **#461 P1**: `GITHUB_API` URL 상수 9개 파일 일괄 치환 + Gate 임계값 3종 (`GATE_DEFAULT_APPROVE/REJECT/MERGE_THRESHOLD`) constants.py 단일 출처 → ORM·dataclass·API·UI 4곳 sync. **#462 P1**: CLAUDE.md·active.md 테마명 `glass/claude-dark` → `pastel/catppuccin` 정정 + test_semgrep 2개 isinstance-only 어설션 강화 (`filename`·`issues` 검증 추가). **#463 P1**: lifespan startup `TELEGRAM_WEBHOOK_SECRET` 미설정 시 prod-only SECURITY 경고 + test_main 3건 커버리지. **#464 P2**: `validate_external_url` async화 + `socket.getaddrinfo` → `asyncio.to_thread` (이벤트 루프 블로킹 방지) + 5개 notifier caller `await` 추가 + test_http.py async 변환 + test_retry_concurrency_postgres 2곳 assertion 강화 (is not None → len==1/isinstance list). 단위 2810→2813, 통합 125→154.
- **사이클 100** (2026-05-17): pytest 성능 병목 해소 (#449) — `pytest.ini` `--timeout=30` 전역 적용 (subprocess hang 방지) + starlette/fastapi DeprecationWarning 필터 + `pytest-timeout>=2.3.0` 추가 + `Makefile` `test-local` 타겟 (slow 제외 Windows 로컬용) + `tests/integration/test_static_analyzer.py` module-scope fixtures 도입 (`_clean_result`/`_eval_result` — analyze_file subprocess 모듈당 1회 제한). 테스트 수 변동 없음 (34 passed).
- **사이클 98** (2026-05-15): CodeQL py/exit-from-finally 수정 (#433) — `tests/unit/ui/test_router.py` finally 블록 람다 2건 → 명시 함수 `_restore_get_current_user()` / `_restore_require_login()` 교체 (CodeQL alert #390 해소). HTMX hx-boost 네비게이션 (#434) — `htmx.min.js` 1.9.12 vendoring + `base.html` `<body hx-boost="true">` + `htmx:afterSettle` 프로그레스바 연동 + `analysis_detail.html` Chart.js `destroy()` 가드 + `test_htmx_vendor.py` 회귀가드 3건 (단위 2914→2917). hx-boost 후속 수정 (#435) — `docs/architecture.md` htmx.min.js 항목 추가 + `repo_detail.html`/`dashboard.html` `themechange` boolean 플래그 가드 (stale closure 버그 발생 — #436으로 즉시 수정). themechange stale closure 완전 수정 (#436) — boolean 플래그 → remove-before-add 패턴 3개 파일 (`_repoThemeHandler`/`_dashThemeHandler`/`_riThemeHandler`) + `.claude/rules/ui.md` themechange 패턴 갱신.