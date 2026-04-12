from unittest.mock import MagicMock, patch
from src.github_client.diff import get_pr_files, get_push_files, ChangedFile


def _make_mock_file(filename, patch_text, content_bytes):
    f = MagicMock()
    f.filename = filename
    f.patch = patch_text
    contents = MagicMock()
    contents.decoded_content = content_bytes
    return f, contents


def test_get_pr_files_returns_all_file_types():
    mock_file_py, mock_contents_py = _make_mock_file(
        "src/app.py", "@@ -1 +1 @@\n+import os", b"import os\n"
    )
    mock_file_md, mock_contents_md = _make_mock_file(
        "README.md", "@@ -1 +1 @@\n+# hi", b"# hi\n"
    )
    mock_pr = MagicMock()
    mock_pr.head.sha = "abc123"
    mock_pr.get_files.return_value = [mock_file_py, mock_file_md]
    mock_repo = MagicMock()
    mock_repo.get_pull.return_value = mock_pr
    mock_repo.get_contents.side_effect = [mock_contents_py, mock_contents_md]
    with patch("src.github_client.diff.Github") as MockGithub:
        MockGithub.return_value.get_repo.return_value = mock_repo
        result = get_pr_files("token", "owner/repo", 1)
    assert len(result) == 2
    assert result[0].filename == "src/app.py"
    assert result[1].filename == "README.md"


def test_get_push_files_returns_all_file_types():
    mock_file_py, mock_contents_py = _make_mock_file("utils.py", "@@ +1 @@\n+x=1", b"x=1\n")
    mock_file_js, mock_contents_js = _make_mock_file("app.js", "@@ +1 @@\n+var a", b"var a\n")
    mock_commit = MagicMock()
    mock_commit.files = [mock_file_py, mock_file_js]
    mock_repo = MagicMock()
    mock_repo.get_commit.return_value = mock_commit
    mock_repo.get_contents.side_effect = [mock_contents_py, mock_contents_js]
    with patch("src.github_client.diff.Github") as MockGithub:
        MockGithub.return_value.get_repo.return_value = mock_repo
        result = get_push_files("token", "owner/repo", "abc123")
    assert len(result) == 2
    assert result[0].filename == "utils.py"
    assert result[1].filename == "app.js"


def test_get_pr_files_handles_content_error():
    mock_file, _ = _make_mock_file("broken.py", "@@ +1 @@", b"")
    mock_pr = MagicMock()
    mock_pr.head.sha = "abc123"
    mock_pr.get_files.return_value = [mock_file]
    mock_repo = MagicMock()
    mock_repo.get_pull.return_value = mock_pr
    from github import GithubException
    mock_repo.get_contents.side_effect = GithubException(404, "Not found")
    with patch("src.github_client.diff.Github") as MockGithub:
        MockGithub.return_value.get_repo.return_value = mock_repo
        result = get_pr_files("token", "owner/repo", 1)
    assert result[0].content == ""
