# AI 분석 결과 GitHub Issue 등록 기능 — 구현 계획

> ⛔ **정책 18 (Claude ↔ Codex mutual 검증) 은 2026-07-10 폐기되었다** — 사용자가 Codex 구독을 해지해 `codex` 실행 파일이 없다.
> **본 문서에 남아 있는 "Codex 검증 의뢰 / Codex OK 후 push" 류 단계는 수행하지 않는다** (완료된 작업의 역사 기록).  ⛔ *(폐기 2026-07-10 — Codex 단계 수행 안 함)*
> 대체: Claude 단독 2-layer (정책 8 5+1 + `pipeline-reviewer` / opus whole-branch 적대 리뷰). push 전 게이트 = `pytest tests/unit` 전체 통과.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AI 분석 결과(AI 제안사항 + 정적 분석 이슈)를 사용자가 확인·편집해 GitHub Issue로 등록하고, 등록 이력과 GitHub 상태를 실시간 동기화하는 기능을 analysis_detail(Phase 1) + repo_detail(Phase 2)에 추가한다.

**Architecture:** DB에 `issue_registrations` 테이블을 신설해 등록 이력과 GitHub Issue 번호를 저장한다. 서버가 `issue_key`(SHA256 해시)로 중복을 판별하고, TTL 5분 캐시 기반으로 GitHub API에서 open/closed 상태를 동기화한다. 프론트엔드는 `fetch()`로 REST API를 호출하고, 모달에서 제목·본문·라벨을 편집한 후 생성한다.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, httpx(singleton), Jinja2, Vanilla JS(fetch + DOM), pytest-asyncio, unittest.mock

---

## 파일 맵

### Phase 1 — 신규 생성
| 파일 | 역할 |
|------|------|
| `src/models/issue_registration.py` | IssueRegistration ORM |
| `alembic/versions/0035_issue_registrations.py` | DB 마이그레이션 |
| `src/repositories/issue_registration_repo.py` | DB CRUD + 중복 조회 |
| `src/services/issue_registration_service.py` | 등록 로직 + 상태 동기화 |
| `src/api/issue_registration.py` | REST 라우터 |
| `tests/unit/models/test_issue_registration.py` | ORM 모델 테스트 |
| `tests/unit/repositories/test_issue_registration_repo.py` | 리포지토리 테스트 |
| `tests/unit/github_client/test_issues_create.py` | github_client 추가 함수 테스트 |
| `tests/unit/services/test_issue_registration_service.py` | 서비스 테스트 |
| `tests/unit/api/test_issue_registration_api.py` | API 테스트 |

### Phase 1 — 기존 수정
| 파일 | 변경 내용 |
|------|----------|
| `src/github_client/issues.py` | `create_issue()` + `get_issue_state()` 추가 |
| `src/main.py` | issue_registration 라우터 include |
| `src/templates/analysis_detail.html` | Issue 등록 패널 + 모달 추가 |

### Phase 2 — 추가 신규/수정
| 파일 | 변경 내용 |
|------|----------|
| `src/services/issue_registration_service.py` | `get_repo_issue_summary()` 추가 |
| `src/api/issue_registration.py` | `GET /repo-summary` 엔드포인트 추가 |
| `src/templates/repo_detail.html` | 반복 이슈 일괄 등록 패널 추가 |
| `tests/unit/services/test_issue_registration_service.py` | Phase 2 테스트 추가 |
| `tests/unit/api/test_issue_registration_api.py` | repo-summary 테스트 추가 |

---

## ─── PHASE 1: analysis_detail 개별 등록 ───

---

### Task 1: ORM 모델 + Alembic 마이그레이션

**Files:**
- Create: `src/models/issue_registration.py`
- Create: `alembic/versions/0035_issue_registrations.py`
- Create: `tests/unit/models/test_issue_registration.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/unit/models/test_issue_registration.py
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from src.database import Base
from src.models.issue_registration import IssueRegistration


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
    # analysis_id/repo_id FK 없는 SQLite 테스트 — FK enforce 없음
    rec = IssueRegistration(
        analysis_id=1, repo_id=1, issue_type="ai_suggestion",
        issue_key="abc", github_issue_number=42,
        created_at=datetime.now(timezone.utc),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    assert rec.github_issue_state == "open"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
make test-file f=tests/unit/models/test_issue_registration.py
```
Expected: `ImportError` (모듈 없음)

- [ ] **Step 3: ORM 모델 작성**

```python
# src/models/issue_registration.py
"""IssueRegistration ORM — AI 분석 결과 GitHub Issue 등록 이력.
IssueRegistration ORM — records of GitHub Issues created from AI analysis results.
"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint

from src.database import Base


# pylint: disable=too-few-public-methods
class IssueRegistration(Base):
    """분석 결과 항목별 GitHub Issue 등록 이력 — 중복 등록 방지 + 상태 동기화.
    Per-item GitHub Issue registration record — dedup guard + state sync.
    """

    __tablename__ = "issue_registrations"
    __table_args__ = (
        # 동일 리포 내 issue_key 중복 방지 — 리포 간 동일 이슈는 허용
        # Prevent duplicate issue_key within the same repo; allow same key across repos
        UniqueConstraint("repo_id", "issue_key", name="uq_issue_reg_repo_key"),
        Index("ix_issue_reg_analysis_id", "analysis_id"),
        Index("ix_issue_reg_repo_id", "repo_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(
        Integer, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False
    )
    repo_id = Column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    # "ai_suggestion" | "static_issue"
    issue_type = Column(String, nullable=False)
    # SHA256 해시 — AI: suggestion_text[:500] / 정적: tool:category:message[:200]
    # SHA256 hash — AI: suggestion_text[:500] / static: tool:category:message[:200]
    issue_key = Column(String(64), nullable=False)
    github_issue_number = Column(Integer, nullable=False)
    # "open" | "closed" — TTL 5분 캐시로 GitHub API 동기화
    # "open" | "closed" — synced from GitHub API with 5-minute TTL cache
    github_issue_state = Column(String, nullable=False, server_default="open")
    github_issue_synced_at = Column(DateTime, nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
make test-file f=tests/unit/models/test_issue_registration.py
```
Expected: 4 passed

- [ ] **Step 5: Alembic 마이그레이션 작성**

```python
# alembic/versions/0035_issue_registrations.py
"""issue_registrations 테이블 신설 — AI 분석 결과 GitHub Issue 등록 이력.
Create issue_registrations table for AI analysis result GitHub Issue registration history.

Revision ID: 0035
Revises: 0034
Create Date: 2026-05-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "issue_registrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("repo_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(), nullable=False),
        sa.Column("issue_key", sa.String(length=64), nullable=False),
        sa.Column("github_issue_number", sa.Integer(), nullable=False),
        sa.Column(
            "github_issue_state",
            sa.String(),
            nullable=False,
            server_default="open",
        ),
        sa.Column("github_issue_synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repo_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repo_id", "issue_key", name="uq_issue_reg_repo_key"),
    )
    op.create_index("ix_issue_reg_analysis_id", "issue_registrations", ["analysis_id"])
    op.create_index("ix_issue_reg_repo_id", "issue_registrations", ["repo_id"])


def downgrade() -> None:
    op.drop_index("ix_issue_reg_repo_id", table_name="issue_registrations")
    op.drop_index("ix_issue_reg_analysis_id", table_name="issue_registrations")
    op.drop_table("issue_registrations")
```

- [ ] **Step 6: 커밋**

```bash
git add src/models/issue_registration.py alembic/versions/0035_issue_registrations.py tests/unit/models/test_issue_registration.py
git commit -m "feat: IssueRegistration ORM + alembic 0035 마이그레이션"
```

---

### Task 2: Repository 레이어

**Files:**
- Create: `src/repositories/issue_registration_repo.py`
- Create: `tests/unit/repositories/test_issue_registration_repo.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
make test-file f=tests/unit/repositories/test_issue_registration_repo.py
```
Expected: `ImportError`

