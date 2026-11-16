#!/usr/bin/env python3
"""문서 총량 가드 — 이 PR 이 문서 총 글자 수를 늘렸으면 본문에 그 결정을 적게 한다 (회고 원장 L18 P2-4 · P2-16 · 사용자 11-16 결정).

CLAUDE.md «문서 총량은 늘리지 않는다» 를 재는 곳이 없어, 한 창에서 +815자가 늘었고 9 PR 이 순증이었다(넷은 «뺀 것 없음»).

- 범위 = 추적 `.md` 가운데 `docs/reports/` · `.claude/` · `tests/` · `e2e/` 밖 — 회고가 잰 묶음이다. 보고서(이력) ·
  에이전트 지시 · 시험 픽스처는 «문서 총량» 이 아니다.
- 잰다 = 병합 기점과 HEAD 의 그 묶음 총 글자 수(UTF-8 로 읽은 문자 수).
- 같거나 줄었으면 통과. 늘었으면 PR 본문 줄 맨 앞(들여쓰기 허용, 인용부호 없이)에
  `doc-growth: <무엇을 뺐고 왜 늘었는가 — 16자 이상>` 이 있어야 통과한다. 자리표시자(`<…>`) · HTML 주석 안은 인정하지 않는다.
- PR 맥락(본문 · base/head)이 없으면(로컬 · push) 재지 않는다 — 로컬 게이트는 «안 잼» 으로 찍는다.

Doc-total gate: if this PR grows the tracked documentation, the PR body must say why (`doc-growth:`).
"""
from __future__ import annotations

import os
import re
import subprocess  # nosec B404 — git 만, 인자는 이 파일의 상수 + 커밋 이름
import sys
from pathlib import Path

# 🔴 PR 본문은 **단일 리더**를 통해서만 읽는다 — 원문을 정규식에 넘기면 HTML 주석 안 표지가
# 「리뷰어 비가시 + 게이트 통과」를 성립시킨다. 단일성 강제: `tests/unit/scripts/test_pr_body_single_reader.py`.
# Read the PR body only through the single hardened reader.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_claim_review_trace import (  # noqa: E402  # pylint: disable=wrong-import-position
    read_pr_body,
)

# 총량에 들지 않는 곳 — 이력(보고서) · 에이전트 지시 · 시험 / not part of the documentation total
_EXCLUDED = ("docs/reports/", ".claude/", "tests/", "e2e/")
# 사유 줄 — 줄 맨 앞(들여쓰기 허용) · 인용부호로 시작하지 않음 · 자리표시자(`<…>`)가 아님 · 16자 이상
# The reason line: at line start, not quoted, not a `<placeholder>`, at least 16 characters.
MARKER = re.compile(r"^[ \t]*(?![`'\"])doc-growth\s*:\s*(?!<)\S.{15,}", re.MULTILINE)


def _make_stdout_safe() -> None:
    """Windows cp949 stdout 에서 이모지/한글 출력 크래시 방지 — UTF-8 재구성(errors=replace).
    Guard against the cp949 emoji/Korean print crash on Windows (UTF-8, replace on miss)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 재구성 불가한 스트림(파이프·구버전) — 출력 인코딩은 최선 노력 / best-effort only


def _git(*args: str) -> str:
    """git → stdout. 실패 시 **loud 종료**(fail-CLOSED) — 빈 출력을 «문서 0자» 로 읽지 않게.

    🔴 **PARITY GUARD** — 형제 가드들과 같은 계약이다(`tests/unit/scripts/test_guard_git_failclosed.py`).
    Fail-closed git helper shared in contract with the sibling guards.
    """
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=False,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print(f"🔴 git 실패 — 가드 실행 불가 (fail-closed): git {' '.join(args)}")
        print(f"   {(result.stderr or '').strip()[:300]}")
        sys.exit(2)
    return result.stdout or ""


def counts(path: str) -> bool:
    """그 추적 경로가 문서 총량에 드는가. / Whether a tracked path counts toward the documentation total."""
    return path.endswith(".md") and not path.startswith(_EXCLUDED)


def doc_chars(rev: str) -> dict[str, int]:
    """그 커밋의 문서별 글자 수 — 총량에 드는 추적 `.md` 만."""
    names = [n for n in _git("ls-tree", "-r", "-z", "--name-only", rev).split("\0") if n]
    return {name: len(_git("show", f"{rev}:{name}")) for name in names if counts(name)}


def _append_step_summary(markdown: str) -> None:
    """job summary 에 한 줄 — 늘린 결정은 사람이 여는 자리에 남는다. 기록 실패는 판정을 바꾸지 않는다."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(markdown)
    except OSError:
        pass  # 기록 실패가 판정을 바꾸면 안 된다 / logging must never change the verdict


def main() -> int:
    _make_stdout_safe()
    base = (os.environ.get("PR_BASE_SHA") or "").strip()
    head = (os.environ.get("PR_HEAD_SHA") or "").strip()
    if not base and not head:
        print("⏭️ 문서 총량 — PR 맥락(본문 · base/head)이 없어 안 잼")
        return 0
    if not (base and head):
        print("🔴 PR 맥락이 반쪽이다(base 나 head 하나만 왔다) — 범위를 못 잰다(fail-closed)")
        return 1
    merge_base = _git("merge-base", base, head).strip()
    before, after = doc_chars(merge_base), doc_chars(head)
    if not after:
        print("🔴 문서 범위가 비었다 — 총량에 드는 추적 .md 를 하나도 못 읽었다(범위 붕괴 · fail-closed)")
        return 1
    total_before, total_after = sum(before.values()), sum(after.values())
    delta = total_after - total_before
    summary = (f"문서 총량 {total_before:,} → {total_after:,} ({delta:+,}자 · 추적 .md {len(after)}개, "
               "보고서 · .claude · 시험 제외)")
    if delta <= 0:
        print(f"✅ {summary} — 늘지 않았다")
        return 0
    grown = sorted(((after.get(p, 0) - before.get(p, 0), p) for p in set(before) | set(after)), reverse=True)
    reason = MARKER.search(read_pr_body())
    if reason:
        said = reason.group(0).split(":", 1)[1].strip()
        print(f"✅ {summary} — 본문의 사유: {said[:160]}")
        _append_step_summary(f"- 📏 **문서 총량 {delta:+,}자** — 사유: {said[:200]}\n")
        return 0
    print(f"🔴 {summary} — 늘었는데 본문에 `doc-growth:` 사유가 없다:")
    for d, p in grown:
        if d > 0:
            print(f"   + {p} {d:+,}")
    print("해결: 늘린 만큼 다른 곳을 줄이거나, PR 본문 줄 맨 앞(들여쓰기 허용, 인용부호 없이)에")
    print("   `doc-growth: <무엇을 뺐고 왜 늘었는가 — 16자 이상>` 을 적는다. HTML 주석 안은 인정되지 않는다.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
