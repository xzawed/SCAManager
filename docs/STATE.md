# SCAManager 프로젝트 상태

> 현재 수치와 출처. 과거 작업 서사는 git 이력에 있다.

## 현재 수치 (2026-08-16 기준)

> 테스트 수가 바뀌면 파일 끝 SSOT 불릿 `(A→**B** 단위 … = **C** 수집)` 만 고치고 `py -3 scripts/check_docs_sync.py --fix` 를 돌린다. 종합 수치·추적셀 머리·README 2배지는 그 한 줄에서 파생된다. 날짜 헤더는 수치를 갱신한 세션 날짜로 맞춘다. 작업 서사는 여기에 쌓지 않는다.

**최신 (2026-08-16 — 문서 = 현재 코드 상태)**
- `docs/cycle-history.md`·`docs/backlog.md` 퇴역. 과거 서사는 git, 열린 일감은 GitHub Issues.
- 이 파일은 현재 수치 + 측정 방법만 유지한다. 테스트 수 SSOT = 파일 끝 불릿 한 줄.

**종합 수치**: 전체 **7237** 수집 (단위 **7066** + 통합 171) / E2E **121** (`#1291` 중복 제거 후; CI 120 통과 / 1 skip / 0 실패) / pylint **9.99/10** (`src/` — CI `lint-src` 가 `--fail-under` 를 README 배지에서 파생. `scripts/` 미게이트).

| 지표 | 값 | 비고 |
|------|-----|------|
| 전체 테스트 | **7237 수집** | `pytest tests/` — 단위 7066 + 통합 171 (현재). SSOT = 아래 §테스트 수 추적 이력 한 줄. |
| 통합 테스트 | **171개** | `py -3 -m pytest --collect-only -q tests/integration`. PG 전용은 `pg-concurrency` CI job, 로컬 미설정 시 skip. |
| E2E 테스트 | **121개** | `make test-e2e` (Chromium Playwright). = 121 collected (110 표준 + 11 perf). 성분 대조 = `scripts/check_e2e_scope.py`. `make test-perf` 로 perf 만. e2e ↔ `tests/integration` 동시 실행 금지 (`e2e/pytest.ini` 가 asyncio_mode 미설정). |
| SonarCloud Quality Gate | **OK** (2026-07-22 live API) | `api/qualitygates/project_status` |
| SonarCloud Security Rating | **A** | Vuln 0, Hotspots 0 (`api/measures/component`) |
| SonarCloud Reliability Rating | **A** (2026-07-22 live API) | bugs 0 · `api/measures/component` |
| SonarCloud Maintainability Rating | **A** (2026-07-22 live API) | Code Smells **145** (`api/measures/component`). BLOCKER/CRITICAL 0 이라 게이트 무영향. |
| SonarCloud BLOCKER / CRITICAL | **0 / 0** | 2026-07-22 재스캔 실측 |
| pylint | **9.99/10** | `python -m pylint src/` — 배지·STATE·ci.yml 이 10.00 을 주장했으나 실측은 9.99. 집행 = `scripts/check_docs_sync.py::check_lint_badge` + CI `--fail-under` 를 README 배지에서 파생. `scripts/` 미게이트. |
| 커버리지 | **Python 97% (2026-06-12 스냅샷 — 미재측정) / JS: E2E 커버** | Python: `py -3 -m pytest tests/unit --cov=src` (8497줄 중 291 미커버). 헤더 날짜가 최신이라 현재값으로 오독되기 쉬워 시점을 명시한다. 인라인 JS 는 Python cov 밖 — 언어별 분리 보고. |
| bandit HIGH | **0개** | bandit 1.9.4 (Python 3.12+) |
| flake8 | **CI 미게이트** (실측 14 E501 + 1 E131 = 15건 — `|| true` advisory) | `flake8 src/` |
| 지원 언어 (AI 리뷰) | **49개** | `src/analyzer/pure/language.py` — Tier1/2/3 가이드 |
| 지원 언어 (정적분석) | **27개** (등록 분석기 25종이 ≥1 지원) | (도구,언어) 쌍을 합산하면 중복. 고유 언어는 27. Semgrep 22 + ESLint/tsc 2 + ShellCheck·cppcheck·slither·rubocop·golangci-lint 각 1 + Python 3 + hadolint·ktlint·tflint·sqlfluff·yamllint·phpstan·swiftlint·stylelint·htmlhint·buf_lint·dart_analyze·psscriptanalyzer·dotnet_format·clippy |
| Tier1 정적분석 도구 | **25종** | pylint·flake8·bandit·semgrep·eslint·shellcheck·cppcheck·slither·rubocop·golangci-lint·hadolint·ktlint·tflint·tsc·sqlfluff·yamllint·phpstan·swiftlint·stylelint·htmlhint·buf_lint·dart_analyze·psscriptanalyzer·dotnet_format·clippy |
| pytest-asyncio | **1.4.0** | SSOT = Python 3.12 (CI `ci.yml` + Railway `.python-version`). 로컬 3.13 호환, 3.14 미검증. |
| CodeQL | **pass** | `.github/workflows/codeql.yml` 주 1회. README 배지와 페어 |

