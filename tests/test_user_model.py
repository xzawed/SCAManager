import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-cid")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-csecret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from src.database import Base
from src.models.user import User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def test_create_user(db):
    """User 생성 및 DB 저장."""
    user = User(google_id="g-123", email="test@example.com", display_name="Test User")
    db.add(user)
    db.commit()
    db.refresh(user)
    assert user.id is not None
    assert user.google_id == "g-123"
    assert user.email == "test@example.com"
    assert user.display_name == "Test User"
    assert user.created_at is not None


def test_google_id_unique_constraint(db):
    """google_id는 unique 제약이 있다."""
    db.add(User(google_id="same-id", email="a@b.com", display_name="User A"))
    db.commit()
    db.add(User(google_id="same-id", email="c@d.com", display_name="User B"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_email_unique_constraint(db):
    """email은 unique 제약이 있다."""
    db.add(User(google_id="id-1", email="same@example.com", display_name="User A"))
    db.commit()
    db.add(User(google_id="id-2", email="same@example.com", display_name="User B"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_user_query_by_google_id(db):
    """google_id로 User 조회."""
    db.add(User(google_id="g-456", email="foo@bar.com", display_name="Foo Bar"))
    db.commit()
    found = db.query(User).filter(User.google_id == "g-456").first()
    assert found is not None
    assert found.email == "foo@bar.com"


def test_repository_user_id_is_nullable(db):
    """기존 Repository는 user_id 없이 생성 가능하다 (하위 호환성)."""
    from src.models.repository import Repository
    repo = Repository(full_name="owner/orphan-repo")
    db.add(repo)
    db.commit()
    db.refresh(repo)
    assert repo.user_id is None


def test_repository_owner_relationship(db):
    """Repository.owner는 연결된 User를 반환한다."""
    from src.models.repository import Repository
    user = User(google_id="g-rel-1", email="rel@example.com", display_name="Rel User")
    db.add(user)
    db.flush()
    repo = Repository(full_name="owner/owned-repo", user_id=user.id)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    assert repo.user_id == user.id
    assert repo.owner.email == "rel@example.com"
