"""Git Bash 경로를 Windows 경로로 — 막는 훅 둘이 함께 쓰는 도우미와 그 배선 (원장 #1940 M06 P1-24).
Git Bash paths become Windows paths: the helper both blocking hooks share, and its wiring.

Windows 의 Python 은 `/c/x` · `/tmp/x` 를 작업 드라이브 아래로 연다 — Git Bash 는 `C:\\x` · 사용자 임시 폴더로 연다. 그래서 훅이
정직한 명령을 막고(없는 폴더), `/tmp` 는 다른 파일을 재고 통과시켰다. 규칙 시험은 플랫폼 판정을 바꿔 리눅스 CI 에서도 돈다.
"""
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / ".claude" / "hooks"))
import block_credential_dump as hook  # noqa: E402
import git_bash_paths  # noqa: E402
from scripts import scan_publish  # noqa: E402
from tests.unit.scripts.test_scan_publish import _PLANTED, _denied, _hook  # noqa: E402


@pytest.fixture
def on_windows(monkeypatch):
    """Git for Windows 의 마운트를 고정한 Windows — `/tmp` 는 사용자 임시 폴더, 그 밖은 Git 설치 뿌리 아래(`cygpath -m /<맨 위>`).
    Windows with fixed Git Bash mounts."""
    monkeypatch.setattr(git_bash_paths, "_ON_WINDOWS", True)
    mounts = {"": "D:/Tools/Git", "tmp": "D:/scratch/Temp"}
    monkeypatch.setattr(git_bash_paths, "_mount", lambda top: mounts.get(top, f"D:/Tools/Git/{top}"))


@pytest.mark.parametrize("bash, windows", [
    ("/c/work/body.md", "C:/work/body.md"),
    ("/f", "F:/"),
    ("/tmp", "D:/scratch/Temp"),
    ("/tmp/body.md", "D:/scratch/Temp/body.md"),
    ("/usr/bin/env", "D:/Tools/Git/usr/bin/env"),
    ("/dev/null", "NUL"),
    ("/dev/stdin", None),
    # Grok(9f9325d6) — `..` 는 마운트 경계를 넘는다: Git Bash 는 바꾸기 전에 글자로 접는다 / `..` folds before mapping
    ("/tmp/../etc/passwd", "D:/Tools/Git/etc/passwd"),
    ("/usr/../../c/Windows/win.ini", "C:/Windows/win.ini"),
    ("/c/../tmp/body.md", "D:/scratch/Temp/body.md"),
    ("/proc/cpuinfo", None),
    # Grok(275e94e9) — 빗금 셋 이상은 하나다(POSIX) · Cygwin 은 `\` 도 구분자로 본다 / 3+ slashes are one; `\` separates
    ("///etc/passwd", "D:/Tools/Git/etc/passwd"),
    ("/c\\Windows\\win.ini", "C:/Windows/win.ini"),
    ("/", "D:/Tools/Git"),
    ("C:/work/body.md", "C:/work/body.md"),
    ("docs/body.md", "docs/body.md"),
    ("//server/share/body.md", "//server/share/body.md"),
])
def test_git_bash_paths_become_the_windows_paths_bash_opens(bash, windows, on_windows):
    """`/x/…` 는 드라이브 · `/tmp` 는 임시 폴더 · 그 밖의 뿌리는 Git 설치 아래 · 장치는 모름(None) · 나머지는 그대로."""
    assert git_bash_paths.git_bash_to_windows(bash) == windows


def test_a_root_path_is_unknown_without_cygpath(on_windows, monkeypatch):
    """🔴 마운트를 못 물으면 `/usr/…` · `/tmp/…` 은 어디를 여는지 모른다 — None(막는 쪽)이지 작업 드라이브 아래가 아니다."""
    monkeypatch.setattr(git_bash_paths, "_mount", lambda top: None)
    assert [git_bash_paths.git_bash_to_windows(p) for p in ("/usr/bin/env", "/tmp/body.md")] == [None, None]


def test_tmp_follows_the_mount_not_the_python_temp_folder(on_windows, monkeypatch):
    """🔴 `/tmp` 는 Git Bash 의 마운트(fstab)를 따른다 — 사용자가 옮겼으면 Python 의 임시 폴더가 아니다(Grok 275e94e9)."""
    monkeypatch.setattr(git_bash_paths, "_mount", lambda top: {"tmp": "E:/custom-tmp"}.get(top, "D:/Tools/Git"))
    assert git_bash_paths.git_bash_to_windows("/tmp/body.md") == "E:/custom-tmp/body.md"


def test_nothing_changes_outside_windows(monkeypatch):
    """리눅스 · macOS 의 `/tmp` · `/c` 는 그 글자 그대로다."""
    monkeypatch.setattr(git_bash_paths, "_ON_WINDOWS", False)
    assert [git_bash_paths.git_bash_to_windows(p) for p in ("/tmp/x", "/c/x")] == ["/tmp/x", "/c/x"]


