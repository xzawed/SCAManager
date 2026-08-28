"""모든 가드(scripts/check_*.py · .claude/hooks/*.py)가 **실제 게이트에 배선**됐는지 강제.

## 사고 — dead-wiring 재발의 구조적 근본 (2026-07-20 문서 재구성 진단 P1)

이 저장소가 반복하는 실패 클래스 중 하나: **가드/훅을 만들었는데 어느 게이트에도 안 걸려
무동작**(#1145 스모크 훅이 `main()` 미배선으로 alembic/scripts 를 통째로 놓침 · #1140 dead
code). 12개 check 스크립트 + 4개 훅의 배선이 **5개 이질 표면**(pre-commit·CI·SessionStart·
PostToolUse·PreToolUse)에 흩어져 있는데, "모든 가드가 어딘가에 배선됐나" 를 한 곳에서 강제하는
관측면이 없었다 — 신규 가드는 어떤 테스트도 배선을 강제하지 않아 조용히 dead 로 출시될 수 있었다.

## 🔴 배선 판정 = 실제 참조 관측 (산문 아님, AGENTS.md 불변식 3)

`.pre-commit-config.yaml`·`.github/workflows/*.yml`·`.claude/settings.json` 에서 가드가
**실제로 호출**(`python scripts/<stem>.py` 등)되는지 본다 — 단순 언급(주석)은 배선 아님
(Grok 최종 검증: substring 판정은 이 파일이 강제하려는 fail-open 을 가드 자신이 범한 것). 의도적 비-게이트(라이브러리/공유 헬퍼)는
`_ADVISORY_ALLOWLIST` 에 사유와 함께 명시해야만 면제 — 그래야 "그냥 안 배선" 과 "의도적 면제" 가
구별된다.
"""
import json
import re
from pathlib import Path

import pytest

from tests.unit.scripts._wiring_shape import surface_invokes

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS = _ROOT / "scripts"
_HOOKS = _ROOT / ".claude" / "hooks"

# 🔴 의도적 비-게이트(배선 면제) — 사유 필수. 신규 추가 시 회고/PR 에서 정당화.
#   공유 라이브러리성 스크립트나 **의도적으로 차단을 뗀** 도구가 생기면 여기 등재.
_ADVISORY_ALLOWLIST: dict[str, str] = {
    # 2026-07-29 사용자 결정 — pre-commit 차단 해제, 스크립트는 수동 점검용으로 보존.
    # 이 훅은 커밋을 막을 수 있는 유일한 **스타일** 규칙이었고 구체적 제품 결함 사례를 인용하지
    # 않았다(다른 모든 가드와 달리 사고 기반이 아님). CLAUDE.md 의 이중언어 주석 **원칙 자체는
    # 유효**하며, 해제된 것은 기계 차단뿐이다 → 비율은 `scripts/i18n_comments/check_bilingual.py src/ --report`
    #   (이 스크립트는 staged 추가분 전용이라 손으로 돌리면 잴 것이 없다 — 그때 exit 2).
    # User decision 2026-07-29: unblocked but kept for manual runs. It was the only *style* rule able
    # to fail a commit and cited no concrete defect; the CLAUDE.md principle itself still stands.
    # 🔴 키는 파일 경로가 아니라 **stem**(확장자 없는 파일명) — `_guard_files()` 가 `path.stem` 으로 대조한다.
    "check_bilingual_comments":
        "이중언어 주석 = 스타일 규칙(사고 기반 아님). 차단 해제·수동 점검 보존 (사용자 결정 2026-07-29)",
}


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
    """가드가 각 표면에서 **실제로 호출**되는가 — 단순 언급 아님.

    🔴 Grok 최종 적대검증 (2026-07-20): 이전 판은 `stem in text` substring 이었다. 그러면
    **주석·설명이 가드 이름을 언급하기만 해도 "배선됨"** 으로 오판된다 — 이 파일이 강제하려는
    바로 그 fail-open anti-pattern(AGENTS.md 불변식 1)을 가드 자신이 범한 것이다.
    → `python scripts/<stem>.py` / `python .claude/hooks/<stem>.py` 형태의 **실제 호출**
    (pre-commit `entry:`·CI `run:`·settings 훅 command)만 배선으로 인정한다.
    Only an actual invocation counts as wired; a mere mention (comment) does not.

    🔴 path-comment fail-open 봉인 (감사 self-defect): 경로 토큰이 텍스트 어디든(주석 포함) 있으면
    배선으로 셌다 — `# TODO: wire scripts/check_x.py` 같은 **전체 경로 주석**도 통과시켜, 이 파일이
    막으려는 anti-pattern 을 자신이 범했다. YAML 표면(pre-commit/ci)은 주석 제거 후 매칭.

    🔴 **실행자 앵커 봉인 (2026-07-31 Grok claim-review + 뮤테이션 실측)**: 위 두 차례 강화 뒤에도
    정규식은 **경로 토큰만** 봤다 — docstring 은 "`python scripts/<stem>.py` 형태의 실제 호출만
    인정한다" 고 단언했으나 구현에 `python` 요구가 없었다(observer-lie). 그래서 주석이 아닌
    `echo scripts/check_x.py` 데코이는 그대로 통과했다. 실측: ci.yml 의 실호출을 echo 로 바꿔도
    `tests/unit/scripts`+`tests/unit/hooks` 498건이 전부 초록(뮤테이션 GROK-20260731-2).
    이제 판정은 `tests/unit/scripts/_wiring_shape.surface_invokes` — **명령어가 인터프리터인지** 구조 판정한다.
    Third hardening: the regex still matched a bare path token, so a non-comment `echo` decoy passed.
    """
    paths = (f"scripts/{stem}.py", f".claude/hooks/{stem}.py")
    return [
        name for name, text in surfaces.items()
        if any(surface_invokes(text, path) for path in paths)
    ]


