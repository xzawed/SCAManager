"""Cycle 79 PR 1 — alembic 0029 RLS 5 누락 테이블 보강 회귀 가드.

Cycle 79 PR 1 — alembic 0029 RLS 5 missing tables hardening regression guard.

5+1 cross-verify (Cycle 78 NEW-P0-1) — RLS 누락 5 테이블:
- users (self-RLS)
- repo_configs (간접)
- gate_decisions (간접 2-hop)
- merge_retry_queue (간접)
- analysis_feedbacks (직접 user_id)

검증:
    C.1 — revision/down_revision 메타데이터
    C.2 — postgresql dialect: 5 테이블 모두 ALTER + CREATE POLICY 호출
    C.3 — sqlite dialect: op.execute 호출 0회 (skip)
    C.4 — legacy NULL 호환 검증 (repo_configs / merge_retry_queue 의 subquery)
    C.5 — analysis_feedbacks = user_id 직접 격리 (NULL 허용 X)
    C.6 — users = self-RLS (id 직접 비교)
"""
# pylint: disable=wrong-import-position
import importlib.util
import os
import pathlib
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")


def _load_0029_module():
    """alembic/versions/0029_*.py 동적 로드 — 0026 가드 패턴 차용."""
    versions_dir = pathlib.Path(__file__).resolve().parents[3] / "alembic" / "versions"
    candidates = sorted(versions_dir.glob("0029_*.py"))
    assert len(candidates) >= 1, (
        f"alembic/versions/0029_*.py 파일 미존재. 검색 경로: {versions_dir}"
    )
    module_path = candidates[0]
    spec = importlib.util.spec_from_file_location(
        f"alembic_0029_{module_path.stem}", module_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _capture_pg_upgrade_sql() -> list[str]:
    """postgresql dialect mock + upgrade() 호출 + SQL 캡처."""
    module = _load_0029_module()
    fake_bind = MagicMock()
    fake_bind.dialect.name = "postgresql"
    captured: list[str] = []

    def _capture(sql, *_args, **_kwargs):
        captured.append(str(sql))

    with patch.object(module, "op") as mock_op:
        mock_op.get_bind.return_value = fake_bind
        mock_op.execute.side_effect = _capture
        module.upgrade()
    return captured


# ─── C.1 — revision 메타데이터 ──────────────────────────────────────────


def test_alembic_0029_revision_metadata():
    """C.1 — revision = '0029...' + down_revision = '0028...'."""
    module = _load_0029_module()
    assert hasattr(module, "revision")
    assert module.revision.startswith("0029"), (
        f"revision = '0029...' 기대, 실제: {module.revision!r}"
    )
    assert hasattr(module, "down_revision")
    assert module.down_revision is not None and module.down_revision.startswith("0028"), (
        f"down_revision = '0028...' 기대, 실제: {module.down_revision!r}"
    )


# ─── C.2 — postgresql dialect: 5 테이블 모두 ALTER + CREATE POLICY ──────


def test_alembic_0029_postgresql_alters_all_5_tables():
    """C.2 — postgresql dialect 시 5 테이블 모두 ALTER + CREATE POLICY 호출."""
    captured = _capture_pg_upgrade_sql()
    assert len(captured) >= 1, "PG dialect 시 op.execute 호출 0회 — RLS 분기 미진입"

    joined = " ".join(captured).upper()
    # 5 테이블 모두 명시 검증
    for table in ("USERS", "REPO_CONFIGS", "GATE_DECISIONS", "MERGE_RETRY_QUEUE", "ANALYSIS_FEEDBACKS"):
        assert table in joined, f"PG 분기에서 {table} 테이블 ALTER 누락"

    # ROW LEVEL SECURITY 활성화 + CREATE POLICY 호출 검증 (5회 이상)
    assert joined.count("ROW LEVEL SECURITY") >= 5, (
        f"5 테이블 모두 ENABLE ROW LEVEL SECURITY 의무 — count: {joined.count('ROW LEVEL SECURITY')}"
    )
    assert joined.count("CREATE POLICY") >= 5, (
        f"5 테이블 모두 CREATE POLICY 의무 — count: {joined.count('CREATE POLICY')}"
    )


# ─── C.3 — sqlite dialect: 모든 op.execute skip ─────────────────────────


def test_alembic_0029_sqlite_skip():
    """C.3 — sqlite dialect 시 op.execute 호출 0회 (RLS skip — 단위 테스트 호환)."""
    module = _load_0029_module()
    fake_bind = MagicMock()
    fake_bind.dialect.name = "sqlite"

    with patch.object(module, "op") as mock_op:
        mock_op.get_bind.return_value = fake_bind
        mock_op.execute = MagicMock()
        module.upgrade()

    assert mock_op.execute.call_count == 0, (
        f"SQLite dialect 시 op.execute 호출 0회 기대, 실제: {mock_op.execute.call_count}회"
    )


# ─── C.4 — legacy NULL 호환 (repositories RLS 정합) ─────────────────────


def test_alembic_0029_legacy_null_compat_for_indirect_isolation():
    """C.4 — repo_configs / merge_retry_queue subquery 가 legacy NULL 호환."""
    captured = _capture_pg_upgrade_sql()
    joined = " ".join(captured).upper()
    # repositories 의 NULL 허용 호환 (legacy 리포)
    assert "USER_ID IS NULL" in joined, (
        "간접 격리 subquery 가 legacy NULL 미허용 — repositories RLS 정합 위반"
    )
    # NULLIF 패턴 정합 (current_setting 빈 문자열 처리)
    assert "NULLIF" in joined, (
        "current_setting('app.user_id', true) 의 NULLIF 처리 누락"
    )


# ─── C.5 — analysis_feedbacks = user_id 직접 격리 (NULL 허용 X) ─────────


def test_alembic_0029_analysis_feedbacks_direct_isolation():
    """C.5 — analysis_feedbacks 가 user_id 직접 격리 (NULL 허용 X)."""
    captured = _capture_pg_upgrade_sql()
    # analysis_feedbacks 영역 추출
    feedback_sql = next(
        (s for s in captured if "analysis_feedbacks" in s.lower()), None
    )
    assert feedback_sql is not None, "analysis_feedbacks 영역 SQL 누락"
    upper = feedback_sql.upper()
    # user_id = current_setting (직접 격리)
    assert "USER_ID = NULLIF" in upper, (
        "analysis_feedbacks user_id 직접 격리 누락"
    )


# ─── C.6 — users = self-RLS (id 직접 비교) ───────────────────────────────


def test_alembic_0029_users_self_rls():
    """C.6 — users 가 self-RLS (id 직접 비교)."""
    captured = _capture_pg_upgrade_sql()
    # 0029 가 users 에 ALTER TABLE users ENABLE ROW LEVEL SECURITY 를 발화하는지 검증
    # Verify 0029 emits ALTER TABLE users ENABLE ROW LEVEL SECURITY
    # (구 `or "ON users" in s.lower()` 서브분기 제거: s.lower() 라 대문자 "ON users" 절대 미매칭 dead-branch #31)
    users_sql = next(
        (s for s in captured if "ALTER TABLE users" in s),
        None,
    )
    # users RLS SQL 이 반드시 존재해야 함 (구 dead `or` fallback 제거 — 가드 강화 #31)
    # The users RLS statement must be present (removed the dead `or` fallback)
    assert users_sql is not None, "users RLS (ALTER TABLE users) SQL 누락"
    joined = " ".join(captured).upper()
    # users.id = current_setting (self-RLS)
    assert "ID = NULLIF" in joined, (
        "users self-RLS (id 직접 비교) 누락"
    )
