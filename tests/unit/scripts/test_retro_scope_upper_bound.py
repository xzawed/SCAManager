"""회고 범위의 상한은 `origin/main` 이다 — 리터럴 `HEAD` 가 아니다 (회고 2026-09-16 P0).

## 사고

회고가 피처 브랜치에서 돌았다. `merged_prs` 가 `{boundary}..HEAD` 를 읽어 그 브랜치 끝까지만
셌고, 실행 중 main 에 머지된 #1684 가 열거에서 빠졌다. 정직성 필드 둘(`gh_only`·`unmeasured`)은
「일치한다」를 인쇄했다 — GitHub 대조축의 판정식이 `base != "main"` 이라 base=main 탈출을
원리적으로 못 봤기 때문이다.

## 이 파일이 잠그는 것

진짜 git 저장소를 임시로 만들어 잰다. `_git` 을 흉내 내면 «어느 ref 까지 세는가» 를 못 잰다.

1. HEAD 가 피처 브랜치여도 main 에 머지된 PR 이 열거에 남는다.
2. 브랜치 커밋 제목 끝의 Issue 번호 `(#N)` 을 PR 로 세지 않는다.
3. HEAD 가 main 끝과 다르면 `head-not-main` 을 싣는다 — 같으면 싣지 않는다(항상-발화 방지).
4. GitHub 대조는 base 가 아니라 **머지 시각**으로 창을 자른다.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "retro_scope.py"


def _load():
    spec = importlib.util.spec_from_file_location("retro_scope_ub", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rs = _load()


def _run(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout


def _commit(repo: Path, subject: str, path: str = "f.txt") -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(target.read_text(encoding="utf-8") + subject + "\n" if target.exists()
                      else subject + "\n", encoding="utf-8")
    _run(repo, "add", path)
    _run(repo, "commit", "-q", "-m", subject)


@pytest.fixture
def feature_branch_repo(tmp_path, monkeypatch):
    """main 에 PR 이 머지된 **뒤** 피처 브랜치가 체크아웃된 저장소.

    main : 리포트(#10) → #11 → #12   ← origin/main
    feat : 리포트(#10) → #11 → `wip (#1639)`   ← HEAD (1639 는 Issue 번호)
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(repo, "init", "-q", "-b", "main")
    _run(repo, "config", "user.email", "t@example.com")
    _run(repo, "config", "user.name", "t")
    _run(repo, "config", "commit.gpgsign", "false")
    _commit(repo, "docs: 회고 리포트 (#10)", "docs/reports/2026-01-01-retrospective.md")
    _commit(repo, "fix: a (#11)")
    _run(repo, "checkout", "-q", "-b", "feat")
    _commit(repo, "wip: 화면 손질 (#1639)", "g.txt")
    _run(repo, "checkout", "-q", "main")
    _commit(repo, "fix: b (#12)")
    _run(repo, "update-ref", "refs/remotes/origin/main", "main")
    _run(repo, "checkout", "-q", "feat")

    monkeypatch.setattr(rs, "_ROOT", repo)
    monkeypatch.setattr(rs, "_REPORTS", repo / "docs" / "reports")
    monkeypatch.setattr(rs, "_gh_json", lambda _a: None)  # gh 없음 — git 축만 잰다
    return repo


def test_a_pr_merged_to_main_stays_in_scope_while_head_is_a_feature_branch(feature_branch_repo):
    """🔴 P0 재현 — HEAD 가 피처 브랜치여도 main 에 머지된 #12 가 열거에 있어야 한다."""
    out = rs.compute(fetched=True)
    assert out["ok"] is True, out
    assert 12 in out["prs"], f"main 에 머지된 PR 이 빠졌다 — 상한이 HEAD 다: {out['prs']}"
    assert 11 in out["prs"], out["prs"]


def test_an_issue_number_in_a_branch_commit_subject_is_not_counted(feature_branch_repo):
    """브랜치 커밋 제목 끝 `(#1639)` 는 Issue 번호다 — main 의 squash 제목만 PR 번호다."""
    out = rs.compute(fetched=True)
    assert 1639 not in out["prs"], f"Issue 번호를 PR 로 셌다: {out['prs']}"


def test_head_not_main_is_reported_on_a_feature_branch(feature_branch_repo):
    """작업 트리가 main 끝과 다르면 「안 쟀다」를 싣는다 — 「일치한다」로 인쇄하지 않는다."""
    out = rs.compute(fetched=True)
    assert "head-not-main" in out["unmeasured"], out["unmeasured"]
    assert out["main_head"] and out["main_head"] != out["head"][:8], out


def test_head_not_main_is_absent_when_head_is_the_main_tip(feature_branch_repo):
    """대조군 — HEAD 가 main 끝이면 싣지 않는다. 항상 실리면 아무것도 구별하지 못한다."""
    _run(feature_branch_repo, "checkout", "-q", "main")
    out = rs.compute(fetched=True)
    assert "head-not-main" not in out["unmeasured"], out["unmeasured"]
    assert out["prs"] == [11, 12], out["prs"]


def test_an_unfetched_main_is_reported_as_unmeasured(feature_branch_repo):
    """받지 않은 `origin/main` 은 낡았을 수 있다 — 그 사실을 넘긴다. 받았으면 넘기지 않는다."""
    assert "origin-main-not-fetched" in rs.compute(fetched=False)["unmeasured"]
    assert "origin-main-not-fetched" not in rs.compute(fetched=True)["unmeasured"]


# ── GitHub 대조 — base 가 아니라 머지 시각 ──────────────────────────────────


def test_cross_check_selects_by_merge_time_not_by_base(monkeypatch):
    """🔴 base=main 인 PR 도 창 안이면 담는다 — 예전 판정식 `base != "main"` 이 #1684 를 못 봤다.

    창은 시각으로 자른다: 같은 날이라도 창 시작보다 먼저 머지된 PR 은 담지 않는다.
    오프셋이 다른 두 표기(`+09:00` 과 `Z`)를 같은 시각으로 비교해야 한다.
    """
    seen = {}

    def fake_gh(args):
        seen["args"] = args
        return [
            {"number": 9, "mergedAt": "2026-08-30T00:30:00Z"},   # 09:30+09:00 — 창 시작 전
            {"number": 12, "mergedAt": "2026-08-30T01:30:00Z"},  # 10:30+09:00 — 창 안
            {"number": 13, "mergedAt": "2026-08-31T05:00:00Z"},  # 창 안 (base 무관)
            {"number": "x", "mergedAt": "2026-08-31T05:00:00Z"},  # 형식 불량 — 버린다
        ]

    monkeypatch.setattr(rs, "_gh_json", fake_gh)
    got = rs.github_merged_prs("2026-08-30T10:00:00+09:00")
    assert got == [12, 13], f"머지 시각으로 창을 자르지 않는다 — {got}"
    assert "merged:>=2026-08-29" in seen["args"], (
        f"검색 날짜가 UTC 하루 앞이 아니다 — 창 앞쪽이 잘린다: {seen['args']}")


def test_cross_check_reports_what_git_log_missed(feature_branch_repo, monkeypatch):
    """git log 산출과의 차집합이 `gh_only` 다 — base=main 탈출도 여기 실린다."""
    monkeypatch.setattr(rs, "_gh_json", lambda _a: [
        {"number": 11, "mergedAt": "2999-01-01T00:00:00Z"},
        {"number": 12, "mergedAt": "2999-01-01T00:00:00Z"},
        {"number": 14, "mergedAt": "2999-01-01T00:00:00Z"},  # git log 에 없는 PR
    ])
    out = rs.compute(fetched=True)
    assert out["gh_checked"] is True
    assert out["gh_only"] == [14], out
    assert 14 in out["prs"], out["prs"]
