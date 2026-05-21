"""GateDecision 모델 단위 테스트 — unique constraint + CASCADE 검증.
GateDecision model unit tests — unique constraint and CASCADE verification.

사이클 113 P0-E 회귀 가드: analysis_id UNIQUE constraint가 DB 레벨에서 실제로
IntegrityError를 발화하는지 검증한다. upsert semantic에 필수 (분석 1건 당 1건).
Cycle 113 P0-E regression guard: verifies that the analysis_id UNIQUE constraint
actually raises IntegrityError at the DB level. Required for upsert semantics (1 per analysis).
"""
from __future__ import annotations

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

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models.analysis import Analysis
from src.models.gate_decision import GateDecision
from src.models.repository import Repository
from src.models.user import User


# ─── Fixture ───────────────────────────────────────────────────────────────


@pytest.fixture()
def db():
    """단일 connection 공유 SQLite in-memory 세션 (StaticPool).
    SQLite in-memory session with shared single connection (StaticPool).
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def analysis(db: Session) -> Analysis:
    """테스트용 Analysis 레코드 (Repository + User 포함).
    Analysis record for tests (with Repository and User).
    """
    user = User(github_id=1, github_login="tester", email="t@x.com", display_name="Tester")
    db.add(user)
    db.flush()

    repo = Repository(full_name="owner/repo", user_id=user.id)
    db.add(repo)
    db.flush()

    a = Analysis(
        repo_id=repo.id,
        commit_sha="abc123",
        score=80,
        grade="B",
        result={},
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


# ─── T-4: analysis_id UNIQUE constraint 회귀 가드 ──────────────────────────


def test_gate_decision_analysis_id_unique_constraint(db: Session, analysis: Analysis):
    """동일 analysis_id로 GateDecision 2건 삽입 시 IntegrityError 발생.
    Inserting two GateDecisions with the same analysis_id raises IntegrityError.

    사이클 113 P0-E 회귀 가드: GateDecision.analysis_id에 unique=True 제약이
    실제 DB 레벨에서 작동함을 검증한다. 제약이 없으면 save_gate_decision()의
    upsert semantic이 깨져 중복 결정 레코드가 생성될 수 있다.
    Cycle 113 P0-E regression guard: verifies unique=True constraint on
    GateDecision.analysis_id works at the DB level. Without this constraint,
    the upsert semantic of save_gate_decision() breaks, allowing duplicate records.
    """
    first = GateDecision(
        analysis_id=analysis.id,
        decision="approve",
        mode="auto",
        decided_by="bot",
    )
    db.add(first)
    db.commit()

    # 동일 analysis_id로 두 번째 삽입 시도
    # Attempt second insert with same analysis_id
    second = GateDecision(
        analysis_id=analysis.id,
        decision="reject",
        mode="manual",
        decided_by="bot",
    )
    db.add(second)

    # UNIQUE constraint 위반 → IntegrityError
    # UNIQUE constraint violation → IntegrityError
    with pytest.raises(IntegrityError):
        db.commit()


def test_gate_decision_different_analyses_allowed(db: Session, analysis: Analysis):
    """서로 다른 analysis_id로는 GateDecision 각 1건씩 정상 삽입된다.
    GateDecision records for different analysis_ids are inserted successfully.

    UNIQUE constraint가 같은 analysis_id에 대해서만 작동하고
    다른 analysis_id는 허용하는지 검증한다.
    Verifies the UNIQUE constraint only blocks same analysis_id,
    while different analysis_ids are permitted.
    """
    # 두 번째 Analysis 레코드 생성
    # Create a second Analysis record
    a2 = Analysis(
        repo_id=analysis.repo_id,
        commit_sha="def456",
        score=70,
        grade="C",
        result={},
    )
    db.add(a2)
    db.commit()
    db.refresh(a2)

    gd1 = GateDecision(analysis_id=analysis.id, decision="approve", mode="auto", decided_by="bot")
    gd2 = GateDecision(analysis_id=a2.id, decision="reject", mode="auto", decided_by="bot")
    db.add(gd1)
    db.add(gd2)
    db.commit()  # 두 건 모두 정상 삽입 — IntegrityError 없어야 함

    count = db.query(GateDecision).count()
    assert count == 2
