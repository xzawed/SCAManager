"""Phase 4 PR-T1 — Python static analyzer tools 단위 테스트.

대상 모듈: `src/analyzer/io/tools/python.py`
  - _PylintAnalyzer  (code_quality)
  - _Flake8Analyzer  (code_quality)
  - _BanditAnalyzer  (security, 테스트 파일 제외)

subprocess.run mock 으로 실제 도구 바이너리 호출 없이 모든 경로 검증.
14-에이전트 감사 R1-B 에서 식별된 Critical Gap (test_python.py 전무) 해소.
"""
import json
import os
import subprocess

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:test")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123456")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

# pylint: disable=redefined-outer-name,wrong-import-position
from unittest.mock import MagicMock, patch

import pytest

from src.analyzer.io.tools.python import (
    _BanditAnalyzer,
    _Flake8Analyzer,
    _PylintAnalyzer,
)
from src.analyzer.pure.registry import (
    AnalyzeContext,
    Category,
    Severity,
)
from src.constants import STATIC_ANALYSIS_TIMEOUT


# ──────────────────────────────────────────────────────────────────────────
# 공용 헬퍼 — subprocess.run mock + AnalyzeContext fixture
# ──────────────────────────────────────────────────────────────────────────


def _mock_proc(stdout: str = "", returncode: int = 0) -> MagicMock:
    """subprocess.run 반환값을 모방하는 MagicMock 생성."""
    mock = MagicMock()
    mock.stdout = stdout
    mock.returncode = returncode
    return mock


@pytest.fixture
def py_ctx() -> AnalyzeContext:
    """Python 파일용 AnalyzeContext (테스트 아님)."""
    return AnalyzeContext(
        filename="src/example.py",
        content="x = 1\n",
        language="python",
        tmp_path="/tmp/example.py",
        is_test=False,
    )


@pytest.fixture
def py_test_ctx() -> AnalyzeContext:
    """Python 테스트 파일용 AnalyzeContext."""
    return AnalyzeContext(
        filename="tests/test_example.py",
        content="def test_foo(): pass\n",
        language="python",
        tmp_path="/tmp/test_example.py",
        is_test=True,
    )


@pytest.fixture
def js_ctx() -> AnalyzeContext:
    """JavaScript 파일 — Python analyzer가 supports() 거부해야 함."""
    return AnalyzeContext(
        filename="src/app.js",
        content="const x = 1;\n",
        language="javascript",
        tmp_path="/tmp/app.js",
        is_test=False,
    )


# ──────────────────────────────────────────────────────────────────────────
# _PylintAnalyzer
# ──────────────────────────────────────────────────────────────────────────


class TestPylintAnalyzerAttributes:
    """name/category 속성 + Analyzer Protocol 구현 검증."""

    def test_name_is_pylint(self):
        assert _PylintAnalyzer().name == "pylint"

    def test_category_is_code_quality(self):
        assert _PylintAnalyzer().category == Category.CODE_QUALITY


class TestPylintSupports:
    """supports(): language=='python' 만 True."""

    def test_returns_true_for_python(self, py_ctx):
        assert _PylintAnalyzer().supports(py_ctx) is True

    def test_returns_false_for_javascript(self, js_ctx):
        assert _PylintAnalyzer().supports(js_ctx) is False

    @pytest.mark.parametrize("lang", ["go", "rust", "shell", "ruby", "unknown"])
    def test_returns_false_for_other_languages(self, lang):
        ctx = AnalyzeContext(
            filename="x", content="", language=lang,
            tmp_path="/tmp/x", is_test=False,
        )
        assert _PylintAnalyzer().supports(ctx) is False


class TestPylintIsEnabled:
    """is_enabled(): 항상 True (pip 의존성 보장)."""

    def test_always_enabled_for_prod(self, py_ctx):
        assert _PylintAnalyzer().is_enabled(py_ctx) is True

    def test_always_enabled_for_test(self, py_test_ctx):
        assert _PylintAnalyzer().is_enabled(py_test_ctx) is True


