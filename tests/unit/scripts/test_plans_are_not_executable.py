"""실행 지시 어휘를 담은 문서가 **"지금 실행하라"** 로 읽히지 않는지.

끝난 계획·설계 트리는 디스크에 두지 않는다. 살아 있는 마크다운에 cue 가 있으면
do-not-execute 표지 또는 인용 면제 마커가 있어야 한다.

Completed-plan trees are gone. The remaining axis is the global cue scan.
"""
import re
import subprocess  # nosec B404
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]

# 실행 지시로 읽히는 어휘 — 이게 있으면 에이전트가 실행 대상으로 오인한다.
_EXECUTION_CUE = re.compile(
    r"executing-plans|subagent-driven-development|task-by-task|REQUIRED SUB-SKILL"
)
# 완료 표지 — "실행 금지" 를 명시해야 인정한다.
_DONE_MARKER = re.compile(r"실행 대상이 아닙니다|do not execute", re.IGNORECASE)

# 미체크가 이 수 이상이면 "남은 일 목록" 으로 읽힌다.
_UNCHECKED_THRESHOLD = 5

# 🔴 인용 면제 — 실행 지시 어휘를 **서술로** 쓰는 문서(사이클 서사 등)를 위한 유일한 출구.
# 사유 없는 빈 마커는 자기발급이므로 **10자 이상**을 요구한다
# (`check_claim_review_trace._EXEMPT` · `check_test_count_sync._DEFERRED` 와 같은 관용구).
#
# 🔴 **정직 기준 — 이것은 길이만 잰다** (Grok claim-review `019ff074` 적발):
# `xxxxxxxxxxxx` 같은 무의미한 10자도 통과한다. 즉 이 요구가 막는 것은 **빈 마커 자기발급**
# 하나뿐이고, *"사유가 타당한가"* 는 판정하지 않는다 — 자유 산문의 진위는 정적으로 잴 수 없다
# (`check_claim_review_trace` 가 자기 한계로 적어 둔 것과 같은 축). 위조 비용을 올릴 뿐이다.
# Length-only: it stops the empty self-issued marker, not a bad-faith reason.
_CUE_QUOTE_EXEMPT = re.compile(r"<!--\s*guard-cue-quote:\s*\S[^>]{10,}?-->")


_RETIRED_PLAN_TREES = ("docs/_archive", "docs/design")


def _plan_docs():
    """퇴역한 계획 트리에 추적 마크다운이 남아 있으면 목록에 담는다.

    2026-08-16 이후 이 목록은 비어 있어야 한다. 다시 채워지면 이력 트리가 부활한 것이다.
    """
    tracked = _tracked_md() or []
    return [rel for rel in tracked if rel.startswith(_RETIRED_PLAN_TREES)]


def test_retired_plan_trees_are_gone():
    """🔴 끝난 계획·설계 트리는 디스크에 두지 않는다 — 빈 분모를 채점하지 않기 위해."""
    leftover = _plan_docs()
    assert leftover == [], (
        f"퇴역한 계획 트리가 남아 있다: {leftover}\n"
        "→ 끝난 이력은 지우고, 이 목록을 다시 채점 대상으로 만들지 말 것."
    )


def test_done_marker_is_not_satisfied_by_a_date_alone():
    """🔴 표지 판정이 공허하지 않은지 — 날짜나 '완료' 단어만으로는 통과하면 안 된다."""
    assert not _DONE_MARKER.search("2026-08-01 완료된 작업입니다")
    assert _DONE_MARKER.search("🔴 완료된 이력 문서입니다 — 실행 대상이 아닙니다.")
    assert _DONE_MARKER.search("Completed historical record — do not execute.")


# ── cue 축 전역화 (2026-08-11 문서 감사 PR-1) ────────────────────────────
#
# ## 왜 전역인가 (실측)
#
# 계획 배치는 2026-08-16 에 퇴역했다. 남은 축은 **전역 cue 스캔**이다.
#
# 🔴 실제 위험: 그 문서들은 최상단에 *"REQUIRED SUB-SKILL: Use superpowers:executing-plans
# to implement this plan task-by-task"* 를 그대로 달고 있고, 미체크 박스가 최대 87개다.
# 에이전트가 열면 **완료된 과거 계획을 지금 실행할 일감으로 읽는다**.
#
# ## 두 축을 분리하는 이유
#
# - `cue`(실행 지시 어휘) = **전역**. 어디에 있든 위험하다.
# - `unchecked>=5`(남은 일 목록) = **계획 배치 한정**. 전역화하면 살아있는 운영 체크리스트
#   (`.claude/policies/active.md`·`docs/runbooks/rls-role-separation.md` 등)에까지
#   "실행하지 마라" 를 붙이게 된다 — 감사가 오탐으로 지목한 축이다.
#
# ## 인용 면제
#
# 🔴 면제는 **명시 마커로만** 성립한다 — 산문 판정으로 예외를 만들면 다음 사람이
# 아무 문서에나 어휘를 넣고 빠져나간다.



