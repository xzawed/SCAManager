"""railway_issue.py i18n 키 + body/title 언어 적용 — 사이클 153 Sprint 1."""
from __future__ import annotations

import json
import pathlib

import pytest

_TRANS_DIR = pathlib.Path("src/i18n/translations")
_LOCALES = ["ko", "en", "ja"]
_KEYS = ["build_failed", "log_fetch_failed", "dashboard_link"]


def _load(locale: str) -> dict:
    return json.loads((_TRANS_DIR / f"{locale}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _KEYS)
def test_railway_key_exists(locale: str, key: str):
    """notifier.railway.<key>가 모든 locale에 존재해야 한다."""
    assert "railway" in _load(locale)["notifier"], f"[{locale}] notifier.railway 없음"
    assert key in _load(locale)["notifier"]["railway"], f"[{locale}] {key} 없음"


def test_railway_body_english_no_korean():
    """en 언어로 빌드한 Railway Issue body에 '대시보드'/'못했' 한국어 누출 없어야 한다.
    Railway Issue body built with en must not leak Korean.
    """
    from src.notifier.railway_issue import _build_issue_body
    from src.railway_client.models import (
        RailwayCommitInfo,
        RailwayDeployEvent,
        RailwayProjectInfo,
    )
    event = RailwayDeployEvent(
        project=RailwayProjectInfo(
            project_id="p1", project_name="proj", environment_name="prod",
        ),
        commit=RailwayCommitInfo(
            commit_sha="abc1234def", repo_full_name="o/r", commit_message="msg",
        ),
        status="FAILED",
        deployment_id="d1",
        timestamp="2026-06-01",
    )
    out = _build_issue_body(event=event, logs_tail=None, language="en")
    assert "대시보드" not in out and "못했" not in out, f"영어 body에 한국어 누출: {out!r}"
    assert "Open Railway Dashboard" in out
    assert "Failed to fetch logs" in out


def test_railway_body_korean_default():
    """language 미전달 시 ko default (하위 호환)."""
    from src.notifier.railway_issue import _build_issue_body
    from src.railway_client.models import (
        RailwayCommitInfo,
        RailwayDeployEvent,
        RailwayProjectInfo,
    )
    event = RailwayDeployEvent(
        project=RailwayProjectInfo(
            project_id="p1", project_name="proj", environment_name="prod",
        ),
        commit=RailwayCommitInfo(
            commit_sha="abc1234def", repo_full_name="o/r", commit_message="msg",
        ),
        status="FAILED",
        deployment_id="d1",
        timestamp="2026-06-01",
    )
    out = _build_issue_body(event=event, logs_tail=None)
    assert "대시보드" in out


def _railway_event():
    from src.railway_client.models import (
        RailwayCommitInfo,
        RailwayDeployEvent,
        RailwayProjectInfo,
    )
    return RailwayDeployEvent(
        project=RailwayProjectInfo(
            project_id="p1", project_name="proj", environment_name="prod",
        ),
        commit=RailwayCommitInfo(
            commit_sha="abc1234def", repo_full_name="o/r", commit_message="msg",
        ),
        status="FAILED",
        deployment_id="d1",
        timestamp="2026-06-01",
    )


@pytest.mark.asyncio
async def test_handler_threads_language_to_create_issue():
    """_handle_railway_deploy_failure 가 language 를 create_deploy_failure_issue 로 배선 (사이클 154 seam).

    핸들러→발신 함수 language 배선 회귀 가드 (152 seam 패턴을 railway 에 적용).
    """
    from unittest.mock import AsyncMock, patch
    from src.webhook.providers import railway  # pylint: disable=import-outside-toplevel

    with patch(
        "src.webhook.providers.railway.create_deploy_failure_issue", new_callable=AsyncMock
    ) as mock_create:
        await railway._handle_railway_deploy_failure(  # pylint: disable=protected-access
            repo_full_name="o/r",
            event=_railway_event(),
            decrypted_api_token=None,  # 로그 조회 skip → logs_tail=None
            github_token="ghp_x",
            language="ja",
        )

    assert mock_create.await_count == 1
    assert mock_create.await_args.kwargs["language"] == "ja"
    assert mock_create.await_args.kwargs["logs_tail"] is None


@pytest.mark.asyncio
async def test_handler_log_fetch_failure_keeps_logs_tail_none():
    """로그 조회 실패 시 logs_tail 이 None 유지 → i18n 키 대체 (하드코딩 한국어 차단, 사이클 154 P2)."""
    from unittest.mock import AsyncMock, patch
    from src.railway_client.logs import RailwayLogFetchError
    from src.webhook.providers import railway  # pylint: disable=import-outside-toplevel

    with patch(
        "src.webhook.providers.railway.fetch_deployment_logs",
        new_callable=AsyncMock, side_effect=RailwayLogFetchError("boom"),
    ), patch(
        "src.webhook.providers.railway.create_deploy_failure_issue", new_callable=AsyncMock
    ) as mock_create:
        await railway._handle_railway_deploy_failure(  # pylint: disable=protected-access
            repo_full_name="o/r",
            event=_railway_event(),
            decrypted_api_token="token",  # 조회 시도 → 예외 → None 유지
            github_token="ghp_x",
            language="en",
        )

    assert mock_create.await_count == 1
    # 한국어 "로그 조회 실패" 가 Issue body 로 새지 않고 None 유지 (railway_issue 가 i18n 키로 대체)
    assert mock_create.await_args.kwargs["logs_tail"] is None