class TestPylintRunSubprocessCall:
    """subprocess.run 호출 인자 검증."""

    def test_includes_pylint_binary_and_path(self, py_ctx):
        with patch("subprocess.run", return_value=_mock_proc("[]")) as mock_run:
            _PylintAnalyzer().run(py_ctx)
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "pylint"
        assert "/tmp/example.py" in cmd

    def test_uses_static_analysis_timeout(self, py_ctx):
        with patch("subprocess.run", return_value=_mock_proc("[]")) as mock_run:
            _PylintAnalyzer().run(py_ctx)
        assert mock_run.call_args.kwargs["timeout"] == STATIC_ANALYSIS_TIMEOUT

    def test_includes_json_output_format(self, py_ctx):
        with patch("subprocess.run", return_value=_mock_proc("[]")) as mock_run:
            _PylintAnalyzer().run(py_ctx)
        cmd = mock_run.call_args.args[0]
        assert "--output-format=json" in cmd

    def test_test_file_adds_extra_disables(self, py_test_ctx):
        """is_test=True → W0611,W0212,C0302,R0401 추가 disable."""
        with patch("subprocess.run", return_value=_mock_proc("[]")) as mock_run:
            _PylintAnalyzer().run(py_test_ctx)
        cmd = mock_run.call_args.args[0]
        disable_arg = next(a for a in cmd if a.startswith("--disable="))
        assert "W0611" in disable_arg
        assert "R0401" in disable_arg

    def test_prod_file_no_extra_test_disables(self, py_ctx):
        """is_test=False → W0611 등 미포함."""
        with patch("subprocess.run", return_value=_mock_proc("[]")) as mock_run:
            _PylintAnalyzer().run(py_ctx)
        cmd = mock_run.call_args.args[0]
        disable_arg = next(a for a in cmd if a.startswith("--disable="))
        assert "W0611" not in disable_arg


class TestPylintRunOutputParsing:
    """JSON 출력 파싱 + Severity 분류."""

    def test_maps_error_type_to_error_severity(self, py_ctx):
        stdout = json.dumps([
            {"type": "error", "message": "undefined name", "line": 5},
        ])
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _PylintAnalyzer().run(py_ctx)
        assert len(issues) == 1
        assert issues[0].severity == Severity.ERROR
        assert issues[0].tool == "pylint"
        assert issues[0].line == 5
        assert issues[0].category == Category.CODE_QUALITY

    def test_maps_fatal_type_to_error_severity(self, py_ctx):
        stdout = json.dumps([
            {"type": "fatal", "message": "fatal error", "line": 1},
        ])
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _PylintAnalyzer().run(py_ctx)
        assert issues[0].severity == Severity.ERROR

    def test_maps_warning_type_to_warning_severity(self, py_ctx):
        stdout = json.dumps([
            {"type": "warning", "message": "unused var", "line": 3},
        ])
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _PylintAnalyzer().run(py_ctx)
        assert issues[0].severity == Severity.WARNING

    def test_maps_convention_type_to_warning_severity(self, py_ctx):
        """convention/refactor/info 등 비-error 타입은 모두 WARNING."""
        stdout = json.dumps([
            {"type": "convention", "message": "naming", "line": 1},
        ])
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _PylintAnalyzer().run(py_ctx)
        assert issues[0].severity == Severity.WARNING

    def test_non_json_stdout_raises_so_the_run_is_marked_incomplete(self, py_ctx):
        """🔴 구 테스트는 이 입력에 `issues == []` 를 단언했다 — 결함을 정답으로 못박았다.

        docstring 은 「pylint banner」라고 했지만 `--output-format=json` 에서 pylint 는
        배너를 내지 않는다. 실측: **정상이면 clean 도 JSON 배열**(exit 16/20 은 메시지
        범주 비트이지 실패가 아니다), **크래시면 stdout 빈값 + exit 32**. 즉 JSON 이
        아닌 stdout 은 언제나 *실패* 다.

        `[]` 를 돌려주면 `static.py` 가 `incomplete` 로 승격하지 못해 미분석 코드가
        만점을 받고 auto-merge 된다.

        The old assertion certified a crash as a clean run; pylint never emits a banner in
        JSON mode, so non-JSON stdout always means failure.
        """
        with patch("subprocess.run", return_value=_mock_proc("Your code rated 10.00/10", 32)):
            with pytest.raises(RuntimeError, match="pylint"):
                _PylintAnalyzer().run(py_ctx)

    def test_empty_stdout_raises(self, py_ctx):
        """🔴 pylint 는 clean 파일에도 `[]` 를 출력한다 — **빈 출력은 clean 이 아니다**.

        실측: crash 시에만 stdout 이 빈다(exit 32). flake8 과 정반대라 같은 판별식을
        쓸 수 없다(flake8 은 빈 출력이 정당한 clean).
        """
        with patch("subprocess.run", return_value=_mock_proc("", 32)):
            with pytest.raises(RuntimeError, match="pylint"):
                _PylintAnalyzer().run(py_ctx)

    def test_propagates_language_field(self, py_ctx):
        stdout = json.dumps([{"type": "warning", "message": "x", "line": 1}])
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _PylintAnalyzer().run(py_ctx)
        assert issues[0].language == "python"


