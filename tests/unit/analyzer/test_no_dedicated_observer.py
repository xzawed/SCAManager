"""전담 관측면이 하나도 돌지 않은 파일을 「완전」으로 기록하지 않는다.

## 사고 (실측 2026-08-29, 프로덕션 `supports()` 로 역인덱싱)

`PROVISIONED_ANALYZERS` 와 대조하면 **전담 분석기가 배포본에 하나도 없는 언어가 6개**다:

    rust     clippy 미조달        swift   swiftlint 미조달
    php      phpstan 미조달       csharp  전담 어댑터 없음 (#1565 로 지웠다)
    scala    전담 어댑터 없음      elixir  전담 어댑터 없음

이 언어들에서는 semgrep 하나만 돈다. 그런데 semgrep 의 규칙은 언어마다 편차가 크고
(자체 보고: elixir 0 · cpp 0 · swift 2 · rust 4), 취약 코드를 넣어도 이슈 0건이 나온다.
실측: `analyze_file("vuln.ex", <System.cmd 주입>)` → `issues=0 · tools=[]`.

`static.py::🔴 `ran > 0` 이면 승격하지 않는다` 는 「semgrep 이 커버하는 Rust·PHP·Swift」라고
적고 승격을 막는다. 그 문장은 **선언상 참이고 실효로 거짓**이다 — 커버는 되는데 못 본다.
결과가 「분석됨 · 이슈 0건 · 완전」이고 auto-merge 에 도달한다.

## 이 축이 하는 것

`uncovered_language`(지원 분석기 **0개**)와 `static_analysis_incomplete`(미분석) 사이의 빈칸을
메운다 — **지원은 되는데 전담 관측면이 하나도 안 돌았다.**

🔴 **차단하지 않는다.** `pipeline.md::- `static_uncovered_languages`` 가 정한 대로 가시화만
한다(점수 신뢰도 + 경고). 차단하면 조달 실패가 다시 벽이 되고, 그것은 #1568 이 닫으려는 것이다.

The gap between "no analyzer supports this language" and "an analyzer crashed": every dedicated
analyzer for this language was absent or disabled, so only the generic fallback ran.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("SESSION_SECRET", "0123456789abcdef0123456789abcdef")

import pytest  # noqa: E402

from src.analyzer.pure.registry import REGISTRY, AnalyzeContext  # noqa: E402


def _ctx(language: str, filename: str) -> AnalyzeContext:
    return AnalyzeContext(filename=filename, content="x", language=language,
                          is_test=False, tmp_path=f"/tmp/{filename}")  # nosec B108


# ── 범용 분석기는 정확히 하나다 (파생 판정) ──────────────────────────────


def test_exactly_one_generic_analyzer_is_declared():
    """🔴 「전담이 아니다」를 손으로 적은 목록이 아니라 **선언**으로 판정한다.

    이 수가 늘면 「전담 관측면」의 정의가 바뀐 것이므로 그 자리에서 red 가 된다.
    """
    # `src.analyzer.io.static` 을 임포트하면 어댑터가 전부 등록된다(그 모듈 상단의
    # side-effect import 들). 🔴 plain `import src…` 를 쓰지 않는다 — 이 파일이
    # `from src… import` 도 쓰므로 공존하면 CodeQL py/import-and-import-from 을
    # 자초한다(`scripts/check_dual_import.py`). `# noqa: F401` 로 가리는 것도 막힌다
    # (`scripts/check_noqa_sideeffect.py`). string-path 가 두 가드를 모두 통과하는 형태다.
    import importlib  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    assert importlib.import_module("src.analyzer.io.static").PROVISIONED_ANALYZERS, "등록 전제 붕괴"
    generic = sorted(a.name for a in REGISTRY if getattr(a, "is_generic", False))
    assert generic == ["semgrep"], (
        f"범용 분석기 선언이 {generic} — 전담 관측면 판정의 전제가 바뀌었다"
    )


# ── 축 판정 ──────────────────────────────────────────────────────────────


def test_generic_only_run_sets_the_axis():
    """🔴 범용 하나만 돌면 그 파일은 「전담 관측면 없음」이다."""
    from src.analyzer.io.static import _run_analyzers, StaticAnalysisResult  # noqa: PLC0415

    ctx = _ctx("elixir", "v.ex")
    result = StaticAnalysisResult(filename="v.ex")
    _run_analyzers(ctx, result)
    assert result.no_dedicated_observer == "elixir", (
        "전담 어댑터가 없는 언어인데 축이 서지 않았다"
    )


def test_dedicated_run_does_not_set_the_axis():
    """🔴 부정 통제 — 전담이 하나라도 돌면 축은 서지 않는다. 과차단이 이 작업의 위험이다."""
    from src.analyzer.io.static import _run_analyzers, StaticAnalysisResult  # noqa: PLC0415

    ctx = _ctx("python", "v.py")
    result = StaticAnalysisResult(filename="v.py")
    _run_analyzers(ctx, result)
    assert result.no_dedicated_observer is None, (
        f"python 은 전담 분석기가 도는데 축이 섰다 — 과차단"
    )


def test_axis_does_not_block_the_gate():
    """🔴 이 축은 **가시화 전용**이다 — 차단하면 조달 실패가 다시 벽이 된다(#1568)."""
    from src.analyzer.io.static import StaticAnalysisResult  # noqa: PLC0415

    result = StaticAnalysisResult(filename="v.ex")
    result.no_dedicated_observer = "elixir"
    assert result.incomplete is False, "이 축이 incomplete 를 세우면 벽이 된다"


# ── 파이프라인 집계 · 점수 신뢰도 ─────────────────────────────────────────


def test_pipeline_aggregates_the_languages():
    """파일별 축이 실행 단위로 모인다 — `static_uncovered_languages` 와 같은 형태."""
    from src.worker.pipeline import _aggregate_no_dedicated_observers  # noqa: PLC0415
    from src.analyzer.io.static import StaticAnalysisResult  # noqa: PLC0415

    a = StaticAnalysisResult(filename="a.ex"); a.no_dedicated_observer = "elixir"
    b = StaticAnalysisResult(filename="b.rs"); b.no_dedicated_observer = "rust"
    c = StaticAnalysisResult(filename="c.py")
    assert _aggregate_no_dedicated_observers([a, b, c]) == ["elixir", "rust"]


@pytest.mark.parametrize("payload,expected", [
    ({"static_no_dedicated_observers": ["elixir"]}, True),
    ({"static_no_dedicated_observers": []}, False),
    ({}, False),
])
def test_score_is_unreliable_when_no_dedicated_observer(payload, expected):
    """🔴 전담 관측면이 없었으면 점수를 신뢰 가능으로 표시하지 않는다.

    대조군 둘을 함께 건다 — 빈 목록과 키 부재에서 뒤집히면 그것도 결함이다.
    """
    from src.scorer.reliability import score_is_unreliable  # noqa: PLC0415

    assert score_is_unreliable(payload) is expected


# ── 🔴 범용조차 돌지 않은 경우는 이 축이 아니다 (Grok claim-review 정정) ──────────
#
# 첫 판 조건은 `supported > 0 and dedicated_ran == 0` 이었다. 그러면 semgrep 이 지원하지
# 않는 언어(css·dart·powershell·protobuf)까지 잡혀 「범용 검사기만 봤다」는 경고가 **거짓**이
# 된다 — 아무것도 안 봤기 때문이다. 그 자리는 `uncovered_language`(실행 0개)가 담당한다.
# 운영자가 전부 끈 경우도 같은 이유로 빠진다.


def test_axis_does_not_fire_when_nothing_ran():
    """🔴 실행 0개면 이 축이 아니다 — 경고 문구가 거짓이 되고 `uncovered_language` 와 겹친다."""
    from src.analyzer.io.static import _run_analyzers, StaticAnalysisResult  # noqa: PLC0415

    ctx = _ctx("css", "a.css")   # semgrep 미지원 · 전담(stylelint)은 이 호스트에 없다
    result = StaticAnalysisResult(filename="a.css")
    ran, _opted, _supported = _run_analyzers(ctx, result)
    assert ran == 0, f"전제 붕괴 — css 에서 무언가 돌았다(ran={ran}). 이 대조군은 무효다"
    assert result.no_dedicated_observer is None, (
        "아무것도 안 돌았는데 「범용만 봤다」로 표시됐다"
    )


def test_axis_does_not_fire_when_operator_disabled_everything():
    """🔴 운영자가 전부 끈 것은 「내가 껐다」다 — 결함으로 되돌려주지 않는다(기존 opt-out 규칙)."""
    from src.analyzer.io.static import _run_analyzers, StaticAnalysisResult  # noqa: PLC0415

    class _Cfg:
        disabled_tools = ["semgrep", "pylint", "flake8", "bandit"]

    ctx = AnalyzeContext(filename="v.py", content="x", language="python",
                         is_test=False, tmp_path="/tmp/v.py",  # nosec B108
                         repo_config=_Cfg())
    result = StaticAnalysisResult(filename="v.py")
    ran, opted, _supported = _run_analyzers(ctx, result)
    assert ran == 0 and opted > 0, f"전제 붕괴 — ran={ran} opted={opted}"
    assert result.no_dedicated_observer is None


# ── C# 은 전담 관측면이 **없다** — dotnet_format 은 지웠다 (#1565) ──────────────
#
# 🔴 `dotnet format` 은 프로젝트/솔루션을 요구하는데 `static.py` 는 파일 하나를 임시
#    디렉터리에 떼어 놓는다. 실측(세 입력 전부): `exit=1 · 이슈 0건 · stderr 749바이트`
#    (「유효한 프로젝트 또는 솔루션 파일이 아님」) — **한 번도 동작한 적이 없다.**
#
# 🔴 그런데 등록돼 있으면 그 무동작이 「돌았다」로 세어져 이 축을 **지웠다**. 실측:
#      dotnet 있음   unavailable=[]                no_dedicated=None      ← 「완전 · 깨끗」
#      dotnet 없음   unavailable=['dotnet_format'] no_dedicated='csharp'  ← 사실
#    **설치돼 있으면 보고가 더 나빴다.**
#
# 🔴 임시 `.csproj` 로 감싸도 살아나지 않는다(#1586 인코딩 수정 이후 재측정):
#      full format(proj)    dirty 5건 / clean 0 / **broken 0** · 5.3s
#      whitespace --folder  dirty 5건 / clean 0 / **broken 0** · 1.7s
#    `broken` 은 문법이 깨졌는데 공백만 정돈된 C# 이다 — 둘 다 「깨끗」으로 본다.
#    `dotnet format` 은 서식 도구이지 분석기가 아니고, 진단도 `.cs` 가 아니라
#    프로젝트/폴더에 귀속돼 줄번호가 소스의 것이 아니다.
#
# 🔴 `is_enabled` 를 항상 False 로 두는 것은 **오답이었다**(Grok claim-review `01a05733`).
#    그 갈래의 뜻은 「바이너리 부재」이고 `_binary_is_absent` 는 `dotnet` 이 아니라
#    **`dotnet_format` 이라는 이름의 바이너리**를 찾는다 — 누가 그 이름을
#    `PROVISIONED_ANALYZERS` 에 넣으면 모든 `.cs` 가 `incomplete` 가 되고 dotnet 을 깔아도
#    안 풀린다. 그리고 그 선택은 `test_supported_languages_are_reachable.py` 의
#    도달가능성 가드를 **피하는** 것이었다 — 그 가드가 제 일을 한 것이다. 그래서 지웠다.
#
# C# has no dedicated observer: the adapter never analysed anything, and keeping it registered
# merely erased this axis.


def test_csharp_has_no_dedicated_observer():
    """🔴 C# 은 semgrep 만 본다 — 그 사실이 기록되어야 한다.

    🔴 `_run_analyzers` 가 아니라 **`analyze_file`** 로 잰다. 전자는 축 하나만 세우고
    `uncovered_language`·`incomplete` 는 호출부가 정한다 — 그 둘을 안 보면 「가시화만 하고
    차단하지 않는다」는 이 절의 주장이 검사되지 않는다(Grok claim-review `01a05742`).
    Measure through the production entry point: the axis is only half the claim.
    """
    from src.analyzer.io.static import analyze_file  # noqa: PLC0415

    result = analyze_file("Program.cs", "class A\n{\n    public int X;\n}\n")
    assert result.no_dedicated_observer == "csharp", (
        "C# 에 전담 관측면이 생겼다 — 조달이 바뀌었다면 이 절 전체를 다시 쓸 것"
    )
    assert result.incomplete is False, "가시화 축이 차단으로 바뀌었다 — 이 절의 계약 위반"
    assert getattr(result, "uncovered_language", None) is None, (
        "semgrep 이 지원하는데 `uncovered_language` 가 섰다 — 두 축이 뒤섞였다"
    )


def test_no_adapter_claims_to_be_a_dedicated_csharp_observer():
    """🔴 위 축이 **어댑터 부재**에서 오는지 확인한다 — 「돌긴 했는데 0건」과 가른다.

    `supports("csharp")` 가 참인 전담 어댑터가 하나라도 등록돼 있으면, 그것이 무동작이어도
    `dedicated_ran` 을 올려 축을 지운다. 그 자리가 정확히 `#1565` 였다.
    """
    dedicated = sorted(
        a.name for a in REGISTRY
        if not getattr(a, "is_generic", False) and a.supports(_ctx("csharp", "Program.cs"))
    )
    assert dedicated == [], (
        f"C# 전담 어댑터가 등록돼 있다: {dedicated}. 그것이 실제로 분석하는지 먼저 재라 — "
        "무동작이면 이 축을 지우고 그 파일은 「완전 · 깨끗」이 된다(#1565)."
    )
