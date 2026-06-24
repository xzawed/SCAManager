"""CI dead-symbol 가드 정합 (회고 C1 — 자초 CodeQL cascade 근본 차단).
CI dead-symbol guard integrity (retro C1 — root fix for the self-inflicted CodeQL cascade).

tests/ 미사용 import(F401)·변수(F841)가 pre-merge 에서 안 잡혀 main full-scan CodeQL 에 사후
포착 → 별도 fix PR(#516/#517/#520/#521/#522) 을 반복 유발한 cascade 를 차단한다(A2: PR diff 한정).
🔴 핵심 불변식: flake8 호출은 반드시 `--isolated` 동반 — 없으면 setup.cfg per-file-ignore
(`tests/*:F401,F841`)가 검사를 무력화해 항상 통과(false-pass)한다(실증 확인).
Critical invariant: the flake8 call MUST use `--isolated`, else the setup.cfg per-file-ignore
silently masks the check (empirically verified false-pass).
"""
import re
from pathlib import Path

# 리포 루트 / repo root
_ROOT = Path(__file__).resolve().parents[3]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"


def _ci_text() -> str:
    return _CI.read_text(encoding="utf-8")


def test_ci_lints_changed_tests_for_dead_symbols():
    """CI 가 flake8 --isolated --select=F401,F841 로 dead symbol 을 검사한다 (순서 무관)."""
    ci = _ci_text()
    has = re.search(
        r"flake8[^\n]*--isolated[^\n]*--select=F401,F841"
        r"|flake8[^\n]*--select=F401,F841[^\n]*--isolated",
        ci,
    )
    assert has, "CI 에 flake8 --isolated --select=F401,F841 dead-symbol 가드 누락"


def test_ci_dead_symbol_guard_scoped_to_changed_files():
    """가드는 PR 변경 파일 한정(A2) — 전체 tests/ 일괄(`flake8 ... tests/` 고정 경로) 금지.
    full-scan 이면 기존 76건 legacy 위반으로 즉시 실패하므로 PR-diff 스코프여야 함."""
    ci = _ci_text()
    # PR 이벤트 한정 + base.sha diff 사용 = 변경 파일 스코프 신호
    assert "github.event.pull_request.base.sha" in ci, "PR diff base SHA 미사용 (변경 파일 스코프 아님)"
    # 고정 경로 전체 스캔(`--select=F401,F841 tests/`)이 아님을 확인 — legacy 76건 회피
    assert not re.search(r"--select=F401,F841\s+tests/\b", ci), \
        "전체 tests/ 일괄 스캔은 기존 legacy 위반으로 실패 — PR diff 한정이어야 함"
