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


def test_guard_rejects_cross_dir_and_substring_mentions(monkeypatch):
    """🔴 트리 밖 경로/부분단어 언급은 '등재'로 인정 안 함 — cross-dir/substring fail-open 봉인.

    이전 bare `f"{pkg}/" in text` 는 데이터흐름 fence 의 엔드포인트 `/api/webhook`·타 디렉토리
    `tests/mcp/`·부분단어 `recapi/` 로도 통과해, src 트리에서 빠져도 미탐이었다(감사 self-defect).
    트리 엔트리 위치(앞이 word-char/슬래시 아님)만 인정하도록 봉인.
    """
    mod = _load()
    fake_tree = (
        "POST /api/webhook/telegram\n"  # 앞=/ (엔드포인트 경로)
        "recapi/ 관련 언급\n"            # 앞=c (부분단어)
        "tests/mcp/test_x.py\n"         # 앞=/ (타 디렉토리)
    )
    monkeypatch.setattr(mod, "_tree_text", lambda: fake_tree)
    monkeypatch.setattr(mod, "_packages", lambda: ["api", "mcp"])
    monkeypatch.setattr(mod, "_top_modules", lambda: [])
    missing = mod.missing_entries()
    assert any("api" in m for m in missing) and any("mcp" in m for m in missing), (
        f"cross-dir/부분단어 언급을 트리 등재로 오인(fail-open): missing={missing}"
    )


def test_guard_accepts_proper_tree_entry(monkeypatch):
    """대조군 — 트리 엔트리 `├── api/` 는 정상 인정(경계 규칙 과탐 방지)."""
    mod = _load()
    monkeypatch.setattr(mod, "_tree_text", lambda: "├── api/\n└── mcp/\n")
    monkeypatch.setattr(mod, "_packages", lambda: ["api", "mcp"])
    monkeypatch.setattr(mod, "_top_modules", lambda: [])
    assert mod.missing_entries() == []


def test_guard_is_wired():
    """🔴 이 가드가 pre-commit·CI 에 배선됐는지(정의만 하고 미배선 dead 방지).

    (test_guard_wiring_coverage.py 가 전 가드에 대해 강제하지만, 여기서도 명시 확인.)
    """
    pc = (_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    ci = "\n".join(p.read_text(encoding="utf-8") for p in (_ROOT / ".github" / "workflows").glob("*.yml"))
    assert "check_architecture_tree_sync" in pc, "pre-commit 미배선"
    assert "check_architecture_tree_sync" in ci, "CI 미배선"
