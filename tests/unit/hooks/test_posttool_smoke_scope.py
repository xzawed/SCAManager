"""PostToolUse 스모크 훅의 **탐지 범위**와 **배너 정직성** 불변식.

## 사고 3종 (2026-07-19 회고 P2 — D10·D11·D12)

이 훅은 *"전체 스위트를 60s 타임아웃에 돌려 SIGTERM → `|| true` 로 삼킨"* false-green 을
없애려고 만들어졌다. 그런데 훅 자신이 같은 병을 세 가지 형태로 재생산하고 있었다:

1. 🔴 **D12 — 0-단언 실행에 `✅ 스모크 통과`.** `--co`(수집만) 경로에도 통과 배너가 붙었다.
   아무것도 검증하지 않은 실행이 검증 통과로 보인다. 수집 성공은 "import 가 안 깨졌다" 이지
   "동작이 옳다" 가 아니다.

2. 🔴 **D10 — 정확한 대응 테스트가 있는데 강등.** `src/` 직속 파일은 무조건 collection 으로
   내려갔는데, 7개 중 **6개가 정확히 대응하는 테스트 파일을 갖고 있다**
   (config·crypto·database·logging_config·main·scheduler). 실행 가능한 단언이 있는데
   0-단언으로 내려앉았고, 그중 `logging_config.py` 는 이 사이클 토큰 유출 봉인 지점,
   `scheduler.py` 는 cron P0 대체 코어다.

3. 🔴 **D11 — 최다 결함 영역이 커버 밖.** `alembic/`(#1102 fileConfig 가 앱 로깅 파괴)과
   `scripts/`(가드 스크립트 다수)는 훅이 **아예 발동하지 않았다**.

세 가지가 겹치면: 결함이 가장 많은 곳에는 훅이 안 돌고, 도는 곳에서는 단언 없이 ✅ 가 뜬다.
"""
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / ".claude" / "hooks"))

from posttool_pytest_smoke import (  # noqa: E402
    _banner,
    derive_test_target,
    is_watched_file,
)


# ── D12: 배너가 '단언 실행' 과 '수집만' 을 구별한다 ──────────────────────


def test_collection_only_run_is_not_labelled_passed():
    """🔴 단언 0건 실행에 '통과' 라고 쓰면 안 된다 — 이 훅이 없애려던 바로 그 거짓말."""
    banner = _banner(rc=0, asserted=False)
    assert "통과" not in banner, f"0-단언 실행이 통과로 표시된다: {banner}"
    assert "단언 0건" in banner, f"단언이 없었다는 사실이 배너에 없다: {banner}"


def test_asserted_run_is_labelled_passed():
    """대조군 — 실제 단언이 돌면 통과로 표시돼야 한다(아무것도 통과 못 하면 규칙이 무의미)."""
    assert "✅" in _banner(rc=0, asserted=True)


@pytest.mark.parametrize("rc", [1, 2, 5])
def test_failure_is_labelled_failure_regardless_of_assertion_state(rc):
    """실패는 단언 여부와 무관하게 실패다."""
    for asserted in (True, False):
        assert "❌" in _banner(rc=rc, asserted=asserted)


def test_timeout_is_distinguished_from_both_pass_and_fail():
    """🔴 타임아웃은 통과도 실패도 아니다 — 판정 불가를 통과로 접으면 false-green."""
    banner = _banner(rc=None, asserted=True)
    assert "✅" not in banner and "❌" not in banner, banner


# ── D10: 정확 대응 테스트 파일을 찾는다 ─────────────────────────────────


_SRC_DIRECT_WITH_TESTS = [
    "config", "crypto", "database", "logging_config", "main", "scheduler",
]


@pytest.mark.parametrize("stem", _SRC_DIRECT_WITH_TESTS)
def test_src_direct_files_map_to_their_exact_test_file(stem):
    """🔴 `src/X.py` 에 `tests/unit/test_X.py` 가 있으면 **그 파일**을 돌려야 한다.

    이전 판은 전부 collection 스모크로 강등했다.
    """
    target = derive_test_target(f"src/{stem}.py", _ROOT)
    assert target == f"tests/unit/test_{stem}.py", (
        f"src/{stem}.py 가 정확 대응 테스트로 매핑되지 않는다: {target}"
    )
    assert (_ROOT / target).is_file(), f"{target} 이 실제로 없다 — 이 테스트의 전제 붕괴"


def test_src_subarea_files_still_map_to_their_subarea():
    """회귀 방지 — 서브영역 매핑(기존 동작)이 깨지면 안 된다."""
    assert derive_test_target("src/gate/engine.py", _ROOT) == "tests/unit/gate"
    assert derive_test_target("src/worker/pipeline.py", _ROOT) == "tests/unit/worker"


def test_file_without_a_matching_test_falls_back_to_collection():
    """대응 테스트가 없으면 None → 호출부가 collection 스모크로 내려간다.

    `src/constants.py` 는 대응 테스트가 없다(실측) — 없는 것을 있다고 하면 안 된다.
    """
    assert derive_test_target("src/constants.py", _ROOT) is None
    assert derive_test_target("src/__init__.py", _ROOT) is None


# ── D11: alembic/ · scripts/ 도 감시한다 ────────────────────────────────


@pytest.mark.parametrize("path", [
    "alembic/env.py",
    "scripts/check_retro_cadence.py",
    "src/gate/engine.py",
])
def test_high_defect_roots_are_watched(path):
    """🔴 `alembic/`·`scripts/` 도 감시 대상이다 — 이전엔 발동조차 안 했다."""
    assert is_watched_file(path), f"{path} 가 감시 대상이 아니다"


def test_alembic_edits_route_to_migration_tests():
    """`alembic/env.py` = #1102 결함 지점. 마이그레이션 테스트로 라우팅돼야 한다."""
    target = derive_test_target("alembic/env.py", _ROOT)
    assert target == "tests/unit/migrations"
    assert (_ROOT / target).is_dir(), "tests/unit/migrations 가 없다 — 전제 붕괴"


def test_script_edits_route_to_their_exact_test_when_one_exists():
    """`scripts/X.py` → `tests/unit/scripts/test_X.py`(있으면), 없으면 디렉토리."""
    assert derive_test_target("scripts/check_retro_cadence.py", _ROOT) == (
        "tests/unit/scripts/test_check_retro_cadence.py"
    )
    assert derive_test_target("scripts/does_not_exist_xyz.py", _ROOT) == "tests/unit/scripts"


def test_non_python_and_unwatched_paths_are_ignored():
    """오발동 방지 — docs 편집마다 pytest 가 돌면 훅이 소음이 된다."""
    for path in ("docs/STATE.md", "README.md", "src/templates/base.html"):
        assert not is_watched_file(path), f"{path} 가 감시 대상으로 잡혔다"


def test_windows_backslash_paths_are_normalized():
    """Windows 경로 — 훅은 실제로 이 형태를 받는다."""
    assert is_watched_file(r"D:\Source\SCAManager\src\scheduler.py")
    assert derive_test_target(r"D:\Source\SCAManager\src\gate\engine.py", _ROOT) == "tests/unit/gate"
