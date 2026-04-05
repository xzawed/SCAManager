import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database import Base
from src.models.repository import Repository
from src.models.analysis import Analysis


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def test_create_repository(db_session):
    repo = Repository(full_name="owner/repo", telegram_chat_id="-100123")
    db_session.add(repo)
    db_session.commit()
    found = db_session.query(Repository).filter_by(full_name="owner/repo").first()
    assert found is not None
    assert found.telegram_chat_id == "-100123"


def test_create_analysis(db_session):
    repo = Repository(full_name="owner/repo")
    db_session.add(repo)
    db_session.flush()

    analysis = Analysis(
        repo_id=repo.id,
        commit_sha="abc123",
        pr_number=42,
        score=80,
        grade="B",
        result={"issues": []},
    )
    db_session.add(analysis)
    db_session.commit()

    found = db_session.query(Analysis).filter_by(commit_sha="abc123").first()
    assert found.score == 80
    assert found.grade == "B"
    assert found.pr_number == 42
