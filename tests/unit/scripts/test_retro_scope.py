"""회고 범위 기계 산출(`scripts/retro_scope.py`) 검증.

## 사고 (2026-07-19 회고 P0-2)

정책 8 진화 (5)는 회고 범위를 *"직전 정식 회고 이후 머지 PR **+ 본 세션 산출물 전체**"* 로
규정했는데, **그 정책을 신설한 세션이 첫 적용에서 자기 산출물 2건을 누락**했다. 범위를 손으로
`#1108~#1129` 라 적었고, 회고 착수 직전 머지된 `#1130`·`#1131` 이 빠졌다. 누락된 2건은
세션에서 **가장 마지막에 머지된 = 검증이 가장 덜 된** 산출물이다.

🔴 이건 주의력 문제가 아니다 — 범위를 적는 시점과 회고가 시작되는 시점이 다른 한 **구조적으로
반복**된다. 그래서 산출을 코드로 옮겼다.

## 이 파일이 잠그는 것

`merged_prs` 가 **호출 시점의 HEAD** 를 본다는 것, 그리고 `newest_retro` 가
같은 날 회고를 순번으로 고른다는 것.
"""
import subprocess
import sys
from pathlib import Path

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


def test_newest_retro_picks_latest_date_excluding_non_retros():
    """정식 회고만 대상으로 최신 날짜 선택 — review/audit 는 제외."""
    files = [
        "2026-06-23-retrospective.md",
        "2026-07-03-retrospective.md",
        "2026-07-17-grok-full-review.md",
        "2026-06-16-session-retrospective.md",
        "INDEX.md",
    ]
    assert retro_scope.newest_retro(files) == "2026-07-03-retrospective.md"


def test_newest_retro_none_when_no_retros():
    """정식 회고가 없으면 None."""
    assert retro_scope.newest_retro(["INDEX.md", "2026-07-17-grok-full-review.md"]) is None
    assert retro_scope.newest_retro([]) is None


def test_newest_retro_same_date_picks_higher_sequence():
    """같은 날 회고 2건 — 파일명 사전순이 아니라 순번이 이긴다."""
    files = [
        "2026-07-19-retrospective.md",
        "2026-07-19-retrospective-2.md",
        "2026-07-18-retrospective.md",
    ]
    assert retro_scope.newest_retro(files) == "2026-07-19-retrospective-2.md"


def test_newest_retro_same_date_order_independent():
    """입력 순서가 결과를 바꾸면 안 된다."""
    a = ["2026-07-19-retrospective.md", "2026-07-19-retrospective-2.md"]
    assert (
        retro_scope.newest_retro(a)
        == retro_scope.newest_retro(list(reversed(a)))
        == "2026-07-19-retrospective-2.md"
    )


def test_newest_retro_same_date_sequence_is_numeric_not_lexical():
    """순번은 숫자 비교 — 문자열이면 '10' < '2' 가 되어 10차가 밀린다."""
    files = [
        "2026-07-19-retrospective-2.md",
        "2026-07-19-retrospective-10.md",
    ]
    assert retro_scope.newest_retro(files) == "2026-07-19-retrospective-10.md"


def test_newest_retro_later_date_beats_higher_sequence():
    """날짜가 순번보다 우선 — 어제의 10차보다 오늘의 1차가 최신이다."""
    files = [
        "2026-07-18-retrospective-10.md",
        "2026-07-19-retrospective.md",
    ]
    assert retro_scope.newest_retro(files) == "2026-07-19-retrospective.md"


def test_retro_date_extracts_from_retrospective_filename():
    """정식 회고 파일명에서 YYYY-MM-DD 추출."""
    assert retro_scope.retro_date("2026-07-03-retrospective.md") == "2026-07-03"
    assert retro_scope.retro_date("2026-06-16-session-retrospective.md") == "2026-06-16"


def test_retro_date_rejects_non_retrospective_reports():
    """'retrospective' 없는 리포트는 None — 카덴스 경계 오인 차단."""
    assert retro_scope.retro_date("2026-07-17-grok-full-review.md") is None
    assert retro_scope.retro_date("INDEX.md") is None


def test_compute_reports_failure_reason_instead_of_silent_empty(monkeypatch, tmp_path):
    """실패 시 **사유와 함께** ok=False — 조용히 빈 범위를 돌려주면 회고가 0건을 본다."""
    monkeypatch.setattr(retro_scope, "_REPORTS", tmp_path / "nope")
    r = retro_scope.compute()
    assert r["ok"] is False and r.get("reason"), "실패가 사유 없이 조용하다"


