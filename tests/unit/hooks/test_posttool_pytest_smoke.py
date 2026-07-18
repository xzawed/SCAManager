"""PostToolUse pytest 스모크 훅 정합 (회고 2026-07-18 P1 테마 C — Hook false-green 봉인).
PostToolUse pytest smoke hook (retro 2026-07-18 P1 theme C — seals the hook false-green).

기존 훅은 `pytest tests/`(전체 5566)를 60s 타임아웃에 돌려 완주 불가 → SIGTERM → `|| true` 로
삼켜져 false-green. 'Hook 신뢰' 필수 원칙의 토대가 붕괴. 이 스모크는 편집된 src 경로 → 대응
tests/unit 서브디렉토리만 빠르게 돌려(없으면 collection 스모크) 실제로 완주하는 신호를 준다.
The old hook ran the full 5566-test suite in a 60s timeout → SIGTERM → `|| true` swallow → false-green.
This smoke scopes to the affected tests/unit subdir (collection smoke fallback), so it actually finishes.

전체 게이트는 push-time(6-step ②)로 위임 — 이 훅은 best-effort 조기 실패 탐지(전체 게이트 대체 아님).
The full gate stays at push-time (6-step ②); this hook is best-effort early-failure detection.
"""
import sys
from pathlib import Path

# 훅 파일 직접 임포트 (src/ 외부) — test_doc_review_gate.py 동일 패턴.
# Import the hook file directly (outside src/) — same pattern as test_doc_review_gate.py.
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / ".claude" / "hooks"))

from posttool_pytest_smoke import derive_test_target, is_src_file  # noqa: E402


# ── 순수 함수: is_src_file ───────────────────────────────────────────────
# Pure function: is_src_file

def test_is_src_file_true_for_src_paths():
    assert is_src_file("src/gate/engine.py") is True
    assert is_src_file("d:/Source/SCAManager/src/worker/pipeline.py") is True
    assert is_src_file("d:\\Source\\SCAManager\\src\\notifier\\telegram.py") is True


def test_is_src_file_false_for_non_src():
    assert is_src_file("tests/unit/gate/test_engine.py") is False
    assert is_src_file("README.md") is False
    assert is_src_file("docs/STATE.md") is False
    assert is_src_file("") is False


# ── 순수 함수: derive_test_target ────────────────────────────────────────
# Pure function: derive_test_target

def test_derive_test_target_maps_top_level_area():
    """src/<area>/... → tests/unit/<area> (영역 단위 스코프)."""
    assert derive_test_target("src/gate/engine.py") == "tests/unit/gate"
    assert derive_test_target("src/worker/pipeline.py") == "tests/unit/worker"
    assert derive_test_target("src/services/dashboard_service.py") == "tests/unit/services"


def test_derive_test_target_handles_absolute_and_backslash():
    """절대경로·백슬래시(Windows) 정규화."""
    assert derive_test_target("d:/Source/SCAManager/src/api/routes/foo.py") == "tests/unit/api"
    assert derive_test_target("d:\\Source\\SCAManager\\src\\notifier\\telegram.py") == "tests/unit/notifier"


def test_derive_test_target_none_for_direct_src_file():
    """src 직속 파일(main.py 등)은 서브영역 없음 → None (collection 스모크 fallback)."""
    assert derive_test_target("src/main.py") is None
    assert derive_test_target("src/constants.py") is None


def test_derive_test_target_none_for_non_src():
    """src 아닌 파일 → None."""
    assert derive_test_target("tests/unit/gate/test_engine.py") is None
    assert derive_test_target("README.md") is None