- [ ] **Step 3: 리포지토리 구현**

```python
# src/repositories/issue_registration_repo.py
"""issue_registration_repo — IssueRegistration CRUD + 중복 조회 단일 출처.
issue_registration_repo — single source for IssueRegistration CRUD and dedup lookup.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.models.issue_registration import IssueRegistration


def find_by_key(db: Session, *, repo_id: int, issue_key: str) -> IssueRegistration | None:
    """repo_id + issue_key 로 기존 등록 이력을 조회한다.
    Look up an existing registration by repo_id and issue_key.
    """
    return (
        db.query(IssueRegistration)
        .filter(
            IssueRegistration.repo_id == repo_id,
            IssueRegistration.issue_key == issue_key,
        )
        .first()
    )


def create(
    db: Session,
    *,
    analysis_id: int,
    repo_id: int,
    issue_type: str,
    issue_key: str,
    github_issue_number: int,
) -> IssueRegistration:
    """Issue 등록 이력을 INSERT하고 반환한다.
    Insert a new registration record and return it.
    """
    record = IssueRegistration(
        analysis_id=analysis_id,
        repo_id=repo_id,
        issue_type=issue_type,
        issue_key=issue_key,
        github_issue_number=github_issue_number,
        github_issue_state="open",
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_by_analysis(db: Session, *, analysis_id: int) -> list[IssueRegistration]:
    """특정 분석의 모든 등록 이력을 반환한다.
    Return all registrations for a given analysis.
    """
    return (
        db.query(IssueRegistration)
        .filter(IssueRegistration.analysis_id == analysis_id)
        .all()
    )


def list_by_repo(db: Session, *, repo_id: int) -> list[IssueRegistration]:
    """특정 리포의 모든 등록 이력을 최신순으로 반환한다.
    Return all registrations for a given repo, newest first.
    """
    return (
        db.query(IssueRegistration)
        .filter(IssueRegistration.repo_id == repo_id)
        .order_by(IssueRegistration.created_at.desc())
        .all()
    )


def update_state(db: Session, *, record: IssueRegistration, state: str) -> None:
    """GitHub Issue 상태와 동기화 시각을 갱신한다.
    Update the GitHub Issue state and sync timestamp.
    """
    record.github_issue_state = state
    record.github_issue_synced_at = datetime.now(timezone.utc)
    db.commit()
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
make test-file f=tests/unit/repositories/test_issue_registration_repo.py
```
Expected: 8 passed

- [ ] **Step 5: 커밋**

```bash
git add src/repositories/issue_registration_repo.py tests/unit/repositories/test_issue_registration_repo.py
git commit -m "feat: issue_registration_repo — CRUD + 중복 조회"
```

---

### Task 3: github_client/issues.py — create_issue + get_issue_state

**Files:**
- Modify: `src/github_client/issues.py`
- Create: `tests/unit/github_client/test_issues_create.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/unit/github_client/test_issues_create.py
from unittest.mock import AsyncMock, MagicMock
import pytest
from src.github_client.issues import create_issue, get_issue_state


def _mock_client(monkeypatch, json_data):
    """get_http_client() 싱글톤을 모킹한다.
    Mock the get_http_client() singleton.
    """
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock(return_value=None)
    mock_response.json.return_value = json_data
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.get = AsyncMock(return_value=mock_response)
    monkeypatch.setattr("src.github_client.issues.get_http_client", lambda: mock_client)
    return mock_client


@pytest.mark.asyncio
async def test_create_issue_returns_number_url_state(monkeypatch):
    _mock_client(monkeypatch, {
        "number": 44,
        "html_url": "https://github.com/owner/repo/issues/44",
        "state": "open",
    })
    result = await create_issue(
        "token", "owner/repo",
        title="Test", body="Body", labels=["bug"],
    )
    assert result["number"] == 44
    assert result["html_url"] == "https://github.com/owner/repo/issues/44"
    assert result["state"] == "open"


@pytest.mark.asyncio
async def test_create_issue_sends_correct_payload(monkeypatch):
    mock_client = _mock_client(monkeypatch, {
        "number": 1, "html_url": "https://github.com/o/r/issues/1", "state": "open"
    })
    await create_issue("token", "owner/repo", title="T", body="B", labels=["l1", "l2"])
    call_kwargs = mock_client.post.call_args.kwargs
    assert call_kwargs["json"] == {"title": "T", "body": "B", "labels": ["l1", "l2"]}


@pytest.mark.asyncio
async def test_get_issue_state_returns_open(monkeypatch):
    _mock_client(monkeypatch, {"state": "open"})
    state = await get_issue_state("token", "owner/repo", 44)
    assert state == "open"


@pytest.mark.asyncio
async def test_get_issue_state_returns_closed(monkeypatch):
    _mock_client(monkeypatch, {"state": "closed"})
    state = await get_issue_state("token", "owner/repo", 44)
    assert state == "closed"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
make test-file f=tests/unit/github_client/test_issues_create.py
```
Expected: `ImportError` (함수 없음)

- [ ] **Step 3: github_client/issues.py에 두 함수 추가**

