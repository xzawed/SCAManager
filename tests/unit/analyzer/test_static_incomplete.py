"""정적분석 도구 subprocess 타임아웃 → incomplete 전파 테스트 (Task9 P1 #7).
Static analysis tool subprocess-timeout → incomplete propagation tests (Task9 P1 #7).

도구가 타임아웃 시 빈 목록을 '무음' 반환하면 미분석 카테고리(특히 security)가 만점으로
인플레이션되어 auto-merge fail-open 이 된다. analyze_file 이 StaticAnalysisResult.incomplete 로
이를 신호하면 _run_static_with_timeout → static_analysis_incomplete 마커 → 게이트 차단.
"""
import shutil
import subprocess
from unittest.mock import patch

import pytest

from src.analyzer.io.static import StaticAnalysisResult, analyze_file


def test_static_result_incomplete_defaults_false():
    """StaticAnalysisResult.incomplete 기본값은 False (회귀 가드 — 기존 생성부 무영향)."""
    assert StaticAnalysisResult(filename="a.py").incomplete is False


def test_analyze_file_marks_incomplete_on_subprocess_timeout():
    """도구 subprocess 타임아웃 시 StaticAnalysisResult.incomplete=True 여야 한다 (#7 fail-closed).

    빈 이슈 목록을 무음 반환하면 만점 인플레로 이어지므로, 타임아웃을 incomplete 로 신호해
    auto-merge/auto-approve 가 미분석 코드를 자동 처리하지 못하게 한다.
    """
    code = "import os\nx = 1\n"  # python → pylint/flake8/bandit 적용
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="pylint", timeout=30)):
        result = analyze_file("app.py", code)
    assert result.incomplete is True


def test_analyze_file_not_incomplete_on_normal_run():
    """타임아웃이 없으면 incomplete=False 여야 한다 (회귀 가드, #7).

    비-코드 파일(README.md)은 분석기가 적용되지 않아 subprocess 호출도 없다 → incomplete False.
    """
    result = analyze_file("README.md", "# hello\n")
    assert result.incomplete is False


def test_analyze_file_marks_incomplete_on_analyzer_crash():
    """감사 ④ (옵션 B): 분석기 run()이 예상외 예외로 crash 하면 incomplete=True (fail-closed).

    이전엔 static.py 의 broad except 가 crash 를 로깅만 하고 삼켜 — 미분석 코드가 만점 인플레로
    auto-merge 되는 fail-open 이었다(타임아웃만 fail-closed 인 비대칭). 도구가 내부에서 못 잡는
    예외(RuntimeError 등)는 incomplete 로 승격해 게이트가 차단한다.
    """
    code = "import os\nx = 1\n"  # python → pylint/flake8/bandit 적용
    # subprocess.run 이 도구 내부 except 가 못 잡는 예외(RuntimeError)를 던지면 run() 밖으로 전파됨
    with patch("subprocess.run", side_effect=RuntimeError("boom")):
        result = analyze_file("app.py", code)
    assert result.incomplete is True


def test_analyze_file_not_incomplete_on_missing_tool():
    """감사 ④ (옵션 B 경계): 도구 미설치(FileNotFoundError)는 incomplete 아님 — 현행 유지.

    미설치는 도구 내부 `except (..., FileNotFoundError)` 가 잡아 빈 목록을 반환하므로
    static.py 의 broad except 에 도달하지 않는다 → incomplete=False (의도적 미설치 = opt-out).
    이 경계를 명문화해 옵션 B(crash→incomplete, 미설치→현행) 회귀를 차단한다.
    """
    code = "import os\nx = 1\n"
    with patch("subprocess.run", side_effect=FileNotFoundError("pylint")):
        result = analyze_file("app.py", code)
    assert result.incomplete is False


