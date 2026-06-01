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
