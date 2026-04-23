# SCAManager 프로젝트 상태

> 이 파일이 단일 진실 소스(Single Source of Truth)다. Phase 완료·주요 변경 시 여기를 먼저 갱신한다.

## 현재 수치 (2026-04-23 기준 — Phase E (E.1~E.5) 전체 완료 — Path A 완결)

| 지표 | 값 | 비고 |
|------|-----|------|
| 단위 테스트 | **1232개** | pytest (0 failed) — Phase E.5 +2 (Onboarding 3단계 튜토리얼) |
| SonarCloud Quality Gate | **OK** | CI #6 (2026-04-23) 반영 |
| SonarCloud Security Rating | **A** | Vuln 0, Hotspots 0 |
| SonarCloud Reliability Rating | **A** | Bugs 0 |
| SonarCloud Maintainability Rating | **A** | Code Smells 58 (-20 from 78) |
| SonarCloud BLOCKER / CRITICAL | **0 / 0** | Phase Q.7 완료 — 5건 Cognitive Complexity 전부 해소 |
| E2E 테스트 | **49개** | `make test-e2e` (Chromium Playwright) |
| pylint | **10.00/10** | `python -m pylint src/` — 만점 |
| 커버리지 | **96.2%** | `make test-cov` (database.py 100%, ui/router.py 99.4%) |
| bandit HIGH | **0개** | bandit 1.9.4 (Python 3.14 대응) |
| flake8 | **0건** | `flake8 src/` |
| 지원 언어 (AI 리뷰) | **50개** | language.py — Tier1/2/3 가이드 |
| 지원 언어 (정적분석) | **38개+** | Semgrep 23 + ESLint 2 + ShellCheck 1 + cppcheck 1 + slither 1 + rubocop 1 + golangci-lint 1 + Python 3 도구 |
| Tier1 정적분석 도구 | **10종** | pylint·flake8·bandit·semgrep·eslint·shellcheck·cppcheck·slither·**rubocop**·**golangci-lint** |
| pytest-asyncio | **1.3.0** | Python 3.14 DeprecationWarning 제거 완료 |

## 주요 파일 역할 (빠른 참조)

| 파일 | 역할 |
|------|------|
| `src/constants.py` | 전역 상수 단일 출처 — 점수배점·감점·AI기본값·등급·알림한도·TTL·타임아웃 |
| `src/analyzer/registry.py` | Analyzer Protocol + REGISTRY + register() + AnalyzeContext + AnalysisIssue |
| `src/analyzer/tools/*.py` | 개별 분석기 — 모듈 로드 시 자동 register() 호출 |
| `src/notifier/_common.py` | notifier 공통 헬퍼 — format_ref, get_all_issues, truncate_message |
| `src/notifier/_http.py` | HTTP_CLIENT_TIMEOUT 적용 httpx 클라이언트 빌더 |
| `src/webhook/router.py` | GitHub Webhook 수신 + per-repo secret TTL 캐시(5분) |
| `src/gate/engine.py` | 3-옵션 Gate + GateDecision upsert (중복 INSERT 방지) |
| `src/repositories/` | DB 접근 계층 — repository_repo, analysis_repo |
| `src/worker/pipeline.py` | 분석 파이프라인 + build_analysis_result_dict |
| `tests/conftest.py` | 환경변수 주입 + _webhook_secret_cache autouse 클리어 |

## 작업 이력 (그룹별)

### 그룹 1 — 핵심 기능 구축 (2026-04-05 ~ 04-12)

| 작업 | 주요 내용 |
|------|----------|
| 초기 설계 | FastAPI + PostgreSQL + GitHub OAuth + Webhook + 점수 체계 + Telegram 알림 |
| Gate 시스템 | 3-옵션(PR 댓글·Auto Approve·Telegram 반자동) 완전 독립 처리 |
| 웹 대시보드 | 리포 현황·점수 차트·분석 상세·설정 UI |
| CLI Hook | pre-push hook → AI 리뷰 → 대시보드 반영 |
| 스코어 버그 수정 | 89점 고정 문제 해소 (SHA 이동 + AI status 필드) |