def test_both_blocking_hooks_use_the_shared_helper():
    """🔴 두 훅이 같은 도우미를 쓴다 — 불러오기에 실패해 막는 쪽 대체 함수로 떨어지면 정직한 Git Bash 경로가 다시 막힌다."""
    assert hook.git_bash_to_windows is git_bash_paths.git_bash_to_windows
    assert scan_publish.git_bash_to_windows is git_bash_paths.git_bash_to_windows


def _fake_git_bash(tmp_path):
    """`/fake/…` 를 tmp_path 아래로 여는 Git Bash — 플랫폼과 상관없이 배선을 잰다 / a Git Bash that opens /fake under tmp_path."""
    root = str(tmp_path).replace("\\", "/")
    return lambda path: root + path[len("/fake"):] if path.startswith("/fake") else path


def test_the_credential_hook_looks_in_the_folder_bash_opens(tmp_path, monkeypatch):
    """🔴 credential 훅은 Git Bash 경로의 와일드카드를 Bash 가 여는 폴더에서 잰다 — .env 꼴이 없으면 통과, 있으면 막힘.
    (예전엔 작업 드라이브 아래 없는 폴더를 재 늘 막았고, `/tmp` 는 다른 폴더를 재 통과시켰다.)"""
    (tmp_path / "dir").mkdir()
    (tmp_path / "dir" / "README.md").write_text("notes\n", encoding="utf-8")
    monkeypatch.setattr(hook, "git_bash_to_windows", _fake_git_bash(tmp_path))
    assert hook.decide_with_hint("cat /fake/dir/*", str(tmp_path), "bash") is None
    (tmp_path / "dir" / "prod.env").write_text("A=1\n", encoding="utf-8")
    assert hook.decide_with_hint("cat /fake/dir/*", str(tmp_path), "bash") is not None


def test_a_git_bash_absolute_path_stays_absolute_when_the_cwd_is_unknown(tmp_path, monkeypatch):
    """🔴 작업 폴더를 모를 때(`cd "$X"`)도 Git Bash 절대 경로는 절대 경로다 — Python 3.13+ 의 Windows 는 `/…` 를 상대 경로로 봐
    «작업 폴더를 몰라 못 잰다» 로 막았다(라이브 훅은 3.14 로 돈다)."""
    (tmp_path / "dir").mkdir()
    (tmp_path / "dir" / "README.md").write_text("notes\n", encoding="utf-8")
    monkeypatch.setattr(hook, "git_bash_to_windows", _fake_git_bash(tmp_path))
    assert hook.decide_with_hint('cd "$X" && cat /fake/dir/*', str(tmp_path), "bash") is None


def test_the_credential_hook_does_not_translate_powershell_paths(tmp_path, monkeypatch):
    """대조군 — PowerShell 은 Git Bash 가 아니다: `/fake/…` 를 바꾸지 않는다(없는 폴더라 막는 쪽)."""
    (tmp_path / "dir").mkdir()
    monkeypatch.setattr(hook, "git_bash_to_windows", _fake_git_bash(tmp_path))
    assert hook.decide_with_hint("cat /fake/dir/*", str(tmp_path), "powershell") is not None


def test_the_publish_scan_reads_the_body_file_bash_opens(tmp_path, monkeypatch, capsys):
    """🔴 게시 전 검사는 Git Bash 경로의 본문 파일을 Bash 가 여는 파일에서 잰다 — 깨끗하면 통과, 꼴이면 막힘."""
    (tmp_path / "clean.md").write_text("clean body\n", encoding="utf-8")
    (tmp_path / "dirty.md").write_text(_PLANTED["email"] + "\n", encoding="utf-8")
    monkeypatch.setattr(scan_publish, "git_bash_to_windows", _fake_git_bash(tmp_path))
    assert _hook(monkeypatch, capsys, "gh pr comment 1 --body-file /fake/clean.md", tmp_path) is None
    assert _denied(_hook(monkeypatch, capsys, "gh pr comment 1 --body-file /fake/dirty.md", tmp_path))


def test_the_publish_scan_denies_a_body_path_bash_cannot_place(tmp_path, monkeypatch, capsys):
    """🔴 어디를 여는지 모르는 Git Bash 경로(장치 · Git 뿌리를 못 물음)의 본문은 못 잰 것이다 — 막는다."""
    monkeypatch.setattr(scan_publish, "git_bash_to_windows", lambda path: None if path.startswith("/") else path)
    assert _denied(_hook(monkeypatch, capsys, "gh pr comment 1 --body-file /usr/share/body.md", tmp_path))
