"""RLS 정적 매트릭스(_RLS_MATRIX)와 Alembic RLS 정책의 자동탐지 완전성 검사.

Auto-detection completeness check between the static RLS matrix (``_RLS_MATRIX``)
and the actual ``ENABLE ROW LEVEL SECURITY`` statements in Alembic migrations.

배경 / Background
----------------
``src/services/saas_service.py::_RLS_MATRIX`` 는 admin RLS 감사 리포트
(``GET /admin/rls-audit``)의 단일 출처다. 새 테이블에 alembic 으로 RLS 정책을
적용해도 이 매트릭스를 갱신하지 않으면 감사 리포트가 갭(미적용 테이블)을 보고하지
못한다 — 실제로 0037 의 ``issue_registrations`` 가 한동안 매트릭스에서 누락됐었다.

``_RLS_MATRIX`` is the single source of the admin RLS audit report
(``GET /admin/rls-audit``). When a new table gets an RLS policy in alembic but the
matrix isn't updated, the audit report silently fails to surface the gap — exactly
what happened to ``issue_registrations`` (0037) for a while.

동작 방식 / How it works
------------------------
- 모든 alembic 마이그레이션 파일에서 ``ALTER TABLE <t> ENABLE ROW LEVEL SECURITY``
  구문을 정규식으로 추출 → 실제 RLS 적용 테이블 집합.
- ``_RLS_MATRIX`` 의 ``table`` 키 집합과 양방향(bijection) 대조.
- 누락(매트릭스 미등재) 또는 유령(존재하지 않는 alembic 정책) 항목을 모두 차단한다.

This is a regression guard: adding RLS to a new table in alembic *forces* a matching
matrix entry (and vice versa), so the audit report can never silently drift again.
"""
import glob
import os
import re

from src.services.saas_service import _RLS_MATRIX

# 마이그레이션 파일 디렉토리 — 테스트 파일 기준 상대 경로
# Migration directory, resolved relative to this test file.
_MIGRATIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "alembic", "versions"
)

# ``ALTER TABLE <table> ENABLE ROW LEVEL SECURITY`` 만 매칭 (DISABLE 은 제외).
# 선택적 스키마 한정(public.foo)·큰따옴표 식별자("foo")도 bare 테이블명으로 정규화 —
# 미래 마이그레이션 변형이 가드를 silent 우회(false-negative)하지 못하게 차단.
# Match only ENABLE statements (downgrade DISABLE must not match). Optional schema
# qualification (public.foo) and quoted identifiers ("foo") normalise to the bare
# table name so a future migration variant cannot silently bypass the guard.
_RLS_ENABLE_RE = re.compile(
    r'ALTER\s+TABLE\s+(?:"?\w+"?\.)?"?(\w+)"?\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY',
    re.IGNORECASE,
)


def _alembic_rls_tables() -> set[str]:
    """모든 alembic 마이그레이션에서 RLS 가 활성화된 테이블 집합을 반환.

    Return the set of tables that have RLS enabled across all alembic migrations.
    """
    pattern = os.path.join(_MIGRATIONS_DIR, "*.py")
    tables: set[str] = set()
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding="utf-8") as migration_file:
            tables.update(m.group(1) for m in _RLS_ENABLE_RE.finditer(migration_file.read()))
    return tables


def _matrix_tables() -> set[str]:
    """``_RLS_MATRIX`` 의 table 키 집합을 반환.

    Return the set of table names declared in ``_RLS_MATRIX``.
    """
    return {entry["table"] for entry in _RLS_MATRIX}


def test_rls_matrix_covers_every_alembic_rls_table() -> None:
    """alembic 으로 RLS 적용된 모든 테이블이 _RLS_MATRIX 에 등재돼 있어야 한다.

    Every table that has RLS enabled in alembic must appear in ``_RLS_MATRIX``,
    otherwise the admin audit report under-reports coverage.
    """
    missing = _alembic_rls_tables() - _matrix_tables()
    assert not missing, (
        f"\n\nalembic 에 RLS 가 적용됐지만 _RLS_MATRIX 에 누락된 테이블: {sorted(missing)}\n"
        f"Tables with RLS in alembic but missing from _RLS_MATRIX: {sorted(missing)}\n\n"
        f"수정 / Fix: src/services/saas_service.py 의 _RLS_MATRIX 에 누락 테이블 항목을 추가하세요.\n"
    )


def test_rls_matrix_has_no_phantom_tables() -> None:
    """_RLS_MATRIX 의 모든 테이블이 실제 alembic RLS 정책을 가져야 한다.

    Every table in ``_RLS_MATRIX`` must have a real ``ENABLE ROW LEVEL SECURITY``
    statement in alembic — guards against stale/typo'd matrix entries.
    """
    phantom = _matrix_tables() - _alembic_rls_tables()
    assert not phantom, (
        f"\n\n_RLS_MATRIX 에 있으나 alembic RLS 정책이 없는 유령 테이블: {sorted(phantom)}\n"
        f"Tables in _RLS_MATRIX with no matching alembic RLS policy: {sorted(phantom)}\n\n"
        f"수정 / Fix: 오타이거나 마이그레이션이 누락됐습니다. _RLS_MATRIX 항목 또는 alembic 을 점검하세요.\n"
    )


def test_rls_matrix_exact_bijection() -> None:
    """alembic RLS 테이블 집합과 _RLS_MATRIX 테이블 집합이 정확히 일치해야 한다.

    The two sets must be exactly equal (bijection) — the strongest guard.
    """
    assert _alembic_rls_tables() == _matrix_tables(), (
        f"\n\nalembic RLS 테이블 ≠ _RLS_MATRIX 테이블\n"
        f"alembic: {sorted(_alembic_rls_tables())}\n"
        f"matrix : {sorted(_matrix_tables())}\n"
    )


def test_rls_enable_regex_normalises_schema_and_quotes() -> None:
    """스키마 한정/따옴표 식별자/대소문자 변형도 bare 테이블명으로 정규화돼야 한다.

    Future migration variants (schema-qualified, quoted, lowercase) must normalise to
    the bare table name; DISABLE statements must never match. Guards against the
    silent false-negative class where the bijection check would mis-classify a table.
    """
    accepted = [
        ("ALTER TABLE foo ENABLE ROW LEVEL SECURITY", "foo"),
        ("ALTER TABLE public.foo ENABLE ROW LEVEL SECURITY", "foo"),
        ('ALTER TABLE "foo" ENABLE ROW LEVEL SECURITY', "foo"),
        ('ALTER TABLE public."foo" ENABLE ROW LEVEL SECURITY', "foo"),
        ("alter table foo enable row level security", "foo"),
    ]
    for sql, expected in accepted:
        match = _RLS_ENABLE_RE.search(sql)
        assert match is not None and match.group(1) == expected, f"미정규화: {sql!r}"

    # downgrade DISABLE 은 절대 매칭 금지
    assert _RLS_ENABLE_RE.search("ALTER TABLE foo DISABLE ROW LEVEL SECURITY") is None