# ──────────────────────────────────────────────────────────────────────────────
# 🔴 조달 계약으로 갈라친 차단 (backlog R21, 사용자 결정 2026-08-01 — 옵션 C)
#
# 이전: `unavailable_tools` 가 있으면 **무조건** incomplete → 배포 이미지가 애초에 설치하지
#       않는 도구의 언어(rust·dart·C#·php·powershell·css/scss·swift·protobuf·html)는
#       auto-merge 가 **영구 불가**였다. 손댈 수 없는 이유로 막히는 것은 게이트가 아니라 벽이다.
# 이제: 조달 계약(`PROVISIONED_ANALYZERS`) 안 도구가 사라지면 = **실제 배포 회귀** → 차단 유지.
#       계약 밖 도구 부재 = **제품 미제공** → `uncovered_language` 로 가시화만.
#
# 🔴 여기서 보는 것은 **행동**이다. 계약 목록끼리 대조하는 테스트
# (`test_procurement_contract.py`)만으로는 게이트가 실제로 어떻게 판정하는지 알 수 없다.
# ──────────────────────────────────────────────────────────────────────────────

def _force_absent(monkeypatch, absent_names):
    """지정 분석기만 '바이너리 없음' 으로 만든다 — 나머지는 그대로.

    `is_enabled` 를 이름 기준으로 갈아끼워 `unavailable_tools` 경로를 실제로 태운다
    (합성 결과 객체를 만들지 않는다 — 불변식 2).

    🔴 **`shutil.which` 도 함께 갈아끼운다** (2026-08-17 CI 실측으로 추가).
    `is_enabled` 만 조작하면 «바이너리 부재» 축은 **실행 환경에 맡겨진다**:
    개발 PC(Windows)에는 shellcheck 이 없어 통과했지만, CI 러너에는 설치돼 있어
    `_binary_is_absent` 가 False 를 내며 두 테스트가 red 였다.
    헬퍼 이름이 «바이너리 없음» 이면 그 사실을 **테스트가 만들어야** 한다 —
    환경이 우연히 만들어 주기를 기대하면 그 초록은 머신마다 다른 것을 잰다.
    Also stub `shutil.which`: patching `is_enabled` alone leaves the binary-absence axis to
    the host, so the same test measured different things on the dev PC and on CI.
    """
    from src.analyzer.pure.registry import REGISTRY

    for analyzer in REGISTRY:
        if analyzer.name in absent_names:
            monkeypatch.setattr(
                type(analyzer), "is_enabled", lambda self, ctx: False, raising=False
            )

    absent = set(absent_names)
    monkeypatch.setattr(
        "src.analyzer.io.static.shutil.which",
        lambda name: None if name in absent else f"/usr/bin/{name}",
    )


def test_unprovisioned_tool_absence_surfaces_without_blocking(monkeypatch):
    """🔴 계약 밖 도구만 부재 → 차단하지 않고 미커버로 표면화한다.

    이 단언이 깨지면 R21 이 재발한 것이다 — 해당 언어 리포의 auto-merge 가 영구 차단된다.
    """
    from src.analyzer.io.static import PROVISIONED_ANALYZERS, analyze_file

    assert "stylelint" not in PROVISIONED_ANALYZERS, "전제 붕괴 — stylelint 는 미조달이어야 한다"
    _force_absent(monkeypatch, {"stylelint"})

    result = analyze_file("theme.css", "a { color: red }\n")
    assert result.incomplete is False, (
        "미조달 도구 부재로 차단됐다 — auto-merge 영구 불가(R21 재발)"
    )
    assert result.uncovered_language == "css", "차단하지 않는 대신 가시화는 해야 한다"


def test_provisioned_tool_absence_still_blocks(monkeypatch):
    """🔴 대칭 — 조달 계약 안 도구가 사라지면 **실제 배포 회귀**이므로 계속 차단한다.

    이 단언이 없으면 위 완화가 fail-open 이 된다: 배포 사고로 shellcheck 가 사라져도
    조용히 만점 + auto-merge 통과.
    """
    from src.analyzer.io.static import PROVISIONED_ANALYZERS, analyze_file

    assert "shellcheck" in PROVISIONED_ANALYZERS, "전제 붕괴 — shellcheck 는 조달 대상이어야 한다"
    # 🔴 `.sh` 는 semgrep 도 지원한다. 승격 분기는 **실행 0개**일 때만 도는 설계라
    #    (semgrep 이 커버하는 언어의 과차단 방지) 둘 다 없애야 이 축을 실제로 태운다.
    #    실측으로 확인 후 좁혔다 — 처음엔 shellcheck 만 없애고 "차단 안 됨" 을 결함으로 오독했다.
    # Both must be absent: the promotion branch only runs when ZERO analyzers ran.
    _force_absent(monkeypatch, {"shellcheck", "semgrep"})

    result = analyze_file("deploy.sh", "#!/bin/sh\necho hi\n")
    assert result.incomplete is True, (
        "조달된 도구가 사라졌는데 차단하지 않았다 — 배포 회귀가 무음으로 통과한다"
    )
    assert "shellcheck" in result.unavailable_tools


