"""GitHub API client for fetching changed files from PRs and push commits."""
import logging

from github import Github, GithubException

from src.github_client.models import ChangedFile

logger = logging.getLogger(__name__)


def get_pr_files(github_token: str, repo_name: str, pr_number: int) -> list[ChangedFile]:
    """Fetch all changed files for a given pull request."""
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    return _collect_changed_files(repo, pr.get_files(), pr.head.sha)


def get_push_files(github_token: str, repo_name: str, commit_sha: str) -> list[ChangedFile]:
    """Fetch all changed files for a given push commit SHA."""
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    commit = repo.get_commit(commit_sha)
    return _collect_changed_files(repo, commit.files, commit_sha)


def _collect_changed_files(repo, files, ref: str) -> list[ChangedFile]:
    """Collect file content and patch for each changed file in the given ref."""
    result = []
    for f in files:
        try:
            content = repo.get_contents(f.filename, ref=ref).decoded_content.decode("utf-8")
        except (GithubException, UnicodeDecodeError) as exc:
            logger.debug("파일 내용 로드 실패 %s@%s: %s", f.filename, ref, exc)
            content = ""
        result.append(ChangedFile(
            filename=f.filename,
            content=content,
            patch=f.patch or "",
        ))
    return result
