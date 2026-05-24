# tests/unit/models/test_issue_registration.py
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from src.database import Base
from src.models.issue_registration import IssueRegistration
import src.models.analysis  # noqa: F401
import src.models.repository  # noqa: F401


@pytest.fixture
def mem_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db, engine
    db.close()
    engine.dispose()


def test_issue_registration_table_created(mem_db):
    _, engine = mem_db
    inspector = inspect(engine)
    assert "issue_registrations" in inspector.get_table_names()


def test_issue_registration_columns(mem_db):
    _, engine = mem_db
    inspector = inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("issue_registrations")}
    assert cols >= {
        "id", "analysis_id", "repo_id", "issue_type", "issue_key",
        "github_issue_number", "github_issue_state", "github_issue_synced_at",
        "created_at",
    }


def test_unique_constraint_exists(mem_db):
    _, engine = mem_db
    inspector = inspect(engine)
    uqs = inspector.get_unique_constraints("issue_registrations")
    uq_cols = [frozenset(u["column_names"]) for u in uqs]
    assert frozenset({"repo_id", "issue_key"}) in uq_cols


def test_default_state_is_open(mem_db):
    db, _ = mem_db
    rec = IssueRegistration(
        analysis_id=1, repo_id=1, issue_type="ai_suggestion",
        issue_key="abc", github_issue_number=42,
        created_at=datetime.now(timezone.utc),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    assert rec.github_issue_state == "open"