class TestPylintRunGracefulDegradation:
    """예외 상황 graceful fallback 검증."""

    def test_timeout_returns_empty_list(self, py_ctx, caplog):
        import logging
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="pylint", timeout=30),
        ):
            with caplog.at_level(logging.WARNING):
                issues = _PylintAnalyzer().run(py_ctx)
        assert issues == []
        assert any("pylint timed out" in r.message for r in caplog.records)

    def test_file_not_found_returns_empty(self, py_ctx):
        """pylint 미설치 시 FileNotFoundError → []."""
        with patch("subprocess.run", side_effect=FileNotFoundError("pylint not installed")):
            issues = _PylintAnalyzer().run(py_ctx)
        assert issues == []

    def test_broken_json_raises(self, py_ctx):
        """🔴 `[` 로 시작하지만 파싱이 깨진 출력 = 도구가 온전한 결과를 못 냈다.

        구 테스트는 `[]` 를 단언해 그 상태를 «이슈 없음» 으로 고정했다. 파싱 실패는
        이슈를 통째로 잃는다는 뜻이므로, 삼키면 그만큼 점수가 부풀려진다.
        eslint 어댑터가 같은 입력에 `RuntimeError` 를 올리는 것과 대칭이다.
        """
        with patch("subprocess.run", return_value=_mock_proc("[broken json", 32)):
            with pytest.raises(RuntimeError, match="pylint"):
                _PylintAnalyzer().run(py_ctx)


# ──────────────────────────────────────────────────────────────────────────
# _Flake8Analyzer
# ──────────────────────────────────────────────────────────────────────────


class TestFlake8AnalyzerAttributes:
    def test_name_is_flake8(self):
        assert _Flake8Analyzer().name == "flake8"

    def test_category_is_code_quality(self):
        assert _Flake8Analyzer().category == Category.CODE_QUALITY


class TestFlake8Supports:
    def test_supports_python(self, py_ctx):
        assert _Flake8Analyzer().supports(py_ctx) is True

    def test_rejects_javascript(self, js_ctx):
        assert _Flake8Analyzer().supports(js_ctx) is False


class TestFlake8IsEnabled:
    def test_always_enabled(self, py_ctx, py_test_ctx):
        assert _Flake8Analyzer().is_enabled(py_ctx) is True
        assert _Flake8Analyzer().is_enabled(py_test_ctx) is True


class TestFlake8RunSubprocessCall:
    def test_includes_flake8_binary(self, py_ctx):
        with patch("subprocess.run", return_value=_mock_proc("")) as mock_run:
            _Flake8Analyzer().run(py_ctx)
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "flake8"

    def test_includes_max_line_length(self, py_ctx):
        with patch("subprocess.run", return_value=_mock_proc("")) as mock_run:
            _Flake8Analyzer().run(py_ctx)
        cmd = mock_run.call_args.args[0]
        assert "--max-line-length=120" in cmd

    def test_test_file_adds_ignore_flag(self, py_test_ctx):
        """is_test=True → --ignore=E302,E402,... 추가."""
        with patch("subprocess.run", return_value=_mock_proc("")) as mock_run:
            _Flake8Analyzer().run(py_test_ctx)
        cmd = mock_run.call_args.args[0]
        ignore_args = [a for a in cmd if a.startswith("--ignore=")]
        assert ignore_args
        assert "F401" in ignore_args[0]


class TestFlake8RunOutputParsing:
    def test_parses_row_col_text_format(self, py_ctx):
        stdout = "10:5: E501 line too long\n3:1: F401 unused import\n"
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _Flake8Analyzer().run(py_ctx)
        assert len(issues) == 2
        assert issues[0].line == 10
        assert "E501" in issues[0].message
        assert issues[1].line == 3
        assert all(i.severity == Severity.WARNING for i in issues)

    def test_skips_malformed_lines(self, py_ctx):
        """parts.split(':',2) 결과 길이 != 3 → continue (skip)."""
        stdout = "totally invalid line\n5:2: valid issue\n"
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _Flake8Analyzer().run(py_ctx)
        assert len(issues) == 1
        assert issues[0].line == 5

    def test_skips_value_error_on_int_parse(self, py_ctx):
        """int(parts[0]) 실패 시 continue."""
        stdout = "abc:def: not a number\n7:3: valid\n"
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _Flake8Analyzer().run(py_ctx)
        assert len(issues) == 1
        assert issues[0].line == 7

    def test_returns_empty_for_empty_stdout(self, py_ctx):
        with patch("subprocess.run", return_value=_mock_proc("")):
            issues = _Flake8Analyzer().run(py_ctx)
        assert issues == []


