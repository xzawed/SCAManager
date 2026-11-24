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

import scripts.check_hook_surface_fresh as fresh

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


# witness-corpus: 11-15~21 창에서 실제로 바뀐 경로 — 주 체크아웃이 낡아 꺼져 있던 훅 표면(원장 #1917 P1-2 증거 diff)과 같은 창의 세션 무관 경로(CI · 운영 이미지 · 앱)
_WINDOW_PATHS = [
    ("CLAUDE.md", True),
    (".claude/hooks/block_credential_dump.py", True),
    ("scripts/retro_scope.py", True),
    ("requirements-semgrep.txt", False),
    (".github/workflows/ci.yml", False),
    ("src/config.py", False),
]


@pytest.mark.parametrize(("rel", "announced"), _WINDOW_PATHS)
def test_a_stale_window_path_is_announced_exactly_when_it_feeds_the_session(repo, rel, announced):
    """🔴 경계를 사건 쪽에서 잰다 — 주 체크아웃이 origin/main 보다 뒤일 때 세션에 먹히는 경로만 이름으로 알린다."""
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("old\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "old")
    path.write_text("new\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "new")
    _git(repo, "update-ref", "refs/remotes/origin/main", _git(repo, "rev-parse", "HEAD"))
    _git(repo, "reset", "-q", "--hard", "HEAD~1")
    proc = _run(repo)
    assert proc.returncode == 0
    assert (rel in proc.stdout) is announced, proc.stdout


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
    def _gone():
        raise FileNotFoundError("cwd was deleted")

    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.setattr(fresh.os, "getcwd", _gone)
    assert fresh.main() == 0


def test_git_missing_from_path_is_announced(monkeypatch, capsys):
    """🔴 git 을 못 부르면(FileNotFoundError) 조용히 넘기지 않는다 — «못 쟀다» 한 줄 · exit 0(Grok `2c797603` 반례)."""
    def _no_git(*_args, **_kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(fresh.subprocess, "run", _no_git)
    assert fresh.main() == 0
    assert "못 쟀다" in capsys.readouterr().out


def test_a_failing_git_is_announced_not_hidden(monkeypatch, capsys):
    """🔴 못 재면 조용히 넘기지 않는다 — 기준은 있는데 git 이 실패하면 «못 쟀다» 한 줄 · 그래도 exit 0."""
    def _fails(*_args):
        raise SystemExit(2)

    monkeypatch.setattr(fresh, "_inside_repo", lambda _root: True)
    monkeypatch.setattr(fresh, "_has_base", lambda _root: True)
    monkeypatch.setattr(fresh, "_git", _fails)
    assert fresh.main() == 0
    assert "못 쟀다" in capsys.readouterr().out


def test_git_refusing_the_repository_is_announced_not_treated_as_no_repo(repo, monkeypatch, capsys):
    """🔴 git 이 저장소를 거부하면(safe.directory 소유권 — 종료 128) «저장소 아님» 처럼 조용히 넘어가지 않는다(Grok `2c797603`)."""
    real_run = fresh.subprocess.run

    def _refuses(args, *a, **k):
        if "--verify" in args:
            return subprocess.CompletedProcess(args, 128, b"", b"fatal: detected dubious ownership")
        return real_run(args, *a, **k)

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))
    monkeypatch.setattr(fresh.subprocess, "run", _refuses)
    assert fresh.main() == 0
    assert "못 쟀다" in capsys.readouterr().out


def test_a_missing_origin_main_stays_silent(repo, monkeypatch, capsys):
    """부정 통제 — origin/main 이 없는 것(종료 1)은 정상 상태다(원격 없음 · fetch 전)."""
    _git(repo, "update-ref", "-d", "refs/remotes/origin/main")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))
    assert fresh.main() == 0
    assert capsys.readouterr().out.strip() == ""


def test_advice_is_empty_when_nothing_is_wrong():
    assert fresh.advice("main", []) == []


def test_advice_names_the_branch_and_the_differing_files():
    lines = fresh.advice("fix/y", [".claude/hooks/a.py", "scripts/b.py"])
    assert len(lines) == 2
    assert "fix/y" in lines[0]
    assert ".claude/hooks/a.py" in lines[1] and "2 파일" in lines[1]


def test_a_detached_head_is_not_main():
    assert "분리된 HEAD" in fresh.advice("HEAD", [])[0]
