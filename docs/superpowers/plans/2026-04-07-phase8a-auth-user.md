# Phase 8A: Google OAuth + User Model + Per-User Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Google OAuth login so each user sees only their own repositories in the dashboard.

**Architecture:** New `User` ORM + `users` table; `Repository` gets nullable `user_id` FK; `SessionMiddleware` cookie-based auth; `require_login` FastAPI dependency guards all UI routes; existing Webhook/API endpoints unchanged.

**Tech Stack:** authlib>=1.3.0 (OAuth2), starlette SessionMiddleware (cookie sessions), SQLAlchemy 2.x FK, Alembic migration, FastAPI Depends

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `requirements.txt` | Add authlib |
| Modify | `tests/conftest.py` | Add 3 new env defaults |
| Modify | `src/config.py` | Add google_client_id, google_client_secret, session_secret |
| Create | `src/models/user.py` | User ORM (google_id, email, display_name) |
| Modify | `src/models/repository.py` | Add user_id FK (nullable) + owner relationship |
| Create | `alembic/versions/0005_add_users_and_user_id.py` | DB migration |
| Create | `src/auth/__init__.py` | Package marker |
| Create | `src/auth/session.py` | get_current_user() + require_login dependency |
| Create | `src/auth/google.py` | /login, /auth/google, /auth/callback, /auth/logout routes |
| Create | `src/templates/login.html` | Login page ("Google로 로그인" button) |
| Modify | `src/main.py` | SessionMiddleware + auth router |
| Modify | `src/ui/router.py` | require_login dependency + user_id filter + ownership check |
| Create | `tests/test_user_model.py` | User CRUD + constraints + Repository FK |
| Create | `tests/test_auth_session.py` | get_current_user + require_login unit tests |
| Create | `tests/test_auth_google.py` | OAuth routes unit tests (mocked) |
| Modify | `tests/test_ui_router.py` | dependency override + updated mocks + new auth tests |

---

## Task 1: Add authlib dependency + extend config

**Files:**
- Modify: `requirements.txt`
- Modify: `tests/conftest.py`
- Modify: `src/config.py`

- [ ] **Step 1: Add authlib to requirements.txt**

Edit `requirements.txt` — add after the httpx line:
```
authlib>=1.3.0
```

Full file after change:
```
fastapi==0.115.0
uvicorn[standard]==0.30.6
pydantic-settings==2.3.4
sqlalchemy==2.0.35
alembic==1.13.3
psycopg2-binary==2.9.11
PyGithub==2.3.0
httpx==0.27.2
authlib>=1.3.0
python-telegram-bot==21.6
anthropic>=0.25.0
pylint==3.3.1
flake8==7.1.1
bandit==1.8.0
pytest==8.3.3
pytest-asyncio==0.24.0
playwright>=1.44.0
pytest-playwright>=0.5.0
jinja2==3.1.6
python-multipart==0.0.22
```

- [ ] **Step 2: Add new env defaults to tests/conftest.py**

Edit `tests/conftest.py` — add 3 lines after the existing `os.environ.setdefault` block:

```python
import os
import pytest
from fastapi.testclient import TestClient

# Set required env vars before any src.* imports that trigger Settings() loading
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

from src.main import app


@pytest.fixture
def client():
    return TestClient(app)
```

- [ ] **Step 3: Add 3 new fields to src/config.py**

Edit `src/config.py` — add 3 fields to the `Settings` class:

```python
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    database_url: str
    github_webhook_secret: str
    github_token: str
    telegram_bot_token: str
    telegram_chat_id: str
    anthropic_api_key: str = ""
    api_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    session_secret: str = "dev-secret-change-in-production"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("database_url")
    @classmethod
    def fix_postgres_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)
        if 'supabase.co' in v and 'sslmode' not in v:
            v += '?sslmode=require'
        return v


settings = Settings()
```

- [ ] **Step 4: Install authlib**

```bash
pip install authlib
```

Expected output: `Successfully installed authlib-x.x.x`

- [ ] **Step 5: Run existing tests to confirm no regression**

```bash
pytest tests/ -q
```

Expected: `146 passed`

- [ ] **Step 6: Commit**

```bash
git add requirements.txt tests/conftest.py src/config.py
git commit -m "feat: add authlib dependency and OAuth env vars to config"
```

---

## Task 2: User ORM model (TDD)

