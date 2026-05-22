---
description: DB / 마이그레이션 작업 시 적용되는 SCAManager 규칙 (path-scoped)
paths:
  - "alembic/**"
  - "src/models/**"
  - "src/database.py"
  - "src/repositories/**"
---

# DB / 마이그레이션 규칙

- 🔴 **Supabase RLS 권한 모델 + 운영 활성화 미들웨어 (Phase 3 PR 5 #223 + postlude #228)**: `alembic/versions/0026_supabase_rls_policies.py` 가 3 테이블 (`repositories`, `analyses`, `merge_attempts`) 에 RLS policy 적용 (PG 전용 + dialect 분기 — SQLite 단위 테스트 자동 skip). 세션 컨텍스트 변수 = `current_setting('app.user_id', true)` 패턴 (Supabase Auth `auth.uid()` 미사용 — GitHub OAuth 정합). 운영 활성화 = `src/middleware/rls_session.py` (request 시작 시 `scope["session"]["user_id"]` → contextvars) + `src/database.py::_set_rls_user_id_per_query` event listener (매 query 직전 `SET LOCAL app.user_id = '<id>'` 발화). 1차 안전망 = 앱 레벨 filter (`src/services/dashboard_service.py::_apply_*_user_filter`, SQLite/PG 호환). 2차 안전망 = RLS policy (PG/Supabase 전용). **🔴 ASGI middleware 의무** (BaseHTTPMiddleware 우회 — Starlette `dispatch` 가 별도 anyio task 에서 `call_next` 호출해 contextvars 전파 X). middleware 등록 순서 = LIFO (RLS inner / SessionMiddleware outer — 후자가 먼저 호출).
- **dialect 분기 helper `is_postgresql(bind_or_conn)` (사이클 82 PR 1 #272)**: `src/shared/alembic_dialect.py::is_postgresql(bind_or_conn)` (duck typing — `bind`/`op.get_context()` 양 호환). 11 사용처 일괄 치환 (alembic 0024/0026/0027/0028/0029 + `src/database.py` event listener). 예외: `alembic/env.py:88` SQLite-specific 분기 보존. 사용 패턴: `from src.shared.alembic_dialect import is_postgresql; if not is_postgresql(op.get_bind()): return`.
- 🔴 **Alembic batch_alter_table 금지**: SQLite 전용 패턴. PostgreSQL에서는 `op.create_unique_constraint('이름', '테이블', ['컬럼'])` 직접 사용. 잘못 사용 시 lifespan 마이그레이션 실패 → Railway 헬스체크 실패. **예외**: `0005_add_users_and_user_id.py`, `0006_phase8b_github_oauth.py`는 이미 프로덕션에 적용된 이력 마이그레이션이므로 수정 금지. 신규 마이그레이션(0007 이후)에만 이 규칙을 적용한다.
- **FailoverSessionFactory**: `DATABASE_URL_FALLBACK` 설정 시 Primary `OperationalError` → Fallback DB 자동 전환. `_probe_primary_loop` daemon 스레드가 복구 확인 후 자동 복귀. 미설정 시 단일 엔진 모드(probe 스레드 없음). 소비자 코드(`SessionLocal()`)는 변경 없이 그대로 사용. `engine = SessionLocal._primary_engine`으로 alembic/env.py 호환성 유지.
- **CurrentUser 데이터클래스 패턴**: `get_current_user()`는 ORM User 컬럼 값을 `CurrentUser` dataclass (`src/auth/session.py:11`) 에 복사 반환 — `db.expunge()` 미사용. 세션 종료 후 속성 접근 안전. 관계 lazy-load 사용 금지 (dataclass 에 복사되지 않은 관계 접근 시 DetachedInstanceError 발생).
- **ThreadPoolExecutor with 블록 금지**: `with` 문은 `shutdown(wait=True)` 호출 → DNS hang 시 무기한 블록. `try/finally` + `executor.shutdown(wait=False)` 패턴 사용 (database.py 참조).
- **SQLite hostaddr 제외**: `_ipv4_connect_args`는 hostname이 None(SQLite URL)이면 빈 dict 반환 — 그렇지 않으면 `sqlite3.connect(hostaddr=...)` TypeError 발생.
- **`Analysis.author_login` NULL 정책**: 신규 컬럼은 backfill 없이 NULL 허용. 모든 집계는 `WHERE author_login IS NOT NULL` 적용. backfill 필요 시 `scripts/backfill_author.py` 별도 실행. PR 이벤트 = `pull_request.user.login`, Push 이벤트 = `head_commit.author.username`.
- **`Repository.user_id` NULL backfill 스크립트**: `scripts/backfill_repository_user_id.py` (사이클 66 #229) — author_login JOIN 패턴. dry-run default + `--apply` 명시 의무. `_resolve_user_id_for_repo` pure 함수 + 4 카운터 (resolved/skipped_no_analysis/skipped_no_author/skipped_no_user). 실제 적용은 사용자 명시.
- 🔴 **ORM 컬럼 추가 시 마이그레이션 필수 동반**: `models/*.py`에 `Column(...)` 추가 후 반드시 `make revision m="설명"` 으로 마이그레이션 파일을 함께 생성해야 한다. 단위 테스트는 in-memory SQLite(`Base.metadata.create_all`)로 ORM 정의 그대로 테이블을 만들기 때문에 마이그레이션 파일이 없어도 테스트가 통과한다. 그러나 실제 DB(PostgreSQL/Railway)에는 컬럼이 생성되지 않아 운영 환경에서 500 에러가 발생한다. 전례: `leaderboard_opt_in` 컬럼 (PR #72·#74, 2026-04-26).
- **`merge_retry_queue` 클레임 패턴**: `claim_batch` 은 단일 SQL `UPDATE … WHERE claimed_at IS NULL RETURNING (attempts_count = 1) AS is_first` 로 원자적 클레임 + 첫-지연 알림 결정 동시 수행. Postgres 는 `FOR UPDATE SKIP LOCKED`, SQLite 는 dialect 분기. 재배포 중 stale claim 은 5분 후 재클레임. 신규 큐 도입 시 동일 패턴 권장.
- 🔴 **DB 인덱스 정의 — ORM `__table_args__` + alembic 양쪽 의무 (Phase H PR-4A)**: 신규 인덱스 추가 시 `models/*.py` 의 `__table_args__ = (Index(...), ...)` 와 `alembic/versions/NNNN_*.py` 의 `op.create_index(...)` 양쪽 정의 필수. ORM-only 정의는 단위 테스트 (in-memory SQLite `create_all`) 에서는 인식되지만 운영 PG 에 미반영 → 인덱스 활용 실패. 회귀 가드 테스트는 SQLAlchemy `inspect()` 로 인덱스 컬럼 검증 (`tests/unit/migrations/test_0023_composite_indexes.py` 참조).
- 🔴 **FK ondelete CASCADE 일관성 매트릭스 (Phase H C7)**: child 테이블의 `ForeignKey("parent.id")` 추가 시 다른 child 모델의 `ondelete` 정책 일관성 검토 의무. 현재 `analyses.id` 를 참조하는 child 4종 모두 CASCADE 통일:

  | child 모델 | FK 컬럼 | ondelete | 도입 시점 |
  |------|------|------|------|
  | `MergeAttempt.analysis_id` | analyses.id | **CASCADE** | Phase F.1 |
  | `MergeRetryQueue.analysis_id` | analyses.id | **CASCADE** | Phase 12 |
  | `AnalysisFeedback.analysis_id` | analyses.id | **CASCADE** | Phase E.3 |
  | `GateDecision.analysis_id` | analyses.id | **CASCADE** | Phase H C7 (alembic 0024) |

  신규 child 추가 시 동일 CASCADE 적용 (default), 다른 정책 (RESTRICT/SET NULL) 채택 시 회고에 사유 명시. application-level `delete_repo_cascade` (`ui/_helpers.py`) 는 admin script 우회 경로 보완 — DB 레벨 CASCADE 가 1차 안전망.
