# SCAManager 작업 유형별 실행 순서 + 도구 사용 시점 + 모바일 보호

> CLAUDE.md 필수 원칙 섹션 분리본 (사이클 92 PR-D).
> 참조용 절차 문서 — 실행 전 확인용 runbook.

---

## 작업 유형별 필수 실행 순서

**1. 새 기능 구현 시**
1. `test-writer` 에이전트 → 테스트 파일 작성 (Red)
2. Hook 자동 실행 → 실패 확인 (Red 검증)
3. 구현 코드 작성
4. Hook 자동 실행 → 통과 확인 (Green)
5. `/lint` → 코드 품질 검사 (Refactor)
6. `/test coverage` → 커버리지 확인

**2. 파이프라인 수정 시** (`src/worker/`, `src/analyzer/`, `src/scorer/`)
1. `test-writer` 에이전트 → 변경 대상 테스트 선작성
2. 구현 후 Hook 자동 실행 결과 확인
3. `pipeline-reviewer` 에이전트 → 멱등성·오류 처리·성능 검토
4. `/lint` → 보안(bandit) 포함 전체 검사

**3. Webhook/API 수정 시** (`src/webhook/`, `src/notifier/`, `src/main.py`)
1. `test-writer` 에이전트 → 엔드포인트 테스트 선작성
2. 구현 후 `/test webhook` 또는 `/test pipeline`으로 모듈 테스트
3. `/webhook-test` → 로컬 서버에서 실제 엔드-투-엔드 검증
4. 서명 검증 로직 변경 시 401/202 응답 코드 직접 확인

**4. 다음 Phase 착수 시**
1. 현행 Phase 완료 조건 모두 충족 확인 (`/test`, `/lint`)
2. `/phase-next` → 브레인스토밍 및 설계 시작
3. 설계 문서 작성 후 `test-writer` 에이전트로 Phase 첫 테스트 작성

---

## 도구 사용 시점 요약

| 도구 | 사용 시점 | 통과 기준 |
|------|----------|----------|
| PostToolUse Hook | `src/` 파일 편집 직후 자동 실행 | 0 failed |
| `/test` | Hook 실패 시 상세 분석, PR 생성 전 | 전체 통과 |
| `/test coverage` | Phase 완료 전 커버리지 확인 | 커버리지 유지 또는 향상 |
| `/lint` | 테스트 통과 후 (Refactor 단계), Phase 완료 전 | pylint 8.0+, bandit HIGH 0 |
| `/webhook-test` | Webhook·파이프라인·알림 경로 변경 후 | 202 Accepted 응답 |
| `/phase-next` | Phase 완료 조건 충족 후, 다음 Phase 착수 전 | — |
| `test-writer` 에이전트 | 모든 신규 기능·모듈 구현 착수 전 | 테스트 파일 먼저 생성 |
| `pipeline-reviewer` 에이전트 | 파이프라인 핵심 파일 변경 후 | 전 항목 ✅ |

---

## 모바일 환경 보호 — 수정 금지 파일

아래 파일들은 자동화 테스트로 검증이 불가능한 고위험 영역이다.
**`pytest, fastapi, sqlalchemy`가 import 불가능한 환경(테스트 환경 미구성)에서는 절대 수정하지 않는다.**
PreToolUse Hook(`.claude/hooks/check_edit_allowed.py`)이 자동으로 차단한다.

| 파일/경로 | 위험 유형 | 차단 조건 |
|-----------|----------|----------|
| `alembic/versions/` | DB 스키마 손상, 데이터 손실 | 테스트 환경 없을 때 |
| `src/templates/*.html` | Jinja2 렌더링 오류 (pytest 미감지) | 테스트 환경 없을 때 |
| `railway.toml` | 프로덕션 배포 실패 | 테스트 환경 없을 때 |
| `Procfile` | 프로덕션 시작 명령 오류 | 테스트 환경 없을 때 |
| `alembic.ini` | Alembic 경로 설정 오류 | 테스트 환경 없을 때 |

**예외:** `make test` 가 정상 실행되는 환경(로컬 PC, GitHub Codespaces)에서는 모든 파일 수정이 허용된다.
