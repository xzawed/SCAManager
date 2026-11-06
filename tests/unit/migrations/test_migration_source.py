"""`_migration_source` 자기검증 — SQL 로 세는 것은 실제로 보내는 글자뿐인가.

Calibrates the migration reader: only strings handed to execute()/text() count as SQL.
"""
from __future__ import annotations

import pytest

from ._migration_source import module_constants, sql_literals

_SQL = "DROP INDEX IF EXISTS ix_demo"


_UPGRADE = "def upgrade():\n    op.execute('SELECT 1')\n"


@pytest.mark.parametrize("module", [
    f'"""{_SQL} 를 보낸다."""\n' + _UPGRADE,
    f"# {_SQL}\n" + _UPGRADE,
    f'NOTE = "{_SQL}"\n' + _UPGRADE,
    f'def downgrade():\n    op.execute("{_SQL}")\n' + _UPGRADE,
    f'def upgrade():\n    op.execute("-- {_SQL}\\nSELECT 1")\n',
], ids=["docstring", "comment", "unsent-constant", "other-function", "sql-comment"])
def test_text_that_is_not_sent_from_upgrade_is_not_sql(tmp_path, module):
    """🔴 docstring · 주석 · 보내지 않는 상수 · 다른 함수 · SQL 주석 속 글자는 upgrade 의 SQL 이 아니다."""
    path = tmp_path / "m.py"
    path.write_text(module, encoding="utf-8")
    assert _SQL in path.read_text(encoding="utf-8")
    assert not any(_SQL in sql for sql in sql_literals(path, "upgrade"))


@pytest.mark.parametrize("call", [
    f'op.execute("{_SQL}")',
    f'conn.execute(sa.text("{_SQL}"))',
    f'op.execute(\n        """\n        {_SQL}\n        """\n    )',
], ids=["op.execute", "sa.text", "multiline"])
def test_sent_sql_is_found(tmp_path, call):
    """대조군 — `op.execute` · `sa.text` · 여러 줄 SQL 은 공백을 접은 채로 찾는다."""
    path = tmp_path / "m.py"
    path.write_text(f"def upgrade():\n    {call}\n", encoding="utf-8")
    assert _SQL in sql_literals(path, "upgrade")


def test_sql_string_literals_keep_their_dashes(tmp_path):
    """SQL 문자열 리터럴 안의 `--` 는 주석이 아니다 — 지우면 보내는 SQL 이 잘린다(Grok C7 반례)."""
    path = tmp_path / "m.py"
    path.write_text("def upgrade():\n    op.execute(\"SELECT '--keep me' AS x -- note\\nFROM t\")\n",
                    encoding="utf-8")
    assert sql_literals(path, "upgrade") == ["SELECT '--keep me' AS x FROM t"]


def test_results_follow_source_order(tmp_path):
    """결과는 소스 순서다 — 구문 트리 너비 우선 순서가 새지 않는다(Grok C7 반례)."""
    path = tmp_path / "m.py"
    path.write_text('def upgrade():\n    conn.execute(sa.text("FIRST"))\n    op.execute("SECOND")\n',
                    encoding="utf-8")
    assert sql_literals(path, "upgrade") == ["FIRST", "SECOND"]


def test_async_and_nested_definitions(tmp_path):
    """`async def upgrade` 도 찾는다. upgrade 안에서 정의한 함수의 SQL 은 upgrade 의 SQL 로 센다(그 안에서 부르니까)."""
    path = tmp_path / "m.py"
    path.write_text('async def upgrade():\n    def inner():\n        op.execute("NESTED")\n    inner()\n',
                    encoding="utf-8")
    assert sql_literals(path, "upgrade") == ["NESTED"]


def test_missing_function_is_red_not_empty(tmp_path):
    """못 재면 red — 함수 이름이 틀리면 빈 목록(«SQL 없음») 이 아니라 실패다."""
    path = tmp_path / "m.py"
    path.write_text("def upgrade():\n    pass\n", encoding="utf-8")
    with pytest.raises(AssertionError):
        sql_literals(path, "upgrad")


def test_module_constants_reads_literals_only(tmp_path):
    """최상위 리터럴 대입만 — 함수 안 대입과 식은 빠진다."""
    path = tmp_path / "m.py"
    path.write_text('_INDEX = "ix_a"\n_N = 3\n_X = f(1)\ndef g():\n    _INNER = "no"\n', encoding="utf-8")
    assert module_constants(path) == {"_INDEX": "ix_a", "_N": 3}
