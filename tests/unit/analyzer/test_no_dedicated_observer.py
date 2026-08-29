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
    import src.analyzer.io.tools  # noqa: F401,PLC0415 — 전 어댑터 등록

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