def _dead_hook_references(settings_text: str) -> list[str]:
    """settings 텍스트가 참조하는 `.claude/hooks/<name>.py` 중 **실파일이 없는** 것.

    죽은 배선(존재하지 않는 훅을 settings 가 참조) 탐지 — 실파일 대조(tautology 아님).
    """
    names = re.findall(r"\.claude/hooks/([A-Za-z0-9_]+)\.py", settings_text)
    return [n for n in names if not (_HOOKS / f"{n}.py").is_file()]


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


def test_settings_json_referenced_hooks_resolve_to_real_files():
    """🔴 settings.json 이 참조하는 훅 파일이 실제로 존재하는가 — 죽은 배선(부재 훅 참조) 차단.

    이전 판은 `for hook in _HOOKS.glob(): assert hook.is_file()` 로 **항상 참**(tautological) —
    글롭으로 찾은 파일이 존재하는지 묻는 공허한 단언이라 죽은 배선을 전혀 못 잡았다(감사 self-defect).
    이제 settings.json 텍스트에서 `.claude/hooks/<name>.py` 참조를 추출해 실파일 대조.
    """
    raw = (_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8")
    json.loads(raw)  # 유효 JSON 확인
    referenced = re.findall(r"\.claude/hooks/([A-Za-z0-9_]+)\.py", raw)
    assert referenced, "settings.json 이 훅을 하나도 참조 안 함 — 전제 붕괴(대조군)"
    dead = _dead_hook_references(raw)
    assert not dead, f"settings.json 이 존재하지 않는 훅을 참조(죽은 배선): {dead}"


def test_dead_hook_reference_detector_catches_missing():
    """🔴 죽은-배선 탐지기가 공허하지 않은지 — 부재 훅 참조를 실제로 잡는가(뮤테이션).

    tautological 판을 대체한 탐지기가 진짜 죽은 배선을 잡는지 합성 참조로 실증.
    """
    synthetic = '{"command": "python .claude/hooks/nonexistent_xyz_hook.py"}'
    assert _dead_hook_references(synthetic) == ["nonexistent_xyz_hook"], (
        "존재하지 않는 훅 참조를 탐지 못함 — 탐지기가 공허"
    )


def test_wiring_detection_requires_invocation_not_mention():
    """🔴 주석/설명이 가드 이름을 언급만 해도 '배선됨' 으로 잡으면 안 된다 (Grok 최종 검증).

    이 파일이 강제하려는 fail-open anti-pattern 을 가드 자신이 범하지 않았는지 자가 검증.
    """
    surfaces = {"ci": "# check_fake_guard.py 는 중요하다(주석뿐, 실제 호출 없음)"}
    assert _wired_surfaces("check_fake_guard", surfaces) == [], (
        "주석 언급만으로 배선으로 오판됐다 — substring anti-pattern 재발"
    )
    real = {"ci": "run: python scripts/check_fake_guard.py"}
    assert _wired_surfaces("check_fake_guard", real) == ["ci"], "실제 호출을 배선으로 못 잡았다"


@pytest.mark.parametrize("decoy", [
    "      - run: echo scripts/check_fake_guard.py",
    "      - run: true  # scripts/check_fake_guard.py",
    "      - run: cat scripts/check_fake_guard.py",
    '{"hooks": [{"command": "echo \'skipping .claude/hooks/check_fake_guard.py\'"}]}',
])
def test_wiring_detection_rejects_non_comment_decoy(decoy):
    """🔴 **주석이 아닌** 비실행 데코이도 배선 아님 — 실행자 앵커 봉인(2026-07-31).

    이전 두 차례 강화(substring→경로토큰, +주석제거)는 **주석 축만** 막아, `echo <경로>` 처럼
    주석이 아니면서 실행하지 않는 형태를 통과시켰다. 자가검증의 부정 통제가 주석 사례뿐이라
    이 구멍을 볼 수 없었다(양성 대조군만 `python` 을 포함).
    Non-comment, non-executing decoys must also fail: the prior negative control only tested comments.
    """
    assert _wired_surfaces("check_fake_guard", {"ci": decoy}) == [], (
        f"비실행 데코이를 배선으로 오판 — fail-open 재발: {decoy!r}"
    )


def test_wiring_detection_ignores_full_path_in_comment():
    """🔴 주석 안에 **전체 경로**가 있어도 배선으로 오판 안 함 — path-comment fail-open 봉인.

    이전 판은 `scripts/<stem>.py` 를 텍스트 어디서든(주석 포함) 찾아, `# TODO: wire
    scripts/check_x.py` 같은 언급도 '배선됨' 으로 셌다 — 이 파일이 막으려는 바로 그 anti-pattern.
    """
    commented = {"ci": "        # TODO: wire scripts/check_fake_guard.py 나중에\n"}
    assert _wired_surfaces("check_fake_guard", commented) == [], (
        "주석 안 전체 경로를 배선으로 오판 — path-comment fail-open"
    )
    # 대조군: 인라인 주석이 붙어도 실제 run: 호출은 배선으로 인정
    inline = {"ci": "        run: python scripts/check_fake_guard.py  # 실행\n"}
    assert _wired_surfaces("check_fake_guard", inline) == ["ci"], (
        "인라인 주석 제거가 실제 호출까지 지웠다 — 과제거"
    )
