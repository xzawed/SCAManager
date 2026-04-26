# SCAManager 에이전트·스킬·슬래시 명령 인덱스

이 파일이 단일 진실 소스다. 새 에이전트·스킬 추가 시 여기에도 등재.

---

## 프로젝트 전용 에이전트 (`.claude/agents/`)

| 에이전트 | 호출 시점 | 주요 역할 |
|---------|----------|----------|
| `test-writer` | **모든 신규 기능·모듈 구현 착수 전** (TDD Red) | conftest 패턴·mock 전략 숙지, 테스트 파일 먼저 작성 |
| `pipeline-reviewer` | `src/worker/pipeline.py`, `src/analyzer/`, `src/scorer/` 변경 후 | 파이프라인 무결성·멱등성·오류 처리 검토 |

---

## 프로젝트 전용 스킬 (`.claude/skills/`)

| 슬래시 명령 | 동작 |
|------------|------|
| `/lint` | pylint + flake8 + bandit 결과 요약 |
| `/test` | pytest 전체 또는 특정 모듈 실행 |
| `/webhook-test` | 로컬 서버에 서명된 GitHub webhook 페이로드 전송 |
| `/phase-next` | 현 Phase 완료 확인 후 다음 Phase 브레인스토밍 시작 |

---

## superpowers 플러그인 에이전트

| 에이전트 | 호출 시점 |
|---------|----------|
| `superpowers:code-reviewer` | 주요 구현 단계 완료 후 계획 대비 검토 |
| `superpowers:brainstorming` | 새 기능·Phase 착수 전 설계 단계 |
| `superpowers:systematic-debugging` | 버그·테스트 실패·예상치 못한 동작 발생 시 |
| `superpowers:test-driven-development` | 기능·버그픽스 구현 전 (test-writer와 함께) |
| `superpowers:writing-plans` | spec·요구사항이 있는 다단계 작업 전 |
| `superpowers:verification-before-completion` | 완료 선언·커밋·PR 생성 직전 |

---

## make 타겟 요약

| 명령 | 동작 |
|------|------|
| `make gate` | **Phase 완료 게이트** — pytest + pylint + flake8 + bandit |
| `make test` | pytest 전체 (빠른 출력) |
| `make test-cov` | pytest + 커버리지 |
| `make lint` | pylint + flake8 + bandit |
| `make test-file f=tests/foo.py` | 특정 파일 테스트 |
| `make run` | 개발 서버 (port 8000) |
| `make test-e2e` | E2E 테스트 (headless) |

---

## CLAUDE.md Agent 작업 규칙과의 관계

`CLAUDE.md`의 "Agent 작업 규칙" 섹션은 **언제 무엇을 써야 하는지** 규칙을 정의한다.  
이 파일은 **무엇이 있는지** 목록을 제공한다. 두 파일이 서로 보완 관계다.

> **갱신 방법**: 새 에이전트·스킬 추가 시 이 파일과 CLAUDE.md "도구 사용 시점 요약" 표를 동기화한다.

---

## Phase 12 이후 신규 서비스 모듈 (에이전트 없음, 직접 구현)

| 모듈 | 역할 |
|------|------|
| `src/services/merge_retry_service.py` | CI-aware Auto Merge 재시도 워커 (`process_pending_retries`) |
| `src/gate/retry_policy.py` | 재시도 정책 순수 함수 (`should_retry`, `compute_next_retry_at`, `is_expired`) |
| `src/models/merge_retry.py` | MergeRetryQueue ORM (append-only claim 패턴) |

> 최종 갱신: 2026-04-27 (Phase 12 완료 후)
