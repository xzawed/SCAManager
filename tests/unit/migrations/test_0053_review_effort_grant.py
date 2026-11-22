"""0053 — review_effort 열과 관측 역할 GRANT (Issue #1905 ③a).

0053 adds repo_configs.review_effort and grants it to the observer role on PostgreSQL only.
실 PG 에서 권한이 그대로 걸리는지는 tests/integration/test_observer_role_postgres.py 가 잰다(CI PG 작업).
Whether the grant really applies is measured on real PostgreSQL by the integration test.
"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

_PATH = Path(__file__).resolve().parents[3] / "alembic" / "versions" / "0053_repo_config_review_effort.py"


def _load():
    spec = importlib.util.spec_from_file_location("revision_0053", _PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Op:
    def __init__(self, dialect: str):
        self.calls: list[tuple] = []
        self._bind = SimpleNamespace(dialect=SimpleNamespace(name=dialect))

    def get_bind(self):
        return self._bind

    def add_column(self, table, column):
        self.calls.append(("add_column", table, column.name, column.nullable))

    def drop_column(self, table, column):
        self.calls.append(("drop_column", table, column))

    def execute(self, sql):
        self.calls.append(("execute", str(sql)))


def test_upgrade_grants_the_new_column_to_the_observer_on_postgres(monkeypatch):
    rev = _load()
    op = _Op("postgresql")
    monkeypatch.setattr(rev, "op", op)
    rev.upgrade()
    assert op.calls[0] == ("add_column", "repo_configs", "review_effort", True)
    executed = [call[1] for call in op.calls if call[0] == "execute"]
    assert len(executed) == 1, op.calls
    # 역할이 있을 때만 · 그 컬럼 하나만 / only when the role exists, and only that column
    assert "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'scamanager_observer')" in executed[0]
    assert "GRANT SELECT (review_effort) ON repo_configs TO scamanager_observer;" in executed[0]
    assert executed[0].count("GRANT") == 1


def test_upgrade_on_sqlite_only_adds_the_column(monkeypatch):
    rev = _load()
    op = _Op("sqlite")
    monkeypatch.setattr(rev, "op", op)
    rev.upgrade()
    assert op.calls == [("add_column", "repo_configs", "review_effort", True)]


def test_downgrade_drops_the_column_and_with_it_the_grant(monkeypatch):
    # 컬럼을 지우면 그 컬럼 권한도 함께 사라진다(0051 과 같다) / dropping the column drops its grant too
    rev = _load()
    op = _Op("postgresql")
    monkeypatch.setattr(rev, "op", op)
    rev.downgrade()
    assert op.calls == [("drop_column", "repo_configs", "review_effort")]
