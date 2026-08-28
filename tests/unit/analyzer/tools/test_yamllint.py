"""yamllint YAML 분석기 테스트.
yamllint YAML analyzer tests.
"""
import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from src.analyzer.pure.registry import AnalyzeContext, Severity, REGISTRY


def _make_ctx(language: str, filename: str) -> AnalyzeContext:
    return AnalyzeContext(
        filename=filename, content="", language=language,
        is_test=False, tmp_path=f"/tmp/{filename}",
    )


_YAMLLINT_JSON = json.dumps([
    {"line": 3, "column": 1, "level": "error",
     "message": "wrong indentation: expected 2 but found 4", "rule": "indentation"},
    {"line": 10, "column": 5, "level": "warning",
     "message": "too many spaces before colon", "rule": "colons"},
])


def _mock_proc(stdout: str = "", returncode: int = 1):
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


class TestYamllintAnalyzer:
    def test_supports_yaml(self):
        # yaml 언어는 supports()가 True를 반환해야 한다
        # supports() must return True for yaml language
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer
        assert _YamllintAnalyzer().supports(_make_ctx("yaml", "config.yaml"))

    def test_does_not_support_python(self):
        # python 언어는 supports()가 False를 반환해야 한다
        # supports() must return False for python language
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer
        assert not _YamllintAnalyzer().supports(_make_ctx("python", "app.py"))

    def test_is_enabled_when_installed(self):
        # yamllint 바이너리가 있으면 is_enabled()는 True를 반환한다
        # is_enabled() must return True when yamllint binary is present
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer
        ctx = _make_ctx("yaml", "config.yaml")
        with patch("shutil.which", return_value="/usr/bin/yamllint"):
            assert _YamllintAnalyzer().is_enabled(ctx) is True

    def test_is_enabled_false_when_missing(self):
        # yamllint 바이너리가 없으면 is_enabled()는 False를 반환한다
        # is_enabled() must return False when yamllint binary is absent
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer
        ctx = _make_ctx("yaml", "config.yaml")
        with patch("shutil.which", return_value=None):
            assert _YamllintAnalyzer().is_enabled(ctx) is False

    def test_json_output_is_not_a_contract_this_tool_can_honour(self):
        """🔴 구 테스트(`test_parses_json_output`)를 이것으로 **대체**했다.

        그 테스트는 yamllint 가 JSON 배열을 준다고 가정하고 파싱을 단언했다. 그런데
        `requirements.txt` 가 핀한 1.38.0 은 `-f json` 자체를 모른다 —
        선택지는 `{parsable,standard,colored,github,auto}` 뿐이다. 즉 그 테스트는
        **일어날 수 없는 입력**에 대한 단언이었고, 실제 운영에서 어댑터는 매번 exit 2 로
        죽으면서 그 실패를 «이슈 0건» 으로 보고하고 있었다.

        존재하지 않는 계약을 초록으로 지키는 테스트는 결함을 정답으로 못박는다. 지금은
        JSON 이 들어오면 **파서 계약 위반으로 raise** 하는 것이 옳다.

        The old test asserted parsing of a JSON shape the pinned yamllint cannot emit,
        certifying an impossible contract while the adapter failed on every real call.
        """
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer

        with patch("subprocess.run", return_value=_mock_proc(_YAMLLINT_JSON, 1)):
            with pytest.raises(RuntimeError, match="unparseable"):
                _YamllintAnalyzer().run(_make_ctx("yaml", "config.yaml"))

    def test_returns_empty_on_timeout(self):
        # subprocess TimeoutExpired 시 빈 목록을 반환해야 한다
        # Must return empty list on subprocess TimeoutExpired
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer
        ctx = _make_ctx("yaml", "config.yaml")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("yamllint", 30)):
            with patch("shutil.which", return_value="/usr/bin/yamllint"):
                assert _YamllintAnalyzer().run(ctx) == []

    def test_returns_empty_on_empty_output(self):
        # 빈 stdout은 빈 이슈 목록을 반환해야 한다
        # Empty stdout must return an empty issue list
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer
        ctx = _make_ctx("yaml", "config.yaml")
        with patch("subprocess.run", return_value=_mock_proc("", 0)):
            issues = _YamllintAnalyzer().run(ctx)
        assert issues == []

    def test_module_registers_yamllint(self):
        # 모듈 임포트 시 REGISTRY에 yamllint가 자동 등록된다
        # Module import must auto-register yamllint in REGISTRY
        import importlib
        # 🔴 string-path 로 부른다 — 같은 모듈을 `import X` 와 `from X import` 로
        #    함께 참조하면 CodeQL py/import-and-import-from 을 자초한다
        #    (testing.md 「모듈 패치 시 이중 import 회피 — string-path 우선」).
        # String-path avoids mixing `import X` with `from X import` in one module.
        mod = importlib.import_module("src.analyzer.io.tools.yamllint")
        importlib.reload(mod)
        names = [a.name for a in REGISTRY]
        assert "yamllint" in names


