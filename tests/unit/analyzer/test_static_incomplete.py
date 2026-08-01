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
    """
    from src.analyzer.pure.registry import REGISTRY

    for analyzer in REGISTRY:
        if analyzer.name in absent_names:
            monkeypatch.setattr(
                type(analyzer), "is_enabled", lambda self, ctx: False, raising=False
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
