# Phase 12 완료 + 문서 정비 세션 회고 (2026-04-27)

## 개요

Phase 12(CI-aware Auto Merge Retry) 머지 후 CI 도구 마이그레이션 + 전체 문서 정비를 수행한 세션 회고.
하루에 PR 5개(#82·#84·#86·#87·#85 닫음)가 처리됐으며, 다중 에이전트 병렬 작업 중 브랜치 충돌 사고가 발생했다.

---

## 수행 작업

| PR | 내용 | 결과 |
|----|------|------|
| #82 | Phase 12 CI-aware Auto Merge Retry | **MERGED** — 1709 단위 테스트 |
| #84 | SonarCloud action v5 교체 | **MERGED** — deprecated `@master` → `sonarqube-scan-action@v5` |
| #86 | Phase 12 전체 문서 동기화 | **MERGED** — CLAUDE.md·STATE.md·README·guides·runbooks·reference |
| #87 | docs/ 구조 재편 | **MERGED** — `_archive/`(18개) + 로그 삭제(19개) |
| #85 | Dependabot v6 bump | **CLOSED** — v6 BREAKING CHANGE 선제 차단 |

---

## 잘 된 것

### Dependabot v6 BREAKING CHANGE 선제 차단

Dependabot이 `sonarqube-scan-action` v5 → v6 bump PR을 올렸을 때, CI 실패 로그를 직접 읽고 v6에서 "Project not found" 오류가 발생하는 breaking change임을 특정한 뒤 PR을 닫았다. 머지했다면 SonarCloud 스캔이 무음으로 깨졌을 것이다.

**교훈**: Dependabot PR은 자동 머지하지 말고 CI 실패 내용을 반드시 확인한다. `@master` 고정 액션처럼 추측 수정이 아닌 **로그 우선 원칙**을 그대로 적용.

### Phase 12 설계 품질

`merge_retry_queue`의 원자적 claim 패턴(SKIP LOCKED), SHA atomicity 보장(`expected_sha`), 첫 지연 알림 1회 제한 설계가 탄탄했다. 1709개 테스트가 모두 통과.

### 문서 동기화 범위

단순 수치 교정이 아닌 실제 누락 내용을 채웠다:
- `핵심 데이터 흐름`에 재시도 경로 3줄 추가
- Phase 12 환경변수 7개 (`docs/reference/env-vars.md`)
- Stale Claim 복구 절차 SQL (`docs/runbooks/merge-retry.md`)
- `github-integration-guide.md`에 check_suite 구독 확인 섹션 추가

### docs/_archive 접근 방식

"보존 가치 있는 것은 아카이브, 재현 가능한 로그는 삭제"라는 원칙을 세워 적용했다. `docs/_archive/README.md`에 보관 기준을 명문화해 향후 판단 기준도 남겼다.

---

## 잘 안 된 것

### 🔴 병렬 에이전트 브랜치 충돌 (PR 3개 → 1개)

**계획**: PR-A(CLAUDE.md), PR-B(STATE.md+README), PR-C(guides+runbooks+reference) 독립 브랜치에서 병렬 생성.

**실제**: 세 에이전트가 모두 현재 워킹 디렉토리의 같은 브랜치(`docs/guides-update`)에 커밋 → PR 1개에 모든 변경이 합쳐졌다.

**근본 원인**:
1. `isolation: worktree`를 PR-A(첫 번째 에이전트)에만 적용하고 나머지 에이전트에는 적용하지 않았다.
2. 에이전트 프롬프트에 "이 고유 브랜치명으로 checkout하라"는 명시적 첫 단계가 없었다.
3. 완료 기준에 "PR URL을 반환"이 없어 PR-A 에이전트가 분석만 하고 멈췄다.

**이번 결과**: 내용이 모두 올바르게 들어갔고 충돌이 없어 PR 1개로 처리 완료. 파일 충돌이 있었다면 작업 전체를 재실행해야 했을 것이다.

**추가된 규칙** (`CLAUDE.md` 병렬 에이전트 브랜치 관리 섹션):
- 독립 브랜치가 필요한 모든 에이전트에 `isolation: worktree` 적용
- 프롬프트 **첫 단계**에서 `git checkout -b <고유-브랜치명>` 명시
- 완료 기준에 "PR URL 반환" 포함

---

## 확인된 기존 규칙

| 규칙 | 검증 경위 |
|------|----------|
| 빌드 실패는 로그 우선, 추측 수정 금지 | v6 breaking change → 로그 확인 후 PR 닫음 |
| Dependabot minor/patch라도 CI 실패 확인 필수 | 동상 |
| docs/_archive에 보관, 로그는 삭제 | 이번 세션에서 원칙화 후 적용 |
| 문서 동기화는 수치만이 아닌 내용까지 | 6개 항목 신규 추가로 검증 |

---

## 향후 주의 사항

### sonarqube-scan-action v6 마이그레이션 (보류)

v6 breaking change: `sonar.projectKey` 설정 방식 변경으로 SonarCloud에서 "Project not found" 오류 발생. `sonar-project.properties` 마이그레이션이 선행되어야 한다.

```
현재: sonarqube-scan-action@v5 (안정 동작)
대기: v6 마이그레이션 가이드 검토 후 별도 PR로 진행
```

Dependabot이 다시 v6 bump PR을 올리면 위 이유로 닫는다.

### merge_retry_queue 첫 운영 모니터링

Phase 12의 핵심 기능이 첫 production PR에서 동작할 시점을 주시해야 한다. 예상 관찰 포인트:
- Stale claim(5분 초과 미해제) 발생 여부
- `terminal` 상태 도달 시 Telegram/GitHub Issue 생성 정상 여부
- `check_suite.completed` 웹훅 30초 디바운스 정상 동작 여부

### _archive 관리 기준 유지

앞으로 outdated plan·spec·가이드는 `docs/_archive/`로, 재현 가능한 로그는 삭제로 일관하게 처리한다. (`docs/_archive/README.md` 기준 참조)
