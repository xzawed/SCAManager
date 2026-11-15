"""회고 범위의 기점 — 리포트가 적은 «분석 종료 head» 는 main 위에 있을 때만 믿는다 (회고 원장 L14).

## 사고

09-16 회고 리포트는 head 로 **피처 브랜치 끝**(`2613028e`)을 적었다. 그 브랜치는 뒤에 #1684 로
squash 머지됐다. 11-06 회고의 범위 산출은 그 SHA 가 (그 클론에서) 해석된다는 이유만으로 거기서부터
셌다 — `git log 끝..main` 은 갈라진 지점부터 main 을 다시 세므로 #1684 가 두 회고에 들어갔다.
출력의 «경계 커밋» 은 실제 기점이 아니어서 그것으로 diff 를 잰 쪽은 반대로 #1684~#1686 을 놓쳤다.

## 이 파일이 잠그는 것

진짜 git 저장소를 임시로 만들어 잰다(조상 판정을 흉내 내면 이 결함을 못 잰다).

1. main 밖 head 가 어느 PR 의 마지막 head 였으면 그 PR 의 머지 커밋부터 센다 — 그 PR 은 빠지고 뒤는 들어온다.
2. 그 대응을 못 찾으면(`gh` 없음) 경계에서 세고 두 축을 «안 쟀다» 로 넘긴다 — 조용히 겹치지 않는다.
3. 대조군 — main 위 head 는 그대로 기점이다.
4. 출력은 실제 기점(`scan_from`)과 그 출처를 싣는다.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "retro_scope.py"


def _load():
    spec = importlib.util.spec_from_file_location("retro_scope_hm", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rs = _load()


def _run(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout.strip()


def _commit(repo: Path, subject: str, path: str = "f.txt", text: str | None = None) -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    body = text if text is not None else (
        (target.read_text(encoding="utf-8") if target.exists() else "") + subject + "\n")
    target.write_text(body, encoding="utf-8")
    _run(repo, "add", path)
    _run(repo, "commit", "-q", "-m", subject)
    return _run(repo, "rev-parse", "HEAD")


@pytest.fixture
def squashed_head_repo(tmp_path, monkeypatch):
    """직전 리포트가 squash 된 브랜치 끝을 head 로 적은 저장소.

    feat : c0 → B(브랜치 끝 — 리포트가 적은 head)
    main : c0 → S `feat: x (#101)`(B 의 squash) → R 리포트(#102) → #103 → #104   ← origin/main · HEAD
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(repo, "init", "-q", "-b", "main")
    _run(repo, "config", "user.email", "t@example.com")
    _run(repo, "config", "user.name", "t")
    _run(repo, "config", "commit.gpgsign", "false")
    _commit(repo, "chore: init (#100)")
    _run(repo, "checkout", "-q", "-b", "feat")
    tip = _commit(repo, "wip: x", "x.txt", "x\n")
    _run(repo, "checkout", "-q", "main")
    squash = _commit(repo, "feat: x (#101)", "x.txt", "x\n")
    _commit(repo, "docs: 회고 리포트 (#102)", "docs/reports/2026-01-01-retrospective.md",
            f"| head | `{tip[:8]}` — 🔴 main 이 아니라 피처 브랜치 끝이다 |\n")
    _commit(repo, "fix: a (#103)")
    _commit(repo, "fix: b (#104)")
    _run(repo, "update-ref", "refs/remotes/origin/main", "main")

    monkeypatch.setattr(rs, "_ROOT", repo)
    monkeypatch.setattr(rs, "_REPORTS", repo / "docs" / "reports")
    return {"repo": repo, "tip": tip, "squash": squash}


def _gh_maps_tip_to(squash: str, tip: str):
    """`gh api …/commits/<tip>/pulls` 는 #101 을 돌려주고, 머지 PR 목록 조회는 빈 목록을 준다."""
    def fake(args):
        if args[:1] == ["api"] and args[1].endswith(f"/commits/{tip}/pulls"):
            return [{"number": 101, "merged_at": "2026-01-02T00:00:00Z",
                     "merge_commit_sha": squash, "head": {"sha": tip}}]
        return []
    return fake


def test_a_squashed_branch_tip_head_moves_to_its_pr_merge_commit(squashed_head_repo, monkeypatch):
    """🔴 직전 회고가 본 #101 은 빠지고, 그 뒤 머지분(#102~#104)은 들어온다."""
    r = squashed_head_repo
    monkeypatch.setattr(rs, "_gh_json", _gh_maps_tip_to(r["squash"], r["tip"]))
    out = rs.compute(fetched=True)
    assert out["ok"] is True, out
    assert out["prs"] == [102, 103, 104], f"main 밖 head 에서 세어 겹치거나 빠졌다: {out['prs']}"
    assert out["scan_from"] == r["squash"][:8] and out["scan_from_kind"] == "report-head-pr-merge", out
    assert "report-merge-gap" not in out["unmeasured"], out["unmeasured"]


def test_an_unmapped_branch_tip_head_is_reported_unmeasured_not_counted_from(squashed_head_repo, monkeypatch):
    """🔴 대응을 못 찾으면 그 SHA 에서 세지 않는다 — 경계에서 세고 «안 쟀다» 두 축을 싣는다."""
    monkeypatch.setattr(rs, "_gh_json", lambda _a: None)
    out = rs.compute(fetched=True)
    assert 101 not in out["prs"], f"직전 회고가 본 PR 을 다시 셌다: {out['prs']}"
    assert out["scan_from_kind"] == "boundary", out
    assert {"report-head-not-on-main", "report-merge-gap"} <= set(out["unmeasured"]), out["unmeasured"]


def test_a_head_on_main_is_still_the_scan_start(squashed_head_repo, monkeypatch):
    """대조군 — 리포트가 main 위 SHA 를 적었으면 그대로 기점이다(옮기지도 «안 쟀다» 도 아니다)."""
    r = squashed_head_repo
    report = r["repo"] / "docs" / "reports" / "2026-01-01-retrospective.md"
    report.write_text(f"| head | `{r['squash'][:8]}` = main |\n", encoding="utf-8")
    monkeypatch.setattr(rs, "_gh_json", lambda _a: [])
    out = rs.compute(fetched=True)
    assert out["prs"] == [102, 103, 104], out["prs"]
    assert out["scan_from_kind"] == "report-head", out
    assert "report-head-not-on-main" not in out["unmeasured"], out["unmeasured"]


def test_a_pr_whose_final_head_moved_past_the_recorded_tip_is_not_mapped(squashed_head_repo, monkeypatch):
    """회고 뒤에 커밋이 더 붙은 PR 은 옮기지 않는다 — 그 뒤 커밋을 «봤다» 로 셀 수 없다."""
    r = squashed_head_repo

    def fake(args):
        if args[:1] == ["api"]:
            return [{"number": 101, "merged_at": "2026-01-02T00:00:00Z",
                     "merge_commit_sha": r["squash"], "head": {"sha": "f" * 40}}]
        return []

    monkeypatch.setattr(rs, "_gh_json", fake)
    out = rs.compute(fetched=True)
    assert out["scan_from_kind"] == "boundary", out
    assert "report-head-not-on-main" in out["unmeasured"], out["unmeasured"]
