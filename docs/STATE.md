# SCAManager 프로젝트 상태

> 이 파일이 단일 진실 소스(Single Source of Truth)다. Phase 완료·주요 변경 시 여기를 먼저 갱신한다.

## 현재 수치 (2026-08-06 기준)

> 📌 **이전 세션·PR별 누적 작업 서사는 [`docs/cycle-history.md`](cycle-history.md) 단일 출처** (사이클 60~166, 최신순). 본 헤더는 **최신 1건 + 종합 수치만** 유지 — 32KB 단일 라인 SSOT 가독성 복원 (품질감사 docclr-1, 2026-06-17, cycle-history.md 에 서사 전량 보존[append-only] 확인 후 트리밍). 🔴 **다음 세션 갱신 규칙**: 신규 작업 완료 시 (0) **본 섹션 날짜 헤더(line 5 `## 현재 수치 (YYYY-MM-DD 기준)`)를 최신 세션 날짜로 갱신** (회고 2026-07-03 C5 #60 — 절차에서 상시 누락되던 필드), (1) 본 "최신" 블록을 새 작업으로 교체 + 종합 수치 갱신, (2) 직전 작업의 전체 서사는 `docs/cycle-history.md` 최신순 맨 앞에 본문 섹션으로 이관 (헤더에 "직전" 체인 누적 금지 — 본 정리의 회귀 방지), (3) **"최신" 블록은 불릿 5~8줄로 작성 — 단일 라인 금지** (2026-07-09 rank14: 단일 라인은 diff 심의·가독성 저해, doc_review_gate CRITICAL 게이팅 대상. 종합 수치 표·추적셀[테이블 셀]은 단일 라인 유지).

**최신 (2026-08-06~08 세션17 — 회고 P1 + 결정 6건 + 진단 처방 P1~P4 + 5+1 회고 + 적대 재검증, PR #1297~#1319)**
- **회고 P1 4건**(`#1297`~`#1300`) + **사용자 결정 4건**(R56·R0-2·R57·R64, `#1303`~`#1306`).
- 🔴 **사용자 질문이 창을 바꿨다** — *"반복되는 실수가 문서 규모 문제인가"*. 9-에이전트
  진단 결론: **총량 가설 3/10 · "규칙이 지켜지지 않는다" 8/10**. 증상은 정확, 기전은 반대다 —
  못 지킨 규칙마다 문서를 한 줄 더 쓴 결과가 그 규모다(`발화율 100% / 이행률 0%` 실측).
- 🔴 **지배 원인**: 결함을 고친 당사자가 관측자를 같은 PR 에서 만들고, 그 관측자가
  **진실 대신 자기 사본**을 잰다. 이 창이 자기 몸으로 증명했다 — 수치 오판독이 4지점에
  전파돼 `check_docs_sync` ✅ 로 통과·머지되고 **main 이 12시간 49분 빨갰다**.
- **처방 4건 전부 구현**: **P1** 역-뮤테이션 게이트(소급 6 PR 전건 red) · **P2** 드리프트
  PR 차단(advisory 제거·이월은 명시 마커) · **P3** main red 지속시간 관측(방치 20h·12.8h 실측)
  · **P4** 🔴 예산제(집행자 없는 🔴 증가 차단, 산식 **67/290 = 23.1%** 고정).
- 🔴 **처방을 만드는 동안 내가 만든 가드가 나를 6번 막았다** — 특히 P1 의 `__pycache__`
  fail-open 은 **Linux 에서만 발현**해 로컬이 못 봤다(backlog R30 축).

**종합 수치**: 전체 **7457** 수집 (단위 **7286** + 통합 171) / E2E **121** (`#1291` 이 중복 1건 제거) — CI 실측 **120 통과 / 1 skip / 0 실패**(`#1294`, 2026-08-06). 🔴 배선(`#1288`) 이래 **처음 전건 초록**이다: 스위트-앱 drift 30건(`#1291`) · CSP 가 자기 폰트를 차단하던 앱 결함 · CI 가 CSS 빌드 없이 돌던 설정 결함(`#1294`)을 순서대로 해소. backlog R52 / pylint **9.99/10** (src/ — 🔴 **CI `lint-src` job 이 `--fail-under` 를 **README 배지에서 파생**해 게이트**한다(2026-08-12 문서감사 PR-4 — 이전 리터럴 9.90 은 9.99 도 10.00 주장도 전부 통과시켰다). scripts/ 는 미게이트).

| 지표 | 값 | 비고 |
|------|-----|------|
| 전체 테스트 | **7457 수집** *(헤더 = 최신값, 이 셀 = pytest 누적 추적)* | `pytest tests/` — 단위 7286 + 통합 171 (현재). 누적 이력은 **아래 §테스트 수 추적 이력** 참조 (단위 baseline 4718). |
| 통합 테스트 | **171개** | tests/integration/ — 사이클 81 영역 🅑 모바일 Phase 1 MVP +34 + **사이클 84 i18n PR-18 smoke +11** + **PR #400 repo insights +22** + **사이클 99 #441 +3** (repo_report_api auth·list·404) + **사이클 100~101 누적** (test_retry_concurrency_postgres assertion 강화). 기존 test_settings_mobile.py 일부 Windows cp949 인코딩 오류 제외. + **사이클 143 #690 repo_detail i18n smoke +2** (151→153). + **사이클 165 #817 +1** (claim_decision PG first-writer-wins invariant — 153→154, pg-concurrency CI job 실행 / 로컬 PG 미설정 시 skip). + **2026-07-18 P2#43 #1092 +4** (retention DELETE PG round-trip — CI 배선 메타 1[로컬 실행] + purge_expired/purge_terminal/비-UTC TZ 3[pg-concurrency job, 로컬 skip], 154→158). + **2026-07-29 세션11 #1228 +7** (런타임 eslint 무동작 5-결함 봉인 — 실 subprocess round-trip, 158→165). **= 171 collected 실측 (`py -3 -m pytest --collect-only -q tests/integration`, 2026-08-01. PG 테스트는 pg-concurrency CI job 에서 통과, 로컬 skip)** — 🔴 이 셀이 158 에 머물러 헤더(line 34)·세션 블록(line 19)의 165 와 어긋나 있던 것을 2026-07-30 실측으로 재동기화 |
| E2E 테스트 | **121개** | `make test-e2e` (Chromium Playwright) — Phase 3 PR 6 +7 + **사이클 84 i18n PR-16 +14** (3 언어 × 4 페이지 — login/overview/dashboard/settings + Cookie fallback + locale switch). 사이클 94 #372: test_save_success ordering 트랩 차단 (`_reset_repo_config()` 헬퍼) + test_two_column 보류 (`@pytest.mark.skip`). **+ 사이클 106 #500 `@pytest.mark.perf` 12개** (TTFB/FCP/LCP/DCL/Load — 3회 avg/min/max). **+ 사이클 127 #605 `test_nav_handler_survives_hx_boost_renavigation` +1** (hx-boost 3회 재방문 회귀 가드). **+ 사이클 127 #609 사전 실패 8건 해소** (5 TIMEOUT: test_theme.py glass/claude-dark 셀렉터 → pastel/catppuccin 갱신 + 3 ERROR: test_repos_mode.py auth_cookies 픽스처 제거). **+ 사이클 161 #766 `test_reveal_progress_handlers_use_remove_before_add` +1** (base.html _initReveal/_finishProgress hx-boost 핸들러 누적 가드 — 3회 재방문 후 document 슬롯 단일 저장 검증). **+ 2026-06-13 U2 +2** (`test_effects_init_reruns_on_hx_boost` — effects.js init hx-boost 재실행, 3회 재방문 후 `document._fxEffectsHandler` function + `body.fx-ready` 검증 · `test_magnetic_hover_registers_on_overlapping_cards` — Codex mutual 발견 회귀 가드, effect별 독립 추적으로 magnetic mousemove `--mx` 등록 검증). **+ 2026-06-17 repos 점수추이 차트 #929 +1** (`test_repos_mode_score_trend_chart_renders` — repo 선택 + score_trend≥2[서로 다른 날짜] seed → `Chart.getChart('repoTrendChart')` 인스턴스 부착 검증 + pageerror trap, repos 모드 Chart.js 미로드 회귀 봉인). **+ 2026-06-18 repo_detail 차트 #933 +1** (`test_repo_detail_score_chart_renders` — repo_detail(`/repos/{name}`) scoreChart 렌더 + pageerror trap, I18N 스코프 회귀 런타임 봉인). **+ 2026-06-18 개요 count-up 0/100 고착 (commit 1c0a483/75f942e) +3** (`test_overview_score_survives_io_miss`·`test_overview_score_renders_full_load`·`test_overview_score_survives_double_init` — IntersectionObserver no-op 주입 시 `.repo-card__score` "0/100" pre-fill 고착 해제[rAF 안전망] + below-fold 이중 init[IIFE 재실행 + htmx:afterSettle] dispose 회귀 복구[작은 뷰포트 + `document._fxEffectsHandler()` 직접 호출 결정론 재현], pageerror trap). **+ 2026-06-19 개요 점수 실제 네비게이션 회귀 가드 +1** (`test_overview_score_survives_repo_to_overview_nav` — repo 상세 `/repos/{name}` full load → repo↔개요 hx-boost 왕복 3회 후 `.repo-card__score` "0/100" 미고착 검증. 사용자 보고 경로[repo 화면 거친 뒤 개요 이동 시 0/100 고착]를 그대로 재현 — 기존 테스트가 IO no-op + `document._fxEffectsHandler()` 직접 호출로 이중 init 을 인위 시뮬한 coverage gap 보완). **+ 2026-07-09 개요 count-up cross-closure 봉인 #1039 +1** (`test_overview_score_survives_single_nav_cross_closure` — hx-boost swap 시 IIFE 클로저 2개가 `.repo-card__score` "0/100" pre-fill 을 교차 오염하는 고착을 fresh full-load 단일 nav ×8 로 충실 재현 → `dataset.cuBound` owned-array early-return 가드 검증, TDD 가드 OFF 6/8 고착 → ON 0/8). **= 121 collected (110 표준 + 11 perf)** — 🔴 2026-08-08 실측 정정: 이 셀만 **122** 로 남아 같은 파일 종합수치(121)·`e2e/EXPECTED_COUNT`(121)·README 배지 2곳(121)과 **모순**이었다. `#1291` 이 중복 1건을 제거할 때 종합수치만 따라오고 이 셀이 뒤처졌다. 🔴 E2E 축은 `check_docs_sync`·`check_test_count_sync` 어느 쪽도 보지 않는 **미집행 축**이라 자정되지 않았다(회고 N-P0-4). 🔴 **그리고 그 정정이 또 틀렸다** — `#1316` 이 총계를 121 로 고치면서 내역을 `109 + 12` 로 적었는데 실측은 `110 + 11` 이다(두 성분 다 거짓). 같은 커밋이 만든 전용 집행자는 `총계 == 표준 + perf` 만 봐서 **초록인 채로 거짓을 지켰다** — 합이 맞는 거짓 쌍은 무한히 많다. 이제 `check_e2e_scope.py` 가 **성분별로** 실측 대조한다. `make test-perf` 로 perf 마커만 선택 실행. ⚠️ e2e ↔ tests/integration 동시 실행 금지 — `e2e/pytest.ini` 의도적 asyncio_mode 미설정, 분리 실행 default (`make test-e2e` vs CI command `pytest tests/`) |
| SonarCloud Quality Gate | **OK** (2026-07-22 live API 실측) | #658 ReDoS S5852 hotspot 해소 + #946 aria-label 로 `Web:InputWithoutLabelCheck` 해소. ✅ **2026-07-22 VERIFIED (정책 19 — live main API 실측)**: #1168 이 new-code reliability 버그 2건(S5779·S5863)으로 QG 를 일시 regress 시켰다가 머지 전 수정 → **main `api/qualitygates/project_status` = OK** 실측 확인(all 6 conditions OK: new_reliability/security/maintainability_rating=1·new_coverage 96.4·new_dup 0·hotspots_reviewed 100). #1168 회귀 완전 복구. |
| SonarCloud Security Rating | **A** | Vuln 0, Hotspots 0 (dotnet_format·tsc ReDoS 패턴 #658 수정) |
| SonarCloud Reliability Rating | **A** (2026-07-22 live API 실측) | ✅ **2026-07-22 VERIFIED (live main API)**: `api/measures/component` = **bugs 0 · reliability_rating A · security_rating A · vulnerabilities 0**. #1168 이 도입한 new-code reliability 버그 2건(S5779·S5863)을 does-not-raise wrapper 제거·pinned oracle 로 수정 후 main 재스캔 반영 확인 — 회귀 완전 복구. |
| SonarCloud Maintainability Rating | **A** (2026-07-22 live API 실측) | Code Smells **145** (2026-07-22 live `api/measures/component` 실측 — 2026-06-22 의 109 에서 증가[신규 코드 유입]이나 **maintainability A 유지·new_maintainability_rating=1 OK·게이트 무영향**. BLOCKER/CRITICAL 0 유지). |
| SonarCloud BLOCKER / CRITICAL | **0 / 0** | #948~#954 로 전부 해소 — BLOCKER `S8414` 1건(#948) + CRITICAL 10건(`S1192` 3 + `S3776` 7, #949~#954). 2026-06-22 재스캔 실측 |
| pylint | **9.99/10** | `python -m pylint src/` — 🔴 **2026-08-12 실측 정정**: 배지·STATE·ci.yml 이 10.00 을 주장했으나 실제는 9.99 다(잔여 3건 = `config.py:236` E1136 · `ai_review.py:215` E1125 `duration_ms` 누락[진짜 버그 후보] · `pipeline.py` C0302 1089/1000줄). 집행 = `scripts/check_docs_sync.py::check_lint_badge` + CI `--fail-under` 배지 파생. 이하 역사: — #415 잔여 21건 전체 해소 (C0415 17 lazy import inline disable + C0301 1 + R0913/R0917 3 + W0718/W0613 2 + E0401 1). **10.00 달성**. 🔴 **2026-07-19: 9.99 로 drift 했던 것을 7건 정리해 10.00 복원** (D3 사용자 결정) — `main.py` 세션 시크릿 상수 모듈 승격·CORS 상수 명명·alembic import 블록 분리(로컬 동명 패키지라 pylint 가 first-party 로 봄), `scheduler.py` 의도적 broad-except 3건에 사유 주석 + inline disable. |
| 커버리지 | **Python 97% (2026-06-12 스냅샷 — 미재측정) / JS: E2E 커버** | Python: `py -3 -m pytest tests/unit --cov=src` (8497줄 중 291 미커버, 97% — **2026-06-12 실측 이후 재측정 없음**. 🔴 헤더 날짜가 최신이라 현재값으로 오독되기 쉬워 시점을 명시한다). JS: E2E pageerror 트랩(PR #605) + 정적 스캐너(PR #606) + ESLint(PR #607)으로 보완. `src/templates/*.html` 인라인 JS는 Python 커버리지 미측정 — 언어별 분리 보고 의무 (사이클 127 P0 학습). |
| bandit HIGH | **0개** | bandit 1.9.4 (Python 3.12+ 대응) |
| flake8 | **CI 미게이트** (실측 14 E501 + 1 E131 = 15건 — `|| true` advisory, 의도적 제외) | `flake8 src/` |
| 지원 언어 (AI 리뷰) | **49개** | language.py — Tier1/2/3 가이드 (도달불가 json_schema dead 가이드 제거, analyzer-pure-001) |
| 지원 언어 (정적분석) | **27개** (등록 분석기 25종이 ≥1 지원) | 🔴 **아래 내역은 (도구,언어) 쌍 48건이라 합산하면 중복이다** — 고유 언어는 27개다. Semgrep 22 + ESLint/tsc 2 + ShellCheck 1 + cppcheck 1 + slither 1 + rubocop 1 + golangci-lint 1 + Python 3 + **신규 15**: Dockerfile(hadolint)·Kotlin(ktlint)·HCL(tflint)·SQL(sqlfluff)·YAML(yamllint)·PHP(phpstan)·Swift(swiftlint)·CSS(stylelint)·SCSS(stylelint)·HTML(htmlhint)·Protobuf(buf_lint)·Dart(dart_analyze)·PowerShell(psscriptanalyzer)·C#(dotnet_format)·Rust(clippy) |
| Tier1 정적분석 도구 | **25종** | pylint·flake8·bandit·semgrep·eslint·shellcheck·cppcheck·slither·rubocop·golangci-lint·**hadolint**·**ktlint**·**tflint**·**tsc**·**sqlfluff**·**yamllint**·**phpstan**·**swiftlint**·**stylelint**·**htmlhint**·**buf_lint**·**dart_analyze**·**psscriptanalyzer**·**dotnet_format**·**clippy** |
| pytest-asyncio | **1.4.0** | Python 3.12+ DeprecationWarning 제거 완료 · **SSOT=Python 3.12** — CI(`.github/workflows/ci.yml` python-version) + Railway(`.python-version`=3.12, nixpacks 핀; default 3.11) + docs 동일 (로컬 dev 3.13 = 3.12+ 호환). 3.14 미검증 선언 정정 (#22) |
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
| `src/repositories/` | DB 접근 계층 13종 — repository_repo (`find_by_full_name` + Phase H 신규 `find_by_full_name_with_owner` opt-in joinedload), analysis_repo, analysis_feedback_repo, analysis_attempt_repo (0045: `find_orphaned` / `purge_by_ids` 분석 소실 흔적), merge_attempt_repo, gate_decision_repo, repo_config_repo, user_repo, merge_retry_repo, insight_narrative_cache_repo (0033: `record_error` / `record_error_repo` 에러 빈도 추적), claude_api_cost_repo (0043: Anthropic 비용 집계), security_alert_log_repo, issue_registration_repo |
| `src/worker/pipeline.py` | 분석 파이프라인 + build_analysis_result_dict |
| `src/models/merge_retry.py` | MergeRetryQueue ORM — 재시도 큐 (append-only claim 패턴) |
| `src/repositories/merge_retry_repo.py` | enqueue_or_bump · claim_batch · mark_succeeded/terminal/expired — 원자적 SKIP LOCKED 클레임 |
| `src/gate/retry_policy.py` | 순수 함수: parse_reason_tag · should_retry · compute_next_retry_at · is_expired |
| `src/github_client/checks.py` | get_ci_status · get_required_check_contexts (5분 TTL 캐시) |
| `src/services/merge_retry_service.py` | process_pending_retries — CI-aware 재시도 워커 |
| `src/gate/native_automerge.py` | enable_or_fallback() — GraphQL `enablePullRequestAutoMerge` 우선 + REST `merge_pr` 폴백 (Tier 3 PR-A, 그룹 52) |
| `src/gate/_merge_attempt_states.py` | MergeAttempt.state lifecycle 정규 상수 (LEGACY/ENABLED_PENDING_MERGE/ACTUALLY_MERGED/DISABLED_EXTERNALLY) — Phase 3 PR-B1 도입 |
| `src/github_client/graphql.py` | GraphQL POST 래퍼 + `enablePullRequestAutoMerge` mutation + `EnableAutoMergeResult` 분류 + 5xx 자동 재시도 (Phase H PR-1B-2, `_GRAPHQL_*` 상수) |
| `src/static/vendor/chart.umd.min.js` | Chart.js 4.4.0 UMD min vendoring (UI 감사 Step C) — CDN 차단/오프라인 환경에서 빈 차트 회피. `src/main.py` 의 CachedStaticFiles (`Cache-Control: no-cache` ETag 재검증) mount 로 노출. 사용 페이지: repo_detail / analysis_detail / dashboard. 운영 가이드: `docs/runbooks/static-assets.md` (PR-D4) |
| `src/main.py` `CachedStaticFiles` | `StaticFiles` 서브클래스 — 200/304 응답에 `Cache-Control: no-cache`(ETag 재검증) 자동 주입. 🔴 무버전 URL(`/static/js/effects.js` 등)이라 immutable 장기 캐시 금지 — immutable+1년은 배포 후 구 JS/CSS 를 최대 1년 서빙(2026-06-18 stale 사고, #936 라이브 미반영). `no-cache` 는 변경 시 즉시 전파·미변경 시 304(본문 재다운로드 없음) (사이클 97 #423 도입, 2026-06-18 immutable→no-cache 정정) |
| `src/services/repo_insight_service.py` `compute_score_kpi` | 공유 헬퍼 — cur/prev 분석 리스트 → avg_score/score_delta/grade 계산. `repo_kpi` + `dashboard_service.repo_insight_cards` 양쪽에서 재사용 (CPD 제거 목적, 사이클 97 #423) |
| `src/services/dashboard_service.py` `_fetch_analyses_for_window` / `_group_analyses_by_repo` | N+1 제거 배치 헬퍼 — repo_ids IN 절 단일 쿼리 + per-repo cap 그룹화 (사이클 97 #423) |
| `tests/conftest.py` | 환경변수 주입 + _webhook_secret_cache autouse 클리어 + _user_repos_cache autouse 클리어 |

## 작업 이력

> 본문 전량(38,450자 · 46항목 · 2026-05-14~2026-06-12)은 2026-08-15
> [`cycle-history.md` §STATE.md 이관 — 작업 이력](cycle-history.md#statemd-이관--작업-이력-2026-05-14--2026-06-12)
> 로 이관했다. `:7` 이 이미 *"이전 세션·PR별 누적 작업 서사는 cycle-history 단일 출처"* 로
> 이 이관을 승인한다 — 새 계약을 만들지 않는다.
>
> 🔴 **아카이브 `STATE.md:N` 인용 오프셋 (2026-08-15, 헤딩+포인터 유지)**:
> 원문 line 79–127 = 49줄 → 이 stub = 17줄. `docs/_archive/**` 의 `STATE.md:N` 은
> 시점 기록이라 고치지 않았다(docs.md). 살아 있는 인용은 이 이관에서 갱신했다.
>
> | 인용 대상 N | 건수 | 따라가면 |
> |---|---:|---|
> | N < 79 | 175 | 그대로 |
> | 79–127 (이관된 절) | 1 | 그 줄에 원문 없음 → 위 이관처 |
> | N ≥ 128 | 33 | **−32줄** |

## 테스트 수 추적 이력

> 🔴 **새 항목은 이 절 맨 아래에 한 줄로 추가한다. 위 표 셀에 적지 않는다.**
> 형식이 곧 계약이다 — 항목은 `… (A→**B** 단위 … = **C** 수집)` 처럼 **단위와 누계를 모두**
> 담아야 한다. `check_docs_sync.py` 가 **마지막 불릿**을 파싱해 표 헤더·README 배지와 대조하며,
> 수치가 없는 항목이 꼬리에 오면 **red** 다(형식 미준수 자체가 실패 — Grok claim-review 지적).
> 단위 baseline **4718**. 최신 누계는 위 표의 헤더 값과 일치해야 하며,
> `scripts/check_docs_sync.py` 가 **머리(표 헤더)와 꼬리(이 절 마지막 줄)를 양쪽 다** 대조한다.
>
> 🔴 **왜 표 밖으로 옮겼나 (2026-08-05)**: 이 이력이 표 셀 안에 있을 때 그 줄은 **30,806자**
> 였다. 머리(누계)와 꼬리(최신 증분)가 한 줄 안에서 30,752자 떨어져 있어 **동시에 볼 수 없었고**,
> Grep 은 그 줄의 표시를 거부했으며(`[Omitted long matching line]`), 172자 변경이 84 KB diff 로
> 나와 리뷰가 불가능했다. 실제로 꼬리만 갱신하고 머리를 빠뜨린 사고가 났다.
> ⚠️ **파일을 옮기지는 않았다** — `doc_review_gate.py`·`check_docs_sync.py` 가 `docs/STATE.md`
> 경로를 하드코딩하므로 이동 시 관측자가 조용히 죽는다.

- (이전 사이클 73~128 누적 2948)
- **사이클 129 #614 AI Issue 등록 +59** (2948→3007).
- **사이클 130 #617 +2** (3007→3009).
- **사이클 131 Claude Design 재설계 #625~#633 +13** (3009→3022 단위).
- **사이클 139 #660~#664 +13** (rate_limiter 5 + notifier 5 + dashboard 3, 3022→3035 단위).
- **사이클 140 #666~#667 +17** (GateAction 17개, 3035→3052 단위).
- **사이클 141 #669 +9** (Rate Limiting 보강 9개, 3052→3061 단위).
- **사이클 142 P0 수정 — 실측 기반 재집계** (3061→3213 단위, 이전 과소집계 152건 보정).
- **사이클 142 Phase B-D #674~#676 +8** (S2/S4 test_main +3, conftest autouse +5, 3213→3221 단위).
- **사이클 142 회고 Tier B #679 +3** (LimitBodySizeMiddleware 413/400/200 회귀 가드, 3221→3224 단위).
- **사이클 142 회고 Tier B P1-4 #682 +105** (dashboard repos i18n 키 존재 105케이스, 3224→3329 단위).
- **사이클 143 #686+#689+#690 +150** (analysis_detail i18n +18, repo_detail 일반 텍스트 +66, 이슈 UI +66, 3329→3479 단위).
- **사이클 143 smoke +2** (151→153 통합).
- **사이클 144 #694+#695+#696 +55** (analysis_detail issue_panel +36, repo_detail bulk +12, 렌더 정합 가드 +7, 3479→3534 단위).
- **사이클 145 #698+#699 +153** (analysis_detail js_msg +66, repo_detail js_msg +87, 3534→3687 단위).
- **사이클 146 #702~#705 +571** (base theme +48, repo_insights +186, settings +120, landing +217, 3687→4258 단위).
- **사이클 147 #707~#708 +40** (settings 토스트/hint +18, render-parity 가드 +22, 4258→4298 단위).
- **사이클 149 #712~#715 +109** (gate 메시지 i18n + dead code 제거 — gate_messages/merge_advice 키 테스트, 4298→4407 단위).
- **사이클 150 #717 +19** (웹 UI 에러 메시지 i18n — web_errors 키 테스트, 4407→4426 단위).
- **사이클 151 #724 +16** (hook.py CLI 에러 i18n — hook_errors 키 테스트, 4426→4442 단위).
- **사이클 152 #726~#728 +51** (통합 회고 P0 수정 — format_ref +7, engine merge i18n, validator+seam 테스트, 4442→4493 단위).
- **사이클 153 #730~#731 +34** (railway Issue i18n +11, cron 주간/트렌드 i18n, 4493→4527 단위).
- **사이클 154 +6** (telegram 반자동 콜백 seam +2, cron escape 가드 +2, railway 핸들러 seam +2 — 사이클 153 회고 발견 P0 telegram.py:120 + P2 6건 수정, 4527→4533 단위).
- **사이클 155 +11** (발신 모듈 한국어 AST 소스 스캔 자동 가드 +3 + telegram ko-default seam +1, 4533→4537 + 가드 검증 식별 P1 수정 — resolve_ai_summary 현지화 테스트 +7 [ai_unavailable 키 3 + success/en/ja/none 4], 4537→4544 단위).
- **사이클 156 Theme B S1 +2** (SSRF _http.py fail-closed 봉인 — 빈 host·DNS gaierror 분기 회귀가드, mutation KILLED, src 무변경, 4544→4546 단위).
- **S2 +4** (4채널 SSRF 차단 early-return 봉인 — discord/slack/webhook/n8n validate=False 시 build_safe_client 미호출, mutation 전부 KILLED, 4546→4550 단위).
- **S4 +9** (coverage-tail — checks.py `_legacy_state_to_ci_status` parametrize 6 + 레거시 fallback e2e 1 [auto-merge gate 정확성] + security_scan 처리 본체 happy/rollback 2 [kwargs 값 단언 PR-5C 봉인], mutation KILLED, 4550→4559 단위).
- **S3 +0** (PG SKIP LOCKED 동시성 CI container — test_retry_concurrency_postgres 3건 CI 영구 skip→pass 상태전환 [new job `pg-concurrency` + postgres:16 service + barrier 결정성], 단위 불변 4559).
- **사이클 159 PR-A +1** (security_scan rollback 후 secret-scanning 지속 회귀가드 — except 절 break/return 회귀 차단, 4559→4560 단위).
- **사이클 159 PR-B +3** (`_http.py` DNS `except OSError` 확장 — timeout/OSError fail-closed 가드 2 + `scan_all_repos` 외부 루프 rollback 세션 격리 1, 4560→4563 단위).
- **사이클 160~161 실측 재집계** (이전 추적 누락분 #760~763 포함 — 단위 4563→4615, E2E 112→113): #764 클램프 회귀가드 단위 +2 (범위초과→cap / 음수→0) · #766 hx-boost 핸들러 누적 가드 nav E2E +1 · 나머지 단위 증가분은 #760~763(integrity-audit 세션) 미추적분 실측 반영 (단위 4615 + 통합 153 = 4768 수집).
- **사이클 162 #775~#781 +13** (RLS 자동탐지 가드 5 [test_rls_matrix_completeness 4 + issue_registrations 1] + P1-1 정적분석 타임아웃 가드 3 [AutoMergeAction skip 1 + 파이프라인 wiring 2] + P1-2 동시 insert race 1 + 기타 실측, 4615→4628 단위; #776/#781 은 기존 테스트 정정·#777 JS/#778 워크플로우는 Python 테스트 무증가).
- **사이클 163 #783~#787 +20** (area=gate P2 백로그 — #783 ApproveAction 정적분석 가드 +1 · #784 hook 점수 안전변환 +3 [비숫자/None/Infinity 직접 단위] · #785 merge_retry validator +6 · #786 zero-SHA 조기종료 +8 [skip 2 + `_is_blank_sha` parametrize 6] · #787 `_ensure_repo` race 복구 +2, 4628→4648 단위).
- **사이클 164 #794~#796 +2** (area=gate 잔여 6 결함 사용자 Q1~Q4 — #795 정적분석 재구성 +3 [타임아웃 부분결과 보존·파일 단위 격리·전량실패 안전망] · #796 telegram 대칭화 −2 [Block2 log_merge_attempt 관측 테스트 engine 이관] · #794 regate first-writer-wins +1, 4648→4650 단위).
- **사이클 164 회고 follow-up #798/#799 +5** (#798 PR 코멘트 incomplete 경고 배너 +2 · #799 회귀 가드 3건 [incomplete 종단·_race_recover 대칭·semi-auto 임계 layer], 4650→4655 단위).
- **사이클 165 Task9 리메디에이션 #802~814 +58** (P1 #802~810: telegram authz·secure_str_compare·incomplete fail-open·hook SHA race·check_suite force-due·RLS 가시화 + P2 #811~814: #11 claim 원자화 2 + telegram replay 2 · #13 webhook 본문 4 · #24 ai_review per-field · #12 SSRF docstring 2 · #25 hook NULL 5 · overview F-오분류 1, 4655→4713 단위).
- **사이클 165 회고 follow-up #816/#817 +3** (#816 docs/rule 정합·정책18 §3 2-tier = docstring/룰만 단위 무증가 · #817 회고 P1 테스트 갭 = claim_decision NOT NULL 흡수 +1 · seam 실DB +1 단위 + PG first-writer-wins invariant +1 통합[pg-concurrency CI job], 단위 4713→4715 · 통합 153→154).
- **사이클 165 회고 P2-② 봉인 #819 +3** (CLI-hook parse_error 인플레 점수 → _regate→gate fail-open 봉인 — run_gate_check orchestrator parse_error 차단/success 허용 +2 · _regate→gate result pass-through 배선 +1, 4715→4718 단위).
- **사이클 166 Task9 full 감사 P2 백로그 #820~#824 +5** (#821 insight_cache 유령 인덱스 회귀 가드 +1 [Red 2→Green 1] · #823 hx-boost 리스너 누적 정적 가드 +2 [add_repo pagehide·tweaks keydown] · #824 i18n 이중이스케이프 +2 [render no-double-escape·safe-contract allowlist]; #820 docs·#822 effects.js dead-code·#17 ORM 정합·#31 test dead-branch 은 단위 무증가, 4718→4723 단위).
- **사이클 166 잔여 DB/정리 #826~#828 +3** (#826 ORM↔alembic 인덱스 가드 +2 [test_0023 state_repo·partial unique] · #828 analyses FK CASCADE 가드 +1 [test_0038]; #827 고아 CSS 단위 무증가, 4723→4726 단위).
- **사이클 166 결정 영역 #830/#831 +1** (#831 #23 gate retry 'passed' 의도 회귀 가드 +1; #830 #22 Python SSOT docs-only 무증가, 4726→4727 단위).
- **사이클 166 회고/후속 #833/#834 +1** (#834 _coerce_score int() 절삭 의미 가드 +1; #833 Railway 핀 정정 docs-only 무증가, 4727→4728 단위).
- **사이클 166 #836 #18 +2** (전역 ORM↔alembic compare_metadata 가드 [PG-only] + 필터 로직 로컬 가드, 4728→4730 단위).
- **2026-06-09 적대 재검증 #839~#841 +3** (#32 settings JS-리터럴 tojson 정적 가드 +1 · #840 test_0039 repositories.user_id FK +1 · #841 test_0040 users 인덱스명 rename +1, 4730→4733 단위).
- **2026-06-09~10 잔여작업 #843 +2** (drift ③④' analyses/insight_cache 부분 인덱스 ORM 선언 가드 test_orm_partial_indexes 2건, 4733→4735 단위; #844 #2 RLS runbook docs-only 무증가).
- **2026-06-10 RLS Phase 2 +52** (test_worker_session_routing — config 변환/factory identity·독립 인스턴스/RLS listener 범위/ast 정적 라우팅 가드 16모듈×2/웹 negative 가드 + Codex R1/R2 강화 [전수 inventory 양방향 2 + 재바인딩 금지 1 + 모듈 객체 import 금지 1], 4735→4787 단위).
- **2026-06-10 RLS Phase 3 +22** (test_0041 가드 7 [bijection·NO FORCE 오염 포함] + saas force/bypass 실측 8 + 라우트 db-전달 2 + 렌더 bypass 배너 2 + routing 가드 scripts parametrize 2 + PG-live round-trip 1 [pg-concurrency CI, 로컬 skip], 4787→4809 단위).
- **2026-06-10 RLS #2 Phase 4 OAuth blocker +8** (auth_callback worker 세션 전환 [옵션 ②] hybrid 계약 가드 +2 [github.py bare+worker import 존재 + alias 금지 parametrize] + Codex mutual 발견 시스템 API 라우트 3종 worker 재라우팅 가드 +6 [test 5 alias/no-bare parametrize 가 _WORKER_ALIAS_MODULES 17→20 확장, repos·stats·repo_report × 2], 4809→4817 단위; src/auth/github.py·api 3종·test_github.py patch 전환은 무증가).
- **2026-06-10 RLS #2 Phase 4 admin hybrid +7** (#849 후속 — hybrid 계약 +4 + 엔드포인트 라우팅 sentinel +3 + `_get_worker_db` 커버 +2, 4817→4826 단위; `_get_worker_db` 분기 자체는 무증가).
- **2026-06-11 정합성 감사 follow-up — pipeline AI-fail NULL-persist +4** (P1: AI 리뷰 genuine 실패[api_error/parse_error] 시 인플레 점수 NULL 저장 — hook #25/#814 대칭, _save_and_gate `ai_review_failed` 게이트; api_error/parse_error→NULL·success/no_api_key/empty_diff→점수 유지 4 케이스; P2 ai_review.py literal 17/17/7→`AI_DEFAULT_*_RAW` 상수는 무증가, 4826→4830 단위).
- **2026-06-11 정합성 감사 follow-up 후속 4 PR (#855·#854·#856·#852) +8** (#855 SSRF 저장-시 단일출처+email CRLF +3 · #854 webhook secret 캐시 상한 +3 · #856 `_kpiCountupHandler` historyRestore[#473 대칭] +2 · #852 docs 정합 무증가, 4830→4838 단위, 각 머지 커밋 collect-only 실측).
- **2026-06-11 2nd-LLM 머지 검증자 (cross-vendor 거버넌스, feat/merge-verifier) +26** (verifier 15 + openai_client 5 + PR 코멘트 1 + AutoMerge 가드 5, 4838→4864 단위).
- **2026-06-11 잔여/후속 #861 +16** (verifier `interpret_verdict` fail-closed 엄격 파싱 회귀 가드 — 비-bool safe 7 [parametrize] · 비-False manipulation 6 · real-bool 보존 1 · httpx `_call_via_http` fallback 2, 4864→4880 단위).
- **2026-06-12 #863 +6** (verifier diff/token cap fail-closed 봉인 회귀 — merge_verifier 47라인 + openai_client 49라인, 4880→4886 단위).
- **2026-06-12 #865 +9** (verifier 봉인 P1-1 반자동 parity 단일출처화 회귀 — verifier_blocks_merge 7 + engine 가드 6 + telegram parity 1, 기존 auto_merge_verifier 5 교체, 4886→4895 단위).
- **2026-06-12 정합성 감사 #868~#871 +12** (P0 hook auth +3 · U0 dashboard 격리 +1 · C6+C2 AI-fail fail-open +6 · C3 retry 격리 +2, 4895→4907 단위).
- **2026-06-12 정합성 감사 P2 백로그 #874~#879 +8** (dead-code 제거 −6[#874] · C27 telegram escape +1[#875] · C10 pylint/bandit 방어 +5·C18 shebang +1[#876] · C14/C28/C11 +4[#877] · U3 render 가드 +1·C30 modify 0[#878] · CodeQL fix 0[#879], 4907→4915 단위).
- **2026-06-12 CodeQL #515 fix +1** (migration-completeness `_REGISTERED_MODELS` read 등록 검증 테스트, 4915→4916 단위).
- **2026-06-13 U2 effects.js 재초기화 +1** (test_hx_boost_listener_guards `test_effects_animations_reinit_on_hx_boost` 정적 가드, 4916→4917 단위).
- **2026-06-13 C1 save_gate_decision dead wrapper 제거 −2** (죽은-래퍼 전용 테스트 2개 제거: `test_save_gate_decision_updates_existing_record`=upsert UPDATE 분기 `test_gate_decision_repo::test_upsert_updates_existing` 중복 + `test_save_gate_decision_db_failure`=래퍼 미호출 side_effect 미발화 false-confidence; 35 inert patch de-indent·multi-patch 4·unused import 정리는 무증감, 4917→4915 단위).
- **2026-06-13 C12·C22·U1 머지 #884~#886 +23** (#884 C12 OTP rate-limit +11 [`_OtpAttemptLimiter` 단위 7 + telegram `_handle_connect` 통합 4] · #885 C22 diff 절단 마커 +10 [review_code 4 + result_dict 2 + gate 3 + telegram 반자동 1] · #886 U1 0027 RLS 의도적 divergence 구조단언 가드 +2, 4915→**4938** 단위).
- **2026-06-14 회고(5+1) P1 follow-up +1** (#888 회귀 가드 — 디스패처가 `_NOT_CONNECTED_MSG` 상수 직접 반환 ast 단언 `test_dispatcher_returns_not_connected_constant_directly`, 4938→**4939** 단위; README.ko 배지·db.md U1 노트는 무증감).
- **2026-06-14 회고 P2 #893~#895 +1** (#894 C22 절단 점수 NULL 회귀 가드 `test_save_and_gate_nulls_score_on_ai_truncated` +1; #893 P2-a 테스트 i18n 키 고정·#895 C12 OTP 6→8 은 단언/생성 변경이라 무증감, 4939→**4940** 단위).
- **2026-06-15 starlette 1.0 마이그레이션 #902 +2** (`test_route_helpers.py` registered_paths/route_name_count 견고성 가드 2 [prefix/Mount/중첩 6케이스 + count unique/missing/duplicate]; requirements 핀·라우트 등록 테스트 6 적응은 무증감, 4940→**4942** 단위).
- **2026-06-15 마이그레이션 0039/0040 멱등화 #904 +3** (`test_0020_round_trip` PG drift 행동 테스트 1 [운영 사고 재현·pg-concurrency 핀] + test_0039/0040 멱등 가드 정적 2, 4942→**4945** 단위).
- **2026-06-16 잔여/후속 #906~#908 +7** (#908 MIGRATION_DATABASE_URL — config 5 [migration_database_url default empty/postgres 정규화/supabase ssl/effective_migration_url fallback/precedence] + env.py ast 회귀 가드 2 [effective_migration_url 사용 강제·database_url 직접 사용 금지]; #906 railway.toml·#907 docs 무증가, 4945→**4952** 단위).
- **2026-06-16 회고 P2 #915 +3** (CODE-2 config Supabase SSL host/query-param 파싱 회귀 가드 — pooler SSL / credential `supabase.com` SSL 미강제 / 기존 query `&` 병합·sslmode 중복 방지, 4952→**4955** 단위; #916 docs-only 무증가). (`pytest --co` 단위 4955 + 통합 154 = 5109 수집).
- **2026-06-16 회고 P2 #919 +2** (CODE-3 env online connect_args URL 흐름 AST 가드 +1 · TEST-2 effective_migration_url 정규화 결합 +1, 4955→**4957** 단위). (`pytest --co` 단위 4957 + 통합 154 = 5111 수집).
- **2026-06-17 #921 차트 hx-boost race 가드 +8** (4 차트 템플릿[dashboard/analysis_detail/repo_insights/repo_detail] `typeof Chart` undefined early-return + vendor `<script>` onload no-anim 재빌드 + `_<scope>ChartReady` 노출 회귀 가드 `test_chart_race_guards.py` 8, 4957→**4965** 단위). (`pytest --co` 단위 4965 + 통합 154 = 5119 수집).
- **2026-06-17 품질감사 P2 #926 +6** (resilience logs JSONDecodeError 가드 1 + openai fallback 메트릭 대칭 1 + config validator 멀티필드 통합 회귀 가드 4 [fallback/worker postgres 정규화·빈-값 passthrough], 4965→**4971** 단위). (`pytest --co` 단위 4971 + 통합 154 = 5125 수집).
- **2026-06-17 repos 점수추이 차트 #929 +3** (`test_dashboard_loads_chartjs_in_repos_mode` 정적 가드 1 + repos 모드 Chart.js 로드 렌더 단위 2 [score_trend>1 로드·1점 경계 미로드], 4971→**4974** 단위; E2E `test_repos_mode_score_trend_chart_renders` +1 별도). (`pytest --co` 단위 4974 + 통합 154 = 5128 수집).
- **2026-06-18 AI 리뷰 max_tokens parse_error 근본 수정 #931 +4** (max_tokens 충분성 회귀가드 +1 + stop_reason 절단 마커 +1 + 정상 케이스 보존 +1 + settings configurable +1, 4974→**4978** 단위). (`pytest --co` 단위 4978 + 통합 154 = 5132 수집).
- **2026-06-18 repo_detail I18N 스코프 차트 fix #933 +1** (I18N 전역 스코프 정적 가드 +1 [window._repoChartI18N 고유 전역 노출 + 범용 window.I18N 할당 회귀 차단 + buildChart 지역 참조]; E2E repo_detail scoreChart +1 별도, 4978→**4979** 단위). (`pytest --co` 단위 4979 + 통합 154 = 5133 수집).
- **2026-06-18 개요 count-up 0/100 고착 안전망 + 이중 init P1 (commit 1c0a483/75f942e) +1** (`onceInView` IO-miss 가드 +1; 이중 init dispose 는 가드 교체(`_disposers in src` false-pass)라 무증가, E2E +3 별도, 4979→**4980** 단위). (`pytest --co` 단위 4980 + 통합 154 = 5134 수집).
- **2026-06-18 정적 자산 immutable 캐시 stale 사고 수정 +1** (`CachedStaticFiles` immutable+1년 → `no-cache` ETag; 기존 immutable 가드 교체, 4980→**4981** 단위). (`pytest --co` 단위 4981 + 통합 154 = 5135 수집).
- **2026-06-19 2nd-LLM 검증자 OpenAI-호환 base_url 일반화 +7** (`verifier_base_url` config default/env 2 + openai_client base_url SDK·httpx 양 경로 전달 + 기본값 회귀 가드 합계 4 + merge_verifier 전파 1 — OpenAI 비구독자도 무료 OpenAI-호환 공급자[GitHub Models 등]로 추가 비용 0 활성화, 4981→**4988** 단위).
- **2026-06-22 폼 입력 a11y aria-label #946 +23** (test_input_aria_labels 20 컨트롤 raw 템플릿 aria-label 정적 가드 parametrize + count-lock 1 + test_detail render-parity 신규 4키 ko/en 2, 4988→**5011** 단위). (`pytest --co` 단위 5011 + 통합 154 = 5165 수집).
- **2026-06-22 SonarCloud BLOCKER+CRITICAL 정리 #948~#950 +2** (CORS 미들웨어 순서 정적 가드 + 조건부 CORS 블록 reload 커버 테스트 2 [#948]; S1192 #949·S3776 #950 은 순수 refactor 무증가, 5011→**5013** 단위).
- **2026-06-22 후속 S6853 폼 라벨 #957 +9** (`test_label_associated_control.py` — for/id 연결 6 parametrize + dangling 부재 + telegram_link div 전환 + count-lock, 5013→**5022** 단위; #956 hook·#958 docs·#944/#945 deps 무증가).
- **2026-06-22 점수 NULL 절단 분리 #960 무증감** (입력 diff 절단을 `_persisted_score_is_unreliable` NULL 트리거에서 제거 → 절단 시 점수 유지; 회귀 가드 `test_save_and_gate_nulls_score_on_ai_truncated`→`test_save_and_gate_persists_score_on_ai_truncated` rename, 단위 불변 5022). (`pytest --co` 단위 5022 + 통합 154 = 5176 수집).
- **2026-06-23 native auto-merge SHA-atomicity fail-closed #962 +1** (`head_sha` 미확보 시 terminal[NETWORK_ERROR] — guardless merge 차단, enqueue 안 함, 5022→**5023** 단위). (`pytest --co` 단위 5023 + 통합 154 = 5177 수집).
- **2026-06-23 감사 보안/게이트 fail-open 봉인 3건 +4** (① auth fail-closed 재구성 +1[기본 503 + API_AUTH_DISABLED opt-out·http 휴리스틱 제거·기존 5 케이스 교체] · ④ static crash→incomplete +2[analyzer RuntimeError→incomplete·미설치 FileNotFoundError→현행 경계] · ③ retry sha-bound 불변식 +1[expected_sha=commit_sha 바인딩 가드], 5023→**5027** 단위). (`pytest --co` 단위 5027 + 통합 154 = 5181 수집).
- **2026-06-23 감사 P2 — markdown 인젝션 escape + 단일출처 2건 +13** (markdown 인젝션 escape 11[escape_markdown 단위 4·escape_slack_mrkdwn 단위 3·discord/slack/github issue.message escape 통합 3·discord ai_summary 보존 경계 1] + test_config claude_review_max_tokens 기본 8192 가드 2; merge_retry literal→merge_reasons 상수는 동작 불변 refactor 무증가, 5027→**5040** 단위). (`pytest --co` 단위 5040 + 통합 154 = 5194 수집).
- **2026-06-23 회고 follow-up P2 — github_issue escape +2** (P2-1 `_build_issue_body` bandit issue.message markdown escape 누락 4번째 채널 — escape_markdown 적용 회귀 가드 + ai_summary 보존 경계 2; DOC-DRIFT-1 cycle-history stale 정정·DQ-2 static 주석 정정·DQ-1 api.md ai_summary 비대칭 명문화는 docs/주석만 무증가, 5040→**5042** 단위). (`pytest --co` 단위 5042 + 통합 154 = 5196 수집).
- **2026-06-23 회고 도구 — docs/repo-integrity pre-commit 훅 +7** (check_docs_sync/check_toc_anchors stdlib 체커 회귀 가드 — 현재 repo 통과 + 합성 위반 적발 양방향 + github_slug em-dash 더블하이픈·dedup 단위, 5042→**5049** 단위; 스크립트 3종·.pre-commit wiring·testing.md 가이드는 무증가). (`pytest --co` 단위 5049 + 통합 154 = 5203 수집).
- **2026-06-23 repo-automation PR-H — 신규 훅 3종 +15** (check_env_vars_sync 3 + check_bilingual_comments 7 + check_config_5way_sync 5; 스크립트·pre-commit 배선 무증가, 5049→**5064** 단위). (`pytest --co` 단위 5064 + 통합 154 = 5218 수집).
- **2026-06-23 회고 P2 백로그 — .env.example footgun + 가드 파서 견고화 #971 +9** (NEW-GAP-1 `.env.example` `API_AUTH_DISABLED=1` 활성 출하 차단 가드 +1 + Codex mutual NG #2 파서 견고성 회귀 가드 +8 [plain/inline-comment/quote 2종/quoted+comment/export/주석 2종 parametrize]; GAP-5 conftest 마스킹 추적 주석·DQ-3 verifier 활성화 runbook·docs sync 무증가, 5064→**5073** 단위). (`pytest --co` 단위 5073 + 통합 154 = 5227 수집).
- **2026-06-23 repo-automation PR-W — 워크플로우 loop 단일출처 +4** (loop-until-dry drift 가드 4 [현재 repo 통과 + 합성 param-drift/invariant-missing/template-missing 적발 양방향]; `_lib/loop-until-dry.template.mjs` 정본·`integrity-audit.mjs` 명명 상수 리팩터·`retrospective.mjs` 신규는 .mjs 무증가, 5073→**5077** 단위). (`pytest --co` 단위 5077 + 통합 154 = 5231 수집).
- **2026-06-23 회고 follow-up — drift 가드 false-pass 봉인 +1** (주석-only 불변식 false-pass 회귀 가드 1 [#936 학습 재적용 — 주석 제거 후 매칭]; C3 W2 `/2`→`/${DRY_THRESHOLD}` 정정·C2 회고 보고서 아카이브·C6 retrospective runbook·C7 spec 헤더는 무증가, 5077→**5078** 단위). (`pytest --co` 단위 5078 + 통합 154 = 5232 수집).
- **2026-06-24 잔여작업 #977~#979 +7** (#978 retrospective.mjs 회복력 가드 +4 [try/catch + evidence 출력 + 주석 false-pass 봉인 합성 2] + #979 CI dead-symbol 가드 +3 [lint job `--isolated`/`$changed`/PR-only 단언]; #977 docs-only 무증가, 5078→**5085** 단위). (`pytest --co` 단위 5085 + 통합 154 = 5239 수집).
- **2026-06-24 R13 #985 +2** (bilingual 훅 cp949 버그픽스 회귀 가드 2 [encoding utf-8 정적 단언 + None-stdout 견고화]; native_automerge 주석·설계 docs 정정 무증가, 5085→**5087** 단위). (`pytest --co` 단위 5087 + 통합 154 = 5241 수집).
- **2026-06-24 R13 follow-up C10-d #987 +2** (retrospective.mjs UNVERIFIED bounded 재검증 회귀 가드 2 [재검증 존재 정적 단언 + 주석 false-pass 봉인]; .mjs/runbook 정정 무증가, 5087→**5089** 단위). (`pytest --co` 단위 5089 + 통합 154 = 5243 수집).
- **2026-06-25 전체 품질 감사 6 PR +27** (#989 env.py 완전성 정적 가드 +1 · #992 notifier P2[Slack i18n parse_error 현지화 1 + truncate 경계 6] +7 · #993 robustness P2[repo_path 인코딩 4 + DB config 하한 7 + 정상케이스/경계 2] +13 · #994 minor P2[grade 순서독립 + KeyError + 캐시 상한/만료/불변/evict 4 + ...] +6; #990 n8n docs·#991 quick wins[rename/cron] 무증가, 5089→**5116** 단위). (`pytest --co` 단위 5116 + 통합 154 = 5270 수집).
- **2026-06-25 CodeQL self-inflicted 봉인 +1** (#989 의 env.py 11 모델 전수 import 가 유발한 `py/unused-import` 9건[#528~536] → env.py `_REGISTERED_MODELS` 튜플 명시 참조 + 런타임 완전성 단언으로 봉인[test_migration_completeness.py 동일 패턴], AST 회귀 가드 `test_env_registers_every_imported_model_for_codeql` +1, 5116→**5117** 단위).
- **2026-06-29 B 백로그 3 PR — 품질감사 잔여 보류 구현** (#997 services-001 orphan 가드 +1 · #998 analyzer-pure-001 json_schema dead 가이드 제거 −5[tier3 load parametrize −1 · tier3 generic i18n −4] + 카운트 50→49 동기화 · #999 notifier-002 n8n chatId C-safe docs-only 무증가, 5117→**5113** 단위). (`pytest --co` 단위 5113 + 통합 154 = 5267 수집).
- **2026-06-29 cross-vendor 감사 3 fix PR** (#1006 P1-① crypto invalid-key startup 검증 +2 · #1007 P1-② STRICT_MIGRATION fail-fast +3 · #1008 P2[disabled_tools 주석 0036·`_sync_state` 예외확장·railway 비-dict 가드] +2, 5113→**5120** 단위). (`pytest --co` 단위 5120 + 통합 154 = 5274 수집).
- **2026-06-29 구조검토 후속 #1010~1013 +1** (#1012 integrity-audit.mjs C10 회복력 가드 +1 [test_retrospective_resilience.py 의 integrity-audit completeness try/catch 격리 가드]; #1010 apply-now-safe docs 9건·#1011 services.md path-scoped rule·#1013 gitignore 정리는 무증가, 5120→**5121** 단위). (`pytest --co` 단위 5121 + 통합 154 = 5275 수집).
- **2026-07-03 #1021 감사 note 하드닝 +13** (N1 operations days 상한[API+HTML] · N2 config locale 멤버십 · N3 git rename 파싱 회귀, 5121→**5134** 단위). (`pytest --co` 단위 5134 + 통합 154 = 5288 수집)
- **2026-07-03 5+1 회고 fix — C3 가격 parity +5** (`test_pricing_parity.py` 3-소스 정합 5 [#1024], 5134→**5139** 단위).
- **C2 dual-import 가드 +11** (`check_dual_import` 순수함수 9 + CI 배선 메타 2 [#1027], 5139→**5150** 단위). (`pytest --co` 단위 5150 + 통합 154 = 5304 수집).
- **2026-07-08 C1 비용 메트릭 DB 영속화 (feat/cost-metrics-persistence)** — claude_api_calls 모델+마이그레이션 0043+RLS · claude_api_cost_repo(record+user_cost_summary) · log_claude_api_call fail-safe DB 영속화+repo_id/user_id 귀속 · dashboard 월 비용 KPI+i18n · 경계/fail-safe 테스트 (이전 트레일 5150 + #1033~#1035 머지분 + C1 → 실측 **5197** 단위). (pytest --co 단위 5197 + 통합 154 = 5351 수집).
- **2026-07-08 설정 저장 in-flight 버튼 로딩 (feat/settings-save-feedback) +3** (test_settings_save_feedback.py — htmx 로딩 속성/label-spinner 마크업/saving 3로케일 정적 가드; 직전 #1036 DOC_REVIEW_GATE_DISABLED 등 머지분 미추적 +6 실측 재집계 흡수 → pytest --co 단위 **5206** + 통합 154 = 5360 수집).
- **2026-07-09 개요 점수 0/100 count-up 고착 fix (fix/overview-countup-cross-closure) +2** (`dataset.cuBound`/`sbBound`/`fbBound` 교차 클로저 가드; E2E +1 별도 121→122 — warmup 이 고착을 마스킹했다; pytest --co 단위 **5208** + 통합 154 = 5362 수집).
- **2026-07-09 설정 옵션 간소화 (feat/settings-simplification) +9** (가드 9; 고아 i18n `badge_advanced` 제거로 `_KEYS` −6 → 순증 +3; 🔴 `form=` 누락=데이터손실 — opus 리뷰 적발, 단위 **5211** + 통합 154 = 5365 수집).
- **2026-07-09 설정 옵션 설명 가독성 (feat/settings-desc-readability) +46** (test_settings_desc_readability.py — typography(`--text-desc` color-mix 중간대비·12px·lh) + 8키 3로케일 copy 간결화(`<br>` 제거·장황 단축) 정적 가드 46[6키×3로케일 no-br 18 + 8키×3 존재 24 + CSS 4]; UI-only·백엔드 불변 → pytest --co 단위 **5257** + 통합 154 = 5411 수집).
- **2026-07-09 모델 select 세로배치 fix (fix/settings-model-select-layout) +1** (test_ai_review_model_stacks_select_and_hint — B-1 이 review_model 흡수 시 `.field-row` 대신 `.ai-review-model` bespoke 래퍼로 만들어 select+설명이 같은 줄 inline 노출된 회귀 → `.ai-review-model { flex-direction:column }` 세로배치 정적 가드; #1043 설명 확대로 노출됨 → 단위 5258).
- **④ 비용 KPI legacy 필터 + RLS 0044 정합 +5** (claude_api_cost_repo `_owned_repo_ids_subquery` legacy repo(user_id NULL) 비용 포함 회귀 가드 + `_persist_cost` 실배선 테스트 2 + 마이그레이션 0044 claude_api_calls RLS legacy 절 정책 가드 3 — 회고 후속 ④ Codex mutual 적발 [app-layer 수정이 0043 RLS 로 무효화 → 0044 로 DB 레이어 정합] → 단위 5263).
- **② i18n _KEYS↔템플릿 양방향 가드 +2** (test_keys_match_template = set(_KEYS)==settings.html settings.* 참조 집합 강제 + test_keys_no_duplicates — #1041 손유지 목록 drift 봉인; 페어 = CLAUDE.md 6-step push-전 전체 tests/unit 게이트 + 정책 18 §2 → 단위 5265).
- **⑤ 설정 폼 orphan(form=) 가드 +2** (test_settings_form_membership = html.parser 로 settings.html 의 name= 컨트롤이 어느 `<form>` 에도 안 속하고 `form=` 없는 orphan 0 강제[#1041 form= 데이터손실 클래스] + detector 자기검증 — 구조적 멤버십만 검사라 필드-parity fragility 회피; 페어 = retrospective.mjs `code` 도메인 UX/시각 회귀 렌즈 명시[정책 8 "5종" 보존] → 단위 **5267** + 통합 154 = 5421 수집).
- **2026-07-17 Grok 백로그 NULL-owner IDOR + 워커 내구성 6 PR (#1060~#1066) +98** (#1060 +30 [repo 14 + pipeline durability 11 + RLS matrix + admin/pipeline] · #1061 +7 [affiliation 1 + pagination 1 + POST 502 4 + i18n 1] · #1062 +23 [쓰기 403×7 + 읽기 200×7 + 소유자×5 + i18n 2] · #1063 +11 [범위 6 + 경계 0/100 2 + merge<reject 1 + merge==reject 1 + reject=0 1] · #1064 +3 [소유자 비회귀 + NULL-owner 미노출 + unclaimed] · #1065 +5 [생성 경고 2 + 개요 배너 3] · #1066 0; baseline 5282 +30+7+23+11+3+5 = 5361 passed / **5365 수집**[+4 skipped] → 단위 **5365** + 통합 154 = 5519 수집).
- **2026-07-18 프리미엄 준비도 감사 Wave 0~2 코드전용 8 PR (#1068~#1075) +47** (#1068 PR 코멘트 AI-실패 경고 · #1069 retry 좁은 except rollback · #1070 result JSON 컬럼-select · #1071 config `is_production` 하드닝 · #1072 approve SHA 결속 · #1073 orphan sweep 배선+finish 위치이동 · #1074 feedback_status owner 필터+배선 가드 · #1075 retention sweep; baseline 5365 → 5408 passed / **5412 수집**[+4 skipped] → 단위 **5412** + 통합 154 = 5566 수집).
- **2026-07-18 세션2 회고 + fix 4 트랙 (#1077~#1086) +55** (5+1 회고 후 재발방지 기계 가드 — A1 카덴스 카운터 순수함수+셸 회귀 13 · A2 noqa-은닉 가드 순수함수+CI배선 14 · B1 hook 스모크 경로 파생 6 · B2 dead-code AST 참조 순수함수+CI배선 16 · P2#41 dashboard owner-filter parity AST 6; #1077/#1079 CodeQL #545 튜플-참조·C docs drift·D owed 원장은 무증가, baseline 5412 → 5463 passed / **5467 수집**[+4 skipped] → 단위 **5467** + 통합 154 = 5621 수집).
- **2026-07-18 세션2 후속 (#1088~#1092) +8 단위·+4 통합** (회고 P2 실행 — P2#36 repo-integrity CI backstop 메타 +3 · P2#18 begin_attempt fail-safe durability +1 · P2#17 merge_retry 4 종결경로 미러링 가드 +4; #1088 email/worktree docs·#1085 계열 무증가. 통합 = P2#43 retention PG round-trip 파일 +4[메타 1 + PG 3 skipif]. baseline 5467 → **5475 단위** + **158 통합** = 5633 수집).
- **2026-07-18 후속 2 (#1094) +5 단위** (자초 CodeQL py/empty-except 봉인 — `test_empty_except_guard.py`: 탐지기 긍정/부정 통제 4 + scripts//hooks 전역 AST 불변식 1. 주석 4곳 수정·subprocess encoding 수정은 무증가. baseline 5475 → **5480 단위** + **158 통합** = 5638 수집).
- **2026-07-19 회고 P0 2건 (#1095) +38 단위** (railway cron 무음실패 가드 19[탐지기 통제 8 + cron 5×2] · owed 카운터 순수함수 11 · SessionStart 배선 가드 8. baseline 5480 → **5518 단위** + **158 통합** = 5676 수집).
- **2026-07-19 회고 P1 가드 탐지기 (#1096) +10 단위** (noqa flake8 동형 분리 4 · git fail-CLOSED parity 7 중 신규 파일 7 — 합계 +10 실측). baseline 5518 → **5528 단위** + **158 통합** = 5686 수집).
- **2026-07-19 CodeQL 게이트 + dead-code 한정참조 (#1097·#1098) +23 단위** (CodeQL alert 게이트 12[순수함수 9 + CI 배선 메타 3] · dead-code 한정참조 11). baseline 5528 → **5551 단위** + **158 통합** = 5709 수집).
- **2026-07-19 인앱 스케줄러 (#1099) +1 단위 순증**(스케줄러 27 신규(커버리지 100%) · 구 cron 명령 가드 13 → 재발방지 4 로 대체). baseline 5551 → **5565 단위** + **158 통합** = 5723 수집 — 스케줄러 27[시각계산 7·기동조건 3·JOBS 배선 4·job 본문 5·루프 격리 2·생명주기 3·분기 3] + 재발방지 가드 4, 구 cron 명령 가드 13 대체).
- **2026-07-19 앱 로깅 설정 (#1100) +5 단위**(핸들러 부착·INFO 통과·멱등·DEBUG 부정통제·main 배선). baseline 5565 → **5570 단위** + **158 통합** = 5728 수집).
- **2026-07-19 세션4 — PR 머지 + tflint 조달 출처 가드 +7 단위**(#1116 fix-up +2 · 본 PR +5; 직전 트레일 5653 은 실측 5657 대비 4건 과소집계 → 5657+2+5 = **5664 단위** + **158 통합** = 5822 수집).
- **2026-07-19 세션4 후반 (#1119~#1126) +20 단위** (조달 출처 가드 5[#1119] · webhook URL 유출 3[#1122] · stdout 인코딩 가드 5[#1123] · 스케일링 가드 8[#1121] · 추출기 완전성 4[#1126, 기존 13 중 1건 단언 보강] — #1120·#1124·#1125 는 docs/config only 무증가. baseline 5664 → **5684 단위** + **158 통합** = 5842 수집).
- **세션5~7 통합 정산 (#1127~#1175) — 트레일 append 누락분 일괄 (회고 2026-07-22 P2 STATE-drift)** (5684→**5866** 단위·통합 158 불변 = **6024** 수집; 개별 PR 델타는 각 세션 종료 커밋·회고 아카이브[`docs/_archive/reports/`] 참조. 트레일이 세션4 에서 멈춰 헤더와 ~182 갭이던 것을 일괄 정산 — 세션별 재분해는 false-precision 회피 위해 생략).
- **세션8 종합감사 이행+5+1 회고+회고 P1 (#1194~#1201) +63** (5866→**5929** 단위 — P1-5 CAS·P2 5클러스터·회고 P1-A/B[dual-import 대칭·DATETIME 전수]; docs/backlog 이관·아카이브 보고서는 무증가).
- **세션8 감사 잔여 라운드 (#1202~#1211) +17** (5929→**5946** 단위 — 명확버그 8[#1204~#1208 · security_scan pagination #1210] · webhook issue-close BackgroundTask #1211 · 설계결정 5; #1202/#1203/#1209 docs·CAS 정확화는 무증가).
- **세션8 가드 self-defect 라운드 (#1213~#1215) +6** (5946→**5952** 단위 — B8 escape/alias 2 · arch-tree-sync cross-dir 2 · wiring-coverage path-comment/tautological 2; 전부 뮤테이션 red).
- **세션9~13 통합 정산 (#1217~#1267)** (5952→**6552** 단위 · 통합 158→**171** = 6723 수집 — 트레일이 세션8 에서 멈춰 있던 것을 일괄 정산[세션5~7 정산과 동일 방식], 개별 델타는 cycle-history·회고 아카이브 참조).
- **세션14 backlog 잔여 이행 (#1268~#1271) +55** (6552→**6607** 단위 — R16/R17 가드 +12 · R20 집행면 +13 · R31 훅 행동 +23 · R30/R24 관측면 +7; 통합 171 불변 = **6778** 수집, collect-only 실측 2026-08-02).
- **세션15 trailing sync (#1275·#1276) +14** (6607→**6621** 단위 = 6792 수집).
- **세션16 게이트 stdin 봉인 + 핀 ground-truth 가드 (#1279·#1280) +14** (6621→**6635** 단위 — stdin UTF-8 +5 · 핀 축 +9; 통합 171 불변 = **6806** 수집, collect-only 실측 2026-08-04).+ **세션16 2차 — 게이트 stdin·핀 가드 후속 (#1281·#1282) +7** (6635→**6642** 단위 — 프롬프트 캐시 구조 가드 7; 통합 171 불변 = **6813** 수집, collect-only 실측 2026-08-04).
- **세션16 3차 — claim-review 잔여 이행 (#1284) +12** (6642→**6654** 단위 — 가변 원천 캐시 분리 + 캐시 사망 감지 + 조용한 무력화 3경로 봉인; 통합 171 불변 = **6825** 수집, collect-only 실측 2026-08-05).
- **세션16 4차 — 죽은 기록 정리 + 구조화 출력 (#1285·#1286) +6** (6654→**6658** 단위 — 스키마·배선 가드 4 + 회귀 2; 통합 171 불변 = **6829** 수집, collect-only 실측 2026-08-05).
- **세션16 5차 — 구조화 출력 서비스 3경로 + 빈 env P0 (#1289) +3** (6658→**6661** 단위 — `output_config` 배선 가드 1 + 빈/명시 env 폴백 2; 통합 171 불변 = **6832** 수집, collect-only 실측 2026-08-05).
- **세션16 6차 — 문서 감사 P0~P2 (#1293) +14** (6661→**6675** 단위 — 이력 꼬리 축 4 + `--fix` 파생 2 + 절 유일성·산술 3 + memory-refs 범위 3 + e2e drift 2; 통합 171 불변 = **6846** 수집, collect-only 실측 2026-08-06).
- **세션16 7차 — CSP 가 자기 폰트를 차단하던 앱 결함 (#1294) +3** (6675→**6678** 단위 — CSP↔템플릿 정합 가드 2 + 대조군 1; 통합 171 불변 = **6849** 수집, collect-only 실측 2026-08-06).
- **세션16 8차 — CLAUDE.md 424→196줄 (Anthropic 200줄 기준) + 5+1 회고 반영·보존 (#1296) +32** (6678→**6710** 단위 — 행동 규칙 생존 가드 30 + 대조군 2; 통합 171 불변 = **6881** 수집, collect-only 실측 2026-08-06).
- **세션17 1차 — Anthropic 응답 첫-블록 가정 봉인 (#1297, R61) +20** (6710→**6730** 단위 — first_text_block 동작 12 + AST 배선 5 + 훅 동등성 1 + 대조군 2; 통합 171 불변 = **6901** 수집, collect-only 실측 2026-08-06).
- **세션17 2차 — e2e 공허화 3경로 봉인 (#1298, R58) +10** (6730→**6740** 단위 — skip→raise AST 2 + 범위 baseline fail-closed 4 + 배선 술어 4; 통합 171 불변 = **6911** 수집, collect-only 실측 2026-08-06).
- **세션17 3차 — 비용 로그 호출당 1행 (#1299, R63) +9** (6740→**6749** 단위 — 실행 관측 6 + AST 순서 2 + 단일 호출부 1; 통합 171 불변 = **6920** 수집, collect-only 실측 2026-08-06).
- **세션17 4차 — 실패 호출의 비용 토큰 보존 (#1300, R65) +11** (6749→**6760** 단위 — 실행 관측 8 + 실 DB 관통 1 + AST 리터럴 차단 1 + 로그 가시성 1; 통합 171 불변 = **6931** 수집, collect-only 실측 2026-08-06).
- **세션17 5차 — Code Scanning note 2건 해소 (#1302) +2** (6760→**6762** 단위 — e2e 폴링이 실패 이유를 버리지 않는지 1 + 그 이유가 메시지에 실리는지 1; 통합 171 불변 = **6933** 수집, collect-only 실측 2026-08-06).
- **세션17 6차 — pre-commit 설정 정정 + 표면 관측자 신설 (#1303, R56 Phase 0) +14** (6762→**6776** 단위 — 죽은 인터프리터 조합 차단 3 + entry 실재 7 + 설치 타입 계약 3 + autofixer exclude 2 중 중복 제외; 통합 171 불변 = **6947** 수집, collect-only 실측 2026-08-06).
- **세션17 7차 — pre-commit 관측자 결함 4종 봉인 + 실제 설치 (#1303, R56 Phase 1) +9** (6776→**6785** 단위 — 중화 훅 4형태 defeat + 죽은 인터프리터 + 타입 오선언 + 부분 설치 + PATH 무관 + 설정 대조; 통합 171 불변 = **6956** 수집, collect-only 실측 2026-08-06).
- **세션17 8차 — owed 원장 완전성 축 (#1304, R0-2) +8** (6785→**6793** 단위 — 원장 부재/빈 원장/정체/판정불가 4 + 대조군 2 + git 전용 배선 2; 통합 171 불변 = **6964** 수집, collect-only 실측 2026-08-06).
- **세션17 9차 — claim-review 트리거를 정책 19 에 맞춤 + TruffleHog Lob 오탐 봉인 (#1305, R57) +26** (6793→**6819** 단위 — 코드 표면 트리거 6 + 표면 목록·경로 산출 4 + Grok 지적 이행 4 + 합법 verdict 8 + Lob 오탐 가드 2 + 대조군 2; 통합 171 불변 = **6990** 수집, collect-only 실측 2026-08-07).
- **세션17 10차 — e2e required check 승격 + 이름 drift 가드 (R64) +3** (6821→**6824** 단위 — job 이름 리터럴 1 + 목록 비공허 1 + 조건부 if 금지 1; 통합 171 불변 = **6995** 수집, collect-only 실측 2026-08-07). 초판 `6840`/`7011` 은 계기 오염(`git ls-files` 3-stage, `6824+4×4`) — 사람이 틀린 게 아님. 봉인 `#1315`.
- **세션17 12차 — STATE 드리프트를 PR 시점에 차단 (P2) +10** (6824→**6834** 단위 — CI 배선 3 + stale 알리바이 차단 2 + 이월 마커 계약 3 + summary 배선 2; 통합 171 불변 = **7005** 수집, collect-only 실측 2026-08-07).
- **세션17 13차 — P1 역-뮤테이션 게이트 (#1310) +17** (6834→**6851** 단위 — 공허 테스트 차단 1 + 대조군 1 + 범위 2 + fail-closed 4 + 분류·three-dot 3 + 면제 2 + 배선 3; 통합 171 불변 = **7022** 수집, collect-only 실측 2026-08-08).
- **세션17 14차 — main red 관측자 (#1311, P3) +16** (6851→**6867** 단위 — 지속시간 산출 5 + 판정불가 4 + 보고내용 3 + advisory·무상태 2 + 배선 1; 통합 171 불변 = **7038** 수집, collect-only 실측 2026-08-08).
- **세션17 15차 — 🔴 예산제 (#1312, P4) +18** (6867→**6885** 단위 — 산식 5 + 증감 판정 6 + 면제 3 + 표면·배선 4; 통합 171 불변 = **7056** 수집, collect-only 실측 2026-08-08). 🔴 산식 고정: 🔴 **290**건 중 집행자 동반 **67건(23.1%)** — 22%/29% 가 공존하던 것을 재현 가능하게 확정.
- **세션17 16차 — required check 대기 중 auto-merge 포기 봉인 (#1314, R68) +12** (6885→**6897** 단위 — 대기 가능 승격 1 + 과도완화 대조군 1 + CI 상태 행렬 4 + 타 태그 대조군 2 + 예산 상한 1; 통합 171 불변 = **7068** 수집, collect-only 실측 2026-08-08).
- **세션17 17차 — 회고 P0 봉인 3건 + Grok 반증 반영 (#1315) +41** (6897→**6938** 단위 — 인덱스 오염 6 + PR 본문 리더 21 + 이월 운반체 12 + PR step 배선 2; 통합 171 불변 = **7109** 수집, collect-only 실측 2026-08-08). `6840` = 계기 오염(10차와 동일). Grok `019fe026` BROKEN — 이월 마커가 머지 tip 에 없어 push 도 범위로 읽게 고침.
- **세션17 18차 — 회고 P0 문서·원장 축 2건 + E2E 집행자 신설 (#1316) +11** (6938→**6949** 단위 — 회고 범위 기계 파생 5 + E2E 단일 출처 6; 통합 171 불변 = **7120** 수집, collect-only 실측 2026-08-08). 🔴 E2E 수치는 **집행자가 없어** STATE 안에서 자기 자신과 모순(121 vs 122)이었다 — 같은 문서·같은 세션에서 집행자 붙은 숫자는 100% 정확했고 안 붙은 숫자는 8곳이 틀렸다(회고의 가장 깨끗한 대조 실험).
- **세션19 1차 — 가드 표면 PR 의 claim-review 자기 면제 차단 (#1317) +30** (6949→**6994** 단위; 통합 171 불변 = **7165** 수집, collect-only 실측 2026-08-08). 사용자 *"필수로 승격"* — 관측자 저술 PR 은 `claim-review-not-required` 로 통과 불가. `session` 벤더 중립화(워크플로 run id). Grok `019fe089` BROKEN: 목록 밖 `tools/check_x.py` 면제 · docs-only 테스트가 `base==head`. 잔여 = R74.
- **세션19 2차 — 6-step ② 를 잴 수 있는 질문으로 교체 (R48) +15** (6994→**7009** 단위; 통합 171 불변 = **7180** 수집, collect-only 실측 2026-08-10). *"돌렸는가"* → *"본문 숫자가 기계값에서 파생됐는가"*. 오라클 #1305 −10 · #1310 −1 · #1312 −16(base drift 배제: tip=6819·6851·6885). 표+화살표 2종. 수치 없으면 *"미실행"*(안 적기 우회는 봇 PR 때문에 열어둠 = R76). 적대 `wf_9a4878aa-eab` BROKEN 4건 수용.
- **세션19 3차 — DB 자격증명 유출 실경로 봉인 (R8) +13** (7009→**7022** 단위 — alembic %-보간 8 + 리댁션 5; 통합 171 불변 = **7193** 수집, collect-only 실측 2026-08-10). 두 번 틀림: ① 원 기전(*SQLAlchemy 가 URL 을 예외에 담는다*)은 7표면 실측으로 거짓 ② 그래서 *"활성 유출 0"* 도 거짓 — `alembic/env.py` `set_main_option` 이 ConfigParser 보간으로 `ValueError` 에 URL 전문, `preDeployCommand` 가 매 배포 탄다. 계층 2 가 못 봄. 잔여 = R77. (#1326)
- **세션19 4차 — import 시점 설정 검증이 자격증명을 인쇄하던 축 봉인 (R77) +12** (7022→**7034** 단위; 통합 171 불변 = **7205** 수집, collect-only 실측 2026-08-10). R8 과 다른 축 — import 시점 pydantic 이라 로그 필터 미도달. 등재 처방(*validator 재발생*)은 거짓. Grok BROKEN: `(root)` loc 이 모델 전체를 인쇄. (#1327)
- **세션19 6차 — 감사·계획 산출물 리포 영속화 (인수인계 PR) +4** (7034→**7038** 단위 — 보고서 색인 +2 + 런북 색인 +2; 통합 171 불변 = **7209** 수집, collect-only 실측 2026-08-11). 스위트 후 색인을 등재하고 재측정 안 함 — 7034 를 두 번 보고. 이 세션에서만 같은 형태 3회(#1325·#1327·#1329). R48 본문 축이 #1329 CI red 로 잡음.
- **세션19 5차 — 실행 오인 위험 전역 차단 (문서감사 PR-1) +7** (7038→**7045** 단위; 통합 171 불변 = **7216** 수집, collect-only 실측 2026-08-11). 가드가 초록이던 이유 = 범위가 좁음(2배치 12건/0 → 넓히자 13건). `docs/superpowers/` 가 gitignore 인데 rglob 이 포함 → 로컬-only red. `git ls-files` 한정. Grok `019ff074` BROKEN: 주석 *"어디에 있든"* vs 스캔 2디렉토리 · 사유는 길이만. 확대는 잠복 개선이라 스캔 범위를 구조로 고정. (#1328)
- **세션19 7차 — SESSION_SECRET 3분기 문서 정합 (문서감사 PR-3) +8** (7045→**7053** 단위 — 3분기 실행 5 + 문서 정합 2 + `main` 배선 1; 통합 171 불변 = **7224** 수집, collect-only 실측 2026-08-11). 문서 3지점이 *"32자 미만이면 기동 실패"* 를 조건 없이 적었으나 기본값(31자)은 경고 후 기동. Grok 2라운드(`019ff0c3`·`019ff145`)가 봉인을 반증 — 픽스처가 배선을 가림. R79·R80. 운영 `UNVERIFIED`. 봉인 주장 안 함. (#1330)
> 🔴 **8차 결번 — 행을 추가하지 말 것** (R84). `#1331` 이 8차였다가 리베이스로 11차가 되며 번호만 비었다. 7차가 7053 으로 끝나고 9차가 7053 으로 시작해 수치 사슬은 이어져 있다. 2026-08-13 회고의 *"8차에 `#1335` 복원"* 처방은 귀속이 틀려 기각했다.

- **세션19 9차 — duration_ms 관측자 0 을 닫는다 (E1125 오탐 확정) +5** (7053→**7058** 단위 — 성공/예외 2 + 실경과 1 + 취소 1 + 호출 AST 1; 통합 171 불변 = **7229** 수집, collect-only 실측 2026-08-12). 계획서 E1125 는 오탐(`finally` 가 채움). 진짜 공백 = 단언 0건. ⑤ 이월 판단이 틀림. (#1332)
- **세션19 10차 — 문서 총량 감축 제안서 (실행 0건) +2** (7058→**7060** 단위 — 런북 색인 parametrize +2; 통합 171 불변 = **7231** 수집, collect-only 실측 2026-08-12). 제안서+색인만. Grok `019ff3d1` 초판 4축 WEAKENED 반영: backlog ✅ 잔여 20행 · 이력은 16k 창 밖이라 트리밍 이득 0 · 창 안 비대는 §작업 이력 38,449자 · `guards.md` 로드는 맥락 의존. Grok *"41행/50%"* 기각(R행 재측정 39/47%). 세션 오류 3건 중 정리가 막는 것은 ≤1.5건. (#1334)
- **세션19 11차 — README 충돌 마커 + pylint 진리값 (문서감사 PR-4) +23** (7060→**7083** 단위; 통합 171 불변 = **7254** 수집, collect-only 실측 2026-08-12). main 에 README 충돌 마커가 커밋돼 있었고 `--fix` 가 블록 안을 갱신하며 마커를 살리고 *"정합 ✅"*. pylint 배지 `10.00` vs 실측 **9.99** — 배지에서 floor 파생(9.99→9.985 exit 0 / 10.00→9.995 exit 18). 반올림 폭 0.005 만 뺌. Grok `019ff301` BROKEN 4건. 중간 트리에서 7081 로 적어 CI red — 측정 시점 문제(R30 아님). (#1331)
- **세션19 12차 — 이월 4건 일괄 종결 (trailing sync) +42** (7083→**7125** 단위 — 통합 171 불변 = **7296** 수집, collect-only 실측 2026-08-12). `#1335`·`#1337`·`#1336` 이월 + `#1331` 이 자기 +23 만 반영해 base 가 갈라짐. +42 는 네 PR 누적 — per-PR 귀속은 사후 재구성 불가. `#1337` 이 `deferral_carriers()` fail-open 을 봉인: 조회 실패 시 tip 면제 상속. docstring 의 *"fail-closed"* 는 tip 에 마커가 없을 때만 참이었고 `#1335` 첫 실사용이 main 을 red 로 만듦. (#1338)
- **세션19 13차 — 🔴 예산제에 분모 축 신설 (회고 P0①) +7** (7125→**7132** 단위 — 표면 삭제 축 5 + rename 대조 2; 통합 171 불변 = **7303** 수집, collect-only 실측 2026-08-13). `guards.md`+`docs.md` 삭제 시 무집행 221→171 인데 게이트 EXIT 0 — 분모를 못 봄. `missing_surfaces` 를 delta 앞에. `red-budget-exempt:` 로 삭제를 덮지 않음. M1 삭제 EXIT 1 / M2 정상 EXIT 0. (#1340)
- **세션19 14차 — 반례 일반화 규율 채택 +11** (7132→**7143** 단위 — AGENTS.md 어휘 생존 가드 11건; 통합 171 불변 = **7314** 수집, collect-only 실측 2026-08-13). 사용자 결정으로 R83 종결 — (A) 클래스 명명+다른 인스턴스 red 후에만 *"닫았다"* · (B) 뮤테이션 red 는 *"이 뮤테이션을 막았다"* 로만. `불변식 4` 로 안 붙임(30여 곳이 `3-불변식` 참조). 기계 집행 주장 안 함. (#1342)
- **세션19 15~17차 — 3층 분리 + 압축 + 공격적 재편 (배치 이월 종결) +5** (7143→**7148** 단위 — 4 PR 순변화; 통합 171 불변 = **7319** 수집, collect-only 실측 2026-08-14). 초판 산술이 안 닫힘 — `#1342` 가 STATE 를 이미 썼는데 이월 마커도 달아 이중 계상(+16 vs +5). 실제 이월: `#1345` +17 · `#1343` 0 · `#1344` −12(자기 커밋 −13, 여기 −12 는 `#1342` 머지 후 +관측 +1). 적대 `wf_d4c837bb-603`. 잔여 R88·R89. (#1346)
- **세션19 18차 — 5+1 회고 + P0 2건 이행 +9** (7148→**7157** 단위; 통합 171 불변 = **7328** 수집, collect-only 실측 2026-08-14). 회고 `wf_2b615d5e-8c5` P0 둘 다 이 세션 작품. (a) `#1345` 가 *"집행률 100%"* 선언과 같은 커밋에서 계수 밖 마커 30개 — 표면 6개로 확대 (b) 범위 손입력으로 `#1347` 이 회고를 피함. P0-B 진짜 기전: 오라클은 맞았고 3시간 회고 중 `#1347` 이 머지됨 → `scope_drift_during_run`. 검증 2종이 *"분모가 어디인가"* 는 안 물음. 잔여 R90~R92. (#1348)
- **세션19 19차 — 회고 결정 2건 이행 (R92 + 지표 절대값화) +19** (7157→**7176** 단위 — `check_open_decisions` 10 + 배선 1 + 지표 형식 2 + 한계 고지 1; 통합 171 불변 = **7347** 수집, collect-only 실측 2026-08-14). 재기 기전 0 → SessionStart advisory, 라이브 6건. 비율 «28%→100%» 두 번 다 분모가 움직임 → 절대값. Grok `019fffde` BROKEN — stderr `%`. (#1349)
- **세션19 20차 — 문서감사 PR-5 (게이트 예산 거짓 집행자 교체) + 원장 중복 정리 +3** (7176→**7179** 단위 — 전문 원천 1 + 85% 여유 1 + 크기 리터럴 금지 1 + 예산 길이 축 1; 통합 171 불변 = **7350** 수집, collect-only 실측 2026-08-14). `"pylint" in state_section` 을 README 배지 파싱으로 교체. 지문이 앞에 있으면 예산 축이 안 보여 길이 축을 넣음. R90=R71 중복. (#1350)
- **세션19 21차 — Grok 독립 검증 38건 전수 + R70·R94 해소 +12** (7179→**7191** 단위 — main-red 결론 판정 9 + owed 관측자 대조 2; 통합 171 불변 = **7362** 수집, collect-only 실측 2026-08-15). Grok 38건 독립 검증(세션 `01a00061`~`01a000ce`). 해소 2(R70·R94) · PARTIALLY_FIXED 6. 가장 값진 발견 = R46(무검증 점수가 KPI 에 혼입). 원장 오류 8건은 각 R행이 정본. 원장 구획 헤딩 인용으로 파서를 끊음 — 직전 owed 글리프와 같은 클래스(traps B5), 두 번 다 *"하지 않겠다"* 고 쓴 문장이 하게 만듦. (#1352)
- **세션19 22차 — R46 라이브 점수 결함 해소 (사용자 승인 High tier) +23** (7191→**7214** 단위; 통합 171 불변 = **7385** 수집, collect-only 실측 2026-08-15). NULL-persist 는 genuine AI 실패만, 나머지는 점수 유지·집계 제외. 고지 1/9→9/9. 실측 평균 71 → **90.0 · 제외 2**. Grok 초판 뮤테이션 0건 — CLI 픽스처가 `incomplete` 를 달아 분기 삭제해도 21 passed. (#1353)
- **세션19 23차 — R67 훅 경로 절대화 (사용자 승인 · Grok 저술) +16** (7214→**7230** 단위; 통합 171 불변 = **7401** 수집, collect-only 실측 2026-08-15). 훅 9종 cwd 상대 → `${CLAUDE_PROJECT_DIR:-.}/`. `_wiring_shape` lstrip('./') 가 `.claude` 점을 먹음. Grok `01a00214` BROKEN: 스키마 나열 4형태 GREEN → JSON 재귀 스캔. 봉인 아님. (#1354)
- **세션19 24차 — 문서 심의 게이트 원장 신설 (R80 선행 · Grok 저술) +20** (7230→**7250** 단위; 통합 171 불변 = **7421** 수집, collect-only 실측 2026-08-15). 조사가 R80 (a)를 반증 — 원장 0건이라 효과 측정 불가. 원장 먼저. Grok `01a0037a` 3건 — 훅 0바이트. RMW 155/160 → append **1/160**. (#1357)
- **세션19 25차 — `--fix` 가 원장에 거짓을 쓰던 P0 + 감축 관측자 신설 (Grok 저술) +25** (7250→**7284** 단위 — 영역 한정 계약 + 원장 가드 + 형제 패턴 3종; 통합 171 불변 = **7455** 수집, collect-only 실측 2026-08-15). 🔴 **`check_docs_sync --fix` 가 append-only 원장을 조용히 덮고 있었다** — `_STATE_CELL_TOTAL` 이 **파일 전역 첫-매치**라, §현재 수치 표기가 깨지면 2026-07-17 원장 항목 `**5365 수집**` 이 `**7421 수집**` 으로 덮이고 **`ok=True` + 재검증 True** 였다(실경로 재현). ⚠️ **라이브 오염은 없었다** — 세션 시작 시점과 현재 원장 값이 동일(`5365/5412/5467`). 발동 조건이 이번 세션에 성립한 적이 없다. 🔴 **claim-review 가 같은 클래스를 2건 더 찾았다**(`01a00434`) — `_README_BADGE` 는 README 선두 decoy 에 쓰고, `_STATE_HIST_*` 는 마지막 불릿 안 decoy 쌍을 SSOT 로 읽어 **틀린 누계를 파생 3지점에 전파**했다(후자가 원장 덮어쓰기보다 나쁘다). 셋 다 «매치가 정확히 1개» 계약으로 닫았다. 🔴 **새 가드의 테스트 3건이 자기 축을 안 쟀다** — `단절`·`항목`·`baseline` 이 **다른 축 메시지에 부분문자열로 살아 있어**, 판정 함수를 죽여도 초록이었다. 메시지 검사를 폐기하고 `Violation(axis, kind, data)` 구조 단언으로 교체했다. traps B5 를 내가 만든 가드에서 재생산한 것이다. 🔴 **예외 사유 16자 하한은 연극이었다** — `xxxxxxxxxxxxxxxx` 로 실제 단절을 침묵시켰다. 길이를 늘리지 않고 **상한 1건 + 리터럴 핀**으로 비용을 구조에 옮겼다(길이는 원리적으로 의미를 못 잰다). ⚠️ **못 막는 것을 배너에 인쇄한다**: 항목 수·문자 수·사슬 토큰을 유지한 **등가 길이 `X` 필러**는 통과한다(R81 클래스). 그리고 영역 한정과 사후 단언을 **동시에** 지우면 여전히 원장에 쓴다 — 각 층은 따로 red 다.
- **세션19 26차 — STATE 감축 4단위 + 다음 세션 인계 (Grok 저술) +2** (7284→**7286** 단위 — 신규 runbook 이 색인·헤딩 가드의 parametrize 대상이라 2 케이스 파생; 통합 171 불변 = **7457** 수집, collect-only 실측 2026-08-15). 🔴 **`docs/STATE.md` 113,955 → 55,043자 (−51.7%)** — 단위 1 세션19 21항목 압축(−69%) · 단위 2 `--fix` 가 append-only 원장을 덮던 P0 + 형제 2건 + 감축 관측자 신설 · 단위 3 원장 25항목 압축 · 단위 4 §작업 이력 46항목 전량 이관. ⚠️ **단위 4 는 감축이 아니라 이관**이라 리포 총량은 **+1,028자**다(본문 shingle 97%가 유일본이었다 — 선행 조사의 «34항목 중복» 은 제목 프록시 착시였다). 🔴 **내가 쓴 «세션 누적 −51.7%» 는 틀렸다** — 113,955 는 **감축 착수 직전**이고 세션 시작은 **98,685자**다. 세션 중 원장 항목을 더해 **+15,270 먼저 늘린 뒤** 줄였다. 세션 전체 기준은 **−44.2%** 이고 두 숫자는 정의가 다르다. Grok 이 인계 문서를 쓰며 적발했다. 🔴 **최대 사고는 과잉 절삭이었다** — 단위 3 이 PR 번호 귀속 · Grok 반증 기록 · 결함명 · `UNVERIFIED` 를 지웠는데 **가드가 전건 초록**이었다. 적대 검증이 4줄을 적발했고 나머지를 대조시키니 **10줄이 더** 나왔다(총 14줄). 사실 토큰만 복원했다(서사는 안 되살림). `traps` **C7** 로 등재 — *압축의 «무엇을 남길지» 는 기계가 못 잰다*. ⚠️ **고치지 않고 보고만 한 것 4건**: `check_toc_anchors` 가 헤딩 아래 항목 완전성을 안 본다 · 등가 길이 `X` 필러 · 예외 사유 진위 · 영역 한정과 사후 단언 동시 제거. 인계 문서 §4 가 정본이다.
