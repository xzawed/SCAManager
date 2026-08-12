---
description: DB / 마이그레이션 작업 시 적용되는 SCAManager 규칙 (path-scoped)
paths:
  - "alembic/**"
  - "src/models/**"
  - "src/database.py"
  - "src/repositories/**"
---

# DB / 마이그레이션 규칙

> 🔴 **사고 재현·측정 로그는 [`docs/_archive/rules-incident-log.md#db`](../../docs/_archive/rules-incident-log.md#db) 로 옮겼다 — 규칙을 완화·삭제하려면 아카이브를 먼저 읽을 것** (2026-08-12 밀도 압축).
> 여기 남은 것은 규칙 · 왜 한 줄 · 가드 파일명뿐이며, 서사가 짧아진 것이 규칙이 약해졌다는 뜻이 아니다.
> 역링크·앵커·절 보존 집행: `tests/unit/scripts/test_rules_archive_backlink.py`.

## 마이그레이션 PR pre-flight 체크리스트

착수 전 순서대로 확인한다(아래 상세 규칙의 액션 요약).

- [ ] **ORM Boolean/신규 컬럼** = `server_default` 지정(raw-SQL insert NOT NULL 회귀 방어)
- [ ] **신규 RLS 테이블** = 같은 마이그레이션에 `ENABLE` + `FORCE` + `_RLS_MATRIX` **3 동기화**
- [ ] **PG 전용 SQL** = `is_postgresql(op.get_bind())` 분기(SQLite 단위 테스트 자동 skip)
- [ ] **env.py URL override 영향** = `effective_migration_url` 경유
- [ ] **모델 import 완전성** = 전 모델 import + `_REGISTERED_MODELS`(미import 모델이 `drop_table` 로 잡히는 footgun 차단)
- [ ] **`make migrate` 왕복** = `downgrade -1` → `upgrade head`

🔴 **MCP 운영 DB = 정책 12** — SELECT-only 자율 / 변경·PII SELECT 는 **사용자 사전 승인**.
**호출했으면 PR 본문에 결과를 명시**한다(정책 3 — 감사 추적).

## 🔴 관측을 끄는 결함

- 🔴 **`alembic/env.py` 의 `fileConfig` 는 앱 로깅을 파괴한다 — `is_configured()` 가드 제거 금지.**
  *왜*: lifespan 이 인프로세스로 `command.upgrade()` 를 도는데, 그 시점 `fileConfig` 가
  (a) root 핸들러를 stderr 로 **교체**하고 (b) `disable_existing_loggers=True` 로 `uvicorn.access` 와
  **모든 `src.*` 로거를 비활성화**한다. 앱 INFO·access 로그가 **출시 이래 전부 소실**됐다.
  가드 형태: `if config.config_file_name is not None and not is_configured():`
  (CLI 단독 실행은 앱 설정이 없으므로 기존대로 ini 로깅 적용 — 양쪽 만족).
  🔴 **관측 부재를 외부 인프라 탓으로 돌리기 전에 앱 자신이 관측을 끄고 있는지 먼저 배제할 것.**
  가드: `tests/unit/migrations/test_alembic_env_logging_guard.py`

## 세션 라우팅 (이 파일이 본문 — 다른 영역은 여기를 가리킨다)

- 🔴 **`WorkerSessionLocal` — background/시스템 컨텍스트 전용.**
  `from src.database import WorkerSessionLocal as SessionLocal` **alias 의무**(모듈 심볼명 `SessionLocal` 유지 —
  기존 테스트 patch 대상 불변), 웹 경로는 bare 유지, **혼용 금지**.
  대상 = **background 17 모듈**(`worker/pipeline`·`webhook/providers/*`·`webhook/_helpers`·`gate/engine`·
  `gate/actions/*`·`notifier/*` lazy·`api/internal_cron`·`api/hook`·`shared/claude_metrics`)
  **+ 시스템 API 3종**(`api/repos`·`api/stats`·`api/repo_report` — `require_api_key` cross-tenant, `_SYSTEM_API_MODULES`).
  신규 background 진입점은 `tests/unit/test_worker_session_routing.py` 의 `_BACKGROUND_MODULES` 등재 의무(AST 가드가 bare import 를 fail).
  - 🔴 **hybrid 예외 = `_HYBRID_DB_MODULES` 3건**: `src/auth/github.py` · **`src/api/admin.py`** · `src/ui/routes/admin.py`.
    두 심볼을 **구분해** import 한다(**alias 금지**). github: callback=worker / logout=bare.
    admin 2종: tenants·operations(cross-tenant 집계)=worker(`_get_worker_db`) /
    등재 집행: `tests/unit/test_worker_session_routing.py`.
    🔴 **rls-audit=bare(`_get_db`) 유지 의무** — `connection_bypasses_rls` 진단은 **app role 로 평가돼야 정확**하고,
    worker 로 바꾸면 **항상 우회로 오진단**된다.
    신규 hybrid 는 `_HYBRID_DB_MODULES` 등재 + 계약 가드 + **엔드포인트별 라우팅 sentinel 가드** 의무
    (`tests/unit/test_worker_session_routing.py`).
  - `DATABASE_URL_WORKER` 미설정 시 `WorkerSessionLocal is SessionLocal`(현행 보존) / 설정 시 독립 단일 엔진
    (failover 없음 + RLS `SET LOCAL` listener 미등록 — BYPASSRLS worker role 전제).
- **`FailoverSessionFactory`** — `DATABASE_URL_FALLBACK` 설정 시 primary `OperationalError` → fallback 전환,
  daemon probe 스레드가 복구 후 자동 복귀. 소비자 코드 변경 0.
- **`CurrentUser` dataclass** — ORM 값을 복사 반환(`db.expunge()` 미사용). **관계 lazy-load 금지**(DetachedInstanceError).

## RLS

- 🔴 **RLS 활성화 미들웨어는 ASGI 여야 한다 — `BaseHTTPMiddleware` 금지.**
  *왜*: Starlette `dispatch` 가 **별도 anyio task** 에서 `call_next` 를 부르므로 **contextvars 가 전파되지 않는다**
  → `app.user_id` 가 끊겨 정책이 미적용/오적용된다.
  **등록 순서 = LIFO**(RLS inner / SessionMiddleware outer). 구현 = `src/middleware/rls_session.py` +
  `src/database.py` 의 `_set_rls_user_id_per_query`(매 query 직전 `SET LOCAL app.user_id`).
- 🔴 **RLS 작업 전 `SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user` 실측 의무.**
  *왜*: BYPASSRLS role 로 접속한 채 "RLS 동작 확인" 을 하면 **정책이 평가조차 되지 않는다**(2차 안전망 실효 0).
  🔴 **FORCE 단독 적용은 무의미하다** — BYPASSRLS 가 FORCE 를 무시한다. role 분리가 선행이다.
- 🔴 **신규 RLS 테이블 추가 시 `src/services/saas_service.py` 의 `_RLS_MATRIX` 동기화 의무.**
  *왜*: 누락 시 admin 감사 리포트(`GET /admin/rls-audit`)가 미적용 테이블 갭을 못 잡는다.
  집행: `tests/unit/test_rls_matrix_completeness.py`.
  🔴 **`FORCE` SQL 은 테이블명을 리터럴로 적는다** — f-string 루프로 조립하면 ENABLE↔FORCE 페어 가드가
  테이블을 인식하지 못해 **가드가 공허해진다**(`tests/unit/migrations/test_0041_rls_force.py`).
- 🔴 **legacy(`user_id IS NULL`) 노출은 테이블별 의도적 비대칭이다** — `0026`(analyses·merge_attempts·
  repositories)은 `OR user_id IS NULL` 로 전역 노출(legacy=admin 영역), `0027`(security_alert_process_logs)은
  **의도적으로 생략**한다. 비대칭 고정: `tests/unit/migrations/test_0027_rls_intentional_divergence.py`.
  🔴 **`0027` 에 `user_id IS NULL` 절을 추가하지 말 것** — "0026 과 일관성" 을 이유로 넣으면
  **legacy 보안 알림이 cross-tenant 로 노출**된다. 신규 정책은 비대칭을 복사하지 말고 테이블 성격으로 판단한다
  (`tests/unit/migrations/test_0027_rls_intentional_divergence.py`).
- 🔴 **env.py 는 `sqlalchemy.url` 을 `settings.effective_migration_url` 로 무조건 override 한다.**
  *왜*: 테스트에서 `cfg.set_main_option("sqlalchemy.url", ...)` **단독 설정은 무효**다.
  운영 결과 = `MIGRATION_DATABASE_URL` 미설정 시 `DATABASE_URL` 로 fallback(RLS Phase 4 credential 게이트).
  집행: `tests/unit/migrations/test_alembic_env_migration_url.py`.
  🔴 **런타임 URL(`DATABASE_URL`·`DATABASE_URL_WORKER`)을 마이그레이션 credential 로 재사용 금지** —
  `MIGRATION_DATABASE_URL` 은 **owner** 여야 한다. non-owner 로 돌면 `alembic_version` 갱신이 실패해 배포가 막히거나
  잘못된 권한으로 DDL 이 나간다(`tests/unit/migrations/test_alembic_env_migration_url.py`).

## alembic 작성 규칙

- 🔴 **`batch_alter_table` 금지** — SQLite 전용 패턴이라 PG 에서 lifespan 마이그레이션 실패 → Railway 헬스체크 실패.
  PG 는 `op.create_unique_constraint(...)` 직접 사용. **예외**: 이미 운영에 적용된 이력 마이그레이션(`0005`·`0006`).
- **dialect 분기는 `src/shared/alembic_dialect.py` 의 `is_postgresql(bind_or_conn)`** (duck typing, bind/context 양 호환).
- 🔴 **ORM 컬럼 추가 시 마이그레이션 필수 동반.**
  *왜*: 단위 테스트는 in-memory SQLite 에 ORM 정의로 테이블을 만들어서 **마이그레이션이 없어도 통과**한다 → 운영 500.
- 🔴 **인덱스는 ORM `__table_args__` + alembic 양쪽 정의 의무** — ORM-only 는 단위 테스트만 인식하고 운영 PG 에 미반영.
- 🔴 **FK `ondelete` 는 형제 child 와 일관성 검토 의무.** `analyses.id` 참조 child 4종은 전부 **CASCADE**
  (`MergeAttempt`·`MergeRetryQueue`·`AnalysisFeedback`·`GateDecision`). 다른 정책 채택 시 회고에 사유 명시.

## 리포지토리 계층

- **`merge_retry_queue` 클레임** = 단일 SQL `UPDATE … WHERE claimed_at IS NULL RETURNING (attempts_count = 1)`
  로 원자 클레임 + 첫-지연 알림 결정 동시 수행. PG 는 `FOR UPDATE SKIP LOCKED`, SQLite 는 dialect 분기.
  재배포 중 stale claim 은 5분 후 재클레임. 신규 큐도 동일 패턴 권장.
- **`Analysis.author_login`** — backfill 없이 NULL 허용, 집계는 전부 `WHERE author_login IS NOT NULL`.
  PR = `pull_request.user.login` / Push = `head_commit.author.username`. backfill = `scripts/backfill_author.py`.
- **`Repository.user_id` backfill** = `scripts/backfill_repository_user_id.py` — dry-run default + `--apply` 명시 의무.
- **`ThreadPoolExecutor` 를 `with` 로 열지 말 것** — `shutdown(wait=True)` 가 DNS hang 시 무기한 블록.
  `try/finally` + `shutdown(wait=False)`.
- **SQLite 는 `hostaddr` 제외** — `_ipv4_connect_args` 가 hostname `None` 이면 빈 dict(아니면 TypeError).