def test_provisioned_tool_absence_blocks_even_when_another_analyzer_ran(monkeypatch):
    """🔴 조달된 도구가 사라지면 **다른 도구가 돌았어도** 차단한다.

    ## 이것이 왜 별도 축인가 — 위 테스트는 이 결함을 보지 못한다

    바로 위 `test_provisioned_tool_absence_still_blocks` 는 semgrep 까지 함께 없애
    `ran == 0` 을 만든 뒤에야 차단을 확인한다. 그 테스트의 주석은 그 조정을
    *"처음엔 shellcheck 만 없애고 «차단 안 됨» 을 결함으로 오독했다"* 라고 적었다 —
    **오독이 아니라 실제 결함이었다.** 테스트가 코드에 맞춰 굽은 것이다.

    ## 실측된 운영 연쇄 (2026-08-16 재검증)

    `railway.toml` 의 조달은 `|| echo WARNING` 으로 실패를 삼킨다. rubocop·golangci-lint·
    slither 가 빠져도 semgrep 은 `requirements.txt` 로 항상 설치되고
    `SUPPORTED_LANGUAGES` 에 ruby·go·solidity 가 **모두** 있다. 따라서 `ran >= 1` 이 되어
    승격 분기 자체가 돌지 않고, `incomplete` 가 서지 않아
    `src/gate/actions/auto_merge.py` 의 차단이 발동하지 않는다 →
    **Ruby·Go·Solidity PR 이 전용 분석기 0회 실행으로 정적 만점을 받고 auto-merge 에 도달한다.**

    `PROVISIONED_ANALYZERS` 의 docstring 은 스스로
    *"a listed tool going missing is a deployment regression (block)"* 이라 적는다.
    이 테스트는 코드가 그 계약을 실제로 이행하는지 잰다.
    A provisioned tool going missing must block regardless of what else ran.
    """
    from src.analyzer.io.static import PROVISIONED_ANALYZERS, analyze_file

    assert "shellcheck" in PROVISIONED_ANALYZERS, "전제 붕괴 — shellcheck 는 조달 대상이어야 한다"
    # 🔴 semgrep 은 **없애지 않는다** — 그것이 이 축의 전부다.
    _force_absent(monkeypatch, {"shellcheck"})

    result = analyze_file("deploy.sh", "#!/bin/sh\necho hi\n")

    assert "shellcheck" in result.unavailable_tools, (
        "전제 붕괴 — shellcheck 가 unavailable_tools 에 기록되지 않았다"
    )
    assert result.incomplete is True, (
        "조달된 shellcheck 가 사라졌는데 semgrep 이 돌았다는 이유로 통과했다 — "
        "배포 회귀가 무음으로 정적 만점을 받고 auto-merge 에 도달한다"
    )


class _OptOutConfig:
    """`disabled_tools` 만 가진 최소 stub (`test_static_disabled.py` 와 같은 관용구)."""

    def __init__(self, disabled):
        self.disabled_tools = list(disabled)


