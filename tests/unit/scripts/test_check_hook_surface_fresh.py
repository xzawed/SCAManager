"""세션 시작 «지금 도는 훅 ≠ main 의 훅» 한 줄 (원장 #1917 M01 P1-1 ~ P1-3).

리포 훅은 주 체크아웃의 파일로 돈다. 11-15 ~ 11-21 주 체크아웃이 기능 브랜치에 머물러 머지된 훅 · 설정 10 PR 이
4~6일 적용되지 않았고, 아무도 알리지 않았다. 여기서는 임시 git 저장소로 네 상태를 재고, 판정 함수를 따로 잰다.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_hook_surface_fresh import advice

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "check_hook_surface_fresh.py"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True,
                          encoding="utf-8").stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """main 한 커밋 + 그 커밋을 가리키는 origin/main — 네트워크 없이 «마지막 fetch» 를 흉내 낸다."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "t")
    (r / ".claude").mkdir()
    (r / ".claude" / "settings.json").write_text("{}\n", encoding="utf-8")
    (r / "scripts").mkdir()
    (r / "scripts" / "x.py").write_text("print(1)\n", encoding="utf-8")
    (r / "src.py").write_text("a = 1\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "init")
    _git(r, "update-ref", "refs/remotes/origin/main", _git(r, "rev-parse", "HEAD"))
    return r


def _run(cwd: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(cwd), "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, str(_SCRIPT)], capture_output=True, text=True, encoding="utf-8",
                          env=env, check=False)


def test_main_in_sync_is_silent(repo):
    proc = _run(repo)
    assert proc.returncode == 0 and proc.stdout.strip() == ""


def test_a_feature_branch_in_the_main_checkout_is_announced(repo):
    _git(repo, "switch", "-q", "-c", "fix/x")
    proc = _run(repo)
    assert proc.returncode == 0
    assert "main 이 아니다" in proc.stdout and "fix/x" in proc.stdout


def test_a_hook_surface_behind_origin_main_is_announced(repo):
    """🔴 main 이어도 뒤처지면 옛 훅이 돈다 — origin/main 이 훅 파일을 바꿨는데 주 체크아웃은 그대로."""
    (repo / ".claude" / "settings.json").write_text('{"hooks": {}}\n', encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "newer hooks")
    _git(repo, "update-ref", "refs/remotes/origin/main", _git(repo, "rev-parse", "HEAD"))
    _git(repo, "reset", "-q", "--hard", "HEAD~1")
    proc = _run(repo)
    assert proc.returncode == 0
    assert "지금 도는 훅" in proc.stdout and ".claude/settings.json" in proc.stdout


def test_a_difference_outside_the_hook_surface_is_silent(repo):
    """부정 통제 — 앱 코드만 다르면 훅과 무관하다(작업 중인 main 은 흔하다)."""
    (repo / "src.py").write_text("a = 2\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "app change")
    proc = _run(repo)
    assert proc.returncode == 0 and proc.stdout.strip() == ""


def test_not_a_repository_never_blocks_the_session(tmp_path):
    proc = _run(tmp_path)
    assert proc.returncode == 0 and proc.stdout.strip() == ""


def test_a_vanished_working_directory_never_blocks_the_session(monkeypatch):
    """🔴 세션 시작 훅은 늘 0 — 지워진 작업 디렉터리에서 os.getcwd() 가 예외를 내도(Grok `2c797603` 반례)."""
    import scripts.check_hook_surface_fresh as fresh

    def _gone():
        raise FileNotFoundError("cwd was deleted")

    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.setattr(fresh.os, "getcwd", _gone)
    assert fresh.main() == 0


def test_a_failing_git_is_announced_not_hidden(monkeypatch, capsys):
    """🔴 못 재면 조용히 넘기지 않는다 — 기준은 있는데 git 이 실패하면 «못 쟀다» 한 줄 · 그래도 exit 0."""
    import scripts.check_hook_surface_fresh as fresh

    def _fails(*_args):
        raise SystemExit(2)

    monkeypatch.setattr(fresh, "_has_repo_and_base", lambda _root: True)
    monkeypatch.setattr(fresh, "_git", _fails)
    assert fresh.main() == 0
    assert "못 쟀다" in capsys.readouterr().out


def test_advice_is_empty_when_nothing_is_wrong():
    assert advice("main", []) == []


def test_advice_names_the_branch_and_the_differing_files():
    lines = advice("fix/y", [".claude/hooks/a.py", "scripts/b.py"])
    assert len(lines) == 2
    assert "fix/y" in lines[0]
    assert ".claude/hooks/a.py" in lines[1] and "2 파일" in lines[1]


def test_a_detached_head_is_not_main():
    assert "분리된 HEAD" in advice("HEAD", [])[0]
