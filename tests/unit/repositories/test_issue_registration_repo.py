# tests/unit/repositories/test_issue_registration_repo.py
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database import Base
from src.models.issue_registration import IssueRegistration
from src.repositories import issue_registration_repo


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _create(db, *, issue_key="key1", repo_id=1, analysis_id=1,
            issue_type="ai_suggestion", github_issue_number=42):
    return issue_registration_repo.create(
        db,
        analysis_id=analysis_id,
        repo_id=repo_id,
        issue_type=issue_type,
        issue_key=issue_key,
        github_issue_number=github_issue_number,
    )


def test_find_by_key_returns_none_when_missing(db):
    result = issue_registration_repo.find_by_key(db, repo_id=1, issue_key="missing")
    assert result is None


def test_create_and_find_by_key(db):
    _create(db, issue_key="abc123", repo_id=1, github_issue_number=42)
    found = issue_registration_repo.find_by_key(db, repo_id=1, issue_key="abc123")
    assert found is not None
    assert found.github_issue_number == 42
    assert found.github_issue_state == "open"


def test_create_sets_created_at(db):
    rec = _create(db)
    assert rec.created_at is not None


def test_list_by_analysis_empty(db):
    result = issue_registration_repo.list_by_analysis(db, analysis_id=99)
    assert result == []


def test_list_by_analysis_returns_records(db):
    _create(db, analysis_id=1, issue_key="k1")
    _create(db, analysis_id=1, issue_key="k2")
    _create(db, analysis_id=2, issue_key="k3")
    result = issue_registration_repo.list_by_analysis(db, analysis_id=1)
    assert len(result) == 2


def test_update_state_changes_state_and_synced_at(db):
    rec = _create(db)
    issue_registration_repo.update_state(db, record=rec, state="closed")
    assert rec.github_issue_state == "closed"
    assert rec.github_issue_synced_at is not None


def test_list_by_repo_returns_records(db):
    _create(db, repo_id=1, issue_key="r1")
    _create(db, repo_id=1, issue_key="r2")
    result = issue_registration_repo.list_by_repo(db, repo_id=1)
    assert len(result) == 2


def test_same_key_different_repo_allowed(db):
    _create(db, repo_id=1, issue_key="same")
    _create(db, repo_id=2, issue_key="same")
    assert issue_registration_repo.find_by_key(db, repo_id=1, issue_key="same") is not None
    assert issue_registration_repo.find_by_key(db, repo_id=2, issue_key="same") is not None
