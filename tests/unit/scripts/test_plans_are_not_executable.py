"""완료된 계획 문서가 **"지금 실행하라"** 로 읽히지 않는지 — 재구현 사고 차단.

## 사고 (2026-08-01 문서 감사, 91 에이전트 · 167 파일)

`.claude/plans/` 9개 문서 중 **7개**가 최상단에 이런 배너를 갖고 있었다:

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement
> this plan **task-by-task**. Steps use checkbox (`- [ ]`) syntax for tracking.

그런데 그 계획들이 다루는 기능(Phase 1 MVP · AI 리뷰 · Gate 엔진 · 대시보드 · OAuth …)은
**이미 전부 출시돼 운영 중**이다. 그리고 9 파일에 **미체크 스텝이 359개** 남아 있다 —
완료 시점에 체크를 되돌려 적지 않았기 때문이다.

🔴 **행동 영향**: 미래 세션이 `.claude/plans/` 를 열면 "REQUIRED: task-by-task 로 구현하라"
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


def _plan_docs():
    out = []
    for base in (".claude/plans", "docs/design"):
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
