# 회고: 3-에이전트 교차 감사 + 500 에러 진단 + 툴링 안전장치 (2026-04-26)

> Phase 9·10·11 완료 직후 수행된 전체 코드베이스 감사, 그 과정에서 발견된 두 가지 버그, 그리고 재발 방지 자동화 설계까지 이어진 하루의 작업 기록.

---

## 타임라인

| 순서 | 작업 | PR | 결과 |
|------|------|-----|------|
| 1 | 3-에이전트 병렬 감사 — 문서·코드·테스트 교차 검증 | #73 | 9건 불일치 수정 |
| 2 | 설정 페이지 500 에러 진단 + 마이그레이션 핫픽스 | #74 | 즉시 복구 |
| 3 | pytest e2e 혼입 현상 문서화 | #75 | CLAUDE.md 규칙화 |
| 4 | 툴링 안전장치 2개 — testpaths + 마이그레이션 완전성 검사 | #76 | 1515 passed |

---

## 1. 3-에이전트 감사 (PR #73)

### 무엇을 했나

사용자가 "여러 에이전트가 서로 활발하게 논의하고 검증한 뒤 수행"을 요청했다. 3개 전문 에이전트를 병렬로 투입했다:

- **에이전트 A** — 문서 일관성 (STATE.md·README·CLAUDE.md 수치 교차 검증)
- **에이전트 B** — 코드 구조 (아키텍처 기술 내용 vs 실제 코드 대조)
- **에이전트 C** — 테스트 구조 (이력 그룹 기술 내용 vs 실제 파일 존재 확인)

### 발견된 9건 불일치

| 심각도 | 항목 | 내용 |
|--------|------|------|
| CRITICAL | 테스트 수 | README 배지 1409 → 실측 1417 (8개 누락) |
| CRITICAL | 커버리지 배지 | 96.5% → 95% (실제 기준으로 수정) |
| MAJOR | CLAUDE.md api/ 섹션 | users.py·internal_cron.py·insights.py 3개 누락 |
| MAJOR | CLAUDE.md ui/router.py | "routes 5개" → "routes 6개" |
| MAJOR | CLAUDE.md ui/routes/ | insights.py 누락 |
| MAJOR | CLAUDE.md templates/ | insights, insights_me 누락 |
| MAJOR | CLAUDE.md analytics_service | author_trend·repo_comparison·leaderboard 함수 누락 |
| MAJOR | CLAUDE.md repositories/ | "6종" → "7종" (user_repo 추가됨) |
| MINOR | STATE.md 그룹 43 | Phase 11 그룹 이력 미기재 |

### 교훈 A — 기능 완료와 문서 갱신은 별개의 주의 수준을 요구한다

Phase 11 구현이 끝나고 PR을 머지했을 때, 코드와 테스트는 정확했다. 그러나 CLAUDE.md의 아키텍처 기술 문서는 새로 추가된 파일 6개 중 5개를 반영하지 못했다. 코드 변경 체크리스트는 잘 작동했지만, **문서 변경 체크리스트가 존재하지 않았다**.

다중 에이전트가 서로 다른 층위(수치/구조/이력)를 독립적으로 검증하고 결과를 합산했을 때, 단일 에이전트로는 놓쳤을 불일치가 드러났다. 병렬 검증의 효과가 실제로 확인된 사례다.

---

## 2. 설정 페이지 500 에러 (PR #74)

### 무엇이 문제였나

사용자가 설정 페이지 접근 시 Internal Server Error 신고. 증상: Phase 11 PR 머지 후 발생.

**진단 순서**:
1. 최근 커밋 확인 → Phase 11 PR #72 머지 직후 시작
2. `alembic/versions/` 디렉토리 목록 확인 → `0018_add_analysis_author.py` 까지만 존재, 0019 없음
3. `src/models/repo_config.py` 확인 → `leaderboard_opt_in` 컬럼 line 35에 존재
4. 결론: **ORM에 컬럼이 있는데 마이그레이션 파일이 없다**

### 왜 테스트를 통과했나

단위 테스트는 `Base.metadata.create_all(engine)` — SQLAlchemy ORM 정의를 직접 읽어 in-memory SQLite 스키마를 생성한다. Alembic 마이그레이션 파일을 전혀 거치지 않는다. ORM에 컬럼이 있으면 테스트 DB에도 생기므로, 마이그레이션 파일의 누락은 단위 테스트 레이어에서 탐지 불가능하다.

