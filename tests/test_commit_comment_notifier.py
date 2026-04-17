"""Tests for src/notifier/commit_comment.py — commit-level AI review comment notifier.

Phase 3-A Red: src/notifier/commit_comment.py 모듈 및 post_commit_comment_from_result
함수가 아직 존재하지 않으므로 모든 테스트는 ImportError 또는 AssertionError로 실패해야 한다.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch


def _make_result(**kwargs):
    """테스트용 Analysis.result dict."""
    base = {
        "score": 82,
        "grade": "B",
        "breakdown": {
            "commit_message": 13,
            "code_quality": 22,
            "security": 18,
            "ai_review": 20,
            "test_coverage": 9,
        },
        "ai_summary": "main.py에 새로운 기능이 추가되었습니다.",
        "file_feedbacks": [
            {"file": "src/main.py", "issues": ["라인 42: 변수명 개선 필요"]},
        ],
        "ai_suggestions": ["타입 힌트 추가 권장"],
        "issues": [
            {"tool": "pylint", "message": "unused-import", "line": 3},
        ],
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# 정상 케이스 — URL / body / headers 검증
# ---------------------------------------------------------------------------

async def test_post_commit_comment_calls_correct_url():
    """GitHub commit comments API(POST /repos/{repo}/commits/{sha}/comments)가 호출되어야 한다."""
    from src.notifier.commit_comment import post_commit_comment_from_result

    with patch("src.notifier.commit_comment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await post_commit_comment_from_result(
            github_token="ghp_test",
            repo_name="owner/repo",
            commit_sha="abc123def",
            result=_make_result(),
        )

    mock_client.post.assert_called_once()
    url = mock_client.post.call_args[0][0]
    # URL 형식: https://api.github.com/repos/{owner}/{repo}/commits/{sha}/comments
    assert "api.github.com" in url
    assert "owner/repo" in url
    assert "commits/abc123def/comments" in url


async def test_post_commit_comment_body_contains_score_and_grade():
    """요청 body의 'body' 필드에 총점·등급이 포함되어야 한다."""
    from src.notifier.commit_comment import post_commit_comment_from_result

    with patch("src.notifier.commit_comment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await post_commit_comment_from_result(
            github_token="ghp_test",
            repo_name="owner/repo",
            commit_sha="deadbeef",
            result=_make_result(score=88, grade="B"),
        )

    payload = mock_client.post.call_args[1]["json"]
    assert "body" in payload
    assert "88/100" in payload["body"]
    assert "B" in payload["body"]


async def test_post_commit_comment_body_includes_ai_summary():
    """요청 body에 result의 ai_summary가 포함되어야 한다."""
    from src.notifier.commit_comment import post_commit_comment_from_result

    with patch("src.notifier.commit_comment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await post_commit_comment_from_result(
            github_token="ghp_test",
            repo_name="owner/repo",
            commit_sha="abc",
            result=_make_result(ai_summary="특별한 AI 요약 텍스트입니다."),
        )

    payload = mock_client.post.call_args[1]["json"]
    assert "특별한 AI 요약 텍스트입니다." in payload["body"]


async def test_post_commit_comment_body_includes_file_feedbacks():
    """요청 body에 file_feedbacks의 파일 경로와 이슈가 포함되어야 한다."""
    from src.notifier.commit_comment import post_commit_comment_from_result

    with patch("src.notifier.commit_comment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await post_commit_comment_from_result(
            github_token="ghp_test",
            repo_name="owner/repo",
            commit_sha="abc",
            result=_make_result(file_feedbacks=[
                {"file": "src/app.py", "issues": ["라인 10: 변수명 개선 필요"]},
            ]),
        )

    body = mock_client.post.call_args[1]["json"]["body"]
    assert "src/app.py" in body
    assert "변수명 개선 필요" in body


# ---------------------------------------------------------------------------
# 인증 헤더 검증 — github_api_headers 재사용
# ---------------------------------------------------------------------------

async def test_post_commit_comment_sets_authorization_header():
    """요청 headers의 Authorization이 'Bearer {token}' 형식이어야 한다."""
    from src.notifier.commit_comment import post_commit_comment_from_result

    with patch("src.notifier.commit_comment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await post_commit_comment_from_result(
            github_token="ghp_secret_abc",
            repo_name="owner/repo",
            commit_sha="abc",
            result=_make_result(),
        )

    headers = mock_client.post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer ghp_secret_abc"


async def test_post_commit_comment_sets_accept_header():
    """요청 headers에 GitHub API Accept 헤더가 포함되어야 한다 (github_api_headers 재사용 확인)."""
    from src.notifier.commit_comment import post_commit_comment_from_result

    with patch("src.notifier.commit_comment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await post_commit_comment_from_result(
            github_token="ghp_test",
            repo_name="owner/repo",
            commit_sha="abc",
            result=_make_result(),
        )

    headers = mock_client.post.call_args[1]["headers"]
    assert headers.get("Accept") == "application/vnd.github+json"


# ---------------------------------------------------------------------------
# keyword-only 시그니처 강제
# ---------------------------------------------------------------------------

async def test_post_commit_comment_requires_keyword_arguments():
    """post_commit_comment_from_result는 keyword-only 시그니처여야 한다."""
    from src.notifier.commit_comment import post_commit_comment_from_result

    with pytest.raises(TypeError):
        # positional 호출은 TypeError를 발생시켜야 함
        await post_commit_comment_from_result(
            "ghp_test", "owner/repo", "abc", _make_result()
        )


# ---------------------------------------------------------------------------
# 에러 처리 — raise_for_status 전파
# ---------------------------------------------------------------------------

async def test_post_commit_comment_raises_on_http_error():
    """HTTP 에러 발생 시 raise_for_status가 예외를 전파해야 한다."""
    from src.notifier.commit_comment import post_commit_comment_from_result

    with patch("src.notifier.commit_comment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("422", request=MagicMock(), response=MagicMock())
        )
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        with pytest.raises(httpx.HTTPStatusError):
            await post_commit_comment_from_result(
                github_token="ghp_test",
                repo_name="owner/repo",
                commit_sha="abc",
                result=_make_result(),
            )


# ---------------------------------------------------------------------------
# 공통 본문 빌더 재사용 — PR 댓글과 동일한 포맷
# ---------------------------------------------------------------------------

async def test_post_commit_comment_body_matches_pr_comment_format():
    """commit comment 본문은 PR comment와 동일한 _build_comment_from_result 포맷을 사용해야 한다."""
    from src.notifier.commit_comment import post_commit_comment_from_result
    from src.notifier.github_comment import _build_comment_from_result

    result = _make_result(score=77, grade="B", ai_summary="동일 포맷 확인")

    with patch("src.notifier.commit_comment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await post_commit_comment_from_result(
            github_token="ghp_test",
            repo_name="owner/repo",
            commit_sha="abc",
            result=result,
        )

    body = mock_client.post.call_args[1]["json"]["body"]
    # PR 댓글 빌더와 동일한 문자열이어야 한다 (재사용 검증)
    expected = _build_comment_from_result(result)
    assert body == expected