class TestFlake8RunGracefulDegradation:
    def test_timeout_returns_empty(self, py_ctx, caplog):
        import logging
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="flake8", timeout=30),
        ):
            with caplog.at_level(logging.WARNING):
                issues = _Flake8Analyzer().run(py_ctx)
        assert issues == []
        assert any("flake8 timed out" in r.message for r in caplog.records)

    def test_file_not_found_returns_empty(self, py_ctx):
        with patch("subprocess.run", side_effect=FileNotFoundError("flake8 not installed")):
            issues = _Flake8Analyzer().run(py_ctx)
        assert issues == []


# ──────────────────────────────────────────────────────────────────────────
# _BanditAnalyzer
# ──────────────────────────────────────────────────────────────────────────


class TestBanditAnalyzerAttributes:
    def test_name_is_bandit(self):
        assert _BanditAnalyzer().name == "bandit"

    def test_category_is_security(self):
        assert _BanditAnalyzer().category == Category.SECURITY


class TestBanditSupports:
    def test_supports_python(self, py_ctx):
        assert _BanditAnalyzer().supports(py_ctx) is True

    def test_rejects_javascript(self, js_ctx):
        assert _BanditAnalyzer().supports(js_ctx) is False


class TestBanditIsEnabled:
    """bandit 은 테스트 파일 제외 (프로덕션 코드만) — 그 축은 `supports` 다.

    🔴 `is_enabled` 는 **바이너리만** 본다. 정책 제외를 거기 두면 `static.py` 가 그것을
    「조달된 도구 부재」로 읽어 모든 테스트 파일을 배포 회귀로 승격한다(실제로 났다).
    """

    def test_supports_prod_files(self, py_ctx):
        assert _BanditAnalyzer().supports(py_ctx) is True

    def test_does_not_support_test_files(self, py_test_ctx):
        assert _BanditAnalyzer().supports(py_test_ctx) is False

    def test_is_enabled_ignores_file_kind(self, py_ctx, py_test_ctx):
        """바이너리 축은 파일 종류에 반응하지 않는다 — 반응하면 축이 섞인 것이다."""
        bandit = _BanditAnalyzer()
        assert bandit.is_enabled(py_ctx) == bandit.is_enabled(py_test_ctx)


class TestBanditRunSubprocessCall:
    def test_includes_bandit_binary_and_json_format(self, py_ctx):
        stdout = json.dumps({"results": []})
        with patch("subprocess.run", return_value=_mock_proc(stdout)) as mock_run:
            _BanditAnalyzer().run(py_ctx)
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "bandit"
        assert "-f" in cmd
        assert "json" in cmd
        assert "/tmp/example.py" in cmd


class TestBanditRunOutputParsing:
    def test_maps_high_severity_to_error(self, py_ctx):
        stdout = json.dumps({"results": [
            {
                "issue_severity": "HIGH",
                "issue_text": "use of subprocess shell=True",
                "line_number": 12,
            },
        ]})
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _BanditAnalyzer().run(py_ctx)
        assert len(issues) == 1
        assert issues[0].severity == Severity.ERROR
        assert issues[0].tool == "bandit"
        assert issues[0].line == 12
        assert issues[0].category == Category.SECURITY

    def test_maps_low_severity_to_warning(self, py_ctx):
        stdout = json.dumps({"results": [
            {"issue_severity": "LOW", "issue_text": "weak rng", "line_number": 5},
        ]})
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _BanditAnalyzer().run(py_ctx)
        assert issues[0].severity == Severity.WARNING

    def test_maps_medium_severity_to_warning(self, py_ctx):
        stdout = json.dumps({"results": [
            {"issue_severity": "MEDIUM", "issue_text": "x", "line_number": 1},
        ]})
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _BanditAnalyzer().run(py_ctx)
        assert issues[0].severity == Severity.WARNING

    def test_returns_empty_when_results_key_missing(self, py_ctx):
        """results 키 없는 정상 JSON → 빈 list (graceful)."""
        stdout = json.dumps({"errors": [], "metrics": {}})
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _BanditAnalyzer().run(py_ctx)
        assert issues == []

    def test_non_json_stdout_raises(self, py_ctx):
        """🔴 bandit 은 clean 파일에도 JSON 객체를 낸다(`{"results": []}`).

        실측: crash 시 stdout 빈값 + exit 2. usage 텍스트가 왔다는 것은 분석을 못 했다는
        뜻이므로 `[]` 로 삼키면 «보안 이슈 0건» 이 되어 만점이 나간다.
        """
        with patch("subprocess.run", return_value=_mock_proc("bandit usage info", 2)):
            with pytest.raises(RuntimeError, match="bandit"):
                _BanditAnalyzer().run(py_ctx)


