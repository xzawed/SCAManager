# RLS role 분리 — 운영 절차

Phase 1 role · Phase 2 worker · Phase 3 FORCE(`0041`) · Phase 4 app role 전환.
테이블 = `_RLS_MATRIX` · 실측 `/admin/rls-audit`(`force_applied=true`·`connection_bypasses_rls=false`).
FORCE = owner-bypass 만 차단(BYPASSRLS 무시) — 실효는 Phase 4.

- 웹 `DATABASE_URL`=`scamanager_app`(NOBYPASSRLS·NOSUPERUSER·비-owner)
- worker `DATABASE_URL_WORKER`=`scamanager_worker`(app+`BYPASSRLS` · 미설정 시 웹 재사용)
- alembic `MIGRATION_DATABASE_URL`=owner `postgres`

## 1. 프로비저닝

두 role 에 `USAGE`·DML·시퀀스 GRANT + `ALTER DEFAULT PRIVILEGES … IN SCHEMA public`(생략 시 신규 테이블 권한 오류) → probe 로 `{host}×{user}×{port}` 확인(redeploy≠검증) → 3 URL 주입 → 재배포 → §3.

## 2. 마이그레이션 credential 게이트 (§6)

`env.py` = `effective_migration_url`(`MIGRATION_DATABASE_URL` or `DATABASE_URL`) — 미설정 시 app role 이 `alembic_version` default-deny 차단. owner·5432(6543 DDL 불가). 근거 = preDeploy 로그 head(`/health` 200 아님 · `STRICT_MIGRATION` 없으면 실패해도 기동).

## 3. 검증

`rolbypassrls` app=false·worker=true · `relrowsecurity AND NOT relforcerowsecurity` 0건 · `app.user_id` 없으면 user-owned 0건, `SET LOCAL app.user_id='<id>'` 면 본인 행.

## 4. 세션 라우팅 (Phase 4)

웹 = bare `SessionLocal` · worker·시스템 API = `WorkerSessionLocal as SessionLocal`(`test_worker_session_routing.py`).

- `rls-audit` = web 세션 — worker 면 항상 우회 오진단.
- fallback 엔진은 `SET LOCAL` listener 미등록 — 비-BYPASSRLS failover 시 웹 차단.

롤백 = `0041` downgrade + owner `DATABASE_URL`(안전망 off).
