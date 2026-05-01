# SCAManager 에이전트·스킬·슬래시 명령 인덱스

이 파일이 단일 진실 소스다. 새 에이전트·스킬 추가 시 여기에도 등재.

---

## 프로젝트 전용 에이전트 (`.claude/agents/`)

| 에이전트 | 호출 시점 | 주요 역할 |
|---------|----------|----------|
| `test-writer` | **모든 신규 기능·모듈 구현 착수 전** (TDD Red) | conftest 패턴·mock 전략 숙지, 테스트 파일 먼저 작성 |
| `pipeline-reviewer` | `src/worker/pipeline.py`, `src/analyzer/`, `src/scorer/` 변경 후 | 파이프라인 무결성·멱등성·오류 처리 검토 |
| `doc-consistency-reviewer` | CLAUDE.md / STATE.md / README / 다른 문서 변경 후 | 문서 간 수치·규칙·인용 정합성 교차 검증 |
| `doc-impact-analyzer` | 문서 수정이 Claude 행동에 영향을 줄 가능성 있을 때 | 문서 변경이 의도하지 않은 행동 변화를 유발하는지 판단 |
| `doc-quality-reviewer` | 회고·STATE·CLAUDE 갱신 직후 | 미래 세션이 오해할 수 있는 모호한 표현 식별 |

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
| `src/services/merge_retry_service.py` | CI-aware Auto Merge 재시도 워커 (`process_pending_retries`) — **PR-B3(~2026-05-06) 폐기 평가 대상**: Tier 3 PR-A 의 native auto-merge enable 신뢰성이 정량 기준 충족 시 retry queue 단순화 가능. 평가 기준은 STATE.md 그룹 53 §잔여 후속 참조. |
| `src/gate/retry_policy.py` | 재시도 정책 순수 함수 (`should_retry`, `compute_next_retry_at`, `is_expired`) |
| `src/models/merge_retry.py` | MergeRetryQueue ORM (append-only claim 패턴) |

---

## Phase H+I 신규 함수/패턴 (2026-05-01)

| 항목 | 위치 | 비고 |
|------|------|------|
| `find_by_full_name_with_owner` | `src/repositories/repository_repo.py` | opt-in joinedload — Phase H PR-3B 신규. 호출처 마이그레이션은 PR-3B-2 후속 (mock chain 70+ 갱신 필요). |
| `_GRAPHQL_MAX_ATTEMPTS` + retry helper | `src/github_client/graphql.py` | GitHub GraphQL 5xx + network error 자동 재시도 (의존성 추가 0). 다른 채널 적용 시 `src/shared/retry_helper.py` 통합 검토. |
| `TELEGRAM_RETRY_AFTER_MAX_SECONDS=30` | `src/notifier/telegram.py` | Telegram 429 retry-after cap (단일 재시도). |
| 🔴 PARITY GUARD docstring 패턴 | `src/gate/engine.py::_get_ci_status_safe` + `src/services/merge_retry_service.py::_get_ci_status_safe` | 의도적 중복 코드 drift 방지 — 양쪽 동시 수정 의무. PR-5A-2 후속에서 실제 dedup 예정. |
| 복합 인덱스 3종 (alembic 0023) | `src/models/analysis.py` + `src/models/merge_attempt.py` `__table_args__` | `ix_analyses_repo_id_created_at`, `ix_analyses_repo_id_author_login`, `ix_merge_attempts_attempted_at`. ORM `__table_args__` 와 alembic 양쪽 정의 의무. |
| FK ondelete CASCADE 일관성 | `src/models/gate_decision.py` (alembic 0024) | child 모델 4종 모두 CASCADE — 신규 child 모델 추가 시 동일 정책 적용 권장. |

> 최종 갱신: 2026-05-01 (Phase H+I 16 PR + 회고/문서 동기화 후)
