# RLS owner-bypass 근본 해결 — 앱 role 분리 + FORCE 운영 Runbook

> 정합성 감사 full(2026-06-08) **P1 #2** — RLS '2차 안전망'이 운영에서 실효 0인 문제의 근본 해결 절차.
> `#810`(rls-audit FORCE 미설정 경고 가시화)의 후속 = 실제 remediation. **이 작업은 운영 DB(Supabase/PG)
> 권한 변경을 동반하므로 코드만으로 완결되지 않는다** — 본 runbook은 그 절차를 문서화한다.

---

## 1. 문제 (왜 RLS 2차 안전망이 지금은 작동하지 않는가)

`alembic/versions/0026_supabase_rls_policies.py`(외 0027/0028/0029/0037 누적)가 **총 11개 테이블**에 RLS policy를 **ENABLE**하지만 **FORCE ROW LEVEL SECURITY는 적용하지 않는다** (0026 자체는 repositories/analyses/merge_attempts 3개 — 나머지 8개는 후속 마이그레이션, 단일 출처 = `saas_service.py::_RLS_MATRIX`). 그리고 운영 앱은 DB에 **`postgres`(또는 테이블 owner + `BYPASSRLS`) role로 접속**한다 (`DATABASE_URL`).

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

```python
# 신규 마이그레이션 (예: 0041_rls_force.py, PG-only, is_postgresql 가드)
for tbl in (  # _RLS_MATRIX 11 테이블
    "repositories", "analyses", "merge_attempts", "security_alert_process_logs",
    "insight_narrative_cache", "users", "repo_configs", "gate_decisions",
    "merge_retry_queue", "analysis_feedbacks", "issue_registrations",
):
    op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")
```

동반:
- `saas_service.py::rls_coverage_summary` `force_applied` → 정적 `False` 대신 **`pg_class.relforcerowsecurity` 실측 쿼리**로 전환 (또는 마이그레이션 적용 후 `True`).
- `test_admin_settings_i18n_render.py::test_admin_rls_audit_hides_force_warning_when_applied` 가드는 이미 `force_applied=True` 시 경고 미표시 검증 — Phase 3 후 실제 동작 정합.
- `0026` docstring·`db.md`·본 runbook의 "FORCE 미적용" 서술 갱신.

### Phase 4 — DATABASE_URL 전환 (운영, 사용자)

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
- `GET /admin/rls-audit` → `force_applied=True` + 경고 배너 미표시.
- 🔴 **background 파이프라인 smoke**: 옵션 A worker role로 webhook 분석·cron 재시도가 user-owned repo에 정상 동작(차단 0).

## 5. 롤백

- FORCE 제거: `ALTER TABLE ... NO FORCE ROW LEVEL SECURITY` (마이그레이션 downgrade).
- `DATABASE_URL`을 `postgres`로 복귀 (즉시 owner/BYPASSRLS-bypass 복원 → 차단 해소, 단 2차 안전망도 다시 0).

## 6. Pre-flight 체크리스트 (RLS 작업 착수 전 의무)

- [ ] **접속 role의 `rolbypassrls` 실측** — `SELECT rolbypassrls FROM pg_roles WHERE rolname=current_user;` (메모리 `project_rls_owner_bypass_finding` 의무)
- [ ] Phase 2(background 전략) **설계·배포 완료** 확인 — 미완 시 Phase 4(URL 전환) 금지(파이프라인 붕괴)
- [ ] 백업/스냅샷 (Supabase PITR) 확보
- [ ] 저트래픽 시간대 (사용자 생활 패턴: 저녁 작업)

---

**관련**: `0026` policy / `saas_service::_RLS_MATRIX` (11 테이블 단일 출처) / `GET /admin/rls-audit` (#810 경고) / `db.md` RLS 규칙 / 정합성 감사 #2.