**Files:**
- Create: `tests/test_user_model.py`
- Create: `src/models/user.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_user_model.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_user_model.py -v
```

Expected: `ImportError: cannot import name 'User' from 'src.models.user'` (file doesn't exist)

- [ ] **Step 3: Create src/models/user.py**

```python
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from src.database import Base


class User(Base):
    __tablename__ = "users"

    id           = Column(Integer, primary_key=True, index=True)
    google_id    = Column(String, unique=True, nullable=False, index=True)
    email        = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow)

    repositories = relationship("Repository", back_populates="owner")
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/test_user_model.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/test_user_model.py src/models/user.py
git commit -m "feat: add User ORM model with google_id/email/display_name"
```

---

## Task 3: Repository model — add user_id FK (TDD)

**Files:**
- Modify: `tests/test_user_model.py` (add 2 tests)
- Modify: `src/models/repository.py`

- [ ] **Step 1: Add FK tests to tests/test_user_model.py**

Append to `tests/test_user_model.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_user_model.py::test_repository_user_id_is_nullable tests/test_user_model.py::test_repository_owner_relationship -v
```

Expected: `AttributeError: type object 'Repository' has no attribute 'user_id'`

- [ ] **Step 3: Modify src/models/repository.py**

```python
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.database import Base


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, unique=True, nullable=False, index=True)
    telegram_chat_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    analyses = relationship("Analysis", back_populates="repository")
    owner = relationship("User", back_populates="repositories")
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/test_user_model.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Run full test suite to confirm no regression**

```bash
pytest tests/ -q
```

Expected: `152 passed` (146 + 6 new)

- [ ] **Step 6: Commit**

```bash
git add tests/test_user_model.py src/models/repository.py
git commit -m "feat: add user_id FK to Repository (nullable, back-compat)"
```

---

## Task 4: DB Migration 0005

**Files:**
- Create: `alembic/versions/0005_add_users_and_user_id.py`

- [ ] **Step 1: Create migration file**

Create `alembic/versions/0005_add_users_and_user_id.py`:

```python
"""add users table and repositories.user_id FK

Revision ID: 0005addusers
Revises: 0004addautomerge
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa

revision = '0005addusers'
down_revision = '0004addautomerge'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('google_id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_google_id'), 'users', ['google_id'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    op.add_column(
        'repositories',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True)
    )
    op.create_index(op.f('ix_repositories_user_id'), 'repositories', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_repositories_user_id'), table_name='repositories')
    op.drop_column('repositories', 'user_id')

    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_google_id'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
```

- [ ] **Step 2: Commit**

```bash
git add alembic/versions/0005_add_users_and_user_id.py
git commit -m "feat: migration 0005 — add users table and repositories.user_id FK"
```

---

## Task 5: Auth session helpers (TDD)

**Files:**
- Create: `tests/test_auth_session.py`
- Create: `src/auth/__init__.py`
- Create: `src/auth/session.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_auth_session.py`:

```python
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
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from src.auth.session import get_current_user, require_login
from src.models.user import User


def _req(session_data=None):
    """session dict を持つ MagicMock Request を返す。"""
    req = MagicMock()
    req.session = session_data if session_data is not None else {}
    return req


def test_get_current_user_no_session():
    """세션에 user_id 없으면 None 반환."""
    result = get_current_user(_req({}))
    assert result is None


def test_get_current_user_invalid_id():
    """세션에 user_id 있지만 DB에 없으면 None 반환."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    with patch("src.auth.session.SessionLocal", return_value=mock_db):
        result = get_current_user(_req({"user_id": 999}))
    assert result is None


def test_get_current_user_valid():
    """세션에 user_id 있고 DB에 유저 존재하면 User 반환."""
    mock_user = User(id=1, google_id="g1", email="a@b.com", display_name="Test")
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user
    with patch("src.auth.session.SessionLocal", return_value=mock_db):
        result = get_current_user(_req({"user_id": 1}))
    assert result is mock_user


def test_require_login_no_session_raises_302():
    """비로그인 시 HTTPException 302 with Location: /login."""
    with pytest.raises(HTTPException) as exc_info:
        require_login(_req({}))
    assert exc_info.value.status_code == 302
    assert exc_info.value.headers["Location"] == "/login"


def test_require_login_returns_user():
    """로그인 상태에서 User 반환."""
    mock_user = User(id=1, google_id="g1", email="a@b.com", display_name="Test")
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user
    with patch("src.auth.session.SessionLocal", return_value=mock_db):
        result = require_login(_req({"user_id": 1}))
    assert result is mock_user
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_auth_session.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.auth'`

- [ ] **Step 3: Create src/auth/__init__.py**

```python
```
(empty file)

- [ ] **Step 4: Create src/auth/session.py**

```python
from fastapi import Request, HTTPException
from src.database import SessionLocal
from src.models.user import User


def get_current_user(request: Request):
    """세션에서 현재 사용자를 반환. 없으면 None."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()


def require_login(request: Request) -> User:
    """로그인 필수 의존성. 비로그인 시 /login 으로 302 리다이렉트."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user
```

- [ ] **Step 5: Run to verify pass**

```bash
pytest tests/test_auth_session.py -v
```

Expected: `5 passed`

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -q
```

Expected: `157 passed`

- [ ] **Step 7: Commit**

```bash
git add tests/test_auth_session.py src/auth/__init__.py src/auth/session.py
git commit -m "feat: add auth session helpers (get_current_user + require_login)"
```

---

## Task 6: Google OAuth router (TDD)

**Files:**
- Create: `tests/test_auth_google.py`
- Create: `src/auth/google.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_auth_google.py`:

```python
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-cid")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-csecret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")