```python
# src/github_client/issues.py 전체 교체
"""GitHub Issues API helpers."""
from src.constants import GITHUB_API
from src.github_client.helpers import github_api_headers
from src.shared.http_client import get_http_client


async def close_issue(
    token: str,
    repo_full_name: str,
    issue_number: int,
    state_reason: str = "completed",
) -> None:
    """Issue 를 closed 상태로 전환. 실패 시 httpx.HTTPStatusError 전파."""
    url = f"{GITHUB_API}/repos/{repo_full_name}/issues/{issue_number}"
    client = get_http_client()
    resp = await client.patch(
        url,
        json={"state": "closed", "state_reason": state_reason},
        headers=github_api_headers(token),
    )
    resp.raise_for_status()


async def create_issue(
    token: str,
    repo_full_name: str,
    *,
    title: str,
    body: str,
    labels: list[str],
) -> dict:
    """GitHub Issue 를 생성하고 number·html_url·state 를 반환한다.
    Create a GitHub Issue and return its number, html_url, and state.
    """
    url = f"{GITHUB_API}/repos/{repo_full_name}/issues"
    client = get_http_client()
    resp = await client.post(
        url,
        json={"title": title, "body": body, "labels": labels},
        headers=github_api_headers(token),
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "number": data["number"],
        "html_url": data["html_url"],
        "state": data["state"],
    }


async def get_issue_state(
    token: str,
    repo_full_name: str,
    issue_number: int,
) -> str:
    """GitHub Issue 현재 상태("open" | "closed")를 반환한다.
    Return the current state ("open" | "closed") of a GitHub Issue.
    """
    url = f"{GITHUB_API}/repos/{repo_full_name}/issues/{issue_number}"
    client = get_http_client()
    resp = await client.get(url, headers=github_api_headers(token))
    resp.raise_for_status()
    return resp.json()["state"]
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
make test-file f=tests/unit/github_client/test_issues_create.py
```
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add src/github_client/issues.py tests/unit/github_client/test_issues_create.py
git commit -m "feat: github_client — create_issue + get_issue_state 추가"
```

---

### Task 4: 서비스 레이어

**Files:**
- Create: `src/services/issue_registration_service.py`
- Create: `tests/unit/services/test_issue_registration_service.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/unit/services/test_issue_registration_service.py
import hashlib
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database import Base
from src.services.issue_registration_service import (
    make_ai_issue_key,
    make_static_issue_key,
    register_issue,
    get_analysis_issue_status,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


# ── key helpers ──

def test_make_ai_issue_key_is_64_chars():
    key = make_ai_issue_key("some suggestion text")
    assert len(key) == 64


def test_make_ai_issue_key_deterministic():
    assert make_ai_issue_key("text") == make_ai_issue_key("text")


def test_make_static_issue_key_excludes_line():
    k1 = make_static_issue_key("bandit", "security", "SQL injection")
    k2 = make_static_issue_key("bandit", "security", "SQL injection")
    assert k1 == k2


def test_make_static_issue_key_differs_by_tool():
    k1 = make_static_issue_key("bandit", "security", "msg")
    k2 = make_static_issue_key("pylint", "security", "msg")
    assert k1 != k2


# ── register_issue ──

@pytest.mark.asyncio
async def test_register_issue_success(db):
    with patch(
        "src.services.issue_registration_service.create_issue",
        new=AsyncMock(return_value={
            "number": 44,
            "html_url": "https://github.com/o/r/issues/44",
            "state": "open",
        }),
    ):
        result = await register_issue(
            db,
            analysis_id=1, repo_id=1,
            repo_full_name="owner/repo",
            github_token="tok",
            issue_type="ai_suggestion",
            issue_key="abc123",
            title="T", body="B", labels=["bug"],
        )
    assert result["github_issue_number"] == 44
    assert result["state"] == "open"


@pytest.mark.asyncio
async def test_register_issue_duplicate_raises_value_error(db):
    with patch(
        "src.services.issue_registration_service.create_issue",
        new=AsyncMock(return_value={
            "number": 44, "html_url": "https://github.com/o/r/issues/44", "state": "open"
        }),
    ):
        await register_issue(
            db, analysis_id=1, repo_id=1, repo_full_name="o/r",
            github_token="tok", issue_type="ai_suggestion", issue_key="dup",
            title="T", body="B", labels=[],
        )

    with pytest.raises(ValueError, match="DUPLICATE:44"):
        with patch(
            "src.services.issue_registration_service.create_issue",
            new=AsyncMock(return_value={
                "number": 99, "html_url": "https://github.com/o/r/issues/99", "state": "open"
            }),
        ):
            await register_issue(
                db, analysis_id=1, repo_id=1, repo_full_name="o/r",
                github_token="tok", issue_type="ai_suggestion", issue_key="dup",
                title="T", body="B", labels=[],
            )


# ── get_analysis_issue_status ──

@pytest.mark.asyncio
async def test_get_analysis_issue_status_empty(db):
    result = await get_analysis_issue_status(
        db, analysis_id=99, repo_full_name="o/r", github_token="tok"
    )
    assert result == []


@pytest.mark.asyncio
async def test_get_analysis_issue_status_syncs_stale(db):
    from src.repositories import issue_registration_repo
    rec = issue_registration_repo.create(
        db, analysis_id=1, repo_id=1, issue_type="ai_suggestion",
        issue_key="k1", github_issue_number=44,
    )
    # synced_at이 None이므로 stale — GitHub API 호출 기대
    with patch(
        "src.services.issue_registration_service.get_issue_state",
        new=AsyncMock(return_value="closed"),
    ):
        result = await get_analysis_issue_status(
            db, analysis_id=1, repo_full_name="o/r", github_token="tok"
        )
    assert result[0]["github_issue_state"] == "closed"
    assert result[0]["github_issue_number"] == 44


@pytest.mark.asyncio
async def test_get_analysis_issue_status_skips_fresh_sync(db):
    from src.repositories import issue_registration_repo
    rec = issue_registration_repo.create(
        db, analysis_id=1, repo_id=1, issue_type="ai_suggestion",
        issue_key="k2", github_issue_number=55,
    )
    # 방금 동기화된 것처럼 synced_at 설정
    # Set synced_at as if just synced
    issue_registration_repo.update_state(db, record=rec, state="open")

    with patch(
        "src.services.issue_registration_service.get_issue_state",
        new=AsyncMock(side_effect=Exception("should not be called")),
    ):
        result = await get_analysis_issue_status(
            db, analysis_id=1, repo_full_name="o/r", github_token="tok"
        )
    assert result[0]["github_issue_state"] == "open"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
make test-file f=tests/unit/services/test_issue_registration_service.py
```
Expected: `ImportError`

- [ ] **Step 3: 서비스 구현**

```python
# src/services/issue_registration_service.py
"""issue_registration_service — Issue 등록 + GitHub 상태 동기화 로직.
issue_registration_service — Issue registration and GitHub state sync logic.
"""
import hashlib
from datetime import datetime, timezone, timedelta

import httpx
from sqlalchemy.orm import Session

from src.github_client.issues import create_issue, get_issue_state
from src.repositories import issue_registration_repo

# GitHub 상태 캐시 TTL (초) — 만료 시 재조회
# GitHub state cache TTL in seconds — refresh after expiry
_SYNC_TTL_SECONDS = 300


def make_ai_issue_key(suggestion_text: str) -> str:
    """AI 제안사항 중복 판별 키 생성 — suggestion_text[:500] SHA256.
    Generate dedup key for AI suggestions — SHA256 of first 500 chars.
    """
    return hashlib.sha256(suggestion_text[:500].encode()).hexdigest()[:64]


def make_static_issue_key(tool: str, category: str, message: str) -> str:
    """정적 분석 이슈 중복 판별 키 생성 — 라인 번호 제외 (커밋 간 drift 방지).
    Generate dedup key for static issues — excludes line number to prevent cross-commit drift.
    """
    content = f"{tool}:{category}:{message[:200]}"
    return hashlib.sha256(content.encode()).hexdigest()[:64]


async def register_issue(
    db: Session,
    *,
    analysis_id: int,
    repo_id: int,
    repo_full_name: str,
    github_token: str,
    issue_type: str,
    issue_key: str,
    title: str,
    body: str,
    labels: list[str],
) -> dict:
    """Issue를 등록한다. 중복이면 ValueError("DUPLICATE:<number>") 발생.
    Register an Issue. Raises ValueError("DUPLICATE:<number>") on duplicate.
    """
    existing = issue_registration_repo.find_by_key(db, repo_id=repo_id, issue_key=issue_key)
    if existing:
        raise ValueError(f"DUPLICATE:{existing.github_issue_number}")

    gh_result = await create_issue(
        github_token,
        repo_full_name,
        title=title,
        body=body,
        labels=labels,
    )
    record = issue_registration_repo.create(
        db,
        analysis_id=analysis_id,
        repo_id=repo_id,
        issue_type=issue_type,
        issue_key=issue_key,
        github_issue_number=gh_result["number"],
    )
    return {
        "github_issue_number": record.github_issue_number,
        "github_issue_url": gh_result["html_url"],
        "state": "open",
    }


async def get_analysis_issue_status(
    db: Session,
    *,
    analysis_id: int,
    repo_full_name: str,
    github_token: str,
) -> list[dict]:
    """analysis_detail용 등록 이력 + TTL 만료 항목 GitHub 상태 동기화.
    Return registration records for analysis_detail; sync stale GitHub states.
    """
    records = issue_registration_repo.list_by_analysis(db, analysis_id=analysis_id)
    now = datetime.now(timezone.utc)
    result = []
    for rec in records:
        stale = (
            rec.github_issue_synced_at is None
            or (now - rec.github_issue_synced_at).total_seconds() > _SYNC_TTL_SECONDS
        )
        if stale:
            try:
                state = await get_issue_state(
                    github_token, repo_full_name, rec.github_issue_number
                )
                issue_registration_repo.update_state(db, record=rec, state=state)
            except httpx.HTTPError:
                # 동기화 실패 시 기존 상태 유지 — 사용자에게 오류 미노출
                # Keep existing state on sync failure — silent fallback
                pass
        result.append({
            "issue_key": rec.issue_key,
            "github_issue_number": rec.github_issue_number,
            "github_issue_state": rec.github_issue_state,
            "github_issue_url": (
                f"https://github.com/{repo_full_name}/issues/{rec.github_issue_number}"
            ),
        })
    return result
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
make test-file f=tests/unit/services/test_issue_registration_service.py
```
Expected: 9 passed

- [ ] **Step 5: 커밋**

```bash
git add src/services/issue_registration_service.py tests/unit/services/test_issue_registration_service.py
git commit -m "feat: issue_registration_service — 등록 + 상태 동기화"
```

---

### Task 5: REST API 라우터 (Phase 1)

**Files:**
- Create: `src/api/issue_registration.py`
- Create: `tests/unit/api/test_issue_registration_api.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/unit/api/test_issue_registration_api.py
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.auth.session import CurrentUser


def _mock_user():
    return CurrentUser(
        id=1, github_login="user", email="u@example.com",
        display_name="User", plaintext_token="ghp_test",
    )


@pytest.fixture
def client():
    return TestClient(app)


def _mock_analysis(repo_id=1):
    m = MagicMock()
    m.id = 10
    m.repo_id = repo_id
    return m


def _mock_repo(full_name="owner/repo", user_id=1):
    m = MagicMock()
    m.id = 1
    m.full_name = full_name
    m.user_id = user_id
    return m


# ── POST /api/issues/register ──

def test_register_returns_401_when_not_logged_in(client):
    resp = client.post("/api/issues/register", json={
        "analysis_id": 1, "issue_type": "ai_suggestion",
        "suggestion_text": "text", "title": "T", "body": "B", "labels": [],
    })
    assert resp.status_code == 401


def test_register_returns_201_on_success(client):
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration._get_analysis_and_repo",
              return_value=(_mock_analysis(), _mock_repo())),
        patch("src.api.issue_registration.register_issue",
              new=AsyncMock(return_value={
                  "github_issue_number": 44,
                  "github_issue_url": "https://github.com/owner/repo/issues/44",
                  "state": "open",
              })),
    ):
        resp = client.post("/api/issues/register", json={
            "analysis_id": 10, "issue_type": "ai_suggestion",
            "suggestion_text": "cache TTL", "title": "T", "body": "B", "labels": ["bug"],
        })
    assert resp.status_code == 201
    assert resp.json()["github_issue_number"] == 44