운영 DB (PostgreSQL / Railway)는 Alembic 마이그레이션 파일만 보고 ALTER TABLE을 실행한다. 파일이 없으니 컬럼이 없고, `SELECT repo_configs.*` 하면 `column "leaderboard_opt_in" does not exist` → 500.

### 수정

`alembic/versions/0019_add_repo_config_leaderboard_opt_in.py` 신규 작성.

```python
op.add_column(
    'repo_configs',
    sa.Column('leaderboard_opt_in', sa.Boolean(), nullable=False, server_default='0'),
)
```

`server_default='0'` 이 핵심이다. `nullable=False` 컬럼을 기존 행이 있는 테이블에 추가할 때, DB 엔진이 기존 행에 채울 기본값을 서버 측에서 알아야 한다. Python 레벨의 `default=False` 는 INSERT 시에만 동작하므로, ALTER TABLE 시점에는 `server_default` 가 필요하다.

### 교훈 B — ORM 컬럼 추가 = 마이그레이션 파일 필수 동반

이 버그 클래스의 특징은 **발견이 매우 늦다**는 것이다:

- 개발자가 코드를 작성할 때: 로컬 in-memory DB에서 잘 됨
- PR 리뷰 때: pytest 전부 통과
- CI에서: 여전히 통과
- 머지 후 Railway 배포: 첫 번째 실제 DB 접근 시점에서야 500

"단위 테스트가 통과 = 프로덕션 안전"이라는 암묵적 가정이 이 경우에는 성립하지 않는다. 마이그레이션 레이어는 테스트 레이어와 분리된 별도의 검증 축이다.

---

## 3. pytest e2e 혼입 현상 (PR #75)

### 무엇이 문제였나

Hook이 자동으로 pytest를 실행할 때 경로 없이 `python -m pytest --tb=short -q`를 실행했다. `pytest.ini`의 `testpaths`가 없으면 pytest는 현재 디렉토리 전체를 탐색한다 → `tests/`와 `e2e/` 모두 수집.

`e2e/`의 Playwright 테스트는 port 8001에 uvicorn 서버를 바인딩한다. Hook 실행 환경에서는 port 8001이 이미 사용 중이거나 바인딩 권한이 없어 첫 E2E 테스트가 실패 → `e2e/` 전체 파일이 `server start failed`로 cascade 실패 → 446건 failed.

처음에는 단위 테스트 446개가 갑자기 실패한 것처럼 보였다. 실제로는 전부 E2E 테스트였으며, 단위 테스트 1448개는 모두 정상이었다.

### 진단 과정

1. 실패 파일 패턴 확인 → `e2e/test_navigation.py`, `e2e/test_repo_workflow.py` 등 전부 `e2e/`
2. `-x` 플래그로 첫 실패 상세 확인 → `OSError: [WinError 10048] 이미 사용 중인 주소`: 포트 8001
3. `python -m pytest tests/ -q` 직접 실행 → 1448 passed, 1 skipped

### 교훈 C — 경로 없는 pytest 실행은 설계가 아니라 우연에 의존한다

`e2e/`와 `tests/`를 분리한 것은 정확히 이 문제를 방지하기 위한 설계였다(CLAUDE.md에도 이미 기술됨). 그러나 그 설계가 실제로 강제되려면 pytest가 경로를 지정해야 한다. 지정하지 않으면 파일 시스템 탐색이 의도를 무시한다.

---

## 4. 툴링 안전장치 (PR #76)

위 두 버그(B, C)로부터 **"코드 규칙"이 아닌 "코드로 강제되는 규칙"** 이 필요하다는 결론을 도출했다.

### testpaths = tests

```ini
[pytest]
testpaths = tests
```

한 줄 추가로 pytest가 경로 없이 실행되어도 `tests/`만 탐색한다. e2e 분리 설계가 실제로 강제된다.

### ORM-마이그레이션 완전성 검사 (67 parametrized tests)

```
tests/unit/test_migration_completeness.py
```

동작 원리:
1. 7개 ORM 모델 전부 import → `Base.metadata`에 등록
2. `alembic/versions/*.py` 전부 읽어 단일 문자열로 합침
3. 각 `(테이블, 컬럼)` 쌍에 대해 정규식 검색
4. 누락 시 `make revision m="..."` 안내와 함께 실패

다음에 누군가가 ORM에 컬럼을 추가하고 마이그레이션 파일 없이 PR을 올리면, CI에서 이 테스트가 즉시 실패한다. `alembic/versions/` 폴더가 ORM과 동기화 상태인지를 **코드가 코드를 검사**한다.

---

## 수치 요약