### 그룹 2 — n8n 자동화 (2026-04-17 ~ 04-19)

| 작업 | 주요 내용 |
|------|----------|
| n8n Phase 1 | 저점 Issue 감지 → claude_fix.sh 실행 → PR 자동 생성 |
| n8n Phase 2 | 봇 PR auto_merge 누락 수정 (re-gate + `claude-fix/` 무한루프 가드) |
| n8n Phase 3 | PR merge 시 `Closes #N` 키워드 파싱 → GitHub Issues API 자동 close |
| auto_merge 견고성 | merge_pr tuple 반환 + mergeable_state 재시도 + Telegram 실패 알림 (+12 테스트) |

### 그룹 3 — 코드 품질 / 아키텍처 리팩터 (2026-04-19)

| 작업 | 주요 내용 | 테스트 증분 |
|------|----------|-----------|
| 리포지토리 계층 신설 | repository_repo/analysis_repo — pipeline·router db.query 직접 사용 교체 | — |
| Notifier 레지스트리 | NotifyContext + Notifier Protocol + REGISTRY + 루프 축약 | — |
| RepoConfig 동기화 해소 | dataclass fields 루프 + model_dump() — 채널 추가 시 7곳→4곳 | — |
| private→public 리네임 | _build_result_dict→build_analysis_result_dict 등 3개 함수 공개 | — |
| DB/커버리지 보강 | database.py FailoverSessionFactory 예외경로 (+16, 75%→100%) | +16 |
| UI 커버리지 보강 | ui/router.py 분기 (+11, 83.9%→99.4%) | +11 |
| 통합 테스트 | webhook→gate end-to-end 3 시나리오 | +3 |
| 테스트 엣지케이스 | gate/engine.py·auth/github.py·github_client/repos.py·알림·보안 | +28 |
| 품질 감사 7라운드 | 정상성·커버리지·결정성·격리성·pylint·flake8·bandit+E2E | — |

### 그룹 4 — 다언어 AI 리뷰 + 정적분석 확장 (Phase 0~C, 2026-04-19)

| Phase | 주요 내용 | 테스트 누계 |
|-------|----------|-----------|
| Phase 0 | language.py(50언어) + review_guides(Tier1×10/Tier2×20/Tier3×20) + review_prompt.py(토큰 예산) | 896 |
| Phase A | registry.py + tools/python.py(Analyzer Protocol) + CQ_WARNING_CAP 단일 cap | 943 |
| Phase B | tools/semgrep.py — 23개 언어, security 자동 분류, graceful degradation | 1004 |
| Phase C | tools/eslint.py(JS/TS) + tools/shellcheck.py(shell) + nixpacks 빌드 수정 | **1074** |

> Phase 0~C 통합 회고: [docs/reports/2026-04-19-multilang-expansion-retrospective.md](reports/2026-04-19-multilang-expansion-retrospective.md)

### 그룹 5 — 구조적 코드품질 전면 개선 (2026-04-19)

