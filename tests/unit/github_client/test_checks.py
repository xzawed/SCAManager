"""GitHub Check Runs / Status API 단위 테스트 (Phase 12 T4)."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.github_client.checks import (
    get_ci_status,
    get_required_check_contexts,
    _parse_link_next,
    _required_contexts_cache,
)

# ── 공통 픽스처 ──────────────────────────────────────────────────────────────
# ── Common fixtures ──────────────────────────────────────────────────────────

TOKEN = "ghp_testtoken"
REPO = "owner/myrepo"
SHA = "abc123def456"
BRANCH = "main"


def _resp(status_code: int, body: dict, headers: dict | None = None) -> MagicMock:
    """Mock httpx 응답 객체 생성 헬퍼.
    Helper to create a mock httpx response object.
    """
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = body
    r.headers = headers or {}
    r.raise_for_status = MagicMock()
    return r


def _check_run(name: str, status: str, conclusion: str | None = None) -> dict:
    """GitHub Check Run 딕셔너리 생성 헬퍼.
    Helper to create a GitHub Check Run dictionary.
    """
    return {"name": name, "status": status, "conclusion": conclusion}


@pytest.fixture(autouse=True)
def clear_cache():
    """각 테스트 후 캐시 클리어 (격리 보장).
    Clear cache after each test to ensure isolation.
    """
    _required_contexts_cache.clear()
    yield
    _required_contexts_cache.clear()


# ── get_ci_status — 기본 케이스 ───────────────────────────────────────────
# ── get_ci_status — base cases ────────────────────────────────────────────


async def test_get_ci_status_running_when_check_in_progress():
    """in_progress 상태 체크런이 있으면 'running' 반환.
    Returns 'running' when any check run is in_progress.
    """
    check_runs_body = {
        "check_runs": [_check_run("CI / test", "in_progress", None)],
        "total_count": 1,
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[
            _resp(200, check_runs_body),   # check-runs 1페이지 / check-runs page 1
        ]
    )

    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        result = await get_ci_status(TOKEN, REPO, SHA)

    assert result == "running"
    # check-runs 1회만 호출 — 레거시 API 미호출 / Only check-runs called — no legacy API call.
    assert mock_client.get.call_count == 1


async def test_get_ci_status_running_when_check_queued():
    """queued 상태 체크런이 있으면 'running' 반환.
    Returns 'running' when any check run is queued.
    """
    check_runs_body = {
        "check_runs": [_check_run("CI / test", "queued", None)],
        "total_count": 1,
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[
            _resp(200, check_runs_body),   # check-runs 1페이지 / check-runs page 1
        ]
    )

    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        result = await get_ci_status(TOKEN, REPO, SHA)

    assert result == "running"
    # check-runs 1회만 호출 — 레거시 API 미호출 / Only check-runs called — no legacy API call.
    assert mock_client.get.call_count == 1


async def test_get_ci_status_passed_when_all_success():
    """모든 체크런이 success/skipped/neutral 이면 'passed' 반환.
    Returns 'passed' when all check runs are success/skipped/neutral.
    """
    check_runs_body = {
        "check_runs": [
            _check_run("CI / lint", "completed", "success"),
            _check_run("CI / test", "completed", "skipped"),
            _check_run("CI / build", "completed", "neutral"),
        ],
        "total_count": 3,
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[
            _resp(200, check_runs_body),
        ]
    )

    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        result = await get_ci_status(TOKEN, REPO, SHA)

    assert result == "passed"
    # check-runs 1회만 호출 — 레거시 API 미호출 / Only check-runs called — no legacy API call.
    assert mock_client.get.call_count == 1


async def test_get_ci_status_failed_when_any_failed():
    """completed 체크런 중 하나라도 failure이면 'failed' 반환.
    Returns 'failed' when any completed check run has a failure conclusion.
    """
    check_runs_body = {
        "check_runs": [
            _check_run("CI / lint", "completed", "success"),
            _check_run("CI / test", "completed", "failure"),
        ],
        "total_count": 2,
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[
            _resp(200, check_runs_body),
        ]
    )

    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        result = await get_ci_status(TOKEN, REPO, SHA)

    assert result == "failed"
    # check-runs 1회만 호출 — 레거시 API 미호출 / Only check-runs called — no legacy API call.
    assert mock_client.get.call_count == 1


async def test_get_ci_status_unknown_when_no_checks():
    """체크런도 레거시 상태도 없으면 'unknown' 반환.
    Returns 'unknown' when there are no check runs and no legacy statuses.
    """
    check_runs_body = {"check_runs": [], "total_count": 0}
    legacy_body = {"state": "pending", "statuses": []}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[
            _resp(200, check_runs_body),
            _resp(200, legacy_body),
        ]
    )

    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        result = await get_ci_status(TOKEN, REPO, SHA)

    assert result == "unknown"


# ── required_contexts 필터링 ─────────────────────────────────────────────
# ── required_contexts filtering ──────────────────────────────────────────


async def test_get_ci_status_terminal_when_required_contexts_empty_set():
    """required_contexts=set() 이면 API 호출 없이 즉시 'failed' 반환.
    Returns 'failed' immediately (no API calls) when required_contexts is empty set.
    """
    mock_client = AsyncMock()
    mock_client.get = AsyncMock()

    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        result = await get_ci_status(TOKEN, REPO, SHA, required_contexts=set())

    assert result == "failed"
    # 빈 set은 필수 체크 없음 → API 호출 불필요 / No API call needed for empty required set.
    mock_client.get.assert_not_called()


async def test_get_ci_status_ignores_non_required_checks():
    """required_contexts에 없는 체크런은 무시 — 필수 체크만 통과이면 'passed'.
    Non-required checks are ignored; if required checks all pass → 'passed'.
    """
    check_runs_body = {
        "check_runs": [
            _check_run("required-ci", "completed", "success"),
            _check_run("optional-flaky", "completed", "failure"),  # 필수 아님 / not required
        ],
        "total_count": 2,
    }
    legacy_body = {"state": "success", "statuses": []}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[
            _resp(200, check_runs_body),
            _resp(200, legacy_body),
        ]
    )

    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        result = await get_ci_status(
            TOKEN, REPO, SHA, required_contexts={"required-ci"}
        )

    assert result == "passed"


# ── 페이지네이션 ──────────────────────────────────────────────────────────
# ── Pagination ────────────────────────────────────────────────────────────


async def test_get_ci_status_follows_link_header_next():
    """Link: rel="next" 헤더를 따라 2페이지 체크런을 수집.
    Follows Link rel="next" header to collect check-runs from page 2.
    """
    page1_body = {
        "check_runs": [_check_run("CI / lint", "completed", "success")],
        "total_count": 2,
    }
    page1_headers = {
        "Link": '<https://api.github.com/repos/owner/myrepo/commits/abc123def456/check-runs?page=2>; rel="next"'
    }
    page2_body = {
        "check_runs": [_check_run("CI / test", "completed", "success")],
        "total_count": 2,
    }
    legacy_body = {"state": "success", "statuses": []}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[
            _resp(200, page1_body, page1_headers),
            _resp(200, page2_body),            # 페이지 2 (next link 없음) / page 2 (no next link)
            _resp(200, legacy_body),            # 레거시 상태 / legacy status
        ]
    )

    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        result = await get_ci_status(TOKEN, REPO, SHA)

    assert result == "passed"
    # 체크런 2페이지 수집 후 filtered 결과 있어 레거시 API는 미호출 (총 2회)
    # 2 check-run pages collected; filtered non-empty so legacy API not called (2 calls total).
    assert mock_client.get.call_count == 2


async def test_get_ci_status_returns_unknown_beyond_5_pages():
    """5페이지 초과 시 'unknown' 반환 + WARNING 로그.
    Returns 'unknown' and logs WARNING when more than 5 pages of check-runs exist.
    """
    next_link_header = {
        "Link": '<https://api.github.com/repos/owner/myrepo/commits/abc123/check-runs?page=99>; rel="next"'
    }
    # 각 페이지마다 success 체크런 + next 링크 / Each page has a success run + next link.
    page_body = {
        "check_runs": [_check_run("CI / step", "completed", "success")],
        "total_count": 999,
    }

    mock_client = AsyncMock()
    # 5페이지 모두 next 링크 반환 / All 5 pages return a next link.
    mock_client.get = AsyncMock(
        return_value=_resp(200, page_body, next_link_header)
    )

    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        result = await get_ci_status(TOKEN, REPO, SHA)

    assert result == "unknown"
    # 체크런 5페이지만 요청 (레거시 미호출) / Only 5 check-run pages requested (no legacy call).
    assert mock_client.get.call_count == 5


# ── 레거시 상태 fallback ───────────────────────────────────────────────────
# ── Legacy status fallback ─────────────────────────────────────────────────


async def test_get_ci_status_uses_legacy_status_when_no_check_runs():
    """체크런 없고 레거시 상태 pending이면 'running' 반환.
    Returns 'running' from legacy status when check-runs list is empty.
    """
    check_runs_body = {"check_runs": [], "total_count": 0}
    legacy_body = {
        "state": "pending",
        "statuses": [{"state": "pending", "context": "ci/test"}],
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[
            _resp(200, check_runs_body),
            _resp(200, legacy_body),
        ]
    )

    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        result = await get_ci_status(TOKEN, REPO, SHA)

    assert result == "running"


# ── _parse_link_next ──────────────────────────────────────────────────────


def test_parse_link_next_extracts_url():
    """Link 헤더에서 rel="next" URL을 정확히 추출.
    Correctly extracts rel="next" URL from a Link header.
    """
    header = (
        '<https://api.github.com/repos/owner/repo/commits/sha/check-runs?page=2>; rel="next", '
        '<https://api.github.com/repos/owner/repo/commits/sha/check-runs?page=5>; rel="last"'
    )
    result = _parse_link_next(header)
    assert result == "https://api.github.com/repos/owner/repo/commits/sha/check-runs?page=2"


def test_parse_link_next_returns_none_when_no_next():
    """rel="next"가 없으면 None 반환.
    Returns None when rel="next" is absent from the Link header.
    """
    header = '<https://api.github.com/check-runs?page=1>; rel="first"'
    result = _parse_link_next(header)
    assert result is None


def test_parse_link_next_returns_none_for_none_input():
    """Link 헤더가 None이면 None 반환.
    Returns None when the Link header itself is None.
    """
    result = _parse_link_next(None)
    assert result is None


# ── get_required_check_contexts ───────────────────────────────────────────


async def test_get_required_check_contexts_returns_contexts():
    """브랜치 보호 필수 체크 컨텍스트 목록을 set으로 반환.
    Returns the branch protection required contexts as a set.
    """
    protection_body = {"contexts": ["CI / test", "CI / lint"]}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_resp(200, protection_body))

    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        result = await get_required_check_contexts(TOKEN, REPO, BRANCH)

    assert result == {"CI / test", "CI / lint"}


async def test_get_required_check_contexts_returns_empty_on_404():
    """브랜치 보호가 없으면(404) 빈 set 반환.
    Returns empty set when branch has no protection rules (404).
    """
    mock_resp = _resp(404, {"message": "Branch not protected"})
    mock_resp.raise_for_status.side_effect = Exception("404 Not Found")

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        result = await get_required_check_contexts(TOKEN, REPO, BRANCH)

    assert result == set()


async def test_get_required_check_contexts_caches_result():
    """동일 (repo, branch) 재호출 시 캐시된 결과 반환 (API 1회만 호출).
    Returns cached result on repeated calls for the same (repo, branch).
    """
    protection_body = {"contexts": ["CI / test"]}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_resp(200, protection_body))

    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        result1 = await get_required_check_contexts(TOKEN, REPO, BRANCH)
        result2 = await get_required_check_contexts(TOKEN, REPO, BRANCH)

    assert result1 == {"CI / test"}
    assert result2 == {"CI / test"}
    # 캐시 적중으로 API는 1회만 호출 / API called only once due to cache hit.
    assert mock_client.get.call_count == 1
