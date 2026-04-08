"""Tests for src.cli.git_diff — local git diff collection."""
from unittest.mock import patch, MagicMock
import subprocess
import pytest

from src.cli.git_diff import (
    ChangedFile,
    GitError,
    get_diff_files,
    get_commit_message,
    get_repo_name,
)


# ── helpers ──────────────────────────────────────────────

def _run_result(stdout="", stderr="", returncode=0):
    r = MagicMock()
    r.stdout = stdout
    r.stderr = stderr
    r.returncode = returncode
    return r


# ── get_diff_files ───────────────────────────────────────

@patch("subprocess.run")
def test_get_diff_files_parses_output(mock_run):
    """Changed file list is parsed from git diff --name-status."""
    mock_run.side_effect = [
        # 1) git diff --name-status
        _run_result(stdout="M\tsrc/app.py\nA\tsrc/new.py\n"),
        # 2) git diff patch for src/app.py
        _run_result(stdout="--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-old\n+new"),
        # 3) file content for src/app.py
        _run_result(stdout="new content"),
        # 4) git diff patch for src/new.py
        _run_result(stdout="--- /dev/null\n+++ b/src/new.py\n@@ -0,0 +1 @@\n+hello"),
        # 5) file content for src/new.py
        _run_result(stdout="hello"),
    ]
    files = get_diff_files(base="HEAD~1")
    assert len(files) == 2
    assert files[0].filename == "src/app.py"
    assert "new content" in files[0].content
    assert files[1].filename == "src/new.py"


@patch("subprocess.run")
def test_get_diff_files_staged_uses_cached(mock_run):
    """--staged flag passes --cached to git diff."""
    mock_run.side_effect = [
        _run_result(stdout=""),  # no files
    ]
    get_diff_files(staged=True)
    call_args = mock_run.call_args_list[0][0][0]
    assert "--cached" in call_args


@patch("subprocess.run")
def test_get_diff_files_deleted_file(mock_run):
    """Deleted files have empty content but patch is preserved."""
    mock_run.side_effect = [
        _run_result(stdout="D\tsrc/old.py\n"),
        # patch
        _run_result(stdout="--- a/src/old.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-removed"),
        # content read fails (file deleted)
        _run_result(stdout="", returncode=128, stderr="fatal: path not found"),
    ]
    files = get_diff_files()
    assert len(files) == 1
    assert files[0].content == ""
    assert "removed" in files[0].patch


@patch("subprocess.run")
def test_get_diff_files_no_changes(mock_run):
    """Returns empty list when no files changed."""
    mock_run.return_value = _run_result(stdout="")
    files = get_diff_files()
    assert files == []


@patch("subprocess.run")
def test_get_diff_files_binary_skipped(mock_run):
    """Binary files are excluded from results."""
    mock_run.side_effect = [
        _run_result(stdout="M\timage.png\n"),
        # patch returns binary notice
        _run_result(stdout="Binary files differ"),
        _run_result(stdout="", returncode=128),
    ]
    files = get_diff_files()
    assert len(files) == 0


@patch("subprocess.run")
def test_get_diff_files_git_not_found(mock_run):
    """Raises GitError when git is not installed."""
    mock_run.side_effect = FileNotFoundError("git not found")
    with pytest.raises(GitError, match="git"):
        get_diff_files()


@patch("subprocess.run")
def test_get_diff_files_timeout(mock_run):
    """Raises GitError on subprocess timeout."""
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=30)
    with pytest.raises(GitError, match="timeout"):
        get_diff_files()


# ── get_commit_message ──────────────────────────────────

@patch("subprocess.run")
def test_get_commit_message_single(mock_run):
    """Returns single commit message."""
    mock_run.return_value = _run_result(stdout="feat: add new feature\n")
    msg = get_commit_message()
    assert msg == "feat: add new feature"


@patch("subprocess.run")
def test_get_commit_message_multi(mock_run):
    """Returns concatenated messages for multi-commit range."""
    mock_run.return_value = _run_result(
        stdout="fix: second commit\n\nfeat: first commit\n"
    )
    msg = get_commit_message(base="HEAD~2")
    assert "fix: second commit" in msg
    assert "feat: first commit" in msg


@patch("subprocess.run")
def test_get_commit_message_empty(mock_run):
    """Returns empty string when no commits found."""
    mock_run.return_value = _run_result(stdout="")
    assert get_commit_message() == ""


# ── get_repo_name ───────────────────────────────────────

@patch("subprocess.run")
def test_get_repo_name_https(mock_run):
    """Parses owner/repo from HTTPS remote URL."""
    mock_run.return_value = _run_result(
        stdout="https://github.com/owner/repo.git\n"
    )
    assert get_repo_name() == "owner/repo"


@patch("subprocess.run")
def test_get_repo_name_ssh(mock_run):
    """Parses owner/repo from SSH remote URL."""
    mock_run.return_value = _run_result(
        stdout="git@github.com:owner/repo.git\n"
    )
    assert get_repo_name() == "owner/repo"


@patch("subprocess.run")
def test_get_repo_name_no_remote(mock_run):
    """Falls back to empty string when no remote."""
    mock_run.side_effect = subprocess.CalledProcessError(128, "git")
    assert get_repo_name() == ""
