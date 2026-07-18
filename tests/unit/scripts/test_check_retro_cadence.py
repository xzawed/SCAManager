"""회고 카덴스 카운터 정합 (회고 2026-07-18 P0 — 카덴스 트리거 문서-only 자기위반 봉인).
Retrospective cadence counter integrity (retro 2026-07-18 P0 — seals the doc-only cadence self-violation).

정책 8 진화 (4) 회고 카덴스 강제 트리거(#1028)가 문서-only 라 첫 측정창에서 자기 위반(~46 PR 무회고).
이 카운터는 "직전 정식 회고 이후 머지 PR 수"를 기계적으로 산출해 세션 시작 시 loud 경고한다 —
인지 의존을 측정 신호로 전환(정책 4 단언+가드 페어).
The counter mechanically computes merged-PR-count-since-last-retro so session start warns loudly,
converting the trigger from cognition-dependent to measured.

🔴 순수 함수만 테스트 — 현재 repo 상태(카덴스 breached 여부)는 시점 의존이라 단언 금지(flaky).
Pure functions only — current-repo cadence state is time-dependent, so not asserted (would flake).
"""
import subprocess
import sys
from pathlib import Path

from scripts.check_retro_cadence import (
    RETRO_PR_THRESHOLD,
    count_merge_prs,
    evaluate,
    newest_retro,
    retro_date,
)

_ROOT = Path(__file__).resolve().parents[3]


# ── 순수 함수: retro_date ────────────────────────────────────────────────
# Pure function: retro_date

def test_retro_date_extracts_from_retrospective_filename():
    """정식 회고 파일명에서 YYYY-MM-DD 추출."""
    assert retro_date("2026-07-03-retrospective.md") == "2026-07-03"
    assert retro_date("2026-06-16-session-retrospective.md") == "2026-06-16"
    assert retro_date("2026-05-06-cycle-85-end-multi-agent-retrospective.md") == "2026-05-06"


def test_retro_date_rejects_non_retrospective_reports():
    """'retrospective' 없는 리포트(감사·리뷰·기획안)는 None — 카덴스 경계 오인 차단.

    🔴 2026-07-17-grok-full-review.md 는 리뷰지 회고가 아니다 — 이걸 회고로 세면
    카덴스가 잘못 리셋된다(본 회고 P0 = grok-review 를 회고로 오인해 무회고 갭 은폐 위험).
    """
    assert retro_date("2026-07-17-grok-full-review.md") is None
    assert retro_date("2026-04-24-comprehensive-audit.md") is None
    assert retro_date("2026-05-05-i18n-phase1-pr1-pre-review.md") is None
    assert retro_date("INDEX.md") is None
    assert retro_date("2026-04-09-code-quality-report.md") is None


# ── 순수 함수: newest_retro ──────────────────────────────────────────────
# Pure function: newest_retro

def test_newest_retro_picks_latest_date_excluding_non_retros():
    """정식 회고만 대상으로 최신 날짜 선택 — grok-review/audit 는 제외."""
    files = [
        "2026-06-23-retrospective.md",
        "2026-07-03-retrospective.md",
        "2026-07-17-grok-full-review.md",  # 회고 아님 — 제외 / not a retro
        "2026-06-16-session-retrospective.md",
        "INDEX.md",
    ]
    assert newest_retro(files) == "2026-07-03-retrospective.md"


def test_newest_retro_none_when_no_retros():
    """정식 회고가 없으면 None."""
    assert newest_retro(["INDEX.md", "2026-07-17-grok-full-review.md"]) is None
    assert newest_retro([]) is None


# ── 순수 함수: count_merge_prs ───────────────────────────────────────────
# Pure function: count_merge_prs

def test_count_merge_prs_counts_squash_merge_subjects():
    """끝에 (#NNNN) 인 squash-merge PR 제목만 카운트."""
    subjects = [
        "fix(test): CodeQL 봉인 (#1077)",
        "docs: 5+1 회고 보고서 (#1078)",
        "Merge branch 'main' into feature",   # PR 아님 / not a PR
        "feat(cron): retention sweep (준비도 감사 #12·#20) (#1075)",  # 본문 #12 있어도 끝 (#1075) 로 1회 / trailing PR only
    ]
    assert count_merge_prs(subjects) == 3