def test_script_runs_and_includes_recent_prs():
    """🔴 실제 저장소에서 실행 — git 파싱이 **건강**한지 검증(합성-only 면 git 파손도 green).

    🔴 pr_count > 0 은 단언하지 않는다 — **타이밍 의존**이다. 회고를 방금 아카이브하면(경계 =
    최근 커밋) pr_count 0 이 정상이고, 그 단언은 회고 아카이브 PR 이 머지되는 순간 main 을 red 로
    만든다(2026-07-22 실측 — 이 테스트를 고친 PR 이 바로 그 사례였다). "git 파손 탐지" 원 의도는
    boundary/head 해결 + pr_count↔prs 일치 + 정렬로 보존한다.
    Runs against the real repo to verify git parsing is healthy. pr_count is timing-dependent
    (0 right after archiving a retro is valid), so it is NOT asserted > 0 — that would turn main
    red the moment a retro-archive PR merges. Intent kept via boundary/head + consistency.
    """
    root = Path(__file__).resolve().parents[3]
    r = subprocess.run(
        [sys.executable, "scripts/retro_scope.py", "--json"],
        cwd=root, capture_output=True, text=True, encoding="utf-8", check=False,
    )
    # 🔴 exit 1 은 고장이 아니라 **fail-closed 응답**이다 — 경계 커밋(직전 회고)을 못 찾으면
    #    사유를 담은 JSON 을 stdout 에 싣고 1 로 끝난다. 형제 파일
    #    `test_retro_scope_is_machine_derived.py:102-110` 이 이미 그 계약을 쓴다.
    # 🔴 2026-08-17 정정: 이전 판은 `returncode != 0` 이면 «git 사용 불가 환경» 이라며
    #    skip 했다. 실측 사유는 `{"ok": false, "reason": "정식 회고 리포트 없음"}` 이었고
    #    (`docs/reports/` 가 비어 있다 — #1372), git 은 멀쩡했다. **거짓 사유로 조용히 skip**
    #    하는 동안 아래 단언 4개가 통째로 미관측이었다.
    # The old version skipped citing "git unavailable" while the real reason was a missing
    # retro report; four assertions went unobserved behind a false skip reason.
    assert r.returncode in (0, 1), (
        f"예상 밖 종료(exit {r.returncode}) — git 실행 자체가 실패했을 수 있다: {r.stderr[-300:]}"
    )
    import json

    data = json.loads(r.stdout)
    if data.get("ok") is not True:
        # 회고 리포트가 없는 것은 정당한 상태다. 그러나 **사유는 반드시 있어야** 한다 —
        # 사유 없는 실패는 이 스크립트가 왜 못 세는지 아무도 모르게 만든다.
        # A missing retro report is legitimate, but the refusal must carry a reason.
        assert data.get("reason"), f"ok=false 인데 사유가 없다: {data}"
        return
    assert data["ok"] is True
    # git 파싱 건강성 = boundary(직전 회고 커밋)·head 가 실제 해결됐고 pr_count 가 prs 와 일치하는가.
    # git-parsing health = boundary/head actually resolved and pr_count consistent with prs.
    assert data["boundary"] and data["head"], "boundary/head 커밋 미해결 — git 파싱 깨짐 가능"
    assert data["pr_count"] == len(data["prs"]), "pr_count 와 prs 길이 불일치 — 파싱 손상"
    assert data["prs"] == sorted(data["prs"]), "정렬되지 않음"


# ── 명시 경계 (--since) — 리포트가 없어도 기계가 범위를 낸다 (#1443 a) ──────────
#
# 🔴 실측(2026-08-18): `docs/reports/` 의 회고 리포트는 2026-05-25(#643)에 아카이브됐고
#    그 뒤 이 도구는 **3개월째 `ok:false`** 였다. 그 사이 회고는 계속 돌았다 —
#    즉 스킬 1단계(「범위는 기계에서 얻는다 · 손 조립 금지」)가 원리적으로 불가능했다.
#
# 🔴 리포트가 없을 때 **경계를 지어내지 않는다.** 모르는 것은 모른다고 하되,
#    호출자가 경계를 주면 그때부터는 기계가 나머지를 계산한다 — 손 조립은 여전히 막힌다.


class TestExplicitBoundary:
    def test_since_sha_yields_a_range_without_any_report(self, monkeypatch, tmp_path):
        """리포트가 0건이어도 `--since` 가 있으면 범위가 나온다."""
        monkeypatch.setattr(retro_scope, "_REPORTS", tmp_path)  # 빈 디렉토리
        head = retro_scope._git(["rev-parse", "HEAD"]).strip()
        r = retro_scope.compute(since=head)
        assert r["ok"] is True
        assert r["anchor"] == "explicit"
        assert r["prev_retro"] is None

    def test_report_anchor_wins_over_since(self, monkeypatch, tmp_path):
        """리포트가 있으면 그것이 정본 — `--since` 는 폴백이지 우회가 아니다."""
        (tmp_path / "2026-08-01-retrospective.md").write_text("x", encoding="utf-8")
        monkeypatch.setattr(retro_scope, "_REPORTS", tmp_path)
        monkeypatch.setattr(retro_scope, "boundary_commit", lambda _f: "deadbee")
        monkeypatch.setattr(retro_scope, "merged_prs", lambda _b: [1, 2])
        r = retro_scope.compute(since="HEAD")
        assert r["anchor"] == "report"
        assert r["prev_retro"] == "2026-08-01-retrospective.md"

    def test_no_report_and_no_since_stays_not_ok_but_actionable(self, monkeypatch, tmp_path):
        """🔴 경계를 **지어내지 않는다** — 다만 사유가 실행 가능해야 한다.

        종전 사유는 「정식 회고 리포트 없음」 한 줄이라 다음 행동이 없었다.
        """
        monkeypatch.setattr(retro_scope, "_REPORTS", tmp_path)
        r = retro_scope.compute()
        assert r["ok"] is False
        assert "--since" in r["reason"], "다음 행동이 사유에 없다"

    def test_bad_since_is_rejected_not_silently_ignored(self, monkeypatch, tmp_path):
        """존재하지 않는 ref 를 주면 red — 조용히 전체 이력을 세면 안 된다."""
        monkeypatch.setattr(retro_scope, "_REPORTS", tmp_path)
        r = retro_scope.compute(since="no-such-ref-xyz")
        assert r["ok"] is False
        assert "no-such-ref-xyz" in r["reason"]
