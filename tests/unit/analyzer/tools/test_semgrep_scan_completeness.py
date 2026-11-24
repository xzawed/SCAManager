"""semgrep 이 대상을 훑지 않은 실행 · 규칙이 끝까지 못 돈 실행은 «완전» 이 아니다 (회고 원장 R-8).

`test_semgrep.py` 는 이 모듈을 `import` 와 `from … import` 두 형태로 이미 부른다 — 새 import 줄은 어느 쪽이든
CodeQL `py/import-and-import-from` 를 자초하므로(`scripts/check_dual_import.py`) 이 파일로 따로 둔다.
A run in which semgrep did not scan the target, or a rule did not finish, is not complete. Kept in its own file so
no new import line joins the two import forms test_semgrep.py already uses.
"""
import json
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:test")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123456")

from unittest.mock import MagicMock, patch  # noqa: E402

import pytest  # noqa: E402


def _mock_semgrep_proc(stdout: str, returncode: int = 0) -> MagicMock:
    """subprocess.run 반환값을 모방한다. / Mimic a subprocess.run result."""
    mock = MagicMock()
    mock.stdout = stdout
    mock.stderr = ""
    mock.returncode = returncode
    return mock


@pytest.fixture
def make_ctx():
    """언어 · 파일명 · 임시 경로를 받아 AnalyzeContext 를 만든다. / AnalyzeContext factory."""
    from src.analyzer.pure.registry import AnalyzeContext

    def _factory(language: str, filename: str = "test_file.py", tmp_path: str = "/tmp/test_file.py"):
        return AnalyzeContext(filename=filename, content="some content", language=language,
                              is_test=False, tmp_path=tmp_path)
    return _factory


# ── 대상을 훑지 않은 실행 · 규칙별 시간 초과 (회고 원장 R-8 — semgrep 1.184.0 실측 payload) ─────────
# A run that did not scan the target, or in which a rule timed out, is not an analysis.

_TARGET = "/tmp/test_file.py"


def _semgrep_json(results=(), errors=(), scanned=(_TARGET,)) -> str:
    """어댑터가 받는 `--json` 출력 — `scanned=None` 이면 `paths` 를 뺀다. / The adapter's --json input."""
    body = {"results": list(results), "errors": list(errors)}
    if scanned is not None:
        body["paths"] = {"scanned": list(scanned)}
    return json.dumps(body)


# 실측 — 같은 이미지에서 `--timeout 1` 로 규칙 시간 초과를 일으킨 출력의 errors 한 항목(이름 · 경로만 바꿈)
# Measured with --timeout 1 on the production image; only the rule id prefix and path are changed.
_RULE_TIMEOUT = {"code": 2, "level": "warn", "type": "Timeout",
                 "rule_id": "python_exec_rule-subprocess-popen-shell-true",
                 "message": f"Timeout when running python_exec_rule-subprocess-popen-shell-true on {_TARGET}",
                 "path": _TARGET}
_PARTIAL_PARSING = {"code": 3, "level": "warn", "type": ["PartialParsing", []],
                    "message": f"Syntax error at line {_TARGET}:7"}
_ONE_FINDING = {"check_id": "python_exec_rule-subprocess-popen-shell-true", "start": {"line": 4},
                "extra": {"severity": "ERROR", "message": "shell=True", "metadata": {"category": "security"}}}

# (원래 이름, 언어). semgrep 이 받는 임시 파일은 제품 함수 `static.py::temp_suffix` 로 짓는다(실측 1.184.0).
# (original name, language); the temp file semgrep receives is named by the product's own temp_suffix.
_UNTARGETED = (("build.sc", "scala"), ("deploy", "javascript"), ("deploy.", "javascript"))
# witness-corpus: (name, language) pairs whose temp file semgrep scans (measured, 1.184.0)
_TARGETED = (("app.py", "python"), ("stub.pyi", "python"), ("app.mjs", "javascript"),
             ("build.gradle.kts", "kotlin"), ("Main.scala", "scala"), ("deploy", "python"))


