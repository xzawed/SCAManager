# SCAManager 프로젝트 상태

> 이 파일이 단일 진실 소스(Single Source of Truth)다. Phase 완료·주요 변경 시 여기를 먼저 갱신한다.

## 현재 수치 (2026-04-19 기준 — 코드 전면 검수 완료)

| 지표 | 값 | 비고 |
|------|-----|------|
| 단위 테스트 | **1076개** | pytest (0 failed) |
| E2E 테스트 | **38개** | `make test-e2e` (Chromium Playwright) |
| pylint | **10.00/10** | `python -m pylint src/` — 만점 |
| 커버리지 | **96.2%** | `make test-cov` (database.py 100%, ui/router.py 99.4%) |
| bandit HIGH | **0개** | bandit 1.9.4 (Python 3.14 대응) |
| flake8 | **0건** | `flake8 src/` |
| 지원 언어 (AI 리뷰) | **50개** | language.py — Tier1/2/3 가이드 |
| 지원 언어 (정적분석) | **34개+** | Semgrep 23 + ESLint 2 + ShellCheck 1 + Python 3 도구 |
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

## 갱신 방법

```bash
make test          # 1074 유지 확인
make lint          # pylint 10.00 + flake8 0건 + bandit HIGH 0개
make test-cov      # 96.2% 유지 확인

git add docs/STATE.md
git commit -m "docs(state): Phase X 완료 — 테스트 NNN개, pylint X.XX"
```

## 잔여 과제

| 우선순위 | 항목 | 비고 |
|---------|------|------|
| **P4 — Phase D** | Tier 1 전용 정적분석 도구 확장 | 도구별 별도 승인 필요 (운영 리스크) |

### Phase D 착수 전 결정 사항

1. **도구별 GO/NO-GO 승인** — 한 번에 묶어서 승인 금지, 도구 1개씩 확인
2. **Docker 전환 여부** — JVM/Rust 계열 포함 시 이미지 2GB+ → 전환 필요
3. **우선 착수 언어 선택** — 아래 표 참고

### Phase D 도구 목록

| 우선순위 | 도구 | 언어 | 이미지 증가 | 리스크 | 비고 |
|---------|-----|-----|------------|-------|------|
| D.1 | cppcheck | C/C++ | +30MB | 🟢 낮음 | apt 단순 설치, 즉시 착수 가능 |
| D.2 | slither | Solidity | +100MB | 🟢 낮음 | pip install, 수요 확인 후 |
| D.3 | RuboCop | Ruby | +80MB | 🟡 중간 | gem install |
| D.4 | golangci-lint | Go | +200MB | 🟡 중간 | go.mod 자동생성 로직 필요 |
| D.5 | PHPStan | PHP | +150MB | 🟠 높음 | PHP 런타임 추가, 수요 확인 후 |
| D.6 | detekt | Kotlin | +350MB | 🟠 높음 | JDK 필요, Docker 전환 후 |
| D.7 | PMD | Java | +300MB | 🔴 최상위 | JVM cold start, Docker 전환 후 |
| D.8 | cargo clippy | Rust | +700MB | 🔴 최상위 | crate 단위 분석 — 아키텍처 변경 필요 |

> 상세 계획: [계획 문서](../../.claude/plans/sunny-inventing-deer.md) Part 2 참조
