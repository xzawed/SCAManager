# Phase 8B: GitHub OAuth + 리포 추가 UI + Webhook 자동 생성 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Google OAuth를 GitHub OAuth로 교체하고, 사용자가 대시보드에서 GitHub 리포를 선택해 Webhook을 자동 생성할 수 있게 한다.

**Architecture:** authlib의 GitHub OAuth2 플로우로 `repo user:email` 스코프 access_token을 획득해 DB에 저장. 리포 추가 시 해당 토큰으로 GitHub API를 호출해 리포 목록을 가져오고 Webhook을 자동 생성. Webhook 검증은 리포별 랜덤 시크릿으로 수행하되 레거시 리포는 전역 시크릿 fallback 유지.

**Tech Stack:** FastAPI, authlib (GitHub OAuth2), SQLAlchemy, Alembic, httpx, Jinja2, SQLite(테스트)/PostgreSQL(운영)

---

## 파일 구조

```
신규:
  alembic/versions/0006_phase8b_github_oauth.py   — 마이그레이션
  src/auth/github.py                               — GitHub OAuth 라우터
  src/github_client/repos.py                       — list_user_repos, create_webhook, delete_webhook
  src/templates/add_repo.html                      — 리포 추가 페이지
  tests/test_auth_github.py                        — GitHub OAuth 테스트
  tests/test_github_repos.py                       — GitHub API 클라이언트 테스트

수정:
  src/models/user.py           — google_id→github_id, github_login, github_access_token
  src/models/repository.py     — webhook_secret, webhook_id 추가
  src/config.py                — google_* 제거, github_client_* 추가, github_token/webhook_secret optional
  src/main.py                  — auth import 교체
  src/auth/google.py           — 삭제
  src/templates/login.html     — GitHub 로그인 버튼
  src/templates/overview.html  — "리포 추가" 버튼 + empty state 변경
  src/webhook/router.py        — 리포별 시크릿 조회 검증
  src/worker/pipeline.py       — owner 토큰 사용
  src/ui/router.py             — /repos/add, /api/github/repos 추가
  tests/conftest.py            — GOOGLE_* → GITHUB_CLIENT_*
  tests/test_user_model.py     — google_id → github_id, 신규 필드 테스트
  tests/test_webhook_router.py — 리포별 시크릿 테스트 추가
  tests/test_pipeline.py       — owner 토큰 fallback 테스트 추가
  tests/test_ui_router.py      — /repos/add 테스트 추가

삭제:
  src/auth/google.py
  tests/test_auth_google.py
```

---

## Task 1: DB 마이그레이션 + User/Repository 모델 업데이트

**Files:**
- Create: `alembic/versions/0006_phase8b_github_oauth.py`
- Modify: `src/models/user.py`
- Modify: `src/models/repository.py`
- Modify: `tests/test_user_model.py`

- [ ] **Step 1: 마이그레이션 파일 작성**

`alembic/versions/0006_phase8b_github_oauth.py`:

```python
"""phase8b github oauth — rename google_id to github_id, add github fields, webhook fields

Revision ID: 0006phase8bgithub
Revises: 0005addusers
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa

revision = '0006phase8bgithub'
down_revision = '0005addusers'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users: google_id → github_id (batch mode for SQLite compatibility)
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('google_id', new_column_name='github_id')
        batch_op.add_column(sa.Column('github_login', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('github_access_token', sa.String(), nullable=True))

    # repositories: webhook_secret, webhook_id 추가
    op.add_column('repositories', sa.Column('webhook_secret', sa.String(), nullable=True))
    op.add_column('repositories', sa.Column('webhook_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('repositories', 'webhook_id')
    op.drop_column('repositories', 'webhook_secret')

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('github_access_token')
        batch_op.drop_column('github_login')
        batch_op.alter_column('github_id', new_column_name='google_id')
```

- [ ] **Step 2: User 모델 업데이트**

`src/models/user.py` 전체 교체:

```python
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from src.database import Base


class User(Base):
    __tablename__ = "users"

    id                  = Column(Integer, primary_key=True, index=True)
    github_id           = Column(String, unique=True, nullable=False, index=True)
    github_login        = Column(String, nullable=True)
    github_access_token = Column(String, nullable=True)
    email               = Column(String, unique=True, nullable=False)
    display_name        = Column(String, nullable=False)
    created_at          = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    repositories = relationship("Repository", back_populates="owner")
```

- [ ] **Step 3: Repository 모델 업데이트**

`src/models/repository.py`에 두 컬럼 추가:

```python
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.database import Base


class Repository(Base):
    __tablename__ = "repositories"

    id             = Column(Integer, primary_key=True, index=True)
    full_name      = Column(String, unique=True, nullable=False, index=True)
    telegram_chat_id = Column(String, nullable=True)
    created_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    webhook_secret = Column(String, nullable=True)
    webhook_id     = Column(Integer, nullable=True)

    analyses = relationship("Analysis", back_populates="repository")
    owner    = relationship("User", back_populates="repositories")
```

- [ ] **Step 4: 실패하는 테스트 먼저 작성**

`tests/test_user_model.py` 전체 교체 (google_id → github_id, 신규 필드 추가):