def _tracked_md():
    """git 이 **추적하는** .md 만 — 스캔을 머신 독립으로 만든다.

    🔴 왜 필요한가 (2026-08-11 실행 중 발견): `docs/superpowers/` 는 `.gitignore:82` 로
    무시된다. 그 안의 계획 문서를 그냥 rglob 로 훑으면 가드가 **로컬에서만 red 이고 CI 는
    그 파일을 보지도 못한다** — 결과가 머신마다 갈리는 가드는 결정론적이지 않다.
    (backlog R30 이 기록한 로컬↔CI 이원의 파일 존재 축 판.)

    🔴 `git ls-files` 는 **중복 제거 의무** — 머지 충돌 중에는 같은 경로를 3-stage 로
    출력해 개수가 부풀려진다([[feedback-measurement-tool-lies-before-you-do]] 의 실사고).
    Only git-tracked files, deduped: ls-files emits 3 stages per conflicted path.
    """
    try:
        out = subprocess.run(  # nosec B603 B607
            ["git", "ls-files", "-z", "--", "*.md"],
            cwd=str(_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return sorted({x for x in (out.stdout or "").split("\0") if x.strip()})


def _scan_targets():
    """스캔 대상 = **git 이 추적하는 전 마크다운**. git 불가 시 rglob 폴백(더 넓다 = fail-closed).

    🔴 왜 전 리포인가 (Grok claim-review `019ff074` 가 초판을 BROKEN 으로 반증):
    초판은 `("docs", ".claude")` 두 디렉토리로 한정해 놓고 주석에는 *"리포 어디에 있든"*
    이라 적었다 — 리포 루트·`e2e/`·`scripts/`·`tests/` 의 `*.md` 는 아예 보지 않았다.
    지금은 그 밖 cue 가 0이라 **잠복**이지만, **주석이 코드보다 넓은 약속을 하는 것**이
    이 리포가 반복해 온 형태다. 범위 자체는
    `test_scan_covers_the_whole_repo_not_just_two_directories` 가 구조로 고정한다.
    """
    tracked = _tracked_md()
    if tracked is not None:
        return tracked
    return sorted(
        p.relative_to(_ROOT).as_posix()
        for p in _ROOT.rglob("*.md")
        if ".git" not in p.parts and "node_modules" not in p.parts
    )


def _cue_docs():
    """실행 지시 어휘를 **자기 문장으로** 담았는데 do-not-execute 표지가 없는 문서."""
    out = []
    for rel in _scan_targets():
        p = _ROOT / rel
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")
            if not _EXECUTION_CUE.search(text):
                continue
            if _DONE_MARKER.search(text) or _CUE_QUOTE_EXEMPT.search(text):
                continue
            out.append(p.relative_to(_ROOT).as_posix())
    return out


def test_cue_axis_is_global():
    """🔴 실행 지시 어휘를 담은 문서는 **리포 어디에 있든** do-not-execute 표지를 갖는다."""
    offenders = _cue_docs()
    assert not offenders, (
        f"실행 지시 어휘를 가졌는데 표지가 없는 문서 {len(offenders)}건 — "
        f"에이전트가 완료된 계획을 실행 일감으로 오인한다:\n  " + "\n  ".join(offenders)
    )


def test_cue_scan_is_not_vacuous():
    """🔴 대조군 — 전역 스캔이 조용히 좁아지면 위 단언이 공허해진다.

    2026-08-16 이력 퇴역 후 실행 지시 어휘를 담던 문서가 디스크에서 사라졌다.
    cue 건수 하한은 더 이상 분모가 아니다(0건이 현재 측정). 대신 **스캔 대상 수**를
    고정한다 — 스캔이 docs/.claude 두 칸으로 줄면 red 다.
    """
    targets = [rel for rel in _scan_targets() if (_ROOT / rel).is_file()]
    assert len(targets) >= 40, f"스캔 대상이 {len(targets)}개다 — 범위 붕괴"


def test_quotation_is_exempt_only_with_marker():
    """🔴 인용 면제는 **마커가 하중을 받는다** — 마커를 지우면 면제가 풀려야 한다.

    이력 트리가 없어진 뒤로는 실물 픽스처를 쓰지 않는다. 인라인 문자열로
    마커 유무만 가른다.
    """
    text = (
        "<!-- guard-cue-quote: 아래는 실행 지시 어휘를 증거로 인용한다 -->\n"
        "Use superpowers:executing-plans to implement this plan task-by-task.\n"
    )
    assert _EXECUTION_CUE.search(text)
    assert _CUE_QUOTE_EXEMPT.search(text)
    mutated = _CUE_QUOTE_EXEMPT.sub("", text)
    assert mutated != text
    assert not _CUE_QUOTE_EXEMPT.search(mutated)
    assert not _DONE_MARKER.search(mutated)


def test_cue_exemption_requires_a_real_reason():
    """🔴 빈 마커로 빠져나갈 수 없다 — 사유 없는 면제는 자기발급이다."""
    assert not _CUE_QUOTE_EXEMPT.search("<!-- guard-cue-quote: -->")
    assert not _CUE_QUOTE_EXEMPT.search("<!-- guard-cue-quote: x -->")
    assert _CUE_QUOTE_EXEMPT.search("<!-- guard-cue-quote: 과거 사이클 흐름 서술이며 지시가 아니다 -->")


def test_unchecked_axis_stays_in_plan_dirs():
    """🔴 오탐 회귀 가드 — `unchecked` 축을 전역화하면 **살아있는 운영 문서**가 걸린다.

    감사가 지목한 실제 오탐 대상으로 고정한다. 이 단언이 깨지면 누군가 축을 전역화한 것이다.
    """
    live = [
        _ROOT / ".claude" / "policies" / "active.md",
        _ROOT / "docs" / "runbooks" / "rls-role-separation.md",
    ]
    for p in live:
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        unchecked = len(re.findall(r"^\s*- \[ \]", text, re.MULTILINE))
        rel = p.relative_to(_ROOT).as_posix()
        if unchecked >= _UNCHECKED_THRESHOLD:
            assert rel not in _plan_docs(), (
                f"{rel} 이 계획 배치 스캔에 들어왔다 — 살아있는 체크리스트에 "
                "'실행하지 마라' 를 붙이게 된다"
            )


def test_cue_scan_ignores_untracked_files():
    """🔴 머신 독립 — git 이 무시하는 경로는 스캔에 들어오지 않는다.

    `docs/superpowers/` 는 `.gitignore:82` 로 무시된다. 그 안의 파일이 스캔에 들어오면
    이 가드는 **로컬에서만 red 이고 CI 에서는 존재조차 하지 않는** 상태가 된다.
    """
    tracked = _tracked_md()
    if tracked is None:
        pytest.skip("git 사용 불가 — 이 축은 판정 불가(스캔은 rglob 로 폴백)")
    assert not any(x.startswith("docs/superpowers/") for x in tracked), (
        "gitignore 대상이 tracked 목록에 있다 — 전제가 바뀌었다"
    )
    for offender in _cue_docs():
        assert offender in tracked, f"미추적 파일이 위반으로 발행됐다: {offender}"


def test_scan_covers_the_whole_repo_not_just_two_directories():
    """🔴 확대가 **관측되는지** — 지금은 `docs`·`.claude` 밖 cue 가 0이라 행동 차이가 없다.

    그래서 행동 단언만으로는 스캔을 다시 2배치로 좁혀도 초록이다(뮤테이션 M4 실측).
    범위 자체를 구조로 고정한다 — 초판이 *"리포 어디에 있든"* 이라 적어 놓고 두 디렉토리만
    보던 것이 이 가드가 고치려는 결함이었다(Grok claim-review `019ff074`).
    """
    targets = _scan_targets()
    outside = [x for x in targets if not x.startswith(("docs/", ".claude/"))]
    assert outside, "스캔이 docs/.claude 로 좁아졌다 — 루트·e2e·scripts·tests 의 md 를 못 본다"
    assert "CLAUDE.md" in targets, "리포 루트 마크다운이 스캔 대상에서 빠졌다"
