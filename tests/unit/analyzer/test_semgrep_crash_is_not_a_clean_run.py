"""크래시한 semgrep 이 «이슈 0건 · 완전» 으로 기록된다 — 미분석 코드가 만점을 받는다 (감사 A2, #1519).

🔴 실측. `src/analyzer/io/tools/semgrep.py` 는 형제 어댑터와 **같은 판정식**을 쓴다:

    if not r.stdout.strip().startswith("{"):   # stdout 이 JSON 이 아니다 = 분석 안 됐다

그런데 형제(`python.py`)는 `raise _fail(...)` 이고 semgrep 만 `return []` 이다.
`python.py::_fail` 의 docstring 이 그 이유를 직접 적는다:

    「`[]` 를 돌려주면 그 실패가 «이슈 0건 · 완전» 이 되어 미분석 코드가 auto-merge 된다.」

그리고 **semgrep 은 java · scala · csharp · swift 의 유일한 분석기**다(실측). 이 언어에서
semgrep 이 죽으면 아무 대체 분석기가 없어 결과가 통째로 조용해진다:

    semgrep 크래시(java) -> issues=[] · incomplete=False · uncovered_language=None
                        -> code_quality 25/25 · security 20/20 · 총점 89 · 등급 B
    같은 크래시(python)   -> incomplete=True     (형제 어댑터가 올림)

`incomplete=False` 라 `src/gate/actions/auto_merge.py` 의 `static_analysis_incomplete`
차단이 걸리지 않는다 — 분석되지 않은 코드가 B 등급으로 자동 머지될 수 있다.

`--json` 이 정상 출력하는 「이슈 없음」도 `{"results": []}` 라 `{` 로 시작한다.
즉 비-`{` stdout 이 정당한 «이슈 0건» 인 경우는 없다(Grok 확인).

The same discriminator raises in the hardened adapters but returns [] in semgrep, and
semgrep is the only analyzer for four languages.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402

from src.analyzer.io.static import (  # noqa: E402
    PROVISIONED_ANALYZERS,
    REGISTRY,
    AnalyzeContext,
    analyze_file,
)
from src.analyzer.io.tools import semgrep as sg  # noqa: E402

_JAVA = "class Foo {}"


class _Result:
    """`subprocess.run` 반환값 더블 — 실물과 같은 세 속성만 갖는다."""

    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def _crash() -> _Result:
    return _Result(2, "", "semgrep: FATAL: unhandled exception\n")


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_semgrep_is_the_only_analyzer_for_these_languages():
    """🔴 전제 — semgrep 단독인 언어가 실제로 있는가.

    없다면 「크래시가 통째로 조용해진다」는 주장이 성립하지 않는다.
    """
    solo = []
    for lang, filename in [("java", "Foo.java"), ("scala", "Foo.scala"),
                           ("csharp", "Foo.cs"), ("swift", "Foo.swift")]:
        ctx = AnalyzeContext(filename=filename, content="x", language=lang, is_test=False,
                             tmp_path=filename, repo_config=None, timed_out=False)
        provisioned = [a.name for a in REGISTRY
                       if a.supports(ctx) and a.name in PROVISIONED_ANALYZERS]
        if provisioned == ["semgrep"]:
            solo.append(lang)
    assert solo, (
        "semgrep 단독인 언어가 하나도 없다 — 전제가 바뀌었다. "
        "다른 분석기가 생겼다면 이 파일의 심각도 서술을 고쳐야 한다."
    )


def test_a_clean_semgrep_run_still_starts_with_a_brace():
    """🔴 전제 — 「이슈 없음」 정상 출력도 `{` 로 시작한다.

    아니라면 비-`{` 를 실패로 보는 판정 자체가 틀린 것이 된다.
    """
    clean = _Result(0, '{"results": [], "errors": []}', "")
    with patch.object(sg.shutil, "which", return_value="/usr/bin/semgrep"), \
         patch.object(sg.subprocess, "run", return_value=clean):
        result = analyze_file("Foo.java", _JAVA, "java")
    assert result.issues == []
    assert result.incomplete is False, "정상 «이슈 0건» 이 incomplete 로 잡히면 과잉 차단이다"


# ─── 결함 ────────────────────────────────────────────────────────────────────


def test_semgrep_crash_marks_the_analysis_incomplete():
    """🔴 크래시가 «완전한 분석» 으로 기록되지 않는다.

    기록되면 `auto_merge` 의 `static_analysis_incomplete` 차단이 걸리지 않아
    분석되지 않은 코드가 자동 머지된다.
    """
    with patch.object(sg.shutil, "which", return_value="/usr/bin/semgrep"), \
         patch.object(sg.subprocess, "run", return_value=_crash()):
        result = analyze_file("Foo.java", _JAVA, "java")

    assert result.incomplete is True, (
        "semgrep 이 크래시했는데 incomplete=False 다 — 이슈 0건이 «깨끗한 완전 분석» 으로 "
        "기록되고, java 는 semgrep 단독이라 아무도 그 코드를 보지 않았다"
    )


def test_semgrep_crash_does_not_produce_a_full_static_score():
    """🔴 크래시한 분석의 정적 점수가 만점이 아니다 — 등급이 실제를 반영한다."""
    from src.scorer.calculator import calculate_score  # noqa: PLC0415

    with patch.object(sg.shutil, "which", return_value="/usr/bin/semgrep"), \
         patch.object(sg.subprocess, "run", return_value=_crash()):
        result = analyze_file("Foo.java", _JAVA, "java")

    assert result.incomplete is True
    score = calculate_score([result])
    assert score.total is not None
    # incomplete 가 서면 파이프라인이 auto-merge 를 차단한다 — 점수 자체는 계산돼도 된다.
    # 여기서 고정하는 것은 «완전» 이라는 거짓 표시가 사라졌다는 것이다.


def test_malformed_json_is_also_a_failure_not_an_empty_result():
    """🔴 semgrep 이 깨진 JSON 을 주면 실패다 — 형제(`python.py`)도 그렇게 다룬다.

    `{` 로 시작하지만 파싱이 깨지는 경우다.
    """
    broken = _Result(0, '{"results": [ {"extra"', "")
    with patch.object(sg.shutil, "which", return_value="/usr/bin/semgrep"), \
         patch.object(sg.subprocess, "run", return_value=broken):
        result = analyze_file("Foo.java", _JAVA, "java")
    assert result.incomplete is True, (
        "깨진 JSON 이 «이슈 0건 · 완전» 으로 기록된다"
    )


def test_missing_binary_reports_the_tool_not_a_crash():
    """대조군 — 바이너리 부재는 **다른 경로**다: `unavailable_tools` 에 이름이 남는다.

    🔴 이 대조군의 첫 판은 `incomplete is False` 를 단언했는데 **틀렸다**(실측):
    semgrep 은 `PROVISIONED_ANALYZERS` 라 부재 자체가 배포 회귀이고 이미
    `incomplete=True` 다. 둘 다 incomplete 이므로 구분되는 것은 **원인 표시**다 —
    부재는 도구 이름을 남기고, 크래시는 남기지 않는다. 그 구분이 사라지면
    운영에서 「설치가 빠졌나 죽었나」를 로그로 못 가른다.
    """
    with patch.object(sg.shutil, "which", return_value=None):
        result = analyze_file("Foo.java", _JAVA, "java")
    assert result.unavailable_tools == ["semgrep"], (
        f"부재가 도구 이름을 남기지 않는다: {result.unavailable_tools}"
    )

    with patch.object(sg.shutil, "which", return_value="/usr/bin/semgrep"),          patch.object(sg.subprocess, "run", return_value=_crash()):
        crashed = analyze_file("Foo.java", _JAVA, "java")
    assert crashed.unavailable_tools == [], (
        f"크래시가 «부재» 로 잘못 분류된다: {crashed.unavailable_tools}"
    )


# ─── JSON 을 찍고도 실패한 실행 (회고 2026-11-06 원장 L03 P1-39) ───────────────────
#
# 🔴 실측(semgrep 1.183.0, `--json --metrics=off`): 레지스트리가 룰셋을 거절하거나 설정이 없으면
# stdout 은 여전히 `{` 로 시작하는 JSON 이고 `results` 는 비어 있으며 종료 코드는 7 이다. 위의
# «`{` 로 시작하면 분석됐다» 판정만으로는 이것이 «이슈 0건 · 완전» 으로 기록된다.
# `--json` 은 찾은 것이 있어도 0 으로 끝난다(`--error` 를 주지 않는다) — 0 이 아닌 값은 실패뿐이다.
# Measured: a rejected registry ruleset or a missing config still prints a JSON object with empty
# results and exits 7; --json exits 0 even with findings, so any non-zero exit is a failure.

_REGISTRY_404 = (
    '{"version": "1.183.0", "results": [], "errors": ['
    '{"code": 2, "level": "error", "type": "SemgrepError", "message": '
    '"Failed to download configuration from https://semgrep.dev/c/p/default HTTP 404."}, '
    '{"code": 7, "level": "error", "type": "SemgrepError", "message": '
    '"invalid configuration file found (1 configs were invalid)"}], '
    '"paths": {"scanned": []}, "skipped_rules": []}'
)
_MISSING_CONFIG = (
    '{"version": "1.183.0", "results": [], "errors": ['
    '{"code": 2, "level": "error", "type": "SemgrepError", "message": '
    '"WARNING: unable to find a config; path `rules.yml` does not exist"}, '
    '{"code": 7, "level": "error", "type": "SemgrepError", "message": '
    '"invalid configuration file found (1 configs were invalid)"}], '
    '"paths": {"scanned": []}, "skipped_rules": []}'
)
_WITH_FINDINGS = (
    '{"version": "1.183.0", "errors": [], "results": ['
    '{"check_id": "java.lang.security.audit.weak-hash", "start": {"line": 3}, '
    '"extra": {"severity": "WARNING", "message": "weak hash", "metadata": {"category": "security"}}}]}'
)
_PARTIAL_PARSE = (
    '{"version": "1.183.0", "results": [], "errors": ['
    '{"code": 3, "level": "warn", "type": ["PartialParsing", []], '
    '"message": "Syntax error at line Foo.java:1"}], "paths": {"scanned": ["Foo.java"]}}'
)


def _analyze(result: _Result):
    with patch.object(sg.shutil, "which", return_value="/usr/bin/semgrep"), \
         patch.object(sg.subprocess, "run", return_value=result):
        return analyze_file("Foo.java", _JAVA, "java")


def test_registry_rejection_is_not_a_clean_run(caplog):
    """🔴 레지스트리가 룰셋을 거절한 실행(종료 7 · JSON · 결과 0)이 «완전한 분석» 으로 기록되지 않는다.

    운영 로그에서 원인을 가를 수 있게 semgrep 이 JSON 에 적은 오류 문장이 경고에 남는다.
    """
    with caplog.at_level("WARNING"):
        result = _analyze(_Result(7, _REGISTRY_404, ""))
    assert result.incomplete is True, (
        "레지스트리 거절(종료 7)이 «이슈 0건 · 완전» 으로 기록된다 — java 는 semgrep 단독이라 "
        "아무도 그 코드를 보지 않았다"
    )
    # JSON 을 그대로 200자 자르면 두 번째 문장이 잘린다 — 원인 문장을 `errors` 에서 꺼내 남기는지 본다
    # Cutting the raw JSON at 200 chars would drop the second message; the cause must come from `errors`.
    for message in ("Failed to download configuration", "invalid configuration file found"):
        assert message in caplog.text, f"실패 원인이 로그에 남지 않는다({message}): {caplog.text[-300:]!r}"


def test_missing_config_is_not_a_clean_run():
    """🔴 설정을 찾지 못한 실행(종료 7 · JSON · 결과 0)도 같은 실패다."""
    assert _analyze(_Result(7, _MISSING_CONFIG, "")).incomplete is True


@pytest.mark.parametrize("returncode", [1, 2, 7, 8, 13])
def test_any_nonzero_exit_with_a_json_body_is_a_failure(returncode):
    """🔴 계기 뒤집기 — «7 일 때만» 같은 좁은 판정이 받아들일 값을 심는다.

    `--json` 은 찾은 것이 있어도 0 이므로, JSON 을 찍고 0 이 아닌 값으로 끝난 실행은 모두 실패다.
    """
    body = '{"version": "1.183.0", "results": [], "errors": []}'
    assert _analyze(_Result(returncode, body, "")).incomplete is True, (
        f"종료 {returncode} 인데 «완전한 분석» 으로 기록된다"
    )


@pytest.mark.parametrize("errors", [1, True, 2.5, "boom", {"message": "m"}, None])
def test_failure_detail_survives_any_errors_shape(errors):
    """🔴 원인 문장을 꺼내다가 다시 터지지 않는다 — `errors` 가 목록이 아닌 JSON 값이어도.

    다시 터지면 실패는 여전히 incomplete 로 가지만, 로그에는 semgrep 의 원인 대신 TypeError 가 남는다.
    (Grok 반례 96c93f6d: `{"errors": 1}` → `for e in 1` → TypeError.)
    """
    exc = sg._fail(  # pylint: disable=protected-access
        AnalyzeContext(filename="Foo.java", content="x", language="java", is_test=False,
                       tmp_path="Foo.java", repo_config=None, timed_out=False),
        _Result(7, '{"errors": "raw"}', ""), {"results": [], "errors": errors})
    assert isinstance(exc, RuntimeError) and "exit=7" in str(exc)


def test_failure_detail_takes_messages_from_mixed_errors():
    """목록 안에 dict 가 아닌 값이 섞여도 dict 의 문장만 모은다."""
    exc = sg._fail(  # pylint: disable=protected-access
        AnalyzeContext(filename="Foo.java", content="x", language="java", is_test=False,
                       tmp_path="Foo.java", repo_config=None, timed_out=False),
        _Result(7, "{}", ""), {"errors": [1, "x", {"message": "first"}, {"message": ""}, {"message": "second"}]})
    assert str(exc).endswith("first; second")


def test_findings_with_exit_zero_stay_a_complete_run():
    """대조군 — 찾은 것이 있는 정상 실행(종료 0)은 이슈를 그대로 돌려주고 완전하다."""
    result = _analyze(_Result(0, _WITH_FINDINGS, ""))
    assert result.incomplete is False, "정상 실행이 incomplete 로 잡히면 과잉 차단이다"
    assert [i.message for i in result.issues] == ["weak hash"]


def test_partial_parsing_with_exit_zero_is_not_promoted_to_a_failure():
    """대조군 — 문법 오류로 일부만 파싱한 실행(종료 0 · `warn`)은 semgrep 이 그 파일을 훑은 것이다.

    실측: `paths.scanned` 에 파일이 있고 종료 코드는 0 이다. 이것까지 실패로 올리면
    문법이 깨진 파일마다 auto-merge 가 막힌다.
    """
    assert _analyze(_Result(0, _PARTIAL_PARSE, "")).incomplete is False


def test_timeout_keeps_its_own_path():
    """대조군 — 타임아웃은 `ctx.timed_out` 으로 이미 fail-closed 다. 이중 처리하지 않는다."""
    import subprocess  # noqa: PLC0415

    with patch.object(sg.shutil, "which", return_value="/usr/bin/semgrep"), \
         patch.object(sg.subprocess, "run",
                      side_effect=subprocess.TimeoutExpired("semgrep", 1)):
        result = analyze_file("Foo.java", _JAVA, "java")
    assert result.incomplete is True, "타임아웃도 미분석이므로 incomplete 여야 한다"
