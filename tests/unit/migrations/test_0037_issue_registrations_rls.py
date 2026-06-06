"""정합성 감사 — alembic 0037 issue_registrations RLS 회귀 가드.

Integrity-audit — alembic 0037 issue_registrations RLS regression guard.

검증:
    C.1 — revision = '0037' / down_revision = '0036'
    C.2 — postgresql dialect: issue_registrations ALTER + CREATE POLICY 호출
    C.3 — sqlite dialect: op.execute 호출 0회 (skip — 단위 테스트 호환)
    C.4 — legacy NULL 호환 (repo_id → repositories.user_id IS NULL 허용)
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


def _load_0037_module():
    """alembic/versions/0037_*.py 동적 로드 — 0029 가드 패턴 차용."""
    versions_dir = pathlib.Path(__file__).resolve().parents[3] / "alembic" / "versions"
    candidates = sorted(versions_dir.glob("0037_*.py"))
    assert len(candidates) >= 1, (
        f"alembic/versions/0037_*.py 파일 미존재. 검색 경로: {versions_dir}"
    )
    module_path = candidates[0]
    spec = importlib.util.spec_from_file_location(
        f"alembic_0037_{module_path.stem}", module_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _capture_pg_upgrade_sql() -> list[str]:
    """postgresql dialect mock + upgrade() 호출 + SQL 캡처."""
    module = _load_0037_module()
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


def test_alembic_0037_revision_metadata():
    """C.1 — revision = '0037' + down_revision = '0036'."""
    module = _load_0037_module()
    assert getattr(module, "revision", None) == "0037", (
        f"revision = '0037' 기대, 실제: {getattr(module, 'revision', None)!r}"
    )
    assert getattr(module, "down_revision", None) == "0036", (
        f"down_revision = '0036' 기대, 실제: {getattr(module, 'down_revision', None)!r}"
    )


def test_alembic_0037_postgresql_applies_rls():
    """C.2 — postgresql dialect 시 issue_registrations ALTER + CREATE POLICY 호출."""
    captured = _capture_pg_upgrade_sql()
    assert len(captured) >= 1, "PG dialect 시 op.execute 호출 0회 — RLS 분기 미진입"

    joined = " ".join(captured).upper()
    assert "ISSUE_REGISTRATIONS" in joined, "PG 분기에서 issue_registrations ALTER 누락"
    assert "ROW LEVEL SECURITY" in joined, "ENABLE ROW LEVEL SECURITY 의무"
    assert "CREATE POLICY" in joined, "CREATE POLICY 의무"


def test_alembic_0037_sqlite_skip():
    """C.3 — sqlite dialect 시 op.execute 호출 0회 (RLS skip — 단위 테스트 호환)."""
    module = _load_0037_module()
    fake_bind = MagicMock()
    fake_bind.dialect.name = "sqlite"

    with patch.object(module, "op") as mock_op:
        mock_op.get_bind.return_value = fake_bind
        module.upgrade()
        mock_op.execute.assert_not_called()


def test_alembic_0037_legacy_null_compat():
    """C.4 — legacy NULL 호환: repo_id 서브쿼리가 user_id IS NULL 행을 허용해야 한다."""
    captured = _capture_pg_upgrade_sql()
    joined = " ".join(captured)
    assert "repo_id IN" in joined, "repo_id 기반 1-hop 격리 누락"
    assert "user_id IS NULL" in joined, (
        "legacy NULL 호환 누락 — repositories RLS 정합(0026/0029) 깨짐"
    )
