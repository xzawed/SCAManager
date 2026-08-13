"""완료된 계획 문서가 **"지금 실행하라"** 로 읽히지 않는지 — 재구현 사고 차단.

## 사고 (2026-08-01 문서 감사, 91 에이전트 · 167 파일)

`docs/_archive/plans/` 9개 문서 중 **7개**가 최상단에 이런 배너를 갖고 있었다:

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement
> this plan **task-by-task**. Steps use checkbox (`- [ ]`) syntax for tracking.

그런데 그 계획들이 다루는 기능(Phase 1 MVP · AI 리뷰 · Gate 엔진 · 대시보드 · OAuth …)은
**이미 전부 출시돼 운영 중**이다. 그리고 9 파일에 **미체크 스텝이 359개** 남아 있다 —
완료 시점에 체크를 되돌려 적지 않았기 때문이다.

🔴 **행동 영향**: 미래 세션이 `docs/_archive/plans/` 를 열면 "REQUIRED: task-by-task 로 구현하라"
+ 미체크 359개를 보게 되고, **이미 있는 기능을 다시 만들기 시작할 수 있다.** 그리고 그 재구현은
기존 코드와 충돌하기 전까지 아무 가드도 울리지 않는다.

`docs/design/` 에도 같은 형태가 2건 있었다(미체크 53 · 32).

## 이 파일이 강제하는 것

미체크 체크박스가 많거나 실행 지시 어휘를 담은 계획 문서는 **완료 표지**를 최상단에 가져야 한다.
표지 문구는 "실행하지 마라" 를 명시해야 한다 — 날짜만 적는 것으로는 부족하다.

Completed plans must carry a do-not-execute banner; otherwise a future agent re-implements
shipped features from their unchecked checkboxes.
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


def _plan_docs():
    out = []
    # 🔴 2026-08-13 이동: `.claude/plans/` → `docs/_archive/plans/`
    #    (`.claude/` 를 **활성 설정만** 담는 공간으로 정리). 여기를 따라 옮기지 않으면
    #    스캐너가 9→3 으로 줄어 이 가드가 조용히 좁아진다 — 실제로 red 로 잡혔다.
    for base in ("docs/_archive/plans", "docs/design"):
        for p in sorted((_ROOT / base).rglob("*.md")):
            text = p.read_text(encoding="utf-8", errors="replace")
            unchecked = len(re.findall(r"^\s*- \[ \]", text, re.MULTILINE))
            if unchecked >= _UNCHECKED_THRESHOLD or _EXECUTION_CUE.search(text):
                out.append(p.relative_to(_ROOT).as_posix())
    return out


def test_the_scan_finds_plan_documents():
    """🔴 대조군 — 스캐너가 아무것도 못 찾으면 아래 단언이 공허하다."""
    docs = _plan_docs()
    assert len(docs) >= 9, f"계획 문서를 {len(docs)}개만 찾았다 — 스캐너 확인: {docs}"


@pytest.mark.parametrize("doc", _plan_docs())
def test_plan_document_declares_it_is_not_executable(doc):
    """🔴 실행 대상이 아니라면 **그렇게 적혀 있어야** 한다.

    이 단언이 깨지면 두 경우다:
      (a) 완료된 계획에 표지가 없다 → 표지를 추가하라.
      (b) 진짜로 지금 실행할 계획이다 → 그 문서는 `.claude/plans`/`docs/design` 이 아니라
          `docs/backlog.md`(할 일의 단일 출처)에 등재돼야 한다.
    """
    text = (_ROOT / doc).read_text(encoding="utf-8", errors="replace")
    unchecked = len(re.findall(r"^\s*- \[ \]", text, re.MULTILINE))
    assert _DONE_MARKER.search(text), (
        f"{doc} 에 완료 표지가 없다 (미체크 {unchecked}개"
        f"{', 실행 지시 어휘 포함' if _EXECUTION_CUE.search(text) else ''}).\n"
        "→ 미래 세션이 이 문서를 실행 대상으로 오인해 **이미 있는 기능을 다시 만든다**."
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
# 기존 스캐너는 `.claude/plans`·`docs/design` **2 배치만** 본다(`_plan_docs`). 그 안에서는
# 12건을 찾고 위반 0 = green 이다. 그런데 같은 술어를 `docs/**`+`.claude/**` 로 넓히면
# 후보 **36건**, 배너 없는 것 **24건**, 그중 실행 지시 어휘(cue)를 가진 것이 **14건**이다.
# 즉 가드가 초록인 이유는 리포가 안전해서가 아니라 **보는 범위가 좁아서**였다.
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
# `docs/cycle-history.md` 는 과거 사이클의 **작업 흐름을 서술**하며 어휘를 쓴다
# (`brainstorming→writing-plans→subagent-driven-development 흐름`). 지시가 아니다.
# 🔴 면제는 **명시 마커로만** 성립한다 — 산문 판정으로 예외를 만들면 다음 사람이
# 아무 문서에나 어휘를 넣고 빠져나간다([[feedback-prose-guard-both-ways]]).



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

    실측(2026-08-11): **전 추적 마크다운**에서 cue 를 담은 문서 **23건**.
    하한 **22** 는 실측 바로 아래다 — 초판의 20 은 3건이 사라져도 초록이라 여유가 과했다
    (Grok claim-review `019ff074` 적발). 스캔이 좁아지거나 문서가 조용히 사라지면 red 다.
    """
    scanned = [
        rel for rel in _scan_targets()
        if (_ROOT / rel).is_file()
        and _EXECUTION_CUE.search((_ROOT / rel).read_text(encoding="utf-8", errors="replace"))
    ]
    assert len(scanned) >= 22, f"cue 문서를 {len(scanned)}개만 찾았다 — 스캔 범위 붕괴"