def _routed_ctx(make_ctx, filename: str, language: str):
    """static.py 와 같은 임시 파일 이름으로 ctx 를 만든다. / A ctx whose tmp_path is named like static.py names it."""
    from src.analyzer.io.static import temp_suffix
    return make_ctx(language, filename, tmp_path=f"/tmp/x/analyze{temp_suffix(filename, language)}")


@pytest.mark.parametrize(("filename", "language"), _UNTARGETED)
def test_supports_skips_files_semgrep_never_targets(make_ctx, filename, language):
    """🔴 semgrep 이 처음부터 대상으로 삼지 않는 임시 파일(scala 스크립트 `.sc` · 확장자 없는 node shebang 스크립트의 `.tmp`)은
    돌리지 않는다. 실측 1.184.0: 둘 다 `paths.scanned` 가 비고 errors 도 없이 종료 0 — 돌리면 «이슈 0건 · 완전» 이 된다.
    """
    from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
    assert _SemgrepAnalyzer().supports(_routed_ctx(make_ctx, filename, language)) is False


@pytest.mark.parametrize(("filename", "language"), _TARGETED)
def test_supports_keeps_files_semgrep_scans(make_ctx, filename, language):
    """대조군 — semgrep 이 실제로 훑는 임시 파일은 그대로 돌린다. 🔴 확장자 없는 python shebang 스크립트(`deploy`)도 임시 파일은
    `.py` 라 훑는다 — 원래 이름으로 판정하면 이 파일에서 semgrep 을 잃는다(자동 보안 리뷰 지적)."""
    from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
    assert _SemgrepAnalyzer().supports(_routed_ctx(make_ctx, filename, language)) is True


def test_run_raises_when_target_was_not_scanned(make_ctx):
    """🔴 종료 0 · errors 0 이어도 `paths.scanned` 가 비면 semgrep 이 대상을 훑지 않은 것이다 — 미분석(R-8).

    우리는 파일 하나만 넘기므로 «비었다» = «안 훑었다» 다. 그대로 두면 «이슈 0건 · 완전» 과 구별할 수 없다.
    """
    from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
    with patch("subprocess.run", return_value=_mock_semgrep_proc(_semgrep_json(scanned=()))):
        with pytest.raises(RuntimeError, match="did not analyze"):
            _SemgrepAnalyzer().run(make_ctx("python", "app.py", tmp_path=_TARGET))


def test_run_raises_when_scanned_paths_are_missing(make_ctx):
    """🔴 못 재면 red — `paths.scanned` 가 없으면 훑었는지 알 수 없다(1.184.0 은 늘 싣는다)."""
    from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
    with patch("subprocess.run", return_value=_mock_semgrep_proc(_semgrep_json(scanned=None))):
        with pytest.raises(RuntimeError, match="did not analyze"):
            _SemgrepAnalyzer().run(make_ctx("python", "app.py", tmp_path=_TARGET))


def _semgrep_did_not_finish_names() -> set[str] | None:
    """조달된 semgrep 이 «규칙이 끝까지 못 돎» 에 내는 JSON 이름 — 못 재면 None.

    🔴 앱 venv 에는 semgrep 이 없다(#1857 — 자기 venv). 그래서 CI 는 조달된 semgrep venv 의 python 이 뽑은 파일
       (`SEMGREP_RULE_DID_NOT_FINISH_JSON` — ci.yml «semgrep 스키마 이름 뽑기» 스텝)로 잰다. 로컬은 import 할 수 있을 때만.
    The procured semgrep's names, dumped from its own venv in CI; locally only when importable.
    """
    dumped = os.environ.get("SEMGREP_RULE_DID_NOT_FINISH_JSON")
    if dumped:
        with open(dumped, encoding="utf-8") as fh:  # 없으면 예외 — CI 에서 덤프가 빠진 것은 red 다
            return set(json.load(fh))
    try:
        from semgrep.semgrep_interfaces import semgrep_output_v1 as schema  # pylint: disable=import-outside-toplevel
    except ImportError:
        return None
    kinds = (schema.Timeout, schema.OutOfMemory, schema.StackOverflow, schema.FixpointTimeout, schema.MatchingError)
    return {kind.to_json() for kind in kinds}


