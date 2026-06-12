"""ORM 모델과 Alembic 마이그레이션 파일의 컬럼 완전성 정적 검사.

Static check: every non-PK column in every ORM model must appear by name
in at least one alembic/versions/*.py file.  Catches the class of bug where
a developer adds a Column to the ORM but forgets to write the migration —
unit tests still pass (Base.metadata.create_all on in-memory SQLite) but
the production DB is missing the column and raises a 500 on first access.

How it works
------------
- All ORM models are imported so SQLAlchemy registers their tables.
- All migration files are read and concatenated into one search blob.
- For each (table, column) pair we do a plain substring search.
- Primary-key columns named "id" are skipped (always present, never migrated
  individually).  Columns whose names are unambiguous enough to match across
  all migration files are accepted.
"""

import glob
import os
import re

import pytest

# --- import every ORM model so SQLAlchemy registers the tables ---
# 🔴 11종 ORM 전수 명시 import (C5): 누락 시 conftest→src.main 전이 import 에 우발 의존(self-contained
# 아님) — 그 4종(insight_narrative_cache·issue_registration·merge_retry·security_alert_log)의 컬럼이
# 마이그레이션 완전성 검사에서 빠져 ORM↔alembic drift 를 못 잡는다. testing.md "empty __init__ + explicit
# ORM import 의무" 정합. 신규 ORM 모델 추가 시 이 목록에 등재 의무.
# Explicitly import all 11 ORM models (C5): otherwise 4 of them rely on the conftest→src.main side-effect
# import chain (not self-contained), excluding their columns from the completeness check.
import src.models.analysis  # noqa: F401
import src.models.analysis_feedback  # noqa: F401
import src.models.gate_decision  # noqa: F401
import src.models.insight_narrative_cache  # noqa: F401
import src.models.issue_registration  # noqa: F401
import src.models.merge_attempt  # noqa: F401
import src.models.merge_retry  # noqa: F401
import src.models.repo_config  # noqa: F401
import src.models.repository  # noqa: F401
import src.models.security_alert_log  # noqa: F401
import src.models.user  # noqa: F401
from src.database import Base

# 마이그레이션 파일을 통합한 검색 텍스트 — 모든 버전 파일 내용을 합침
# Concatenation of all migration file contents used as the search blob.
_MIGRATIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "alembic", "versions"
)

# 마이그레이션 텍스트를 모듈 레벨에서 한 번만 읽음 (성능 최적화)
# Read once at module level to avoid repeated I/O per parameterised test.
def _load_migration_text() -> str:
    pattern = os.path.join(_MIGRATIONS_DIR, "*.py")
    files = glob.glob(pattern)
    contents = []
    for f in sorted(files):
        with open(f, encoding="utf-8") as migration_file:
            contents.append(migration_file.read())
    return "\n".join(contents)


_MIGRATION_TEXT: str = _load_migration_text()

# 검사에서 제외할 컬럼 이름 — 모든 테이블에서 공통으로 사용되는 이름이거나
# 마이그레이션 파일이 아닌 초기 스키마로 생성된 컬럼.
# Column names to skip: either always-present PKs, or so generic that a plain
# substring match would produce false positives.
_SKIP_COLUMNS = frozenset({"id"})

# 검사에서 제외할 테이블 — alembic_version 등 내부 관리 테이블
# Tables managed by Alembic itself, not by our models.
_SKIP_TABLES = frozenset({"alembic_version"})


def _columns_to_check():
    """Base.metadata에 등록된 모든 (테이블명, 컬럼명) 쌍을 반환.

    Returns every (table_name, column_name) pair that should be verified.
    """
    pairs = []
    for table_name, table in Base.metadata.tables.items():
        if table_name in _SKIP_TABLES:
            continue
        for col in table.columns:
            if col.name in _SKIP_COLUMNS:
                continue
            pairs.append((table_name, col.name))
    return pairs


@pytest.mark.parametrize("table_name,column_name", _columns_to_check())
def test_column_appears_in_migration(table_name: str, column_name: str) -> None:
    """각 ORM 컬럼이 Alembic 마이그레이션 파일에 언급되어 있는지 확인.

    Verifies that ``column_name`` appears somewhere in the combined text of all
    migration files.  A missing column means the developer added it to the ORM
    but forgot to write a migration — the production DB will be missing the
    column and return a 500 on first access.

    Fix: run ``make revision m="설명"`` and add ``op.add_column(...)`` for the
    missing column before merging.
    """
    # 컬럼명이 마이그레이션 텍스트에 나타나는지 단어 경계로 검색
    # Search with word-boundary to avoid substring false positives
    # (e.g. "id" inside "repo_id").  We accept either a quoted string form
    # ('column_name' or "column_name") or unquoted as a Python identifier.
    pattern = (
        r"""(?x)                 # verbose mode
        (?:                      # quoted form
            ['"]""" + re.escape(column_name) + r"""['"]
        )
        |
        (?:                      # unquoted identifier form
            \b""" + re.escape(column_name) + r"""\b
        )
    """
    )
    found = bool(re.search(pattern, _MIGRATION_TEXT))
    assert found, (
        f"\n\nORM 컬럼 '{table_name}.{column_name}'이 Alembic 마이그레이션 파일에 없습니다.\n"
        f"ORM column '{table_name}.{column_name}' not found in any migration file.\n\n"
        f"수정 방법 / Fix:\n"
        f"  make revision m=\"add {column_name} to {table_name}\"\n"
        f"  # 생성된 파일에 op.add_column('{table_name}', sa.Column('{column_name}', ...)) 추가\n"
        f"  # Then add op.add_column('{table_name}', sa.Column('{column_name}', ...)) in the new file\n"
    )
