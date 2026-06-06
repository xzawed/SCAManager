from unittest.mock import MagicMock, patch
from src.github_client.diff import get_pr_files, get_push_files, ChangedFile
from src.constants import HTTP_CLIENT_TIMEOUT


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
    assert MockGithub.call_args.kwargs.get("timeout") == int(HTTP_CLIENT_TIMEOUT)
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
    assert MockGithub.call_args.kwargs.get("timeout") == int(HTTP_CLIENT_TIMEOUT)
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


def test_collect_changed_files_log_sanitizes_filename_and_ref(caplog):
    """파일 로드 실패 debug 로그가 filename·ref 를 sanitize 해 CR/LF 로그 인젝션을 차단한다.
    The file-load-failure log sanitizes filename/ref so CR/LF cannot inject fake log lines."""
    import logging
    from github import GithubException
    from src.github_client.diff import _collect_changed_files

    mock_repo = MagicMock()
    mock_repo.get_contents.side_effect = GithubException(404, "Not found")
    f = MagicMock()
    f.filename = "evil.py\nINJECTED-FAKE-LOG-LINE"
    f.patch = ""

    with caplog.at_level(logging.DEBUG, logger="src.github_client.diff"):
        _collect_changed_files(mock_repo, [f], "main\nINJECTED-REF")

    msgs = [r.getMessage() for r in caplog.records]
    assert msgs, "파일 로드 실패 시 debug 로그가 기록되어야 함"
    # 개행이 그대로 들어가면 가짜 로그 라인 주입 가능 — sanitize_for_log 가 제거해야 함
    # Raw newlines would allow fake log-line injection — sanitize_for_log must strip them.
    for m in msgs:
        assert "\n" not in m, f"로그 라인에 개행 주입됨 (sanitize 누락): {m!r}"
