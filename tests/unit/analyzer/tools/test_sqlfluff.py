"""sqlfluff SQL 분석기 테스트.
sqlfluff SQL analyzer tests.
"""
import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from src.analyzer.pure.registry import AnalyzeContext, REGISTRY


def _make_ctx(language: str, filename: str) -> AnalyzeContext:
    return AnalyzeContext(
        filename=filename, content="", language=language,
        is_test=False, tmp_path=f"/tmp/{filename}",
    )


_SQLFLUFF_JSON = json.dumps([{
    "filepath": "/tmp/query.sql",
    "violations": [
        {"line_no": 5, "line_pos": 1, "code": "L001",
         "description": "Unnecessary trailing whitespace."},
        {"line_no": 10, "line_pos": 3, "code": "L014",
         "description": "Inconsistent capitalisation of keywords."},
    ]
}])


def _mock_proc(stdout: str = "", returncode: int = 0):
    m = MagicMock()
    m.stdout = stdout
    m.stderr = ""
    m.returncode = returncode
    return m


@pytest.fixture(autouse=True)
def _isolate_registry():
    """테스트 간 REGISTRY 오염 방지."""
    before = list(REGISTRY)
    yield
    REGISTRY.clear()
    REGISTRY.extend(before)


class TestSqlfluffAnalyzer:
    def test_supports_sql(self):
        # sql 언어는 supports()가 True를 반환해야 한다
        # supports() must return True for sql language
        from src.analyzer.io.tools.sqlfluff import _SqlfluffAnalyzer
        assert _SqlfluffAnalyzer().supports(_make_ctx("sql", "query.sql"))

    def test_does_not_support_python(self):
        # python 언어는 supports()가 False를 반환해야 한다
        # supports() must return False for python language
        from src.analyzer.io.tools.sqlfluff import _SqlfluffAnalyzer
        assert not _SqlfluffAnalyzer().supports(_make_ctx("python", "app.py"))

    def test_is_enabled_when_installed(self):
        # sqlfluff 바이너리가 있으면 is_enabled()는 True를 반환한다
        # is_enabled() must return True when sqlfluff binary is present
        from src.analyzer.io.tools.sqlfluff import _SqlfluffAnalyzer
        ctx = _make_ctx("sql", "query.sql")
        with patch("shutil.which", return_value="/usr/bin/sqlfluff"):
            assert _SqlfluffAnalyzer().is_enabled(ctx) is True

    def test_is_enabled_false_when_missing(self):
        # sqlfluff 바이너리가 없으면 is_enabled()는 False를 반환한다
        # is_enabled() must return False when sqlfluff binary is absent
        from src.analyzer.io.tools.sqlfluff import _SqlfluffAnalyzer
        ctx = _make_ctx("sql", "query.sql")
        with patch("shutil.which", return_value=None):
            assert _SqlfluffAnalyzer().is_enabled(ctx) is False

    def test_parses_violations(self):
        # sqlfluff JSON 출력의 violations를 파싱해 이슈를 반환해야 한다
        # Must parse violations from sqlfluff JSON output and return issues
        from src.analyzer.io.tools.sqlfluff import _SqlfluffAnalyzer
        ctx = _make_ctx("sql", "query.sql")
        with patch("subprocess.run") as mock_run:
            with patch("shutil.which", return_value="/usr/bin/sqlfluff"):
                mock_run.return_value = _mock_proc(_SQLFLUFF_JSON, 65)
                issues = _SqlfluffAnalyzer().run(ctx)
        assert len(issues) == 2
        assert issues[0].line == 5
        assert issues[1].line == 10

    def test_returns_empty_on_timeout(self):
        # subprocess TimeoutExpired 시 빈 목록을 반환해야 한다
        # Must return empty list on subprocess TimeoutExpired
        from src.analyzer.io.tools.sqlfluff import _SqlfluffAnalyzer
        ctx = _make_ctx("sql", "query.sql")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("sqlfluff", 30)):
            with patch("shutil.which", return_value="/usr/bin/sqlfluff"):
                assert _SqlfluffAnalyzer().run(ctx) == []

    def test_returns_empty_on_empty_output(self):
        # 빈 stdout은 빈 이슈 목록을 반환해야 한다
        # Empty stdout must return an empty issue list
        from src.analyzer.io.tools.sqlfluff import _SqlfluffAnalyzer
        ctx = _make_ctx("sql", "query.sql")
        with patch("subprocess.run", return_value=_mock_proc("", 0)):
            issues = _SqlfluffAnalyzer().run(ctx)
        assert issues == []

    def test_module_registers_sqlfluff(self):
        # 모듈 임포트 시 REGISTRY에 sqlfluff가 자동 등록된다
        # Module import must auto-register sqlfluff in REGISTRY
        import importlib
        import src.analyzer.io.tools.sqlfluff  # noqa: F401
        importlib.reload(src.analyzer.io.tools.sqlfluff)
        names = [a.name for a in REGISTRY]
        assert "sqlfluff" in names
