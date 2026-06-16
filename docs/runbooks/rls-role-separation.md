# RLS owner-bypass 근본 해결 — 앱 role 분리 + FORCE 운영 Runbook

> 정합성 감사 full(2026-06-08) **P1 #2** — RLS '2차 안전망'이 운영에서 실효 0인 문제의 근본 해결 절차.
> `#810`(rls-audit FORCE 미설정 경고 가시화)의 후속 = 실제 remediation. **이 작업은 운영 DB(Supabase/PG)
> 권한 변경을 동반하므로 코드만으로 완결되지 않는다** — 본 runbook은 그 절차를 문서화한다.

---

## 1. 문제 (왜 RLS 2차 안전망이 지금은 작동하지 않는가)

`alembic/versions/0026_supabase_rls_policies.py`(외 0027/0028/0029/0037 누적)가 **총 11개 테이블**에 RLS policy를 **ENABLE**한다 (0026 자체는 repositories/analyses/merge_attempts 3개 — 나머지 8개는 후속 마이그레이션, 단일 출처 = `saas_service.py::_RLS_MATRIX`). **FORCE ROW LEVEL SECURITY 는 `0041_rls_force.py`(RLS Phase 3, 2026-06-10)가 11개 테이블 일괄 적용** — 운영 반영 여부는 `/admin/rls-audit` 의 `force_applied`(pg_class 실측)로 확인. 그리고 운영 앱은 현재 DB에 **`postgres`(테이블 owner + `BYPASSRLS`) role로 접속**한다 (`DATABASE_URL` — Phase 4 전환 전까지).

PostgreSQL RLS 우회 규칙:
- **테이블 owner**는 RLS를 기본 우회한다 (FORCE 미설정 시).
- **`BYPASSRLS` 속성 role**은 RLS를 **항상** 우회한다 (FORCE 설정 여부 무관).

따라서:
- 현재 (ENABLE-only + postgres 접속) → RLS USING 절이 **전혀 평가되지 않음** → 2차 안전망 실효성 **0**.
- 🔴 **`ALTER TABLE ... FORCE ROW LEVEL SECURITY`만 추가해도 무의미** — `postgres`가 `BYPASSRLS`면 FORCE를 무시한다. FORCE는 owner-bypass만 막을 뿐 BYPASSRLS-bypass는 못 막는다.
- ⚠️ 따라서 **FORCE 마이그레이션만 단독 적용 금지** — `rls-audit`의 `force_applied=True`가 거짓 안심(false confidence)을 준다. 반드시 아래 role 분리(2단계)를 **선행**해야 한다.

> 실측 근거: 메모리 `project_rls_owner_bypass_finding`(2026-06-08) — 운영 Supabase 앱이 `postgres`(`rolbypassrls=true`)로 접속함을 확인.

## 2. 현재 아키텍처 (변경 전 baseline)

| 계층 | 위치 | 동작 |
|------|------|------|
| 1차 (앱 필터) | `dashboard_service.py::_apply_*_user_filter` 등 | SQLite/PG 공통, 로그인 사용자 쿼리에 `WHERE user_id=...` |
| 2차 (RLS, 의도) | `0026` policy + `database.py::_set_rls_user_id_per_query` | 매 쿼리 직전 `SET LOCAL app.user_id` (PG only). USING 절: `user_id IS NULL OR user_id = app.user_id` |
| 세션 주입 | `middleware/rls_session.py` → `shared/rls_context` contextvar | **웹 요청**의 `session["user_id"]`만 주입 |

🔴 **background 경로(webhook / worker / cron / merge_retry_service)는 `app.user_id`를 설정하지 않는다** (실측: 해당 디렉토리에 `set_rls_user_id` 호출 0건). 현재는 `postgres`(BYPASSRLS) 접속이라 무해(모든 행 접근)하나, **FORCE+비-BYPASSRLS 전환 시 background 쿼리는 `app.user_id` 미설정 → USING 절이 `user_id IS NULL` 행만 허용 → user-owned repo의 webhook 분석·cron 재시도가 전부 차단(파이프라인 붕괴)**.

## 3. 근본 해결 절차 (3단계 — 순서 엄수)

### Phase 1 — 비-BYPASSRLS 앱 role 프로비저닝 (운영 DB 작업, 사용자)

