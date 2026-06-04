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
    _legacy_state_to_ci_status,
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


# ── WBS 감사 P2: URL path 인코딩 일관성 (repos.py _repo_path 패턴 정합) ──────────
# ── WBS audit P2: URL path encoding consistency (matches repos.py _repo_path) ──


async def test_get_ci_status_encodes_repo_and_sha_in_url():
    """repo_full_name/commit_sha 특수문자가 URL 인코딩됨 (슬래시 보존, path injection 방어).
    repo_full_name/commit_sha special chars are URL-encoded (slash preserved, path-injection defence).
    """
    body = {"check_runs": [_check_run("ci", "completed", "success")], "total_count": 1}
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_resp(200, body))

    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        await get_ci_status(TOKEN, "owner/re po", "ab cd")

    called_url = mock_client.get.call_args[0][0]
    assert "owner/re%20po" in called_url   # 슬래시 보존 + 공백 인코딩 / slash kept, space encoded
    assert "ab%20cd" in called_url
    assert "re po" not in called_url       # raw 미인코딩 문자열 미포함 / no raw unencoded value


async def test_get_required_check_contexts_encodes_branch_in_url():
    """branch 특수문자가 URL 인코딩되되 슬래시는 보존된다 (feature/x 정합).
    branch special chars are URL-encoded while slashes are preserved (feature/x semantics).
    """
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_resp(200, {"contexts": ["ci/build"]}))

    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        await get_required_check_contexts(TOKEN, "owner/myrepo", "feat/x y")

    called_url = mock_client.get.call_args[0][0]
    assert "branches/feat/x%20y/" in called_url   # 슬래시 보존 + 공백 인코딩 / slash kept, space encoded


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


async def test_get_ci_status_empty_set_falls_back_to_all_checks():
    """required_contexts=set() 이면 None 처럼 모든 체크를 고려해 평가한다.
    Empty required_contexts falls back to evaluating all checks (treated as None).

    BPR Required Status Checks 미설정 Repo 에서 빈 set 이 반환될 때,
    이전 동작은 즉시 'failed' 였으나 사용자 의도(CI 진행 상태로 판단) 와 어긋남.
    이제는 None 으로 fallback 하여 실제 체크 상태로 평가한다.
    Previous behavior returned 'failed' immediately for empty set, which mismatched
    user intent (PR with running CI shouldn't be marked failed). Now falls back
    to None and evaluates actual check state via API.
    """
    check_runs_body = {
        "check_runs": [_check_run("CI / test", "in_progress", None)],
        "total_count": 1,
    }
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[_resp(200, check_runs_body)])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        result = await get_ci_status(TOKEN, REPO, SHA, required_contexts=set())

    # 빈 set 이어도 API 호출 후 실제 상태로 판단 / Even with empty set, API is called.
    assert result == "running"
    mock_client.get.assert_called()


async def test_get_ci_status_empty_set_with_all_passed():
    """빈 set + 모든 체크 통과 → 'passed' 반환 (fallback 동작).
    Empty set + all checks success → 'passed' (fallback behavior verified).
    """
    check_runs_body = {
        "check_runs": [
            _check_run("SonarQube", "completed", "success"),
            _check_run("Codecov", "completed", "success"),
        ],
        "total_count": 2,
    }
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[_resp(200, check_runs_body)])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        result = await get_ci_status(TOKEN, REPO, SHA, required_contexts=set())

    assert result == "passed"


async def test_get_ci_status_empty_set_with_failed_check():
    """빈 set + 실제 체크 실패 → 'failed' 반환 (fallback 후에도 정확).
    Empty set + actually failed check → 'failed' (fallback still detects real failures).

    이 테스트는 결과 값(`failed`)뿐 아니라 fallback 경로를 실제로 거쳤는지
    (= API 가 호출되었는지) 도 함께 검증한다. 옛 동작은 API 호출 없이 즉시
    'failed' 를 반환했으므로 mock_client.get 이 호출되지 않았다.
    Asserts API was actually called (fallback path), not just the result value.
    Old behavior returned 'failed' without any API call — this distinguishes them.
    """
    check_runs_body = {
        "check_runs": [
            _check_run("SonarQube", "completed", "failure"),
        ],
        "total_count": 1,
    }
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[_resp(200, check_runs_body)])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        result = await get_ci_status(TOKEN, REPO, SHA, required_contexts=set())

    assert result == "failed"
    # fallback 경로 검증 — API 가 실제로 호출되어야 함 (옛 동작은 즉시 반환)
    # Verify fallback path — API must have been called (old behavior returned immediately).
    mock_client.get.assert_called()


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


