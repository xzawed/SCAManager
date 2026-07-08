"""RLS Phase 3 — alembic 0041 FORCE ROW LEVEL SECURITY TDD Red 가드.

RLS Phase 3 — alembic 0041 FORCE ROW LEVEL SECURITY TDD Red guard.

검증 / Verifies:
    F.1 — revision = '0041' / down_revision = '0040'
    F.2 — postgresql dialect upgrade: _RLS_MATRIX 11 테이블 전부 FORCE ROW LEVEL SECURITY
    F.3 — upgrade SQL 에 NO FORCE 미포함 (downgrade SQL 실수 혼입 차단)
    F.4 — sqlite dialect: upgrade/downgrade 모두 op.execute 미호출 (skip — 단위 테스트 호환)
    F.5 — postgresql dialect downgrade: 11 테이블 전부 NO FORCE ROW LEVEL SECURITY
    F.6 — 누적 ENABLE ↔ FORCE bijection (신규 RLS 테이블이 FORCE 누락 시 자동 fail)
    F.7 — FORCE 정규식 normalization (NO FORCE 절대 미매칭 + 스키마/따옴표/소문자 변형 수용)
"""
# pylint: disable=wrong-import-position
import glob
import importlib.util
import os
import pathlib
import re
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

# alembic versions 디렉토리 — 테스트 파일 기준 상대 경로 (절대경로 하드코딩 금지)
# Alembic versions directory, resolved relative to this test file (no hardcoded paths)
_VERSIONS_DIR = pathlib.Path(__file__).resolve().parents[3] / "alembic" / "versions"

# ``ALTER TABLE <t> FORCE ROW LEVEL SECURITY`` 추출 — downgrade 의 ``NO FORCE`` 는
# 구조적으로 미매칭 (캡처 그룹 직전이 반드시 TABLE/스키마 한정이어야 하므로 'NO' 단어가
# 테이블명으로 캡처될 수 없음 — F.7 normalization 테스트가 이를 고정).
# Extract ``ALTER TABLE <t> FORCE ROW LEVEL SECURITY`` — downgrade ``NO FORCE`` can never
# match structurally (the capture group must directly follow TABLE/schema qualification,
# so the word 'NO' cannot be captured as a table name — pinned by the F.7 test).
_RLS_FORCE_RE = re.compile(
    r'ALTER\s+TABLE\s+(?:"?\w+"?\.)?"?(\w+)"?\s+FORCE\s+ROW\s+LEVEL\s+SECURITY',
    re.IGNORECASE,
)

# downgrade 검증용 — ``ALTER TABLE <t> NO FORCE ROW LEVEL SECURITY`` 만 매칭
# For downgrade assertions — matches only ``ALTER TABLE <t> NO FORCE ROW LEVEL SECURITY``
_RLS_NO_FORCE_RE = re.compile(
    r'ALTER\s+TABLE\s+(?:"?\w+"?\.)?"?(\w+)"?\s+NO\s+FORCE\s+ROW\s+LEVEL\s+SECURITY',
    re.IGNORECASE,
)

# ENABLE 추출 — tests/unit/test_rls_matrix_completeness.py 의 _RLS_ENABLE_RE 와 동일 패턴
# ENABLE extraction — same pattern as _RLS_ENABLE_RE in test_rls_matrix_completeness.py
_RLS_ENABLE_RE = re.compile(
    r'ALTER\s+TABLE\s+(?:"?\w+"?\.)?"?(\w+)"?\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY',
    re.IGNORECASE,
)


# 0041 작성 시점의 _RLS_MATRIX 스냅샷(11 테이블) — 0041 은 알려진 11 테이블만 FORCE 하는
# 불변 이력 마이그레이션이므로, F.2/F.5 는 (계속 성장하는) 라이브 _RLS_MATRIX 대신 이 고정
# 스냅샷과 대조한다. 이후 신규 RLS 테이블(예: 0043 claude_api_calls)은 각자의 마이그레이션에서
# 자체 FORCE 문을 실행하며, 누적 정합성은 F.6(cumulative bijection)이 담당한다.
# Snapshot of _RLS_MATRIX as it existed when 0041 was authored (11 tables) — 0041 is an
# immutable historical migration that FORCEs only those known 11 tables, so F.2/F.5 compare
# against this frozen snapshot instead of the (ever-growing) live _RLS_MATRIX. Later RLS
# tables (e.g. 0043 claude_api_calls) apply their own FORCE statement in their own migration;
# cumulative correctness across all migrations is covered by F.6 (cumulative bijection).
_RLS_MATRIX_AT_0041: frozenset[str] = frozenset({
    "repositories", "analyses", "merge_attempts", "security_alert_process_logs",
    "insight_narrative_cache", "users", "repo_configs", "gate_decisions",
    "merge_retry_queue", "analysis_feedbacks", "issue_registrations",
})