def test_quotation_is_exempt_only_with_marker():
    """🔴 인용 면제는 **마커가 하중을 받는다** — 마커를 지우면 red 여야 한다 (뮤테이션).

    실행 지시 어휘를 **인용**하는 실물 문서로 실증한다 — 그 면제가 산문 판정이 아니라
    마커에 걸려 있음을 보인다.

    🔴 **픽스처가 2026-08-13 에 이동했다**: 원래는 `docs/cycle-history.md` 였으나 그 파일이
    320,800 → 81,416자로 압축되며 어휘를 담은 과거 사이클 143개가 아카이브로 접혔다.
    픽스처는 **인용 면제만으로 서 있는** 실물이어야 한다 — `실행 대상이 아닙니다` 표지를
    함께 든 문서는 면제가 중복이라 이 축을 증명하지 못한다(아래 `_DONE_MARKER` 단언).
    실측(2026-08-13) 결과 그 조건을 만족하는 유일한 문서가 이 감사 보고서다.
    """
    src = _ROOT / "docs" / "_archive" / "reports" / "2026-08-10-docs-system-audit.md"
    text = src.read_text(encoding="utf-8", errors="replace")
    assert _EXECUTION_CUE.search(text), f"전제가 깨졌다 — {src.name} 에 어휘가 없다"
    assert _CUE_QUOTE_EXEMPT.search(text), "인용 면제 마커가 없다"
    # 마커를 제거한 사본은 위반으로 판정돼야 한다.
    mutated = _CUE_QUOTE_EXEMPT.sub("", text)
    assert mutated != text
    assert not _CUE_QUOTE_EXEMPT.search(mutated), (
        "마커를 지웠는데도 면제가 성립한다 — 면제가 마커에 걸려 있지 않다"
    )
    assert not _DONE_MARKER.search(mutated), (
        "do-not-execute 표지가 따로 있다면 이 문서는 인용 면제가 필요 없다(면제가 공허)"
    )
    # 🔴 배선 — 정규식이 아니라 **실제 판정 경로**(`_cue_docs`)에서 면제가 작동하는지
    #    (Grok 지적: 초판은 정규식만 검사해 판정 경로를 한 번도 지나지 않았다).
    assert "docs/_archive/reports/2026-08-10-docs-system-audit.md" not in _cue_docs(), (
        "인용 면제가 실제 판정 경로에서 작동하지 않는다"
    )


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