```sql
-- Supabase SQL Editor / psql (DB 관리자 권한으로 실행)
-- 1) RLS 적용 대상 앱 role 생성 (BYPASSRLS 없음, NOSUPERUSER)
CREATE ROLE scamanager_app LOGIN PASSWORD '<강력한_시크릿>' NOBYPASSRLS NOSUPERUSER;

-- 2) 스키마/테이블 권한 부여 (owner 이전이 아니라 GRANT — owner는 마이그레이션 실행용 postgres 유지)
GRANT USAGE ON SCHEMA public TO scamanager_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO scamanager_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO scamanager_app;
-- FOR ROLE postgres: 마이그레이션 owner(postgres)가 향후 생성할 테이블/시퀀스도 자동 GRANT
-- (ALTER DEFAULT PRIVILEGES 는 실행 role 이 만든 객체에만 적용 — owner 명시 필수).
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO scamanager_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO scamanager_app;
```

> **owner 유지 + GRANT** 방식 권장: 테이블 owner를 `postgres`로 두고 앱은 비-owner·비-BYPASSRLS `scamanager_app`로 접속 → owner-bypass·BYPASSRLS-bypass 둘 다 해소. 마이그레이션(`alembic upgrade`)은 계속 `postgres`(owner)로 실행.

🔴 **Phase 1 직후 검증** (FORCE 도입 전): `scamanager_app`로 접속해도 RLS는 아직 `app.user_id` 없는 background 경로에서 owner가 아니므로 RLS가 평가된다 — 즉 **Phase 2 없이 DATABASE_URL만 바꾸면 background 파이프라인이 깨진다**. Phase 2를 먼저 설계·배포할 것.

