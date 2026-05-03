"""Phase 3 PR 5 — alembic 0026 RLS policy 회귀 가드 (TDD Red).

Phase 3 PR 5 — alembic 0026 RLS policy regression guard (TDD Red).

본 마이그레이션 (구현 미존재 단계 — Red):
The migration verified by this module (implementation pending — Red phase):

    alembic/versions/0026_*.py
    - revision = "0026..."
    - down_revision = "0025dropleaderboardoptin"

upgrade() 동작 의도:
upgrade() intent:
    - PostgreSQL: repositories 테이블에 RLS 활성화 + policy 생성
    - SQLite: 모든 op.execute 호출 skip (단위 테스트 환경)

검증 3종:
3 tests:
    C.1 — revision 메타데이터 (revision/down_revision 정확성)
    C.2 — postgresql dialect 시 ENABLE ROW LEVEL SECURITY + CREATE POLICY 호출
    C.3 — sqlite dialect 시 op.execute 호출 0회 (skip 검증)

dialect 분기는 `op.get_context().dialect.name` 분기 패턴 사용:
The dialect branch uses the `op.get_context().dialect.name` check pattern:

    def upgrade():
        if op.get_context().dialect.name == 'postgresql':
            op.execute("ALTER TABLE repositories ENABLE ROW LEVEL SECURITY;")
            op.execute("CREATE POLICY repositories_user_isolation ON repositories ...")
        # SQLite skip — 단위 테스트 환경

회귀 가드 — RLS policy 가 SQLite 환경에서 실행되면 syntax error 발생.
Regression guard — RLS policy execution on SQLite raises syntax error.
"""
# pylint: disable=wrong-import-position
import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")


# ─── C.1 — revision 메타데이터 ─────────────────────────────────────────────


