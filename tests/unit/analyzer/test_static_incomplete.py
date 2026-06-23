"""정적분석 도구 subprocess 타임아웃 → incomplete 전파 테스트 (Task9 P1 #7).
Static analysis tool subprocess-timeout → incomplete propagation tests (Task9 P1 #7).

도구가 타임아웃 시 빈 목록을 '무음' 반환하면 미분석 카테고리(특히 security)가 만점으로
인플레이션되어 auto-merge fail-open 이 된다. analyze_file 이 StaticAnalysisResult.incomplete 로
이를 신호하면 _run_static_with_timeout → static_analysis_incomplete 마커 → 게이트 차단.
"""
import subprocess
from unittest.mock import patch

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