def test_operator_opt_out_suppresses_the_provisioned_regression_promotion(monkeypatch):
    """🔴 운영자가 명시적으로 끈 상태면 조달 회귀 승격도 하지 않는다.

    `is_enabled()` 는 «바이너리 부재» 와 «이 파일엔 해당 없음» 을 구별하지 않는다.
    운영자가 `disabled_tools` 로 도구를 껐는데 그것을 «배포 회귀» 로 되돌려주면
    **자기 설정이 결함으로 보고**된다 — 원래 승격 분기가 `opted_out == 0` 을 요구한
    이유(Grok claim-review P1)와 같은 축이고, `ran` 게이트를 푼 뒤에도 유지돼야 한다.

    이 단언이 없으면 `opted_out` 조건을 지워도 초록이다(뮤테이션 H 생존 실측).
    The operator's own opt-out must never be reported back as a deployment regression.
    """
    from src.analyzer.io.static import PROVISIONED_ANALYZERS, analyze_file

    assert "shellcheck" in PROVISIONED_ANALYZERS
    assert "semgrep" in PROVISIONED_ANALYZERS
    _force_absent(monkeypatch, {"shellcheck"})

    # semgrep 을 운영자가 끈다 → opted_out >= 1. shellcheck 은 부재(조달 회귀 후보).
    result = analyze_file(
        "deploy.sh", "#!/bin/sh\necho hi\n", repo_config=_OptOutConfig(["semgrep"])
    )

    assert "shellcheck" in result.unavailable_tools, "전제 붕괴 — 부재 기록이 없다"
    assert result.incomplete is False, (
        "운영자가 도구를 끈 상태인데 조달 회귀로 승격했다 — 자기 설정이 결함으로 보고된다"
    )


# ──────────────────────────────────────────────────────────────────────────────
# 🔴 2026-08-17 운영 회귀 — `is_enabled()` False 의 두 원인을 갈라야 한다
#
# `#1410` 이 조달 회귀 승격을 `ran == 0` 게이트 밖으로 꺼내면서, `is_enabled()` 가
# **정책상 미적용**으로 False 를 내는 도구까지 «배포 회귀» 로 읽었다. bandit 이 정확히
# 그 경우다 — `_BanditAnalyzer.is_enabled` 는 `not ctx.is_test` 이고 bandit 은
# `PROVISIONED_ANALYZERS` 안에 있다. 결과: **모든 Python 테스트 파일이 incomplete**.
# 실측: analyze_file("tests/unit/test_foo.py", …) → unavailable=['bandit'] incomplete=True
# ──────────────────────────────────────────────────────────────────────────────


def test_policy_disabled_provisioned_tool_does_not_block(monkeypatch):
    """🔴 bandit 이 테스트 파일에서 꺼지는 것은 **배포 회귀가 아니다**.

    이 단언이 없으면 테스트 파일을 건드리는 모든 PR 의 auto-merge 가 막힌다 —
    조달은 멀쩡한데 게이트만 닫히는, 이 리포가 R21 에서 겪은 «벽» 의 재발이다.
    A policy-gated tool (bandit on tests) must not read as a deployment regression.
    """
    from src.analyzer.io.static import PROVISIONED_ANALYZERS, analyze_file

    assert "bandit" in PROVISIONED_ANALYZERS, "전제 붕괴 — bandit 은 조달 대상이어야 한다"
    # 🔴 bandit 바이너리는 **있다고 본다** — 이 리포의 requirements.txt 가 설치한다.
    monkeypatch.setattr("src.analyzer.io.static.shutil.which", lambda _n: "/usr/bin/" + _n)

    result = analyze_file("tests/unit/test_foo.py", "def test_x():\n    assert True\n")

    # 🔴 이제 bandit 은 `unavailable_tools` 에 **들어가지 않는다** — 테스트 파일 제외가
    #    `is_enabled`(바이너리 축)에서 `supports`(대상 축)로 옮겨졌기 때문이다.
    #    이전 판은 여기 들어온 뒤 `_binary_is_absent` 로 걸러졌고, 그 방어는 **우연**이었다:
    #    바이너리가 실제로 사라진 순간 정책 제외와 조달 회귀가 구별 불가가 된다.
    # bandit no longer lands in `unavailable_tools`: the test-file exclusion moved to `supports`.
    assert "bandit" not in result.unavailable_tools, (
        "테스트 파일에서 bandit 이 `unavailable_tools` 에 들어갔다 — 정책 제외가 "
        "`supports` 가 아니라 바이너리 축에 남아 있다"
    )
    assert result.incomplete is False, (
        "정책상 미적용(테스트 파일의 bandit)을 배포 회귀로 승격했다 — "
        "테스트를 건드리는 모든 PR 의 auto-merge 가 막힌다"
    )