# ─── 🔴 이 어댑터는 운영에서 한 번도 YAML 을 분석한 적이 없다 ──────────────────
#
# `requirements.txt` 가 핀한 yamllint 1.38.0 의 `-f` 는
# `{parsable,standard,colored,github,auto}` 뿐이다 — **`json` 이 없다.**
# 어댑터는 그것을 넘기고 있었다(이 커밋 이전).
#
# 실측(1.38.0, 같은 YAML):
#     -f json      → exit 2 · stdout 빈값 · usage 에러
#     -f parsable  → exit 1 · 이슈 6건
#     analyze_file → 이슈 0건 · incomplete=False        ← "깨끗" 으로 집계
#
# 즉 계약 분석기가 매번 죽는데 그 실패가 «문제 없음» 으로 기록된다. 아래 축들은
# (a) 지원되는 포맷을 쓰는가, (b) 실패를 fail-closed 로 올리는가, (c) 진짜 clean 을
# 실패로 오인하지 않는가 — 셋을 함께 고정한다.
#
# The pinned yamllint has no `json` formatter; the adapter has therefore always failed
# and every failure was recorded as "no problems".

_PARSABLE_OUT = (
    "/tmp/c.yaml:3:1: [error] wrong indentation: expected 2 but found 4 (indentation)\n"
    "/tmp/c.yaml:10:5: [warning] too many spaces before colon (colons)\n"
)


class TestYamllintActuallyRuns:
    """어댑터가 실제로 분석을 수행하는가."""

    def test_uses_a_format_the_pinned_yamllint_supports(self):
        """🔴 `-f json` 은 1.38.0 에 없다 — 쓰면 매번 usage 에러로 죽는다."""
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer

        with patch("subprocess.run", return_value=_mock_proc(_PARSABLE_OUT, 1)) as run:
            _YamllintAnalyzer().run(_make_ctx("yaml", "c.yaml"))

        argv = run.call_args[0][0]
        assert "-f" in argv, f"포맷 지정이 없다: {argv}"
        fmt = argv[argv.index("-f") + 1]
        # 🔴 «지원 목록 중 하나» 로 느슨하게 두면 안 된다 — `standard` 도 그 목록에
        #    있지만 파서가 읽는 형식이 아니라 매 줄이 파싱 실패로 raise 된다.
        #    파서와 짝인 포맷 하나로 못박는다 (Grok claim-review 01a02d7a).
        # Not «one of the supported set»: `standard` is supported but the parser cannot
        # read it, so every line would raise. Pin the one format the parser matches.
        assert fmt == "parsable", (
            f"포맷이 {fmt!r} 다 — 파서는 `-f parsable` 출력만 읽는다. "
            "`json` 은 1.38.0 에 아예 없어 매 호출이 exit 2 로 죽는다."
        )

    def test_parses_the_output_that_format_actually_produces(self):
        """포맷을 바꿨으면 파서도 그 출력을 읽어야 한다 — 아니면 여전히 0건이다."""
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer

        with patch("subprocess.run", return_value=_mock_proc(_PARSABLE_OUT, 1)):
            issues = _YamllintAnalyzer().run(_make_ctx("yaml", "c.yaml"))

        assert len(issues) == 2, f"parsable 출력 2줄을 못 읽었다: {issues}"
        assert issues[0].line == 3 and issues[0].severity == Severity.ERROR
        assert issues[1].line == 10 and issues[1].severity == Severity.WARNING
        assert "indentation" in issues[0].message

    def test_usage_error_is_raised_not_swallowed(self):
        """🔴 exit 2(usage/설정 오류) = 분석 못 함. `[]` 를 돌려주면 «깨끗» 이 된다.

        `static.py` 는 `run()` 이 **예외를 올릴 때만** `incomplete` 로 승격한다.
        """
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer

        proc = _mock_proc("", 2)
        proc.stderr = "usage: yamllint [-h] ... error: argument -f: invalid choice: 'json'"
        with patch("subprocess.run", return_value=proc):
            with pytest.raises(RuntimeError, match="yamllint"):
                _YamllintAnalyzer().run(_make_ctx("yaml", "c.yaml"))

    def test_clean_file_is_not_mistaken_for_a_failure(self):
        """대조축 — exit 0 + 빈 출력은 **진짜 깨끗**이다. 여기서 raise 하면 모든 정상
        YAML 이 incomplete 가 되어 auto-merge 가 전면 차단된다(과교정)."""
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer

        with patch("subprocess.run", return_value=_mock_proc("", 0)):
            assert _YamllintAnalyzer().run(_make_ctx("yaml", "c.yaml")) == []

    def test_problems_found_exit_code_is_not_a_failure(self):
        """대조축 — exit 1 은 «문제를 찾았다» 이지 «실패» 가 아니다."""
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer

        with patch("subprocess.run", return_value=_mock_proc(_PARSABLE_OUT, 1)):
            assert len(_YamllintAnalyzer().run(_make_ctx("yaml", "c.yaml"))) == 2

    def test_nonzero_exit_with_findings_is_not_a_failure(self):
        """🔴 종료코드만으로 판정하면 `--strict` 를 켜는 순간 정상 결과를 버린다.

        yamllint 1.38.0 `cli.py:245-252` — `--strict` 면 **warning 만 있어도 exit 2** 이고
        그때 결과는 정상 출력된다. 초판 판별식(`exit not in {0,1}` → raise)은 그 경우
        찾아낸 이슈를 통째로 버리고 `incomplete` 로 올려 **정상 PR 을 막았을 것**이다.
        (Grok claim-review `01a02d7a` 가 이 지뢰를 짚었다.)

        그래서 tsc 어댑터와 같은 규칙을 쓴다 — 먼저 파싱하고, **아무것도 못 읽었는데**
        비정상 종료일 때만 실패다.

        Exit code alone is not the signal: `--strict` exits 2 *with* valid findings.
        """
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer

        with patch("subprocess.run", return_value=_mock_proc(_PARSABLE_OUT, 2)):
            issues = _YamllintAnalyzer().run(_make_ctx("yaml", "c.yaml"))

        assert len(issues) == 2, "비정상 종료라고 정상 결과를 버렸다"

    def test_config_error_exit_code_also_raises(self):
        """대조축 — 설정 오류는 `-1`(255)로 끝난다. 2 만 특별취급하면 새는 경로다."""
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer

        proc = _mock_proc("", 255)
        proc.stderr = "invalid config: not a dict"
        with patch("subprocess.run", return_value=proc):
            with pytest.raises(RuntimeError, match="yamllint"):
                _YamllintAnalyzer().run(_make_ctx("yaml", "c.yaml"))