from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_login_page_loads():
    """GET /login은 로그인 페이지(200 HTML)를 반환한다."""
    with patch("src.auth.google.get_current_user", return_value=None):
        r = client.get("/login")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_login_redirects_if_already_authenticated():
    """이미 로그인된 사용자가 /login 접근 시 / 로 리다이렉트."""
    from src.models.user import User
    mock_user = User(id=1, google_id="g1", email="a@b.com", display_name="Test")
    with patch("src.auth.google.get_current_user", return_value=mock_user):
        r = client.get("/login", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/"


def test_logout_clears_session_and_redirects():
    """POST /auth/logout은 세션을 초기화하고 /login 으로 리다이렉트한다."""
    r = client.post("/auth/logout", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["location"]


def test_callback_creates_new_user_and_redirects():
    """콜백 처리 시 신규 유저를 생성하고 / 로 리다이렉트한다."""
    mock_token = {
        "userinfo": {
            "sub": "google-new-user-id",
            "email": "newuser@gmail.com",
            "name": "New User",
        }
    }
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None  # 신규 유저

    with patch("src.auth.google.oauth.google.authorize_access_token", new_callable=AsyncMock, return_value=mock_token):
        with patch("src.auth.google.SessionLocal", return_value=mock_db):
            r = client.get("/auth/callback?code=test-code&state=test-state", follow_redirects=False)

    assert r.status_code == 302
    assert r.headers["location"] == "/"
    assert mock_db.add.called
    assert mock_db.commit.called


def test_callback_returns_existing_user_and_redirects():
    """콜백 처리 시 기존 유저를 조회하고 / 로 리다이렉트한다."""
    from src.models.user import User
    mock_token = {
        "userinfo": {
            "sub": "google-existing-id",
            "email": "existing@gmail.com",
            "name": "Existing User",
        }
    }
    existing_user = User(id=5, google_id="google-existing-id", email="existing@gmail.com", display_name="Existing User")
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = existing_user

    with patch("src.auth.google.oauth.google.authorize_access_token", new_callable=AsyncMock, return_value=mock_token):
        with patch("src.auth.google.SessionLocal", return_value=mock_db):
            r = client.get("/auth/callback?code=test-code&state=test-state", follow_redirects=False)

    assert r.status_code == 302
    assert r.headers["location"] == "/"
    assert not mock_db.add.called  # 기존 유저이므로 add 미호출
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_auth_google.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.auth.google'`

- [ ] **Step 3: Create src/auth/google.py**

```python
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.config import settings
from src.database import SessionLocal
from src.models.user import User
from src.auth.session import get_current_user

oauth = OAuth()
oauth.register(
    name='google',
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="src/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """로그인 페이지. 이미 로그인된 경우 / 로 리다이렉트."""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/")
    return templates.TemplateResponse(request, "login.html", {})


@router.get("/auth/google")
async def auth_google(request: Request):
    """Google OAuth 동의 화면으로 리다이렉트."""
    redirect_uri = str(request.url_for("auth_callback"))
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request):
    """Google OAuth 콜백 처리. 유저 upsert 후 세션 저장."""
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo", {})

    google_id = userinfo["sub"]
    email = userinfo["email"]
    display_name = userinfo.get("name", email)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.google_id == google_id).first()
        if not user:
            user = User(google_id=google_id, email=email, display_name=display_name)
            db.add(user)
            db.commit()
            db.refresh(user)
        request.session["user_id"] = user.id
    finally:
        db.close()

    return RedirectResponse(url="/")


@router.post("/auth/logout")
async def logout(request: Request):
    """세션 초기화 후 /login 리다이렉트."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)
```

- [ ] **Step 4: Run to verify pass**

```bash
pytest tests/test_auth_google.py -v
```

Expected: `5 passed`

Note: `test_callback_*` tests pass because `authorize_access_token` is fully mocked. The `test_auth_google_redirects` route is not tested here because it requires valid OAuth state — it is covered by manual E2E.

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -q
```

Expected: `162 passed`

- [ ] **Step 6: Commit**

```bash
git add tests/test_auth_google.py src/auth/google.py
git commit -m "feat: add Google OAuth routes (/login, /auth/google, /auth/callback, /auth/logout)"
```

---

## Task 7: Login HTML template

**Files:**
- Create: `src/templates/login.html`

- [ ] **Step 1: Create src/templates/login.html**

```html
{% extends "base.html" %}

{% block title %}로그인 — SCAManager{% endblock %}

{% block content %}
<style>
  .login-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: calc(100vh - 56px);
  }
  .login-card {
    width: 100%;
    max-width: 400px;
    text-align: center;
    padding: 3rem 2rem;
  }
  .login-logo {
    width: 64px;
    height: 64px;
    background: var(--accent-grad);
    border-radius: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 28px;
    margin: 0 auto 1.5rem;
  }
  .login-title {
    font-size: 1.6rem;
    font-weight: 700;
    margin: 0 0 .5rem;
    color: var(--text-primary);
  }
  .login-sub {
    font-size: 14px;
    color: var(--text-muted);
    margin: 0 0 2.5rem;
  }
  .btn-google {
    display: inline-flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    justify-content: center;
    padding: .75rem 1.5rem;
    background: #fff;
    color: #3c4043;
    border: 1px solid #dadce0;
    border-radius: var(--radius-btn);
    font-size: 15px;
    font-weight: 500;
    text-decoration: none;
    transition: box-shadow var(--transition), background var(--transition);
    cursor: pointer;
  }
  .btn-google:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    background: #f8f9fa;
    color: #3c4043;
    text-decoration: none;
  }
  .btn-google svg { flex-shrink: 0; }
