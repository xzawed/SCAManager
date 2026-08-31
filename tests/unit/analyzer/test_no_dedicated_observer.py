"""전담 관측면이 하나도 돌지 않은 파일을 「완전」으로 기록하지 않는다.

## 사고 (실측 2026-08-29, 프로덕션 `supports()` 로 역인덱싱)

`PROVISIONED_ANALYZERS` 와 대조하면 **전담 분석기가 배포본에 하나도 없는 언어가 6개**다:

    rust     clippy 미조달        swift   swiftlint 미조달
    php      phpstan 미조달       csharp  dotnet_format 미조달
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
    # `src.analyzer.io.static` 을 임포트하면 어댑터 23종이 전부 등록된다(그 모듈 상단의
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


# ── dotnet_format 은 전담 관측면이 아니다 — 있으면 오히려 신호를 지운다 (#1565) ──
#
# 🔴 실측(이 개발 PC, dotnet 8.0.424 · 인코딩 수정 #1586 이후):
#
#     dotnet 있음   issues=0 incomplete=False unavailable=[]                no_dedicated=None
#     dotnet 없음   issues=0 incomplete=False unavailable=['dotnet_format'] no_dedicated='csharp'
#
#   **dotnet 이 설치돼 있으면 보고가 더 나빠진다.** 어댑터가 「돌았다」로 세어져
#   `no_dedicated_observer` 신호를 지우고, 그 파일은 「완전히 분석됨 · 이슈 0건」이 된다.
#
# 🔴 그런데 이 어댑터는 **한 번도 분석한 적이 없다.** `dotnet format` 은 프로젝트/솔루션을
#   요구하는데 어댑터는 단일 `.cs` 임시 파일을 넘긴다. 실측(세 입력 전부):
#     현재 argv               exit=1 · hits=0 · stderr 749바이트("유효한 프로젝트가 아님")
#
#   임시 `.csproj` 로 감싸도(처방 A) 사는 것이 아니다 — 실측:
#     full format(proj)       dirty 5건 / clean 0 / **broken 0** · 5.3s
#     whitespace --folder     dirty 5건 / clean 0 / **broken 0** · 1.7s
#   `broken` 은 **문법이 깨졌는데 공백만 정돈된** C# 이다. 둘 다 「깨끗」으로 본다 —
#   `dotnet format` 은 서식 도구이지 분석기가 아니다. 게다가 진단이 `A.cs` 가 아니라
#   프로젝트/폴더에 귀속돼 줄번호가 소스의 것이 아니다.
#
# 🔴 조달: `dotnet` 은 `ci.yml`·`nixpacks.toml`·`railway.toml` 어디에도 없고
#   `PROVISIONED_ANALYZERS` 밖이다. 즉 프로덕션에서는 이미 안 돌고, 위 「더 나쁜」 보고는
#   dotnet 이 깔린 개발 머신에서만 난다 — 그리고 이 리포는 판별식을 그런 머신에서 정한다.
#
# The adapter's presence erases the truth: with dotnet installed a C# file is recorded as
# fully analysed and clean, while without it the missing-observer axis correctly fires.


def test_csharp_keeps_the_missing_observer_axis_even_where_dotnet_is_installed(monkeypatch):
    """🔴 `dotnet` 이 있어도 C# 은 전담 관측면이 없다 — 어댑터가 그 신호를 지우면 안 된다.

    `dotnet` 을 **있는 것으로** 만들고 프로덕션 경로를 태운다. 어댑터가 「돌았다」로
    세어지면 축이 서지 않고, 그 파일은 「완전히 분석됨 · 깨끗」이 된다.
    """
    from src.analyzer.io.static import _run_analyzers, StaticAnalysisResult  # noqa: PLC0415
    import src.analyzer.io.tools.dotnet_format as mod  # noqa: PLC0415

    monkeypatch.setattr(mod.shutil, "which", lambda name: f"/usr/bin/{name}")
    ctx = _ctx("csharp", "Program.cs")
    result = StaticAnalysisResult(filename="Program.cs")
    _run_analyzers(ctx, result)

    assert result.no_dedicated_observer == "csharp", (
        "`dotnet` 이 설치된 머신에서 C# 이 「전담 관측면 있음」으로 기록됐다.\n"
        "  `dotnet format` 은 단일 `.cs` 를 분석하지 못한다(실측: 세 입력 전부 이슈 0건) —\n"
        "  「돌았다」로 세어지면 그 파일은 「완전히 분석됨 · 깨끗」이 되고, dotnet 이\n"
        "  **없는** 머신보다 보고가 나빠진다."
    )


def test_csharp_axis_is_not_an_artifact_of_dotnet_being_absent():
    """🔴 부정 통제 — 위 시험이 「`which` 를 못 찾아서」 통과하는 것이 아님을 가른다.

    `which` 를 건드리지 않은 상태에서도 축은 서야 한다. 두 시험이 함께 있어야
    「dotnet 유무와 무관하게 C# 은 전담 관측면이 없다」가 된다.
    """
    from src.analyzer.io.static import _run_analyzers, StaticAnalysisResult  # noqa: PLC0415

    ctx = _ctx("csharp", "Program.cs")
    result = StaticAnalysisResult(filename="Program.cs")
    _run_analyzers(ctx, result)
    assert result.no_dedicated_observer == "csharp", (
        "C# 에 전담 관측면이 생겼다 — 조달이 바뀌었다면 이 절 전체를 다시 쓸 것"
    )
