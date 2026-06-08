"""GitHub API client for fetching changed files from PRs and push commits."""
import logging

from github import Auth, Github, GithubException

from src.constants import HTTP_CLIENT_TIMEOUT
from src.github_client.models import ChangedFile
from src.shared.log_safety import sanitize_for_log

logger = logging.getLogger(__name__)


def _make_github_client(token: str) -> Github:
    return Github(auth=Auth.Token(token), timeout=int(HTTP_CLIENT_TIMEOUT))


def get_pr_files(github_token: str, repo_name: str, pr_number: int) -> list[ChangedFile]:
    """Fetch all changed files for a given pull request."""
    g = _make_github_client(github_token)
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    return _collect_changed_files(repo, pr.get_files(), pr.head.sha)


def get_push_files(github_token: str, repo_name: str, commit_sha: str) -> list[ChangedFile]:
    """Fetch all changed files for a given push commit SHA."""
    g = _make_github_client(github_token)
    repo = g.get_repo(repo_name)
    commit = repo.get_commit(commit_sha)
    return _collect_changed_files(repo, commit.files, commit_sha)


def _collect_changed_files(repo, files, ref: str) -> list[ChangedFile]:
    """Collect file content and patch for each changed file in the given ref.

    transient fetch 실패(403 rate-limit/5xx)는 fetch_failed=True 로 표시해 호출 파이프라인이
    미분석 코드를 incomplete 로 fail-closed 처리하게 한다. 404(삭제 파일)·UnicodeDecodeError
    (바이너리/비-UTF8)는 정상 케이스이므로 content='' + fetch_failed=False.
    Transient fetch failures (403 rate-limit/5xx) set fetch_failed=True so the pipeline can
    fail-closed; 404 (deleted) and decode errors are legitimate (fetch_failed=False).
    """
    result = []
    for f in files:
        fetch_failed = False
        try:
            content = repo.get_contents(f.filename, ref=ref).decoded_content.decode("utf-8")
        except GithubException as exc:
            # 404 = 삭제된 파일(정상). 그 외(403 secondary rate-limit·5xx)는 transient → fail-closed.
            # 404 = deleted file (legitimate); others (403 rate-limit, 5xx) are transient.
            content = ""
            fetch_failed = getattr(exc, "status", None) != 404
            logger.debug("파일 내용 로드 실패 %s@%s: %s", sanitize_for_log(f.filename), sanitize_for_log(ref), exc)
        except UnicodeDecodeError as exc:
            # 바이너리/비-UTF8 파일 — 분석 불가하나 fetch 자체는 성공 (정상)
            # Binary/non-UTF8 file — not analyzable but the fetch itself succeeded (legitimate)
            content = ""
            logger.debug("파일 디코드 실패 %s@%s: %s", sanitize_for_log(f.filename), sanitize_for_log(ref), exc)
        result.append(ChangedFile(
            filename=f.filename,
            content=content,
            patch=f.patch or "",
            fetch_failed=fetch_failed,
        ))
    return result