async def test_get_required_check_contexts_returns_empty_on_404(caplog):
    """브랜치 보호가 없으면(404) 빈 set 반환 + debug 레벨 로그.
    Returns empty set + debug log when no branch protection (404).
    """
    import logging
    import httpx as _httpx

    mock_resp = _resp(404, {"message": "Branch not protected"})
    mock_resp.status_code = 404
    mock_resp.raise_for_status.side_effect = _httpx.HTTPStatusError(
        "404 Not Found", request=MagicMock(), response=mock_resp,
    )

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    # m1: 404 는 정상 — warning/error 레벨 로그가 없어야 함
    with patch("src.github_client.checks.get_http_client", return_value=mock_client), \
         caplog.at_level(logging.WARNING, logger="src.github_client.checks"):
        result = await get_required_check_contexts(TOKEN, REPO, BRANCH)

    assert result == set()
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


async def test_get_required_check_contexts_returns_empty_on_403_with_warning(caplog):
    """권한 부족(403) — 빈 set + warning 로그.
    Permission denied (403) — empty set + warning log.
    """
    import logging
    import httpx as _httpx

    mock_resp = _resp(403, {"message": "Resource not accessible by integration"})
    mock_resp.status_code = 403
    mock_resp.raise_for_status.side_effect = _httpx.HTTPStatusError(
        "403 Forbidden", request=MagicMock(), response=mock_resp,
    )

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("src.github_client.checks.get_http_client", return_value=mock_client), \
         caplog.at_level(logging.WARNING, logger="src.github_client.checks"):
        result = await get_required_check_contexts(TOKEN, REPO, "branch-403")

    assert result == set()
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("권한" in r.getMessage() or "unauthorized" in r.getMessage() for r in warnings)


async def test_get_required_check_contexts_returns_empty_on_429_with_warning(caplog):
    """rate limit(429) — 빈 set + warning 로그.
    Rate limit (429) — empty set + warning log.
    """
    import logging
    import httpx as _httpx

    mock_resp = _resp(429, {"message": "API rate limit exceeded"})
    mock_resp.status_code = 429
    mock_resp.raise_for_status.side_effect = _httpx.HTTPStatusError(
        "429 Too Many Requests", request=MagicMock(), response=mock_resp,
    )

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("src.github_client.checks.get_http_client", return_value=mock_client), \
         caplog.at_level(logging.WARNING, logger="src.github_client.checks"):
        result = await get_required_check_contexts(TOKEN, REPO, "branch-429")

    assert result == set()
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("rate limit" in r.getMessage().lower() for r in warnings)


async def test_get_required_check_contexts_returns_empty_on_network_error(caplog):
    """네트워크 오류(ConnectError 등) — 빈 set + warning 로그.
    Network error — empty set + warning log.
    """
    import logging
    import httpx as _httpx

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=_httpx.ConnectError("DNS failure"))

    with patch("src.github_client.checks.get_http_client", return_value=mock_client), \
         caplog.at_level(logging.WARNING, logger="src.github_client.checks"):
        result = await get_required_check_contexts(TOKEN, REPO, "branch-net")

    assert result == set()
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("네트워크" in r.getMessage() or "network" in r.getMessage() for r in warnings)


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


# ── 사이클 113 P0-B 회귀 가드 — 3상태 (waiting/pending/requested) ────────
# ── Cycle 113 P0-B regression guard — 3 new in-progress states ────────────