def test_register_returns_409_on_duplicate(client):
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration._get_analysis_and_repo",
              return_value=(_mock_analysis(), _mock_repo())),
        patch("src.api.issue_registration.register_issue",
              new=AsyncMock(side_effect=ValueError("DUPLICATE:38"))),
    ):
        resp = client.post("/api/issues/register", json={
            "analysis_id": 10, "issue_type": "ai_suggestion",
            "suggestion_text": "text", "title": "T", "body": "B", "labels": [],
        })
    assert resp.status_code == 409
    assert "38" in resp.json()["detail"]


def test_register_returns_403_on_permission_error(client):
    import httpx
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration._get_analysis_and_repo",
              return_value=(_mock_analysis(), _mock_repo())),
        patch("src.api.issue_registration.register_issue",
              new=AsyncMock(side_effect=httpx.HTTPStatusError(
                  "403", request=MagicMock(),
                  response=MagicMock(status_code=403)))),
    ):
        resp = client.post("/api/issues/register", json={
            "analysis_id": 10, "issue_type": "ai_suggestion",
            "suggestion_text": "t", "title": "T", "body": "B", "labels": [],
        })
    assert resp.status_code == 403


# ── GET /api/issues/status ──

def test_status_returns_401_when_not_logged_in(client):
    resp = client.get("/api/issues/status?analysis_id=1")
    assert resp.status_code == 401


def test_status_returns_registrations(client):
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration._get_analysis_and_repo",
              return_value=(_mock_analysis(), _mock_repo())),
        patch("src.api.issue_registration.get_analysis_issue_status",
              new=AsyncMock(return_value=[
                  {"issue_key": "k1", "github_issue_number": 44,
                   "github_issue_state": "open",
                   "github_issue_url": "https://github.com/owner/repo/issues/44"},
              ])),
    ):
        resp = client.get("/api/issues/status?analysis_id=10")
    assert resp.status_code == 200
    assert len(resp.json()["registrations"]) == 1
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
make test-file f=tests/unit/api/test_issue_registration_api.py
```
Expected: `ImportError` 또는 404

- [ ] **Step 3: API 라우터 구현**

```python
# src/api/issue_registration.py
"""issue_registration API — GitHub Issue 등록 + 상태 조회 엔드포인트.
issue_registration API — endpoints for registering GitHub Issues and querying state.
"""
import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.auth.session import get_current_user
from src.database import SessionLocal
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.services.issue_registration_service import (
    get_analysis_issue_status,
    make_ai_issue_key,
    make_static_issue_key,
    register_issue,
)

router = APIRouter(prefix="/api/issues")


class RegisterRequest(BaseModel):
    analysis_id: int
    issue_type: str  # "ai_suggestion" | "static_issue"
    # AI 제안사항용 — issue_key 서버 생성에 사용
    # For AI suggestions — used to generate issue_key server-side
    suggestion_text: str | None = None
    # 정적 분석 이슈용 — issue_key 서버 생성에 사용
    # For static issues — used to generate issue_key server-side
    tool: str | None = None
    category: str | None = None
    message: str | None = None
    title: str
    body: str
    labels: list[str]


