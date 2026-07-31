"""lint 게이트가 **자동면에 실제로 배선**돼 있는지 + 메모리 참조 무결성.

## 사고 1 — "게이트 통과" 가 구조적으로 검증 불가였다 (회고 P2 D13)

`make lint` · `make gate`("Phase 완료 게이트") 가 pylint·flake8·bandit 를 전부 `|| true` 로
삼켜 **실패할 수 없었다**. 실패 가능한 `make lint-strict`(`--fail-under=9.90`)는 CI·pre-commit
어디에서도 호출되지 않는 **문서-only** 였다. 그 상태에서 `CLAUDE.md` 는
*"Phase 완료 조건 = /lint 통과"* 를 선언했다 — 커밋 본문의 "lint 통과" 주장이 **기계로
검증 불가**했던 것이다.

🔴 **Grok 적대 검토(2026-07-20)가 내 첫 처방을 반증했다.** 나는 Makefile 의 `|| true` 를 떼는
것이 답이라고 봤으나:
  · **로컬 fail-closed 는 강제력이 아니라 마찰**이다 — CI 가 요구하지 않는 스타일 위반으로
    Phase 의식이 막히면, 에이전트는 `make gate` 를 **아예 안 쓰게** 된다(의식 붕괴).
  · 진짜 간극은 Makefile 이 아니라 **CI 배선 부재**였다. 로컬 exit code 는 사후 검토 불가라
    "lint 통과" 는 여전히 자기 신고로 남는다.
→ 게이트를 **CI job `lint-src`** 에 두고, 이 파일이 그 배선을 단언한다.

## 사고 2 — 존재하지 않는 메모리 파일 참조 (회고 P2 D9)

`check_memory_refs.py` 의 스코프가 3개 문서 한정이라 그 밖의 dangling 2건이 살아 있었다.
미래 세션이 없는 메모리를 읽으려 한다.
"""
import re
from pathlib import Path

import yaml

from scripts.check_memory_refs import normalize, resolve_memory_dir

_ROOT = Path(__file__).resolve().parents[3]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"
_MAKEFILE = _ROOT / "Makefile"
# 🔴 하드코딩 금지 (2026-07-31 회고 P0-8) — 이전 판은 구 PC 슬러그(`d--Source-SCAManager`)를
#   박아 두어 이 테스트가 **모든 환경에서 skip** 됐다: CI 는 메모리 디렉토리가 원래 없어 skip 이
#   설계이고, 유일하게 돌아야 할 로컬에서는 경로가 틀려 skip. 그 사이 dangling 참조 5건이
#   누적됐고 그중 하나는 CLAUDE.md 가 자기 정책 근거로 인용하는 메모리였다.
#   가드와 동일한 유도 로직을 재사용해 drift 를 한 곳으로 모은다.
# The old hardcoded slug made this skip on every machine; reuse the guard's own resolution.
_MEMORY = resolve_memory_dir(_ROOT)

# 🔴 모듈 레벨로 뺀 이유 (2026-07-31): 아래 dangling 스캔은 **리포 상태** 단언이라 탐지기가
#   좁아져도 잡을 대상이 없으면 그대로 초록이다 — 실측으로 확인했다(패턴을 하이픈 전용으로
#   되돌리는 뮤테이션이 GREEN). 탐지기 자신을 검증하려면 패턴이 테스트 가능해야 한다.
# Hoisted to module scope: the repo-state assertion below cannot prove the detector works —
# narrowing the pattern stayed green because nothing dangling remained to catch.
_MEMORY_REF_RE = re.compile(
    r"`((?:feedback|project|user)[-_][\w-]+)\.md`"
    r"|\[\[((?:feedback|project|user)[-_][\w-]+)\]\]"
)


def memory_refs(line: str) -> list[str]:
    """한 줄에서 메모리 슬러그 참조를 추출한다(백틱·wiki-link 양쪽).
    Extract memory slug references from one line, in either notation."""
    return [m.group(1) or m.group(2) for m in _MEMORY_REF_RE.finditer(line)]


def _ci_jobs() -> dict:
    return (yaml.safe_load(_CI.read_text(encoding="utf-8")) or {}).get("jobs", {})


def _run_commands(job: dict) -> str:
    return "\n".join(str(s.get("run", "")) for s in job.get("steps", []) or [])


# ── CI 배선 (강제면) ────────────────────────────────────────────────────