class TestBanditRunGracefulDegradation:
    def test_timeout_returns_empty(self, py_ctx, caplog):
        import logging
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="bandit", timeout=30),
        ):
            with caplog.at_level(logging.WARNING):
                issues = _BanditAnalyzer().run(py_ctx)
        assert issues == []
        assert any("bandit timed out" in r.message for r in caplog.records)

    def test_file_not_found_returns_empty(self, py_ctx):
        with patch("subprocess.run", side_effect=FileNotFoundError("bandit not installed")):
            issues = _BanditAnalyzer().run(py_ctx)
        assert issues == []

    def test_broken_json_raises(self, py_ctx):
        """🔴 파싱 실패를 삼키면 보안 이슈가 통째로 사라진 채 «0건» 이 된다 (pylint 대칭)."""
        with patch("subprocess.run", return_value=_mock_proc("{broken json", 2)):
            with pytest.raises(RuntimeError, match="bandit"):
                _BanditAnalyzer().run(py_ctx)


# ──────────────────────────────────────────────────────────────────────────
# C10 — 키 누락 JSON item 방어 (KeyError fail-open 차단)
# C10 — defensive parsing of key-missing JSON items (block KeyError fail-open)
# ──────────────────────────────────────────────────────────────────────────


class TestC10DefensiveParsing:
    """도구가 키 누락 JSON 을 내도 KeyError 로 analyzer 전체가 중단(이슈 전량 무음 폐기)되지 않아야 한다."""

    def test_pylint_missing_message_key_does_not_crash(self, py_ctx):
        # "message" 키 누락 — 이전엔 KeyError → 전량 폐기(fail-open). 이제 빈 message 로 이슈 보존.
        payload = '[{"type": "warning", "line": 5}]'
        with patch("subprocess.run", return_value=_mock_proc(payload)):
            issues = _PylintAnalyzer().run(py_ctx)
        assert len(issues) == 1               # 이슈 보존 (무음 폐기 X)
        assert issues[0].message == ""
        assert issues[0].line == 5
        assert issues[0].severity == Severity.WARNING

    def test_pylint_missing_type_and_line_defaults(self, py_ctx):
        payload = '[{"message": "bad"}]'
        with patch("subprocess.run", return_value=_mock_proc(payload)):
            issues = _PylintAnalyzer().run(py_ctx)
        assert len(issues) == 1
        assert issues[0].severity == Severity.WARNING  # type 누락 → WARNING
        assert issues[0].line == 0

    def test_bandit_missing_issue_text_key_does_not_crash(self, py_ctx):
        payload = '{"results": [{"issue_severity": "HIGH", "line_number": 3}]}'
        with patch("subprocess.run", return_value=_mock_proc(payload)):
            issues = _BanditAnalyzer().run(py_ctx)
        assert len(issues) == 1               # 이슈 보존
        assert issues[0].message == ""
        assert issues[0].line == 3
        assert issues[0].severity == Severity.ERROR  # HIGH 보존

    def test_bandit_missing_severity_and_line_keys_does_not_crash(self, py_ctx):
        # issue_severity·line_number 둘 다 누락 — 직접 subscript 재도입 시 KeyError 회귀 봉인.
        payload = '{"results": [{"issue_text": "found"}]}'
        with patch("subprocess.run", return_value=_mock_proc(payload)):
            issues = _BanditAnalyzer().run(py_ctx)
        assert len(issues) == 1
        assert issues[0].message == "found"
        assert issues[0].line == 0                       # line_number 누락 → 0
        assert issues[0].severity == Severity.WARNING    # issue_severity 누락 → 비-HIGH → WARNING

    def test_bandit_none_severity_does_not_crash(self, py_ctx):
        # issue_severity=None — str() 래핑이 .upper() AttributeError 를 방지하는지 봉인.
        payload = '{"results": [{"issue_severity": null, "issue_text": "x", "line_number": 2}]}'
        with patch("subprocess.run", return_value=_mock_proc(payload)):
            issues = _BanditAnalyzer().run(py_ctx)
        assert len(issues) == 1
        assert issues[0].severity == Severity.WARNING

    def test_pylint_none_message_and_line_values_safe(self, py_ctx):
        # message/line 값이 None — `or` 폴백이 None 을 ""/0 으로 정규화하는지 봉인.
        payload = '[{"type": "warning", "message": null, "line": null}]'
        with patch("subprocess.run", return_value=_mock_proc(payload)):
            issues = _PylintAnalyzer().run(py_ctx)
        assert len(issues) == 1
        assert issues[0].message == ""
        assert issues[0].line == 0

    def test_bandit_none_text_and_line_values_safe(self, py_ctx):
        payload = '{"results": [{"issue_severity": "HIGH", "issue_text": null, "line_number": null}]}'
        with patch("subprocess.run", return_value=_mock_proc(payload)):
            issues = _BanditAnalyzer().run(py_ctx)
        assert len(issues) == 1
        assert issues[0].message == ""
        assert issues[0].line == 0
        assert issues[0].severity == Severity.ERROR


