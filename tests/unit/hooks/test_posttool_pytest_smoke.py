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

import pytest  # noqa: E402

from posttool_pytest_smoke import (  # noqa: E402
    derive_test_target, is_src_file, is_watched_file,
)


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


def test_derive_test_target_none_only_when_no_matching_test_exists():
    """🔴 src 직속 파일은 **정확 대응 테스트가 없을 때만** None 이다.

    ## 이 테스트가 결함을 고정하고 있었다 (2026-07-19 회고 P2 D10)

    구 판은 `derive_test_target("src/main.py") is None` 을 단언했다 — 즉 훅이 정확한
    대응 테스트를 무시하고 0-단언 수집으로 강등하는 동작을 **정상으로 못박고** 있었다.
    실제로는 `src/` 직속 7파일 중 **6개가 `tests/unit/test_<stem>.py` 를 갖고 있다**.

    "기존 테스트가 왜 통과하는가" 를 물어야 하는 정확한 사례 — 테스트가 초록인 이유가
    구현이 옳아서가 아니라 **테스트가 결함을 기술하고 있어서**였다.
    (`.claude/rules/testing.md` §회귀 차단 트랩 · SMTP 587 과 동일 클래스)
    """
    # 대응 테스트가 실재 → 그 파일로 매핑돼야 한다
    assert derive_test_target("src/main.py") == "tests/unit/test_main.py"
    # 대응 테스트가 없음 → None (collection 스모크 fallback)
    assert derive_test_target("src/constants.py") is None


def test_derive_test_target_none_for_non_src():
    """src 아닌 파일 → None."""
    assert derive_test_target("tests/unit/gate/test_engine.py") is None
    assert derive_test_target("README.md") is None


# ── `.claude/hooks` 감시 (#1441) ──────────────────────────────────────────────
#
# 🔴 훅 자신이 감시 밖이었다. `_WATCHED_ROOTS` 는 `src`·`alembic`·`scripts` 였고,
#    훅을 고쳐도 스모크가 **아예 안 돌았다**. 훅은 모든 편집에 개입하는 표면이라
#    여기서 깨지면 세션 전체가 영향을 받는데, 정작 그 파일만 조기탐지가 0이었다.
#    (같은 파일 :36-38 이 「결함이 가장 많은 곳에 조기탐지가 0이었다」며 alembic·scripts 를
#     넣은 것과 같은 논리다 — 훅만 빠져 있었다.)


class TestClaudeHooksAreWatched:
    """훅 편집이 대응 테스트를 실제로 겨냥하는가."""

    @pytest.mark.parametrize("path", [
        ".claude/hooks/doc_review_gate.py",
        "f:/repo/.claude/hooks/doc_review_gate.py",          # 절대경로
        "f:\repo\.claude\hooks\doc_review_gate.py",      # Windows 구분자
    ])
    def test_hook_file_is_watched(self, path):
        assert is_watched_file(path) is True, f"훅이 감시 밖이다: {path}"

    def test_hook_maps_to_its_exact_test_file(self):
        """정확 대응 파일이 있으면 그것을 겨냥한다 — 디렉토리로 강등하지 않는다."""
        assert derive_test_target(".claude/hooks/doc_review_gate.py") == \
            "tests/unit/hooks/test_doc_review_gate.py"

    def test_hook_without_a_test_falls_back_to_the_directory(self):
        """🔴 대응 테스트가 없는 훅도 **디렉토리**로는 겨냥한다 — None 이면 안 쟀음이 된다.

        실측: `block_credential_dump.py` 는 대응 테스트 파일이 없다(2026-08-18).
        None 을 돌려주면 그 훅 편집은 조기탐지가 영구 0 이다.
        """
        assert derive_test_target(".claude/hooks/block_credential_dump.py") == \
            "tests/unit/hooks"

    def test_non_python_hook_asset_is_not_watched(self):
        """오탐 축 — `.json`·`.md` 는 이 스모크의 대상이 아니다."""
        assert is_watched_file(".claude/settings.json") is False
        assert is_watched_file(".claude/skills/retrospective/SKILL.md") is False

    def test_every_hook_file_resolves_to_a_target(self):
        """🔴 공허화 차단 — 리포의 실제 훅 전부가 겨냥 대상을 갖는다.

        합성 경로만 단언하면 훅이 늘었을 때 이 축이 조용히 뒤처진다.
        """
        root = Path(__file__).resolve().parents[3]
        hooks = sorted((root / ".claude" / "hooks").glob("*.py"))
        assert hooks, ".claude/hooks 에 훅이 0개 — 이 테스트가 공허하다"
        for hook in hooks:
            rel = f".claude/hooks/{hook.name}"
            assert is_watched_file(rel) is True, f"{rel} 감시 밖"
            assert derive_test_target(rel) is not None, f"{rel} 겨냥 대상 없음"