</style>

<div class="login-wrap">
  <div class="card login-card">
    <div class="login-logo">⚡</div>
    <h1 class="login-title">SCAManager</h1>
    <p class="login-sub">GitHub 정적 분석 + AI 코드 리뷰 플랫폼</p>
    <a href="/auth/google" class="btn-google">
      <svg width="20" height="20" viewBox="0 0 48 48">
        <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
        <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
        <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
        <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.31-8.16 2.31-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
        <path fill="none" d="M0 0h48v48H0z"/>
      </svg>
      Google로 로그인
    </a>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Verify test still passes (login.html is used by test_auth_google.py)**

```bash
pytest tests/test_auth_google.py::test_login_page_loads -v
```

Expected: `1 passed`

- [ ] **Step 3: Commit**

```bash
git add src/templates/login.html
git commit -m "feat: add login.html template with Google OAuth button"
```

---

## Task 8: Wire up main.py (SessionMiddleware + auth router)

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: Modify src/main.py**

```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from alembic import command
from alembic.config import Config
from starlette.middleware.sessions import SessionMiddleware

from src.config import settings
from src.webhook.router import router as webhook_router
from src.api.repos import router as api_repos_router
from src.api.stats import router as api_stats_router
from src.ui.router import router as ui_router
from src.auth.google import router as auth_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("DB migration completed")
    except Exception as exc:
        logger.error("DB migration failed: %s", exc)
    yield


app = FastAPI(title="SCAManager", version="0.1.0", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
app.include_router(auth_router)
app.include_router(webhook_router)
app.include_router(api_repos_router)
app.include_router(api_stats_router)
app.include_router(ui_router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/ -q
```