```python
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

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
    user = User(
        github_id="12345",
        github_login="octocat",
        github_access_token="gho_test_token",
        email="test@example.com",
        display_name="Test User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    assert user.id is not None
    assert user.github_id == "12345"
    assert user.github_login == "octocat"
    assert user.github_access_token == "gho_test_token"
    assert user.email == "test@example.com"
    assert user.display_name == "Test User"
    assert user.created_at is not None


def test_github_id_unique_constraint(db):
    """github_id는 unique 제약이 있다."""
    db.add(User(github_id="same-id", email="a@b.com", display_name="User A"))
    db.commit()
    db.add(User(github_id="same-id", email="c@d.com", display_name="User B"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_email_unique_constraint(db):
    """email은 unique 제약이 있다."""
    db.add(User(github_id="id-1", email="same@example.com", display_name="User A"))
    db.commit()
    db.add(User(github_id="id-2", email="same@example.com", display_name="User B"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_user_query_by_github_id(db):
    """github_id로 User 조회."""
    db.add(User(github_id="gh-456", email="foo@bar.com", display_name="Foo Bar"))
    db.commit()
    found = db.query(User).filter(User.github_id == "gh-456").first()
    assert found is not None
    assert found.email == "foo@bar.com"


def test_github_access_token_nullable(db):
    """github_access_token은 nullable이다."""
    user = User(github_id="no-token", email="notoken@example.com", display_name="No Token")
    db.add(user)
    db.commit()
    db.refresh(user)
    assert user.github_access_token is None


def test_repository_user_id_is_nullable(db):
    """기존 Repository는 user_id 없이 생성 가능하다 (하위 호환성)."""
    from src.models.repository import Repository
    repo = Repository(full_name="owner/orphan-repo")
    db.add(repo)
    db.commit()
    db.refresh(repo)
    assert repo.user_id is None
    assert repo.webhook_secret is None
    assert repo.webhook_id is None


def test_repository_webhook_fields(db):
    """Repository에 webhook_secret, webhook_id를 저장할 수 있다."""
    from src.models.repository import Repository
    user = User(github_id="g-wh", email="wh@example.com", display_name="WH User")
    db.add(user)
    db.flush()
    repo = Repository(
        full_name="owner/webhook-repo",
        user_id=user.id,
        webhook_secret="abc123secret",
        webhook_id=99999,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    assert repo.webhook_secret == "abc123secret"
    assert repo.webhook_id == 99999


def test_repository_owner_relationship(db):
    """Repository.owner는 연결된 User를 반환한다."""
    from src.models.repository import Repository
    user = User(github_id="g-rel-1", email="rel@example.com", display_name="Rel User")
    db.add(user)
    db.flush()
    repo = Repository(full_name="owner/owned-repo", user_id=user.id)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    assert repo.user_id == user.id
    assert repo.owner.email == "rel@example.com"
```

- [ ] **Step 5: 테스트 실패 확인**

```bash
pytest tests/test_user_model.py -v
```

Expected: FAIL — `User` has no attribute `github_id` (모델 아직 안 바뀐 상태에서 실행 시) 또는 import 오류

- [ ] **Step 6: 테스트 통과 확인**

모델과 마이그레이션 파일 작성 완료 후:

```bash
pytest tests/test_user_model.py -v
```

Expected: 8 PASSED

- [ ] **Step 7: test_ui_router.py의 google_id 참조 수정**

`tests/test_ui_router.py` 9-10번째 줄 (Google 환경변수):

```python
# 변경 전
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-cid")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-csecret")

# 변경 후
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
```

`tests/test_ui_router.py` 20번째 줄 (`_test_user` 객체):

```python
# 변경 전
_test_user = UserModel(id=1, google_id="g-id-1", email="test@example.com", display_name="Test User")

# 변경 후
_test_user = UserModel(id=1, github_id="12345", github_login="testuser", email="test@example.com", display_name="Test User")
```

- [ ] **Step 8: 전체 테스트 통과 확인**

```bash
pytest tests/ -v
```

Expected: 전체 통과 (기존 테스트에서 `google_id` 오류 없음)

- [ ] **Step 9: 커밋**

```bash
git add alembic/versions/0006_phase8b_github_oauth.py src/models/user.py src/models/repository.py tests/test_user_model.py tests/test_ui_router.py
git commit -m "feat: DB 마이그레이션 + User/Repository 모델 Phase 8B 업데이트"
```

---

## Task 2: GitHub API 클라이언트 (repos.py)

**Files:**
- Create: `src/github_client/repos.py`
- Create: `tests/test_github_repos.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_github_repos.py`:

```python
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_list_user_repos_returns_repo_list():
    """list_user_repos는 GitHub API로 리포 목록을 반환한다."""
    from src.github_client.repos import list_user_repos

    mock_response_data = [
        {"full_name": "owner/repo-a", "private": False, "description": "Repo A"},
        {"full_name": "owner/repo-b", "private": True, "description": "Repo B"},
    ]

    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_response_data
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await list_user_repos("gho_test_token")

    assert len(result) == 2
    assert result[0]["full_name"] == "owner/repo-a"
    assert result[0]["private"] is False
    assert result[1]["full_name"] == "owner/repo-b"
    assert result[1]["private"] is True


@pytest.mark.asyncio
async def test_create_webhook_returns_webhook_id():
    """create_webhook은 GitHub API를 호출하고 webhook_id를 반환한다."""
    from src.github_client.repos import create_webhook

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": 12345678}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await create_webhook(
            token="gho_test_token",
            repo_full_name="owner/test-repo",
            webhook_url="https://example.com/webhooks/github",
            secret="random_secret_hex",
        )

    assert result == 12345678
    call_kwargs = mock_client.post.call_args
    posted_json = call_kwargs.kwargs["json"]
    assert posted_json["name"] == "web"
    assert posted_json["active"] is True
    assert "push" in posted_json["events"]
    assert "pull_request" in posted_json["events"]
    assert posted_json["config"]["url"] == "https://example.com/webhooks/github"
    assert posted_json["config"]["secret"] == "random_secret_hex"


@pytest.mark.asyncio
async def test_delete_webhook_returns_true_on_204():
    """delete_webhook은 204 응답 시 True를 반환한다."""
    from src.github_client.repos import delete_webhook

    mock_resp = MagicMock()
    mock_resp.status_code = 204

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await delete_webhook(
            token="gho_test_token",
            repo_full_name="owner/test-repo",
            webhook_id=12345678,
        )

    assert result is True


@pytest.mark.asyncio
async def test_delete_webhook_returns_false_on_error():
    """delete_webhook은 204 이외 응답 시 False를 반환한다."""
    from src.github_client.repos import delete_webhook

    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await delete_webhook(
            token="gho_test_token",
            repo_full_name="owner/test-repo",
            webhook_id=12345678,
        )

    assert result is False
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_github_repos.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.github_client.repos'`

- [ ] **Step 3: GitHub API 클라이언트 구현**

`src/github_client/repos.py`:

```python
import httpx

GITHUB_API = "https://api.github.com"
_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def _auth_headers(token: str) -> dict:
    return {**_HEADERS, "Authorization": f"Bearer {token}"}


async def list_user_repos(token: str) -> list[dict]:
    """사용자가 접근 가능한 리포 목록 반환 (public + private, per_page=100, sort=updated)."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/user/repos",
            params={"per_page": 100, "sort": "updated", "affiliation": "owner,collaborator"},
            headers=_auth_headers(token),
        )
        resp.raise_for_status()
        return [
            {
                "full_name": r["full_name"],
                "private": r["private"],
                "description": r.get("description") or "",
            }
            for r in resp.json()
        ]


async def create_webhook(token: str, repo_full_name: str, webhook_url: str, secret: str) -> int:
    """Webhook 생성 → webhook_id 반환."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GITHUB_API}/repos/{repo_full_name}/hooks",
            json={
                "name": "web",
                "active": True,
                "events": ["push", "pull_request"],
                "config": {
                    "url": webhook_url,
                    "content_type": "json",
                    "secret": secret,
                    "insecure_ssl": "0",
                },
            },
            headers=_auth_headers(token),
        )
        resp.raise_for_status()
        return resp.json()["id"]


async def delete_webhook(token: str, repo_full_name: str, webhook_id: int) -> bool:
    """Webhook 삭제. 성공(204) 시 True, 그 외 False 반환."""
    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            f"{GITHUB_API}/repos/{repo_full_name}/hooks/{webhook_id}",
            headers=_auth_headers(token),
        )
        return resp.status_code == 204
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_github_repos.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: 커밋**

```bash
git add src/github_client/repos.py tests/test_github_repos.py
git commit -m "feat: GitHub API 클라이언트 — list_user_repos, create_webhook, delete_webhook"
```

---

## Task 3: Config 변경 + GitHub OAuth 인증 교체

**Files:**
- Modify: `src/config.py`
- Modify: `tests/conftest.py`
- Create: `src/auth/github.py`
- Delete: `src/auth/google.py`
- Modify: `src/main.py`
- Modify: `src/templates/login.html`
- Create: `tests/test_auth_github.py`
- Delete: `tests/test_auth_google.py`

- [ ] **Step 1: Config 변경**

`src/config.py` 전체 교체:

```python
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    database_url: str
    github_webhook_secret: str = ""   # 레거시 리포 fallback (optional)
    github_token: str = ""            # 레거시 리포 fallback (optional)
    telegram_bot_token: str
    telegram_chat_id: str
    anthropic_api_key: str = ""
    api_key: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
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

- [ ] **Step 2: conftest.py 환경변수 업데이트**

`tests/conftest.py` 전체 교체:

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
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

from src.main import app


@pytest.fixture
def client():
    return TestClient(app)
```

- [ ] **Step 3: 실패하는 테스트 작성**

`tests/test_auth_github.py`:

```python
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_login_page_loads():
    """GET /login은 로그인 페이지(200 HTML)를 반환한다."""
    with patch("src.auth.github.get_current_user", return_value=None):
        r = client.get("/login")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_login_redirects_if_already_authenticated():
    """이미 로그인된 사용자가 /login 접근 시 / 로 리다이렉트."""
    from src.models.user import User
    mock_user = User(id=1, github_id="12345", email="a@b.com", display_name="Test")
    with patch("src.auth.github.get_current_user", return_value=mock_user):
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
    mock_token = {"access_token": "gho_new_token"}
    mock_user_info = MagicMock()
    mock_user_info.json.return_value = {
        "id": 99001,
        "login": "newuser",
        "name": "New User",
    }
    mock_emails_resp = MagicMock()
    mock_emails_resp.json.return_value = [
        {"email": "newuser@github.com", "primary": True, "verified": True}
    ]
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None  # 신규 유저

    with patch("src.auth.github.oauth.github.authorize_access_token",
               new_callable=AsyncMock, return_value=mock_token):
        with patch("src.auth.github.oauth.github.get",
                   new_callable=AsyncMock,
                   side_effect=[mock_user_info, mock_emails_resp]):
            with patch("src.auth.github.SessionLocal", return_value=mock_db):
                r = client.get(
                    "/auth/callback?code=test-code&state=test-state",
                    follow_redirects=False,
                )

    assert r.status_code == 302
    assert r.headers["location"] == "/"
    assert mock_db.add.called
    assert mock_db.commit.called


def test_callback_updates_existing_user_and_redirects():
    """콜백 처리 시 기존 유저의 토큰을 갱신하고 / 로 리다이렉트한다."""
    from src.models.user import User
    mock_token = {"access_token": "gho_updated_token"}
    mock_user_info = MagicMock()
    mock_user_info.json.return_value = {
        "id": 99002,
        "login": "existinguser",
        "name": "Existing User",
    }
    mock_emails_resp = MagicMock()
    mock_emails_resp.json.return_value = [
        {"email": "existing@github.com", "primary": True, "verified": True}
    ]
    existing_user = User(
        id=5,
        github_id="99002",
        github_login="existinguser",
        email="existing@github.com",
        display_name="Existing User",
    )
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = existing_user

    with patch("src.auth.github.oauth.github.authorize_access_token",
               new_callable=AsyncMock, return_value=mock_token):
        with patch("src.auth.github.oauth.github.get",
                   new_callable=AsyncMock,
                   side_effect=[mock_user_info, mock_emails_resp]):
            with patch("src.auth.github.SessionLocal", return_value=mock_db):
                r = client.get(
                    "/auth/callback?code=test-code&state=test-state",
                    follow_redirects=False,
                )

    assert r.status_code == 302
    assert r.headers["location"] == "/"
    assert not mock_db.add.called   # 기존 유저이므로 add 미호출
    assert existing_user.github_access_token == "gho_updated_token"
```

- [ ] **Step 4: 테스트 실패 확인**

```bash
pytest tests/test_auth_github.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.auth.github'` 또는 import 오류

- [ ] **Step 5: GitHub OAuth 라우터 구현**

`src/auth/github.py`:

```python
import logging
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.config import settings
from src.database import SessionLocal
from src.models.user import User
from src.auth.session import get_current_user

logger = logging.getLogger(__name__)

oauth = OAuth()
oauth.register(
    name="github",
    client_id=settings.github_client_id,
    client_secret=settings.github_client_secret,
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "repo user:email"},
)

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="src/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """로그인 페이지. 이미 로그인된 경우 / 로 리다이렉트."""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request, "login.html", {})


@router.get("/auth/github")
async def auth_github(request: Request):
    """GitHub OAuth 동의 화면으로 리다이렉트."""
    redirect_uri = str(request.url_for("auth_callback"))
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request):
    """GitHub OAuth 콜백. 유저 upsert 후 세션 저장."""
    token = await oauth.github.authorize_access_token(request)
    access_token = token["access_token"]

    user_resp = await oauth.github.get("user", token=token)
    user_info = user_resp.json()

    emails_resp = await oauth.github.get("user/emails", token=token)
    emails = emails_resp.json()
    primary_email = next(
        (e["email"] for e in emails if e.get("primary") and e.get("verified")),
        user_info.get("email") or "",
    )

    github_id = str(user_info["id"])
    github_login = user_info.get("login", "")
    display_name = user_info.get("name") or github_login

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.github_id == github_id).first()
        if not user:
            user = User(
                github_id=github_id,
                github_login=github_login,
                github_access_token=access_token,
                email=primary_email,
                display_name=display_name,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.github_access_token = access_token
            user.github_login = github_login
            user.display_name = display_name
            db.commit()
        request.session["user_id"] = user.id
    finally:
        db.close()

    return RedirectResponse(url="/", status_code=302)


@router.post("/auth/logout")
async def logout(request: Request):
    """세션 초기화 후 /login 리다이렉트."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)
```

- [ ] **Step 6: main.py import 교체**

`src/main.py` 14번째 줄:

```python
# 변경 전
from src.auth.google import router as auth_router

# 변경 후
from src.auth.github import router as auth_router
```

- [ ] **Step 7: login.html 업데이트 (Google → GitHub 버튼)**

`src/templates/login.html` 전체 교체:

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
  .btn-github {
    display: inline-flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    justify-content: center;
    padding: .75rem 1.5rem;
    background: #24292f;
    color: #fff;
    border: 1px solid #24292f;
    border-radius: var(--radius-btn);
    font-size: 15px;
    font-weight: 500;
    text-decoration: none;
    transition: box-shadow var(--transition), background var(--transition);
    cursor: pointer;
  }
  .btn-github:hover {
    background: #32383f;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    color: #fff;
    text-decoration: none;
  }
  .btn-github svg { flex-shrink: 0; }
</style>

<div class="login-wrap">
  <div class="card login-card">
    <div class="login-logo">⚡</div>
    <h1 class="login-title">SCAManager</h1>
    <p class="login-sub">GitHub 정적 분석 + AI 코드 리뷰 플랫폼</p>
    <a href="/auth/github" class="btn-github">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="white">
        <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
      </svg>
      GitHub로 로그인
    </a>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 8: 기존 파일 삭제**

```bash
rm src/auth/google.py
rm tests/test_auth_google.py
```

- [ ] **Step 9: 테스트 통과 확인**

```bash
pytest tests/test_auth_github.py -v
```

Expected: 5 PASSED

- [ ] **Step 10: 전체 테스트 확인**

```bash
pytest tests/ -v --ignore=tests/test_auth_google.py 2>/dev/null || pytest tests/ -v
```

Expected: 모든 테스트 통과 (test_auth_google.py 삭제됐으므로 해당 파일 오류 없음)

- [ ] **Step 11: 커밋**

```bash
git add src/config.py src/auth/github.py src/main.py src/templates/login.html tests/conftest.py tests/test_auth_github.py
git commit -m "feat: Google OAuth → GitHub OAuth 교체 (repo user:email 스코프)"
```

---

## Task 4: Webhook 검증 로직 변경 (리포별 시크릿)

**Files:**
- Modify: `src/webhook/router.py`
- Modify: `tests/test_webhook_router.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_webhook_router.py`를 읽고 아래 테스트 2개를 파일 끝에 추가:

```python
def test_webhook_uses_repo_specific_secret(client):
    """리포별 webhook_secret이 있으면 해당 시크릿으로 검증한다."""
    import hmac, hashlib
    from unittest.mock import patch, MagicMock

    payload = b'{"repository": {"full_name": "owner/repo-with-secret"}, "ref": "refs/heads/main", "after": "abc123", "commits": []}'
    repo_secret = "per-repo-secret-xyz"
    sig = "sha256=" + hmac.new(repo_secret.encode(), payload, hashlib.sha256).hexdigest()

    mock_repo = MagicMock()
    mock_repo.webhook_secret = repo_secret
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_repo
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=None)

    with patch("src.webhook.router.SessionLocal", return_value=mock_db):
        with patch("src.webhook.router.run_analysis_pipeline"):
            r = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": sig,
                    "X-GitHub-Event": "push",
                    "Content-Type": "application/json",
                },
            )
    assert r.status_code == 202


def test_webhook_falls_back_to_global_secret_for_legacy_repo(client):
    """webhook_secret이 없는 레거시 리포는 전역 시크릿으로 검증한다."""
    import hmac, hashlib
    from unittest.mock import patch, MagicMock

    payload = b'{"repository": {"full_name": "owner/legacy-repo"}, "ref": "refs/heads/main", "after": "abc123", "commits": []}'
    global_secret = "test_secret"  # conftest.py의 GITHUB_WEBHOOK_SECRET
    sig = "sha256=" + hmac.new(global_secret.encode(), payload, hashlib.sha256).hexdigest()

    mock_repo = MagicMock()
    mock_repo.webhook_secret = None   # 레거시 리포
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_repo
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=None)

    with patch("src.webhook.router.SessionLocal", return_value=mock_db):
        with patch("src.webhook.router.run_analysis_pipeline"):
            r = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": sig,
                    "X-GitHub-Event": "push",
                    "Content-Type": "application/json",
                },
            )
    assert r.status_code == 202
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_webhook_router.py::test_webhook_uses_repo_specific_secret tests/test_webhook_router.py::test_webhook_falls_back_to_global_secret_for_legacy_repo -v
```

Expected: FAIL — 기존 코드는 전역 시크릿만 사용하므로 per-repo-secret 테스트 실패

- [ ] **Step 3: Webhook 검증 로직 변경**

`src/webhook/router.py`의 `github_webhook` 함수를 아래로 교체:

```python
@router.post("/webhooks/github", status_code=202)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None),
):
    payload = await request.body()

    # payload에서 리포 이름 파싱 (per-repo 시크릿 조회용)
    full_name = ""
    try:
        data = json.loads(payload)
        full_name = data.get("repository", {}).get("full_name", "")
    except (json.JSONDecodeError, AttributeError):
        data = {}

    # 리포별 시크릿 조회 → 없으면 전역 시크릿 fallback
    secret = settings.github_webhook_secret
    if full_name:
        with SessionLocal() as db:
            repo = db.query(Repository).filter(
                Repository.full_name == full_name
            ).first()
            if repo and repo.webhook_secret:
                secret = repo.webhook_secret

    if not verify_github_signature(payload, x_hub_signature_256, secret):
        raise HTTPException(status_code=401, detail="Invalid signature")

    if not data:
        return {"status": "ignored"}

    if x_github_event not in HANDLED_EVENTS:
        return {"status": "ignored"}

    if x_github_event == "pull_request":
        action = data.get("action")
        if action not in HANDLED_PR_ACTIONS:
            return {"status": "ignored"}

    background_tasks.add_task(run_analysis_pipeline, x_github_event, data)
    return {"status": "accepted"}
```

**주의:** 파일 상단에 `from src.models.repository import Repository` import가 이미 있는지 확인. 없으면 추가.

- [ ] **Step 4: SessionLocal context manager 확인**

`src/webhook/router.py` 상단 import에 `SessionLocal`이 있는지 확인. 이미 있음 (기존 코드에서 사용 중).

- [ ] **Step 5: 테스트 통과 확인**

```bash
pytest tests/test_webhook_router.py -v
```

Expected: 모든 기존 테스트 + 신규 2개 통과

- [ ] **Step 6: 커밋**

```bash
git add src/webhook/router.py tests/test_webhook_router.py
git commit -m "feat: Webhook 검증 — 리포별 시크릿 우선, 레거시 전역 시크릿 fallback"
```

---

## Task 5: 파이프라인 변경 (owner 토큰 사용)

**Files:**
- Modify: `src/worker/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_pipeline.py`를 읽고 파일 끝에 아래 테스트 2개를 추가:

```python
@pytest.mark.asyncio
async def test_pipeline_uses_owner_github_token():
    """리포 owner의 github_access_token이 있으면 settings.github_token 대신 사용한다."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from src.models.user import User
    from src.models.repository import Repository

    owner = User(id=1, github_id="111", github_login="owner", email="o@e.com",
                 display_name="Owner", github_access_token="gho_owner_token")
    repo = MagicMock(spec=Repository)
    repo.id = 10
    repo.full_name = "owner/repo"
    repo.owner = owner

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = repo
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=None)

    event_data = {
        "repository": {"full_name": "owner/repo"},
        "pull_request": {"head": {"sha": "abc123"}, "title": "feat: test"},
        "number": 1,
    }

    with patch("src.worker.pipeline.SessionLocal", return_value=mock_db):
        with patch("src.worker.pipeline.get_pr_files", return_value=[]) as mock_get_files:
            await run_analysis_pipeline("pull_request", event_data)

    # owner 토큰이 사용됐는지 확인
    if mock_get_files.called:
        call_args = mock_get_files.call_args
        assert call_args[0][0] == "gho_owner_token"


@pytest.mark.asyncio
async def test_pipeline_falls_back_to_settings_token_when_no_owner():
    """owner나 github_access_token이 없으면 settings.github_token을 사용한다."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from src.models.repository import Repository

    repo = MagicMock(spec=Repository)
    repo.id = 20
    repo.full_name = "owner/legacy-repo"
    repo.owner = None  # 소유자 없는 레거시 리포

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = repo
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=None)

    event_data = {
        "repository": {"full_name": "owner/legacy-repo"},
        "after": "def456",
        "commits": [{"message": "fix: legacy"}],
    }

    with patch("src.worker.pipeline.SessionLocal", return_value=mock_db):
        with patch("src.worker.pipeline.get_push_files", return_value=[]) as mock_get_files:
            await run_analysis_pipeline("push", event_data)

    if mock_get_files.called:
        call_args = mock_get_files.call_args
        assert call_args[0][0] == "ghp_test"  # conftest의 GITHUB_TOKEN
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_pipeline.py::test_pipeline_uses_owner_github_token tests/test_pipeline.py::test_pipeline_falls_back_to_settings_token_when_no_owner -v
```

Expected: FAIL — 현재 파이프라인은 `settings.github_token` 고정 사용

- [ ] **Step 3: 파이프라인 owner 토큰 로직 추가**

`src/worker/pipeline.py`의 `run_analysis_pipeline` 함수에서 첫 번째 DB 세션 블록을 교체:

```python
async def run_analysis_pipeline(event: str, data: dict) -> None:
    try:
        repo_name: str = data["repository"]["full_name"]
        commit_message = _extract_commit_message(event, data)

        # Repository 등록 + owner 토큰 결정
        owner_token: str = settings.github_token  # 기본값: 전역 토큰 fallback
        db: Session = SessionLocal()
        try:
            repo = db.query(Repository).filter_by(full_name=repo_name).first()
            if not repo:
                repo = Repository(
                    full_name=repo_name,
                    telegram_chat_id=settings.telegram_chat_id,
                )
                db.add(repo)
                db.commit()
            if repo.owner and repo.owner.github_access_token:
                owner_token = repo.owner.github_access_token
        finally:
            db.close()
```

그 다음, `settings.github_token`이 사용되는 모든 위치를 `owner_token`으로 교체:

- 줄 57: `files = get_pr_files(settings.github_token, ...)` → `files = get_pr_files(owner_token, ...)`
- 줄 61: `files = get_push_files(settings.github_token, ...)` → `files = get_push_files(owner_token, ...)`
- 줄 127: `github_token=settings.github_token,` → `github_token=owner_token,`
- 줄 155: `github_token=settings.github_token,` → `github_token=owner_token,`

최종 `run_analysis_pipeline` 전체:

```python
async def run_analysis_pipeline(event: str, data: dict) -> None:
    try:
        repo_name: str = data["repository"]["full_name"]
        commit_message = _extract_commit_message(event, data)

        # Repository 등록 + owner 토큰 결정
        owner_token: str = settings.github_token
        db: Session = SessionLocal()
        try:
            repo = db.query(Repository).filter_by(full_name=repo_name).first()
            if not repo:
                repo = Repository(
                    full_name=repo_name,
                    telegram_chat_id=settings.telegram_chat_id,
                )
                db.add(repo)
                db.commit()
            if repo.owner and repo.owner.github_access_token:
                owner_token = repo.owner.github_access_token
        finally:
            db.close()

        if event == "pull_request":
            pr_number: int | None = data["number"]
            commit_sha: str = data["pull_request"]["head"]["sha"]
            files = get_pr_files(owner_token, repo_name, pr_number)
        else:
            pr_number = None
            commit_sha = data["after"]
            files = get_push_files(owner_token, repo_name, commit_sha)

        if not files:
            logger.info("No changed files in %s @ %s", repo_name, commit_sha)
            return

        patches = [(f.filename, f.patch) for f in files if f.patch]
        analysis_results, ai_review = await asyncio.gather(
            _run_static_analysis(files),
            review_code(settings.anthropic_api_key, commit_message, patches),
        )

        score_result = calculate_score(analysis_results, ai_review=ai_review)

        n8n_url: str | None = None
        db = SessionLocal()
        try:
            repo = db.query(Repository).filter_by(full_name=repo_name).first()

            existing = db.query(Analysis).filter_by(
                commit_sha=commit_sha, repo_id=repo.id
            ).first()
            if existing:
                logger.info("Commit %s already analyzed, skipping", commit_sha)
                return

            analysis = Analysis(
                repo_id=repo.id,
                commit_sha=commit_sha,
                pr_number=pr_number,
                score=score_result.total,
                grade=score_result.grade,
                result={
                    "breakdown": score_result.breakdown,
                    "ai_summary": ai_review.summary,
                    "ai_suggestions": ai_review.suggestions,
                    "commit_message_feedback": ai_review.commit_message_feedback,
                    "code_quality_feedback": ai_review.code_quality_feedback,
                    "security_feedback": ai_review.security_feedback,
                    "direction_feedback": ai_review.direction_feedback,
                    "test_feedback": ai_review.test_feedback,
                    "file_feedbacks": ai_review.file_feedbacks,
                    "issues": [
                        {
                            "tool": i.tool,
                            "severity": i.severity,
                            "message": i.message,
                            "line": i.line,
                        }
                        for r in analysis_results
                        for i in r.issues
                    ],
                },
            )
            db.add(analysis)
            db.commit()
            db.refresh(analysis)

            n8n_url = get_repo_config(db, repo_name).n8n_webhook_url

            if pr_number is not None:
                try:
                    await run_gate_check(
                        db=db,
                        github_token=owner_token,
                        telegram_bot_token=settings.telegram_bot_token,
                        repo_full_name=repo_name,
                        pr_number=pr_number,
                        analysis_id=analysis.id,
                        score_result=score_result,
                    )
                except Exception as exc:
                    logger.error("Gate check failed: %s", exc)
        finally:
            db.close()

        notify_tasks = [
            send_analysis_result(
                bot_token=settings.telegram_bot_token,
                chat_id=settings.telegram_chat_id,
                repo_name=repo_name,
                commit_sha=commit_sha,
                score_result=score_result,
                analysis_results=analysis_results,
                pr_number=pr_number,
                ai_review=ai_review,
            )
        ]
        if pr_number is not None:
            notify_tasks.append(
                post_pr_comment(
                    github_token=owner_token,
                    repo_name=repo_name,
                    pr_number=pr_number,
                    score_result=score_result,
                    analysis_results=analysis_results,
                    ai_review=ai_review,
                )
            )
        if n8n_url:
            notify_tasks.append(
                notify_n8n(
                    webhook_url=n8n_url,
                    repo_full_name=repo_name,
                    commit_sha=commit_sha,
                    pr_number=pr_number,
                    score_result=score_result,
                )
            )
        results = await asyncio.gather(*notify_tasks, return_exceptions=True)
        for idx, exc in enumerate(results):
            if isinstance(exc, Exception):
                task_names = ["telegram"]
                if pr_number is not None:
                    task_names.append("github_comment")
                if n8n_url:
                    task_names.append("n8n")
                name = task_names[idx] if idx < len(task_names) else "unknown"
                logger.error("Notification [%s] failed: %s", name, exc, exc_info=exc)

    except Exception:
        logger.exception("Analysis pipeline failed for event=%s", event)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_pipeline.py -v
```

Expected: 모든 기존 테스트 + 신규 2개 통과

- [ ] **Step 5: 커밋**

```bash
git add src/worker/pipeline.py tests/test_pipeline.py
git commit -m "feat: 파이프라인 — repo owner 토큰 우선 사용, settings.github_token fallback"
```

---

## Task 6: 리포 추가 UI + 템플릿

**Files:**
- Modify: `src/ui/router.py`
- Create: `src/templates/add_repo.html`
- Modify: `src/templates/overview.html`
- Modify: `tests/test_ui_router.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_ui_router.py`를 읽고 파일 끝에 아래 테스트들을 추가:

```python
def test_add_repo_page_loads():
    """GET /repos/add는 리포 추가 페이지(200 HTML)를 반환한다."""
    r = client.get("/repos/add")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_api_github_repos_returns_json():
    """GET /api/github/repos는 리포 목록 JSON을 반환한다."""
    from unittest.mock import AsyncMock, patch

    mock_repos = [
        {"full_name": "owner/repo-a", "private": False, "description": ""},
        {"full_name": "owner/repo-b", "private": True, "description": "Private"},
    ]

    with patch("src.ui.router.list_user_repos", new_callable=AsyncMock, return_value=mock_repos):
        with patch("src.ui.router.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.all.return_value = []
            mock_sl.return_value.__enter__.return_value = mock_db
            r = client.get("/api/github/repos")

    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 2


def test_api_github_repos_excludes_already_registered():
    """GET /api/github/repos는 이미 등록된 리포를 제외한다."""
    from unittest.mock import AsyncMock, patch, MagicMock
    from src.models.repository import Repository

    mock_repos = [
        {"full_name": "owner/repo-a", "private": False, "description": ""},
        {"full_name": "owner/already-registered", "private": False, "description": ""},
    ]
    existing_repo = MagicMock(spec=Repository)
    existing_repo.full_name = "owner/already-registered"

    with patch("src.ui.router.list_user_repos", new_callable=AsyncMock, return_value=mock_repos):
        with patch("src.ui.router.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.all.return_value = [existing_repo]
            mock_sl.return_value.__enter__.return_value = mock_db
            r = client.get("/api/github/repos")

    assert r.status_code == 200
    data = r.json()
    full_names = [repo["full_name"] for repo in data]
    assert "owner/already-registered" not in full_names
    assert "owner/repo-a" in full_names


def test_add_repo_post_creates_repo_and_webhook():
    """POST /repos/add는 리포를 DB에 저장하고 Webhook을 생성한 후 리다이렉트한다."""
    from unittest.mock import AsyncMock, patch, MagicMock

    with patch("src.ui.router.create_webhook", new_callable=AsyncMock, return_value=77777):
        with patch("src.ui.router.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None  # 미등록
            mock_sl.return_value.__enter__.return_value = mock_db
            r = client.post(
                "/repos/add",
                data={"repo_full_name": "owner/new-repo"},
                follow_redirects=False,
            )

    assert r.status_code == 303
    assert "/repos/owner/new-repo" in r.headers["location"]
    assert mock_db.add.called
    assert mock_db.commit.called


def test_add_repo_post_rejects_duplicate():
    """POST /repos/add는 이미 등록된 리포에 대해 400을 반환한다."""
    from unittest.mock import AsyncMock, patch, MagicMock
    from src.models.repository import Repository

    existing = MagicMock(spec=Repository)
    existing.full_name = "owner/already-registered"

    with patch("src.ui.router.SessionLocal") as mock_sl:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing
        mock_sl.return_value.__enter__.return_value = mock_db
        r = client.post(
            "/repos/add",
            data={"repo_full_name": "owner/already-registered"},
            follow_redirects=False,
        )

    assert r.status_code == 400
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_ui_router.py::test_add_repo_page_loads tests/test_ui_router.py::test_api_github_repos_returns_json -v
```

Expected: FAIL — 404 (라우트가 없음)

- [ ] **Step 3: ui/router.py에 신규 라우트 추가**

`src/ui/router.py` 상단 import에 추가:

```python
import secrets
from src.github_client.repos import list_user_repos, create_webhook
```

그리고 파일의 `@router.get("/", ...)` **앞에** (반드시 path variable 라우트보다 먼저) 신규 라우트 3개를 추가:

```python
@router.get("/repos/add", response_class=HTMLResponse)
async def add_repo_page(request: Request, current_user: User = Depends(require_login)):
    return templates.TemplateResponse(request, "add_repo.html", {"current_user": current_user})


@router.get("/api/github/repos")
async def github_repos_list(current_user: User = Depends(require_login)):
    with SessionLocal() as db:
        existing_names = {
            r.full_name for r in db.query(Repository).filter(
                Repository.user_id == current_user.id
            ).all()
        }
    repos = await list_user_repos(current_user.github_access_token or "")
    return [r for r in repos if r["full_name"] not in existing_names]


@router.post("/repos/add")
async def add_repo(request: Request, current_user: User = Depends(require_login)):
    form = await request.form()
    repo_full_name = (form.get("repo_full_name") or "").strip()
    if not repo_full_name:
        raise HTTPException(status_code=400, detail="리포 이름이 필요합니다")

    with SessionLocal() as db:
        existing = db.query(Repository).filter(
            Repository.full_name == repo_full_name
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="이미 등록된 리포입니다")

    webhook_secret = secrets.token_hex(32)
    webhook_url = str(request.base_url) + "webhooks/github"
    webhook_id = await create_webhook(
        current_user.github_access_token or "",
        repo_full_name,
        webhook_url,
        webhook_secret,
    )

    with SessionLocal() as db:
        repo = Repository(
            full_name=repo_full_name,
            user_id=current_user.id,
            webhook_secret=webhook_secret,
            webhook_id=webhook_id,
        )
        db.add(repo)
        db.commit()

    return RedirectResponse(url=f"/repos/{repo_full_name}", status_code=303)
```

**주의:** 위 세 라우트는 반드시 `@router.get("/repos/{repo_name:path}/settings", ...)` **앞에** 위치해야 한다. 파일의 `@router.get("/", ...)` 바로 앞에 삽입.

최종 라우트 순서:
1. `GET /repos/add` ← 신규
2. `GET /api/github/repos` ← 신규
3. `POST /repos/add` ← 신규
4. `GET /` (overview)
5. `GET /repos/{repo_name:path}/settings`
6. `POST /repos/{repo_name:path}/settings`
7. `GET /repos/{repo_name:path}`

- [ ] **Step 4: add_repo.html 작성**

`src/templates/add_repo.html`:

```html
{% extends "base.html" %}
{% block title %}리포 추가 — SCAManager{% endblock %}
{% block content %}
<style>
  .add-repo-card { max-width: 560px; margin: 2rem auto; }
  .form-group { margin-bottom: 1.25rem; }
  .form-label {
    display: block;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-muted);
    margin-bottom: .5rem;
    text-transform: uppercase;
    letter-spacing: .05em;
  }
  .form-select {
    width: 100%;
    padding: .625rem 1rem;
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: var(--radius-btn);
    color: var(--text-primary);
    font-size: 14px;
    transition: border-color var(--transition), background var(--transition);
    appearance: none;
    cursor: pointer;
  }
  .form-select:focus {
    outline: none;
    border-color: var(--border-focus);
    background: var(--bg-input-focus);
  }
  .repo-hint {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: .5rem;
  }
  .loading-text {
    font-size: 13px;
    color: var(--text-muted);
    margin-top: .5rem;
  }
</style>

<div class="page-header">
  <a class="back-btn" href="/">← 돌아가기</a>
  <div>
    <h2>리포지토리 추가</h2>
    <p class="subtitle">GitHub 리포를 선택하면 Webhook이 자동 생성됩니다</p>
  </div>
</div>

<div class="card add-repo-card">
  <form method="post" action="/repos/add" id="addRepoForm">
    <div class="form-group">
      <label class="form-label" for="repo_full_name">GitHub 리포지토리</label>
      <select class="form-select" name="repo_full_name" id="repo_full_name" required>
        <option value="">리포 목록 불러오는 중...</option>
      </select>
      <p class="repo-hint" id="repoHint">GitHub API에서 접근 가능한 리포 목록을 불러옵니다.</p>
    </div>
    <button type="submit" class="btn btn-primary" style="width:100%;justify-content:center;" id="submitBtn" disabled>
      Webhook 생성 + 리포 추가
    </button>
  </form>
</div>

{% block scripts %}
<script>
  const select = document.getElementById('repo_full_name');
  const submitBtn = document.getElementById('submitBtn');
  const hint = document.getElementById('repoHint');

  async function loadRepos() {
    try {
      const resp = await fetch('/api/github/repos');
      if (!resp.ok) throw new Error('API 오류: ' + resp.status);
      const repos = await resp.json();

      select.innerHTML = '';
      if (repos.length === 0) {
        select.innerHTML = '<option value="">추가 가능한 리포가 없습니다</option>';
        hint.textContent = '모든 리포가 이미 등록되었거나 접근 가능한 리포가 없습니다.';
        return;
      }

      const placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = '리포를 선택하세요';
      select.appendChild(placeholder);

      repos.forEach(repo => {
        const opt = document.createElement('option');
        opt.value = repo.full_name;
        opt.textContent = repo.full_name + (repo.private ? ' 🔒' : '');
        select.appendChild(opt);
      });

      hint.textContent = repos.length + '개 리포를 불러왔습니다.';
    } catch (e) {
      select.innerHTML = '<option value="">리포 목록 로드 실패</option>';
      hint.textContent = '오류: ' + e.message;
    }
  }

  select.addEventListener('change', () => {
    submitBtn.disabled = !select.value;
  });

  loadRepos();
</script>
{% endblock %}
{% endblock %}
```