def test_binary_absence_still_blocks_when_which_returns_none(monkeypatch):
    """대칭 — 바이너리가 **정말로** 없으면 여전히 차단한다.

    위 완화가 조달 회귀 축까지 꺼버리면 `#1410` 이 되돌려진다.
    """
    from src.analyzer.io.static import PROVISIONED_ANALYZERS, analyze_file

    assert "shellcheck" in PROVISIONED_ANALYZERS
    _force_absent(monkeypatch, {"shellcheck"})
    # `which` 가 None → 진짜 부재
    monkeypatch.setattr("src.analyzer.io.static.shutil.which", lambda _n: None)

    result = analyze_file("deploy.sh", "#!/bin/sh\necho hi\n")

    assert "shellcheck" in result.unavailable_tools
    assert result.incomplete is True, (
        "바이너리가 실제로 없는데 차단하지 않았다 — #1410 이 되돌려졌다"
    )


# ── 조달 계약이 파이썬 3종(pylint·flake8·bandit)에 도달하는가 ──────────────
#
# 🔴 세 어댑터는 `is_enabled` 가 `return True`(pylint·flake8) / `not ctx.is_test`(bandit) 라
#    **바이너리를 관측하지 않았다**. 그래서 부재해도 `unavailable_tools` 에 들어가지 않고
#    조달 회귀 승격이 원리적으로 도달하지 못했다 — 파이썬 파일은 분석기가 사라져도
#    「깨끗함」 만점을 받고 auto-merge 됐다. 나머지 13종은 전부 `shutil.which` 를 본다.
# The three Python adapters never observed their binaries, so the provisioned-regression
# promotion could not reach them: a Python file scored clean with zero analyzers.


@pytest.mark.parametrize("tool", ["pylint", "flake8", "bandit"])
def test_python_tool_absence_promotes_to_incomplete(tool, monkeypatch):
    """🔴 조달된 파이썬 도구가 없으면 `incomplete` — 만점 auto-merge 를 막는다."""
    from src.analyzer.io.static import PROVISIONED_ANALYZERS, analyze_file

    assert tool in PROVISIONED_ANALYZERS, f"{tool} 이 조달 계약에서 빠졌다 — 이 테스트가 공허하다"

    real = shutil.which
    monkeypatch.setattr(
        "shutil.which", lambda n, *a, **k: None if n == tool else real(n, *a, **k)
    )

    result = analyze_file("src/app.py", "x=1\n")

    assert tool in result.unavailable_tools, (
        f"{tool} 바이너리가 없는데 `unavailable_tools` 에 들어가지 않았다 — "
        "`is_enabled` 가 바이너리를 관측하지 않는다(승격이 도달 불가)"
    )
    assert result.incomplete is True, (
        f"{tool} 부재가 `incomplete` 로 승격되지 않았다 — 파이썬 파일이 분석기 없이 "
        "만점을 받고 auto-merge 된다"
    )


def test_bandit_policy_exclusion_lives_in_supports_not_is_enabled():
    """🔴 「테스트 파일엔 bandit 미적용」은 `supports` 축이다 — `is_enabled` 로 두면 회귀한다.

    `is_enabled=False` 는 **바이너리 부재**를 뜻하고, bandit 은 조달 계약 안이라
    모든 테스트 파일이 배포 회귀로 승격된다(그 회귀가 실제로 났다).
    """
    from src.analyzer.io.tools.python import _BanditAnalyzer
    from src.analyzer.pure.registry import AnalyzeContext

    bandit = _BanditAnalyzer()
    test_ctx = AnalyzeContext(
        filename="tests/unit/test_foo.py", content="", tmp_path="", language="python", is_test=True,
    )
    prod_ctx = AnalyzeContext(
        filename="src/app.py", content="", tmp_path="", language="python", is_test=False,
    )

    assert bandit.supports(test_ctx) is False, (
        "테스트 파일 제외가 `supports` 에 없다 — `is_enabled` 로 두면 조달 회귀로 오승격된다"
    )
    assert bandit.supports(prod_ctx) is True

    # `is_enabled` 는 **오직** 바이너리만 본다 — 파일 종류에 반응하면 축이 섞인 것이다.
    assert bandit.is_enabled(test_ctx) == bandit.is_enabled(prod_ctx), (
        "`is_enabled` 가 파일 종류에 따라 갈린다 — 바이너리 관측 축에 정책이 섞였다"
    )