def test_pylint_floor_is_enforced_by_a_ci_job():
    """🔴 pylint 회귀 가드가 **CI 에서** 돌아야 한다 — 로컬 타깃은 근거가 아니다.

    이전엔 `lint-strict` 가 문서에만 있었고 어떤 job 도 부르지 않았다.
    """
    hits = [
        name for name, job in _ci_jobs().items()
        if re.search(r"pylint\s+--fail-under", _run_commands(job))
    ]
    assert hits, (
        "pylint --fail-under 을 실행하는 CI job 이 없다 — "
        "'lint 통과' 주장이 기계로 검증 불가한 상태로 되돌아갔다"
    )


def test_bandit_runs_on_src_in_ci():
    """🔴 bandit 은 이전에 **어떤 자동면에도 없었다** — 보안 정적분석이 통째로 미게이트였다."""
    hits = [
        name for name, job in _ci_jobs().items()
        if re.search(r"bandit\s+-r\s+src/", _run_commands(job))
    ]
    assert hits, "bandit 을 src/ 에 실행하는 CI job 이 없다"


def test_gate_target_can_actually_fail():
    """🔴 `make gate` 는 이름이 게이트다 — **실패할 수 있어야** 한다.

    `|| true` 로 삼키면 "게이트 통과" 보고가 아무것도 보장하지 않는다.
    (최종 강제면은 CI 지만, 이름과 동작이 어긋나면 그 자체가 거짓 신호다.)
    """
    text = _MAKEFILE.read_text(encoding="utf-8")
    m = re.search(r"^gate:\n((?:\t.*\n)+)", text, re.M)
    assert m, "gate 타깃을 찾을 수 없다 — Makefile 형식 확인"
    recipe = m.group(1)
    swallowed = [ln.strip() for ln in recipe.splitlines() if "|| true" in ln]
    assert not swallowed, (
        f"gate 레시피가 실패를 삼킨다: {swallowed}\n"
        "→ 게이트라고 이름 붙인 타깃은 실패할 수 있어야 한다."
    )
    assert "pytest" in recipe and "pylint" in recipe, f"gate 가 비었다: {recipe!r}"


def test_lint_target_is_documented_as_advisory():
    """대조군 — `lint` 는 **점검**이라 `|| true` 가 의도다. 그 의도가 문서화돼야 한다.

    의도가 안 적히면 다음 세션이 "게이트인데 왜 안 막지?" 로 오해하거나,
    반대로 무심코 fail-closed 로 바꿔 Grok 이 경고한 마찰을 만든다.
    """
    text = _MAKEFILE.read_text(encoding="utf-8")
    head = text[: text.index("\nlint:")]
    assert "advisory" in head or "게이트가 아니다" in head, (
        "`lint` 타깃이 advisory(비게이트)라는 설명이 없다"
    )


# ── 메모리 참조 무결성 (스코프 밖 dangling) ─────────────────────────────