# ──────────────────────────────────────────────────────────────────────────────
# 스폰 축 fail-closed (#1557 W3)
#
# 🔴 `except OSError` 는 두 가지를 한 갈래로 보냈다: 「바이너리가 없다」(조달 축)와
#    「which() 를 통과했는데 실행이 실패했다」(미분석). 후자는 깨진 shebang·권한·TOCTOU 이고
#    분석이 **안 된** 것이므로 `[]` 로 돌려주면 그 침묵이 «이슈 0건 · 완전» 이 된다.
#    `FileNotFoundError` 로 좁히면 앞은 그대로 `[]`, 뒤는 올라가 `static.py` 가 incomplete 로 승격한다.
# A spawn failure after which() succeeded is unanalyzed, not "binary absent".
# ──────────────────────────────────────────────────────────────────────────────


class TestYamllintSpawnAxisFailClosed:
    def test_file_not_found_still_returns_empty(self):
        """대조군 — 바이너리 부재는 조달 축이다."""
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer
        ctx = _make_ctx("yaml", "config.yaml")
        with patch("subprocess.run", side_effect=FileNotFoundError("yamllint not found")):
            with patch("shutil.which", return_value="/usr/bin/yamllint"):
                assert _YamllintAnalyzer().run(ctx) == []

    @pytest.mark.parametrize("exc", [
        PermissionError("permission denied"),
        OSError(8, "Exec format error"),
    ], ids=["permission", "enoexec"])
    def test_spawn_failure_is_not_a_clean_run(self, exc):
        """🔴 which() 통과 후의 실행 실패는 미분석 — 올라가야 한다."""
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer
        ctx = _make_ctx("yaml", "config.yaml")
        with patch("subprocess.run", side_effect=exc):
            with patch("shutil.which", return_value="/usr/bin/yamllint"):
                with pytest.raises(OSError):
                    _YamllintAnalyzer().run(ctx)