> ✅ **Phase 1 운영 완료 (2026-06-10 — Claude MCP `execute_sql` 직접 실행, 사용자 정책 12 승인)**: `scamanager_app`(LOGIN, NOBYPASSRLS) + `scamanager_worker`(LOGIN, BYPASSRLS) 생성 + GRANT(테이블 12/12 full DML·시퀀스 11/11) + `ALTER DEFAULT PRIVILEGES FOR ROLE postgres` 등록 완료. **기능 실증**: `SET LOCAL ROLE scamanager_app` → repositories 가시 0/8 행(RLS 평가 = owner-bypass 해소) / `scamanager_worker` → 8/8(BYPASSRLS 동작 보존). 검증용 `GRANT scamanager_app/scamanager_worker TO postgres` 멤버십 유지(SET ROLE 재검증용). 🔴 임시 비밀번호는 채팅 전달됨 — **Phase 4 전 `ALTER ROLE ... PASSWORD` 교체 의무**. ⚠️ 부수 실측: `alembic_version` 이 relrowsecurity=true + policy 0건 → 비-owner role 은 default-deny(현재는 마이그레이션이 owner `postgres` 로 실행돼 무해 — Phase 4 후 앱 런타임이 이 테이블을 읽는 코드 추가 금지). 🔴 **Phase 4 caveat**: `DATABASE_URL`=app 전환 + pre-deploy `alembic upgrade head` 시 마이그레이션이 app role 로 돌아 이 default-deny 에 막힌다 → `MIGRATION_DATABASE_URL`(owner) 설정 필수(✅ #908 코드 구현 — §6 게이트, Phase 4 시 env 설정만). 적용 범위 = Supabase 만(사용자 결정 — 온프레미스는 활성화 시 동일 SQL).

### Phase 2 — background 경로 RLS 전략 (코드 설계 — 선행 필수)

background DB 세션(webhook 처리·`merge_retry_service`·cron·worker)은 특정 사용자 컨텍스트가 없으므로 `app.user_id` 미설정 → RLS USING이 차단한다. 세 옵션 (택1):

| 옵션 | 방식 | 장점 | 단점 |
|------|------|------|------|
| **A. service role 분리** (권장) | background 세션만 별도 `BYPASSRLS` service role(`scamanager_worker`)로 접속 (`DATABASE_URL_WORKER` 신설), 웹 요청은 `scamanager_app`(비-BYPASSRLS) | 명확한 권한 분리, RLS 무결성 보존 | 이중 엔진/세션 팩토리 + 라우팅 코드 |
| **B. owner 주입** | background 작업 진입 시 처리 대상 repo의 `user_id`를 `set_rls_user_id`로 주입 | 단일 role 유지 | 모든 background 진입점에 주입 누락 위험(grep 강제 가드 필요) |
| **C. service-context policy** | RLS USING에 `current_setting('app.context')='service'` 예외 추가 + background가 그 플래그 설정 | role 단일 | policy 복잡도↑, 플래그 누출 시 우회 |

**옵션 A — worker role 프로비저닝 (운영 DB, Phase 1 과 함께 실행)**:

```sql
-- background 전용 BYPASSRLS service role (webhook/cron/worker 세션용)
CREATE ROLE scamanager_worker LOGIN PASSWORD '<강력한_시크릿>' BYPASSRLS NOSUPERUSER;
GRANT USAGE ON SCHEMA public TO scamanager_worker;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO scamanager_worker;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO scamanager_worker;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO scamanager_worker;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO scamanager_worker;
```

> ⚠️ `scamanager_worker` 는 **BYPASSRLS** — background 작업이 모든 repo 접근(현 postgres 동작 보존). 웹 요청은 비-BYPASSRLS `scamanager_app`. 두 경로 분리로 RLS 무결성(웹) + 파이프라인 동작(background) 양립.

🔴 **옵션 A 선택 시 코드 작업**(별도 PR, 정책 15 High tier 사전 확인): `DATABASE_URL_WORKER` env + `WorkerSessionLocal` 팩토리 + background 진입점(`webhook/providers`, `worker/pipeline`, `services/merge_retry_service`, cron)의 세션을 worker 팩토리로 전환 + 회귀 가드(background는 worker 세션, 웹은 app 세션). `env-vars.md`·`deploy.md` 등재.

> ✅ **Phase 2 코드 구현 완료 (2026-06-10, 옵션 A — 사용자 권장안 위임 결정)**: `DATABASE_URL_WORKER` env + `database.py::WorkerSessionLocal`(`_build_worker_session_factory` — 미설정 시 `SessionLocal` 동일 객체 재사용으로 현행 보존) + background 16 모듈 alias 전환(`worker/pipeline`·`webhook/providers/*`·`webhook/_helpers`·`gate/engine`+actions 2종·`notifier` lazy 6종·`api/internal_cron`·`api/hook` — `services/merge_retry_service` 는 cron 에서 세션 주입받아 자동 커버) + ast 정적 라우팅 가드 52 테스트(`tests/unit/test_worker_session_routing.py` — alias 강제 + 전수 inventory 양방향 + 재바인딩 금지 + 모듈 객체 import 금지). **운영 활성화 잔여**: Phase 1 role 생성 → `DATABASE_URL_WORKER` env 설정(Phase 4) — 미설정 동안은 현행 동작과 완전 동일.

### Phase 3 — FORCE 적용 + 상태 반영 (Phase 1·2 완료 후)

> ✅ **Phase 3 코드 완료 (2026-06-10)**: `alembic/versions/0041_rls_force.py` — 11 테이블 리터럴 `FORCE ROW LEVEL SECURITY`(PG-only, is_postgresql 가드, downgrade=`NO FORCE`) + `saas_service.py::rls_coverage_summary(db)` 가 `pg_class.relforcerowsecurity` **실측**(bound parameter, 11/11 일치 시만 True — 마이그레이션 미적용 DB 거짓 안심 차단) + **`connection_bypasses_rls` 실측**(rolbypassrls OR rolsuper — FORCE 적용 후에도 BYPASSRLS 접속이면 `/admin/rls-audit` 에 우회 경고 배너 표시, Phase 3~4 사이 거짓 안심 창 봉인) + 호출처 2곳(`api/admin.py`/`ui/routes/admin.py`) db 전달 + `scripts/backfill_repository_user_id.py` worker 세션 alias 전환. 회귀 가드 `tests/unit/migrations/test_0041_rls_force.py`(**ENABLE↔FORCE bijection** — 신규 RLS 테이블이 FORCE 누락 시 자동 fail) + `test_0020_round_trip.py::test_migration_0041_force_round_trip_postgres`(실 PG upgrade/downgrade + 실측 양성 경로, pg-concurrency CI). **운영 반영 = 배포 시 `alembic upgrade head`**(owner `postgres` 자격) — 현 postgres 접속에서는 무해(BYPASSRLS 가 FORCE 무시). ⚠️ 표현 주의: Phase 4 의 2차 안전망 실효는 **role 전환에서 오고**, FORCE 는 비-BYPASSRLS owner 연결 사고 대비 defense-in-depth (비-owner 앱 role 은 ENABLE 만으로 RLS 평가).

```python
# 0041_rls_force.py 핵심 형태 (실제 파일은 11 테이블 리터럴 SQL — bijection 가드가
# raw 텍스트 정규식 추출이므로 f-string 루프 조립 금지)
ALTER TABLE repositories FORCE ROW LEVEL SECURITY;  # ... _RLS_MATRIX 11 테이블 전부
```

동반 (전부 완료):
- ✅ `saas_service.py::rls_coverage_summary` `force_applied` → **`pg_class.relforcerowsecurity` 실측 쿼리** 전환.
- ✅ `test_admin_settings_i18n_render.py::test_admin_rls_audit_hides_force_warning_when_applied` 가드 — `force_applied=True` 시 경고 미표시 (실측 도입 후 실제 동작 정합).
- ✅ `0026` docstring·`db.md`·본 runbook·i18n `force_warning_body`(3 locale)의 "FORCE 미적용" 서술 갱신.

### Phase 4 — DATABASE_URL 전환 (운영, 사용자)

> ✅ **Phase 4 코드 차단 경로 해소 — 옵션 ② + 시스템 API 라우팅 (2026-06-10, 사용자 결정 위임 + Codex mutual)**: Phase 4 전환 시 비-BYPASSRLS app role 에서 깨지는 **세션 없는(시스템 컨텍스트) 코드 경로 2종**을 worker 세션으로 전환.
>
> **(1) OAuth 콜백 (옵션 ②)**: `auth_callback`(`src/auth/github.py`)의 users upsert(`find_by_github_id` SELECT + 신규 User INSERT)만 `WorkerSessionLocal`(BYPASSRLS, 시스템 컨텍스트)로 전환 — 콜백 시점 `app.user_id=''` 로 인한 users self-RLS 차단 우회. `logout` 은 세션이 있어(`request.session["user_id"]`) bare `SessionLocal`(웹 RLS 경로, 본인 행) 유지. `_HYBRID_DB_MODULES`(github.py — bare+worker 둘 다 허용) 카테고리 + 계약 가드 2종(테스트 10).
>
> **(2) 시스템 API 라우트 (Codex mutual 발견 #2 Phase 4 갭)**: `require_api_key`(글로벌 키) 인증 + 세션 없이 cross-tenant 전체 데이터를 반환하는 `src/api/repos.py`·`stats.py`·`repo_report.py` 3종을 `WorkerSessionLocal as SessionLocal`(background 패턴)로 전환 — Phase 4 후 RLS 가 owned 행을 은닉/차단(`list_repos`/analyses/config/delete under-report·404)하는 것 방어. 라우팅 가드 `_SYSTEM_API_MODULES` 신설(`_WEB_API_MODULES` 에서 분리 — 이 3종은 세션 없는 시스템 컨텍스트). 현 BYPASSRLS postgres 의 cross-tenant 동작을 Phase 4 후에도 보존.
>
> **(3) admin 대시보드 cross-tenant 조회 (`src/api/admin.py` + `src/ui/routes/admin.py`)**: admin 은 `require_admin` **세션**이 있지만, `tenants`(`tenant_inventory` — User/Repository/Analysis)·`operations`(`operations_kpi` — MergeAttempt/User)는 **전체 테넌트 집계**라 Phase 4 admin 세션 RLS(`app.user_id=admin`)가 admin 본인 행만 남겨 under-report 한다. 두 엔드포인트만 `_get_worker_db`(BYPASSRLS) 경유로 분기 — admin 대시보드 cross-tenant 가시성 보존. 🔴 **`rls-audit` 는 web 세션(`_get_db`) 유지 의무**: `connection_bypasses_rls` 가 **현재 connection 의 rolbypassrls** 를 실측하는 진단이라 웹 app role 로 평가돼야 정확하다(worker=BYPASSRLS 면 항상 우회=TRUE 오진단). → admin 2 모듈 = `_HYBRID_DB_MODULES`(엔드포인트별 web/worker 분기). 엔드포인트별 세션 라우팅은 sentinel 회귀 가드(`test_admin_endpoints.py`)로 봉인.
>
> `DATABASE_URL_WORKER` 미설정 동안은 `WorkerSessionLocal is SessionLocal` 이라 **현행 동작과 완전 동일** — Phase 4 에서 worker URL 설정 시 자동 발효.
>
> ✅ **세션 없는/cross-tenant 코드 차단 경로 전부 해소** (OAuth 콜백 + 시스템 API 3종 + admin 대시보드 2종). 🔴 **잔여 = Phase 4 운영 전환만**(아래 §Phase 4 명령 — `DATABASE_URL`/`DATABASE_URL_WORKER` 설정 + PW 교체, 사용자).

> **이전 blocker 서술 (해소 전 — 근거 보존)**: OAuth 로그인 경로가 users self-RLS 에 차단된다 — `auth_callback` 은 웹 `SessionLocal` 로 upsert 를 수행하는데 콜백 시점 `session["user_id"]` 부재 → `app.user_id=''` → `users_self_isolation`(0029, `id = app.user_id`, FOR ALL = implicit WITH CHECK) 이 SELECT/INSERT 모두 거부. `scamanager_app`(비-owner) 전환 즉시 전원 로그인 불가 (FORCE 무관, 0041 롤백으로도 미해소). 검토 옵션: ① 별도 policy/컨텍스트 키 ② auth upsert worker 세션 경유(채택) ③ users policy WITH CHECK 분리.

```
DATABASE_URL=postgresql://scamanager_app:<시크릿>@<host>/<db>      # 웹 요청 (비-BYPASSRLS)
DATABASE_URL_WORKER=postgresql://scamanager_worker:<시크릿>@<host>/<db>  # 옵션 A 시 background (BYPASSRLS)
```
마이그레이션 실행은 별도 owner(`postgres`) 자격으로 (`alembic upgrade head`). ✅ **메커니즘 = `MIGRATION_DATABASE_URL` (#908 구현)** — `alembic/env.py` 가 `settings.effective_migration_url`(= `migration_database_url or database_url`)을 `sqlalchemy.url` 로 사용하므로, Phase 4 전환 시 `MIGRATION_DATABASE_URL`(owner)을 설정하면 pre-deploy(`railway.toml preDeployCommand`)·lifespan 마이그레이션이 owner 자격으로 실행돼 `alembic_version` default-deny 를 회피한다. 🔴 **Phase 4 전 `MIGRATION_DATABASE_URL` env 설정 필수**(§6 게이트 — 미설정 시 `DATABASE_URL`=app fallback → 차단).

### Phase 4 전환 실행 순서 (transition-day — 단계별 게이트)

> 🔬 **운영 현재 상태 실측 (2026-06-11 → 2026-06-16 갱신, Supabase `qaoirpyhldlkeoyppfwq` read-only — 정책 12 SELECT 자율)**: Phase 1 role ✅ — `scamanager_app`(rolbypassrls=**false**)·`scamanager_worker`(rolbypassrls=**true**) 존재 + GRANT app/worker SELECT·INSERT 12/12 + policy 11/11. ✅ **step 0 운영 완료 (2026-06-16)**: 사용자가 Railway 대시보드 pre-deploy=`alembic upgrade head` 동기화(#906) + 재배포 → **alembic `0038`→`0041`** + **`pg_class.relforcerowsecurity=true` 11/11**(force_applied=True 실측). ✅ **step 1/2/3 운영 전환 검증 완료 (2026-06-16 — docs #920)**: 사용자 step 1(PW 교체, SQL Editor)+step 2(`DATABASE_URL`→`scamanager_app`·`DATABASE_URL_WORKER`→`scamanager_worker`·`MIGRATION_DATABASE_URL`→postgres/owner[#908])+재배포 후 재확인 검증 — `pg_stat_activity` 라이브 **앱=`scamanager_app`(rolbypassrls=false)** 접속 실측(더 이상 postgres 아님) + alembic 0041·force 11/11 + `SAAS_ADMIN_EMAILS` 설정 후 `/admin/rls-audit` UI 매트릭스 11/11·**경고 배너 없음** + 로그인 smoke(`xzawed`)·대시보드 실데이터 정상 = **connection_bypasses_rls=False**. `alembic_version`(enabled·not-forced·policy 0)은 #908 `MIGRATION_DATABASE_URL` owner 게이트로 마이그레이션 정상. 🔴 **잔여 = 선택 심층검증만**(신규가입 smoke·cross-tenant 누출 pooler 격리·`/admin/tenants` cross-tenant 가시성 — 비차단).

| # | 작업 | 주체 | 게이트 (다음 단계 진입 조건) |
|---|------|------|------------------------------|
| **0** ✅ | ~~최신 main 운영 배포 → `alembic upgrade head` 가 0039→0041 적용(FORCE on)~~ **완료 (2026-06-16)** — 사용자 Railway pre-deploy 동기화(#906)+재배포 → alembic 0041·force 11/11. 이 시점 아직 `postgres`(BYPASSRLS) 접속 = **차단 0**(안전). | 사용자 | ✅ `force_applied=True` 실측(MCP). (`connection_bypasses_rls=True` + 경고 배너 = **정상** — URL 전환 전 BYPASSRLS 접속이라 기대값) |
| **1** ✅ | `scamanager_app`·`scamanager_worker` PW 교체(`ALTER ROLE ... PASSWORD`) — Phase 1 임시 PW 폐기 | 사용자 | ✅ **완료 (2026-06-16)** — SQL Editor 직접 교체 |
| **2** ✅ | `DATABASE_URL`=scamanager_app + `DATABASE_URL_WORKER`=scamanager_worker + `MIGRATION_DATABASE_URL`=postgres/owner(#908) (Railway env) → 재배포 | 사용자 | ✅ **완료 (2026-06-16)** — `/health` 200 + `pg_stat_activity` 라이브 `scamanager_app`(bypassrls=false) 접속 실측 |
| **3** 🟡 | 종단 검증 (§4 항목) — **핵심 완료 (2026-06-16 docs #920)** | 사용자 | ✅ 로그인 smoke(`xzawed`) · ✅ `rls-audit` 경고 미표시 + force 11/11 + connection_bypasses_rls=False(pg_stat_activity 실측) · ✅ 대시보드 실데이터 · 🟡 **선택 잔여**: 신규가입 smoke·`/admin/tenants` cross-tenant·pooler `SET LOCAL` 격리 |

🔴 **0번 배포와 1번 비밀번호 교체는 독립 선행 작업**이다. 비밀번호 교체 자체는 RLS 접속 role을 바꾸지 않는다. **2번 URL 전환은 0번 `force_applied=True`와 1번 신규 PW 접속 성공을 모두 확인하기 전 금지**(Phase 3 미완 상태에서 role 전환 시 2차 안전망 미확인 + background 차단 위험). 이후 단계는 직전 게이트 미충족 시 진입 금지. 롤백: §5(`DATABASE_URL`→`postgres` 복귀).

> 🔴 **lifespan 마이그레이션 silent-fail 주의 (회고 DOC-2)** — step 2 게이트의 `/health` 200 만으로 마이그레이션 성공을 단정 금지. `src/main.py::_run_migrations` 는 `asyncio.wait_for(timeout=30)` + broad-except 로 감싸여 마이그레이션 실패 시에도 `logger.error("... starting app anyway")` 후 앱을 띄운다(`/health` 200 반환). 즉 Phase 4 에서 `MIGRATION_DATABASE_URL`(owner) 미설정으로 app role 마이그레이션이 `alembic_version` default-deny 에 막히면 **pre-deploy(`railway.toml`, loud-fail = 배포 중단)만 이를 가시화**하고 lifespan 은 무음 통과한다. 따라서 재발 방지의 실효는 pre-deploy 단독에 달려 있으므로(대시보드 설정으로 pre-deploy 가 비활성/변경되면 lifespan silent-fail 로 회귀 — railway.toml 주석 참조), **transition-day 에는 Railway Deploy 로그에서 `alembic upgrade head` 성공(head revision 도달)을 직접 확인** + `/admin/rls-audit` 의 alembic version/force 실측을 step 2 게이트로 삼는다.

## 4. 검증

```sql
-- role 속성 확인 (앱 role은 rolbypassrls=false 여야 함)
SELECT rolname, rolbypassrls, rolsuper FROM pg_roles WHERE rolname IN ('scamanager_app','scamanager_worker','postgres');

-- FORCE 적용 확인 (11 테이블 relforcerowsecurity=true)
SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class
WHERE relname IN ('repositories','analyses', ...) ORDER BY relname;
```
- 앱(`scamanager_app`) 접속 + `app.user_id` 미설정 → user-owned 행 **0건**(격리 동작 확인).
- 앱 접속 + `SET LOCAL app.user_id='<id>'` → 해당 사용자 행만.
- `GET /admin/rls-audit` → `force_applied=True` + `connection_bypasses_rls=False` + 경고 배너 미표시. (Phase 4 전 = `connection_bypasses_rls=True` → BYPASSRLS 우회 경고 배너 표시가 정상 — 거짓 안심 창 가시화, RLS Phase 3.)
- 🔴 **로그인 smoke (Phase 4 P1 blocker 페어)**: 기존 사용자 재로그인 + 신규 GitHub 계정 가입이 모두 성공해야 한다 — auth 경로 RLS 전략 적용 검증.
- 🔴 **admin 크로스테넌트 가시성**: `/admin/tenants` 가 전체 사용자를 표시하는지 확인 (웹 세션 RLS 로 admin 1명만 보이면 under-report 회귀).
- 🔴 **background 파이프라인 smoke**: 옵션 A worker role로 webhook 분석·cron 재시도가 user-owned repo에 정상 동작(차단 0).
- 🔴 **pooler 테넌트 격리 smoke (deep-research 외부 검증 P1, 2026-06-10)**: Supabase pooler(Supavisor) 경유 시 **세션 변수의 풀링 안전성 실측 의무**. AWS RDS 가이드는 "세션 변수는 server-side pooling(pgBouncer)과 비호환일 수 있으니 풀링 전략이 세션 상태를 공유하는지 테스트하라"고 명시. SCAManager 는 `SET LOCAL`(트랜잭션 스코프) + `_set_rls_user_id_per_query`(매 쿼리 직전 재발화) + `sessionmaker(autocommit=False)` 조합이라 transaction-pooling 모드에서 안전(SET LOCAL 이 매 트랜잭션 재설정)이 **설계상 기대**되나, **운영 pooler 모드(transaction 6543 vs session 5432) + 실제 엔진 isolation_level 이 autocommit 아님**을 Phase 4 전환 시 실측 확인. 검증: 두 테넌트 A/B 의 요청을 풀 재사용이 발생하도록 교차 부하 → A 가 B 행을 보지 못함(누출 0) + `app.user_id` 미설정 쿼리가 default-deny(0행) 확인. 🔴 **autocommit 엔진이면 `SET LOCAL` 이 별도 트랜잭션으로 분리돼 다음 쿼리에 미적용 → 테넌트 누출/전면 차단 위험** — `create_engine(..., isolation_level=...)` 비-autocommit 보장 의무.

## 5. 롤백

- FORCE 제거: `ALTER TABLE ... NO FORCE ROW LEVEL SECURITY` (마이그레이션 downgrade).
- `DATABASE_URL`을 `postgres`로 복귀 (즉시 owner/BYPASSRLS-bypass 복원 → 차단 해소, 단 2차 안전망도 다시 0).

## 6. Pre-flight 체크리스트 (RLS 작업 착수 전 의무)

- [ ] 🔴 **연결/auth 진단 = Railway env 변경 *전* 로컬 secret-safe probe 의무 (2026-06-15 prod 다운 학습)** — Phase 4 의 `DATABASE_URL`/`DATABASE_URL_WORKER` 전환·PW 교체 후 접속 검증은 **redeploy 로 검증하지 않는다**. gitignore 된 `.dbpw` + 1회성 psycopg2 probe(이미 의존성)로 `{host}×{user}×{port}` 매트릭스를 *내가 직접* 돌려 `select 1` OK 확인 후 진행. canonical host = Supabase MCP `get_project` / Dashboard Connect 재도출(stale 로그 가정 금지 — `aws-N` prefix 가변). 상세: [`railway.md` §Railway↔Supabase 연결 invariants](railway.md) · 메모리 `feedback-connectivity-probe-first`.
- [ ] 🔴 **마이그레이션 credential 게이트 — Phase 4 시 `MIGRATION_DATABASE_URL`(owner) 설정 (두 번째 벽, 정책 15 High tier)** — `alembic/env.py` 가 `sqlalchemy.url` 을 `settings.effective_migration_url`(= `migration_database_url or database_url`)로 override 한다 (`MIGRATION_DATABASE_URL` 미설정 시 `DATABASE_URL` fallback). Phase 4 에서 `DATABASE_URL`=`scamanager_app`(비-BYPASSRLS)로 바꾸면서 **`MIGRATION_DATABASE_URL`(owner)을 설정하지 않으면** pre-deploy `alembic upgrade head`(`railway.toml`)·lifespan `_run_migrations` 가 app role 로 실행 → `alembic_version`(relrowsecurity=true·policy 0건 = default-deny)을 비-owner app role 이 못 읽어 마이그레이션 실패·배포 차단. 따라서 Phase 4 전에 마이그레이션 전용 owner credential(`MIGRATION_DATABASE_URL`)을 분리하고 pre-deploy/lifespan 이 이를 사용해야 한다 — ✅ **코드 구현 완료 (#908)**: `config.py` `effective_migration_url`(= `migration_database_url or database_url`) + `alembic/env.py` 가 이를 `sqlalchemy.url` 로 사용. **Phase 4 시 `MIGRATION_DATABASE_URL`(owner) env 설정만 잔여**(미설정 시 `DATABASE_URL`=app fallback → 차단). 🔴 런타임 `DATABASE_URL`/`DATABASE_URL_WORKER` 를 마이그레이션 credential 로 수용 금지. (`pg_class` 실측: `alembic_version` relrowsecurity=true·policy 0건 — §Phase 1 운영 완료 노트.)
  - 🔴 **pooler 모드 caveat (회고 DOC-3)**: `MIGRATION_DATABASE_URL` 은 owner(`postgres`) credential + **session-pooling 포트(5432) 또는 direct 호스트 권장**. Supabase transaction-pooling(6543)은 DDL 다수·트랜잭션 경계·prepared statement 가 많은 alembic 마이그레이션과 세션 상태 비공유로 비호환 가능 → 예기치 않은 마이그레이션 실패 위험. Railway 는 Outbound IPv6 가 opt-in(기본 비활성)이라 기본 egress=IPv4 → direct `db.<ref>`(IPv6-only) 도달 불가(Outbound IPv6 활성 시 예외) → pooler 의 **session 포트(5432)** 사용. 런타임 `DATABASE_URL` 은 transaction-pooling(6543)이어도 무방하나 마이그레이션 URL 은 session/direct 로 분리 권장. (실제 host/포트는 transition-day 에 Supabase Dashboard Connect 에서 재도출 — §6 pre-flight probe 페어.)
- [ ] **접속 role의 `rolbypassrls` 실측** — `SELECT rolbypassrls FROM pg_roles WHERE rolname=current_user;` (메모리 `project_rls_owner_bypass_finding` 의무) — `/admin/rls-audit` 의 `connection_bypasses_rls` 가 동일 실측(rolbypassrls OR rolsuper)을 자동 표기
- [x] 🔴 **OAuth 로그인 경로(users self-RLS) 전략 확정** — ✅ 옵션 ②(auth upsert worker 세션 경유) 코드 완료(2026-06-10). `/admin/tenants` under-report 는 잔여(별도 권한 결정, §Phase 4 참조)
- [ ] Phase 2(background 전략) **설계·배포 완료** 확인 — 미완 시 Phase 4(URL 전환) 금지(파이프라인 붕괴)
- [x] ✅ **0041 FORCE 운영 반영 확인 — `force_applied=True`** (✅ **2026-06-16 step 0 완료**: 사용자 Railway pre-deploy 동기화(#906)+재배포 → alembic `0038`→`0041` + `pg_class.relforcerowsecurity=true` 11/11 MCP 실측. 이전 2026-06-11 = `0038`<`0041` FORCE 미적용이었음. §Phase 4 전환 실행 순서 0번)
- [ ] **fallback/온프레미스 DB 에 0041 수동 적용 시 해당 접속 role rolbypassrls 실측 의무** — fallback engine 은 RLS `SET LOCAL` listener 미등록(`src/database.py` — primary engine 한정)이라, 비-BYPASSRLS owner 접속이면 failover 중 web 쿼리가 `app.user_id` 미설정 상태로 차단될 수 있다
- [ ] 백업/스냅샷 (Supabase PITR) 확보
- [ ] 저트래픽 시간대 (사용자 생활 패턴: 저녁 작업)

---

**관련**: `0026` policy / `saas_service::_RLS_MATRIX` (11 테이블 단일 출처) / `GET /admin/rls-audit` (#810 경고) / `db.md` RLS 규칙 / 정합성 감사 #2.
