"""`check_architecture_tree_sync.py` 회귀 가드 — 신규 파일 미등재를 실제로 잡는가.

## 배경 (2026-07-20 문서 재구성 진단 P1)

architecture.md 는 src/ 트리 SSOT 로 선언됐으나 동기 가드가 0개 → "신규 파일 미등재" 3회 재발.
이 테스트는 그 가드가 (1) 현재 동기 상태를 통과시키고 (2) 미등재 파일을 실제로 잡는지 확인한다.
가드 자신도 관측자이므로 3-불변식(AGENTS.md) 적용 — 실제 파일시스템 대조 + 뮤테이션 red.
"""
import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "check_architecture_tree_sync.py"


def _load():
    spec = importlib.util.spec_from_file_location("_arch_sync", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_arch_sync"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_current_tree_is_in_sync():
    """🔴 현재 architecture.md 는 src/ 트리와 동기 상태여야 한다(baseline)."""
    mod = _load()
    missing = mod.missing_entries()
    assert not missing, f"architecture.md 트리 미등재: {missing}"


def test_guard_discovers_real_packages_and_modules():
    """대조군 — 탐색이 비면 위 단언이 공허하다."""
    mod = _load()
    assert len(mod._packages()) >= 20, "src/ 패키지 탐색이 사실상 비었다"
    assert len(mod._top_modules()) >= 5, "src/ 최상위 모듈 탐색이 사실상 비었다"


def test_guard_catches_an_unlisted_entry(monkeypatch):
    """🔴 미등재 항목을 실제로 잡는가 — 뮤테이션(가공의 신규 패키지)."""
    mod = _load()
    real = mod._packages
    monkeypatch.setattr(mod, "_packages", lambda: real() + ["brand_new_unlisted_pkg"])
    missing = mod.missing_entries()
    assert any("brand_new_unlisted_pkg" in m for m in missing), (
        "가공의 미등재 패키지를 탐지하지 못했다 — 가드가 fail-open"
    )


def test_guard_is_wired():
    """🔴 이 가드가 pre-commit·CI 에 배선됐는지(정의만 하고 미배선 dead 방지).

    (test_guard_wiring_coverage.py 가 전 가드에 대해 강제하지만, 여기서도 명시 확인.)
    """
    pc = (_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    ci = "\n".join(p.read_text(encoding="utf-8") for p in (_ROOT / ".github" / "workflows").glob("*.yml"))
    assert "check_architecture_tree_sync" in pc, "pre-commit 미배선"
    assert "check_architecture_tree_sync" in ci, "CI 미배선"
