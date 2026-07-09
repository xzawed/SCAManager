"""0044 회귀 가드 — claude_api_calls RLS 정책이 legacy repo(user_id IS NULL) 를 포함한다.

0044 regression guard — the claude_api_calls RLS policy includes legacy repos (user_id IS NULL),
matching the 0026 analyses/merge convention (paired with the app-layer _owned_repo_ids_subquery fix).
Found by Codex mutual review: the 0043 policy filtered legacy-repo cost rows under Phase 4 app-role RLS,
so the monthly-cost KPI still omitted legacy cost despite the app-layer fix.
"""
import pathlib
import re

_MIG = pathlib.Path("alembic/versions/0044_claude_api_calls_legacy_rls.py")


def _read() -> str:
    return _MIG.read_text(encoding="utf-8")


def test_0044_policy_includes_legacy_repo_clause():
    """upgrade 정책(_POLICY_WITH_LEGACY)의 repo 서브쿼리가 legacy(user_id IS NULL)를 포함."""
    # The upgrade policy's repo subquery must include the legacy (user_id IS NULL) clause.
    src = _read()
    m = re.search(r"_POLICY_WITH_LEGACY\s*=\s*\"\"\"(.*?)\"\"\"", src, re.DOTALL)
    assert m, "_POLICY_WITH_LEGACY 정의 없음 — 테스트 stale"
    body = m.group(1)
    assert "repo_id IN" in body, "repo 서브쿼리 없음"
    sub = body[body.find("SELECT id FROM repositories"):]
    assert "user_id IS NULL" in sub, (
        "upgrade 정책의 repo 서브쿼리에 legacy(user_id IS NULL) 절 누락 — Phase 4 RLS 가 legacy 비용 필터링"
    )


def test_0044_downgrade_restores_strict_policy():
    """downgrade(_POLICY_STRICT)는 legacy 미포함 원본(0043) 정책으로 복원."""
    # Downgrade restores the original strict (no-legacy) 0043 policy.
    src = _read()
    m = re.search(r"_POLICY_STRICT\s*=\s*\"\"\"(.*?)\"\"\"", src, re.DOTALL)
    assert m, "_POLICY_STRICT 정의 없음"
    body = m.group(1)
    sub = body[body.find("SELECT id FROM repositories"):]
    assert "user_id IS NULL" not in sub, "downgrade strict 정책의 repo 서브쿼리가 legacy 절 포함 — 원본 복원 아님"


def test_0044_pg_gated_and_chains_from_0043():
    """정책 변경은 PG 전용(is_postgresql) + down_revision 0043 체인."""
    # Policy change is PostgreSQL-only + chains from 0043.
    src = _read()
    assert "is_postgresql" in src, "PG 가드(is_postgresql) 누락 — SQLite 에서 RLS 미지원 no-op 필요"
    assert 'down_revision = "0043"' in src, "down_revision 0043 아님 — 마이그레이션 체인 단절"
    assert 'revision = "0044"' in src
