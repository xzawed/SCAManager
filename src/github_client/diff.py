from dataclasses import dataclass
from github import Github


@dataclass
class ChangedFile:
    filename: str
    content: str
    patch: str


def get_pr_files(github_token: str, repo_name: str, pr_number: int) -> list[ChangedFile]:
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    return _collect_python_files(repo, pr.get_files(), pr.head.sha)


def get_push_files(github_token: str, repo_name: str, commit_sha: str) -> list[ChangedFile]:
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    commit = repo.get_commit(commit_sha)
    return _collect_python_files(repo, commit.files, commit_sha)


def _collect_python_files(repo, files, ref: str) -> list[ChangedFile]:
    result = []
    for f in files:
        if not f.filename.endswith(".py"):
            continue
        try:
            content = repo.get_contents(f.filename, ref=ref).decoded_content.decode("utf-8")
        except Exception:
            content = ""
        result.append(ChangedFile(
            filename=f.filename,
            content=content,
            patch=f.patch or "",
        ))
    return result
