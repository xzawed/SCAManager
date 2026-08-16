# RLS role 분리 — 운영 절차

운영 DB 의 앱 접속 role 과 마이그레이션 credential 을 다루는 절차.
테이블 집합의 정본은 `src/services/saas_service.py` 의 `_RLS_MATRIX` (현재 13 테이블).
FORCE 실측은 `rls_coverage_summary(db)` → `/admin/rls-audit`.

## 현재 계약

| role | 속성 | 누가 쓰는가 |
|------|------|-------------|
| `scamanager_app` | `NOBYPASSRLS` · 비-owner | 웹 요청. `DATABASE_URL` |
| `scamanager_worker` | `BYPASSRLS` · 비-owner | background / 시스템 컨텍스트. `DATABASE_URL_WORKER` |
| `postgres` (owner) | owner + 보통 `BYPASSRLS` | alembic 만. `MIGRATION_DATABASE_URL` |

- 웹 경로는 bare `SessionLocal`(app role). background 17 모듈은 `WorkerSessionLocal as SessionLocal`.
  hybrid 3건(`src/auth/github.py` · `src/api/admin.py` · `src/ui/routes/admin.py`)은 두 심볼을 구분한다.
  가드: `tests/unit/test_worker_session_routing.py`.
- **`rls-audit` 는 web 세션(`_get_db`) 유지.** `connection_bypasses_rls` 는 **현재 connection** 의
  `rolbypassrls OR rolsuper` 를 읽는다. worker 로 돌리면 항상 우회로 나온다.
- **FORCE 만으로는 부족하다.** `BYPASSRLS` role 은 FORCE 를 무시한다. owner 는 FORCE 가 있어야
  우회가 막힌다. 정본: [`.claude/rules/db.md`](../../.claude/rules/db.md) §RLS.
- `DATABASE_URL_WORKER` 미설정 시 `WorkerSessionLocal is SessionLocal` — 웹·background 가
  같은 URL 을 쓴다. worker URL 을 비-BYPASSRLS 로 두면 background 가 RLS 에 막힌다.
- fallback 엔진(`DATABASE_URL_FALLBACK`)은 RLS `SET LOCAL` listener 를 등록하지 않는다
  (`src/database.py`). 비-BYPASSRLS owner 로 failover 하면 웹 쿼리가 차단될 수 있다.

## 검증

```sql
SELECT rolname, rolbypassrls, rolsuper
FROM pg_roles
WHERE rolname IN ('scamanager_app', 'scamanager_worker', 'postgres');

SELECT relname, relrowsecurity, relforcerowsecurity
FROM pg_class
WHERE relname IN (
  'repositories', 'analyses', 'merge_attempts',
  'security_alert_process_logs', 'insight_narrative_cache', 'users',
  'repo_configs', 'gate_decisions', 'merge_retry_queue',
  'analysis_feedbacks', 'issue_registrations',
  'claude_api_calls', 'analysis_attempts'
)
ORDER BY relname;
```

기대:

- `scamanager_app.rolbypassrls = false`
- `scamanager_worker.rolbypassrls = true`
- `_RLS_MATRIX` 13 테이블 `relforcerowsecurity = true`
- 앱 접속 + `app.user_id` 미설정 → user-owned 행 0건
- 앱 접속 + `SET LOCAL app.user_id='<id>'` → 그 사용자 행만
- `GET /admin/rls-audit` → `force_applied=True` + `connection_bypasses_rls=False` + 우회 경고 없음
- 로그인(기존 계정 + 신규 가입) 성공
- `/admin/tenants` 가 전체 사용자를 보여 줌 (web RLS 로 admin 본인만 보이면 회귀)
- webhook 분석·cron 재시도가 user-owned repo 에서 동작

pooler 격리: `SET LOCAL` + `_set_rls_user_id_per_query` + 비-autocommit 세션이 전제다.
`create_engine` 이 autocommit 이면 `SET LOCAL` 이 다음 쿼리에 안 남는다.
런타임 URL 은 transaction-pooling(6543) 가능. 마이그레이션 URL 은 session(5432) 또는 direct.

## 롤백

- FORCE 제거: alembic `0041` downgrade (`NO FORCE ROW LEVEL SECURITY`).
- `DATABASE_URL` 을 owner/`postgres` 로 되돌리면 즉시 접속은 살아나지만 RLS 2차 안전망도 꺼진다.

## 연결을 바꾸기 전

Railway env 를 바꾸기 **전에** 로컬 secret-safe probe 로 `{host}×{user}×{port}` 를 돌린다.
redeploy 로 접속을 검증하지 않는다. canonical host 는 Supabase Dashboard Connect
(또는 MCP `get_project`)에서 다시 읽는다. `aws-N` prefix 는 이전될 수 있다.
상세: [`railway.md`](railway.md) 연결 invariants.

## 마이그레이션 credential

`alembic/env.py` 는 `settings.effective_migration_url`
(= `MIGRATION_DATABASE_URL` 또는 `DATABASE_URL`)로 `sqlalchemy.url` 을 덮어쓴다.
가드: `tests/unit/migrations/test_alembic_env_migration_url.py`.

- `DATABASE_URL` 이 `scamanager_app` 인데 `MIGRATION_DATABASE_URL` 이 비면
  alembic 이 app role 로 돈다. `alembic_version` 은 RLS enable + policy 0
  (default-deny)이라 비-owner 는 테이블을 못 읽는다 → 배포 실패 또는 스키마 정체.
- 런타임 `DATABASE_URL` / `DATABASE_URL_WORKER` 를 마이그레이션 credential 로 쓰지 않는다.
- `MIGRATION_DATABASE_URL` 은 owner + session 포트(5432) 또는 direct. 6543 은 DDL 과 안 맞는다.

`/health` 200 만으로 마이그레이션 성공을 단정하지 않는다.
`src/main.py::_run_migrations` 는 실패해도 `STRICT_MIGRATION` 이 아니면 앱을 띄운다.
실게이트는 `railway.toml` pre-deploy `alembic upgrade head`.
Deploy 로그에서 head revision 도달을 확인하고 `/admin/rls-audit` 로 force 를 본다.

## 신규 PG 에 role 을 만들 때

Supabase 외 온프레미스/fallback 을 켤 때 같은 SQL 을 쓴다. owner 는 `postgres` 로 두고 GRANT 만 한다.

```sql
CREATE ROLE scamanager_app LOGIN PASSWORD '<secret>' NOBYPASSRLS NOSUPERUSER;
GRANT USAGE ON SCHEMA public TO scamanager_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO scamanager_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO scamanager_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO scamanager_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO scamanager_app;

CREATE ROLE scamanager_worker LOGIN PASSWORD '<secret>' BYPASSRLS NOSUPERUSER;
GRANT USAGE ON SCHEMA public TO scamanager_worker;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO scamanager_worker;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO scamanager_worker;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO scamanager_worker;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO scamanager_worker;
```

그 다음 `DATABASE_URL` / `DATABASE_URL_WORKER` / `MIGRATION_DATABASE_URL` 을 넣고
§연결을 바꾸기 전 probe → 재배포 → §검증.

관련: `saas_service._RLS_MATRIX` · `GET /admin/rls-audit` · [`.claude/rules/db.md`](../../.claude/rules/db.md).
