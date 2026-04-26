"""tests/unit/worker/test_extract_author_login.py — _extract_author_login() 단위 테스트 (Red 상태).
tests/unit/worker/test_extract_author_login.py — Unit tests for _extract_author_login() (Red state).

환경변수는 src 임포트 전 반드시 주입해야 한다.
Environment variables must be injected before any src.* imports.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

from src.worker.pipeline import _extract_author_login  # noqa: E402


# ── 픽스처: PR 이벤트 페이로드 샘플 ──
# ── Fixture: sample PR event payload ──
_PR_DATA = {
    "pull_request": {
        "user": {
            "login": "octocat"
        }
    }
}

# ── 픽스처: push 이벤트 페이로드 샘플 ──
# ── Fixture: sample push event payload ──
_PUSH_DATA = {
    "head_commit": {
        "author": {
            "username": "monalisa"
        }
    }
}


def test_pr_event_returns_pull_request_user_login():
    # PR 이벤트에서 pull_request.user.login 값을 반환한다
    # Returns pull_request.user.login for a PR event.
    result = _extract_author_login("pull_request", _PR_DATA)
    assert result == "octocat"


def test_push_event_returns_head_commit_author_username():
    # push 이벤트에서 head_commit.author.username 값을 반환한다
    # Returns head_commit.author.username for a push event.
    result = _extract_author_login("push", _PUSH_DATA)
    assert result == "monalisa"


def test_pr_event_missing_pull_request_key_returns_none():
    # PR 이벤트에서 pull_request 키가 없으면 None을 반환한다
    # Returns None when pull_request key is absent in a PR event.
    result = _extract_author_login("pull_request", {})
    assert result is None


def test_push_event_missing_head_commit_key_returns_none():
    # push 이벤트에서 head_commit 키가 없으면 None을 반환한다
    # Returns None when head_commit key is absent in a push event.
    result = _extract_author_login("push", {})
    assert result is None


def test_push_event_missing_author_key_returns_none():
    # push 이벤트에서 head_commit.author 키가 없으면 None을 반환한다
    # Returns None when head_commit.author key is absent in a push event.
    result = _extract_author_login("push", {"head_commit": {}})
    assert result is None


def test_unknown_event_type_returns_none():
    # 알 수 없는 event_type이면 None을 반환한다
    # Returns None for an unrecognized event_type.
    result = _extract_author_login("unknown_event", _PR_DATA)
    assert result is None


def test_pr_event_missing_user_key_returns_none():
    # PR 이벤트에서 pull_request.user 키가 없으면 None을 반환한다
    # Returns None when pull_request.user key is absent.
    result = _extract_author_login("pull_request", {"pull_request": {}})
    assert result is None


def test_push_event_missing_username_key_returns_none():
    # push 이벤트에서 head_commit.author.username 키가 없으면 None을 반환한다
    # Returns None when head_commit.author.username key is absent.
    result = _extract_author_login("push", {"head_commit": {"author": {}}})
    assert result is None
