# SCAManager 프로젝트 상태

> 이 파일이 단일 진실 소스(Single Source of Truth)다. Phase 완료·주요 변경 시 여기를 먼저 갱신한다.

## 현재 수치 (2026-04-27 기준 — Phase 12 CI-aware Auto Merge 재시도 완료)

| 지표 | 값 | 비고 |
|------|-----|------|
| 단위 테스트 | **1709개** | pytest 9.0.3 (0 failed, 5 skipped — 3 Postgres-gated + 2 pre-existing) — 2026-04-27 로컬 실측 |
| SonarCloud Quality Gate | **OK** | CI #6 (2026-04-23) 반영 |
| SonarCloud Security Rating | **A** | Vuln 0, Hotspots 0 |
| SonarCloud Reliability Rating | **A** | Bugs 0 |
| SonarCloud Maintainability Rating | **A** | Code Smells 58 (-20 from 78) |
| SonarCloud BLOCKER / CRITICAL | **0 / 0** | Phase Q.7 완료 — 5건 Cognitive Complexity 전부 해소 |
| E2E 테스트 | **53개** | `make test-e2e` (Chromium Playwright) — Telegram 카드 +4 |
| pylint | **10.00/10** | `python -m pylint src/` — 만점 유지 |
| 커버리지 | **95%** | `make test-cov` — 신규 파일 100% (analytics_service, api/insights, ui/routes/insights) |
| bandit HIGH | **0개** | bandit 1.9.4 (Python 3.14 대응) |
| flake8 | **0건** | `flake8 src/` |
| 지원 언어 (AI 리뷰) | **50개** | language.py — Tier1/2/3 가이드 |
| 지원 언어 (정적분석) | **37개+** | Semgrep 22 + ESLint 2 + ShellCheck 1 + cppcheck 1 + slither 1 + rubocop 1 + golangci-lint 1 + Python 3 도구 |
| Tier1 정적분석 도구 | **10종** | pylint·flake8·bandit·semgrep·eslint·shellcheck·cppcheck·slither·**rubocop**·**golangci-lint** |
| pytest-asyncio | **1.3.0** | Python 3.14 DeprecationWarning 제거 완료 |

## 주요 파일 역할 (빠른 참조)

| 파일 | 역할 |
|------|------|
| `src/constants.py` | 전역 상수 단일 출처 — 점수배점·감점·AI기본값·등급·알림한도·TTL·타임아웃 |
| `src/analyzer/pure/registry.py` | Analyzer Protocol + REGISTRY + register() + AnalyzeContext + AnalysisIssue + Category/Severity StrEnum |
| `src/analyzer/tools/*.py` | 개별 분석기 — 모듈 로드 시 자동 register() 호출 |
| `src/notifier/_common.py` | notifier 공통 헬퍼 — format_ref, get_all_issues, truncate_message |
| `src/notifier/_http.py` | HTTP_CLIENT_TIMEOUT 적용 httpx 클라이언트 빌더 |
| `src/webhook/_helpers.py` | `get_webhook_secret()` + `_webhook_secret_cache` per-repo TTL 캐시(5분) |
| `src/webhook/router.py` | Webhook 라우터 aggregator — providers 3개 include |
| `src/gate/engine.py` | 3-옵션 Gate + GateDecision upsert (중복 INSERT 방지) + MergeAttempt 관측(Phase F.1) |
| `src/gate/merge_reasons.py` | auto-merge 실패 사유 정규 태그 상수 (Phase F QW5) |
| `src/gate/merge_failure_advisor.py` | `get_advice(reason)` — reason tag → 권장 조치 텍스트 (Phase F.3, 순수 함수) |
| `src/notifier/merge_failure_issue.py` | `create_merge_failure_issue()` — auto-merge 실패 GitHub Issue (Phase F.3, dedup 24h) |
| `src/models/merge_attempt.py` | MergeAttempt ORM — score/threshold 스냅샷 + failure_reason 태그 (Phase F.1, append-only) |
| `src/shared/merge_metrics.py` | parse_reason_tag + log_merge_attempt — DB INSERT + 구조화 로그 (Phase F.1) |
| `src/repositories/` | DB 접근 계층 8종 — repository_repo, analysis_repo, analysis_feedback_repo, merge_attempt_repo, gate_decision_repo, repo_config_repo, user_repo, merge_retry_repo |
| `src/worker/pipeline.py` | 분석 파이프라인 + build_analysis_result_dict |
| `src/models/merge_retry.py` | MergeRetryQueue ORM — 재시도 큐 (append-only claim 패턴) |
| `src/repositories/merge_retry_repo.py` | enqueue_or_bump · claim_batch · mark_succeeded/terminal/expired — 원자적 SKIP LOCKED 클레임 |
| `src/gate/retry_policy.py` | 순수 함수: should_retry · compute_next_retry_at · is_expired · mergeable_state_terminality |
| `src/github_client/checks.py` | get_ci_status · get_required_check_contexts (5분 TTL 캐시) |
| `src/services/merge_retry_service.py` | process_pending_retries — CI-aware 재시도 워커 |
| `tests/conftest.py` | 환경변수 주입 + _webhook_secret_cache autouse 클리어 |

## 작업 이력 (그룹별)

### 그룹 50 (2026-04-27 · SonarCloud 마이그레이션 + 전체 문서 정비 + docs 구조 재편)

**목표**: Phase 12 머지 후 CI 도구 현행화, 전체 문서 Phase 12 동기화, docs/ 디렉토리 구조 정비.

**변경 내용**:

| PR | 파일 | 변경 |
|----|------|------|
| #84 | `.github/workflows/ci.yml` | deprecated `sonarcloud-github-action@master` → `sonarqube-scan-action@v5` + `SONAR_HOST_URL` |
| #86 | `CLAUDE.md` | 핵심 데이터 흐름에 재시도 경로 추가, 단위 테스트 수 1709 반영 |
| #86 | `docs/STATE.md` | repositories 8종 카운트, Phase 12 파일 5개 역할 추가 |
| #86 | `README.md` | Phase 12 CI-aware Auto Merge Retry 섹션 추가 |
| #86 | `docs/reference/env-vars.md` | Phase 12 환경변수 7개 섹션 신규 추가 |
| #86 | `docs/guides/github-integration-guide.md` | check_suite 구독 확인 섹션 추가 |
| #86 | `docs/runbooks/merge-retry.md` | `MERGE_RETRY_CHECK_SUITE_WEBHOOK_ENABLED` + Stale Claim 복구 절차 추가 |
| #87 | `docs/_archive/` | 완료된 plan 7개·spec 7개·guide 3개·history 1개 → _archive 이동 (총 18개) |
| #87 | `docs/reports/artifacts/` | 재현 가능한 로그/JSON 19개 삭제 |
| #87 | `docs/design/INDEX.md`, `docs/agents-index.md` | Phase 12 항목 추가 |
| #87 | `docs/_archive/README.md` | 아카이브 기준 및 탐색 가이드 신규 작성 |

**닫은 PR**: #85 Dependabot `sonarqube-scan-action` v5→v6 — v6 BREAKING CHANGE("Project not found") 확인 후 닫음.

**추가된 규칙**: CLAUDE.md `### 병렬 에이전트 — 브랜치 충돌 방지` 섹션 (2026-04-27 세션 사고 교훈).

회고: [2026-04-27-phase12-docs-overhaul-retrospective](reports/2026-04-27-phase12-docs-overhaul-retrospective.md)

---

### 그룹 49 (2026-04-27 · Phase 12 CI-aware Auto Merge 재시도 완료 — T15 문서화)

**목표**: PR 자동 머지 시 `mergeable_state=unstable`(CI 진행 중) 또는 `unknown` 상태에서 단일 실패 대신 `merge_retry_queue`에 큐잉하여 최대 24시간 자동 재시도. `check_suite.completed` 웹훅 즉각 트리거 + 5분 cron fallback 이중 보장.

**신규 파일 (구현)**:

| 파일 | 역할 |
|------|------|
| `alembic/versions/0020_add_merge_retry_queue.py` | `merge_retry_queue` 테이블 DDL |
| `src/models/merge_retry.py` | `MergeRetryQueue` ORM |
| `src/repositories/merge_retry_repo.py` | `enqueue_or_bump`, `claim_batch`, `release_claim`, `mark_succeeded`, `mark_terminal`, `mark_abandoned`, `mark_expired`, `abandon_stale_for_pr`, `find_pending_by_sha` |
| `src/gate/retry_policy.py` | 순수 함수: `parse_reason_tag`, `should_retry`, `compute_next_retry_at`, `is_expired`, `mergeable_state_terminality` |
| `src/github_client/checks.py` | `get_ci_status`, `get_required_check_contexts` (5분 TTL 캐시, D2+D8 페이지네이션) |
| `src/services/merge_retry_service.py` | `process_pending_retries` 워커 |
| `docs/runbooks/merge-retry.md` | 운영 가이드 (T15 문서화) |

**신규 테스트 파일**:
- `tests/unit/gate/test_retry_policy.py`
- `tests/unit/github_client/test_checks.py`
- `tests/unit/services/test_merge_retry_service.py`
- `tests/unit/repositories/test_merge_retry_repo.py`
- `tests/unit/api/test_internal_cron_retry.py`
- `tests/unit/webhook/providers/test_check_suite_handler.py`
- `tests/unit/github_client/test_repos_webhook_events.py`
- `tests/unit/gate/test_auto_merge_enqueue.py`
- `tests/unit/ui/test_settings_webhook_banner.py`
- `tests/integration/test_retry_end_to_end.py`
- `tests/integration/test_retry_concurrency_postgres.py` (Postgres-gated, 3 skipped)
- `tests/unit/migrations/test_0020_round_trip.py`

**주요 수정 파일**:
- `src/constants.py` — `HANDLED_EVENTS`에 `"check_suite"` 추가
- `src/config.py` — retry 설정 7개 필드 추가
- `src/gate/engine.py` — retriable 실패 시 즉시 terminal 대신 큐잉
- `src/gate/github_review.py` — `merge_pr(expected_sha=...)` SHA atomicity (D1)
- `src/gate/merge_reasons.py` — 8-state taxonomy 확장 (D11)
- `src/github_client/repos.py` — `"check_suite"` WEBHOOK_EVENTS 추가, `update_webhook_events()`, `list_webhooks()` 헬퍼
- `src/api/internal_cron.py` — `POST /api/internal/cron/retry-pending-merges` 엔드포인트
- `src/webhook/providers/github.py` — `check_suite.completed` 핸들러 + `pull_request.synchronize` abandon-stale hook + 30초 디바운스
- `src/ui/routes/settings.py` — stale webhook 감지 (`_detect_stale_webhook`)
- `src/templates/settings.html` — `check_suite` 구독 누락 시 경고 배너
- `src/repositories/__init__.py` — `merge_retry_repo` export
- `railway.toml` — `*/5 * * * *` retry sweep cronJob 추가

**테스트 증분**: 1495 → **1709** passed (5 skipped — 3 Postgres-gated + 2 pre-existing)
**품질**: pylint 10.00 · bandit HIGH 0 · 커버리지 ~95%

---

### 그룹 48 (2026-04-26 · Insights 버그 수정 — PR #81)

**배경**: PR #80 머지 후 `/insights` 접근 시 500 에러 발생. `Repository.config` 속성이 존재하지 않음.

**변경 내용**:

| 파일 | 변경 |
|------|------|
| `src/ui/routes/insights.py` | `r.config` 접근 제거 → `RepoConfig` 직접 쿼리로 교체 |
| `tests/unit/ui/test_insights_routes.py` | StaticPool 실제 SQLite 회귀 테스트 추가 — ORM 속성 오류 감지 |