def test_alembic_0026_revision_metadata():
    """C.1 — alembic 0026 revision = "0026..." + down_revision == "0025...".

    C.1 — alembic 0026 revision starts with "0026", down_revision matches "0025...".

    체인 정합성 검증 — 0025 (drop leaderboard_opt_in) → 0026 (RLS policies).
    Chain integrity — 0025 (drop leaderboard_opt_in) → 0026 (RLS policies).
    """
    # 모듈 import 자체가 ImportError → Red 신호 (파일 미존재)
    # Module import itself raises ImportError → Red signal (file missing)
    import importlib

    # 모듈명 패턴: 0026_*.py — glob 으로 찾기보다는 명시적 파일명 패턴 사용.
    # File-name pattern: 0026_*.py — use glob-based discovery for flexibility.
    import pathlib

    versions_dir = pathlib.Path(__file__).resolve().parents[3] / "alembic" / "versions"
    candidates = sorted(versions_dir.glob("0026_*.py"))
    assert len(candidates) >= 1, (
        f"alembic/versions/0026_*.py 파일 미존재 — Red 단계 정상 신호. "
        f"검색 경로: {versions_dir}"
    )

    # 모듈 동적 import — 파일명에서 .py 제거 + alembic.versions 접두사 모듈 로드
    # Dynamic module import — strip .py suffix, load via spec
    module_path = candidates[0]
    spec = importlib.util.spec_from_file_location(
        f"alembic_0026_{module_path.stem}", module_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # revision 메타데이터 검증
    # Verify revision metadata
    assert hasattr(module, "revision"), "0026 모듈에 revision 식별자 누락"
    assert module.revision.startswith("0026"), (
        f"revision = '0026...' 기대, 실제: {module.revision!r}"
    )
    assert hasattr(module, "down_revision"), "0026 모듈에 down_revision 누락"
    assert module.down_revision is not None and module.down_revision.startswith("0025"), (
        f"down_revision = '0025...' 기대, 실제: {module.down_revision!r}"
    )


# ─── C.2 — postgresql dialect: ENABLE RLS + CREATE POLICY ─────────────────


def test_alembic_0026_postgresql_creates_rls_policies():
    """C.2 — postgresql dialect 환경에서 ENABLE ROW LEVEL SECURITY + CREATE POLICY 호출.

    C.2 — On postgresql dialect, calls ENABLE ROW LEVEL SECURITY + CREATE POLICY.

    검증 키워드 (대소문자 무관):
    - "ROW LEVEL SECURITY" (ENABLE 구문)
    - "CREATE POLICY" (정책 생성 구문)
    - "repositories" (대상 테이블)

    op.get_context().dialect.name == "postgresql" mock + op.execute 캡처 → SQL 키워드 검증.
    """
    import importlib
    import pathlib

    versions_dir = pathlib.Path(__file__).resolve().parents[3] / "alembic" / "versions"
    candidates = sorted(versions_dir.glob("0026_*.py"))
    assert len(candidates) >= 1, "0026 파일 미존재 (Red 단계 신호)"

    module_path = candidates[0]
    spec = importlib.util.spec_from_file_location(
        f"alembic_0026_{module_path.stem}", module_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # op 모듈 자체 mock — get_context() + execute 모두 가로챔
    # Mock the op module itself — intercept get_context() + execute
    fake_context = MagicMock()
    fake_context.dialect.name = "postgresql"

    captured_sql: list[str] = []

    def _capture_execute(sql, *_args, **_kwargs):
        captured_sql.append(str(sql))

    with patch.object(module, "op") as mock_op:
        mock_op.get_context.return_value = fake_context
        mock_op.execute.side_effect = _capture_execute
        module.upgrade()

    # 1 회 이상 SQL 실행 (PG 분기 진입)
    # SQL executed ≥ 1 time (PG branch entered)
    assert len(captured_sql) >= 1, (
        "PG dialect 시 op.execute 호출 0회 — RLS 분기 미진입 (Red 단계 정상)"
    )

    joined_sql = " ".join(captured_sql).upper()
    # ENABLE ROW LEVEL SECURITY 호출 검증
    # Verify ENABLE ROW LEVEL SECURITY call
    assert "ROW LEVEL SECURITY" in joined_sql, (
        f"PG 분기에서 'ROW LEVEL SECURITY' 키워드 누락. captured: {captured_sql}"
    )
    # CREATE POLICY 호출 검증
    # Verify CREATE POLICY call
    assert "CREATE POLICY" in joined_sql, (
        f"PG 분기에서 'CREATE POLICY' 키워드 누락. captured: {captured_sql}"
    )
    # 대상 테이블 (repositories) 검증
    # Verify target table (repositories)
    assert "REPOSITORIES" in joined_sql, (
        f"PG 분기에서 'repositories' 테이블 대상 누락. captured: {captured_sql}"
    )


# ─── C.3 — sqlite dialect: 모든 op.execute skip ────────────────────────────


def test_alembic_0026_sqlite_skip():
    """C.3 — sqlite dialect 시 op.execute 호출 0회 (RLS 미적용).

    C.3 — On sqlite dialect, op.execute is called 0 times (RLS not applied).

    SQLite 는 RLS 미지원 — 단위 테스트 환경 (in-memory SQLite) 에서 PG 전용 SQL
    실행 시 syntax error 발생. dialect 분기로 skip 의무.

    SQLite does not support RLS — running PG-only SQL in the unit test
    environment (in-memory SQLite) raises a syntax error. Dialect branch
    MUST skip these statements.
    """
    import importlib
    import pathlib

    versions_dir = pathlib.Path(__file__).resolve().parents[3] / "alembic" / "versions"
    candidates = sorted(versions_dir.glob("0026_*.py"))
    assert len(candidates) >= 1, "0026 파일 미존재 (Red 단계 신호)"

    module_path = candidates[0]
    spec = importlib.util.spec_from_file_location(
        f"alembic_0026_{module_path.stem}", module_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # SQLite dialect 시뮬레이션
    # Simulate SQLite dialect
    fake_context = MagicMock()
    fake_context.dialect.name = "sqlite"

    with patch.object(module, "op") as mock_op:
        mock_op.get_context.return_value = fake_context
        mock_op.execute = MagicMock()
        module.upgrade()

    # SQLite 분기 — op.execute 호출 0회 (모든 RLS SQL skip)
    # SQLite branch — op.execute called 0 times (all RLS SQL skipped)
    assert mock_op.execute.call_count == 0, (
        f"SQLite dialect 시 op.execute 호출 0회 기대, 실제: {mock_op.execute.call_count}회. "
        f"SQLite 환경에서 RLS SQL 실행 시 syntax error → 단위 테스트 깨짐."
    )
