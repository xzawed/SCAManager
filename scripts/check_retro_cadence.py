#!/usr/bin/env python3
"""회고 카덴스 카운터 — 직전 정식 회고 이후 머지 PR 수를 세어 임계 도달 시 loud 경고.
Retrospective cadence counter — counts merged PRs since the last formal retrospective and
warns loudly when the policy-8 trigger threshold is reached.

회고 2026-07-18 P0: 정책 8 진화 (4) 회고 카덴스 강제 트리거(#1028)가 **문서-only** 라 첫 측정창에서
자기 위반(~46 PR·5~6 세션 무회고, ~3x 임계). 2026-07-03 시정(문서 추가)이 행동을 못 바꿈 → 재발.
이 카운터는 인지 의존을 **측정 신호**로 전환한다 — 세션 시작 시 실행(작업 시작 전 필수 체크리스트).
Retro 2026-07-18 P0: the doc-only cadence trigger self-violated in its first measurement window;
the 2026-07-03 doc-only remedy failed to change behavior. This counter converts the reminder from
cognition-dependent to measured — run at session start (pre-work checklist).

🔴 비차단(advisory) — 항상 exit 0. 임계 도달 시 경고 배너만 출력(정책 17 안정성: 커밋/PR 미간섭).
Non-blocking (advisory) — always exit 0; prints a warning banner at threshold (policy 17 stability:
never interferes with commits/PRs, incl. the retrospective report PR itself).

사용법 / Usage: python scripts/check_retro_cadence.py
"""
import re
import subprocess
import sys
from pathlib import Path

# 직전 정식 회고 이후 머지 PR 이 이 수 이상이면 5+1 회고 진입 판정 (정책 8 진화 (4) — ≥15 PR).
# When merged PRs since the last formal retrospective reach this, a 5+1 retrospective is due.
RETRO_PR_THRESHOLD = 15

_REPORTS_DIR = Path("docs/_archive/reports")
# 정식 회고 파일명 = YYYY-MM-DD-...retrospective....md — 'retrospective' 미포함(감사·리뷰·기획안)은 제외.
# 🔴 2026-07-17-grok-full-review.md 같은 리뷰를 회고로 오인하면 카덴스가 잘못 리셋된다(본 회고 P0 근본).
# Formal-retro filename must contain 'retrospective'; audits/reviews/plans are excluded so a review
# is never mistaken for a retro (that mis-reset is the root of this cycle's P0 gap).
_RETRO_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})-.*retrospective.*\.md$")
# squash-merge PR 제목 = 끝에 (#NNNN). 본문 중간 #NN(이슈/감사 참조)은 미카운트(오버카운트 차단).
# squash-merge PR subject ends with (#NNNN); inline #NN refs are not counted (avoids over-counting).
_MERGE_PR = re.compile(r"\(#\d+\)\s*$")


def retro_date(filename):
    """정식 회고 파일명에서 날짜(YYYY-MM-DD) 추출 — 회고 아니면 None.
    Extract the date from a formal-retro filename; None if not a retrospective."""
    m = _RETRO_NAME.match(filename)
    return m.group(1) if m else None


def _retro_seq(filename):
    """같은 날 회고의 순번 — `-N.md` 접미사가 있으면 N, 없으면 1 (첫 회고).
    Sequence within a same-day set: `-N.md` suffix → N, otherwise 1 (the first).

    🔴 이게 없으면 날짜 tie 가 **파일명 ASCII 순**으로 깨진다. `-`(0x2D) < `.`(0x2E) 이므로
    `2026-07-19-retrospective.md` 가 `...-retrospective-2.md` 를 이겨 **더 오래된 회고**가
    최신으로 뽑혔다(2026-07-19 회고 P2 실측 — 경계가 6 PR 어긋남).
    Without this the same-date tie falls back to ASCII filename order and picks the OLDER retro.
    """
    m = re.search(r"-(\d+)\.md$", filename)
    return int(m.group(1)) if m else 1