def test_count_merge_prs_ignores_inline_issue_refs():
    """본문 중간 #NN 은 미카운트 — 끝 (#NNNN) 만 (오버카운트 차단)."""
    assert count_merge_prs(["fix #12 in the middle then done"]) == 0
    assert count_merge_prs(["chore: bump (준비도 감사 #6·#17) (#1070)"]) == 1


def test_count_merge_prs_empty():
    assert count_merge_prs([]) == 0


# ── 순수 함수: evaluate ──────────────────────────────────────────────────
# Pure function: evaluate

def test_evaluate_breached_at_or_above_threshold():
    """pr_count >= threshold 면 breached True (경계 포함)."""
    breached, _ = evaluate(46, threshold=15)
    assert breached is True
    breached, _ = evaluate(15, threshold=15)
    assert breached is True, "경계값(정확히 임계)도 breached — >= 판정"


def test_evaluate_not_breached_below_threshold():
    breached, msg = evaluate(5, threshold=15)
    assert breached is False
    assert "5" in msg and "15" in msg, "메시지에 현재/임계 카운트 노출"


def test_evaluate_default_threshold_is_15():
    """default threshold = RETRO_PR_THRESHOLD (정책 8 진화 (4) ≥15 PR)."""
    assert RETRO_PR_THRESHOLD == 15
    breached, _ = evaluate(15)
    assert breached is True


# ── 스크립트 존재 + 셸 실측 (integration-lite) ───────────────────────────
# Script existence + shell smoke

def test_script_file_exists():
    """스크립트가 존재하고 세션 시작 체크리스트에서 호출 가능."""
    assert (_ROOT / "scripts" / "check_retro_cadence.py").is_file()


def test_script_runs_without_crashing():
    """🔴 스크립트가 크래시 없이 exit 0 (advisory) — Windows cp949 이모지 크래시 회귀 봉인.

    세션 시작 체크리스트에서 로컬(Windows)로 실행되므로 배너 이모지(🔴)가 cp949 stdout 에서
    UnicodeEncodeError 를 내면 안 된다. _make_stdout_safe 회귀 가드.

    🔴 `encoding="utf-8"` 필수 — 미지정 시 reader 스레드가 로케일 기본(Windows cp949)으로
    UTF-8 출력을 디코드하다 UnicodeDecodeError → `r.stderr` 가 비어 아래 단언이 **무조건 통과**
    (가드가 정작 Windows 에서 눈이 먼다). 전 가드 스크립트가 쓰는 관용구와 동일하게 맞춘다.
    Without an explicit encoding the reader thread decodes UTF-8 output as cp949 and dies,
    leaving `r.stderr` empty so the assertion below spuriously passes on the very platform
    it guards. Matches the `encoding="utf-8"` idiom used by every guard script.
    """
    r = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "check_retro_cadence.py")],
        capture_output=True, text=True, check=False, cwd=str(_ROOT),
        encoding="utf-8", errors="replace",
    )
    assert r.returncode == 0, f"advisory 스크립트가 non-zero 종료 (stderr={r.stderr[:300]})"
    assert "UnicodeEncodeError" not in r.stderr, "cp949 이모지 크래시 재발"


def test_checklist_wires_the_counter():
    """🔴 CLAUDE.md 작업 시작 전 필수 체크리스트가 카운터를 배선 — 문서-only 재발 방지.

    본 회고 P0 = 문서-only 정책이 두 번 실패. 스크립트만 있고 체크리스트 미배선이면
    다시 인지 의존이 된다 → 체크리스트 bash 블록에 스크립트 호출이 존재해야 한다.
    """
    claude_md = (_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "check_retro_cadence.py" in claude_md, (
        "CLAUDE.md 체크리스트에 check_retro_cadence.py 호출 누락 — 카운터가 배선 안 되면 문서-only 재발"
    )
