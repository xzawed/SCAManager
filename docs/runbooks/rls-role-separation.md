# RLS role 분리 — 운영 절차

Phase 1 role 프로비저닝 · Phase 2 worker 분리 · Phase 3 FORCE(`0041`) · Phase 4 app role
전환. 테이블 정본 `saas_service._RLS_MATRIX` · 실측 `/admin/rls-audit`.

- 웹 `DATABASE_URL` = `scamanager_app`(NOBYPASSRLS·비-owner)
- background `DATABASE_URL_WORKER` = `scamanager_worker`(BYPASSRLS · 미설정 시 웹 재사용)
- alembic `MIGRATION_DATABASE_URL` = owner `postgres`(BYPASSRLS)

FORCE 는 owner-bypass 만 막고 BYPASSRLS 는 무시한다 — 실효는 Phase 4 전환이다.

## 1. role 생성·전환

1) `CREATE ROLE scamanager_app LOGIN PASSWORD '<s>' NOBYPASSRLS NOSUPERUSER;` · worker 는
   동일 + `BYPASSRLS`. owner 는 `postgres` 유지 + GRANT.
2) 두 role 에 schema `USAGE`·전 테이블 DML·전 시퀀스 GRANT + `ALTER DEFAULT PRIVILEGES …
   IN SCHEMA public` 로 동일 예약(생략 시 신규 테이블 권한 오류).
3) env 교체 전 로컬 probe 로 `{host}×{user}×{port}` 확인(redeploy 는 검증이 아니다 ·
   [railway.md](railway.md)) → 3 URL 주입 → 재배포 → §3.

## 2. 마이그레이션 credential 게이트 (§6)

`alembic/env.py` 는 `effective_migration_url`(=`MIGRATION_DATABASE_URL` or `DATABASE_URL`)
을 쓴다(가드 `test_alembic_env_migration_url.py`). 비우면 alembic 이 app role 로 돌아
`alembic_version` default-deny 에 막힌다. owner + 5432/direct(6543 은 DDL 불가, 런타임 URL
은 무방). 근거는 `railway.toml` preDeploy 로그의 head 도달(`/health` 200 아님 —
`STRICT_MIGRATION` 없으면 실패해도 기동).

## 3. 검증

```sql
-- app=false·worker=true
SELECT rolname, rolbypassrls, rolsuper FROM pg_roles WHERE rolname LIKE 'scamanager%';
-- 0
SELECT count(*) FROM pg_class WHERE relrowsecurity AND NOT relforcerowsecurity;
```

1) `app.user_id` 미설정 → user-owned 0건 / `SET LOCAL app.user_id='<id>'` → 본인 행만.
2) `/admin/rls-audit` → `force_applied=true`·`connection_bypasses_rls=false`.
3) 로그인·`/admin/tenants`·webhook·cron.

## 4. 세션 라우팅 (Phase 4)

웹 = bare `SessionLocal` · background·시스템 API = `WorkerSessionLocal as SessionLocal`
(목록·hybrid 정본 `test_worker_session_routing.py`).

- `rls-audit` 는 web 세션 유지 — worker 로 돌리면 항상 우회로 오진단.
- fallback 엔진은 `SET LOCAL` listener 미등록 — 비-BYPASSRLS failover 시 웹이 막힌다.

롤백: `0041` downgrade(NO FORCE) + `DATABASE_URL` owner 복귀(안전망 off).
