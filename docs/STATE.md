# SCAManager 프로젝트 상태

> 이 파일이 단일 진실 소스(Single Source of Truth)다. Phase 완료·주요 변경 시 여기를 먼저 갱신한다.

## 현재 수치 (2026-05-14 기준 — **사이클 97**: P0 경로 하드코딩 수정 (#420) + 문서 정비 (#421) + Issue #408 기능 구현 (#423 — 네비게이션 진행 바 + CachedStaticFiles + N+1 쿼리 제거 + compute_score_kpi 공유 헬퍼 + CPD 0.0% 달성)): 130+ PR #188~#423 — 누적 정책 본문 19건 + 메모리 30건 (활성 28 + deprecated 2). 단위 2912 / 통합 129 / E2E 96 / pylint **10.00/10**

| 지표 | 값 | 비고 |
|------|-----|------|
| 단위 테스트 | **2912개** | pytest 9.0.3 — 사이클 73~75 +67 + 사이클 78~82 +114 (2122→2236) + 사이클 84 i18n 18 PR +473 누적 + **사이클 85 Sentry 완전 제거 -40** + **#375 일러스트 회귀 가드 +13** + **#397 UI 리디자인 +26** (form/mobile/sweep) + **사이클 96 #415 pylint +0** + **사이클 97 #423 +4** (CachedStaticFiles 2 + recurring_count 회귀가드 2). **= 2912 collected** |
| 통합 테스트 | **129개** | tests/integration/ — 사이클 81 영역 🅑 모바일 Phase 1 MVP +34 + **사이클 84 i18n PR-18 smoke +11** (3 언어 × /login Cookie + HTML lang attr + default fallback + i18n metrics). **= 124 passed / 5 skipped / 0 failed** |
| E2E 테스트 | **96개** | `make test-e2e` (Chromium Playwright) — Phase 3 PR 6 +7 + **사이클 84 i18n PR-16 +14** (3 언어 × 4 페이지 — login/overview/dashboard/settings + Cookie fallback + locale switch). **사이클 94 #372 (추정 수치 — 사용자 `make test-e2e` 검증 후 정정 영역)**: test_save_success ordering 트랩 차단 (`_reset_repo_config()` 헬퍼) → PASS 회복 + test_two_column UX 결정 영역 보류 (`@pytest.mark.skip`). **추정 = 95 passed / 1 skipped / 0 failed**. ⚠️ e2e ↔ tests/integration 동시 실행 금지 — `e2e/pytest.ini` 의도적 asyncio_mode 미설정, 분리 실행 default (`make test-e2e` vs CI command `pytest tests/`) |
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
- **사이클 95** (2026-05-14): 문서 정비 P2 (#410~#413) — testing.md SessionLocal 경고 추가 / architecture.md mockup-polar.html 항목 / AGENTS.md 중복 표 → 링크 3건 / STATE.md 그룹 13-61 아카이브 / CLAUDE.md HTML 주석 7블록 + line 361 압축 (59줄 절감).
- **사이클 96** (2026-05-14): pylint 10.00/10 달성 (#415) — C0415 17건 inline disable + C0301/R0913/R0917/W0718/W0613/E0401 처리. PR-D5 (#417): CLAUDE.md HTML 블록 3·5 → docs/policies/active.md 이전 (#정책-17-why-how + #정책-5-phase-종료-cross-reference 신설).
- **사이클 97** (2026-05-14): P0 경로 하드코딩 수정 (#420) — `.codex/hooks.json` + `doc_review_gate.py` × 2 + `.claude/settings.json` + `CLAUDE.md` `f:/` → `d:/` 전수 교체. 문서 정비 (#421) — AGENTS.md 완료 6-step 정정 + `.codex/rules/deploy.md` nixpacks exit127 경고 추가. Issue #408 기능 구현 (#423) — MPA 네비게이션 진행 바 (`#page-progress` CSS+JS IIFE, 같은 경로 앵커 가드) + `CachedStaticFiles` (1년 캐시 immutable) + `dashboard_service.repo_insight_cards` N+1 → 배치 IN 쿼리 2건 (`_fetch_analyses_for_window` + `_group_analyses_by_repo`) + `compute_score_kpi` 공유 헬퍼 추출 (CPD 5.5%→0.0%) + `recurring_issue_count` count≥2 수정. 단위 테스트 2708→2912.