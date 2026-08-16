# SCAManager 프로젝트 상태

> 이 파일이 단일 진실 소스(Single Source of Truth)다. Phase 완료·주요 변경 시 여기를 먼저 갱신한다.

## 현재 수치 (2026-08-06 기준)

> 🔴 **2026-08-16: `docs/cycle-history.md` 는 삭제됐다** — 과거 세션·PR 서사의 단일 출처였고, 지금은 **git 이력**이 그 자리다. 아래 갱신 규칙의 «cycle-history 로 이관» 단계는 더 이상 수행하지 않는다(그 파일이 없다). 본 헤더는 **최신 1건 + 종합 수치만** 유지 — 32KB 단일 라인 SSOT 가독성 복원 (품질감사 docclr-1, 2026-06-17, cycle-history.md 에 서사 전량 보존[append-only] 확인 후 트리밍). 🔴 **다음 세션 갱신 규칙**: 신규 작업 완료 시 (0) **본 섹션 날짜 헤더(line 5 `## 현재 수치 (YYYY-MM-DD 기준)`)를 최신 세션 날짜로 갱신** (회고 2026-07-03 C5 #60 — 절차에서 상시 누락되던 필드), (1) 본 "최신" 블록을 새 작업으로 교체 + 종합 수치 갱신, (2) 직전 작업의 전체 서사는 `docs/cycle-history.md` 최신순 맨 앞에 본문 섹션으로 이관 (헤더에 "직전" 체인 누적 금지 — 본 정리의 회귀 방지), (3) **"최신" 블록은 불릿 5~8줄로 작성 — 단일 라인 금지** (2026-07-09 rank14: 단일 라인은 diff 심의·가독성 저해, doc_review_gate CRITICAL 게이팅 대상. 종합 수치 표·추적셀[테이블 셀]은 단일 라인 유지).

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

**종합 수치**: 전체 **7295** 수집 (단위 **7124** + 통합 171) / E2E **121** (`#1291` 이 중복 1건 제거) — CI 실측 **120 통과 / 1 skip / 0 실패**(`#1294`, 2026-08-06). 🔴 배선(`#1288`) 이래 **처음 전건 초록**이다: 스위트-앱 drift 30건(`#1291`) · CSP 가 자기 폰트를 차단하던 앱 결함 · CI 가 CSS 빌드 없이 돌던 설정 결함(`#1294`)을 순서대로 해소. backlog R52 / pylint **9.99/10** (src/ — 🔴 **CI `lint-src` job 이 `--fail-under` 를 **README 배지에서 파생**해 게이트**한다(2026-08-12 문서감사 PR-4 — 이전 리터럴 9.90 은 9.99 도 10.00 주장도 전부 통과시켰다). scripts/ 는 미게이트).

| 지표 | 값 | 비고 |
|------|-----|------|
| 전체 테스트 | **7295 수집** *(헤더 = 최신값, 이 셀 = pytest 누적 추적)* | `pytest tests/` — 단위 7124 + 통합 171 (현재). 현재 SSOT 는 **아래 §테스트 수 추적 이력** 한 줄이다. |
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

> 본문 전량(38,450자 · 46항목 · 2026-05-14~2026-06-12)은 2026-08-15 에 `cycle-history.md`
> 로 이관됐고, **그 파일은 2026-08-16 에 삭제됐다.**
> 🔴 **지금 그 46항목을 읽는 유일한 방법은 git 이다** — 예: `git show <삭제 직전 SHA>:docs/cycle-history.md`.
> 삭제 커밋 이전의 어느 리비전에서도 열린다. 아래 오프셋 표는 그때 이 파일이 어떻게 밀렸는지의
> 기록이라 **여전히 유효**하다(아카이브의 `STATE.md:N` 인용을 따라갈 때 쓴다).
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

> 이 절은 더 이상 이력이 아니다. 과거 179개 항목은 git 이력에 있다.
> 아래 **한 줄**이 `check_docs_sync.py` 의 SSOT 다. 테스트 수가 바뀌면 이 불릿의
> `(A→**B** 단위 … = **C** 수집)` 만 고치고 `py -3 scripts/check_docs_sync.py --fix` 를 돌린다.

- **현재** (7148→**7124** 단위; 통합 171 불변 = **7295** 수집)