| 지표 | 세션 전 | 세션 후 | 변화 |
|------|---------|---------|------|
| 단위 테스트 | 1417 | 1515 | +98 |
| 문서 불일치 | 9건 | 0건 | 전부 수정 |
| 마이그레이션 누락 감지 | 없음 | CI 자동 검사 | 신규 |
| E2E 혼입 방지 | 경로 지정 필요 | testpaths 강제 | 신규 |
| PRs | — | #73 #74 #75 #76 | 4건 |

---

## 전체 회고

### 잘 된 것

**사용자의 프로세스 감각이 올바르다.** "여러 에이전트가 서로 검증한 뒤 수행"이라는 요청이 실제 버그를 발견했다. Phase 11 이후 단일 에이전트 검토로 진행했다면 문서 불일치 9건과 500 에러를 당분간 발견하지 못했을 가능성이 높다.

**증상에서 근본 원인까지 빠르게 도달했다.** 500 에러 신고 → 마이그레이션 파일 확인 → ORM 대조 → 수정까지 진단 경로가 직선적이었다. Railway rubocop/prism 사건(추측 기반 2차 실패 후 3차 성공)과 달리 첫 번째 수정이 정확했다.

**버그를 고치는 것에서 멈추지 않았다.** 500 에러를 수정하고, 왜 단위 테스트가 잡지 못했는지를 분석하고, 그 분석을 코드로 만들어 다음 같은 버그를 막는 검사기를 만들었다. 버그 수정 → 원인 분석 → 방어 코드의 전체 루프를 완성했다.

### 아쉬운 것

**마이그레이션 동반 규칙이 구현보다 교훈이 먼저 와야 했다.** `leaderboard_opt_in`은 Phase 11 설계 단계에서 이미 ORM 컬럼으로 결정됐다. 그 시점에 "ORM 컬럼 = 마이그레이션 동반 필수" 검사기가 있었다면 PR #72 리뷰 과정에서 잡혔을 것이다. 이번에는 사용자가 500 에러를 보고하고 나서야 수정됐다.

**CLAUDE.md 동기화 체크리스트가 너무 암묵적이었다.** Phase 11 구현 시 "새 파일을 추가하면 CLAUDE.md 아키텍처 섹션도 갱신"이라는 규칙은 있었지만, 6개 파일 중 5개가 빠졌다. 체크리스트 항목이 자동으로 강제되지 않으면 바쁜 구현 중에 놓치기 쉽다. 문서도 "코드로 검사"할 방법을 검토할 필요가 있다.

### 구조적 관찰

이번 세션에서 발견된 두 버그는 모두 **"테스트가 통과했지만 실제로는 틀렸다"** 유형이다:

- 마이그레이션 누락: 단위 테스트 1448개 통과, 프로덕션에서 500
- E2E 혼입: 단위 테스트 정상, 환경에 따라 446건 false failure

이 유형은 테스트 레이어 자체의 맹점(blind spot)에서 발생한다. 테스트를 더 많이 만드는 것이 아니라, **테스트가 검증하지 못하는 영역을 명시적으로 확인하는 별도 레이어**가 필요하다. PR #76의 마이그레이션 완전성 검사가 그 예시다.

---

## 다음에 적용할 것

1. **새 ORM 컬럼 추가 시**: 마이그레이션 완전성 테스트가 CI에서 자동으로 잡는다. 별도 기억 필요 없음.
2. **경로 없는 pytest 실행 시**: `testpaths = tests`가 e2e 혼입을 막는다.
3. **Phase 완료 후 문서 갱신 시**: CLAUDE.md 아키텍처 섹션의 갱신 체크리스트를 PR 템플릿에 포함하는 것을 검토할 만하다.
4. **다중 에이전트 감사**: 대형 Phase 완료 후에는 이번처럼 3-에이전트 교차 검증을 수행한다. 비용 대비 발견 효과가 입증됐다.

---

## 관련 PR

| PR | 제목 | 역할 |
|----|------|------|
| #73 | docs: 3-에이전트 교차 감사 | 문서 불일치 9건 수정 |
| #74 | fix: 0019 마이그레이션 추가 | 설정 페이지 500 에러 복구 |
| #75 | docs: ORM 컬럼 추가 시 마이그레이션 필수 규칙 | 교훈 문서화 |
| #76 | chore: pytest testpaths 고정 + 마이그레이션 완전성 검사 | 재발 방지 자동화 |

## 관련 문서

- [STATE.md](../STATE.md) — 그룹 44·45
- [CLAUDE.md](../../CLAUDE.md) — "DB/마이그레이션" 섹션 ORM 컬럼 규칙
