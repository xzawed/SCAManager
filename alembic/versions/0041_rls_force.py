"""RLS Phase 3 — FORCE ROW LEVEL SECURITY 적용 (정합성 감사 #2, PostgreSQL 전용)

Revision ID: 0041
Revises: 0040
Create Date: 2026-06-10

정합성 감사 full(2026-06-08) P1 #2 의 Phase 3 — `_RLS_MATRIX` 11개 테이블에
FORCE ROW LEVEL SECURITY 를 적용한다. ENABLE-only RLS 는 테이블 owner 연결을
기본 우회하므로, FORCE 로 owner 에 대해서도 USING 절 평가를 강제한다.

🔴 역할 구분 주의 — BYPASSRLS role(예: Supabase `postgres`) 연결은 FORCE 와 무관하게
RLS 를 항상 우회하고, Phase 4 의 비-owner `scamanager_app` 은 ENABLE 만으로 RLS 가
평가된다. 즉 Phase 4 의 2차 안전망 실효는 **role 전환(Phase 1/2/4)에서 오고**, 본
FORCE 는 "비-BYPASSRLS owner 연결" 사고(향후 owner 직접 접속 등)를 막는
**defense-in-depth** 다. 관련 단계:
- Phase 1: 비-BYPASSRLS 앱 role `scamanager_app` 프로비저닝 (2026-06-10 운영 완료)
- Phase 2: background 경로 worker 세션 분리 (#847 — BYPASSRLS `scamanager_worker`,
  `app.user_id` 미설정 background 차단 회피)
- Phase 4: DATABASE_URL 을 `scamanager_app` 으로 전환 (운영, 사용자)
절차·검증: docs/runbooks/rls-role-separation.md Phase 3.

RLS Phase 3 — FORCE ROW LEVEL SECURITY on the 11 `_RLS_MATRIX` tables (PG only).
ENABLE-only RLS is bypassed for the table owner; FORCE makes the USING clause apply
to the owner as well. Note the division of roles: BYPASSRLS connections bypass RLS
regardless of FORCE, and the non-owner Phase 4 app role evaluates RLS with ENABLE
alone — the Phase 4 security gain comes from the role switch, while this FORCE is
defense-in-depth against a future non-BYPASSRLS owner connection.

SQLite (단위 테스트): skip — RLS 미지원 환경 호환.
SQLite (unit tests): skip — RLS is not supported there.
회귀 가드: tests/unit/migrations/test_0041_rls_force.py (ENABLE↔FORCE bijection 포함).
"""
from alembic import op

from src.shared.alembic_dialect import is_postgresql


revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


# _RLS_MATRIX 11 테이블 리터럴 SQL — bijection 가드(test_0041)가 raw 파일 텍스트를
# 정규식으로 추출하므로 f-string 루프 조립 금지 (가드가 테이블을 인식 못 함).
# Literal SQL for the 11 _RLS_MATRIX tables — the bijection guard extracts table
# names from raw file text, so f-string loop assembly is forbidden (it would blind
# the guard).
_FORCE_SQL = """
ALTER TABLE repositories FORCE ROW LEVEL SECURITY;
ALTER TABLE analyses FORCE ROW LEVEL SECURITY;
ALTER TABLE merge_attempts FORCE ROW LEVEL SECURITY;
ALTER TABLE security_alert_process_logs FORCE ROW LEVEL SECURITY;
ALTER TABLE insight_narrative_cache FORCE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
ALTER TABLE repo_configs FORCE ROW LEVEL SECURITY;
ALTER TABLE gate_decisions FORCE ROW LEVEL SECURITY;
ALTER TABLE merge_retry_queue FORCE ROW LEVEL SECURITY;
ALTER TABLE analysis_feedbacks FORCE ROW LEVEL SECURITY;
ALTER TABLE issue_registrations FORCE ROW LEVEL SECURITY;
"""

# downgrade — FORCE 만 해제, ENABLE/policy 는 보존 (0026~0037 영역 불변)
# downgrade — remove FORCE only; ENABLE and policies stay (0026~0037 untouched)
_UNFORCE_SQL = """
ALTER TABLE repositories NO FORCE ROW LEVEL SECURITY;
ALTER TABLE analyses NO FORCE ROW LEVEL SECURITY;
ALTER TABLE merge_attempts NO FORCE ROW LEVEL SECURITY;
ALTER TABLE security_alert_process_logs NO FORCE ROW LEVEL SECURITY;
ALTER TABLE insight_narrative_cache NO FORCE ROW LEVEL SECURITY;
ALTER TABLE users NO FORCE ROW LEVEL SECURITY;
ALTER TABLE repo_configs NO FORCE ROW LEVEL SECURITY;
ALTER TABLE gate_decisions NO FORCE ROW LEVEL SECURITY;
ALTER TABLE merge_retry_queue NO FORCE ROW LEVEL SECURITY;
ALTER TABLE analysis_feedbacks NO FORCE ROW LEVEL SECURITY;
ALTER TABLE issue_registrations NO FORCE ROW LEVEL SECURITY;
"""


def upgrade() -> None:
    """11 테이블에 FORCE ROW LEVEL SECURITY 적용 (PostgreSQL 만, SQLite skip).

    Apply FORCE ROW LEVEL SECURITY to the 11 tables (PostgreSQL only; SQLite skips).
    """
    bind = op.get_bind()
    if not is_postgresql(bind):
        return  # SQLite 단위 테스트 호환 — RLS skip
    op.execute(_FORCE_SQL)


def downgrade() -> None:
    """FORCE 해제 (NO FORCE) — ENABLE/policy 보존 (PostgreSQL 만).

    Remove FORCE (NO FORCE) while keeping ENABLE and policies (PostgreSQL only).
    """
    bind = op.get_bind()
    if not is_postgresql(bind):
        return
    op.execute(_UNFORCE_SQL)