**교훈**: SessionLocal Mock 기반 테스트는 ORM 속성 오류를 감지하지 못함 → 핵심 라우트에 실 DB 경로 테스트 필요.

---

### 그룹 47 (2026-04-26 · Insights Phase A+B UX 고도화 — PR #80)

**배경**: 사용자가 Insights 탭의 UX를 개선 요청. 여러 에이전트 협의로 Phase A(빠른 개선)+B(중간 백엔드) 통합 구현.

**변경 내용**:

| 파일 | 변경 | 역할 |
|------|------|------|
| `src/services/analytics_service.py` | `repo_comparison()`에 `min_score/max_score` 추가 | 점수 분산 노출 |
| `src/ui/routes/insights.py` | leaderboard·top_issues·kpi dict 컨텍스트 추가, `_compute_kpi()` 헬퍼 | 페이지 데이터 풍부화 |
| `src/api/insights.py` | `/repos/compare` 응답에 `min_score/max_score` 포함 | API 일관성 |
| `src/templates/insights.html` | 체크박스 칩 리포 선택, JS 탭(리포 비교/리더보드), 등급 뱃지, min-max 범위 | UX 개선 |
| `src/templates/insights_me.html` | KPI 카드 4종, grade-boundary Chart.js 플러그인, top-5 이슈 섹션 | UX 개선 |
| `tests/unit/services/test_analytics_service_insights.py` | min/max 검증 2개 신규 | 회귀 방어 |
| `tests/unit/ui/test_insights_routes.py` | 라우트 컨텍스트 3개 신규 + 기존 2개 업데이트 | 회귀 방어 |

**결과**: 단위 테스트 1528→1533 (+5) · pylint 10.00/10 유지

---

### 그룹 46 (2026-04-26 · 문서 구조 개선 + 사고 전 방어 테스트 2종 — PR #77)

**배경**: 3-에이전트 협의로 도출한 "사고 이전 방어" 접근법. 5-way sync 누락과 로그 인젝션 방어 회귀를 CI에서 자동 감지.

**변경 내용**:

| 파일 | 변경 | 역할 |
|------|------|------|
| `CLAUDE.md` | 🧭 탐색 가이드 + 🔴 고위험 규칙 강조 + 섹션 순서 재정렬 | 작업 워크플로 일치 + 빠른 규칙 탐색 |
| `docs/reports/INDEX.md` | "현재 상태 바로가기" 섹션 + 누락 회고 2건 추가 | 문서 탐색 진입점 개선 |
| `tests/unit/test_repo_config_sync.py` | 신규 (3 tests) | RepoConfigData ↔ RepoConfigUpdate ↔ ORM 3-way 필드 완전 일치 정적 검사 |
| `tests/unit/shared/test_stage_metrics_robustness.py` | 신규 (10 tests) | stage_timer 예약 키 보호 + 엣지 케이스 — 로그 인젝션 방어 회귀 게이트 |

**CLAUDE.md 핵심 변경**:
- **🧭 탐색 가이드**: 상단에 상황→섹션 링크 테이블 추가 (신규 기능·파이프라인·Webhook·Phase 착수 등)
- **🔴 상위 3대 위반 박스**: asyncio_mode / batch_alter_table / ORM 컬럼 마이그레이션 누락
- **섹션 순서 재정렬**: 체크리스트 → 필수 원칙 (실제 워크플로 순서 반영)
- **완료 5-step**: ①커밋 ②PR ③push ④STATE.md ⑤CLAUDE.md 아키텍처 동기화
- **CLAUDE.md 동기화 체크리스트**: 신규 파일·ORM·API·메트릭 추가 시 갱신 항목 테이블

**테스트 증분**: +13 (1515 → **1528** passed)
**품질**: pylint 10.00 · bandit HIGH 0

---

### 그룹 45 (2026-04-26 · 툴링 안전장치 — PR #76)

**배경**: PR #74(leaderboard_opt_in 500 에러)와 PR #75(pytest e2e 혼입 446건 실패) 발견 사항의 **재발 방지** 자동화.

**변경 내용**:

| 파일 | 변경 | 역할 |
|------|------|------|
| `pytest.ini` | `testpaths = tests` 추가 | 경로 없이 `python -m pytest` 실행 시 `e2e/` 수집 방지 |
| `tests/unit/test_migration_completeness.py` | 신규 (67 parametrized) | ORM 컬럼 전수 검사 — Alembic 마이그레이션 파일에 컬럼명 존재 여부 정적 확인 |

**migration completeness 테스트 동작 원리**:
1. 7개 ORM 모델 import → `Base.metadata` 테이블/컬럼 등록
2. `alembic/versions/*.py` 전체 읽어 단일 검색 텍스트로 합침
3. `(테이블명, 컬럼명)` 쌍마다 정규식 검색 (`'column'` 또는 `\bcolumn\b`)
4. 누락 시 `make revision m="설명"` 안내 메시지와 함께 실패

**테스트 증분**: +67 (1448 → **1515** passed)

### 그룹 43 (2026-04-26 · Phase 11 팀/멀티 리포 인사이트 완료 — PR #72)

**목표**: 개발자별 점수 추세 + 멀티 리포 비교 뷰 + 옵트인 리더보드. Phase 10 `analytics_service.py` 확장.

**신규 파일**:

| 파일 | 역할 |
|------|------|
| `alembic/versions/0018_add_analysis_author.py` | `analyses.author_login String NULL` + 인덱스 — backfill 없음 |
| `src/api/insights.py` | `GET /api/insights/authors/{login}/trend`, `/repos/compare`, `/leaderboard` — `require_api_key` |
| `src/ui/routes/insights.py` | `GET /insights` (리포 비교), `GET /insights/me` (본인 추세) |
| `src/templates/insights.html` | 멀티 리포 비교 페이지 — 리포 셀렉터 + 비교 표 |
| `src/templates/insights_me.html` | 개인 추세 대시보드 — Chart.js 라인 차트 + 추세 표 |
| `tests/unit/services/test_analytics_service_insights.py` | 9 테스트 — author_trend 4 + repo_comparison 2 + leaderboard 3 |
| `tests/unit/api/test_insights_api.py` | 9 테스트 — 엔드포인트 3종 + 인증 + 빈 파라미터 분기 |
| `tests/unit/ui/test_insights_routes.py` | 5 테스트 — save/restore require_login 격리 패턴 |
| `tests/unit/worker/test_extract_author_login.py` | 8 테스트 — PR/push/None 경계 케이스 |

**수정 파일**:
- `src/models/analysis.py` — `author_login = Column(String, nullable=True, index=True)` 추가
- `src/worker/pipeline.py` — `_extract_author_login()` 추가 + Analysis 저장 시 author_login 설정
- `src/services/analytics_service.py` — `author_trend`, `repo_comparison`, `leaderboard` 함수 추가 (Phase 10 산출물 확장)
- `src/models/repo_config.py` — `leaderboard_opt_in: bool = False` 컬럼 추가
- `src/config_manager/manager.py` — `RepoConfigData.leaderboard_opt_in` 추가
- `src/api/repos.py` — `RepoConfigUpdate.leaderboard_opt_in` 추가
- `src/ui/routes/settings.py` — `leaderboard_opt_in` 폼 처리 추가
- `src/templates/settings.html` — 카드 ③ `leaderboard_opt_in` 토글 추가 (PRESETS 제외)
- `src/templates/base.html` — nav "Insights" 링크 추가
- `src/ui/router.py` — `insights.router` 등록 (routes 5 → 6개)
- `src/main.py` — `api_insights_router` 등록

**핵심 설계 결정**:
- `leaderboard_opt_in`: 기본 False, PRESETS 9개 제외 — 팀 합의 후 명시 옵트인 필요
- `Analysis.author_login` NULL 정책: backfill 없음. 모든 집계 `WHERE author_login IS NOT NULL`
- leaderboard 안전 가드: `opted_in_repo_ids` None 또는 빈 리스트면 즉시 `[]` 반환 — 의도치 않은 게이미피케이션 방지
- RepoConfig → repo_id 해결: RepoConfig에 `repo_id` FK 없음 → 2-query lookup (RepoConfig → full_name → Repository → id)
- 테스트 격리 버그 수정: `test_insights_routes.py`가 `require_login` override 저장/복원 패턴으로 `test_router.py` 영구 override 삭제 방지

**테스트 증분**: +31 (1417 → **1448** passed)
**품질**: pylint 10.00 · bandit HIGH 0 · 커버리지 95% (신규 파일 전체 100%)

### 그룹 44 (2026-04-26 · hotfix — 설정 페이지 500 에러 수정 PR #74)