def _get_analysis_and_repo(db: Session, analysis_id: int) -> tuple:
    """analysis_id로 Analysis + Repository를 조회한다. 없으면 404 raise.
    Look up Analysis and Repository by analysis_id. Raises 404 if not found.
    """
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    repo = db.query(Repository).filter(Repository.id == analysis.repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return analysis, repo


def _make_issue_key(req: RegisterRequest) -> str:
    """요청에서 issue_key를 생성한다.
    Generate issue_key from the request payload.
    """
    if req.issue_type == "ai_suggestion":
        text = req.suggestion_text or req.title
        return make_ai_issue_key(text)
    tool = req.tool or ""
    category = req.category or ""
    message = req.message or req.title
    return make_static_issue_key(tool, category, message)


@router.post("/register", status_code=201)
async def register(request: Request, req: RegisterRequest):
    """AI 분석 이슈를 GitHub Issue로 등록한다.
    Register an AI analysis issue as a GitHub Issue.
    """
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required")

    issue_key = _make_issue_key(req)

    with SessionLocal() as db:
        analysis, repo = _get_analysis_and_repo(db, req.analysis_id)
        try:
            result = await register_issue(
                db,
                analysis_id=req.analysis_id,
                repo_id=repo.id,
                repo_full_name=repo.full_name,
                github_token=current_user.plaintext_token,
                issue_type=req.issue_type,
                issue_key=issue_key,
                title=req.title,
                body=req.body,
                labels=req.labels,
            )
        except ValueError as exc:
            # "DUPLICATE:<number>" 형식
            # "DUPLICATE:<number>" format
            if str(exc).startswith("DUPLICATE:"):
                issue_num = str(exc).split(":")[1]
                raise HTTPException(
                    status_code=409,
                    detail=f"이미 등록된 이슈입니다 (#{issue_num})",
                ) from exc
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                raise HTTPException(
                    status_code=403,
                    detail="Issues 쓰기 권한이 없습니다. GitHub 토큰을 확인해 주세요.",
                ) from exc
            raise HTTPException(status_code=502, detail="GitHub API 오류") from exc

    return result


@router.get("/status")
async def get_status(request: Request, analysis_id: int):
    """analysis_detail용 등록 이력 + GitHub 상태 동기화 결과를 반환한다.
    Return registration history and synced GitHub state for analysis_detail.
    """
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required")

    with SessionLocal() as db:
        analysis, repo = _get_analysis_and_repo(db, analysis_id)
        statuses = await get_analysis_issue_status(
            db,
            analysis_id=analysis_id,
            repo_full_name=repo.full_name,
            github_token=current_user.plaintext_token,
        )

    return {"registrations": statuses}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
make test-file f=tests/unit/api/test_issue_registration_api.py
```
Expected: 7 passed

- [ ] **Step 5: 커밋**

```bash
git add src/api/issue_registration.py tests/unit/api/test_issue_registration_api.py
git commit -m "feat: issue_registration API — POST /register + GET /status"
```

---

### Task 6: main.py 라우터 등록

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: 라우터 등록 위치 확인**

```bash
grep -n "include_router" src/main.py
```

- [ ] **Step 2: 라우터 import + include 추가**

`src/main.py`의 기존 `include_router` 블록 아래에 추가:

```python
from src.api.issue_registration import router as issue_registration_router
# ... 기존 라우터들 아래에 추가
app.include_router(issue_registration_router)
```

- [ ] **Step 3: 회귀 가드 테스트 — 엔드포인트 존재 확인**

```python
# tests/unit/test_main.py에 아래 테스트 추가
def test_issue_registration_endpoints_exist(client):
    # 미인증 시 401 (404가 아닌 것이 확인 포인트)
    resp = client.post("/api/issues/register", json={})
    assert resp.status_code != 404
    resp = client.get("/api/issues/status?analysis_id=1")
    assert resp.status_code != 404
```

- [ ] **Step 4: 기존 테스트 전체 통과 확인**

```bash
make test-fast
```
Expected: 모두 passed (새 테스트 포함)

- [ ] **Step 5: 커밋**

```bash
git add src/main.py tests/unit/test_main.py
git commit -m "feat: main.py — issue_registration 라우터 등록"
```

---

### Task 7: analysis_detail.html — Issue 등록 패널 + 모달

**Files:**
- Modify: `src/templates/analysis_detail.html`

> **Note:** 이 Task는 UI/시각 변경을 포함한다. 정책 11 — 4-테마 × 모바일/데스크탑 8 조합 시각 확인 필요.

- [ ] **Step 1: 현재 analysis_detail.html 하단 구조 파악**

```bash
grep -n "{% block\|</body>\|</main>\|score\|grade" src/templates/analysis_detail.html | tail -20
```

- [ ] **Step 2: analysis_detail 라우트에서 등록 상태 패싱 확인**

`src/api/` 또는 `src/ui/` 에서 `analysis_detail` 라우트를 찾아 `analysis.result` 가 템플릿에 전달되는지 확인:

```bash
grep -rn "analysis_detail" src/ --include="*.py"
```

- [ ] **Step 3: Issue 등록 패널 + 모달 추가**

`analysis_detail.html`의 `</main>` 또는 기존 콘텐츠 블록 마지막에 아래 섹션을 추가한다.

```html
{# ─── GitHub Issue 등록 패널 (신규) ─── #}
<section class="issue-reg-panel" id="issueRegPanel"
         data-analysis-id="{{ analysis.id }}"
         data-ai-suggestions="{{ analysis.result.ai_suggestions | tojson }}"
         data-static-issues="{{ analysis.result.issues | tojson }}">

  <h3 class="panel-title">📋 GitHub Issue 등록</h3>

  {# 탭 #}
  <div class="issue-reg-tabs" role="tablist">
    <button class="issue-tab active" data-tab="ai" role="tab">
      💡 AI 제안사항 <span class="issue-tab-count" id="aiCount"></span>
    </button>
    <button class="issue-tab" data-tab="static" role="tab">
      🔴 정적 분석 이슈 <span class="issue-tab-count" id="staticCount"></span>
    </button>
  </div>

  {# AI 제안 목록 #}
  <div class="issue-tab-panel" id="tabAi">
    <ul class="issue-list" id="aiIssueList"></ul>
  </div>

  {# 정적 분석 이슈 목록 #}
  <div class="issue-tab-panel hidden" id="tabStatic">
    <ul class="issue-list" id="staticIssueList"></ul>
  </div>
</section>

{# ─── 편집 모달 ─── #}
<div class="issue-modal-overlay hidden" id="issueModalOverlay" role="dialog" aria-modal="true">
  <div class="issue-modal">
    <h4 class="issue-modal-title">📝 GitHub Issue 생성</h4>

    <label class="issue-modal-label">제목
      <input type="text" id="issueTitle" class="issue-modal-input">
    </label>

    <label class="issue-modal-label">본문
      <textarea id="issueBody" class="issue-modal-textarea" rows="6"></textarea>
    </label>

    <label class="issue-modal-label">라벨 (쉼표 구분)
      <input type="text" id="issueLabels" class="issue-modal-input"
             placeholder="bug, enhancement">
    </label>

    <div class="issue-modal-actions">
      <button type="button" class="btn-secondary" id="issueModalCancel">취소</button>
      <button type="button" class="btn-primary" id="issueModalSubmit">
        GitHub에 Issue 생성 →
      </button>
    </div>
    <p class="issue-modal-error hidden" id="issueModalError"></p>
  </div>
</div>

{# ─── 성공 토스트 ─── #}
<div class="issue-toast hidden" id="issueToast"></div>

<script>
(function _initIssueReg() {
  const panel     = document.getElementById('issueRegPanel');
  if (!panel) return;

  const analysisId    = Number(panel.dataset.analysisId);
  const aiSuggestions = JSON.parse(panel.dataset.aiSuggestions || '[]');
  const staticIssues  = JSON.parse(panel.dataset.staticIssues  || '[]');

  // ── 상태 로드 ──
  const stateMap = {}; // issue_key → {number, state, url}

  async function loadStatus() {
    try {
      const r = await fetch(`/api/issues/status?analysis_id=${analysisId}`);
      if (!r.ok) return;
      const data = await r.json();
      data.registrations.forEach(reg => {
        stateMap[reg.issue_key] = reg;
      });
      renderAll();
    } catch (_) { /* 상태 로드 실패 시 조용히 무시 */ }
  }

  // ── 렌더링 ──
  function renderAll() {
    renderList('aiIssueList', 'aiCount', aiSuggestions.map(buildAiItem));
    renderList('staticIssueList', 'staticCount', staticIssues.map(buildStaticItem));
  }

  function buildAiItem(text, idx) {
    return { key: _aiKey(text), label: text, type: 'ai_suggestion',
             suggestionText: text, title: `💡 [AI 제안] ${text.slice(0,60)}` };
  }

  function buildStaticItem(issue) {
    return {
      key: _staticKey(issue.tool, issue.category, issue.message),
      label: `${issue.tool} — ${issue.message}`,
      type: 'static_issue',
      tool: issue.tool, category: issue.category, message: issue.message,
      title: `🔴 [${issue.category}] ${issue.tool}: ${issue.message.slice(0,50)}`,
    };
  }

  function renderList(listId, countId, items) {
    const ul = document.getElementById(listId);
    const countEl = document.getElementById(countId);
    ul.innerHTML = '';
    if (countEl) countEl.textContent = `(${items.length})`;
    items.forEach(item => ul.appendChild(buildRow(item)));
  }

  function buildRow(item) {
    const li = document.createElement('li');
    li.className = 'issue-row';
    const label = document.createElement('span');
    label.className = 'issue-row-label';
    label.textContent = item.label;
    li.appendChild(label);

    const reg = stateMap[item.key];
    if (reg) {
      const badge = document.createElement('a');
      badge.href = reg.github_issue_url;
      badge.target = '_blank';
      badge.rel = 'noopener noreferrer';
      badge.className = reg.github_issue_state === 'closed'
        ? 'issue-badge issue-badge--closed'
        : 'issue-badge issue-badge--open';
      badge.textContent = reg.github_issue_state === 'closed'
        ? `✅ #${reg.github_issue_number} 해결됨`
        : `🔵 #${reg.github_issue_number} 진행중`;
      li.appendChild(badge);
    } else {
      const btn = document.createElement('button');
      btn.className = 'btn-register';
      btn.textContent = 'Issue 등록';
      btn.addEventListener('click', () => openModal(item));
      li.appendChild(btn);
    }
    return li;
  }

  // ── 탭 전환 ──
  document.querySelectorAll('.issue-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.issue-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.issue-tab-panel').forEach(p => p.classList.add('hidden'));
      tab.classList.add('active');
      document.getElementById(tab.dataset.tab === 'ai' ? 'tabAi' : 'tabStatic')
              .classList.remove('hidden');
    });
  });

  // ── 모달 ──
  let _currentItem = null;

  function openModal(item) {
    _currentItem = item;
    document.getElementById('issueTitle').value = item.title;
    document.getElementById('issueBody').value = _defaultBody(item);
    document.getElementById('issueLabels').value =
      item.type === 'ai_suggestion' ? 'ai-suggestion, enhancement' : `${item.category || 'bug'}`;
    document.getElementById('issueModalError').classList.add('hidden');
    document.getElementById('issueModalOverlay').classList.remove('hidden');
    document.getElementById('issueTitle').focus();
  }

  function closeModal() {
    document.getElementById('issueModalOverlay').classList.add('hidden');
    _currentItem = null;
  }

  function _defaultBody(item) {
    const sha = panel.dataset.analysisId;
    if (item.type === 'ai_suggestion') {
      return `## 📌 분석 정보\n분석 ID: ${analysisId}\n\n## 💡 AI 제안 내용\n${item.suggestionText}\n\n---\n*SCAManager AI 분석 결과에서 생성됨*`;
    }
    return `## 📌 분석 정보\n분석 ID: ${analysisId}\n\n## 🔴 이슈 내용\n- 도구: ${item.tool}\n- 카테고리: ${item.category}\n- 메시지: ${item.message}\n\n---\n*SCAManager 정적 분석 결과에서 생성됨*`;
  }

  document.getElementById('issueModalCancel').addEventListener('click', closeModal);
  document.getElementById('issueModalOverlay').addEventListener('click', e => {
    if (e.target === document.getElementById('issueModalOverlay')) closeModal();
  });

  document.getElementById('issueModalSubmit').addEventListener('click', async () => {
    if (!_currentItem) return;
    const btn = document.getElementById('issueModalSubmit');
    btn.disabled = true;
    btn.textContent = '생성 중...';

    const payload = {
      analysis_id: analysisId,
      issue_type: _currentItem.type,
      suggestion_text: _currentItem.suggestionText || null,
      tool: _currentItem.tool || null,
      category: _currentItem.category || null,
      message: _currentItem.message || null,
      title: document.getElementById('issueTitle').value.trim(),
      body: document.getElementById('issueBody').value,
      labels: document.getElementById('issueLabels').value
              .split(',').map(s => s.trim()).filter(Boolean),
    };

    try {
      const r = await fetch('/api/issues/register', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
      });
      const data = await r.json();
      if (!r.ok) {
        const errEl = document.getElementById('issueModalError');
        errEl.textContent = data.detail || '오류가 발생했습니다.';
        errEl.classList.remove('hidden');
        btn.disabled = false;
        btn.textContent = 'GitHub에 Issue 생성 →';
        return;
      }
      // 성공 — 상태 맵 갱신 후 목록 다시 렌더링
      stateMap[_currentItem.key] = {
        github_issue_number: data.github_issue_number,
        github_issue_state: 'open',
        github_issue_url: data.github_issue_url,
      };
      closeModal();
      renderAll();
      showToast(`✅ Issue #${data.github_issue_number} 생성됨 — <a href="${data.github_issue_url}" target="_blank" rel="noopener noreferrer">GitHub에서 보기 →</a>`);
    } catch (_) {
      const errEl = document.getElementById('issueModalError');
      errEl.textContent = '네트워크 오류가 발생했습니다. 다시 시도해 주세요.';
      errEl.classList.remove('hidden');
      btn.disabled = false;
      btn.textContent = 'GitHub에 Issue 생성 →';
    }
  });

  // ── 토스트 ──
  function showToast(html) {
    const toast = document.getElementById('issueToast');
    toast.innerHTML = html;
    toast.classList.remove('hidden');
    setTimeout(() => toast.classList.add('hidden'), 5000);
  }

  // ── issue_key 생성 (서버와 동일 로직 불필요 — 서버가 생성) ──
  // 클라이언트는 고유 식별자로만 사용하므로 단순 인덱스 기반
  // Client uses a simple index-based key — server generates the real SHA256 key
  function _aiKey(text) { return 'ai:' + text.slice(0, 50); }
  function _staticKey(tool, cat, msg) { return `st:${tool}:${cat}:${(msg||'').slice(0,40)}`; }

  // ── 초기화 ──
  loadStatus().then(renderAll);
})();
</script>
```

> **Note:** `_aiKey` / `_staticKey` 는 클라이언트 측 UI 상태 매핑용(렌더링 목적)이다. 실제 중복 판별 `issue_key` 는 서버(`make_ai_issue_key` / `make_static_issue_key`)가 생성하며, 페이지 로드 시 `GET /api/issues/status` 응답의 `issue_key` 필드와 직접 비교한다. 클라이언트 측 UI 매핑 오류 시 뱃지가 보이지 않을 수 있으나 중복 등록 자체는 서버에서 409로 차단된다.

- [ ] **Step 4: E2E 회귀 가드 테스트 추가**

```python
# e2e/test_issue_registration.py
import pytest


@pytest.mark.asyncio
async def test_issue_reg_panel_exists_on_analysis_detail(page, live_server, seeded_analysis):
    """analysis_detail 페이지에 Issue 등록 패널이 존재한다."""
    await page.goto(f"{live_server}/analyses/{seeded_analysis.id}")
    panel = page.locator("#issueRegPanel")
    await panel.wait_for(state="visible", timeout=5000)
    assert await panel.is_visible()


@pytest.mark.asyncio
async def test_issue_reg_tabs_switch(page, live_server, seeded_analysis):
    """AI 제안사항 / 정적 분석 이슈 탭 전환이 동작한다."""
    await page.goto(f"{live_server}/analyses/{seeded_analysis.id}")
    await page.locator(".issue-tab[data-tab='static']").click()
    assert await page.locator("#tabStatic").is_visible()
    assert not await page.locator("#tabAi").is_visible()
```

- [ ] **Step 5: lint 통과 확인**

```bash
make lint
```

- [ ] **Step 6: 커밋**

```bash
git add src/templates/analysis_detail.html e2e/test_issue_registration.py
git commit -m "feat(ui): analysis_detail Issue 등록 패널 + 편집 모달"
```

---

## ─── PHASE 2: repo_detail 반복 이슈 일괄 등록 ───

---

### Task 8: 서비스 — repo 반복 이슈 요약 + 일괄 동기화

**Files:**
- Modify: `src/services/issue_registration_service.py`
- Modify: `tests/unit/services/test_issue_registration_service.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
# tests/unit/services/test_issue_registration_service.py 에 추가
from src.services.issue_registration_service import get_repo_issue_summary


@pytest.mark.asyncio
async def test_get_repo_issue_summary_empty(db):
    result = await get_repo_issue_summary(
        db, repo_id=99, repo_full_name="o/r", github_token="tok"
    )
    assert result == []


@pytest.mark.asyncio
async def test_get_repo_issue_summary_returns_with_registration_state(db):
    from src.repositories import issue_registration_repo
    issue_registration_repo.create(
        db, analysis_id=1, repo_id=1, issue_type="static_issue",
        issue_key="sk1", github_issue_number=55,
    )
    with patch(
        "src.services.issue_registration_service.get_issue_state",
        new=AsyncMock(return_value="open"),
    ):
        result = await get_repo_issue_summary(
            db, repo_id=1, repo_full_name="o/r", github_token="tok"
        )
    assert len(result) == 1
    assert result[0]["github_issue_number"] == 55
    assert result[0]["github_issue_state"] == "open"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
make test-file f=tests/unit/services/test_issue_registration_service.py
```
Expected: `ImportError` (`get_repo_issue_summary` 없음)

- [ ] **Step 3: get_repo_issue_summary 추가**

`src/services/issue_registration_service.py` 하단에 추가:

```python
async def get_repo_issue_summary(
    db: Session,
    *,
    repo_id: int,
    repo_full_name: str,
    github_token: str,
) -> list[dict]:
    """repo_detail용 등록 이력 + TTL 만료 항목 일괄 GitHub 상태 동기화.
    Return all repo registrations for repo_detail; bulk-sync stale GitHub states.
    """
    records = issue_registration_repo.list_by_repo(db, repo_id=repo_id)
    now = datetime.now(timezone.utc)
    result = []
    for rec in records:
        stale = (
            rec.github_issue_synced_at is None
            or (now - rec.github_issue_synced_at).total_seconds() > _SYNC_TTL_SECONDS
        )
        if stale:
            try:
                state = await get_issue_state(
                    github_token, repo_full_name, rec.github_issue_number
                )
                issue_registration_repo.update_state(db, record=rec, state=state)
            except httpx.HTTPError:
                pass
        result.append({
            "issue_key": rec.issue_key,
            "issue_type": rec.issue_type,
            "github_issue_number": rec.github_issue_number,
            "github_issue_state": rec.github_issue_state,
            "github_issue_url": (
                f"https://github.com/{repo_full_name}/issues/{rec.github_issue_number}"
            ),
            "created_at": rec.created_at.isoformat() if rec.created_at else None,
        })
    return result
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
make test-file f=tests/unit/services/test_issue_registration_service.py
```
Expected: 전체 passed

- [ ] **Step 5: 커밋**

```bash
git add src/services/issue_registration_service.py tests/unit/services/test_issue_registration_service.py
git commit -m "feat: issue_registration_service — get_repo_issue_summary 추가"
```

---

### Task 9: API — GET /repo-summary 엔드포인트

**Files:**
- Modify: `src/api/issue_registration.py`
- Modify: `tests/unit/api/test_issue_registration_api.py`

- [ ] **Step 1: 실패 테스트 추가**

```python
# tests/unit/api/test_issue_registration_api.py 에 추가
from src.services.issue_registration_service import get_repo_issue_summary


def test_repo_summary_returns_401_when_not_logged_in(client):
    resp = client.get("/api/issues/repo-summary?repo_id=1")
    assert resp.status_code == 401


def test_repo_summary_returns_registrations(client):
    mock_repo = _mock_repo()
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration._get_repo_or_404", return_value=mock_repo),
        patch("src.api.issue_registration.get_repo_issue_summary",
              new=AsyncMock(return_value=[
                  {"issue_key": "k1", "issue_type": "static_issue",
                   "github_issue_number": 55, "github_issue_state": "open",
                   "github_issue_url": "https://github.com/owner/repo/issues/55",
                   "created_at": "2026-05-24T00:00:00"},
              ])),
    ):
        resp = client.get("/api/issues/repo-summary?repo_id=1")
    assert resp.status_code == 200
    assert len(resp.json()["registrations"]) == 1
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
make test-file f=tests/unit/api/test_issue_registration_api.py
```
Expected: 실패 (`repo-summary` 엔드포인트 없음)

- [ ] **Step 3: repo-summary 엔드포인트 추가**

`src/api/issue_registration.py` 에 import 추가:

```python
from src.services.issue_registration_service import (
    get_analysis_issue_status,
    get_repo_issue_summary,   # 추가
    make_ai_issue_key,
    make_static_issue_key,
    register_issue,
)
```

라우터 하단에 헬퍼 + 엔드포인트 추가:

```python
def _get_repo_or_404(db: Session, repo_id: int) -> Repository:
    """repo_id로 Repository를 조회한다. 없으면 404 raise.
    Look up Repository by repo_id. Raises 404 if not found.
    """
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo


@router.get("/repo-summary")
async def repo_summary(request: Request, repo_id: int):
    """repo_detail용 등록 이력 + GitHub 상태를 반환한다.
    Return registration history and GitHub state for repo_detail.
    """
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Login required")

    with SessionLocal() as db:
        repo = _get_repo_or_404(db, repo_id)
        registrations = await get_repo_issue_summary(
            db,
            repo_id=repo_id,
            repo_full_name=repo.full_name,
            github_token=current_user.plaintext_token,
        )

    return {"registrations": registrations}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
make test-file f=tests/unit/api/test_issue_registration_api.py
```
Expected: 전체 passed

- [ ] **Step 5: 커밋**

```bash
git add src/api/issue_registration.py tests/unit/api/test_issue_registration_api.py
git commit -m "feat: issue_registration API — GET /repo-summary 추가"
```

---

### Task 10: repo_detail.html — 반복 이슈 일괄 등록 패널

**Files:**
- Modify: `src/templates/repo_detail.html`

> **Note:** UI/시각 변경 — 정책 11 적용. 4-테마 × 모바일/데스크탑 8 조합 시각 확인 필요.

- [ ] **Step 1: repo_detail.html 구조 파악**

```bash
grep -n "{% block\|</section>\|</main>\|repo\." src/templates/repo_detail.html | head -30
```

- [ ] **Step 2: 반복 이슈 일괄 등록 패널 추가**

기존 AI 인사이트 섹션 아래 또는 `</main>` 직전에 추가:

```html
{# ─── 반복 이슈 일괄 등록 패널 (Phase 2 신규) ─── #}
<section class="issue-reg-panel" id="repoBulkPanel"
         data-repo-id="{{ repo.id }}">

  <h3 class="panel-title">🔁 반복 이슈 — Issue 등록 관리</h3>

  <div class="issue-reg-tabs" role="tablist">
    <button class="issue-tab active" data-tab="static" role="tab">
      🔴 정적 분석 이슈 <span class="issue-tab-count" id="repoStaticCount"></span>
    </button>
    <button class="issue-tab" data-tab="ai" role="tab">
      💡 AI 제안사항 <span class="issue-tab-count" id="repoAiCount"></span>
    </button>
  </div>

  <div class="issue-bulk-toolbar">
    <label class="issue-filter-label">
      <input type="checkbox" id="showUnregisteredOnly"> 미등록만 보기
    </label>
    <button class="btn-primary" id="bulkRegisterBtn" disabled>
      선택 항목 일괄 Issue 등록 (0건) →
    </button>
  </div>

  <div class="issue-tab-panel" id="repoTabStatic">
    <ul class="issue-list" id="repoStaticList"></ul>
  </div>
  <div class="issue-tab-panel hidden" id="repoTabAi">
    <ul class="issue-list" id="repoAiList"></ul>
  </div>
</section>

{# ─── 일괄 등록 모달 ─── #}
<div class="issue-modal-overlay hidden" id="bulkModalOverlay" role="dialog" aria-modal="true">
  <div class="issue-modal">
    <div class="issue-modal-progress" id="bulkProgress"></div>
    <h4 class="issue-modal-title">📝 GitHub Issue 생성</h4>

    <label class="issue-modal-label">제목
      <input type="text" id="bulkTitle" class="issue-modal-input">
    </label>
    <label class="issue-modal-label">본문
      <textarea id="bulkBody" class="issue-modal-textarea" rows="5"></textarea>
    </label>
    <label class="issue-modal-label">라벨 (쉼표 구분)
      <input type="text" id="bulkLabels" class="issue-modal-input">
    </label>

    <div class="issue-modal-actions">
      <button type="button" class="btn-secondary" id="bulkCancel">취소</button>
      <button type="button" class="btn-secondary" id="bulkSkip">이 항목 건너뜀</button>
      <button type="button" class="btn-primary"   id="bulkSubmit">생성 후 다음 →</button>
    </div>
    <p class="issue-modal-error hidden" id="bulkError"></p>
  </div>
</div>

<div class="issue-toast hidden" id="repoIssueToast"></div>

<script>
(function _initRepoBulk() {
  const panel = document.getElementById('repoBulkPanel');
  if (!panel) return;

  const repoId   = Number(panel.dataset.repoId);
  const stateMap = {}; // issue_key → registration
  let _allItems  = [];   // { key, type, label, analysis_id, title, body, labels }
  let _queue     = [];   // 선택된 등록 대상 항목 배열
  let _queueIdx  = 0;

  // ── 상태 로드 ──
  async function loadSummary() {
    try {
      const r = await fetch(`/api/issues/repo-summary?repo_id=${repoId}`);
      if (!r.ok) return;
      const data = await r.json();
      data.registrations.forEach(reg => { stateMap[reg.issue_key] = reg; });
      renderAll();
    } catch (_) {}
  }

  function renderAll() {
    const staticItems = _allItems.filter(i => i.type === 'static_issue');
    const aiItems     = _allItems.filter(i => i.type === 'ai_suggestion');
    const showUnreg   = document.getElementById('showUnregisteredOnly').checked;

    renderList('repoStaticList', 'repoStaticCount', staticItems, showUnreg);
    renderList('repoAiList',     'repoAiCount',     aiItems,     showUnreg);
    updateBulkBtn();
  }

  function renderList(listId, countId, items, showUnregOnly) {
    const ul = document.getElementById(listId);
    const ce = document.getElementById(countId);
    const filtered = showUnregOnly ? items.filter(i => !stateMap[i.key]) : items;
    ul.innerHTML = '';
    if (ce) ce.textContent = `(${filtered.length})`;
    filtered.forEach(item => ul.appendChild(buildBulkRow(item)));
  }

  function buildBulkRow(item) {
    const li = document.createElement('li');
    li.className = 'issue-row';
    const reg = stateMap[item.key];

    if (!reg) {
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.dataset.key = item.key;
      cb.addEventListener('change', updateBulkBtn);
      li.appendChild(cb);
    }

    const lbl = document.createElement('span');
    lbl.className = 'issue-row-label' + (reg && reg.github_issue_state === 'closed' ? ' line-through' : '');
    lbl.textContent = item.label;
    li.appendChild(lbl);

    if (reg) {
      const badge = document.createElement('a');
      badge.href = reg.github_issue_url;
      badge.target = '_blank';
      badge.rel = 'noopener noreferrer';
      badge.className = reg.github_issue_state === 'closed'
        ? 'issue-badge issue-badge--closed'
        : 'issue-badge issue-badge--open';
      badge.textContent = reg.github_issue_state === 'closed'
        ? `✅ #${reg.github_issue_number} 해결됨`
        : `🔵 #${reg.github_issue_number} 진행중`;
      li.appendChild(badge);
    }
    return li;
  }

  function updateBulkBtn() {
    const checked = document.querySelectorAll('.issue-list input[type=checkbox]:checked');
    const btn = document.getElementById('bulkRegisterBtn');
    btn.disabled = checked.length === 0;
    btn.textContent = `선택 항목 일괄 Issue 등록 (${checked.length}건) →`;
  }

  // ── 탭 전환 ──
  document.querySelectorAll('#repoBulkPanel .issue-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('#repoBulkPanel .issue-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('#repoBulkPanel .issue-tab-panel').forEach(p => p.classList.add('hidden'));
      tab.classList.add('active');
      document.getElementById(tab.dataset.tab === 'static' ? 'repoTabStatic' : 'repoTabAi')
              .classList.remove('hidden');
    });
  });

  document.getElementById('showUnregisteredOnly').addEventListener('change', renderAll);

  // ── 일괄 등록 ──
  document.getElementById('bulkRegisterBtn').addEventListener('click', () => {
    const checked = [...document.querySelectorAll('.issue-list input[type=checkbox]:checked')];
    _queue = checked.map(cb => _allItems.find(i => i.key === cb.dataset.key)).filter(Boolean);
    _queueIdx = 0;
    if (_queue.length > 0) openBulkModal();
  });

  function openBulkModal() {
    const item = _queue[_queueIdx];
    document.getElementById('bulkProgress').textContent =
      `${_queueIdx + 1} / ${_queue.length}`;
    document.getElementById('bulkTitle').value  = item.title;
    document.getElementById('bulkBody').value   = item.body;
    document.getElementById('bulkLabels').value = item.labels.join(', ');
    document.getElementById('bulkError').classList.add('hidden');
    document.getElementById('bulkSubmit').disabled = false;
    document.getElementById('bulkSubmit').textContent =
      _queueIdx < _queue.length - 1 ? '생성 후 다음 →' : 'GitHub에 Issue 생성';
    document.getElementById('bulkModalOverlay').classList.remove('hidden');
  }

  function closeBulkModal() {
    document.getElementById('bulkModalOverlay').classList.add('hidden');
    _queue = [];
    _queueIdx = 0;
  }

  document.getElementById('bulkCancel').addEventListener('click', closeBulkModal);

  document.getElementById('bulkSkip').addEventListener('click', () => {
    _queueIdx++;
    if (_queueIdx < _queue.length) openBulkModal();
    else closeBulkModal();
  });

  document.getElementById('bulkSubmit').addEventListener('click', async () => {
    const item = _queue[_queueIdx];
    const btn  = document.getElementById('bulkSubmit');
    btn.disabled = true;
    btn.textContent = '생성 중...';

    const payload = {
      analysis_id: item.analysis_id,
      issue_type:  item.type,
      suggestion_text: item.type === 'ai_suggestion' ? item.suggestionText || null : null,
      tool:     item.tool     || null,
      category: item.category || null,
      message:  item.message  || null,
      title:    document.getElementById('bulkTitle').value.trim(),
      body:     document.getElementById('bulkBody').value,
      labels:   document.getElementById('bulkLabels').value
                .split(',').map(s => s.trim()).filter(Boolean),
    };

    try {
      const r    = await fetch('/api/issues/register', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
      });
      const data = await r.json();
      if (!r.ok) {
        const errEl = document.getElementById('bulkError');
        errEl.textContent = data.detail || '오류 발생';
        errEl.classList.remove('hidden');
        btn.disabled = false;
        btn.textContent = '다시 시도';
        return;
      }
      stateMap[item.key] = {
        github_issue_number: data.github_issue_number,
        github_issue_state:  'open',
        github_issue_url:    data.github_issue_url,
      };
      _queueIdx++;
      if (_queueIdx < _queue.length) {
        openBulkModal();
      } else {
        closeBulkModal();
        renderAll();
        const toast = document.getElementById('repoIssueToast');
        toast.textContent = `✅ ${_queue.length}건 Issue 등록 완료`;
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('hidden'), 5000);
      }
    } catch (_) {
      document.getElementById('bulkError').textContent = '네트워크 오류';
      document.getElementById('bulkError').classList.remove('hidden');
      btn.disabled = false;
      btn.textContent = '다시 시도';
    }
  });

  // ── 초기화 ──
  loadSummary();
})();
</script>
```

- [ ] **Step 3: lint 통과 확인**

```bash
make lint
```

- [ ] **Step 4: 전체 단위 테스트 통과 확인**

```bash
make test-fast
```
Expected: 모두 passed

- [ ] **Step 5: 커밋**

```bash
git add src/templates/repo_detail.html
git commit -m "feat(ui): repo_detail 반복 이슈 일괄 등록 패널 (Phase 2)"
```

---

## 최종 완료 체크리스트

- [ ] `make test-fast` 전체 통과
- [ ] `make lint` 통과 (pylint + flake8 + bandit)
- [ ] `make migrate` — 운영 DB에 0035 마이그레이션 적용 확인
- [ ] analysis_detail 페이지에서 AI 제안사항 탭 → Issue 등록 → 모달 → 생성 → 뱃지 전환 동작 확인
- [ ] repo_detail 페이지에서 일괄 등록 패널 → 체크박스 선택 → 일괄 모달 → 순서대로 생성 동작 확인
- [ ] 중복 등록 시 409 + "이미 등록된 이슈입니다" 메시지 확인
- [ ] **정책 18 Codex mutual 검증 의뢰 (push 전)**  ⛔ *(폐기 2026-07-10 — Codex 단계 수행 안 함)*
- [ ] `git push` + PR 생성 (`gh pr create`)
- [ ] `docs/STATE.md` 수치 갱신 + `docs/cycle-history.md` 사이클 이력 추가
- [ ] `docs/architecture.md` — 신규 파일 5종 + 엔드포인트 3개 동기화
