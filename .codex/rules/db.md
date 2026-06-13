---
description: DB / 마이그레이션 작업 시 적용되는 SCAManager 코딩 규칙 (Codex용 — path-scoped)
paths:
  - "alembic/**"
  - "src/models/**"
  - "src/database.py"
  - "src/repositories/**"
---

# DB / 마이그레이션 규칙 (Codex)

- 🔴 **ORM 컬럼 추가 시 마이그레이션 필수**: `models/*.py` 에 `Column(...)` 추가 후 반드시 `make revision m="설명"` 실행. 단위 테스트(in-memory SQLite)는 마이그레이션 없이도 통과하지만, 운영 DB에는 컬럼이 없어 500 에러 발생.
- 🔴 **`batch_alter_table` 금지**: PostgreSQL 에서 `op.create_unique_constraint('이름', '테이블', ['컬럼'])` 직접 사용.
- **dialect 분기**: `from src.shared.alembic_dialect import is_postgresql; if not is_postgresql(op.get_bind()): return`
- **DB 인덱스 이중 정의**: `models/*.py` 의 `__table_args__ = (Index(...),)` + `alembic/versions/` 의 `op.create_index(...)` 양쪽 모두 필수.
- **FK ondelete CASCADE**: `analyses.id` 참조 child 4종 모두 CASCADE — 신규 child FK 추가 시 동일.
- **DB 세션**: `get_current_user()` 는 `db.expunge(user)` 후 반환 — 관계 lazy-load 사용 금지.
- **ThreadPoolExecutor**: `with` 문 금지 (shutdown hang) — `try/finally` + `executor.shutdown(wait=False)`.
- **`(data.get("key") or {}).get(...)` 패턴**: GitHub 페이로드의 None-able 키 접근 시 `or {}` 정규화 필수.
- 🔴 **RLS legacy 노출 비대칭 (감사 U1, 2026-06-13)**: `0026`(analyses/merge_attempts/repositories)는 `OR user_id IS NULL`(legacy 전역 노출)을 갖지만 `0027`(security_alert_process_logs)는 **의도적으로 생략**(더 엄격). **0027 에 `user_id IS NULL` 추가 금지** — legacy 보안알림 cross-tenant 노출. 가드: `tests/unit/migrations/test_0027_rls_intentional_divergence.py`. 🔴 **app↔RLS 방향 모순 (회고 P1)**: 활성 app-layer 필터(`_apply_owner_filter`/dashboard 의 `OR Repository.user_id.is_(None)`)는 legacy 전역 노출 = 0027 strict 의도와 정반대. `#2` Phase 4(비-BYPASSRLS) 전환 시 legacy 행에서 RLS 차단이 우선해 행동 변화 → strict 통일 시 app 필터 `is_(None)` 절도 동시 제거(사용자 결정, `#2` 묶음).