| 작업 | 주요 내용 |
|------|----------|
| 순환 import 해소 | AnalysisIssue를 registry.py로 이동 — static.py↔tools/*.py 순환 제거 |
| pylint 10.00 달성 | dispatch dict(language.py), _AnalysisSaveParams, _select_guide_modes 추출 |
| 하드코딩 제거 | constants.py에 16개 상수 추가 (AI 점수 범위·알림 한도·캐시 TTL·타임아웃) |
| notifier 공통화 | _common.py 신설 — 6개 알림 모듈의 이슈 수집·절단 로직 통합 |
| GateDecision upsert | save_gate_decision() — 재시도 시 중복 INSERT 방지 |
| webhook secret 캐시 | _get_webhook_secret() — DB 조회 5분 TTL 캐시 |
| 테스트 격리 | conftest.py autouse fixture — _webhook_secret_cache 테스트 간 클리어 |

### 그룹 6 — UI 개선 (2026-04-19)

| 작업 | 주요 내용 | 테스트 증분 |
|------|----------|-----------|
| overview 최근 점수 제거 | "최근 점수" 컬럼 제거 → `리포지토리\|분석\|평균 점수\|등급` 4컬럼 | +2 |
| 등급 평균 기반 전환 | `calculate_grade(avg_score)` — 최신 분석 grade 아닌 평균 점수 기반 | — |
| `_grade` 공개화 | `calculate_grade(score)` 공개 함수 (ui/router.py 재사용) | — |
| DB 쿼리 최적화 | `latest_id_subq`/`latest_map` 배치 조회 제거 (쿼리 1개 감소) | — |

### 그룹 7 — Railway 배포 실패 → GitHub Issue 자동 등록 (2026-04-20)

| 작업 | 주요 내용 | 테스트 증분 |
|------|----------|-----------|
| ORM 필드 추가 | `RepoConfig`에 `railway_deploy_alerts`/`railway_webhook_token`/`railway_api_token` + Alembic 0012 | +2 |
| railway_client 패키지 | `RailwayDeployEvent` dataclass + `parse_railway_payload()` + `fetch_deployment_logs()` | +9 |
| railway_issue notifier | `create_deploy_failure_issue()` — Search API dedup + Issue 생성 | +7 |
| Webhook 엔드포인트 | `POST /webhooks/railway/{token}` + BackgroundTask 핸들러 | +5 |
| Settings UI | 카드 ⑤ Railway 알림 + PRESETS 3개 블록 + GET/POST 핸들러 | +3 (RepoConfigData/API) |

### 그룹 8 — 5-Round 감사 후속 테스트 보강 (2026-04-21)

| 작업 | 주요 내용 | 테스트 증분 |
|------|----------|-----------|
| _notify_merge_failure 커버리지 | Telegram HTTPError 예외·skip 경로 고정 + caplog.at_level 안정화 | +2 |
| save_gate_decision UPDATE 분기 | upsert 재사용 경로 + SQLAlchemy 2.x 호환 + 교차 세션 count | +1 |
| _regate_pr_if_needed rollback | SQLAlchemyError 시 rollback + gate skip + 오류 로그 | +1 |
| _save_and_gate TOCTOU 감지 | 동시 삽입 감지 경로 고정 (신규 test_pipeline_save_and_gate.py) | +1 |
| CLAUDE.md HMAC 주석 정정 | [:16] → [:32] (128-bit) 문서 오기 수정 | — |

### 그룹 9 — Settings 페이지 재설계 (2026-04-21)

| 작업 | 주요 내용 | 테스트 증분 |
|------|----------|-----------|
| 스모크 테스트 3종 (TDD Red) | form 필드 16개 보존 · railway_deploy_alerts toggle-switch · 프리셋 `<details>` + 신규 JS 헬퍼 3종 | +3 |
| PR 카드 재편 (①) | 헤더 '⚡ PR 동작' → '📋 PR 들어왔을 때', auto_merge + merge_threshold 를 Push 카드에서 이동 | — |
| 이벤트 후 피드백 카드 통합 (②) | commit_comment / create_issue / railway_deploy_alerts 3종을 트리거별 소제목(Push 이후 / 점수 미달 시 / Railway 빌드 실패 시) 그룹핑 + raw checkbox → toggle-switch 통일 | — |
| 시스템 & 토큰 카드 통합 (⑤) | CLI Hook + Webhook 재등록 + Railway API 토큰(.masked-field + 👁️) + Railway Webhook URL 통합. 메인 `<form id="settingsForm">` + `form="settingsForm"` 바깥 필드 바인딩 | — |
| 위험 구역 카드 ⑥ 분리 | 리포 삭제 `<details>` 를 독립 카드(빨간 그라디언트)로 최하단 분리 | — |
| 프리셋 P1 diff 미리보기 | onPresetToggle 재정의 + renderPresetDiff(name) 신규 — 현재값 vs 프리셋값 9 필드 diff 테이블, 변경 필드는 var(--accent) 색상 · 불변 필드는 opacity:.45 | — |
| 프리셋 P2 적용 하이라이트 | flashPresetChanges(changedFields) 신규 + @keyframes preset-flash 2.5s 애니메이션 (box-shadow glow + background fade) | — |
| 저장 오류 UX | ?save_error=1 쿼리 감지 시 .advanced-details.open = true 자동 펼침 (문제 필드 접근성) | — |
| 백엔드 불변 | ORM·RepoConfigData·POST 핸들러·PRESETS 9개 필드·JS 헬퍼 5종 시그니처 전부 불변 | — |
| E2E 자동 검증 | 8단계 Verification 자동화 — 6카드·P1 diff·P2 하이라이트·mask-toggle·save_error 아코디언·auto_merge 위치·위험구역 분리 + 기존 3개 preset 적용 방식 업데이트 | E2E +11 (38→49) |

### 그룹 10 — Phase D.1 cppcheck 도구 추가 (2026-04-21)

| 작업 | 주요 내용 | 테스트 증분 |
|------|----------|-----------|
| 단위 테스트 선작성 (TDD Red) | supports(c/cpp/other)·is_enabled binary·XML 파싱 엣지케이스·subprocess timeout/OSError/ParseError | +14 |
| `_CppCheckAnalyzer` 구현 | Analyzer Protocol · XML v2 stderr 파싱 · `--enable=warning,style,performance,portability` · category='code_quality' · `_parse_cppcheck_xml` 분리(mock 없이 검증 가능) | — |
| Registry 등록 검증 | `_register_cppcheck_analyzers()` 명시 호출 후 REGISTRY 확인 + 속성(name/category/SUPPORTED_LANGUAGES) | +2 |
| nixpacks.toml aptPkgs | cppcheck 바이너리를 Railway 배포 이미지에 포함 (+30MB, Docker 전환 불필요) | — |
| 백엔드 불변 | Analyzer Protocol · REGISTRY · `analyze_file()` 로직 · `AnalysisIssue` · `calculator.py` · `language.py` 전부 그대로 | — |

### 그룹 11 — 5라운드 다중 에이전트 합의 품질 감사 (2026-04-21)

| 라운드 | 렌즈 | 점수 | 비고 |
|-------|------|------|------|
| R1 | 정상성 | 20/20 | 1126 passed, 0 failed, 326.88s |
| R2 | 커버리지 | 15/20 | pytest-cov 설치 불가(DNS 제약), STATE.md 96.2% 참조. 절차적 페널티 -5 |
| R3 | 결정성·격리성 | 20/20 | 3회 반복 + 역순 모두 1126 passed. CoV 3.5%. Agent B·C 합의 |
| R4 | 보안·Lint | 20/20 | pylint 10.00 / flake8 0 / bandit HIGH 0. LOW 7건 전부 false positive |
| R5 | 통합·E2E | 20/20 | 49 passed, 38.72s. Settings 재설계 E2E 커버리지 실효적 검증 |
| **합계** | **A 등급** | **95/100** | 3 에이전트 합의, ±3 초과 편차 0건 |

주요 권고 (차기 Phase 반영): `requirements-dev.txt` 에 pytest-cov 추가, `test_db_result_stores_source_pr` 14.57s 조사, `RailwayDeployEvent` sub-dataclass 분리, PyGithub `auth=` 마이그레이션.

**후속 해소 (동일일 2026-04-21)** — 3 에이전트(P/Q/R) 병렬 회귀 조사 → 근본 원인 확정 + 테스트 3파일 수정:
- `_run_static_analysis` mock 누락 (pipeline 7건 +200% 회귀 공통 원인) — `mock_deps` fixture + `test_pipeline_pr_regate.py` 시나리오 3개 모두 mock 추가
- `patch("src.notifier.n8n.notify_n8n_issue")` 경로 오류 (webhook_issues BackgroundTask DNS 블로킹) — `src.webhook.router.notify_n8n_issue` 로 변경
- Quick Win 2건 동시 반영: `pytest-cov>=5.0.0` 추가, `asyncio_default_fixture_loop_scope = function` 설정

**측정 효과**: 전체 pytest 시간 **326.88s → 70.81s (78% 단축)**. 1126 passed 유지, Production 코드 변경 0.

상세: [docs/reports/2026-04-21-quality-audit-round5.md](reports/2026-04-21-quality-audit-round5.md) 의 `Follow-up` 섹션

**잔여 권고 해소 (동일일 2026-04-21, 3건 연속)**:
- **#8** `e2e/conftest.py` `_ALEMBIC_HEAD` 자동 추출 — DAG 파싱으로 교체, 신규 마이그레이션 추가 시 수동 수정 불필요
- **#9** `tests/test_static_analyzer.py` → `tests/integration/` 이동 + `pytest.ini markers.slow` 선언 + `integration/conftest.py` 자동 마킹 (37 slow / 1089 fast / 총 1126)
- **#6** PyGithub `login_or_token` → `Auth.Token` 마이그레이션 (src/github_client/diff.py) — E2E warnings **41 → 4** (37건 제거)

**후속 해소 (2026-04-22)**:
- **#5** `RailwayDeployEvent` sub-dataclass 분리 — 그룹 12 참조. 3-그룹 nested(`RailwayProjectInfo`/`RailwayCommitInfo`/top-level) 로 재구조화 완료. pylint R0902 informational 제거, 외부 API 불변.

### 그룹 12 — RailwayDeployEvent sub-dataclass 리팩토링 (2026-04-22)

| 작업 | 주요 내용 | 테스트 증분 |
|------|----------|-----------|
| models.py 재구조화 | `RailwayProjectInfo`(3) + `RailwayCommitInfo`(3) + top-level(3) nested dataclass — pylint R0902 informational (9/7) 제거 | — |
| parser 내부 변경 | `parse_railway_payload` 시그니처 불변, sub-dataclass 생성자 호출로 내부만 전환 | — |
| notifier 접근 체인 | `railway_issue.py` 11곳 nested 접근(`event.project.*`/`event.commit.*`)으로 업데이트 (출력 문자열 불변) | — |
| 테스트 fixture 재작성 | `test_railway_client.py`(2곳) + `test_railway_issue_notifier.py`(`_EVENT` fixture nested 재작성) | — |
| 외부 API 불변 | `parse_railway_payload` · `create_deploy_failure_issue` 시그니처 · Webhook payload 스키마 · DB 전부 그대로 | — |

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

**총 증분**: 1188 → 1232 passed (+44). 모든 변경은 pylint 10.00 / flake8 0 / 회귀 없음.

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
- `xzawed/SCAManager-test-samples` 에 `.rb` · `.go` 샘플 푸시 후 rubocop/golangci-lint 실제 동작 확인 → [P4-Gate-2 가이드](guides/p4-gate-2-verification.md) 2단계부터.

### 그룹 22 — Phase Q.7 + S.4 + S.3-D 완결 + P4-Gate 재료 (2026-04-23)

3-에이전트 논의 로드맵([reports/2026-04-23-remaining-roadmap-3agent.md](reports/2026-04-23-remaining-roadmap-3agent.md)) 시나리오 B (균형형) 실행. Step 1~6·8 완료. Step 7 (P4-Gate 실증) 사용자 대기, Step 9~10 (D.3/D.4) 게이트 통과 후 해금.

| Step | 커밋 | 내용 |
|------|------|------|
| 1+2 (S.4 + S.3-D) | `f678222` | `test_pipeline.py` fixture 를 Option A (함수 단위 patch) 로 재설계 + `repository_repo.find_by_full_name` 내부 `filter_by → filter` 전환 + UI/webhook 4파일 `repository_repo` 경유 확산 (deps.py · _helpers.py · add_repo.py · railway.py). S.1-4·S.3-D 2회 실패의 근본 원인 해소. |
| 3~5 (Q.7-2~5) | `e551839` | Cognitive Complexity CRITICAL 4건 해소 — slither 3 헬퍼 · github_comment 6 헬퍼 · formatter 4 헬퍼 · git_diff 1 헬퍼 추출. 모두 순수 함수, 외부 API 불변. |
| 6 (P4-Gate 재료) | `6ec93f4` | `docs/guides/p4-gate-verification.md` + `docs/samples/p4-gate/{buffer_overflow.c, reentrancy.sol, verify_tool_hits.sh}` — 사용자 실증 PR 재료. |
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
make test          # 1107 유지 확인
make lint          # pylint 10.00 + flake8 0건 + bandit HIGH 0개
make test-cov      # 96%+ 유지 확인 (소폭 변동 가능)

git add docs/STATE.md
git commit -m "docs(state): Phase X 완료 — 테스트 NNN개, pylint X.XX"
```

## 잔여 과제

> 🎯 **방향 전환 (2026-04-23)**: Path A (서비스화) 공식 선택 → Phase E 로드맵 가동. Phase D.5~D.8 **영구 보류**. 상세: [`reports/2026-04-23-phase-e-service-pivot-decision.md`](reports/2026-04-23-phase-e-service-pivot-decision.md).

> 👤 **사용자 수행 가이드**: P4-Gate-2 Railway 실증 (rubocop/golangci-lint) 만 남음 → [`guides/user-actions-remaining.md`](guides/user-actions-remaining.md). 기타 잔여 항목은 Phase E 내부 작업으로 흡수됨.

> 🧭 **과거 로드맵 (이전 방향, 2026-04-23 이전)**: [`reports/2026-04-23-remaining-roadmap-3agent.md`](reports/2026-04-23-remaining-roadmap-3agent.md). 시나리오 B 기준으로 완료된 단계들은 유효하나, **D.5~D.8 부분은 Phase E 결정으로 폐기**. 역사 문서로 보존.

| 우선순위 | 항목 | 비고 |
|---------|------|------|
| **✅ Phase Q.1~Q.6 완료 (SonarCloud 청산)** | Quality Gate OK + 3종 Rating A 달성 | [Follow-up 섹션](reports/2026-04-23-sonarcloud-baseline.md#follow-up--phase-q1q6-전체-실행-결과-2026-04-23-세션). Bugs/Vuln/Hotspots/BLOCKER 0, Code Smells 78→58 |
| **✅ Phase Q.7 완료 (CRITICAL 5건 해소)** | run_gate_check 5 헬퍼 · slither 3 헬퍼 · github_comment 6 헬퍼 · formatter 4 헬퍼 · git_diff 1 헬퍼 추출 | 커밋 `e551839` (Q.7-2~5) · `842ea1d` (Q.7-1). pipeline-reviewer 승인. 1170 passed · pylint 10.00 유지. CRITICAL 5→0. |
| **✅ Phase S.2 완료 (UI/Webhook router 분할)** | UI router → `src/ui/routes/` 5 모듈 · Webhook router → `src/webhook/providers/` 3 provider | 그룹 20 참조. mock 경로 193곳 재작성 완료, 1170 passed 유지 |
| **✅ Phase S.3 완료 (구조 정리 5단계)** | S.3-A Service 스캐폴딩 + S.3-B Analyzer pure/io + S.3-C tests/unit + S.3-E Notifier 8클래스 이동 + S.3-D UI/webhook repository_repo 확산 | 그룹 21 참조. S.3-D 는 S.4 완료와 함께 커밋 `f678222` 에 포함. |
| **✅ Phase S.4 완료 (pipeline test mock 재설계)** | test_pipeline.py fixture 를 Option A (repository_repo / analysis_repo / get_repo_config 직접 patch) 로 전환 + repository_repo.find_by_full_name 내부 filter_by → filter 전환 | 커밋 `f678222`. 1170 passed. S.1-4 · S.3-D 2회 실패의 근본 원인 해소. |
| **✅ P4-Gate 통과 (2026-04-23)** | D.1 cppcheck / D.2 slither 프로덕션 실증 — 6/6 통과 | `xzawed/SCAManager-test-samples` 리포 분석 #543: cppcheck 4건 (L12 buffer·L18 scanf·L23/24 uninitvar) + slither 3건 (reentrancy-eth L13 포함). 코드품질 -10, 보안 -7 감점 반영 확인. D.3 RuboCop 해금. |
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
