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
from src.worker.pipeline import (
    _extract_commit_message,
    _extract_event_metadata,
    _extract_pr_head_ref,
)


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


def test_pr_pull_request_present_but_none_returns_empty():
    """pull_request 키가 present-but-None 일 때 AttributeError 없이 '' 반환.
    When pull_request key is present-but-None, returns '' without AttributeError.

    GitHub 가 키를 None 으로 보내는 경우 default `{}` 가 적용되지 않아 회귀 (PR #124 패턴).
    GitHub may send the key as None — the default `{}` is not applied (PR #124 pattern).
    """
    data = {"pull_request": None}
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


# ──────────────────────────────────────────────────────────────────────────
# _extract_pr_head_ref — PR head 브랜치 ref 추출 (None-안전)
# _extract_pr_head_ref — extract PR head branch ref (None-safe)
# ──────────────────────────────────────────────────────────────────────────


def test_head_ref_returns_branch_on_pull_request():
    """정상 PR 페이로드에서 head.ref 반환."""
    data = {"pull_request": {"head": {"ref": "feature/x"}}}
    assert _extract_pr_head_ref("pull_request", data) == "feature/x"


def test_head_ref_none_when_not_pull_request_event():
    """pull_request 이벤트가 아니면 None (push 등)."""
    data = {"pull_request": {"head": {"ref": "feature/x"}}}
    assert _extract_pr_head_ref("push", data) is None


def test_head_ref_pull_request_present_but_none_returns_none():
    """pull_request 가 present-but-None 일 때 AttributeError 없이 None (PR #124 패턴).
    When pull_request is present-but-None, returns None without AttributeError.
    """
    data = {"pull_request": None}
    assert _extract_pr_head_ref("pull_request", data) is None


def test_head_ref_head_present_but_none_returns_none():
    """head 키가 present-but-None 일 때 AttributeError 없이 None."""
    data = {"pull_request": {"head": None}}
    assert _extract_pr_head_ref("pull_request", data) is None


def test_head_ref_missing_keys_returns_none():
    """head/ref 키가 아예 없으면 None."""
    assert _extract_pr_head_ref("pull_request", {}) is None
    assert _extract_pr_head_ref("pull_request", {"pull_request": {}}) is None


# ──────────────────────────────────────────────────────────────────────────
# _extract_event_metadata — head present-but-None 안전성 (PR #124 패턴)
# _extract_event_metadata — head present-but-None safety (PR #124 pattern)
# ──────────────────────────────────────────────────────────────────────────


def test_event_metadata_pr_head_present_but_none_returns_empty_sha():
    """PR 이벤트에서 head 키가 present-but-None 이면 commit_sha='' (AttributeError 없음).
    When head is present-but-None on a PR event, commit_sha is '' without AttributeError.
    """
    data = {"number": 7, "pull_request": {"head": None}, "repository": {"full_name": "o/r"}}
    repo_name, commit_sha, _msg, pr_number = _extract_event_metadata("pull_request", data)
    assert repo_name == "o/r"
    assert commit_sha == ""
    assert pr_number == 7
