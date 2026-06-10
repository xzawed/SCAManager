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

> ✅ **Phase 1 운영 완료 (2026-06-10 — Claude MCP `execute_sql` 직접 실행, 사용자 정책 12 승인)**: `scamanager_app`(LOGIN, NOBYPASSRLS) + `scamanager_worker`(LOGIN, BYPASSRLS) 생성 + GRANT(테이블 12/12 full DML·시퀀스 11/11) + `ALTER DEFAULT PRIVILEGES FOR ROLE postgres` 등록 완료. **기능 실증**: `SET LOCAL ROLE scamanager_app` → repositories 가시 0/8 행(RLS 평가 = owner-bypass 해소) / `scamanager_worker` → 8/8(BYPASSRLS 동작 보존). 검증용 `GRANT scamanager_app/scamanager_worker TO postgres` 멤버십 유지(SET ROLE 재검증용). 🔴 임시 비밀번호는 채팅 전달됨 — **Phase 4 전 `ALTER ROLE ... PASSWORD` 교체 의무**. ⚠️ 부수 실측: `alembic_version` 이 relrowsecurity=true + policy 0건 → 비-owner role 은 default-deny(마이그레이션은 owner `postgres` 실행이라 무해 — Phase 4 후 앱 런타임이 이 테이블을 읽는 코드 추가 금지). 적용 범위 = Supabase 만(사용자 결정 — 온프레미스는 활성화 시 동일 SQL).

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

> ✅ **OAuth 로그인 blocker 해소 — 옵션 ② 코드 구현 완료 (2026-06-10, 사용자 결정 위임)**: `auth_callback`(`src/auth/github.py`)의 users upsert(`find_by_github_id` SELECT + 신규 User INSERT)만 `WorkerSessionLocal`(BYPASSRLS worker role, 시스템 컨텍스트)로 전환 — 콜백 시점 `app.user_id=''` 로 인한 users self-RLS 차단을 우회한다. `logout` 은 세션이 있어(`request.session["user_id"]`) bare `SessionLocal`(웹 RLS 경로, 본인 행) 유지. `_WEB_DB_MODULES` 가드는 `_HYBRID_DB_MODULES`(github.py — bare + worker 둘 다 허용) 카테고리로 재설계 + 계약 가드 2종 추가(`tests/unit/test_worker_session_routing.py` 테스트 10). `DATABASE_URL_WORKER` 미설정 동안은 `WorkerSessionLocal is SessionLocal` 이라 **현행 동작과 완전 동일** — Phase 4 에서 worker URL 설정 시 자동 발효. 🔴 **잔여(동일 영역, 별도 결정 필요)**: `/admin/tenants`(`tenant_inventory`)는 여전히 웹 세션이라 admin 의 타 사용자 행이 은닉되어 under-report (fail-safe 방향 — admin 이 더 적게 봄, 로그인 장애 아님). admin 크로스테넌트 가시성 복원은 **권한 상승(admin 이 전체 테넌트 행 조회) 결정**이라 별도 PR + 사용자 확인 필요.

> **이전 blocker 서술 (해소 전 — 근거 보존)**: OAuth 로그인 경로가 users self-RLS 에 차단된다 — `auth_callback` 은 웹 `SessionLocal` 로 upsert 를 수행하는데 콜백 시점 `session["user_id"]` 부재 → `app.user_id=''` → `users_self_isolation`(0029, `id = app.user_id`, FOR ALL = implicit WITH CHECK) 이 SELECT/INSERT 모두 거부. `scamanager_app`(비-owner) 전환 즉시 전원 로그인 불가 (FORCE 무관, 0041 롤백으로도 미해소). 검토 옵션: ① 별도 policy/컨텍스트 키 ② auth upsert worker 세션 경유(채택) ③ users policy WITH CHECK 분리.

```
DATABASE_URL=postgresql://scamanager_app:<시크릿>@<host>/<db>      # 웹 요청 (비-BYPASSRLS)
DATABASE_URL_WORKER=postgresql://scamanager_worker:<시크릿>@<host>/<db>  # 옵션 A 시 background (BYPASSRLS)
```
마이그레이션 실행은 별도 owner(`postgres`) 자격으로 (`alembic upgrade head`).

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

## 5. 롤백

- FORCE 제거: `ALTER TABLE ... NO FORCE ROW LEVEL SECURITY` (마이그레이션 downgrade).
- `DATABASE_URL`을 `postgres`로 복귀 (즉시 owner/BYPASSRLS-bypass 복원 → 차단 해소, 단 2차 안전망도 다시 0).

## 6. Pre-flight 체크리스트 (RLS 작업 착수 전 의무)

- [ ] **접속 role의 `rolbypassrls` 실측** — `SELECT rolbypassrls FROM pg_roles WHERE rolname=current_user;` (메모리 `project_rls_owner_bypass_finding` 의무) — `/admin/rls-audit` 의 `connection_bypasses_rls` 가 동일 실측(rolbypassrls OR rolsuper)을 자동 표기
- [x] 🔴 **OAuth 로그인 경로(users self-RLS) 전략 확정** — ✅ 옵션 ②(auth upsert worker 세션 경유) 코드 완료(2026-06-10). `/admin/tenants` under-report 는 잔여(별도 권한 결정, §Phase 4 참조)
- [ ] Phase 2(background 전략) **설계·배포 완료** 확인 — 미완 시 Phase 4(URL 전환) 금지(파이프라인 붕괴)
- [ ] **fallback/온프레미스 DB 에 0041 수동 적용 시 해당 접속 role rolbypassrls 실측 의무** — fallback engine 은 RLS `SET LOCAL` listener 미등록(`src/database.py` — primary engine 한정)이라, 비-BYPASSRLS owner 접속이면 failover 중 web 쿼리가 `app.user_id` 미설정 상태로 차단될 수 있다
- [ ] 백업/스냅샷 (Supabase PITR) 확보
- [ ] 저트래픽 시간대 (사용자 생활 패턴: 저녁 작업)

---

**관련**: `0026` policy / `saas_service::_RLS_MATRIX` (11 테이블 단일 출처) / `GET /admin/rls-audit` (#810 경고) / `db.md` RLS 규칙 / 정합성 감사 #2.
