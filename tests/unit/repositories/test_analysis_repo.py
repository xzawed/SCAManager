"""analysis_repo 단위 테스트."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.repositories import analysis_repo


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_cls = sessionmaker(bind=engine)
    session = session_cls()
    try:
        yield session
    finally:
        session.close()


def _seed_repo(db_session) -> Repository:
    repo = Repository(full_name="owner/repo")
    db_session.add(repo)
    db_session.commit()
    return repo


def test_find_by_sha_returns_none_when_missing(db_session):
    repo = _seed_repo(db_session)
    result = analysis_repo.find_by_sha(db_session, "deadbeef", repo.id)
    assert result is None


def test_save_new_persists_and_returns_analysis(db_session):
    repo = _seed_repo(db_session)
    a = Analysis(repo_id=repo.id, commit_sha="abc123", score=80, grade="B")
    saved = analysis_repo.save_new(db_session, a)
    assert saved.id is not None
    assert saved.commit_sha == "abc123"
    assert db_session.query(Analysis).count() == 1


def test_find_by_sha_returns_existing(db_session):
    repo = _seed_repo(db_session)
    a = Analysis(repo_id=repo.id, commit_sha="abc123", score=80, grade="B")
    analysis_repo.save_new(db_session, a)
    found = analysis_repo.find_by_sha(db_session, "abc123", repo.id)
    assert found is not None
    assert found.score == 80


def test_save_new_returns_existing_on_duplicate_sha(db_session):
    """DB unique constraint 위반 시 기존 레코드를 반환 — race condition 안전망."""
    repo = _seed_repo(db_session)
    first = Analysis(repo_id=repo.id, commit_sha="dup123", score=75, grade="B")
    saved_first = analysis_repo.save_new(db_session, first)

    second = Analysis(repo_id=repo.id, commit_sha="dup123", score=90, grade="A")
    result = analysis_repo.save_new(db_session, second)

    assert result.id == saved_first.id
    assert result.score == 75  # 첫 번째 레코드 그대로
    assert db_session.query(Analysis).count() == 1
