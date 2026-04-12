"""Local git diff collection for CLI usage — reads diffs from the working repo."""
import logging
import re
import subprocess  # nosec B404

from src.github_client.models import ChangedFile

logger = logging.getLogger(__name__)

_TIMEOUT = 30
_BINARY_PATTERN = re.compile(r"^Binary files", re.MULTILINE)


class GitError(Exception):
    """Raised when a git operation fails."""


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(  # nosec B603 B607
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            check=check,
        )
    except FileNotFoundError as exc:
        raise GitError("git is not installed or not in PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"git command timeout after {_TIMEOUT}s") from exc
    except subprocess.CalledProcessError as exc:
        raise GitError(f"git command failed: {exc.stderr or exc}") from exc


def get_diff_files(
    base: str = "HEAD~1", staged: bool = False
) -> list[ChangedFile]:
    """로컬 git diff로 변경 파일 목록과 패치를 수집한다."""
    if staged:
        result = _git("diff", "--cached", "--name-status", check=False)
    else:
        result = _git("diff", "--name-status", base, check=False)

    lines = [ln for ln in result.stdout.strip().splitlines() if ln.strip()]
    if not lines:
        return []

    files: list[ChangedFile] = []
    for line in lines:
        parts = line.split("\t", 1)
        if len(parts) < 2:
            continue
        status, filename = parts[0], parts[1]

        # get patch
        if staged:
            patch_result = _git("diff", "--cached", "--", filename, check=False)
        else:
            patch_result = _git("diff", base, "--", filename, check=False)
        patch = patch_result.stdout

        # skip binary files
        if _BINARY_PATTERN.search(patch):
            continue

        # get file content (empty for deleted files)
        content = ""
        if status != "D":
            content_result = _git("show", "HEAD:" + filename, check=False)
            if content_result.returncode == 0:
                content = content_result.stdout

        files.append(ChangedFile(filename=filename, content=content, patch=patch))

    return files


def get_commit_message(base: str = "HEAD~1") -> str:
    """base부터 HEAD까지 커밋 메시지를 반환한다."""
    result = _git("log", "--format=%B", f"{base}..HEAD", check=False)
    return result.stdout.strip()


def get_repo_name() -> str:
    """git remote origin URL에서 owner/repo 형태의 리포 이름을 추출한다."""
    try:
        result = _git("remote", "get-url", "origin")
    except GitError:
        return ""

    url = result.stdout.strip()
    # SSH: git@github.com:owner/repo.git
    m = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    return m.group(1) if m else ""
