"""회고 범위 기계 산출(`scripts/retro_scope.py`) 검증.

## 사고 (2026-07-19 회고 P0-2)

정책 8 진화 (5)는 회고 범위를 *"직전 정식 회고 이후 머지 PR **+ 본 세션 산출물 전체**"* 로
규정했는데, **그 정책을 신설한 세션이 첫 적용에서 자기 산출물 2건을 누락**했다. 범위를 손으로
`#1108~#1129` 라 적었고, 회고 착수 직전 머지된 `#1130`·`#1131` 이 빠졌다. 누락된 2건은
세션에서 **가장 마지막에 머지된 = 검증이 가장 덜 된** 산출물이다.

🔴 이건 주의력 문제가 아니다 — 범위를 적는 시점과 회고가 시작되는 시점이 다른 한 **구조적으로
반복**된다. 그래서 산출을 코드로 옮겼다.

## 이 파일이 잠그는 것

`merged_prs` 가 **호출 시점의 HEAD** 를 본다는 것, 그리고 경계 판정이 카덴스 카운터와
**같은 함수**를 쓴다는 것(두 곳이 다른 회고를 고르면 카운터와 회고 범위가 어긋난다).
"""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import retro_scope  # noqa: E402


def test_merged_prs_parses_squash_subjects(monkeypatch):
    """squash 머지 제목 끝의 `(#NNNN)` 만 뽑고 정렬·중복 제거한다."""
    monkeypatch.setattr(retro_scope, "_git", lambda a: (
        "fix(x): 뭔가 (#1131)\n"
        "docs: 다른 것 (#1130)\n"
        "chore: PR 아님 — 번호 없음\n"
        "feat: 본문에 (#999) 가 있으나 끝이 아님 — 제외되어야 함\n"
        "docs: 중복 (#1130)\n"
    ))
    assert retro_scope.merged_prs("abc123") == [1130, 1131]


def test_merged_prs_reads_head_at_call_time(monkeypatch):
    """🔴 핵심 — 목록이 **호출 시점**에 산출된다(작성 시점 고정 아님).

    손으로 적은 범위가 굳는 것이 P0 의 기전이었다. 같은 함수를 두 번 부르면 그 사이
    새로 머지된 PR 이 **두 번째 호출에 반영**돼야 한다.
    """
    state = {"log": "docs: 첫 번째 (#1130)\n"}
    monkeypatch.setattr(retro_scope, "_git", lambda a: state["log"])

    first = retro_scope.merged_prs("abc123")
    state["log"] += "docs: 회고 착수 직전 머지 (#1131)\n"  # 그 사이 머지 발생
    second = retro_scope.merged_prs("abc123")

    assert first == [1130]
    assert second == [1130, 1131], "호출 시점 HEAD 를 안 보고 결과가 굳었다 — P0 재현"


def test_boundary_uses_add_commit_not_last_touch(monkeypatch):
    """경계는 리포트가 **추가된** 커밋 — `--diff-filter=A` 가 빠지면 이후 수정 커밋이 잡힌다."""
    seen = {}

    def fake_git(args):
        seen["args"] = args
        return "deadbeef\n"

    monkeypatch.setattr(retro_scope, "_git", fake_git)
    assert retro_scope.boundary_commit("2026-07-19-retrospective-2.md") == "deadbeef"
    assert "--diff-filter=A" in seen["args"], "추가 커밋 필터가 빠졌다 — 경계가 뒤로 밀린다"


def test_boundary_selection_shares_counter_logic():
    """🔴 경계 판정이 카덴스 카운터와 **같은 함수**를 쓴다 — 각자 구현하면 서로 어긋난다.

    실제로 카운터의 tie-break 버그(같은 날 회고 2건 중 오래된 쪽 선택)가 있었고,
    범위 산출이 별도 구현이었다면 그 버그가 두 배로 났을 것이다.
    """
    from check_retro_cadence import newest_retro as counter_newest

    assert retro_scope.newest_retro is counter_newest, (
        "retro_scope 가 자체 최신-회고 판정을 갖고 있다 — 카운터와 갈라진다"
    )


def test_compute_reports_failure_reason_instead_of_silent_empty(monkeypatch, tmp_path):
    """실패 시 **사유와 함께** ok=False — 조용히 빈 범위를 돌려주면 회고가 0건을 본다."""
    monkeypatch.setattr(retro_scope, "_REPORTS", tmp_path / "nope")
    r = retro_scope.compute()
    assert r["ok"] is False and r.get("reason"), "실패가 사유 없이 조용하다"


def test_script_runs_and_includes_recent_prs():
    """🔴 실제 저장소에서 실행 — 산출 범위가 **비어 있지 않아야** 한다.

    합성 입력만 검증하면 실제 git 호출이 깨져도 green 이다(이 세션이 반복해 다룬 형태).
    """
    root = Path(__file__).resolve().parents[3]
    r = subprocess.run(
        [sys.executable, "scripts/retro_scope.py", "--json"],
        cwd=root, capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if r.returncode != 0:
        pytest.skip(f"git 사용 불가 환경 — skip ({r.stdout[:80]})")
    import json

    data = json.loads(r.stdout)
    assert data["ok"] is True
    assert data["pr_count"] > 0, "실제 저장소에서 머지 PR 이 0건 — git 파싱이 깨졌을 가능성"
    assert data["prs"] == sorted(data["prs"]), "정렬되지 않음"
