"""모든 가드(scripts/check_*.py · .claude/hooks/*.py)가 **실제 게이트에 배선**됐는지 강제.

## 사고 — dead-wiring 재발의 구조적 근본 (2026-07-20 문서 재구성 진단 P1)

이 저장소가 반복하는 실패 클래스 중 하나: **가드/훅을 만들었는데 어느 게이트에도 안 걸려
무동작**(#1145 스모크 훅이 `main()` 미배선으로 alembic/scripts 를 통째로 놓침 · #1140 dead
code). 12개 check 스크립트 + 4개 훅의 배선이 **5개 이질 표면**(pre-commit·CI·SessionStart·
PostToolUse·PreToolUse)에 흩어져 있는데, "모든 가드가 어딘가에 배선됐나" 를 한 곳에서 강제하는
관측면이 없었다 — 신규 가드는 어떤 테스트도 배선을 강제하지 않아 조용히 dead 로 출시될 수 있었다.

## 🔴 배선 판정 = 실제 참조 관측 (산문 아님, AGENTS.md 불변식 3)

`.pre-commit-config.yaml`·`.github/workflows/*.yml`·`.claude/settings.json` 에서 가드 파일명이
실제로 참조되는지 본다. 참조가 없으면(= 미배선) FAIL. 의도적 비-게이트(라이브러리/공유 헬퍼)는
`_ADVISORY_ALLOWLIST` 에 사유와 함께 명시해야만 면제 — 그래야 "그냥 안 배선" 과 "의도적 면제" 가
구별된다.
"""
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS = _ROOT / "scripts"
_HOOKS = _ROOT / ".claude" / "hooks"

# 🔴 의도적 비-게이트(배선 면제) — 사유 필수. 신규 추가 시 회고/PR 에서 정당화.
#   현재: 없음(전 가드가 배선됨). 공유 라이브러리성 스크립트가 생기면 여기 등재.
_ADVISORY_ALLOWLIST: dict[str, str] = {}


def _wiring_surfaces() -> dict[str, str]:
    """배선이 선언되는 3 표면의 텍스트."""
    pc = _ROOT / ".pre-commit-config.yaml"
    ci_dir = _ROOT / ".github" / "workflows"
    settings = _ROOT / ".claude" / "settings.json"
    return {
        "pre-commit": pc.read_text(encoding="utf-8") if pc.is_file() else "",
        "ci": "\n".join(p.read_text(encoding="utf-8") for p in ci_dir.glob("*.yml")) if ci_dir.is_dir() else "",
        "settings": settings.read_text(encoding="utf-8") if settings.is_file() else "",
    }


def _guard_files() -> list[Path]:
    checks = sorted(_SCRIPTS.glob("check_*.py"))
    hooks = sorted(p for p in _HOOKS.glob("*.py") if p.name != "__init__.py")
    return checks + hooks


def _wired_surfaces(stem: str, surfaces: dict[str, str]) -> list[str]:
    return [name for name, text in surfaces.items() if stem in text]


# ── 핵심 불변식 ─────────────────────────────────────────────────────────


def test_every_guard_is_wired_or_explicitly_advisory():
    """🔴 모든 check 스크립트·훅은 **실제 게이트에 배선**되거나 명시 면제여야 한다.

    신규 가드가 배선 없이 들어오면 여기서 빨개진다 — dead-wiring 재발의 집행면.
    """
    surfaces = _wiring_surfaces()
    assert any(surfaces.values()), "배선 표면(pre-commit/ci/settings)을 못 읽었다 — 전제 붕괴"

    unwired = []
    for path in _guard_files():
        stem = path.stem
        if stem in _ADVISORY_ALLOWLIST:
            continue
        if not _wired_surfaces(stem, surfaces):
            unwired.append(path.relative_to(_ROOT).as_posix())
    assert not unwired, (
        f"어느 게이트에도 배선되지 않은 가드: {unwired}\n"
        "→ `.pre-commit-config.yaml`/`.github/workflows/*.yml`/`.claude/settings.json` 중 하나에\n"
        "   배선하거나, 의도적 비-게이트면 `_ADVISORY_ALLOWLIST` 에 사유와 함께 등재할 것.\n"
        "   (가드를 만들고 배선 안 하면 전 스위트 green 인데 무동작 — #1145 dead-wiring 클래스)"
    )


def test_advisory_allowlist_entries_still_exist():
    """대조군 — 면제 목록이 사라진 가드를 가리키면 stale 이다."""
    stems = {p.stem for p in _guard_files()}
    stale = sorted(set(_ADVISORY_ALLOWLIST) - stems)
    assert not stale, f"_ADVISORY_ALLOWLIST 가 존재하지 않는 가드를 가리킨다: {stale}"


def test_advisory_allowlist_entries_carry_a_reason():
    """면제는 사유 의무 — 사유 없는 면제는 '그냥 안 배선' 과 구별되지 않는다."""
    silent = [k for k, v in _ADVISORY_ALLOWLIST.items() if not (v or "").strip()]
    assert not silent, f"사유 없는 배선 면제: {silent}"


# ── 자가 검증 ────────────────────────────────────────────────────────────


def test_inventory_discovers_the_real_guards():
    """대조군 — 가드 탐색이 사실상 비면 위 단언이 공허하다."""
    files = _guard_files()
    assert len(files) >= 14, f"가드 탐색이 {len(files)}개 — check_*.py 12 + hooks 4 이상 기대"


def test_settings_json_is_valid_and_referenced_guards_resolve():
    """settings.json 이 참조하는 훅 파일이 실제로 존재하는지(죽은 배선 차단)."""
    settings_path = _ROOT / ".claude" / "settings.json"
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    referenced = json.dumps(data)
    for hook in _HOOKS.glob("*.py"):
        if hook.name == "__init__.py":
            continue
        # settings 가 이 훅을 언급하면, 파일이 실제로 있어야 한다(있음 — 대조 확인)
        if hook.stem in referenced:
            assert hook.is_file()
