"""Phase 4 PR-T2 — pipeline.py 헬퍼 함수 (_extract_commit_message) 단위 테스트.

기존 test_pipeline.py 가 commit message 추출을 happy path 만 다루어, 14-에이전트
감사 R1-B 의 "edge-case 분기 미검증" 갭을 좁힌다.

검증 대상 (worker/pipeline.py):
  - _extract_commit_message: PR title-only / title+body / body=None
  - _extract_commit_message: push head_commit / commits[-1] fallback
  - _extract_commit_message: 모든 분기 빈 페이로드 → ""
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

# pylint: disable=wrong-import-position
from src.worker.pipeline import _extract_commit_message


# ──────────────────────────────────────────────────────────────────────────
# pull_request 이벤트 분기
# ──────────────────────────────────────────────────────────────────────────


def test_pr_title_only_returns_title():
    """PR body 가 None 일 때 title 만 반환 (body 빈 줄 미추가)."""
    data = {"pull_request": {"title": "feat: add X", "body": None}}
    assert _extract_commit_message("pull_request", data) == "feat: add X"


def test_pr_title_with_body_concatenates():
    """PR title + body → 'title\\n\\nbody' 형태."""
    data = {"pull_request": {"title": "feat: X", "body": "Closes #1"}}
    assert _extract_commit_message("pull_request", data) == "feat: X\n\nCloses #1"


def test_pr_empty_body_string_returns_title_only():
    """PR body 가 빈 문자열일 때 title 만 반환."""
    data = {"pull_request": {"title": "fix: Y", "body": ""}}
    assert _extract_commit_message("pull_request", data) == "fix: Y"


def test_pr_missing_pull_request_key_returns_empty():
    """PR 페이로드에 pull_request 키 자체가 없으면 '' (방어적)."""
    data: dict = {}
    assert _extract_commit_message("pull_request", data) == ""


def test_pr_title_with_whitespace_body_strips():
    """body 가 공백만 있을 때 title+body 결합 후 strip 동작."""
    data = {"pull_request": {"title": "fix: Z", "body": "   "}}
    # f"{title}\n\n{body}".strip() — body 공백이지만 truthy → 결합 후 strip
    result = _extract_commit_message("pull_request", data)
    assert result.startswith("fix: Z")


# ──────────────────────────────────────────────────────────────────────────
# push 이벤트 분기
# ──────────────────────────────────────────────────────────────────────────


def test_push_head_commit_message_preferred():
    """head_commit 이 있으면 그 message 사용 (commits 무시)."""
    data = {
        "head_commit": {"message": "chore: update"},
        "commits": [{"message": "ignored"}],
    }
    assert _extract_commit_message("push", data) == "chore: update"


def test_push_head_commit_missing_message_returns_empty():
    """head_commit 존재하지만 message 키 없을 때 '' 반환."""
    data = {"head_commit": {"id": "abc"}}
    assert _extract_commit_message("push", data) == ""


def test_push_no_head_commit_uses_commits_last():
    """head_commit 없으면 commits[-1]['message'] 폴백."""
    data = {
        "head_commit": None,
        "commits": [
            {"message": "first"},
            {"message": "second"},
            {"message": "last"},
        ],
    }
    assert _extract_commit_message("push", data) == "last"


def test_push_empty_payload_returns_empty():
    """push 페이로드에 head_commit / commits 모두 없으면 ''."""
    assert _extract_commit_message("push", {}) == ""


def test_push_empty_commits_list_returns_empty():
    """commits=[] 일 때 '' 반환 (인덱스 에러 없음)."""
    data = {"head_commit": None, "commits": []}
    assert _extract_commit_message("push", data) == ""


def test_unknown_event_type_falls_through_to_push_branch():
    """event != 'pull_request' 면 push 분기 진입 — 알 수 없는 이벤트도 graceful."""
    data = {"head_commit": {"message": "via unknown"}}
    assert _extract_commit_message("issues", data) == "via unknown"