def test_rule_did_not_finish_kinds_match_semgreps_own_schema():
    """🔴 «규칙이 끝까지 못 돎» 목록은 조달된 semgrep 의 출력 스키마가 내는 JSON 이름과 같다 — 이름이 바뀌면 여기서 red.

    #1857 뒤 이 시험은 CI 에서 «semgrep import 불가» 로 영구 skip 이었고, 판올림 두 번(1.185.0 · 1.186.0)을 한 번도
    재지 않았다(원장 #1917 M06 P2-36 · P2-38). 이제 CI 는 조달된 venv 의 덤프로 재고, 그 측정이 빠지면 skip 이 아니라 red 다.
    The list equals the JSON names the procured semgrep's output schema emits; in CI a missing measurement is red.
    """
    names = _semgrep_did_not_finish_names()
    if names is None:
        if os.environ.get("CI"):
            pytest.fail("CI 에서 semgrep 스키마 이름을 못 쟀다 — ci.yml «semgrep 스키마 이름 뽑기» 덤프가 빠졌다")
        pytest.skip("semgrep 이 이 환경에 없다(앱 venv 밖 · #1857) — CI 는 조달된 semgrep venv 의 덤프로 잰다")
    from src.analyzer.io.tools.semgrep import _RULE_DID_NOT_FINISH
    assert _RULE_DID_NOT_FINISH == names


@pytest.mark.parametrize("kind", ["Timeout", "Out of memory", "Stack overflow", "Fixpoint timeout",
                                  "Internal matching error"])
def test_run_raises_when_a_rule_did_not_finish(make_ctx, kind):
    """🔴 규칙이 이 파일에서 끝까지 못 돌았다 — 끝난 규칙의 결과가 있어도 미분석.

    실측(`Timeout`, --timeout 1): 종료 0 · errors 에 위 꼴 · 결과는 끝난 규칙 것만. 지금 상수(규칙 30 s · 실행 상한 30 s)
    에서는 실행 상한이 먼저 끊어 `timed_out` 이 되지만, 둘 중 하나가 바뀌면 이 꼴이 그대로 닿는다.
    """
    from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
    payload = _semgrep_json(results=[_ONE_FINDING], errors=[dict(_RULE_TIMEOUT, type=kind)])
    with patch("subprocess.run", return_value=_mock_semgrep_proc(payload)):
        with pytest.raises(RuntimeError, match="did not analyze"):
            _SemgrepAnalyzer().run(make_ctx("python", "app.py", tmp_path=_TARGET))


@pytest.mark.parametrize("error", [_PARTIAL_PARSING, dict(_PARTIAL_PARSING, type="Syntax error")],
                         ids=["partial-parsing", "syntax-error"])
def test_parse_warnings_still_count_as_scanned(make_ctx, error):
    """대조군 — 파싱 꼴(`PartialParsing` · `Syntax error`)은 훑은 것이다. 실측: 유효한 Python 3.14 t-string 도 부분 파싱
    경고를 내지만 semgrep 은 나머지를 훑어 결과를 낸다 — 이것까지 미분석으로 올리면 새 문법 파일마다 auto-merge 가 막힌다."""
    from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
    payload = _semgrep_json(results=[_ONE_FINDING], errors=[error])
    with patch("subprocess.run", return_value=_mock_semgrep_proc(payload)):
        issues = _SemgrepAnalyzer().run(make_ctx("python", "app.py", tmp_path=_TARGET))
    assert [i.message for i in issues] == ["shell=True"]