def newest_retro(filenames):
    """정식 회고 파일명 목록에서 가장 최신 반환 — 없으면 None.
    Return the newest formal-retro filename, or None.

    정렬 키 = (날짜, 같은 날 순번). 파일명 문자열은 tie-break 에 **쓰지 않는다** —
    사전순은 최신성과 무관하고, 실제로 반대 방향으로 깨졌다(위 `_retro_seq` 주석 참조).
    Sorted by (date, same-day sequence); the filename string is never used as a tiebreaker.
    """
    dated = [(d, _retro_seq(f), f) for f in filenames if (d := retro_date(f))]
    return max(dated)[2] if dated else None


def count_merge_prs(subjects):
    """커밋 제목 목록에서 squash-merge PR (끝 (#NNNN)) 수 카운트.
    Count squash-merge PR subjects (those ending with (#NNNN))."""
    return sum(1 for s in subjects if _MERGE_PR.search(s))


def evaluate(pr_count, threshold=RETRO_PR_THRESHOLD):
    """(breached, message) — pr_count >= threshold 면 breached True (경계 포함).
    Return (breached, message); breached when pr_count >= threshold (boundary inclusive)."""
    breached = pr_count >= threshold
    if breached:
        message = (
            f"🔴 회고 카덴스 트리거 발화 — 직전 정식 회고 이후 머지 PR {pr_count} 건 "
            f"(임계 ≥{threshold}). 정책 8 진화 (4): 5+1 회고 진입 판정 (자기회고 갈음은 사용자 명시 승인 시에만). "
            f"/ Retro cadence trigger FIRED — {pr_count} merged PRs since last retro (>= {threshold})."
        )
    else:
        message = (
            f"✅ 회고 카덴스 여유 — 직전 정식 회고 이후 머지 PR {pr_count} 건 (임계 ≥{threshold}). "
            f"/ Retro cadence OK — {pr_count}/{threshold} PRs since last retro."
        )
    return breached, message


def _git(args):
    """git 서브프로세스 실행 — stdout 반환(실패 시 빈 문자열, advisory 특성).
    Run a git subprocess; return stdout ('' on failure — advisory tool must not crash a session)."""
    try:
        out = subprocess.run(
            ["git", *args], capture_output=True, text=True, check=False, encoding="utf-8"
        )
        return out.stdout or ""
    except OSError:
        return ""


def _boundary_commit(retro_filename):
    """정식 회고 리포트가 추가된 커밋 SHA — 카운트 경계. 미발견 시 None.
    The commit that added the retro report (count boundary); None if not found."""
    path = f"docs/_archive/reports/{retro_filename}"
    sha = _git(["log", "--diff-filter=A", "--format=%H", "-1", "--", path]).strip()
    return sha or None


def _make_stdout_safe():
    """Windows cp949 stdout 에서 이모지(🔴) 출력 크래시 방지 — UTF-8 재구성(errors=replace).
    Guard against the cp949 emoji-print crash on Windows local runs (UTF-8, replace on miss)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / stream without reconfigure


def main():
    """세션 시작 카덴스 점검 — 경고 배너 출력 후 항상 exit 0 (advisory)."""
    _make_stdout_safe()
    reports = _REPORTS_DIR
    if not reports.is_dir():
        print("ℹ️  회고 리포트 디렉토리 없음 — 카덴스 점검 skip / no reports dir")
        return 0
    newest = newest_retro([p.name for p in reports.glob("*.md")])
    if not newest:
        print("ℹ️  정식 회고 리포트 없음 — 카덴스 점검 skip / no formal retro report")
        return 0

    boundary = _boundary_commit(newest)
    if not boundary:
        print(f"ℹ️  {newest} 추가 커밋 미발견 — 카덴스 점검 skip (working tree?) / boundary commit not found")
        return 0

    subjects = _git(["log", "--format=%s", f"{boundary}..HEAD"]).splitlines()
    pr_count = count_merge_prs(subjects)
    # 🔴 breached 는 의도적으로 쓰지 않는다 — 이 도구는 **비차단 advisory** 라
    #   임계 초과여도 exit 0 이고, 판정은 배너를 읽은 Claude 가 한다.
    # Intentionally discarded: this tool is advisory (always exit 0); the banner is the signal.
    _breached, message = evaluate(pr_count)
    print(f"직전 정식 회고 / last formal retro: {newest}")
    print(message)
    # 비차단 — breached 여도 exit 0 (Claude 가 배너 읽고 회고 진입 판정 / advisory).
    return 0


if __name__ == "__main__":
    sys.exit(main())