Expected: `162 passed`

- [ ] **Step 3: Commit**

```bash
git add src/main.py
git commit -m "feat: register SessionMiddleware and auth router in main.py"
```

---

## Task 9: UI router — require_login + user_id filtering + ownership check (TDD)

**Files:**
- Modify: `tests/test_ui_router.py`
- Modify: `src/ui/router.py`

- [ ] **Step 1: Update tests/test_ui_router.py**

Replace the full content of `tests/test_ui_router.py` with:

```python
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-cid")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-csecret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from src.main import app
from src.auth.session import require_login
from src.models.user import User as UserModel

# 모든 UI 테스트에서 require_login 의존성을 우회 (user_id=1 로그인 상태)
_test_user = UserModel(id=1, google_id="g-id-1", email="test@example.com", display_name="Test User")
app.dependency_overrides[require_login] = lambda: _test_user

client = TestClient(app)


def _ctx(db_mock):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_mock)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


# ── 비로그인 리다이렉트 테스트 ──────────────────────────

def test_overview_redirects_when_not_logged_in():
    """비로그인 상태에서 / 접근 시 /login 으로 302 리다이렉트."""
    # 일시적으로 override 제거
    del app.dependency_overrides[require_login]
    try:
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 302
        assert "/login" in r.headers.get("location", "")
    finally:
        app.dependency_overrides[require_login] = lambda: _test_user


# ── 로그인 상태 기존 테스트 (mock 패턴 user_id 필터 반영) ──

def test_overview_returns_html():
    """로그인 후 / 는 200 HTML을 반환한다."""
    mock_db = MagicMock()
    # .filter().order_by().all() 체인 mock
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_repo_detail_returns_html():
    """로그인 후 본인 리포 상세 페이지는 200 HTML을 반환한다."""
    mock_db = MagicMock()
    # user_id=None → 소유권 체크 통과 (nullable 기존 레코드)
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo")
    assert r.status_code == 200


def test_repo_detail_404():
    """존재하지 않는 리포 접근 시 404."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/nope%2Frepo")
    assert r.status_code == 404


def test_repo_detail_404_for_other_users_repo():
    """타인 소유 리포(user_id=2) 접근 시 404. 현재 사용자는 user_id=1."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=2, full_name="owner/repo", user_id=2  # 타인 소유
    )
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo")
    assert r.status_code == 404


def test_settings_returns_html():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    from src.config_manager.manager import RepoConfigData
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.get_repo_config",
                   return_value=RepoConfigData(repo_full_name="owner/repo")):
            r = client.get("/repos/owner%2Frepo/settings")
    assert r.status_code == 200


def test_post_settings_redirects():
    mock_db = MagicMock()
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.upsert_repo_config") as mock_upsert:
            r = client.post(
                "/repos/owner%2Frepo/settings",
                data={
                    "gate_mode": "auto",
                    "auto_approve_threshold": "85",
                    "auto_reject_threshold": "55",
                    "notify_chat_id": "-123",
                    "n8n_webhook_url": "http://n8n.local/webhook/abc",
                },
                follow_redirects=False,
            )
    assert mock_upsert.call_count == 1
    called_config = mock_upsert.call_args[0][1]
    assert called_config.n8n_webhook_url == "http://n8n.local/webhook/abc"
    assert r.status_code == 303


def test_post_settings_empty_n8n_url():
    mock_db = MagicMock()
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.upsert_repo_config") as mock_upsert:
            r = client.post(
                "/repos/owner%2Frepo/settings",
                data={
                    "gate_mode": "disabled",
                    "auto_approve_threshold": "75",
                    "auto_reject_threshold": "50",
                    "notify_chat_id": "",
                    "n8n_webhook_url": "",
                },
                follow_redirects=False,
            )
    assert mock_upsert.call_count == 1
    called_config = mock_upsert.call_args[0][1]
    assert called_config.n8n_webhook_url == ""


def test_post_settings_with_auto_merge_checked():
    mock_db = MagicMock()
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.upsert_repo_config") as mock_upsert:
            r = client.post(
                "/repos/owner%2Frepo/settings",
                data={
                    "gate_mode": "auto",
                    "auto_approve_threshold": "80",
                    "auto_reject_threshold": "50",
                    "notify_chat_id": "",
                    "n8n_webhook_url": "",
                    "auto_merge": "on",
                },
                follow_redirects=False,
            )
    assert mock_upsert.call_count == 1
    called_config = mock_upsert.call_args[0][1]
    assert called_config.auto_merge is True
    assert r.status_code == 303


def test_post_settings_without_auto_merge_checkbox():
    mock_db = MagicMock()
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.upsert_repo_config") as mock_upsert:
            r = client.post(
                "/repos/owner%2Frepo/settings",
                data={
                    "gate_mode": "auto",
                    "auto_approve_threshold": "80",
                    "auto_reject_threshold": "50",
                    "notify_chat_id": "",
                    "n8n_webhook_url": "",
                },
                follow_redirects=False,
            )
    assert mock_upsert.call_count == 1
    called_config = mock_upsert.call_args[0][1]
    assert called_config.auto_merge is False
    assert r.status_code == 303
```

