"""sqlfluff SQL 분석기 테스트.

🔴 `sql` 은 **provisioned 분석기가 sqlfluff 하나뿐인 유일한 언어**다(실측, #1521).
semgrep 은 sql 을 지원하지 않으므로 sqlfluff 가 조용히 죽으면 그 파일에는
**대체 관측면이 전혀 없다** — 미분석 SQL 이 정적 만점을 받고 auto-merge 된다.

아래 시나리오는 실 sqlfluff 4.2.2 로 잰 값이다:

    clean            exit 0  stdout `[{"filepath": …, "violations": []}]`   ← 빈값이 아니다
    위반 있음        exit 1  stdout `[{… "violations": [{"start_line_no": 1, …}]}]`
    잘못된 dialect   exit 2  stdout `Error: Unknown dialect 'zzznope'`      ← 비-JSON
    파일 없음        exit 2  stdout 빈값

즉 (a) 「빈 stdout = 깨끗함」은 틀렸고, (b) `returncode != 0` 을 크래시 신호로 쓰면
**정상 탐지(exit 1)를 크래시로 오분류**한다. 판별식은 stdout 이 JSON 배열인가다.

sqlfluff analyzer tests. SQL is the only language whose sole provisioned analyzer is
sqlfluff, so a silent crash there leaves no alternative observation surface at all.
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


# 실 sqlfluff 4.x 의 키다(실측) — 3.0 에서 `line_no` → `start_line_no` 로 바뀌었다.
# The real key on sqlfluff 4.x; renamed from `line_no` in 3.0.
_SQLFLUFF_JSON = json.dumps([{
    "filepath": "/tmp/query.sql",
    "violations": [
        {"start_line_no": 5, "start_line_pos": 1, "code": "LT01",
         "description": "Unnecessary trailing whitespace."},
        {"start_line_no": 10, "start_line_pos": 3, "code": "CP01",
         "description": "Inconsistent capitalisation of keywords."},
    ]
}])

# sqlfluff 2.x 이하의 키 — 핀을 되돌리는 경우를 위해 호환을 유지한다.
_SQLFLUFF_JSON_LEGACY = json.dumps([{
    "filepath": "/tmp/query.sql",
    "violations": [
        {"line_no": 7, "line_pos": 1, "code": "L001", "description": "Old key shape."},
    ]
}])

# 깨끗한 파일도 문서를 낸다 — 빈 출력이 아니다(실측).
_SQLFLUFF_CLEAN = json.dumps([{"filepath": "/tmp/query.sql", "violations": []}])


def _mock_proc(stdout: str = "", returncode: int = 0, stderr: str = ""):
    m = MagicMock()
    m.stdout = stdout
    m.stderr = stderr
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
        # 🔴 실 sqlfluff 4.x 의 `start_line_no` 를 읽어야 한다. `line_no` 만 읽으면
        #    실물에서는 **모든 이슈의 line 이 0** 이 되는데, 손으로 쓴 mock 픽스처가
        #    `line_no` 를 쓰면 그 어긋남이 초록 뒤에 숨는다.
        # Must read `start_line_no` (sqlfluff 4.x); reading only `line_no` yields line 0
        # for every real issue while a hand-written fixture hides the drift.
        from src.analyzer.io.tools.sqlfluff import _SqlfluffAnalyzer
        ctx = _make_ctx("sql", "query.sql")
        with patch("subprocess.run", return_value=_mock_proc(_SQLFLUFF_JSON, 1)):
            issues = _SqlfluffAnalyzer().run(ctx)
        assert len(issues) == 2
        assert issues[0].line == 5
        assert issues[1].line == 10

    def test_legacy_line_no_key_still_parses(self):
        # 구 키(`line_no`)도 계속 읽는다 — 핀을 되돌려도 line 이 0 이 되지 않게.
        # The pre-3.0 key still parses, so pinning back does not silently zero the lines.
        from src.analyzer.io.tools.sqlfluff import _SqlfluffAnalyzer
        ctx = _make_ctx("sql", "query.sql")
        with patch("subprocess.run", return_value=_mock_proc(_SQLFLUFF_JSON_LEGACY, 1)):
            issues = _SqlfluffAnalyzer().run(ctx)
        assert len(issues) == 1
        assert issues[0].line == 7

    def test_findings_exit_code_is_not_a_crash(self):
        # 🔴 sqlfluff 는 **위반을 찾으면 exit 1** 이다(실측). `returncode != 0` 을
        #    크래시 신호로 쓰면 정상 탐지가 통째로 «분석 실패» 가 된다.
        # sqlfluff exits 1 when it FINDS violations; a nonzero-exit crash discriminator
        # would turn every successful dirty run into a failure.
        from src.analyzer.io.tools.sqlfluff import _SqlfluffAnalyzer
        ctx = _make_ctx("sql", "query.sql")
        with patch("subprocess.run", return_value=_mock_proc(_SQLFLUFF_JSON, 1)):
            issues = _SqlfluffAnalyzer().run(ctx)
        assert len(issues) == 2, "exit 1 + 유효 JSON 은 정상 탐지다"

    def test_clean_run_returns_no_issues_without_raising(self):
        # 깨끗한 파일: exit 0 + `violations: []` → 이슈 0건이되 예외는 아니다.
        # A clean file must produce zero issues without raising.
        from src.analyzer.io.tools.sqlfluff import _SqlfluffAnalyzer
        ctx = _make_ctx("sql", "query.sql")
        with patch("subprocess.run", return_value=_mock_proc(_SQLFLUFF_CLEAN, 0)):
            assert _SqlfluffAnalyzer().run(ctx) == []

    def test_non_json_stdout_raises(self):
        # 🔴 비-JSON stdout = sqlfluff 가 **분석하지 않았다**. `[]` 를 돌려주면
        #    «이슈 0건 · 완전» 이 되어 미분석 SQL 이 만점으로 auto-merge 된다.
        # Non-JSON stdout means sqlfluff never analyzed; returning [] records it as clean.
        from src.analyzer.io.tools.sqlfluff import _SqlfluffAnalyzer
        ctx = _make_ctx("sql", "query.sql")
        crash = _mock_proc("Error: Unknown dialect 'zzznope'\n", 2)
        with patch("subprocess.run", return_value=crash):
            with pytest.raises(RuntimeError, match="sqlfluff"):
                _SqlfluffAnalyzer().run(ctx)

    def test_empty_stdout_raises(self):
        # 🔴 빈 stdout 은 «깨끗함» 이 아니다 — 깨끗한 실행도 `[{…"violations": []}]` 를
        #    낸다(실측). 빈 출력은 sqlfluff 가 시작조차 못 한 경우다(예: 파일 부재, exit 2).
        # An empty stdout is never a clean run: a clean run still emits a JSON document.
        from src.analyzer.io.tools.sqlfluff import _SqlfluffAnalyzer
        ctx = _make_ctx("sql", "query.sql")
        with patch("subprocess.run", return_value=_mock_proc("", 2)):
            with pytest.raises(RuntimeError, match="sqlfluff"):
                _SqlfluffAnalyzer().run(ctx)

    def test_skipped_file_raises_because_zero_entries_means_it_never_ran(self):
        # 🔴 sqlfluff 는 20,000 바이트를 넘는 파일을 **분석하지 않고 건너뛴다**
        #    (`large_file_skip_byte_limit`, 기본 20000). 그때 stdout 은 `[]` 이고
        #    **exit 0** 이라, 「이슈 0건 · 완전」으로 기록되어 만점 + auto-merge 가 된다.
        #    실측: 같은 내용을 10배 길게 하자 3.2KB=9건 → 32KB=0건 · exit 0 · stdout `[]`.
        #    깨끗한 파일은 엔트리 **1개**(`violations: []`)를 낸다 — 엔트리 0개는
        #    「이 경로에 대한 결과가 없다」= 분석하지 않았다는 뜻이다.
        # A skipped file yields `[]` with exit 0; a clean file yields one entry. Zero
        # entries means sqlfluff produced no result for this path at all.
        from src.analyzer.io.tools.sqlfluff import _SqlfluffAnalyzer
        ctx = _make_ctx("sql", "query.sql")
        skipped = _mock_proc(
            "[]", 0,
            stderr=("WARNING Length of file 'query.sql' is 32000 bytes which is over the "
                    "limit of 20000 bytes. Skipping to avoid parser lock."),
        )
        with patch("subprocess.run", return_value=skipped):
            with pytest.raises(RuntimeError, match="sqlfluff"):
                _SqlfluffAnalyzer().run(ctx)

    def test_unparseable_json_raises(self):
        # `[` 로 시작하지만 파싱이 안 되는 출력(절단 등)도 미분석이다.
        # Truncated output that starts with '[' is still an unanalyzed run.
        from src.analyzer.io.tools.sqlfluff import _SqlfluffAnalyzer
        ctx = _make_ctx("sql", "query.sql")
        with patch("subprocess.run", return_value=_mock_proc('[{"violations": ', 2)):
            with pytest.raises(RuntimeError, match="sqlfluff"):
                _SqlfluffAnalyzer().run(ctx)

    def test_timeout_stays_on_the_timeout_axis(self):
        # 타임아웃은 `ctx.timed_out` 이 담당한다 — 예외를 올리지 않고 `[]` 다.
        # The timeout axis is owned by ctx.timed_out; do not raise here.
        from src.analyzer.io.tools.sqlfluff import _SqlfluffAnalyzer
        ctx = _make_ctx("sql", "query.sql")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("sqlfluff", 30)):
            assert _SqlfluffAnalyzer().run(ctx) == []
        assert ctx.timed_out is True

    def test_missing_binary_stays_on_the_procurement_axis(self):
        # 바이너리 부재는 `unavailable_tools` 축이다 — 여기서 예외로 올리지 않는다.
        # A missing binary belongs to the procurement axis, not to incomplete.
        from src.analyzer.io.tools.sqlfluff import _SqlfluffAnalyzer
        ctx = _make_ctx("sql", "query.sql")
        with patch("subprocess.run", side_effect=FileNotFoundError("sqlfluff")):
            assert _SqlfluffAnalyzer().run(ctx) == []

    def test_spawn_failure_is_not_a_clean_run(self):
        # 🔴 `shutil.which` 를 통과한 뒤의 실행 실패(PermissionError·ENOEXEC·TOCTOU)는
        #    「바이너리 부재」가 아니라 **미분석**이다. `except OSError` 로 넓게 삼키면
        #    그 구별이 사라져 미분석이 «깨끗함» 이 된다.
        # A spawn failure after which() succeeded is unanalyzed, not "binary absent".
        from src.analyzer.io.tools.sqlfluff import _SqlfluffAnalyzer
        ctx = _make_ctx("sql", "query.sql")
        with patch("subprocess.run", side_effect=PermissionError("exec format error")):
            with pytest.raises(OSError):
                _SqlfluffAnalyzer().run(ctx)

    def test_module_registers_sqlfluff(self):
        # 모듈 임포트 시 REGISTRY에 sqlfluff가 자동 등록된다
        # Module import must auto-register sqlfluff in REGISTRY
        # 🔴 plain `import src…` 를 쓰지 않는다 — 이 파일이 `from src… import` 도 쓰므로
        #    공존하면 CodeQL py/import-and-import-from 을 자초한다(`check_dual_import.py`).
        #    `reload` 는 유지한다 — `import_module` 만으로는 캐시라 register() 가 재실행되지 않는다.
        # Use the string path: a plain import alongside `from X import` self-inflicts the
        # CodeQL dual-import alert. reload() stays, since import_module alone would not re-run.
        import importlib
        importlib.reload(importlib.import_module("src.analyzer.io.tools.sqlfluff"))
        names = [a.name for a in REGISTRY]
        assert "sqlfluff" in names
