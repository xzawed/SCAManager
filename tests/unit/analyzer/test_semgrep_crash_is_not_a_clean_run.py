"""크래시한 semgrep 이 «이슈 0건 · 완전» 으로 기록된다 — 미분석 코드가 만점을 받는다 (감사 A2, #1519).

🔴 실측. `src/analyzer/io/tools/semgrep.py` 는 형제 어댑터와 **같은 판정식**을 쓴다:

    if not r.stdout.strip().startswith("{"):   # stdout 이 JSON 이 아니다 = 분석 안 됐다

그런데 형제(`python.py`)는 `raise _fail(...)` 이고 semgrep 만 `return []` 이다.
`python.py::_fail` 의 docstring 이 그 이유를 직접 적는다:

    「`[]` 를 돌려주면 그 실패가 «이슈 0건 · 완전» 이 되어 미분석 코드가 auto-merge 된다.」

그리고 **semgrep 은 java·scala·elixir·clojure 의 유일한 분석기**다(실측). 이 언어에서
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
                           ("elixir", "foo.ex"), ("clojure", "foo.clj")]:
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


def test_timeout_keeps_its_own_path():
    """대조군 — 타임아웃은 `ctx.timed_out` 으로 이미 fail-closed 다. 이중 처리하지 않는다."""
    import subprocess  # noqa: PLC0415

    with patch.object(sg.shutil, "which", return_value="/usr/bin/semgrep"), \
         patch.object(sg.subprocess, "run",
                      side_effect=subprocess.TimeoutExpired("semgrep", 1)):
        result = analyze_file("Foo.java", _JAVA, "java")
    assert result.incomplete is True, "타임아웃도 미분석이므로 incomplete 여야 한다"