@pytest.mark.parametrize("status", ["waiting", "pending", "requested"])
async def test_get_ci_status_running_when_check_in_new_in_progress_states(status):
    """사이클 113 P0-B 회귀 가드 — waiting/pending/requested 는 running으로 분류.
    Cycle 113 P0-B regression guard — waiting/pending/requested must be classified as running.

    `_classify_check_runs()` 의 status in ("in_progress", "queued", "waiting", "pending", "requested")
    조건에서 사이클 113에 추가된 3상태를 검증한다.
    향후 리팩토링 시 이 3상태가 무음으로 제거되는 것을 방지한다.

    Validates the 3 states added in cycle 113 to the condition
    `status in ("in_progress", "queued", "waiting", "pending", "requested")`.
    Prevents silent removal of these 3 states during future refactoring.
    """
    # 대상 상태만 가진 체크런 1개로 세팅 / Single check run with the target status only.
    check_runs_body = {
        "check_runs": [_check_run("CI / build", status, None)],
        "total_count": 1,
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[
            _resp(200, check_runs_body),  # check-runs 1페이지 / check-runs page 1
        ]
    )

    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        result = await get_ci_status(TOKEN, REPO, SHA)

    # waiting/pending/requested 모두 "running" 으로 분류되어야 함
    # All of waiting/pending/requested must be classified as "running".
    assert result == "running", (
        f"status={status!r} must be classified as 'running' "
        f"(cycle 113 P0-B regression guard)"
    )
    # check-runs 1회만 호출 — 레거시 API 미호출 / Only check-runs called — no legacy API call.
    assert mock_client.get.call_count == 1


@pytest.mark.parametrize("status", ["waiting", "pending", "requested"])
async def test_get_ci_status_new_states_do_not_fall_through_to_failed(status):
    """사이클 113 P0-B 부정 케이스 — 3상태는 'failed'/'unknown'으로 빠지지 않는다.
    Cycle 113 P0-B negative guard — 3 states must NOT fall through to 'failed' or 'unknown'.

    `_classify_check_runs()` 에서 신규 3상태가 running 분기에 포함되지 않을 경우
    completed 가 아닌 체크런은 기본값(failed 또는 unknown)으로 떨어진다.
    이 테스트는 그 회귀를 명시적으로 차단한다.

    If the 3 new states were missing from the running branch, non-completed
    check runs would fall through to the default (failed or unknown).
    This test explicitly blocks that regression.
    """
    check_runs_body = {
        "check_runs": [_check_run("CI / deploy", status, None)],
        "total_count": 1,
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=[
            _resp(200, check_runs_body),
        ]
    )

    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        result = await get_ci_status(TOKEN, REPO, SHA)

    # "failed" 또는 "unknown" 으로 빠지지 않아야 함 / Must NOT be 'failed' or 'unknown'.
    assert result not in ("failed", "unknown"), (
        f"status={status!r} must not fall through to 'failed'/'unknown' "
        f"(cycle 113 P0-B regression guard)"
    )


# ── 레거시 commit status fallback 봉인 (Theme B S4) ─────────────────────────
# ── Legacy commit status fallback guard (auto-merge gate 정확성 경로) ────────


@pytest.mark.parametrize("state,expected", [
    ("pending", "running"),
    ("success", "passed"),
    ("failure", "failed"),
    ("error", "failed"),
    ("unexpected", "unknown"),
    ("", "unknown"),
])
def test_legacy_state_to_ci_status(state, expected):
    # 레거시 commit status state → CI 상태 매핑 (checks.py:173-183) 전 분기 봉인.
    # 기존 테스트는 check-runs 경로만 거쳐 이 매핑에 0회 도달 — auto-merge gate fallback 정확성 직결.
    assert _legacy_state_to_ci_status(state) == expected


async def test_get_ci_status_legacy_fallback_when_no_check_runs():
    # check-runs 비어 있으면 레거시 commit status fallback (checks.py:143-147) 경유.
    # filtered 가 비면 _classify_check_runs(L130) 미실행 → 레거시 API → _legacy_state_to_ci_status.
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[
        _resp(200, {"check_runs": [], "total_count": 0}),
        _resp(200, {"state": "success", "statuses": [{"state": "success", "context": "ci/legacy"}]}),
    ])
    with patch("src.github_client.checks.get_http_client", return_value=mock_client):
        result = await get_ci_status(TOKEN, REPO, SHA)
    assert result == "passed"