def test_no_dangling_memory_references_in_repo():
    """🔴 저장소가 **존재하지 않는 메모리 파일**을 가리키면 안 된다.

    `check_memory_refs.py` 는 3개 문서만 보므로 그 밖에서 dangling 이 살아남았다(실측 2건).
    여기서는 저장소 전역을 훑되, **취소선으로 소실을 명시한 참조는 허용**한다 —
    조용한 dangling 과 명시된 손실은 다르다.
    """
    if _MEMORY is None or not _MEMORY.is_dir():  # 다른 머신/CI — 메모리 디렉토리 부재 시 판정 불가
        import pytest
        pytest.skip("메모리 디렉토리 없음 — 이 검사는 로컬 전용")

    # 🔴 정규화 비교 + 두 표기 모두 인식 (Grok claim-review F6, 실측 재현).
    #   초판 패턴은 `feedback-` 만 받아 **실제 파일 표기인 `feedback_*.md` 와 wiki-link 를 통째로
    #   못 봤다** — 가드 본체(`check_memory_refs`)는 둘 다 보는데 이 테스트만 눈이 멀어 있었다.
    # The old pattern matched only the hyphen form, so the live `feedback_*.md` files and every
    # wiki-link were invisible here while the guard itself handled both.
    existing = {normalize(p.stem) for p in _MEMORY.glob("*.md")}
    dangling = []
    for path in _ROOT.rglob("*"):
        if path.suffix not in (".md", ".py") or ".git" in path.parts:
            continue
        # 🔴 `.claude/worktrees/` 만 제외한다 — git worktree 는 **같은 파일의 사본**이라 위반을
        #   중복 보고한다(실측 2026-07-31: `.claude/worktrees/fix-wiring/…` 가 본체와 동일 항목을
        #   한 번 더 냈다). 회고 P1 "루트 grep 100% 인플레" 가 가드 안에서 구체화된 형태다.
        #   🔴 초판은 `"worktrees" in path.parts` 라 `docs/worktrees/` 같은 **정당한 경로도 통째로
        #   제외**했다(Grok claim-review F7) — 화장용 중복 제거를 위해 실제 커버리지를 팔았던 것이라
        #   경로 접두사로 좁힌다.
        # Exclude only `.claude/worktrees/`: the bare segment match also dropped legitimate paths,
        # trading real coverage for cosmetic dedup.
        rel_parts = path.relative_to(_ROOT).parts
        if rel_parts[:2] == (".claude", "worktrees"):
            continue
        # 🔴 아카이브는 제외한다 — **append-only 역사 기록**이라 작성 시점엔 참이었고,
        #   지금 와서 고치면 그때의 사실 관계를 왜곡한다(저장소의 기존 원칙: 과거 서사 보존).
        #   실측: 아카이브 1개 파일에만 13건이 있었고 전부 이 성격이다. 이걸 위반으로 신고하면
        #   가드가 '고칠 수 없는 것'을 계속 요구하게 되고, 그러면 사람이 가드를 끈다.
        # Archives are append-only history: true when written, and rewriting them falsifies the record.
        if any(part.startswith("_archive") for part in path.parts):
            continue
        # `cycle-history.md` 도 동일 성격 — 사이클별 **과거 서사**를 append-only 로 쌓는 파일이다
        #   (저장소 원칙: 과거 narrative 보존, LIVE 수치만 정정). 아카이브 디렉토리에 있지 않을 뿐이다.
        # Same append-only history semantics as _archive, just not under that directory.
        if path.name == "cycle-history.md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line in text.splitlines():
            if "~~" in line:          # 소실을 명시한 참조는 허용 / explicitly-marked loss is fine
                continue
            for slug in memory_refs(line):
                if normalize(slug) not in existing:
                    dangling.append(f"{path.relative_to(_ROOT).as_posix()} → {slug}.md")
    assert not dangling, (
        "존재하지 않는 메모리 파일 참조:\n  " + "\n  ".join(sorted(set(dangling))) +
        "\n→ 실재하는 메모리로 바꾸거나, 소실이면 취소선으로 **명시**할 것."
    )


# ── 탐지기 자가 검증 (리포 상태와 무관하게 항상 유효) ────────────────────
# Detector self-check — valid regardless of current repo state.

_REF_HYPHEN = "feedback-" + "lost-thing"
_REF_UNDER = "feedback_" + "lost_thing"


def test_memory_ref_detector_catches_both_notations():
    """🔴 탐지기가 백틱 두 표기 + wiki-link 를 **전부** 잡는가.

    위 dangling 스캔은 리포 상태 단언이라, 잡을 대상이 없으면 탐지기가 좁아져도 초록이다
    (실측: 패턴을 하이픈 전용으로 되돌리는 뮤테이션이 GREEN 이었다). 그래서 탐지기 자신을
    합성 입력으로 검증한다 — 이 단언은 리포에 dangling 이 0건이어도 유효하다.
    The repo-state scan cannot prove the detector; a narrowed pattern stayed green because
    nothing dangling remained. This asserts the detector directly.
    """
    assert memory_refs(f"메모리 `{_REF_HYPHEN}.md` 참조") == [_REF_HYPHEN]
    assert memory_refs(f"메모리 `{_REF_UNDER}.md` 참조") == [_REF_UNDER]
    assert memory_refs(f"본문 [[{_REF_HYPHEN}]] 링크") == [_REF_HYPHEN]
    assert memory_refs(f"본문 [[{_REF_UNDER}]] 링크") == [_REF_UNDER]


def test_memory_ref_detector_ignores_unrelated_text():
    """대조군 — 아무 텍스트나 잡으면 탐지기가 공허하다(전건 오탐)."""
    assert memory_refs("일반 문장 `some-file.md` 와 [[not-a-memory]]") == []
    assert memory_refs("") == []