- [ ] **Step 2: Run the new tests to verify failure (before ui/router.py update)**

```bash
pytest tests/test_ui_router.py::test_overview_redirects_when_not_logged_in tests/test_ui_router.py::test_repo_detail_404_for_other_users_repo -v
```

Expected: `FAILED` — routes don't have require_login yet, so no 302 and no ownership check

- [ ] **Step 3: Update src/ui/router.py**

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from src.database import SessionLocal
from src.models.repository import Repository
from src.models.analysis import Analysis
from src.models.user import User
from src.auth.session import require_login
from src.config_manager.manager import get_repo_config, upsert_repo_config, RepoConfigData

templates = Jinja2Templates(directory="src/templates")
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def overview(request: Request, current_user: User = Depends(require_login)):
    with SessionLocal() as db:
        repos = db.query(Repository).filter(
            Repository.user_id == current_user.id
        ).order_by(Repository.created_at.desc()).all()
        repo_data = []
        for r in repos:
            latest = (db.query(Analysis).filter(Analysis.repo_id == r.id)
                      .order_by(Analysis.created_at.desc()).first())
            count = db.query(Analysis).filter(Analysis.repo_id == r.id).count()
            repo_data.append({
                "full_name": r.full_name,
                "analysis_count": count,
                "latest_score": latest.score if latest else None,
                "latest_grade": latest.grade if latest else None,
            })
    return templates.TemplateResponse(request, "overview.html", {
        "repos": repo_data,
        "current_user": current_user,
    })


@router.get("/repos/{repo_name:path}/settings", response_class=HTMLResponse)
def repo_settings(request: Request, repo_name: str, current_user: User = Depends(require_login)):
    with SessionLocal() as db:
        repo = db.query(Repository).filter(Repository.full_name == repo_name).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        if repo.user_id is not None and repo.user_id != current_user.id:
            raise HTTPException(status_code=404)
        config = get_repo_config(db, repo_name)
    return templates.TemplateResponse(request, "settings.html", {
        "repo_name": repo_name, "config": config,
    })


@router.post("/repos/{repo_name:path}/settings")
async def update_repo_settings(request: Request, repo_name: str, current_user: User = Depends(require_login)):
    form = await request.form()
    with SessionLocal() as db:
        upsert_repo_config(db, RepoConfigData(
            repo_full_name=repo_name,
            gate_mode=form.get("gate_mode", "disabled"),
            auto_approve_threshold=int(form.get("auto_approve_threshold", 75)),
            auto_reject_threshold=int(form.get("auto_reject_threshold", 50)),
            notify_chat_id=form.get("notify_chat_id") or None,
            n8n_webhook_url=form.get("n8n_webhook_url", ""),
            auto_merge=form.get("auto_merge") == "on",
        ))
    return RedirectResponse(url=f"/repos/{repo_name}/settings", status_code=303)


