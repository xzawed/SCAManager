"""이슈 집계 상한 — 한 곳(`src/constants.py`)을 바꾸면 세 곳이 따라온다 (회고 원장 L17 P2-8 · P2-36).

Issue-aggregate cap: change the one constant and all three consumers follow (retro ledger L17 P2-8 · P2-36).

인사이트 서비스 · 대시보드 카드 · MCP 도구 설명이 같은 상한(30)을 따로 적어 두면, 상수를 바꿔도 나머지는 옛 값으로 남고
어떤 시험도 red 가 나지 않았다. 여기서는 상수 하나만 **30 과 다른 값**으로 바꾸고 세 곳이 모두 그 값을 쓰는지 본다 —
사본이 남으면 그 사본이 30 을 내 드러난다.
Each consumer once carried its own 30; here only the constant changes, to a value other than 30, so a leftover copy shows.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import importlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src import constants
from src.database import Base
from src.mcp import repo_report_tools
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User
from src.scorer.reliability import score_is_unreliable

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
_NOW_NAIVE = NOW.replace(tzinfo=None)
_SMALL = 2  # 30 과 다른 상한 — 30 을 따로 적은 사본이 남으면 그 사본만 30 을 낸다 / differs from 30 on purpose


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def repo(db):
    user = User(github_id=91, github_login="capper", email="c@x.com", display_name="C")
    db.add(user)
    db.commit()
    r = Repository(full_name="capper/issues", user_id=user.id)
    db.add(r)
    db.commit()
    return r


def _seed_issue_only_beyond_the_newest_two(db, repo_id: int) -> None:
    """최신 2건엔 이슈가 없고, 그 뒤 2건에만 같은 이슈 — 상한 2 면 반복 이슈 0, 상한 30 이면 1.
    The newest two rows have no issues and the next two share one: 0 recurring under a cap of 2, 1 under 30.
    """
    issue = {"message": "beyond the cap", "category": "code_quality"}
    for i in range(4):
        result = {"issues": [issue]} if i >= 2 else {}
        db.add(Analysis(
            repo_id=repo_id, commit_sha=f"sha-{uuid.uuid4().hex}", score=80, grade="B", result=result,
            score_unreliable=score_is_unreliable(result), created_at=_NOW_NAIVE - timedelta(hours=i + 1),
        ))
    db.commit()


def _recurring_on_the_card(db, repo) -> int:
    from src.services.dashboard_service import repo_insight_cards  # noqa: PLC0415

    cards = {c["repo_id"]: c for c in repo_insight_cards(db, days=30, user_id=repo.user_id, now=NOW)}
    return cards[repo.id]["recurring_issue_count"]


def test_the_seed_counts_one_recurring_issue_under_the_real_cap(db, repo):
    """양성 대조 — 같은 씨앗은 실제 상한(30)에서 반복 이슈 1 이다. 아래 0 이 «씨앗이 약해서» 가 아님을 보인다.
    Positive control: under the real cap the same seed yields one recurring issue.
    """
    _seed_issue_only_beyond_the_newest_two(db, repo.id)
    assert constants.ISSUE_AGGREGATE_MAX_ANALYSES > 4
    assert _recurring_on_the_card(db, repo) == 1


def test_the_dashboard_card_reads_the_constant(db, repo, monkeypatch):
    """카드의 리포당 행 수가 상수를 따른다 — 상한 2 면 최신 2건(이슈 없음)만 읽어 반복 이슈 0."""
    _seed_issue_only_beyond_the_newest_two(db, repo.id)
    monkeypatch.setattr(constants, "ISSUE_AGGREGATE_MAX_ANALYSES", _SMALL)
    assert _recurring_on_the_card(db, repo) == 0


def test_the_insights_page_reads_the_constant(db, repo, monkeypatch):
    """인사이트 페이지의 이슈 집계가 읽는 행 수 · «최근 N건 기준» 의 N 이 상수를 따른다."""
    from src.services import repo_insight_service  # noqa: PLC0415

    _seed_issue_only_beyond_the_newest_two(db, repo.id)
    monkeypatch.setattr(constants, "ISSUE_AGGREGATE_MAX_ANALYSES", _SMALL)
    fetched = repo_insight_service._fetch_analyses(db, repo.id, 30, _NOW_NAIVE)  # pylint: disable=protected-access
    assert len(fetched) == _SMALL
    assert repo_insight_service.issue_basis(10) == _SMALL


def test_the_mcp_tool_descriptions_read_the_constant(monkeypatch):
    """MCP 도구 설명의 «최근 분석 N건» 이 상수에서 만들어진다 — 설명은 모듈을 읽을 때 만들어지므로 다시 읽어 본다.
    The MCP descriptions are built from the constant at import time, so the module is reloaded under the patch.
    """
    monkeypatch.setattr(constants, "ISSUE_AGGREGATE_MAX_ANALYSES", 7)
    try:
        reloaded = importlib.reload(repo_report_tools)
        descriptions = [tool["description"] for tool in reloaded.tools]
        assert len(descriptions) == 2, descriptions
        for text in descriptions:
            assert "최근 분석 7건" in text and "latest 7 analyses" in text, text
            assert "30" not in text, f"설명에 상한 사본 30 이 남았다: {text}"
    finally:
        monkeypatch.undo()
        importlib.reload(repo_report_tools)
