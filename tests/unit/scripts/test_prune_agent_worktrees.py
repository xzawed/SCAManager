"""`scripts/prune_agent_worktrees.py` 회귀 가드 — 실경로 worktree 로 안전 계약을 잰다.

🔴 이 스크립트의 유일한 계약은 **미커밋 변경이 있으면 건드리지 않는다** 이다.
그 계약이 깨지면 에이전트가 작업 중인 내용이 조용히 사라진다 — mock 으로는 못 잰다.
The single contract is "never touch a dirty worktree"; only real worktrees can measure it.
"""
from __future__ import annotations

import subprocess  # nosec B404
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "scripts"))

import prune_agent_worktrees as mod  # noqa: E402


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(  # nosec B603 B607
        ["git", *args], cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False, timeout=60,
    )


@pytest.fixture(name="repo")
def _repo(tmp_path: Path) -> Path:
    """커밋 1개짜리 실제 저장소 — 합성 픽스처가 아니라 진짜 git 이다."""
    root = tmp_path / "repo"
    root.mkdir()
    _git("init", "-q", cwd=root)
    _git("config", "user.email", "t@t.t", cwd=root)
    _git("config", "user.name", "t", cwd=root)
    (root / "f.txt").write_text("base\n", encoding="utf-8")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "base", cwd=root)
    return root


def _add_wt(repo: Path, tmp_path: Path, name: str) -> Path:
    """`_AGENT_DIRS` 에 매칭되는 경로로 worktree 를 만든다."""
    path = tmp_path / ".grok-build" / "worktrees" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    _git("worktree", "add", "-q", "--detach", str(path), "HEAD", cwd=repo)
    return path


def test_clean_agent_worktree_is_removed(repo, tmp_path, monkeypatch):
    """깨끗한 에이전트 worktree 는 제거된다 — 이게 이 스크립트의 목적이다."""
    wt = _add_wt(repo, tmp_path, "clean")
    assert wt.exists()
    mod.main(root=repo)
    assert not wt.exists(), "깨끗한 worktree 가 남았다 — 정리 기전이 돌지 않는다"


def test_dirty_agent_worktree_is_never_touched(repo, tmp_path, monkeypatch):
    """🔴 미커밋 변경이 있으면 **remove 를 시도조차 하지 않는다**.

    ## 왜 「파일이 남아 있다」로 재면 안 되는가 (2026-08-17 뮤테이션 실측)

    `git worktree remove` 는 `--force` 없이 더티 worktree 를 **스스로 거부**한다.
    그래서 이 스크립트의 더티 검사를 통째로 지워도(`if False:`) 파일은 그대로 남고,
    「파일 존재」로 재는 단언은 **초록을 유지한다** — 보호한 것은 git 이지 이 코드가 아니다.
    실측: 그 뮤테이션에서 이 테스트가 통과했고 다른 테스트만 red 였다.

    그래서 여기서는 **`worktree remove` 호출 자체가 없었는지**를 잰다. 그것이 이 스크립트가
    실제로 기여하는 축이다(git 의 거부에 기대지 않는 fail-closed).
    Measure that `remove` was never attempted: git refuses dirty removals itself, so an
    existence assertion stays green even with this guard deleted.
    """
    wt = _add_wt(repo, tmp_path, "dirty")
    (wt / "f.txt").write_text("에이전트가 작업 중\n", encoding="utf-8")

    real = mod._git
    attempted: list[tuple] = []

    def spy(*args, **kwargs):
        if "remove" in args and any("dirty" in str(a) for a in args):
            attempted.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(mod, "_git", spy)
    mod.main(root=repo)

    assert not attempted, (
        f"더티 worktree 에 remove 를 시도했다 — git 이 거부해줘서 살아남은 것뿐이다: {attempted}"
    )
    assert wt.exists(), "미커밋 변경이 있는 worktree 를 지웠다 — 작업 소실"
    assert (wt / "f.txt").read_text(encoding="utf-8").strip() == "에이전트가 작업 중"


def test_non_agent_worktree_is_out_of_scope(repo, tmp_path, monkeypatch):
    """사람이 만든 worktree 는 대상이 아니다 — `_AGENT_DIRS` 밖은 건드리지 않는다."""
    path = tmp_path / "my-work"
    _git("worktree", "add", "-q", "--detach", str(path), "HEAD", cwd=repo)
    mod.main(root=repo)
    assert path.exists(), "사람 worktree 를 지웠다 — 범위를 넘었다"


def test_unreadable_status_is_not_treated_as_clean(repo, tmp_path, monkeypatch):
    """🔴 상태를 못 읽으면 «깨끗하다» 로 읽지 않는다 (fail-closed).

    「모른다」를 「없다」로 접는 것이 이 리포의 반복 실패 클래스다.
    """
    wt = _add_wt(repo, tmp_path, "unreadable")
    real = mod._git

    def fake(*args, **kwargs):
        # 🔴 경로 문자열 정규화가 플랫폼마다 달라 완전 일치로 매칭하면 mock 이 조용히 빗나간다
        #    (실측: 이 테스트 초판이 그렇게 빗나가 «코드가 fail-open» 으로 오판했다).
        # Match by name, not exact path: platform path normalisation made the first version miss.
        if "status" in args and any("unreadable" in str(a) for a in args):
            return subprocess.CompletedProcess(args, 128, "", "fatal: not a git repository")
        return real(*args, **kwargs)

    monkeypatch.setattr(mod, "_git", fake)
    mod.main(root=repo)
    assert wt.exists(), "status 를 못 읽었는데 지웠다 — 「모른다」를 「깨끗하다」로 읽었다"