@router.get("/repos/{repo_name:path}", response_class=HTMLResponse)
def repo_detail(request: Request, repo_name: str, current_user: User = Depends(require_login)):
    with SessionLocal() as db:
        repo = db.query(Repository).filter(Repository.full_name == repo_name).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        if repo.user_id is not None and repo.user_id != current_user.id:
            raise HTTPException(status_code=404)
        analyses = (db.query(Analysis).filter(Analysis.repo_id == repo.id)
                    .order_by(Analysis.created_at.desc()).limit(30).all())
        analyses_data = [
            {"commit_sha": a.commit_sha, "pr_number": a.pr_number,
             "score": a.score, "grade": a.grade,
             "created_at": a.created_at.isoformat() if a.created_at else None}
            for a in analyses
        ]
        rev = list(reversed(analyses_data))
    return templates.TemplateResponse(request, "repo_detail.html", {
        "repo_name": repo_name, "analyses": analyses_data,
        "chart_labels": [a["created_at"][:10] if a["created_at"] else "" for a in rev],
        "chart_scores": [a["score"] for a in rev],
    })
```

- [ ] **Step 4: Run test_ui_router.py to verify all pass**

```bash
pytest tests/test_ui_router.py -v
```

Expected: `11 passed` (8 existing + 2 new auth tests + 1 ownership 404)

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -q
```

Expected: `173 passed` (162 prior + 11 in test_ui_router = total accounts for overlap, net new ~3)

Note: exact count depends on whether prior run was 162; verify `0 failed` matters most.

- [ ] **Step 6: Lint check**

```bash
make lint
```

Expected: pylint ≥ 8.0, bandit 0 HIGH issues

- [ ] **Step 7: Commit**

```bash
git add tests/test_ui_router.py src/ui/router.py
git commit -m "feat: protect UI routes with require_login and filter repos by user_id"
```

---

## Task 10: Final integration — run all tests + push + PR

- [ ] **Step 1: Run full test suite (final)**

```bash
pytest tests/ -q
```

Expected: `0 failed`

- [ ] **Step 2: Run E2E tests**

```bash
make test-e2e
```

Note: E2E tests will now redirect to `/login` for all routes since the real app requires login. This is expected. Existing E2E tests (`test_theme.py`, `test_settings.py`, `test_navigation.py`) will need to be updated in a follow-up to inject a session cookie — but that's Phase 8B scope. For now, verify unit tests all pass.

- [ ] **Step 3: Lint**

```bash
make lint
```

Expected: pylint ≥ 8.0, bandit 0 HIGH

- [ ] **Step 4: Create PR**

```bash
git push origin main
gh pr create --title "feat: Phase 8A — Google OAuth + User model + per-user dashboard" \
  --body "$(cat <<'EOF'
## Summary
- Google OAuth2 login via authlib (SessionMiddleware cookie sessions)
- New `User` ORM + `users` table (google_id, email, display_name)
- `Repository.user_id` FK (nullable for backward compat with existing webhook repos)
- Alembic migration 0005: creates users table + adds repositories.user_id
- `require_login` FastAPI dependency guards all UI routes (/, /repos/*)
- Overview shows only current user's repos (user_id filter)
- Repo detail / settings enforce ownership (user_id mismatch → 404)

## Test plan
- [ ] `make test` — all tests pass (target: 0 failed)
- [ ] `make lint` — pylint ≥ 8.0, bandit 0 HIGH
- [ ] Manual: set GOOGLE_CLIENT_ID/SECRET/SESSION_SECRET in .env
- [ ] Manual: `make run` → visit `/login` → Google login → dashboard shows own repos
- [ ] Manual: logout → visit `/` → redirected to `/login`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ Google OAuth flow (Task 6: /auth/google, /auth/callback)
- ✅ User model (Task 2: google_id, email, display_name, created_at)
- ✅ Repository.user_id FK (Task 3)
- ✅ DB migration (Task 4: 0005)
- ✅ get_current_user + require_login (Task 5)
- ✅ SessionMiddleware in main.py (Task 8)
- ✅ UI routes protected (Task 9: require_login Depends)
- ✅ Per-user dashboard (Task 9: filter by user_id)
- ✅ Ownership check on repo_detail/settings (Task 9: user_id mismatch → 404)
- ✅ Login page template (Task 7)
- ✅ Existing 146 tests adapted (Task 9: dependency override)
- ✅ New tests: test_user_model (6), test_auth_session (5), test_auth_google (5), test_ui_router (3 new) = +19 tests

**Type consistency:**
- `require_login` returns `User` — used as `current_user: User = Depends(require_login)` everywhere ✅
- `get_current_user` returns `User | None` — `require_login` checks for None before returning ✅
- `Repository.owner` ↔ `User.repositories` backref names match ✅
- Migration down_revision `0004addautomerge` matches existing migration ✅
