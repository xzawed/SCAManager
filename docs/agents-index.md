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
| `/integrity-audit` | 전체 정합성 감사 자동화 (loop-until-dry + 3-렌즈 adversarial verify, `.claude/workflows/integrity-audit.mjs`) |
| `/retrospective` | 5+1 회고 자동화 (5 관점 finder + completeness critic, `.claude/workflows/retrospective.mjs`) |
| `/docs-sync` | 문서 수치·서사 동기화 |

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
| `py -3 scripts/pre_push_gate.py` | **push 전 게이트** — CI 가 강제하는 가드. 목록 정본 = 그 파일의 `_INTEGRITY` · `_INTEGRITY_WITH_ARGS` · `_DIFF_SCOPED`. `--full` 이면 pylint·bandit·`pytest tests/unit` 도 |
| `make gate` | ⚠️ **Phase 완료 게이트가 아니다** — pytest + pylint + bandit 뿐(flake8 **미포함** — `Makefile` 주석이 의도적 제외를 명시). 위 가드도 안 돈다. `make` 이 없는 머신이 있다(`make: command not found`) |
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

## 에이전트가 없는 모듈 (직접 구현)

`src/` 트리의 정본은 [architecture.md](architecture.md). 여기엔 에이전트 라우팅이 없는 진입점만 둔다.

| 모듈 | 역할 |
|------|------|
| `src/services/merge_retry_service.py` | CI-aware Auto Merge 재시도 워커 (`process_pending_retries`) |
| `src/gate/retry_policy.py` | `should_retry` · `compute_next_retry_at` · `is_expired` |
| `src/models/merge_retry.py` | MergeRetryQueue ORM |
| `src/repositories/repository_repo.py::find_by_full_name_with_owner` | opt-in joinedload |
| `src/github_client/graphql.py` | GraphQL 5xx + network 재시도 |
| `src/notifier/telegram.py` | `TELEGRAM_RETRY_AFTER_MAX_SECONDS` cap |
| `src/gate/engine.py::_get_ci_status_safe` ↔ `merge_retry_service` 동명 | PARITY GUARD — 의도적 중복, 양쪽 동시 수정 |