- [ ] **Step 5: overview.html 업데이트 ("리포 추가" 버튼 + empty state 변경)**

`src/templates/overview.html`에서 아래 두 곳을 변경:

**① 헤더에 "리포 추가" 버튼 추가** (93-98번째 줄 교체):

```html
<div class="overview-header">
  <h2>리포지토리 현황</h2>
  <div style="display:flex;align-items:center;gap:.75rem;">
    {% if repos %}
    <span class="repo-count">{{ repos | length }}개 리포</span>
    {% endif %}
    <a href="/repos/add" class="btn btn-primary" style="padding:.4rem 1rem;font-size:13px;">+ 리포 추가</a>
  </div>
</div>
```

**② empty state 메시지 변경** (144-151번째 줄 교체):

```html
{% else %}
<div class="card">
  <div class="empty-state">
    <div class="empty-icon">🔗</div>
    <p>등록된 리포지토리가 없습니다.<br>
      <a href="/repos/add">리포 추가</a>를 클릭해 GitHub 리포를 등록하세요.</p>
  </div>
</div>
{% endif %}
```

- [ ] **Step 6: 테스트 통과 확인**

```bash
pytest tests/test_ui_router.py -v
```

Expected: 모든 기존 테스트 + 신규 5개 통과

- [ ] **Step 7: 전체 테스트 통과 확인**

```bash
pytest tests/ -v
```

Expected: 전체 통과 (기존 164개 + 신규: ~19개 추가 = ~183개)

- [ ] **Step 8: lint 통과 확인**

```bash
make lint
```

Expected: pylint 8.0 이상, bandit HIGH 0개

- [ ] **Step 9: 커밋**

```bash
git add src/ui/router.py src/templates/add_repo.html src/templates/overview.html tests/test_ui_router.py
git commit -m "feat: 리포 추가 UI — GitHub 드롭다운 + Webhook 자동 생성"
```

---

## Task 7: CLAUDE.md 업데이트

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: CLAUDE.md 업데이트**

다음 항목을 수정:

**① 프로젝트 구조 — `src/auth/`**:
```
src/auth/
├── __init__.py
├── session.py              # get_current_user() + require_login Depends
└── github.py               # /login, /auth/github, /auth/callback, /auth/logout (authlib GitHub OAuth2)
```
(`google.py` 제거)

**② 마이그레이션 표에 0006 추가**:
```
| `0006_phase8b_github_oauth.py` | github_id 컬럼 rename + github_login/access_token 추가 + webhook_secret/id 추가 |
```

**③ 환경변수 표 업데이트**:
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` 행 제거
- 아래 행으로 교체:
```
| `GITHUB_CLIENT_ID` | GitHub OAuth 앱 클라이언트 ID | `Ov23li...` | ✅ |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth 앱 클라이언트 시크릿 | `github_...` | ✅ |
```
- `GITHUB_TOKEN`, `GITHUB_WEBHOOK_SECRET`은 optional로 변경 설명 추가

**④ 알려진 주의사항 업데이트**:
- "Phase 8A 이후 로그인 필수" 항목에서 `GOOGLE_CLIENT_ID/SECRET` → `GITHUB_CLIENT_ID/SECRET`으로 변경
- 신규 주의사항 추가:
```
- **리포 추가 Webhook URL**: `POST /repos/add` 처리 시 `request.base_url`로 Webhook URL 자동 결정. Railway 배포 시 HTTPS URL이 자동으로 사용됨.
- **GitHub OAuth token**: `repo user:email` 스코프. 재로그인 시 토큰 자동 갱신. 100개 초과 리포는 첫 페이지(100개)만 표시.
```

**⑤ Phase 현황 표에 Phase 8B 추가**:
```
| Phase 8B | GitHub OAuth + 리포 추가 UI + Webhook 자동 생성 | ✅ 완료 (단위 ~183개) |
```

**⑥ 테스트 수 업데이트**: `164개` → 실제 통과 개수

- [ ] **Step 2: 커밋 + 푸시**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md Phase 8B 반영 — GitHub OAuth + 리포 추가 UI"
git push origin main
```

---

## 최종 검증

```bash
# 전체 단위 테스트
pytest tests/ -v

# 코드 품질
make lint

# 수동 E2E 검증 (로컬 .env에 GITHUB_CLIENT_ID/SECRET 설정 후)
make run
# 1. http://localhost:8000 접속 → /login 리다이렉트 확인
# 2. "GitHub로 로그인" 클릭 → GitHub OAuth 동의 → 대시보드 리다이렉트
# 3. /repos/add 접속 → 드롭다운에 GitHub 리포 목록 표시 확인
# 4. 리포 선택 → "Webhook 생성 + 리포 추가" 클릭 → /repos/{repo} 리다이렉트
# 5. GitHub 리포 Settings → Webhooks → SCAManager Webhook 자동 생성 확인
# 6. /auth/logout → /login 리다이렉트 확인
```