# ─── 🔴 과교정 방지 — 세 도구의 «정상» 은 서로 다르다 ────────────────────────
#
# fail-closed 를 한 판별식으로 몰면 반드시 어느 하나가 깨진다. 핀 버전 실측:
#
#   pylint  clean → JSON 배열 `[]` · exit 16   (exit 는 메시지 범주 비트, 실패 아님)
#   bandit  clean → JSON 객체      · exit 0
#   flake8  clean → **빈 출력**    · exit 0    ← 여기에 JSON 판별식을 쓰면 정상 파일이
#                                                 전부 incomplete 가 되어 auto-merge 전면 차단
#
# 아래는 «고쳤더니 정상이 막혔다» 를 막는 축이다.

class TestFailClosedDoesNotBlockCleanRuns:
    """정상 실행을 실패로 오인하지 않는가."""

    def test_pylint_clean_file_is_not_a_failure(self, py_ctx):
        """clean 이어도 pylint 는 `[]` 를 낸다 — exit 16 은 실패가 아니다."""
        with patch("subprocess.run", return_value=_mock_proc("[]", 16)):
            assert _PylintAnalyzer().run(py_ctx) == []

    def test_bandit_clean_file_is_not_a_failure(self, py_ctx):
        """clean 이어도 bandit 은 JSON 객체를 낸다."""
        with patch("subprocess.run", return_value=_mock_proc('{"results": []}', 0)):
            assert _BanditAnalyzer().run(py_ctx) == []

    def test_flake8_clean_file_is_not_a_failure(self, py_ctx):
        """🔴 flake8 만 **빈 출력이 정당한 clean** 이다(exit 0). 여기서 raise 하면
        모든 정상 Python 파일이 차단된다."""
        with patch("subprocess.run", return_value=_mock_proc("", 0)):
            assert _Flake8Analyzer().run(py_ctx) == []

    def test_flake8_crash_still_raises(self, py_ctx):
        """대조축 — 같은 «빈 출력» 이라도 비정상 종료면 실패다(tsc 규칙).

        이 축이 없으면 flake8 은 fail-open 인 채로 남는다 — 빈 출력이 clean 이라는
        이유로 크래시까지 통과시키게 된다.
        """
        proc = _mock_proc("", 2)
        proc.stderr = "flake8: error: unrecognized arguments"
        with patch("subprocess.run", return_value=proc):
            with pytest.raises(RuntimeError, match="flake8"):
                _Flake8Analyzer().run(py_ctx)

    def test_pylint_findings_survive_a_nonzero_exit(self, py_ctx):
        """대조축 — pylint 는 이슈를 찾으면 exit 20 이다. 종료코드로 판정하면 결과를 버린다."""
        stdout = json.dumps([{"type": "error", "message": "boom", "line": 3}])
        with patch("subprocess.run", return_value=_mock_proc(stdout, 20)):
            assert len(_PylintAnalyzer().run(py_ctx)) == 1
