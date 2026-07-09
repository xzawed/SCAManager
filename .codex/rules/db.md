---
description: DB / 마이그레이션 작업 시 적용되는 SCAManager 코딩 규칙 (Codex용 — path-scoped)
paths:
  - "alembic/**"
  - "src/models/**"
  - "src/database.py"
  - "src/repositories/**"
---

# DB / 마이그레이션 규칙 (Codex)

## 🔴 마이그레이션 PR pre-flight 체크리스트 (2026-07-09 rank12)

신규 마이그레이션/ORM 변경 착수 전 (PG 전용문은 SQLite 단위 테스트서 no-op → 운영 PG 에서만 드러나는 비대칭 사전 차단):
- [ ] ORM Boolean/신규 컬럼 = `server_default` 지정 (raw-SQL insert NOT NULL 회귀 방어)
- [ ] 신규 RLS 테이블 = `ENABLE` + `FORCE` + `saas_service._RLS_MATRIX` 3 동기화 (bijection 가드)
- [ ] PG 전용 SQL = `is_postgresql(op.get_bind())` 분기
- [ ] env.py URL override = `effective_migration_url` 경유 (테스트는 settings 싱글톤 patch)
- [ ] `alembic/env.py` 모델 import 완전성 (autogenerate `drop_table` footgun 차단)
- [ ] `make migrate` 왕복 (`downgrade -1` → `upgrade head`)

🔴 **MCP 운영 DB 접근 = 정책 12 SELECT-only 자율 / 변경·PII SELECT = 사용자 사전 승인**. 호출 시 PR 본문 §"MCP 자율 실행 결과"(정책 3) 명시.

- 🔴 **ORM 컬럼 추가 시 마이그레이션 필수**: `models/*.py` 에 `Column(...)` 추가 후 반드시 `make revision m="설명"` 실행. 단위 테스트(in-memory SQLite)는 마이그레이션 없이도 통과하지만, 운영 DB에는 컬럼이 없어 500 에러 발생.
- 🔴 **`batch_alter_table` 금지**: PostgreSQL 에서 `op.create_unique_constraint('이름', '테이블', ['컬럼'])` 직접 사용.
- 🔴 **alembic `env.py` 가 `effective_migration_url` override → RLS Phase 4 마이그레이션 credential 게이트 (2026-06-15 / #908)**: env.py 가 `effective_migration_url`(= `migration_database_url or database_url`) 사용 — `MIGRATION_DATABASE_URL` 미설정 시 `DATABASE_URL` fallback. Phase 4 에서 `DATABASE_URL`=`scamanager_app`(비-BYPASSRLS) 전환 시 **`MIGRATION_DATABASE_URL` 미설정이면** pre-deploy/lifespan 마이그레이션이 app role 로 돌아 `alembic_version` default-deny(relrowsecurity=true·policy 0)에 막힘. ✅ **`MIGRATION_DATABASE_URL`(owner) 코드 구현됨 (#908)** — `config.py` `effective_migration_url`(= `migration_database_url or database_url`) + `env.py` 사용(미설정 시 `DATABASE_URL` fallback). 🔴 Phase 4 시 env 설정만 잔여. 런타임 `DATABASE_URL`/`DATABASE_URL_WORKER` 를 마이그레이션 credential 로 재사용 금지. 회귀 가드: `tests/unit/migrations/test_alembic_env_migration_url.py`. 절차: `docs/runbooks/rls-role-separation.md` §6.
- **dialect 분기**: `from src.shared.alembic_dialect import is_postgresql; if not is_postgresql(op.get_bind()): return`
- **DB 인덱스 이중 정의**: `models/*.py` 의 `__table_args__ = (Index(...),)` + `alembic/versions/` 의 `op.create_index(...)` 양쪽 모두 필수.
- **FK ondelete CASCADE**: `analyses.id` 참조 child 4종 모두 CASCADE — 신규 child FK 추가 시 동일.
- **DB 세션**: `get_current_user()` 는 `db.expunge(user)` 후 반환 — 관계 lazy-load 사용 금지.
- **ThreadPoolExecutor**: `with` 문 금지 (shutdown hang) — `try/finally` + `executor.shutdown(wait=False)`.
- **`(data.get("key") or {}).get(...)` 패턴**: GitHub 페이로드의 None-able 키 접근 시 `or {}` 정규화 필수.
- 🔴 **RLS legacy 노출 비대칭 (감사 U1, 2026-06-13)**: `0026`(analyses/merge_attempts/repositories)는 `OR user_id IS NULL`(legacy 전역 노출)을 갖지만 `0027`(security_alert_process_logs)는 **의도적으로 생략**(더 엄격). **0027 에 `user_id IS NULL` 추가 금지** — legacy 보안알림 cross-tenant 노출. 가드: `tests/unit/migrations/test_0027_rls_intentional_divergence.py`. 🔴 **app↔RLS 방향 모순 (회고 P1)**: 활성 app-layer 필터(`_apply_owner_filter`/dashboard 의 `OR Repository.user_id.is_(None)`)는 legacy 전역 노출 = 0027 strict 의도와 정반대. `#2` Phase 4(비-BYPASSRLS) 전환 시 legacy 행에서 RLS 차단이 우선해 행동 변화 → strict 통일 시 app 필터 `is_(None)` 절도 동시 제거(사용자 결정, `#2` 묶음).