**원인**: Phase 11(PR #72)에서 `RepoConfig` ORM에 `leaderboard_opt_in` 컬럼을 추가했으나 Alembic 마이그레이션 파일이 누락됨. 단위 테스트는 in-memory SQLite로 ORM 정의에서 직접 테이블을 생성하기 때문에 테스트 통과 → 그러나 운영 DB에는 컬럼 미생성 → `GET /repos/{name}/settings` 500 Internal Server Error.

**수정**: `alembic/versions/0019_add_repo_config_leaderboard_opt_in.py` 신규 작성 (`server_default='0'`).

**재발 방지**: CLAUDE.md "DB / 마이그레이션" 섹션에 **ORM 컬럼 추가 시 마이그레이션 필수 동반** 규칙 명시.

### 그룹 42 (2026-04-26 · Phase 10 Telegram 확장 완료 — PR #64)

**목표**: 주간 리포트 cron + 트렌드 알림 + Telegram 인라인 명령 (`/stats`, `/settings`, `/connect`) + OTP 연결 흐름.

**신규 파일**:

| 파일 | 역할 |
|------|------|
| `src/services/analytics_service.py` | 집계 단일 출처 — `weekly_summary`, `moving_average`, `top_issues`, `resolve_chat_id` |
| `src/services/cron_service.py` | 주기적 실행 — `run_weekly_reports`, `run_trend_check` |
| `src/api/internal_cron.py` | `POST /api/internal/cron/weekly|trend` — `INTERNAL_CRON_API_KEY` 전용 인증 |
| `src/api/users.py` | `POST /api/users/me/telegram-otp` — 6자리 OTP 발급 (5분 만료) |
| `src/notifier/telegram_commands.py` | `/stats`, `/settings`, `/connect` 명령 처리 + OTP 검증 |
| `alembic/versions/0017_add_user_telegram_id.py` | `users.telegram_user_id UNIQUE` + `telegram_otp` + `telegram_otp_expires_at` |

**수정 파일**: `src/webhook/providers/telegram.py` (message.text / cmd: 분기), `src/gate/telegram_gate.py` (`_make_callback_token` scope 일반화), `src/models/user.py`, `src/repositories/user_repo.py`, `src/main.py` (라우터 등록), `src/config.py` (`internal_cron_api_key`), `railway.toml` (cron 2개), `src/templates/settings.html` (OTP 카드 ⑤)

**테스트 증분**: +73 (1344 → **1417** passed)
**품질**: pylint 10.00 · bandit HIGH 0 · 커버리지 96.5%

### 그룹 41 (2026-04-26 · Phase 9 자기 분석 루프 방지 완료 — PR #62)

**목표**: SCAManager 자체 리포를 등록해 dogfooding하면서 봇 발신/자기 분석 무한 루프를 3-layer 방어로 차단.

**신규 파일**:

| 파일 | 역할 |
|------|------|
| `src/webhook/loop_guard.py` | `is_bot_sender()` + `has_skip_marker()` + `BotInteractionLimiter` (시간당 6회 상한) |
| `docs/runbooks/self-analysis.md` | 자기 분석 활성화/비활성화 운영 가이드 |

**수정 파일**: `src/webhook/providers/github.py` (`_loop_guard_check()` 삽입 — Kill-switch + BOT_LOGIN_WHITELIST 체크)

**테스트 증분**: +29 (1315 → **1344** passed)
**품질**: pylint 10.00 · bandit HIGH 0

### 그룹 40 (2026-04-26 · 문서 다중 에이전트 심의 시스템)

**배경**: Claude가 중요 문서(CLAUDE.md·STATE.md·에이전트·스킬 정의)를 수정할 때 단일 관점으로 인한 맹점을 방지하기 위해 3개 전문 에이전트가 병렬 심의하는 PreToolUse Hook 시스템 구축. 사용자 가시성보다 Claude 판단 정확성 확보가 핵심 목적.

**신규 파일**:

| 파일 | 역할 |
|------|------|
| `.claude/hooks/doc_review_gate.py` | PreToolUse Hook 진입점 — 등급 분류→병렬 에이전트 호출→거부권 적용→차단/경고/통과 |
| `.claude/agents/doc-impact-analyzer.md` | 행동 변화 감지 에이전트 — 규칙 삭제·조건 변경·예외 추가 검출 (Critical+Important 차단) |
| `.claude/agents/doc-consistency-reviewer.md` | 교차 문서 일관성 검토 에이전트 — 수치 불일치·모순 규칙 검출 (Critical만 차단) |
| `.claude/agents/doc-quality-reviewer.md` | 문서 품질 검토 에이전트 — 모호한 표현·이중 해석 감지 (경고만, 차단 없음) |
| `tests/unit/hooks/test_doc_review_gate.py` | 32개 단위 테스트 — 등급 분류 14 + 거부권 매트릭스 9 + API 병렬 호출 4 + main() 통합 5 |
| `docs/_archive/2026-04-26-doc-review-gate-design.md` | 설계 문서 (archived) |
| `docs/_archive/2026-04-26-doc-review-gate.md` | 구현 계획 문서 (archived) |

**주요 설계 결정**:
- Anthropic Haiku 4.5 병렬 호출 (`asyncio.gather`) → 목표 20초 이내
- API 실패 시 차단 금지 (graceful degradation) — 심의 시스템이 단일 장애점이 되지 않도록
- JSON 코드 블록 우선 파싱 + json.loads fallback — 에이전트 응답에 중괄호 포함 시 파싱 실패 방어
- `.claude/settings.json`에 `doc_review_gate.py` 60초 타임아웃으로 등록 (matcher: Write|Edit|MultiEdit)

### 그룹 39 (2026-04-25 · 보안 강화 — GitHub 봇 클론 사고 대응)

**배경**: GitHub 봇이 프로젝트 리포를 클론하고 있다는 보고에 따라 5개 병렬 에이전트(비밀정보·인증·입력검증·의존성CVE·공격면) 전면 감사 후 12개 보안 이슈 수정 완료.

**수정 내역**:

| # | 영역 | 수정 내용 | 심각도 |
|---|------|---------|--------|
| 1 | `src/main.py` | `SecurityHeadersMiddleware` 추가 — X-Content-Type-Options, X-Frame-Options, HSTS(prod) | HIGH |
| 2 | `src/main.py` | 프로덕션(HTTPS)에서 `/docs` `/redoc` `/openapi.json` 비활성화 | HIGH |
| 3 | `src/main.py` | `/health/tools` 디버그 엔드포인트 제거 — 도구 경로 노출 차단 | HIGH |
| 4 | `src/main.py` | `/health` 응답에서 `active_db` 필드 제거 — 내부 DB 상태 노출 차단 | MEDIUM |
| 5 | `src/auth/github.py` | Session Fixation 방어 — `session.clear()` before `user_id` 저장 | HIGH |
| 6 | `src/analyzer/io/static.py` | TOCTOU tempfile 수정 — `NamedTemporaryFile` → `TemporaryDirectory` | MEDIUM |
| 7 | `src/ui/routes/settings.py` | SSRF 방어 — `_is_safe_webhook_url()` + `_BLOCKED_HOSTS` (사설 IP·메타데이터 차단) | HIGH |
| 8 | `src/gate/telegram_gate.py` + `telegram.py` | HMAC 128-bit 절단 명시 문서화 — Telegram 64바이트 한도 준수 | MEDIUM |
| 9 | `src/api/auth.py` | 운영환경 API_KEY 미설정 시 503 차단 (개발환경은 경고+통과 유지) | HIGH |
| 10 | `src/github_client/repos.py` | Pre-push 훅 heredoc 주입 수정 — `cat << PROMPT` → python3 env var 방식 | MEDIUM |
| 11 | `src/gate/engine.py` + `github.py` | 예외 로깅 정보 노출 — `exc` → `type(exc).__name__` | MEDIUM |
| 12 | `requirements.txt` | CVE 의존성 업그레이드 — authlib≥1.6.11, starlette≥0.47.2, python-multipart≥0.0.26, cryptography≥46.0.7 | HIGH |
| 13 | `requirements-dev.txt` | CVE-2025-71176 — pytest 8.3.3 → ≥9.0.3 (tmpdir race condition) | MEDIUM |

**테스트 증분**: +4 (security headers, /health/tools removed, API key prod-503, API key dev-200)

**Dependabot 알림**: 2건 (CVE-2025-71176 pytest) — 패치 후 수동 dismiss 완료.

### 그룹 38 (2026-04-25 · 이중언어 주석 마이그레이션 완료)

**목적**: 영어권 컨트리뷰터·외부 감사·CodeRabbit/SonarCloud 같은 외부 검토 도구가 코드 의도를 이해할 수 있도록 전 코드베이스 한글 주석에 영어 번역을 병행. CLAUDE.md 이중언어 규칙(신규 코드 기준)을 기존 코드에 소급 적용하는 1회성 마이그레이션.

**대상 규모**:
| 영역 | 파일 | 한글 라인 |
|------|-----|----------|
| `src/` (Python) | ~145 | ~750 |
| `tests/` + `e2e/` | ~81 | ~170 |
| Makefile, CI, scripts, codecov, sonar | ~7 | ~80 |
| `src/templates/*.html` 개발자 주석 | 3 | 41 |

**제외 영역**: `.claude/`, `alembic/versions/`, `src/templates/*.html` UI 카피, `src/analyzer/pure/review_prompt.py` (LLM 프롬프트), `src/analyzer/pure/review_guides/` (LLM 체크리스트), `docs/`

**Phase별 완료**:

| Phase | 범위 | 처리 방식 |
|-------|-----|---------|
| P0 | 자동화 도구 작성 | `check_bilingual.py` 검증기 + `glossary.md` + `manifest.json` |
| P1 | 핵심 설정·런타임 5파일 (constants.py, config.py, database.py, main.py, alembic/env.py) | 수작업 |
| P2 | src/ TOP 20 모듈 (crypto.py, formatter.py, repos.py, calculator.py, ...) | 수작업 |
| P3 | src/ 잔여 ~125 파일 | 수작업 (일괄 패치 스크립트 활용) |
| P4 | tests/ + e2e/ ~81 파일 | `_apply_test_translations.py` 배치 스크립트 (166쌍) |
| P5 | Makefile, CI yml, codecov, sonar, benchmark_static_analysis.py, HTML 41건 | 수작업 + `_apply_html_translations.py` |

**자동화 도구** (`scripts/i18n_comments/`):
- `check_bilingual.py` — 한글-only 잔존 라인 검증기 (KOREAN_RE + 4가지 이중언어 판정 기준)
- `_apply_test_translations.py` — tests/e2e 166쌍 배치 변환 (1회성)
- `_apply_html_translations.py` — HTML <!-- --> 41건 슬래시 포맷 변환 (1회성)
- `glossary.md` — 30개 도메인 용어 사전

**주석 포맷 규칙**:
- 단독 `#` 라인: `# 한글\n# English` (두 줄 분리)
- 인라인 `# 한글`: `# 한글 / English` (슬래시 형식)
- docstring: 한글 줄 + 빈 줄 + English 줄
- HTML 주석: `<!-- 한글 / English -->`

**회귀 없음**: 1296 passed (마이그레이션 전후 동일, 주석-only 변경).

### 그룹 37 (2026-04-25 · Phase H 착수 — F.2 관측 + 메모리 갱신)

- **H.1**: `project_test_gap_analysis.md` 메모리 1287+ 기준 재작성 — 통합 테스트 P2 갭 해소 반영, 잔여 갭 재정의
- **H.2**: Phase F.2 — `handle_gate_callback` 반자동 merge 관측 완료
  - `src/webhook/providers/telegram.py`: `log_merge_attempt` import + merge_pr 직후 nested try/except 삽입
  - `tests/unit/webhook/test_telegram_provider.py`: 기존 2개 보강 + 신규 3개 추가 (+5 테스트)
  - `CLAUDE.md` F.2 "범위 제한" 문구 제거
  - `docs/reports/2026-04-24-comprehensive-audit.md` P2 Phase F.2 ✅ 마킹
- **H.3**: 통합 테스트 2건 보강 (`tests/integration/test_webhook_to_gate.py`)
  - `test_pr_synchronize_updates_analysis`: synchronize 이벤트로 새 SHA 도착 시 두 번째 Analysis 생성 검증
  - `test_gate_block_triggers_notifier`: gate check 후 `build_notification_tasks` 항상 호출 검증 + `repo_name`/`pr_number` 인자 확인

- **H.4**: G.6 벤치마크 기준선 수집 완료
  - `scripts/benchmark_static_analysis.py`: 3 페이로드 × 3회 반복 벽시계+RSS 측정
  - `docs/reports/2026-04-25-static-analysis-baseline.md`: 결과 보고서
  - **판정**: BORDERLINE (전체 평균 14.76s — JS ESLint 미설치로 Railway 실측과 다름)
  - Python-heavy 10 파일 기준 24.33s — Railway 실측 >= 30s 시 Phase I 착수
  - `docs/reports/INDEX.md`: 보고서 등록

**테스트 증분**: +7 (H.2 +5, H.3 +2)

### 그룹 36 (2026-04-24 · P2 이슈 수정 + settings.html 번호 교정)

- **PyGithub 타임아웃**: `diff.py::_make_github_client()` 헬퍼 신설, `timeout=int(HTTP_CLIENT_TIMEOUT)` 적용 (P2)
- **settings.html ①~⑥ 번호**: 빠른 설정 카드에 ① 누락으로 ②→⑤ 1씩 밀림 수정 + 인라인 힌트 참조 ③→④ 교정
- **analyses UniqueConstraint**: `(repo_id, commit_sha)` DB 수준 중복 방지 + `IntegrityError` 처리 안전망 + Migration 0016 + 테스트 4개 신규 (P2)
- **계획 파일**: `docs/_archive/2026-04-24-auto-merge-f3-advisor.md` (archived)

**테스트 증분**: +6 (diff 타임아웃 assert 2 + analysis_repo 4)

### 그룹 35 (2026-04-24 · Phase G.0~G.5 완료)

- **G.0**: 14 에이전트 × 3 Round 전면 감사 보고서 아카이브 (`docs/reports/2026-04-24-comprehensive-audit.md`)
- **G.1**: P1-1 `issue_count` → `file_count` + `issue_count` 분리 (`src/worker/pipeline.py:327`)
- **G.2**: 테스트 수치 1293 으로 3-way 동기화 (README/STATE/CLAUDE) + `.env.example` SMTP 블록 추가
- **G.3**: P1-4 Telegram webhook secret 실패 시 401 반환 (`src/webhook/providers/telegram.py`)
- **G.4**: P1-5 prod 환경 TOKEN_ENCRYPTION_KEY 누락 시 startup SECURITY 경고 (`src/main.py`)
- **G.5**: P1-3 http_client 싱글톤 전환 완료 — 10 파일 / 16 사이트 (gate/github_client/notifier/railway)

### 그룹 34 — Phase F.3 실패 어드바이저 + GitHub Issue 생성 (2026-04-24)

`count_failures_by_reason` 조기 조회 결과 + F.1 로드맵에 따라 F.3 (실패 알림 고도화) 착수 및 완료.

**신규 모듈**:

| 모듈 | 역할 |
|------|------|
| `src/gate/merge_failure_advisor.py` | `get_advice(reason)` — reason tag → 권장 조치 텍스트 (순수 함수, Phase F.3) |
| `src/notifier/merge_failure_issue.py` | `create_merge_failure_issue()` — auto-merge 실패 GitHub Issue 생성 (dedup 24h) |

**수정 모듈**:
- `src/gate/engine.py::_run_auto_merge` — 실패 시 `get_advice()` 호출 + `auto_merge_issue_on_failure` 설정 시 `create_merge_failure_issue()` 조건부 실행
- `src/config_manager/manager.py` + ORM + API body + 설정 폼 — `auto_merge_issue_on_failure` 필드 5-way sync
- `src/templates/settings.html` — `toggleMergeIssueOption` JS 헬퍼 + merge issue 토글 UI

**테스트 증분**: +9 (advisor 3 + merge_failure_issue 3 + engine F.3 경로 3) — 1247 passed.
**품질**: pylint 10.00 · bandit HIGH 0 · 회귀 없음.

### 그룹 33 — Phase F Quick Win + F.1 관측 기반 구축 (2026-04-24)

그룹 32 의 3-에이전트 로드맵에서 **Option B** (Quick Win + F.1) 승인 → 일괄 반영.

**Quick Win 5건 (46ec124)** — auto-merge 안정성 즉시 개선:

| 항목 | 변경 | 효과 |
|------|------|------|
| QW1 | `_MERGEABLE_BLOCK` 에 `"unstable"` 추가 | P0 — BPR 설정 repo 에서 CI 일부 실패 시 사전 차단 |
| QW2 | `merge_unknown_retry_limit` / `delay` 를 `Settings` 로 외부화 | 운영 중 환경변수로 튜닝 가능 |
| QW3 | Telegram 실패 알림에 GitHub PR 링크 추가 | 사용자 1-click 이동 (UX) |
| QW4 | `_run_auto_merge` except 에 `RuntimeError`/`ValueError` 확장 | 예상외 예외도 Telegram 알림 스킵 방지 |
| QW5 | `src/gate/merge_reasons.py` 정규 태그 상수 모듈화 | Phase F.1 `MergeAttempt.failure_reason` enum 과 네이밍 통일 (forbidden→permission_denied, conflict→conflict_sha_changed) |

**Phase F.1 관측 기반 (20790cc)** — MergeAttempt ORM + 집계 + 구조화 로깅:

| 신규 모듈 | 역할 |
|-----------|------|
| `src/models/merge_attempt.py` | MergeAttempt ORM — score/threshold 스냅샷 + failure_reason 정규 태그 + detail_message 원문, analyses CASCADE, append-only |
| `src/repositories/merge_attempt_repo.py` | `create` / `list_by_repo` / `count_failures_by_reason(since=?)` — Phase F.3 advisor 진입점 |
| `src/shared/merge_metrics.py` | `parse_reason_tag` + `log_merge_attempt` (DB INSERT + INFO 구조화 로그). DB 오류 시 rollback + None 반환 |
| `alembic/versions/0014_add_merge_attempts.py` | merge_attempts 테이블 + 인덱스 2개 (analysis_id, repo_name) |

**수정 모듈**:
- `src/gate/engine.py::_run_auto_merge` — `analysis_id` + `db` 키워드 파라미터 추가, `merge_pr` 직후 `log_merge_attempt` 호출 (nested try/except 로 격리 — 관측 실패가 notify 를 막지 않음)

**pipeline-reviewer Blocker 해소**: `log_merge_attempt` 의 `commit()` 실패 경로에 `db.rollback()` 추가 (SQLAlchemy `PendingRollbackError` 방지). 회귀 테스트 2건 추가.

**범위 제한 (의도적)**: `webhook/providers/telegram.py::handle_gate_callback` 의 반자동 merge 는 Phase F.2 범위 — Phase F.1 은 auto-merge 경로만 관측.

**테스트 증분**: +24 (models 4 + repo 5 + shared 12 + engine 3) — 1251 → **1275 passed**.
**품질**: pylint 10.00 · bandit 0 issue (B110 rollback 블록 nosec + 사유 명시).

**Phase F.2~F.5 착수 대기 (2026-04-24 결정)**: 원본 보고서 로직에 따라 **F.1 실측 데이터 축적 후 재평가**. MergeAttempt 배포 직후이므로 실제 실패 분포(`failure_reason` 카운트)가 아직 0 건. 2~4주 운영 후 `count_failures_by_reason(since=...)` 결과로 F.2(사전 체크)·F.4(대시보드)·F.5(BPR 체크) 중 임팩트 큰 항목부터 선정. **F.3 완료 (그룹 34)** — 실패 어드바이저 + GitHub Issue 생성. 조기 착수 시 "데이터 없는 최적화" 가 되어 Claude 권장(Option B)에 위배.

### 그룹 32 — Auto-merge 실패 진단 3-에이전트 + Phase F 로드맵 (2026-04-24)

사용자 보고: 일부 Repo 에서 PR auto-merge 가 실패. 3개 병렬 에이전트 (A: 현재 구현 분석
· B: GitHub 실패 시나리오 · C: 재발 방지 로드맵) 독립 조사 + 종합.

**핵심 결론**:
- 🔴 **P0 버그**: `mergeable_state == "unstable"` 이 `_MERGEABLE_BLOCK` 에 없음 → BPR
  "Require status checks" 설정 repo 에서 merge 시도 후 405 실패. 사용자 보고 현상의 주요 원인.
- 🟡 **가시성 공백**: auto-merge 실패가 DB (`GateDecision`) 에 기록 안 됨 → 추적 불가.
- 🟡 **재시도 부족**: unknown 상태 9초 재시도, 대규모 PR 은 20초+ 소요 가능.
- 🟡 **권장 조치 부재**: Telegram 알림에 사유는 있으나 해결 방법 없음.

**Phase F 로드맵 제안** (5단계, 총 5세션):
- F.1 관측 — `MergeAttempt` ORM + failure_reason enum
- F.2 사전 체크 보강 + unstable 추가 + exponential backoff
- F.3 실패 알림 고도화 + GitHub Issue 자동 생성 옵션
- F.4 대시보드 Auto-merge History 탭
- F.5 Settings UI BPR 호환성 체크 + 권한 dry-run

**Quick Win 5건** (Phase F 착수 전 즉시 적용 가능, 소요 ~90분):
1. `_MERGEABLE_BLOCK` 에 `"unstable"` 추가 (P0 버그)
2. unknown 재시도 파라미터 settings 외부화
3. Telegram 알림에 PR 링크 추가
4. `_run_auto_merge` except 확장
5. `_interpret_merge_error` label 을 `src/gate/merge_reasons.py` 상수로 추출

**상세 보고서**: [reports/2026-04-24-auto-merge-failure-analysis-3agent.md](reports/2026-04-24-auto-merge-failure-analysis-3agent.md).

**사용자 승인 대기**: Option A (Quick Win만) / B (Quick Win + F.1 관측, 권장) / C (Phase F 전체).

### 그룹 31 — 5-렌즈 감사 Minor 이슈 후속 개선 (2026-04-24)

2026-04-23 5-렌즈 감사 (91/100 A) 의 Minor 4건 중 3건 반영 + Agent R5 의 잘못된
지적 1건 반박 (README.ko.md 점수 체계 표는 L139-158 에 이미 존재).

| 수정 | 위치 | 효과 |
|------|------|------|
| 피드백 버튼 aria-label + role="group" + aria-live status | `analysis_detail.html` | 스크린리더 접근성 확보 (R5 +1 예상) |
| env-vars.md 토큰 형식 "your-github-token" 등 | `docs/reference/env-vars.md` | 토큰 형식 누출 방지 (R4 +1 예상) |
| .env.example 동일 형식 + Observability 섹션 추가 | `.env.example` | 신규 사용자 혼동 방지 |
| `_before_send` 단위 테스트 17건 (독립 파일) | `tests/unit/shared/test_sentry_scrubbing.py` | 보안 함수 검증 (R2 +0.5 예상) |

**예상 감사 재점수**: 91 → **~94~95/100**.

**Agent R5 오류 정정**: README.ko.md L139-158 에 점수 체계 표 (5행) + 등급 기준 표 (5행) 가
이미 존재. 영문판과 동일 구조 유지. R5 의 "구조 불일치 -1" 감점은 잘못된 지적.

### 그룹 30 — Phase E 완결 5-렌즈 품질 감사 (2026-04-23)

3-에이전트 후속 수정 (그룹 29) 직후 실시한 **5개 병렬 에이전트 종합 감사** — 이전
2026-04-21 5라운드 감사와 동일 구조 (5렌즈 × 20점 = 100점).

| 렌즈 | 점수 | 핵심 발견 |
|------|------|----------|
| R1 정상성 | **20 / 20** | 1234 passed · 모든 import 정상 · working tree clean |
| R2 커버리지·테스트 품질 | **16 / 20** | _before_send 테스트 부재 · pipeline stage_timer 로그 검증 부재 (-4) |
| R3 아키텍처·결정성 | **18 / 20** | POST /feedback JSON body 패턴 (기존 settings POST 는 form, -2) |
| R4 보안·Lint | **19 / 20** | pylint 10.00 · bandit HIGH 0 · 로그/Sentry/엔드포인트 만점 · -1 (env-vars.md 토큰 형식 노출) |
| R5 서비스 완결성·문서 | **18 / 20** | Phase E 기능 10/10 · 문서 100% 일치 · -1 (aria-label), -1 (README.ko 점수표 누락) |
| **합계** | **91 / 100 · A 등급** | 프로덕션 배포 준비 완료 선언 |

**판정**: 🔴 Critical 0 · 🟠 Major 0 · 🟡 Minor 4건 (전부 점진 개선 가능).
과거 2026-04-21 (95/100) 대비 -4 는 Phase E 신규 코드로 인한 통합 테스트·문서
대칭성 감점. 새 기능 추가 시 일반적 하락폭 대비 준수.

**상세 보고서**: [reports/2026-04-23-phase-e-quality-audit-5lens.md](reports/2026-04-23-phase-e-quality-audit-5lens.md)

**개선 가능 항목 (쉬운 후속)** — 95+ 로 가는 경로:
1. README.ko.md 점수 체계 표 추가 (+1 R5)
2. analysis_detail 피드백 버튼 aria-label 추가 (+1 R5)
3. env-vars.md / .env.example 토큰 형식 "your-secret-here" 로 변경 (+1 R4)
4. test_observability.py 에 _before_send 테스트 4~5건 추가 (+0.5 R2)

### 그룹 29 — 3-에이전트 감사 후속 수정 (2026-04-23)

Phase E 완결 직후 **3개 병렬 에이전트** (Code/Architecture · Documentation · Security)
로 전체 감사 수행. 발견된 🔴 Critical 3건 + 🟠 Major 4건 중 즉시 수정 가능한 항목
일괄 반영. Rate limit / service layer / 쿼리 최적화 등은 별도 후속 Phase 로 연기.

| 심각도 | 위치 | 수정 내용 |
|--------|------|----------|
| 🔴 | `src/shared/stage_metrics.py` | 예약 키 (pipeline_stage/duration_ms/status/error_type) 를 extra_fields·ctx 뒤에 병합해 덮어쓰기 방지 — 로그 인젝션 방어 |
| 🔴 | `src/worker/pipeline.py` | `repo=repo_name` 4곳에 `sanitize_for_log()` 적용 — CLAUDE.md 규약 준수 |
| 🔴 | `src/shared/observability.py` | Sentry `before_send` 훅 추가 — URL query / cookies / Authorization 헤더 스크러빙으로 PII 누수 방어 + `send_default_pii=False` 명시 |
| 🔴 | `CLAUDE.md` | 아키텍처 트리에 Phase E 신규 5개 파일 추가 (observability.py · claude_metrics.py · stage_metrics.py · analysis_feedback.py · analysis_feedback_repo) |
| 🟠 | `src/ui/routes/detail.py` | FeedbackRequest.comment 에 `max_length=2000` — DB 행 크기 폭주 방어 + 경계값 2건 테스트 |
| 🟠 | `src/shared/claude_metrics.py` | docstring 에 "2026-04 기준" + "분기별 재확인 필수" + "±10% 오차" 명시 |
| 🟠 | `src/models/analysis_feedback.py` | CASCADE 삭제 의도 docstring 추가 — 추후 GDPR/계정삭제 대비 SET NULL 전환 가능성 명시 |
| 🟠 | `docs/STATE.md` | 잔여 과제 표의 "P4-Gate 통과" 를 "P4-Gate-1 통과 (완료) / P4-Gate-2 대기 (rubocop/golangci-lint 실증 필요)" 로 분리 |

**보류 (별도 후속 Phase)**:
- Rate limiting (POST /feedback) — 공개 배포 확대 시 slowapi 도입
- detail.py 서비스 레이어 추출 — 현 규모에서는 과도한 리팩토링
- get_calibration SQL 최적화 — 피드백 수 5000+ 도달 시 CASE WHEN 전환
- AnalysisFeedback 데이터 보존 정책 — 테이블 1M 행 도달 시 TTL 배치

**최종 수치**: 1232 → **1234 passed** (+2) · pylint 10.00 · flake8 0. 회귀 없음.

**감사 과정 평가**: 3 에이전트 합의로 발견된 실제 이슈 8건 중 6건 즉시 수정, 2건 문서화된
후속 과제. Agent 1 의 **잘못된 지적 2건** (POST /feedback 테스트 부재 · ai_review 타이머
중복) 은 반박 + 무시. 다중 에이전트 감사의 효용 재확인 — 각각 독립적 렌즈로 본 결과가
보완적 (Agent 2 의 문서 불일치는 Agent 1/3 이 놓친 영역).

### 그룹 28 — Phase E.5 Onboarding 튜토리얼 (2026-04-23)

Path A (서비스화) 로드맵 **최종 단계**. 첫 방문자가 리포 등록까지의 경로를 명확하게
보여주는 3단계 튜토리얼 카드.

**변경 내용**:
- overview.html 의 기존 empty-state (리포 0개 분기) 를 3단계 튜토리얼 카드로 교체
  · 1️⃣ GitHub 리포 선택 — `+ 리포 추가` CTA 버튼
  · 2️⃣ 기본 설정 (Simple 모드) — Phase E.4 에서 만든 Simple 모드 기본값 설명
  · 3️⃣ 첫 Push/PR — 자동 분석 + 👍/👎 피드백 (Phase E.3 연결)
- footer hint: `ANTHROPIC_API_KEY` 없이도 최대 89점(B등급) 가능 안내
- 인라인 CSS — 번호 원형 배지, 단계 카드 hover-bg, footer 파란 강조 박스
- +2 tests (empty-state 시 튜토리얼 노출 / 리포 있을 때 숨김)

**최종 수치**: 1230 → **1232 passed** (+2) · 1 skipped · pylint 10.00 · flake8 0.

## Phase E 전체 완결 — Path A (서비스화) 목표 달성

2026-04-23 하루에 E.1~E.5 5단계를 모두 완료. Phase D (언어 breadth 확장) 에서 Phase E
(서비스 성숙도) 로의 방향 전환이 코드에 반영됨.

| Phase | 목적 | 성과 |
|-------|------|------|
| E.1 | Phase D.5~D.8 공식 중단 | 백로그 정리 (4개 도구 영구 보류 + 재개 3조건) |
| E.2 | Observability 기반 | Sentry + Claude API 메트릭 + Pipeline 5단계 타이밍 (+21 tests) |
| E.3 | AI 점수 피드백 루프 | Thumbs up/down + 정합도 대시보드 (+14 tests) |
| E.4 | Minimal Mode | Settings UI Simple/Advanced 토글 (+3 tests) |
| E.5 | Onboarding 튜토리얼 | empty-state → 3단계 카드 (+2 tests) |

**총 증분**: Phase E 직전 1192 → 1232 passed (**+40** Phase E 본체). AI 파서 견고화(1188→1192) 는 Phase E 착수 직전 별도 수정. 모든 변경은 pylint 10.00 / flake8 0 / 회귀 없음.

### 그룹 27 — Phase E.4 Minimal Mode (Settings UI Simple/Advanced 토글) (2026-04-23)

Path A (서비스화) 로드맵 네 번째 단계. 신규 사용자 onboarding friction 감소 —
기본 Simple 모드는 Python + Telegram + PR comment 핵심 설정만 노출.

**구현 전략 — 순수 클라이언트 측 UI 전환** (백엔드 영향 0, DB 마이그레이션 없음):
- localStorage 에 사용자 선호 영속 (`scamanager_settings_mode`)
- `?mode=simple|advanced` 쿼리 오버라이드 지원
- `data-settings-mode="simple|advanced"` body 속성 + CSS `.adv-only { display:none }` 로 토글
- 기존 설정 값은 그대로 저장, 숨김만 전환

**변경 내용**:
- settings.html 헤더 하단에 Simple/Advanced 토글 바 추가 (inline CSS + JS, 의존성 없음)
- 알림 채널 ③ 카드에서 Discord/Slack/Email/Webhook/n8n 필드에 `adv-only` 클래스 적용 (Telegram 만 Simple 노출)
- 기존 `<details class="advanced-details">` 도 Simple 모드에서 자동 숨김 (PR gate·Feedback 카드)
- Advanced 전환 시 details 자동 펼침 (UX)
- +3 tests (모드 토글 버튼 / adv-only 클래스 / JS 함수 존재)

**Simple 모드에서 보이는 것**:
- 빠른 설정 프리셋 (🚀)
- 알림 채널 중 Telegram 만
- 시스템 & 토큰 (⑤)
- 위험 구역 (⑥)

**Advanced 모드에서 추가로 보이는 것**:
- PR 들어왔을 때 (Gate/Approve/Merge — ①)
- 이벤트 후 피드백 (commit comment/issue/Railway — ②)
- 알림 채널 중 Discord/Slack/Email/Webhook/n8n

**최종 수치**: 1227 → **1230 passed** (+3) · 1 skipped · pylint 10.00 · flake8 0.

### 그룹 26 — Phase E.3 AI 점수 피드백 루프 (2026-04-23)

Path A (서비스화) 로드맵 세 번째 단계. Claude 점수 vs 사람 판단의 정합도를 측정해
auto-merge 결정의 신뢰 기반 구축.

| 세부 | 내용 |
|------|------|
| **E.3-a** ORM + Migration + Repository | `AnalysisFeedback` ORM (analysis_id + user_id FK CASCADE, thumbs +1/-1, comment, timestamps). Alembic 0013. `analysis_feedback_repo` 3함수 (upsert / find / get_calibration_by_score_range). UniqueConstraint 로 (사용자, 분석) 당 1개 강제. +7 tests |
| **E.3-b** 피드백 엔드포인트 | `POST /repos/{name}/analyses/{id}/feedback` (세션 기반 require_login, Pydantic Literal[1,-1] 검증) + `GET .../feedback` (UI 상태 복원용) + `analysis_detail` context 에 `user_feedback` 추가. +7 tests |
| **E.3-c** analysis_detail UI | 점수 배너 아래 "이 점수가 맞나요?" 피드백 카드 — 👍/👎 버튼 + fetch POST + 초기 상태 복원. 카드 CSS + 인라인 JS (약 70줄) |
| **E.3-d** 정합도 대시보드 | overview.py 에서 `get_calibration_by_score_range` 호출 → 5구간 표 (피드백 수·👍 비율·bar chart). 피드백 1건 이상 있을 때만 노출 |

**최종 수치**: 1213 → **1227 passed** (+14) · 1 skipped · pylint 10.00 · flake8 0.

**얻게 된 것**:
- auto-merge threshold 를 조정할 근거 데이터 — 3개월 뒤부터 점수 범위별 👍 비율 분석 가능
- Claude 프롬프트 개선 대상 식별 — 👍 비율 낮은 구간의 분석 케이스 리뷰
- 사용자가 실제로 받는 가치 지표 — 점수가 쓸모없으면 👎 비율 상승

### 그룹 25 — Phase E.2 Observability 기반 구축 (2026-04-23)

Path A (서비스화) 로드맵 두 번째 단계. 프로덕션 관측 가시성 확보 — 예외 수집·
Claude API 비용 추적·파이프라인 단계별 지연 측정.

| 세부 | 커밋 | 내용 |
|------|------|------|
| **E.2a** Sentry SDK 통합 | `91abcba` | `src/shared/observability.py::init_sentry()` — SENTRY_DSN 설정 시만 활성, 미설정 / sentry-sdk 미설치 / init 예외 모두 graceful no-op. FastApiIntegration 자동. lifespan 시작 시 호출. +9 tests (CI 전용 `importorskip`) |
| **E.2b** Claude API 계측 | `ad951d0` | `src/shared/claude_metrics.py` — `estimate_claude_cost_usd` (Opus/Sonnet/Haiku 가격) · `extract_anthropic_usage` · `log_claude_api_call` (extra dict 구조화 로그). ai_review.py 에 time.perf_counter() + success/error 양쪽 경로 계측. +14 tests |
| **E.2c** Pipeline 단계 타이밍 | 이 커밋 | `src/shared/stage_metrics.py::stage_timer` context manager — duration_ms + status + extra_fields + ctx 병합. pipeline.py 에 5개 단계 (pipeline_total/collect_files/analyze/score_and_save/notify) 적용. +7 tests |

**최종 수치**: 1192 → **1213 passed** (+21) · 1 skipped · pylint 10.00 · flake8 0.

**관찰 가능해진 지표** (로그로 자동 기록, structured log shipper 가 파싱 가능):
- 분석 1건당 Claude API cost (USD, 모델별 가격 추정)
- Claude API latency (p50/p95/p99 산출 가능)
- Claude API 성공/실패율 + 에러 타입
- 파이프라인 5단계 각각의 duration_ms + 파일 수·이슈 수·점수·채널 수
- FastAPI 경로별 예외 + request context (Sentry DSN 설정 시)

**사용자 조치 (현재 권장: 보류)**: Sentry Developer 플랜이 14일 Trial 로 확인됨 (2026-04-23). Claude API 메트릭 + 파이프라인 타이밍은 Sentry 없이도 Railway 로그에 자동 기록되므로 `SENTRY_DSN` 빈 상태 유지. 필요 시 [GlitchTip](https://glitchtip.com) (Sentry-compatible, 영구 무료) DSN 만 추가하면 **코드 변경 없이** 즉시 활성화. 상세: [env-vars.md](reference/env-vars.md#observability-선택-phase-e2).

### 그룹 24 — Railway 빌드 안정화 (rubocop/prism 의존성 트랩 해소) (2026-04-23)

Phase D.3 배포 후 Railway 빌드 **2회 연속 실패** → 3차 수정 성공. 상세 경위: [회고 문서](reports/2026-04-23-railway-rubocop-prism-retrospective.md).

| 시도 | 커밋 | 접근 | 결과 |
|-----|------|------|------|
| 1차 수정 | `6aaa268` | `build-essential + libyaml-dev` 추가 + rubocop 1.57.2 핀 | ❌ 동일 prism 오류 재발 (nix/apt PATH 혼재로 gcc 미작동) |
| 근본 원인 분석 | — | 로그 상세 분석: `rubocop-ast` transitive prism 의존성 추적 | — |
| 2차 수정 (최종) | `8042f12` | **`gem install rubocop-ast -v 1.36.2`** 를 rubocop 설치 전에 명시 삽입 | ✅ 배포 성공 (2026-04-23) |

**핵심 통찰**:
- rubocop 1.57.2 는 pure Ruby 이지만 `rubocop-ast (>= 1.28.1, < 2.0)` 제약이 **시간이 지나 prism 을 필요로 하는 최신 버전(1.43+)** 으로 떠올랐음
- "버전 고정"과 "재현 가능 빌드" 는 다르다 — transitive 의존성을 명시 고정해야 진정한 재현성
- P4-Gate 제도의 가치: 로컬 mock 테스트만으로는 프로덕션 환경 (nixpacks + apt + nix) 에서의 gem 설치 동작을 보장 못함

**재발 방지**: Ruby 도구 추가 시 transitive 의존성을 미리 점검. `rubocop-ast 1.36.2` 고정은 향후 rubocop 업데이트에도 유효 (rubocop 1.57.2 제약 만족).

### 그룹 23 — Phase D.3 + D.4 — Ruby·Go 정적분석 확장 (2026-04-23)

시나리오 B 10-step 중 Step 9~10 완료. P4-Gate 실증 통과 (분석 #543) 로 해금된 후 즉시 착수. 두 도구 모두 TDD 로 9개 테스트 선작성 → 구현 9/9 Green → Railway 빌드 설정 추가 순서.

| Step | 커밋 | 내용 |
|------|------|------|
| 9 (D.3) | `2eb0ef0` | `src/analyzer/io/tools/rubocop.py` — Ruby RuboCop 분석기 + 9개 테스트. Security/ cop → category=SECURITY, severity: error/fatal→ERROR. nixpacks `ruby-full`·buildCommand `gem install rubocop --no-document`. |
| 10 (D.4) | `d78b449` | `src/analyzer/io/tools/golangci_lint.py` — Go golangci-lint 분석기 + 9개 테스트. **`_ensure_go_mod` 자동생성 로직** (단일 .go 파일 분석 대응). FromLinter=gosec → SECURITY+ERROR. nixpacks `golang-go`·buildCommand golangci-lint v1.55.2 installer. |

**최종 수치**: 1170 → **1188 passed** (+18) · pylint 10.00 · CRITICAL 0 · Tier1 정적분석 도구 **10종**.

**대기 작업 (Railway 프로덕션 2차 실증)**:
- ✅ **Railway 빌드 성공 (2026-04-23)** — 그룹 24 참조. 이제 바이너리 동작 확인부터 진행 가능.
- `xzawed/SCAManager-test-samples` 에 `.rb` · `.go` 샘플 푸시 후 rubocop/golangci-lint 실제 동작 확인 → [P4-Gate-2 가이드](_archive/p4-gate-2-verification.md) 2단계부터.

### 그룹 22 — Phase Q.7 + S.4 + S.3-D 완결 + P4-Gate 재료 (2026-04-23)

3-에이전트 논의 로드맵([reports/2026-04-23-remaining-roadmap-3agent.md](reports/2026-04-23-remaining-roadmap-3agent.md)) 시나리오 B (균형형) 실행. Step 1~6·8 완료. Step 7 (P4-Gate 실증) 사용자 대기, Step 9~10 (D.3/D.4) 게이트 통과 후 해금.

| Step | 커밋 | 내용 |
|------|------|------|
| 1+2 (S.4 + S.3-D) | `f678222` | `test_pipeline.py` fixture 를 Option A (함수 단위 patch) 로 재설계 + `repository_repo.find_by_full_name` 내부 `filter_by → filter` 전환 + UI/webhook 4파일 `repository_repo` 경유 확산 (deps.py · _helpers.py · add_repo.py · railway.py). S.1-4·S.3-D 2회 실패의 근본 원인 해소. |
| 3~5 (Q.7-2~5) | `e551839` | Cognitive Complexity CRITICAL 4건 해소 — slither 3 헬퍼 · github_comment 6 헬퍼 · formatter 4 헬퍼 · git_diff 1 헬퍼 추출. 모두 순수 함수, 외부 API 불변. |
| 6 (P4-Gate 재료) | `6ec93f4` | `docs/_archive/p4-gate-verification.md` + `docs/samples/p4-gate/{buffer_overflow.c, reentrancy.sol, verify_tool_hits.sh}` — 사용자 실증 PR 재료 (archived). |
| 8 (Q.7-1) | `842ea1d` | `run_gate_check` CC 31 → ≤15 — 5 헬퍼 분할 (`_run_review_comment` · `_run_approve_decision` → `_run_auto_approve`/`_run_semi_auto_approve` · `_run_auto_merge`). pipeline-reviewer 승인. |

**최종 수치**: 1170 passed · pylint 10.00 · flake8 0 · bandit HIGH 0 · **CRITICAL 0** · SonarCloud QG OK · 3종 Rating A.

**대기 작업 (사용자)**:
1. 외부 테스트 리포에 `docs/samples/p4-gate/` 샘플 2개 배치
2. PR 제출 후 Railway 빌드 로그 + 분석 결과 확인
3. 6항목 체크리스트 통과 확인 후 본 세션 재개 → D.3 RuboCop (Step 9) + D.4 golangci-lint (Step 10) 자동 해금

### 그룹 21 — Phase S.3 구조 정리 5단계 (2026-04-23)

3-에이전트 감사 잔여 개선 항목을 5단계로 체계 수행. S.3-A/B/C/E 완료, S.3-D 보류 → **이후 그룹 22 에서 완결** (커밋 `f678222`).

| 세부 | 커밋 | 내용 |
|------|------|------|
| **S.3-A** Service 스캐폴딩 | `60839ac` | `src/services/__init__.py` 신설 — 신규 use case 위치 명시 (기존 3파일 유지) |
| **S.3-B** Analyzer pure/io | `daab76b` | `src/analyzer/{pure,io}/` 분리 — 7파일 이동 + review_guides 이동 + import 경로 119곳 치환 + mock 문자열 경로 치환 |
| **S.3-C** tests/unit 계층화 | `bf83a61` | `tests/unit/` + 21 서브디렉토리 — 65 파일 git mv (src/ 미러링) + `__init__.py` 39개 추가 (파일명 중복 해소) |
| **S.3-D** get_repo_or_404 확산 | 이후 `f678222` | 당시 보류: `repository_repo.find_by_full_name` 을 `filter` 로 전환 시 pipeline test mock 12곳 회귀 (S.1-4 + S.3-D 2회 확정). **그룹 22 (2026-04-23 Step 1+2) 에서 Phase S.4 pipeline test mock Option A 재설계와 함께 완결**. |
| **S.3-E** Notifier 8클래스 이동 | 이 커밋 | pipeline.py 내 익명 클래스 8개 → `src/notifier/*.py` 로 이동 + `src/notifier/__init__.py` auto-register 트리거 + pipeline.py 축약 (200줄 감소). mock 경로 15곳 치환 |

**최종 수치**: 1170 passed · pylint 10.00 · flake8 0 · bandit HIGH 0 · SonarCloud QG OK · 3종 Rating A.

**구조 변화 요약**:
- `src/services/` 신설 (빈 패키지, SOP 명시)
- `src/analyzer/{pure,io}/` 분리 (단방향 의존성)
- `tests/unit/` 21 서브디렉토리 미러링
- `src/notifier/__init__.py` 자동 등록 트리거 (analyzer/tools 선례)
- `src/worker/pipeline.py` 200줄 감소 (임시 클래스 8개 삭제)

### 그룹 20 — Phase S.2 UI/Webhook router 서브패키지 분할 (2026-04-23)

[3-에이전트 진단](reports/2026-04-23-structure-audit-3agent.md) Phase S.2 원안 수행. mock 경로 193곳 일괄 재작성 포함.

**UI router (458줄 → aggregator 24줄 + 6 모듈)**:
- `src/ui/_helpers.py` (신설) — `get_accessible_repo` · `webhook_base_url` · `delete_repo_cascade` · `GITHUB_WEBHOOK_PATH` · `templates` · `logger`
- `src/ui/routes/overview.py` — `GET /`
- `src/ui/routes/add_repo.py` — `GET /repos/add` · `GET /api/github/repos` · `POST /repos/add`
- `src/ui/routes/settings.py` — `GET/POST /repos/{name}/settings` · `POST .../reinstall-hook` · `POST .../reinstall-webhook`
- `src/ui/routes/actions.py` — `POST /repos/{name}/delete`
- `src/ui/routes/detail.py` — `GET /repos/{name}/analyses/{id}` · `GET /repos/{name}` (catch-all, 마지막 include)
- `src/ui/router.py` — aggregator (sub-routers include)

**Webhook router (390줄 → aggregator 40줄 + 4 모듈)**:
- `src/webhook/_helpers.py` (신설) — `_webhook_secret_cache` · `get_webhook_secret` (TTL 캐시)
- `src/webhook/providers/github.py` — `POST /webhooks/github` + `_handle_merged_pr_event` + `_handle_issues_event` + `_extract_closing_issue_numbers`
- `src/webhook/providers/telegram.py` — `POST /api/webhook/telegram` + `_parse_gate_callback` + `handle_gate_callback`
- `src/webhook/providers/railway.py` — `POST /webhooks/railway/{token}` + `_handle_railway_deploy_failure`
- `src/webhook/router.py` — aggregator + 하위 호환 re-export (conftest autouse 용 `_webhook_secret_cache` 등)

**테스트 mock 경로 재작성 193곳**:
- `test_ui_router.py` 의 `src.ui.router.X` → 각 route 모듈 경로 (SessionLocal 61곳 · delete_webhook · create_webhook · get_repo_config 등)
- webhook 5개 테스트 파일의 `src.webhook.router.X` → provider 별 경로 (`.github`, `.telegram`, `.railway`)
- 일부 헬퍼 경로는 `src.ui._helpers.X` / `src.webhook._helpers.X`

**수치**: 1170 passed 유지, pylint 10.00, flake8 0, bandit HIGH 0, SonarCloud QG OK 유지.

### 그룹 19 — 프로젝트 구조 3-에이전트 감사 · Phase S.1 (2026-04-23)

3개 Explore 에이전트 (A: Python 표준 · B: 확장성 · C: 도메인 경계) 병렬 감사 → 합의된 이슈만 S.1~S.3 로 단계 분류. [진단 보고서](reports/2026-04-23-structure-audit-3agent.md).

| 세부 작업 | 변경 내용 |
|----------|----------|
| S.1-1 `src/shared/` 패키지 신설 | `http_client.py` · `log_safety.py` 이동 (git mv 로 이력 보존) + import 경로 4곳 업데이트 |
| S.1-2 Gate 스캐폴딩 삭제 | `src/gate/actions/` 4 파일 + `src/gate/registry.py` + `tests/test_gate_registry.py` 제거 (engine.py 에서 호출 안 되던 죽은 코드 ~250줄 + 테스트 5개 제거) + engine.py docstring 의 Note 정리 |
| S.1-3 Tier 기준 주석 | `src/analyzer/review_guides/__init__.py` 에 Tier 1/2/3 분류 기준 docstring (신규 언어 추가 시 참조용) |
| S.1-4 보류 | `get_repo_or_404` UI/webhook 확산 시도 → 기존 mock 패턴 (`filter` 직접 호출) 과 `repository_repo.find_by_full_name` (`filter_by` 기반) 의 불호환으로 55개 테스트 회귀 → 원복. **Phase S.3 (테스트 mock 일괄 재작성) 로 연기**. |

**결과**: pylint 10.00 / flake8 0 / SonarCloud QG OK 유지. 1175 → 1170 passed (삭제된 test_gate_registry 5건 반영).

### 그룹 18 — Phase Q.5~Q.6 SonarCloud 잔존 이슈 해소 (2026-04-23)

CI #4 재분석 결과 드러난 신규 BLOCKER/Vuln 을 Q.5~Q.6 후속 2커밋으로 해소. **CI #6 에서 Quality Gate OK + 3종 Rating A 달성**.

| Phase | 커밋 | 주요 내용 |
|-------|------|----------|
| Q.5 | `42a83f6` | `src/log_safety.py::sanitize_for_log()` 신설 (+7 단위 테스트) + FastAPI `Annotated[Type, Depends()]` 패턴 11곳 + `<div role="button">` → `<button type="button">` 3곳 |
| Q.6 | `4eea901` | `github_webhook` Header 2곳 Annotated + log S5145 NOSONAR 주석 2곳 (커스텀 sanitizer 를 SonarCloud 가 인식 못 하는 한계) + `_GITHUB_WEBHOOK_PATH` / `_HEALTH_QUERY` 상수화 + JS `void` 제거 |
| **최종** | — | BLOCKER 14→0 · Vuln 2→0 · Quality Gate OK · Security B→A |

**주요 규약 (CLAUDE.md 반영 필요)**:
- `src/log_safety.py::sanitize_for_log()` — user-controlled 입력을 로거에 전달하기 전 반드시 경유. `%r` 포맷만으로는 SonarCloud taint analysis 통과 못 함.
- `src/github_client/repos.py::_repo_path()` — GitHub API URL 에 repo_full_name 삽입 시 `urllib.parse.quote(safe='/')` 방어적 인코딩.
- FastAPI 핸들러는 `Annotated[Type, Depends(...)]` 또는 `Annotated[Type, Header()] = default` 패턴 사용 (Python 3.9+ 권장).
- 커스텀 sanitizer 를 SonarCloud 가 인식 못 할 때 `# NOSONAR <rule>` 주석 + 이유 코멘트로 명시적 suppress.

### 그룹 17 — Phase Q.1~Q.4 SonarCloud 청산 일괄 반영 (2026-04-23)

[2026-04-23 진단 보고서](reports/2026-04-23-sonarcloud-baseline.md) §5 계획에 따라 4개 Phase 를 연속 실행. 테스트 1168 passed 유지, pylint 10.00 유지.

| Phase | 범위 | 예상 효과 |
|-------|------|----------|
| Q.1 | `sonar-project.properties` 에 `sonar.issue.ignore.multicriteria` 4 규칙 추가 — python:S6418 (tests/e2e), python:S930 (tests), Web:S5725 (templates CDN SRI) | BLOCKER 14→7, Vuln 7→4, Bugs 8→4 |
| Q.2 | `src/github_client/repos.py` — `_repo_path()` 헬퍼 + `urllib.parse.quote()` 로 URL path 방어적 인코딩 5곳 | Vuln pythonsecurity:S7044 5건 해소 예상 |
| Q.3 | `<td>` → `<th scope>` 변환 (settings.html 3곳 + analysis_detail.html 1곳), `<div>` click 에 `role/tabindex/onkeydown` 추가 3곳, `.sr-only` 유틸 클래스 base.html 에 정의 | Bugs Web:S5256 4건 + MouseEventWithoutKeyboard 3건 해소 |
| Q.4 | JS renderPresetDiff 인자 수 정정 (2→1), HMAC regex `[\s:]*` 로 ReDoS 완화, float 비교를 `pytest.approx()` 로 교체, logger 포맷 `%s` → `%r` 로 인젝션 차단 2곳 | BLOCKER 잔존 0 + Hotspot 1건 해소 |

다음 CI 실행 후 SonarCloud 재분석 결과로 실제 Rating 변동 확인 예정 (목표: Maintainability A + Reliability A + Security A).

### 그룹 16 — SonarCloud 1차 분석 결과 확보 (2026-04-23)

2026-04-22 push 후 SONAR_TOKEN/CODECOV_TOKEN 등록 → CI #2 `1106242` 성공 → 첫 분석 완료.

| 항목 | 결과 |
|------|------|
| CI workflow | ✅ success (pytest 1168 + Codecov 3s + SonarCloud 58s) |
| Codecov | ✅ 95.58% (125 files, 3656/3825 hits) |
| SonarCloud Quality Gate | ✅ OK (new code 기준) |
| SonarCloud 전체 이슈 | 🔴 93건 (Bugs 8 · Vuln 7 · Hotspots 4 · Smells 78) |
| SonarCloud Rating | Maintainability **A** · Reliability **D** · Security **C** |
| CodeQL | ✅ success (사용자 수동 확인 필요 — GitHub Security 탭) |

**중요 발견**: 내부 pylint 10.00 + bandit HIGH 0 + flake8 0 을 통과했음에도 SonarCloud 는 JS/Web/pythonsecurity 규칙셋으로 93건 감지. 외부 공신력 도입의 가치 증명. 상세 청산 계획은 [2026-04-23 진단 보고서](reports/2026-04-23-sonarcloud-baseline.md) §5 Phase Q.1~Q.4.

### 그룹 15 — 외부 공신력 품질 서비스 연동 (2026-04-22)

README 배지를 Claude/자체 산출 수치가 아닌 **외부 SaaS 가 직접 측정한 결과** 로 전환.

| 작업 | 주요 내용 | 비고 |
|------|----------|------|
| CI 워크플로 | `.github/workflows/ci.yml` 신설 — pytest + coverage.xml + Codecov 업로드 + SonarCloud scan 단일 job | 공개 저장소 무료 |
| CodeQL 워크플로 | `.github/workflows/codeql.yml` — security-extended + security-and-quality 쿼리팩, 주 1회 cron 스캔 | GitHub 내장 |
| SonarCloud 설정 | `sonar-project.properties` — org=xzawed, projectKey=xzawed_SCAManager, python 3.12, coverage.xml 연동 | `SONAR_TOKEN` secret 필요 |
| Codecov 정책 | `codecov.yml` — 전체 95% target, 2% 하락 시 실패, PR diff 80% | `CODECOV_TOKEN` secret 권장 |
| README 배지 6종 | CI · CodeQL · codecov · SonarCloud (Quality Gate · Maintainability · Security) | README.md / README.ko.md 동기화 |
| 연동 가이드 문서 | `docs/integrations/external-quality-services.md` — 초기 설정 + 트러블슈팅 + 삭제/교체 SOP | — |

**사용자 외부 설정 필수 (1회)**: SonarCloud GitHub 연결 + SONAR_TOKEN, Codecov GitHub 연결 + CODECOV_TOKEN. 상세는 [integrations 문서](integrations/external-quality-services.md) 참조.

### 그룹 14 — 6렌즈 품질 감사 권고 #1~8 일괄 반영 (2026-04-22)

10개 커밋 (`f7e80f7` → `110cd7e`) 으로 감사 결과 B+ (505/600) → 후속 해소. [보고서 §Follow-up](reports/2026-04-22-quality-audit-6lens.md#follow-up-2026-04-22--후속-실행-결과).

| 작업 | 주요 내용 | 테스트 증분 |
|------|----------|-----------|
| #1 GITHUB_API 상수 승격 | 5중 중복 정의 제거 + `constants.py` 단일 출처 | — |
| #2 build_safe_client | 감사 오류 정정 — n8n/discord/slack/webhook 4곳 이미 채택 상태 | — |
| #3 Category/Severity StrEnum | registry.py StrEnum 도입 + 9 클래스 변수 + 7 리터럴 치환, 호환성 검증 | +2 |
| #4 CLAUDE.md 트리 최신화 | railway_client · notifier/registry · notifier 2모듈 · analyzer/tools 2모듈 + rename | — |
| #5 STATE.md 순서 교정 | 그룹 12 ↔ 13 시간순 재배치 | — |
| #6 env-vars.md 3필드 | CLAUDE_REVIEW_MODEL · TELEGRAM_WEBHOOK_SECRET · N8N_WEBHOOK_SECRET | — |
| #7 Repository 확충 | user_repo / repo_config_repo / gate_decision_repo 신설 + 10곳 `db.query` 치환 | +11 |
| #8a GateAction 스캐폴딩 | registry.py + actions/ 3모듈 (engine.py 는 기존 유지 — 향후 전환 대기) | +5 |
| #8b http_client 스캐폴딩 | lifespan 싱글톤 + init/close + BackgroundTasks 안전 | +4 |
| pipeline-reviewer 권고 반영 | `_score_from_result` 중복 정의 → `src/gate/_common.py` 단일화 | — |

### 그룹 13 — Phase D.2 slither 도구 추가 (2026-04-22)

| 작업 | 주요 내용 | 테스트 증분 |
|------|----------|-----------|
| 단위 테스트 선작성 (TDD Red) | supports(solidity)·is_enabled binary·JSON 파싱·impact 매핑·`_SECURITY_DETECTORS` 분류·compilation failure skip·subprocess timeout/OSError/JSONDecodeError·스키마 변형(results list) 처리 | +18 |
| `_SlitherAnalyzer` 구현 | Analyzer Protocol · stdout JSON 파싱 (`--json -`) · detector impact High/Medium → error, Low/Informational → warning · mixed-category (security/code_quality) · `_parse_slither_json` 분리로 mock 없이 검증 가능 | — |
| Registry 등록 검증 | `_register_slither_analyzers()` 명시 호출 + 속성(name/category/SUPPORTED_LANGUAGES) 확인 | +2 |
| `requirements.txt` | `slither-analyzer>=0.10.0` 추가 (+100MB, nixpacks 변경 없음) — Python provider 자동 설치 | — |
| 백엔드 불변 | Analyzer Protocol · REGISTRY · `analyze_file()` · AnalysisIssue · calculator · language.py 전부 그대로 | — |

## 갱신 방법

```bash
make test          # 1417 통과 확인
make lint          # pylint 10.00 + flake8 0건 + bandit HIGH 0개
make test-cov      # 96%+ 유지 확인 (소폭 변동 가능)

git add docs/STATE.md
git commit -m "docs(state): Phase X 완료 — 테스트 NNN개, pylint X.XX"
```

## 잔여 과제

> 🎯 **방향 전환 (2026-04-23)**: Path A (서비스화) 공식 선택 → Phase E 로드맵 가동. Phase D.5~D.8 **영구 보류**. 상세: [`reports/2026-04-23-phase-e-service-pivot-decision.md`](reports/2026-04-23-phase-e-service-pivot-decision.md).

> 👤 **사용자 수행 가이드**: P4-Gate-2 Railway 실증 (rubocop/golangci-lint) 만 남음 → [`_archive/user-actions-remaining.md`](_archive/user-actions-remaining.md) (archived). 기타 잔여 항목은 Phase E 내부 작업으로 흡수됨.

> 🧭 **과거 로드맵 (이전 방향, 2026-04-23 이전)**: [`reports/2026-04-23-remaining-roadmap-3agent.md`](reports/2026-04-23-remaining-roadmap-3agent.md). 시나리오 B 기준으로 완료된 단계들은 유효하나, **D.5~D.8 부분은 Phase E 결정으로 폐기**. 역사 문서로 보존.

| 우선순위 | 항목 | 비고 |
|---------|------|------|
| **✅ Phase Q.1~Q.6 완료 (SonarCloud 청산)** | Quality Gate OK + 3종 Rating A 달성 | [Follow-up 섹션](reports/2026-04-23-sonarcloud-baseline.md#follow-up--phase-q1q6-전체-실행-결과-2026-04-23-세션). Bugs/Vuln/Hotspots/BLOCKER 0, Code Smells 78→58 |
| **✅ Phase Q.7 완료 (CRITICAL 5건 해소)** | run_gate_check 5 헬퍼 · slither 3 헬퍼 · github_comment 6 헬퍼 · formatter 4 헬퍼 · git_diff 1 헬퍼 추출 | 커밋 `e551839` (Q.7-2~5) · `842ea1d` (Q.7-1). pipeline-reviewer 승인. 1170 passed · pylint 10.00 유지. CRITICAL 5→0. |
| **✅ Phase S.2 완료 (UI/Webhook router 분할)** | UI router → `src/ui/routes/` 5 모듈 · Webhook router → `src/webhook/providers/` 3 provider | 그룹 20 참조. mock 경로 193곳 재작성 완료, 1170 passed 유지 |
| **✅ Phase S.3 완료 (구조 정리 5단계)** | S.3-A Service 스캐폴딩 + S.3-B Analyzer pure/io + S.3-C tests/unit + S.3-E Notifier 8클래스 이동 + S.3-D UI/webhook repository_repo 확산 | 그룹 21 참조. S.3-D 는 S.4 완료와 함께 커밋 `f678222` 에 포함. |
| **✅ Phase S.4 완료 (pipeline test mock 재설계)** | test_pipeline.py fixture 를 Option A (repository_repo / analysis_repo / get_repo_config 직접 patch) 로 전환 + repository_repo.find_by_full_name 내부 filter_by → filter 전환 | 커밋 `f678222`. 1170 passed. S.1-4 · S.3-D 2회 실패의 근본 원인 해소. |
| **✅ P4-Gate-1 통과 (2026-04-23)** | D.1 cppcheck / D.2 slither 프로덕션 실증 — 6/6 통과 | `xzawed/SCAManager-test-samples` 분석 #543: cppcheck 4건 + slither 3건. 코드품질 -10, 보안 -7 감점 반영. D.3 RuboCop 해금 계기. |
| **⏳ P4-Gate-2 대기 (2026-04-23)** | D.3 rubocop / D.4 golangci-lint Railway 실증 필요 | Railway 빌드 성공 (커밋 `8042f12`) 후 사용자 샘플 PR 제출 대기. 상세: [가이드](_archive/p4-gate-2-verification.md) (archived). |
| **✅ AI 리뷰 파싱 실패 해소 (2026-04-23)** | `_extract_json_payload()` 분리 + 3가지 실패 모드 해소 | 분석 #543 경고 원인 — (1) preamble + 순수 JSON, (2) 대문자 ` ```JSON `, (3) JSON 뒤 trailing text. `re.IGNORECASE` + 첫 `{` ~ 마지막 `}` fallback. +4 tests (1188→1192). |
| **P3-리팩 완결** | 6렌즈 권고 #1~6 ✅ · #7 ✅ · #8a/#8b 스캐폴딩 | [Follow-up 섹션 참조](reports/2026-04-22-quality-audit-6lens.md#follow-up-2026-04-22--후속-실행-결과). 10커밋 완료. 실제 치환 잔존 2건(아래) |
| **P4-Gate 재료 준비 완료 (2026-04-23)** | 샘플 C/Solidity + 가이드 + 검증 스크립트 | [docs/guides/p4-gate-verification.md](guides/p4-gate-verification.md). 사용자가 외부 테스트 리포에 샘플을 넣어 PR 제출 → 6항목 체크 후 D.3 해금. |
| **⏸️ P3-후속 (보류)** | #8a GateAction 엔진 전환 + #8b http_client 15곳 채택 | Phase E 완결 후 재검토. 현재 엔진은 기능상 정상 동작, 순수 리팩토링이므로 서비스화 우선. |
| **⏸️ Phase D.5~D.8 (영구 보류, 2026-04-23)** | PHPStan / detekt / PMD / cargo clippy | Phase E 결정으로 보류. [결정 문서](reports/2026-04-23-phase-e-service-pivot-decision.md) 참조. 재개 기준: 해당 언어 PR 월 5건 이상 + E.2 완료 + Docker 전환 결정. |
| **⏸️ P5 (보류)** | pytest-cov devcontainer 이미지 캐싱 | Phase E 완결 후 재검토. 현재 CI 의 커버리지 측정으로 수치 유지 가능. |
| **🚀 Phase E.1~E.5 (활성)** | Path A 서비스화 로드맵 | E.1 (D.5~D.8 공식 중단) · E.2 (Observability) · E.3 (AI 점수 피드백) · E.4 (Minimal mode) · E.5 (Onboarding). [로드맵 문서](reports/2026-04-23-phase-e-service-pivot-decision.md). |

### D.3 차단 게이트 — ✅ 통과 (2026-04-23)

`xzawed/SCAManager-test-samples` 리포 분석 #543 (commit `a5ff800`) 으로 6/6 항목 전체 통과.

1. [x] **Railway 빌드 로그 확인** — cppcheck/slither/solc 전부 런타임 동작 확인 (간접 증거: 분석 결과에 이슈 감지)
2. [x] **solc 사전 설치 검증** — slither 결과에 `../tmp/tmpdx9ucu1a.sol#13-18` 경로 매핑 → 컴파일 성공
3. [x] **cppcheck 실증** — 4건 감지 (L12 buffer · L18 scanf · L23 unassigned · L24 uninitvar)
4. [x] **slither 실증** — 3건 감지 — L13 **reentrancy-eth** (security) · L8 solc-version · L13 low-level-calls
5. [x] **타임아웃** — 분석 완료, timeout warning 부재
6. [x] **점수 반영** — 코드품질 25→15 (-10) · 보안 20→13 (-7) 감점 확인

**게이트 통과 — D.3 RuboCop 해금**.

### Phase D 착수 전 결정 사항 (D.4 이후)

1. **도구별 GO/NO-GO 승인** — 한 번에 묶어서 승인 금지, 도구 1개씩 확인
2. **Docker 전환 여부** — JVM/Rust 계열 포함 시 이미지 2GB+ → 전환 필요
3. **우선 착수 언어 선택** — 아래 표 참고

### Phase D 도구 목록

| 우선순위 | 도구 | 언어 | 이미지 증가 | 리스크 | 비고 |
|---------|-----|-----|------------|-------|------|
| D.1 | cppcheck | C/C++ | +30MB | ✅ 완료 | 그룹 10 (2026-04-21) — apt 단순 설치 |
| D.2 | slither | Solidity | +100MB | ✅ 완료 | 그룹 13 (2026-04-22) — pip 단순 설치 |
| D.3 | RuboCop | Ruby | +80MB | ✅ 완료 | 그룹 23 (2026-04-23) — `gem install rubocop --no-document`, Security/ cop 분류 |
| D.4 | golangci-lint | Go | +200MB | ✅ 완료 | 그룹 23 (2026-04-23) — v1.55.2 installer, `_ensure_go_mod` 자동생성 |
| D.5 | PHPStan | PHP | +150MB | ⏸️ **영구 보류 (2026-04-23)** | Phase E 결정 — Semgrep 중복, PR 수요 미확인 |
| D.6 | detekt | Kotlin | +350MB | ⏸️ **영구 보류 (2026-04-23)** | Phase E 결정 — JDK + Docker 전환 필요, 수요 없음 |
| D.7 | PMD | Java | +300MB | ⏸️ **영구 보류 (2026-04-23)** | Phase E 결정 — JVM cold start 위험 |
| D.8 | cargo clippy | Rust | +700MB | ⏸️ **영구 보류 (2026-04-23)** | Phase E 결정 — crate 단위 분석, 아키텍처 불일치 |

> **재개 기준 (D.5~D.8)**: 3조건 **모두** 충족 시 재검토 — (1) 해당 언어 PR 월 5건 이상, (2) Phase E.2 Observability 완료, (3) Docker 전환/아키텍처 변경 별도 결정.
> 상세 계획: [Phase E 서비스화 결정 문서](reports/2026-04-23-phase-e-service-pivot-decision.md)

### 📚 초기 이력 (그룹 1~12, 2026-04-05 ~ 04-22)

상세 내용은 [_archive/STATE-groups-1-12-2026-04.md](_archive/STATE-groups-1-12-2026-04.md) — 원본 그대로 보존.

| 그룹 | 날짜 | 핵심 |
|------|------|------|
| 12 | 2026-04-22 | RailwayDeployEvent sub-dataclass 리팩토링 — 3-그룹 nested 구조로 전환, 외부 API 불변 |
| 11 | 2026-04-21 | 5라운드 다중 에이전트 합의 품질 감사 **95/100 A** + 후속 해소 (pytest 326.88s → 70.81s) |
| 10 | 2026-04-21 | Phase D.1 cppcheck 도구 추가 (TDD +16, C/C++ 정적분석) |
| 9 | 2026-04-21 | Settings 페이지 재설계 — 6카드 구조 + 프리셋 P1(diff)/P2(flash) + E2E +11 |
| 8 | 2026-04-21 | 5-Round 감사 후속 테스트 보강 (+5 테스트 — caplog 안정화, upsert UPDATE 분기) |
| 7 | 2026-04-20 | Railway 배포 실패 → GitHub Issue 자동 등록 (+26 테스트, Alembic 0012) |
| 6 | 2026-04-19 | UI 개선 — overview 등급 평균 기반 전환 + 쿼리 최적화 |
| 5 | 2026-04-19 | 구조적 코드품질 전면 개선 — pylint 10.00, 순환 import 해소, notifier 공통화 |
| 4 | 2026-04-19 | 다언어 AI 리뷰 + 정적분석 확장 (Phase 0~C, 50 언어, 1074 테스트) |
| 3 | 2026-04-19 | 코드 품질 / 아키텍처 리팩터 — 리포지토리 계층 + Notifier Registry + RepoConfig 동기화 해소 |
| 2 | 2026-04-17~19 | n8n 자동화 — 저점 Issue → PR 자동 생성 + merge 시 Close 파싱 + auto_merge 견고화 |
| 1 | 2026-04-05~12 | 핵심 기능 구축 — FastAPI + OAuth + Webhook + 점수 체계 + Telegram + 대시보드 + CLI Hook |
