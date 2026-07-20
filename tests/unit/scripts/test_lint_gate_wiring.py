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

_ROOT = Path(__file__).resolve().parents[3]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"
_MAKEFILE = _ROOT / "Makefile"
_MEMORY = Path.home() / ".claude" / "projects" / "d--Source-SCAManager" / "memory"


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
    if not _MEMORY.is_dir():          # 다른 머신/CI — 메모리 디렉토리 부재 시 판정 불가
        import pytest
        pytest.skip("메모리 디렉토리 없음 — 이 검사는 로컬 전용")

    existing = {p.stem for p in _MEMORY.glob("*.md")}
    pattern = re.compile(r"`(feedback-[\w-]+|project[-_][\w-]+|user[-_][\w-]+)\.md`")
    dangling = []
    for path in _ROOT.rglob("*"):
        if path.suffix not in (".md", ".py") or ".git" in path.parts:
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
            for m in pattern.finditer(line):
                if m.group(1) not in existing:
                    dangling.append(f"{path.relative_to(_ROOT).as_posix()} → {m.group(1)}.md")
    assert not dangling, (
        "존재하지 않는 메모리 파일 참조:\n  " + "\n  ".join(sorted(set(dangling))) +
        "\n→ 실재하는 메모리로 바꾸거나, 소실이면 취소선으로 **명시**할 것."
    )