## 주요 파일 역할 (빠른 참조)

전체 트리·데이터 흐름은 [`docs/architecture.md`](architecture.md). 여기는 핫패스만.

| 파일 | 역할 |
|------|------|
| `src/constants.py` | 전역 상수 — 점수배점·감점·AI기본값·등급·알림한도·TTL·타임아웃 |
| `src/analyzer/pure/registry.py` | Analyzer Protocol + REGISTRY + `register()` + AnalyzeContext + AnalysisIssue + Category/Severity |
| `src/analyzer/io/tools/*.py` | 개별 분석기 — import 시 `register()`. `pure/` vs `io/` 분리 |
| `src/notifier/_common.py` | `format_ref` · `get_all_issues` · `truncate_message` |
| `src/notifier/_http.py` | `build_safe_client()` — SSRF 가드 + `HTTP_CLIENT_TIMEOUT` |
| `src/webhook/_helpers.py` | `get_webhook_secret()` + per-repo TTL 캐시(5분, 상한 있음) |
| `src/webhook/loop_guard.py` | 자기분석 루프 방지 3층 (kill-switch / bot sender / skip marker + rate). `is_whitelisted_bot()` |
| `src/webhook/router.py` | Webhook aggregator — providers 3개 (github·telegram·railway) |
| `src/gate/engine.py` | 3-옵션 Gate + GateDecision upsert + MergeAttempt 관측 |
| `src/gate/merge_reasons.py` | auto-merge 실패 사유 정규 태그 |
| `src/gate/merge_failure_advisor.py` | `get_advice(reason)` — 태그 → 권장 조치 (순수 함수) |
| `src/notifier/merge_failure_issue.py` | `create_merge_failure_issue()` — auto-merge 실패 Issue (dedup 24h) |
| `src/models/merge_attempt.py` | MergeAttempt ORM — score/threshold 스냅샷 + failure_reason |
| `src/shared/merge_metrics.py` | `parse_reason_tag` + `log_merge_attempt` |
| `src/repositories/` | DB 계층 13종 — repository / analysis / analysis_feedback / analysis_attempt / merge_attempt / merge_retry / gate_decision / repo_config / user / insight_narrative_cache / claude_api_cost / security_alert_log / issue_registration |
| `src/worker/pipeline.py` | 분석 파이프라인 + `build_analysis_result_dict` |
| `src/models/merge_retry.py` | MergeRetryQueue ORM — append-only claim |
| `src/repositories/merge_retry_repo.py` | `enqueue_or_bump` · `claim_batch` · mark_succeeded/terminal/expired — SKIP LOCKED |
| `src/gate/retry_policy.py` | `parse_reason_tag` · `should_retry` · `compute_next_retry_at` · `is_expired` |
| `src/github_client/checks.py` | `get_ci_status` · `get_required_check_contexts` (5분 TTL) |
| `src/services/merge_retry_service.py` | `process_pending_retries` — CI-aware 재시도 워커 |
| `src/gate/native_automerge.py` | `enable_or_fallback()` — GraphQL `enablePullRequestAutoMerge` 우선 + REST `merge_pr` 폴백 |
| `src/gate/_merge_attempt_states.py` | MergeAttempt.state 정규 상수 (LEGACY / ENABLED_PENDING_MERGE / ACTUALLY_MERGED / DISABLED_EXTERNALLY) |
| `src/github_client/graphql.py` | GraphQL POST + `enablePullRequestAutoMerge` + 5xx 재시도 |
| `src/static/vendor/chart.umd.min.js` | Chart.js UMD vendoring. `CachedStaticFiles` 로 노출. 사용 페이지 정본 = architecture.md |
| `src/main.py` `CachedStaticFiles` | `Cache-Control: no-cache` (ETag 재검증). 무버전 URL 이라 immutable 장기 캐시 금지 — 배포 후 구 JS/CSS 가 남는다. |
| `src/services/repo_insight_service.py` `compute_score_kpi` | cur/prev → avg_score/score_delta/grade. `repo_kpi` + `dashboard_service.repo_insight_cards` 공유 |
| `src/services/dashboard_service.py` `_fetch_analyses_for_window` / `_group_analyses_by_repo` | N+1 제거 — repo_ids IN + per-repo cap |
| `tests/conftest.py` | 환경변수 주입 + webhook secret / user_repos 캐시 autouse 클리어 |

## 테스트 수 추적 이력

> 이 절은 더 이상 이력이 아니다. 과거 179개 항목은 git 이력에 있다.
> 아래 **한 줄**이 `check_docs_sync.py` 의 SSOT 다. 테스트 수가 바뀌면 이 불릿의
> `(A→**B** 단위 … = **C** 수집)` 만 고치고 `py -3 scripts/check_docs_sync.py --fix` 를 돌린다.

- **현재** (7122→**7066** 단위; 통합 171 불변 = **7237** 수집)