def _extract_force_tables(text: str) -> set[str]:
    """FORCE 문 테이블 집합 추출 + 방어적 'NO' 필터 (이중 안전망).

    Extract FORCE-statement tables with a defensive 'NO' filter (belt and braces) —
    even if a future regex edit lets ``NO FORCE`` slip through, the filter blocks it.
    """
    tables: set[str] = set()
    for match in _RLS_FORCE_RE.finditer(text):
        # 정규식이 'NO' 를 잡는 변형으로 퇴화해도 코드 레벨에서 배제
        # Even if the regex degrades into capturing 'NO', exclude it at code level
        if match.group(1).upper() == "NO":
            continue
        tables.add(match.group(1))
    return tables


def _load_0041_module():
    """alembic/versions/0041_*.py 동적 로드 — 0037 가드 패턴 미러.

    Dynamically load alembic/versions/0041_*.py — mirrors the 0037 guard pattern.
    """
    candidates = sorted(_VERSIONS_DIR.glob("0041_*.py"))
    assert len(candidates) >= 1, (
        f"alembic/versions/0041_*.py 파일 미존재. 검색 경로: {_VERSIONS_DIR}"
    )
    module_path = candidates[0]
    spec = importlib.util.spec_from_file_location(
        f"alembic_0041_{module_path.stem}", module_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _capture_pg_upgrade_sql() -> list[str]:
    """postgresql dialect mock + upgrade() 호출 + SQL 캡처 (0037 패턴 미러).

    PostgreSQL dialect mock + call upgrade() + capture SQL (mirrors the 0037 pattern).
    """
    module = _load_0041_module()
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


def _capture_pg_downgrade_sql() -> list[str]:
    """postgresql dialect mock + downgrade() 호출 + SQL 캡처.

    PostgreSQL dialect mock + call downgrade() + capture SQL.
    """
    module = _load_0041_module()
    fake_bind = MagicMock()
    fake_bind.dialect.name = "postgresql"
    captured: list[str] = []

    def _capture(sql, *_args, **_kwargs):
        captured.append(str(sql))

    with patch.object(module, "op") as mock_op:
        mock_op.get_bind.return_value = fake_bind
        mock_op.execute.side_effect = _capture
        module.downgrade()
    return captured


def test_alembic_0041_revision_metadata():
    """F.1 — revision = '0041' + down_revision = '0040'."""
    module = _load_0041_module()
    assert getattr(module, "revision", None) == "0041", (
        f"revision = '0041' 기대, 실제: {getattr(module, 'revision', None)!r}"
    )
    assert getattr(module, "down_revision", None) == "0040", (
        f"down_revision = '0040' 기대, 실제: {getattr(module, 'down_revision', None)!r}"
    )


def test_alembic_0041_postgresql_upgrade_forces_all_rls_matrix_tables():
    """F.2 — PG upgrade: _RLS_MATRIX 11 테이블 전부 FORCE ROW LEVEL SECURITY 실행.

    F.2 — PG upgrade must FORCE ROW LEVEL SECURITY on every _RLS_MATRIX table (11).
    """
    captured = _capture_pg_upgrade_sql()
    assert len(captured) >= 1, "PG dialect 시 op.execute 호출 0회 — FORCE 분기 미진입"

    forced = _extract_force_tables(" ".join(captured))
    assert forced == _RLS_MATRIX_AT_0041, (
        f"\n\nFORCE 적용 테이블 ≠ 0041 작성 시점 _RLS_MATRIX 스냅샷 (11 테이블)\n"
        f"forced: {sorted(forced)}\n"
        f"matrix(0041 시점): {sorted(_RLS_MATRIX_AT_0041)}\n"
        f"누락/잉여: {sorted(forced ^ _RLS_MATRIX_AT_0041)}\n"
    )


def test_alembic_0041_upgrade_does_not_emit_no_force():
    """F.3 — upgrade 캡처 SQL 에 'NO FORCE' 미포함 (downgrade SQL 실수 혼입 차단).

    F.3 — captured upgrade SQL must not contain 'NO FORCE' (no downgrade SQL leakage).
    """
    captured = _capture_pg_upgrade_sql()
    joined = " ".join(captured).upper()
    assert "NO FORCE" not in joined, (
        "upgrade 가 NO FORCE 문을 포함 — downgrade SQL 혼입 / "
        "upgrade emits NO FORCE — downgrade SQL leaked into upgrade"
    )


def test_alembic_0041_sqlite_skip_upgrade_and_downgrade():
    """F.4 — sqlite dialect 시 upgrade/downgrade 모두 op.execute 미호출 (PG-only skip).

    F.4 — on sqlite, both upgrade and downgrade must never call op.execute (PG-only skip).
    """
    module = _load_0041_module()
    fake_bind = MagicMock()
    fake_bind.dialect.name = "sqlite"

    with patch.object(module, "op") as mock_op:
        mock_op.get_bind.return_value = fake_bind
        module.upgrade()
        mock_op.execute.assert_not_called()

    with patch.object(module, "op") as mock_op:
        mock_op.get_bind.return_value = fake_bind
        module.downgrade()
        mock_op.execute.assert_not_called()


def test_alembic_0041_postgresql_downgrade_no_force_all_rls_matrix_tables():
    """F.5 — PG downgrade: 11 테이블 전부 NO FORCE ROW LEVEL SECURITY 실행.

    F.5 — PG downgrade must apply NO FORCE ROW LEVEL SECURITY to all 11 tables.
    """
    captured = _capture_pg_downgrade_sql()
    assert len(captured) >= 1, "PG dialect 시 downgrade op.execute 호출 0회"

    no_forced = {
        match.group(1)
        for match in _RLS_NO_FORCE_RE.finditer(" ".join(captured))
    }
    assert no_forced == _RLS_MATRIX_AT_0041, (
        f"\n\nNO FORCE 적용 테이블 ≠ 0041 작성 시점 _RLS_MATRIX 스냅샷 (11 테이블)\n"
        f"no_forced: {sorted(no_forced)}\n"
        f"matrix(0041 시점): {sorted(_RLS_MATRIX_AT_0041)}\n"
    )


def test_rls_force_enable_bijection_across_all_migrations():
    """F.6 — 누적 ENABLE ↔ FORCE bijection 가드 (test_rls_matrix_completeness 패턴 미러).

    모든 alembic 마이그레이션에서 ENABLE 테이블 집합과 FORCE 테이블 집합을 추출해
    완전 일치를 단언 — 미래 신규 RLS 테이블이 ENABLE 만 하고 FORCE 를 누락하면 자동 fail.

    F.6 — cumulative ENABLE ↔ FORCE bijection guard (mirrors test_rls_matrix_completeness).
    Extracts the ENABLE table set and the FORCE table set across every alembic migration
    and asserts exact equality — a future table getting ENABLE without FORCE fails here.
    """
    enabled: set[str] = set()
    forced: set[str] = set()
    for path in sorted(glob.glob(str(_VERSIONS_DIR / "*.py"))):
        with open(path, encoding="utf-8") as migration_file:
            text = migration_file.read()
        enabled.update(m.group(1) for m in _RLS_ENABLE_RE.finditer(text))
        forced.update(_extract_force_tables(text))

    assert enabled == forced, (
        f"\n\nENABLE RLS 테이블 ≠ FORCE RLS 테이블 (bijection 깨짐)\n"
        f"ENABLE-only (FORCE 누락): {sorted(enabled - forced)}\n"
        f"FORCE-only (ENABLE 없음): {sorted(forced - enabled)}\n\n"
        f"수정 / Fix: 신규 RLS 테이블은 ENABLE + FORCE 양쪽 마이그레이션 의무 "
        f"(owner-bypass 가시화 — docs/runbooks/rls-role-separation.md Phase 3).\n"
    )


def test_rls_force_regex_normalises_schema_and_quotes():
    """F.7 — FORCE 정규식 normalization: 변형 수용 + NO FORCE 절대 미매칭.

    스키마 한정(public.foo)/큰따옴표("foo")/소문자 변형은 bare 테이블명으로 정규화 수용,
    downgrade 의 NO FORCE 는 어떤 변형에서도 매칭 금지 (캡처 그룹 'NO' 오염 차단).

    F.7 — FORCE regex normalization: accept variants, never match NO FORCE.
    Schema-qualified / quoted / lowercase variants normalise to the bare table name;
    downgrade NO FORCE must never match in any variant (no 'NO' capture pollution).
    """
    accepted = [
        ("ALTER TABLE foo FORCE ROW LEVEL SECURITY", "foo"),
        ("ALTER TABLE public.foo FORCE ROW LEVEL SECURITY", "foo"),
        ('ALTER TABLE "foo" FORCE ROW LEVEL SECURITY', "foo"),
        ('ALTER TABLE public."foo" FORCE ROW LEVEL SECURITY', "foo"),
        ("alter table foo force row level security", "foo"),
    ]
    for sql, expected in accepted:
        match = _RLS_FORCE_RE.search(sql)
        assert match is not None and match.group(1) == expected, f"미정규화: {sql!r}"

    # NO FORCE (downgrade) 는 어떤 변형에서도 절대 미매칭 — 정규식 + 코드 필터 양쪽 검증
    # NO FORCE (downgrade) must never match in any variant — verify regex AND code filter
    rejected = [
        "ALTER TABLE foo NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.foo NO FORCE ROW LEVEL SECURITY",
        'ALTER TABLE "foo" NO FORCE ROW LEVEL SECURITY',
        "alter table foo no force row level security",
    ]
    for sql in rejected:
        match = _RLS_FORCE_RE.search(sql)
        # 정규식 레벨: 미매칭이거나, 매칭되더라도 캡처 그룹이 'NO' 면 안 됨
        # Regex level: either no match, or if matched the capture group must not be 'NO'
        assert match is None or match.group(1).upper() != "NO", (
            f"NO FORCE 가 FORCE 정규식에 오염 매칭: {sql!r} → {match.group(1)!r}"
        )
        # 코드 필터 레벨: 추출 헬퍼는 NO FORCE 문에서 어떤 테이블도 추출하면 안 됨
        # Code-filter level: the extraction helper must yield no tables from NO FORCE
        assert _extract_force_tables(sql) == set(), (
            f"NO FORCE 문에서 테이블 추출됨 / table extracted from NO FORCE: {sql!r}"
        )
