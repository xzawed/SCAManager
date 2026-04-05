# Phase 3: PR Gate Engine + Config Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 리포지토리별 설정(RepoConfig)을 DB에 저장하고, 분석 점수에 따라 GitHub PR을 자동 승인·반려하거나 Telegram 인라인 버튼으로 담당자에게 반자동 결정을 요청하는 Gate Engine을 구현한다.

**Architecture:** RepoConfig 모델로 리포별 gate_mode/threshold를 관리하고, Gate Engine이 분석 완료 후 자동(httpx→GitHub Review API) 또는 반자동(httpx→Telegram 인라인 키보드) 경로로 분기한다. Telegram 버튼 클릭 시 POST /api/webhook/telegram 엔드포인트가 GateDecision을 저장하고 GitHub Review를 게시한다.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 (Column 스타일), httpx, alembic, pytest + AsyncMock

---

## File Structure

```
src/
├── models/
│   ├── repo_config.py        # NEW: RepoConfig ORM
│   └── gate_decision.py      # NEW: GateDecision ORM
├── config_manager/
│   ├── __init__.py           # NEW: empty
│   └── manager.py            # NEW: get_repo_config(), upsert_repo_config()
├── gate/
│   ├── __init__.py           # NEW: empty
│   ├── engine.py             # NEW: run_gate_check()
│   ├── github_review.py      # NEW: post_github_review()
│   └── telegram_gate.py      # NEW: send_gate_request()
├── webhook/
│   ├── router.py             # MODIFY: POST /api/webhook/telegram 추가
└── worker/
    └── pipeline.py           # MODIFY: gate engine 호출 추가

tests/
├── test_repo_config_model.py  # NEW
├── test_config_manager.py     # NEW
├── test_gate_engine.py        # NEW
├── test_github_review.py      # NEW
├── test_telegram_gate.py      # NEW
└── test_webhook_telegram.py   # NEW

alembic/versions/
└── xxxx_phase3_add_repo_config_gate_decision.py  # NEW
```

---

### Task 1: RepoConfig + GateDecision ORM 모델 + Migration

**Files:**
- Create: `src/models/repo_config.py`
- Create: `src/models/gate_decision.py`
- Create: `alembic/versions/0002_phase3_add_repo_config_gate_decision.py`
- Test: `tests/test_repo_config_model.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_repo_config_model.py
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from src.models.repo_config import RepoConfig
from src.models.gate_decision import GateDecision


def test_repo_config_defaults():
    config = RepoConfig(repo_full_name="owner/repo")
    assert config.gate_mode == "disabled"
    assert config.auto_approve_threshold == 75
    assert config.auto_reject_threshold == 50
    assert config.notify_chat_id is None
    assert config.n8n_webhook_url is None


def test_repo_config_custom_values():
    config = RepoConfig(
        repo_full_name="owner/repo",
        gate_mode="auto",
        auto_approve_threshold=80,
        auto_reject_threshold=40,
        notify_chat_id="-100999",
    )
    assert config.gate_mode == "auto"
    assert config.auto_approve_threshold == 80
    assert config.notify_chat_id == "-100999"


def test_gate_decision_fields():
    decision = GateDecision(
        analysis_id=1,
        decision="approve",
        mode="auto",
    )
    assert decision.analysis_id == 1
    assert decision.decision == "approve"
    assert decision.mode == "auto"
    assert decision.decided_by is None


def test_gate_decision_manual_with_user():
    decision = GateDecision(
        analysis_id=5,
        decision="reject",
        mode="manual",
        decided_by="telegram_user_john",
    )
    assert decision.decided_by == "telegram_user_john"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_repo_config_model.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create RepoConfig model**

```python
# src/models/repo_config.py
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, JSON, DateTime
from src.database import Base


class RepoConfig(Base):
    __tablename__ = "repo_configs"

    id = Column(Integer, primary_key=True, index=True)
    repo_full_name = Column(String, unique=True, nullable=False, index=True)
    gate_mode = Column(String, default="disabled", nullable=False)
    auto_approve_threshold = Column(Integer, default=75, nullable=False)
    auto_reject_threshold = Column(Integer, default=50, nullable=False)
    notify_chat_id = Column(String, nullable=True)
    n8n_webhook_url = Column(String, nullable=True)
    analysis_rules = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Create GateDecision model**

```python
# src/models/gate_decision.py
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from src.database import Base


class GateDecision(Base):
    __tablename__ = "gate_decisions"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id"), nullable=False, index=True)
    decision = Column(String, nullable=False)   # "approve" | "reject" | "skip"
    mode = Column(String, nullable=False)        # "auto" | "manual"
    decided_by = Column(String, nullable=True)   # Telegram username
    decided_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 5: Create alembic migration**

```python
# alembic/versions/0002_phase3_add_repo_config_gate_decision.py
"""phase3: add repo_configs and gate_decisions tables

Revision ID: 0002phase3
Revises: 3b8216565fed
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa

revision = '0002phase3'
down_revision = '3b8216565fed'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'repo_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('repo_full_name', sa.String(), nullable=False),
        sa.Column('gate_mode', sa.String(), nullable=False, server_default='disabled'),
        sa.Column('auto_approve_threshold', sa.Integer(), nullable=False, server_default='75'),
        sa.Column('auto_reject_threshold', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('notify_chat_id', sa.String(), nullable=True),
        sa.Column('n8n_webhook_url', sa.String(), nullable=True),
        sa.Column('analysis_rules', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_repo_configs_id', 'repo_configs', ['id'], unique=False)
    op.create_index('ix_repo_configs_repo_full_name', 'repo_configs', ['repo_full_name'], unique=True)

    op.create_table(
        'gate_decisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('analysis_id', sa.Integer(), nullable=False),
        sa.Column('decision', sa.String(), nullable=False),
        sa.Column('mode', sa.String(), nullable=False),
        sa.Column('decided_by', sa.String(), nullable=True),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['analysis_id'], ['analyses.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_gate_decisions_id', 'gate_decisions', ['id'], unique=False)
    op.create_index('ix_gate_decisions_analysis_id', 'gate_decisions', ['analysis_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_gate_decisions_analysis_id', table_name='gate_decisions')
    op.drop_index('ix_gate_decisions_id', table_name='gate_decisions')
    op.drop_table('gate_decisions')
    op.drop_index('ix_repo_configs_repo_full_name', table_name='repo_configs')
    op.drop_index('ix_repo_configs_id', table_name='repo_configs')
    op.drop_table('repo_configs')
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_repo_config_model.py -v
```

Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
git add src/models/repo_config.py src/models/gate_decision.py alembic/versions/0002_phase3_add_repo_config_gate_decision.py tests/test_repo_config_model.py
git commit -m "feat: add RepoConfig and GateDecision ORM models with migration"
```

---

### Task 2: ConfigManager (리포별 설정 CRUD)

**Files:**
- Create: `src/config_manager/__init__.py`
- Create: `src/config_manager/manager.py`
- Test: `tests/test_config_manager.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_config_manager.py
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database import Base
from src.models.repo_config import RepoConfig
from src.models.gate_decision import GateDecision
from src.config_manager.manager import (
    get_repo_config, upsert_repo_config, RepoConfigData
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_get_repo_config_returns_default_when_not_found(db):
    config = get_repo_config(db, "owner/nonexistent")
    assert config.repo_full_name == "owner/nonexistent"
    assert config.gate_mode == "disabled"
    assert config.auto_approve_threshold == 75
    assert config.auto_reject_threshold == 50
    assert config.notify_chat_id is None


def test_upsert_creates_new_config(db):
    data = RepoConfigData(
        repo_full_name="owner/repo",
        gate_mode="auto",
        auto_approve_threshold=80,
        auto_reject_threshold=45,
    )
    record = upsert_repo_config(db, data)
    assert record.id is not None
    assert record.gate_mode == "auto"
    assert record.auto_approve_threshold == 80


def test_upsert_updates_existing_config(db):
    data = RepoConfigData(repo_full_name="owner/repo", gate_mode="auto")
    upsert_repo_config(db, data)

    data2 = RepoConfigData(repo_full_name="owner/repo", gate_mode="semi-auto", auto_approve_threshold=90)
    record = upsert_repo_config(db, data2)
    assert record.gate_mode == "semi-auto"
    assert record.auto_approve_threshold == 90

    count = db.query(RepoConfig).filter_by(repo_full_name="owner/repo").count()
    assert count == 1


def test_get_repo_config_returns_existing(db):
    data = RepoConfigData(
        repo_full_name="owner/repo",
        gate_mode="auto",
        notify_chat_id="-100999",
    )
    upsert_repo_config(db, data)

    config = get_repo_config(db, "owner/repo")
    assert config.gate_mode == "auto"
    assert config.notify_chat_id == "-100999"
```

- [ ] **Step 2: Run to verify failure**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_config_manager.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create `__init__.py` and `manager.py`**

```python
# src/config_manager/__init__.py
```

```python
# src/config_manager/manager.py
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from src.models.repo_config import RepoConfig


@dataclass
class RepoConfigData:
    repo_full_name: str
    gate_mode: str = "disabled"
    auto_approve_threshold: int = 75
    auto_reject_threshold: int = 50
    notify_chat_id: str | None = None
    n8n_webhook_url: str | None = None
    analysis_rules: dict = field(default_factory=dict)


def get_repo_config(db: Session, repo_full_name: str) -> RepoConfigData:
    record = db.query(RepoConfig).filter_by(repo_full_name=repo_full_name).first()
    if record is None:
        return RepoConfigData(repo_full_name=repo_full_name)
    return RepoConfigData(
        repo_full_name=record.repo_full_name,
        gate_mode=record.gate_mode,
        auto_approve_threshold=record.auto_approve_threshold,
        auto_reject_threshold=record.auto_reject_threshold,
        notify_chat_id=record.notify_chat_id,
        n8n_webhook_url=record.n8n_webhook_url,
        analysis_rules=record.analysis_rules or {},
    )


def upsert_repo_config(db: Session, data: RepoConfigData) -> RepoConfig:
    record = db.query(RepoConfig).filter_by(repo_full_name=data.repo_full_name).first()
    if record is None:
        record = RepoConfig(
            repo_full_name=data.repo_full_name,
            gate_mode=data.gate_mode,
            auto_approve_threshold=data.auto_approve_threshold,
            auto_reject_threshold=data.auto_reject_threshold,
            notify_chat_id=data.notify_chat_id,
            n8n_webhook_url=data.n8n_webhook_url,
            analysis_rules=data.analysis_rules,
        )
        db.add(record)
    else:
        record.gate_mode = data.gate_mode
        record.auto_approve_threshold = data.auto_approve_threshold
        record.auto_reject_threshold = data.auto_reject_threshold
        record.notify_chat_id = data.notify_chat_id
        record.n8n_webhook_url = data.n8n_webhook_url
        record.analysis_rules = data.analysis_rules
    db.commit()
    db.refresh(record)
    return record
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_config_manager.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/config_manager/ tests/test_config_manager.py
git commit -m "feat: add ConfigManager with get_repo_config and upsert_repo_config"
```

---

### Task 3: GitHub Review API

**Files:**
- Create: `src/gate/__init__.py`
- Create: `src/gate/github_review.py`
- Test: `tests/test_github_review.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_github_review.py
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.gate.github_review import post_github_review


async def test_post_github_review_approve():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("src.gate.github_review.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        await post_github_review("token", "owner/repo", 5, "approve", "LGTM")

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert "APPROVE" in str(call_kwargs)
        assert "owner/repo" in str(call_kwargs)
        assert "5" in str(call_kwargs)


async def test_post_github_review_reject():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("src.gate.github_review.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        await post_github_review("token", "owner/repo", 5, "reject", "Needs work")

        call_kwargs = mock_client.post.call_args
        assert "REQUEST_CHANGES" in str(call_kwargs)


async def test_post_github_review_raises_on_error():
    with patch("src.gate.github_review.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("GitHub API error")
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        with pytest.raises(Exception, match="GitHub API error"):
            await post_github_review("token", "owner/repo", 5, "approve", "OK")
```

- [ ] **Step 2: Run to verify failure**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_github_review.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# src/gate/__init__.py
```

```python
# src/gate/github_review.py
import httpx


async def post_github_review(
    github_token: str,
    repo_full_name: str,
    pr_number: int,
    decision: str,
    body: str,
) -> None:
    event = "APPROVE" if decision == "approve" else "REQUEST_CHANGES"
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/reviews"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={"body": body, "event": event}, headers=headers)
        r.raise_for_status()
```

- [ ] **Step 4: Run tests**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_github_review.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/gate/ tests/test_github_review.py
git commit -m "feat: add GitHub Review API client for auto gate decisions"
```

---

### Task 4: Telegram Gate Request (반자동 인라인 키보드)

**Files:**
- Create: `src/gate/telegram_gate.py`
- Test: `tests/test_telegram_gate.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_telegram_gate.py
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from unittest.mock import AsyncMock, patch, MagicMock
from src.gate.telegram_gate import send_gate_request
from src.scorer.calculator import ScoreResult


async def test_send_gate_request_calls_telegram_api():
    score_result = ScoreResult(total=72, grade="B", breakdown={})
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("src.gate.telegram_gate.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        await send_gate_request(
            bot_token="123:ABC",
            chat_id="-100999",
            analysis_id=42,
            repo_full_name="owner/repo",
            pr_number=7,
            score_result=score_result,
        )

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json") or call_args.args[1]
        assert payload["chat_id"] == "-100999"
        assert "inline_keyboard" in str(payload.get("reply_markup", ""))


async def test_send_gate_request_includes_analysis_id_in_callback():
    score_result = ScoreResult(total=60, grade="C", breakdown={})
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("src.gate.telegram_gate.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        await send_gate_request(
            bot_token="123:ABC",
            chat_id="-100999",
            analysis_id=99,
            repo_full_name="owner/repo",
            pr_number=3,
            score_result=score_result,
        )

        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json") or call_args.args[1]
        assert "99" in str(payload.get("reply_markup", ""))
```

- [ ] **Step 2: Run to verify failure**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_telegram_gate.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement**

```python
# src/gate/telegram_gate.py
import httpx
from src.scorer.calculator import ScoreResult


async def send_gate_request(
    bot_token: str,
    chat_id: str,
    analysis_id: int,
    repo_full_name: str,
    pr_number: int,
    score_result: ScoreResult,
) -> None:
    text = (
        f"🔍 *PR 검토 요청*\n"
        f"리포: `{repo_full_name}` — PR #{pr_number}\n"
        f"점수: *{score_result.total}점* ({score_result.grade}등급)\n\n"
        f"승인 또는 반려를 선택하세요."
    )
    reply_markup = {
        "inline_keyboard": [[
            {"text": "✅ 승인", "callback_data": f"gate:approve:{analysis_id}"},
            {"text": "❌ 반려", "callback_data": f"gate:reject:{analysis_id}"},
        ]]
    }
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": reply_markup,
        })
        r.raise_for_status()
```

- [ ] **Step 4: Run tests**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_telegram_gate.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/gate/telegram_gate.py tests/test_telegram_gate.py
git commit -m "feat: add Telegram inline keyboard for semi-auto gate requests"
```

---

### Task 5: Gate Engine (자동/반자동 분기 로직)

**Files:**
- Create: `src/gate/engine.py`
- Test: `tests/test_gate_engine.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_gate_engine.py
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.gate.engine import run_gate_check
from src.scorer.calculator import ScoreResult
from src.config_manager.manager import RepoConfigData


def _make_score(total: int) -> ScoreResult:
    return ScoreResult(total=total, grade="B", breakdown={})


def _make_db_with_config(gate_mode="disabled", approve=75, reject=50, chat_id=None):
    mock_db = MagicMock()
    config = RepoConfigData(
        repo_full_name="owner/repo",
        gate_mode=gate_mode,
        auto_approve_threshold=approve,
        auto_reject_threshold=reject,
        notify_chat_id=chat_id,
    )
    with patch("src.gate.engine.get_repo_config", return_value=config):
        return mock_db, config


async def test_run_gate_check_skips_when_disabled():
    mock_db, _ = _make_db_with_config("disabled")
    with patch("src.gate.engine.get_repo_config", return_value=RepoConfigData(
        repo_full_name="owner/repo", gate_mode="disabled"
    )):
        with patch("src.gate.engine.post_github_review") as mock_review:
            await run_gate_check(
                db=mock_db, github_token="tok", telegram_bot_token="bot",
                repo_full_name="owner/repo", pr_number=1, analysis_id=1,
                score_result=_make_score(80),
            )
            mock_review.assert_not_called()


async def test_run_gate_check_auto_approve():
    mock_db = MagicMock()
    config = RepoConfigData(repo_full_name="owner/repo", gate_mode="auto",
                            auto_approve_threshold=75, auto_reject_threshold=50)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock) as mock_review:
            with patch("src.gate.engine._save_gate_decision") as mock_save:
                await run_gate_check(
                    db=mock_db, github_token="tok", telegram_bot_token="bot",
                    repo_full_name="owner/repo", pr_number=1, analysis_id=1,
                    score_result=_make_score(80),
                )
                mock_review.assert_called_once()
                call_args = mock_review.call_args
                assert call_args.args[3] == "approve"
                mock_save.assert_called_once_with(mock_db, 1, "approve", "auto")


async def test_run_gate_check_auto_reject():
    mock_db = MagicMock()
    config = RepoConfigData(repo_full_name="owner/repo", gate_mode="auto",
                            auto_approve_threshold=75, auto_reject_threshold=50)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock) as mock_review:
            with patch("src.gate.engine._save_gate_decision") as mock_save:
                await run_gate_check(
                    db=mock_db, github_token="tok", telegram_bot_token="bot",
                    repo_full_name="owner/repo", pr_number=1, analysis_id=1,
                    score_result=_make_score(40),
                )
                call_args = mock_review.call_args
                assert call_args.args[3] == "reject"
                mock_save.assert_called_once_with(mock_db, 1, "reject", "auto")


async def test_run_gate_check_auto_skips_between_thresholds():
    mock_db = MagicMock()
    config = RepoConfigData(repo_full_name="owner/repo", gate_mode="auto",
                            auto_approve_threshold=75, auto_reject_threshold=50)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.post_github_review", new_callable=AsyncMock) as mock_review:
            with patch("src.gate.engine._save_gate_decision") as mock_save:
                await run_gate_check(
                    db=mock_db, github_token="tok", telegram_bot_token="bot",
                    repo_full_name="owner/repo", pr_number=1, analysis_id=1,
                    score_result=_make_score(62),
                )
                mock_review.assert_not_called()
                mock_save.assert_called_once_with(mock_db, 1, "skip", "auto")


async def test_run_gate_check_semi_auto_sends_telegram():
    mock_db = MagicMock()
    config = RepoConfigData(repo_full_name="owner/repo", gate_mode="semi-auto",
                            notify_chat_id="-100999")
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.send_gate_request", new_callable=AsyncMock) as mock_send:
            await run_gate_check(
                db=mock_db, github_token="tok", telegram_bot_token="bot",
                repo_full_name="owner/repo", pr_number=7, analysis_id=5,
                score_result=_make_score(65),
            )
            mock_send.assert_called_once()
            call_kwargs = mock_send.call_args.kwargs
            assert call_kwargs["analysis_id"] == 5
            assert call_kwargs["chat_id"] == "-100999"


async def test_run_gate_check_semi_auto_skips_without_chat_id():
    mock_db = MagicMock()
    config = RepoConfigData(repo_full_name="owner/repo", gate_mode="semi-auto",
                            notify_chat_id=None)
    with patch("src.gate.engine.get_repo_config", return_value=config):
        with patch("src.gate.engine.send_gate_request", new_callable=AsyncMock) as mock_send:
            await run_gate_check(
                db=mock_db, github_token="tok", telegram_bot_token="bot",
                repo_full_name="owner/repo", pr_number=7, analysis_id=5,
                score_result=_make_score(65),
            )
            mock_send.assert_not_called()
```

- [ ] **Step 2: Run to verify failure**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_gate_engine.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement gate engine**

```python
# src/gate/engine.py
import logging
from sqlalchemy.orm import Session
from src.config_manager.manager import get_repo_config
from src.gate.github_review import post_github_review
from src.gate.telegram_gate import send_gate_request
from src.models.gate_decision import GateDecision
from src.scorer.calculator import ScoreResult

logger = logging.getLogger(__name__)


async def run_gate_check(
    db: Session,
    github_token: str,
    telegram_bot_token: str,
    repo_full_name: str,
    pr_number: int,
    analysis_id: int,
    score_result: ScoreResult,
) -> None:
    config = get_repo_config(db, repo_full_name)

    if config.gate_mode == "disabled":
        return

    score = score_result.total

    if config.gate_mode == "auto":
        if score >= config.auto_approve_threshold:
            decision = "approve"
            body = (
                f"✅ 자동 승인: 점수 {score}점 "
                f"(기준: {config.auto_approve_threshold}점 이상)"
            )
        elif score < config.auto_reject_threshold:
            decision = "reject"
            body = (
                f"❌ 자동 반려: 점수 {score}점 "
                f"(기준: {config.auto_reject_threshold}점 미만)"
            )
        else:
            _save_gate_decision(db, analysis_id, "skip", "auto")
            return

        try:
            await post_github_review(github_token, repo_full_name, pr_number, decision, body)
            _save_gate_decision(db, analysis_id, decision, "auto")
        except Exception as exc:
            logger.error("GitHub Review 실패: %s", exc)

    elif config.gate_mode == "semi-auto":
        if not config.notify_chat_id:
            logger.warning("semi-auto 모드이나 notify_chat_id 미설정: %s", repo_full_name)
            return
        try:
            await send_gate_request(
                bot_token=telegram_bot_token,
                chat_id=config.notify_chat_id,
                analysis_id=analysis_id,
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                score_result=score_result,
            )
        except Exception as exc:
            logger.error("Telegram Gate 요청 실패: %s", exc)


def _save_gate_decision(
    db: Session,
    analysis_id: int,
    decision: str,
    mode: str,
    decided_by: str | None = None,
) -> GateDecision:
    record = GateDecision(
        analysis_id=analysis_id,
        decision=decision,
        mode=mode,
        decided_by=decided_by,
    )
    db.add(record)
    db.commit()
    return record
```

- [ ] **Step 4: Run tests**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_gate_engine.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/gate/engine.py tests/test_gate_engine.py
git commit -m "feat: implement Gate Engine with auto/semi-auto PR review logic"
```

---

### Task 6: Telegram Callback Endpoint (반자동 결정 수신)

**Files:**
- Modify: `src/webhook/router.py`
- Test: `tests/test_webhook_telegram.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_webhook_telegram.py
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

APPROVE_PAYLOAD = {
    "update_id": 123456,
    "callback_query": {
        "id": "cq001",
        "from": {"id": 111, "username": "reviewer_john"},
        "data": "gate:approve:42",
        "message": {"message_id": 999, "chat": {"id": -100999}},
    }
}

REJECT_PAYLOAD = {
    "update_id": 123457,
    "callback_query": {
        "id": "cq002",
        "from": {"id": 111, "username": "reviewer_john"},
        "data": "gate:reject:42",
        "message": {"message_id": 999, "chat": {"id": -100999}},
    }
}

NON_GATE_PAYLOAD = {
    "update_id": 123458,
    "callback_query": {
        "id": "cq003",
        "from": {"id": 111, "username": "reviewer_john"},
        "data": "other:action",
        "message": {"message_id": 999, "chat": {"id": -100999}},
    }
}


def test_telegram_webhook_approve_returns_200():
    with patch("src.webhook.router.handle_gate_callback", new_callable=AsyncMock) as mock_handle:
        r = client.post("/api/webhook/telegram", json=APPROVE_PAYLOAD)
        assert r.status_code == 200


def test_telegram_webhook_reject_returns_200():
    with patch("src.webhook.router.handle_gate_callback", new_callable=AsyncMock) as mock_handle:
        r = client.post("/api/webhook/telegram", json=REJECT_PAYLOAD)
        assert r.status_code == 200


def test_telegram_webhook_non_gate_callback_returns_200():
    r = client.post("/api/webhook/telegram", json=NON_GATE_PAYLOAD)
    assert r.status_code == 200


def test_telegram_webhook_no_callback_query_returns_200():
    r = client.post("/api/webhook/telegram", json={"update_id": 1})
    assert r.status_code == 200


def test_telegram_webhook_gate_callback_called_with_correct_args():
    with patch("src.webhook.router.handle_gate_callback", new_callable=AsyncMock) as mock_handle:
        client.post("/api/webhook/telegram", json=APPROVE_PAYLOAD)
        mock_handle.assert_called_once()
        call_kwargs = mock_handle.call_args.kwargs
        assert call_kwargs["analysis_id"] == 42
        assert call_kwargs["decision"] == "approve"
        assert call_kwargs["decided_by"] == "reviewer_john"
```

- [ ] **Step 2: Run to verify failure**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_webhook_telegram.py -v
```

Expected: FAIL (endpoint 없음)

- [ ] **Step 3: Add callback handler and endpoint to router.py**

현재 `src/webhook/router.py` 파일 끝에 추가:

```python
# src/webhook/router.py 전체 (기존 코드 유지 + 추가)
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from src.webhook.validator import verify_signature
from src.worker.pipeline import run_analysis_pipeline
from src.gate.engine import _save_gate_decision
from src.gate.github_review import post_github_review
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.database import SessionLocal
from src.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/webhooks/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(body, signature, settings.github_webhook_secret):
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = await request.json()
    event = request.headers.get("X-GitHub-Event", "")

    if event in ("push", "pull_request"):
        background_tasks.add_task(run_analysis_pipeline, event, payload)

    return {"status": "accepted"}


async def handle_gate_callback(
    analysis_id: int,
    decision: str,
    decided_by: str,
) -> None:
    db = SessionLocal()
    try:
        analysis = db.query(Analysis).filter_by(id=analysis_id).first()
        if not analysis:
            logger.warning("handle_gate_callback: analysis %d not found", analysis_id)
            return

        repo = db.query(Repository).filter_by(id=analysis.repo_id).first()
        if not repo:
            logger.warning("handle_gate_callback: repo not found for analysis %d", analysis_id)
            return

        body = f"{'✅ 승인' if decision == 'approve' else '❌ 반려'} by @{decided_by}"
        await post_github_review(
            settings.github_token,
            repo.full_name,
            analysis.pr_number,
            decision,
            body,
        )
        _save_gate_decision(db, analysis_id, decision, "manual", decided_by)
    except Exception as exc:
        logger.error("Gate callback failed: %s", exc)
    finally:
        db.close()


@router.post("/api/webhook/telegram")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    callback_query = payload.get("callback_query")
    if not callback_query:
        return {"status": "ok"}

    data = callback_query.get("data", "")
    if not data.startswith("gate:"):
        return {"status": "ok"}

    parts = data.split(":")
    if len(parts) != 3:
        return {"status": "ok"}

    _, decision, analysis_id_str = parts
    if decision not in ("approve", "reject"):
        return {"status": "ok"}

    try:
        analysis_id = int(analysis_id_str)
    except ValueError:
        return {"status": "ok"}

    decided_by = callback_query.get("from", {}).get("username", "unknown")
    background_tasks.add_task(
        handle_gate_callback,
        analysis_id=analysis_id,
        decision=decision,
        decided_by=decided_by,
    )
    return {"status": "ok"}
```

- [ ] **Step 4: Run tests**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_webhook_telegram.py -v
```

Expected: 5 passed

- [ ] **Step 5: Run full suite**

```bash
cd D:/Source/SCAManager && python -m pytest tests/ -q
```

Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add src/webhook/router.py tests/test_webhook_telegram.py
git commit -m "feat: add Telegram callback endpoint for semi-auto gate decisions"
```

---

### Task 7: Pipeline에 Gate Engine 통합

**Files:**
- Modify: `src/worker/pipeline.py`
- Test: `tests/test_pipeline.py` (기존 파일에 테스트 추가)

- [ ] **Step 1: Write failing tests (기존 test_pipeline.py에 추가)**

기존 `tests/test_pipeline.py` 파일 끝에 아래 테스트를 추가한다:

```python
# tests/test_pipeline.py 끝에 추가

async def test_pipeline_calls_gate_engine_for_pr_event(mock_deps):
    (mock_push, mock_pr, mock_ai, mock_score, mock_telegram,
     mock_comment, mock_session_cls, mock_settings) = mock_deps

    from src.analyzer.static import StaticAnalysisResult
    from src.analyzer.ai_review import AiReviewResult
    from src.scorer.calculator import ScoreResult

    mock_pr.return_value = [
        MagicMock(filename="a.py", content="x=1", patch="@@ +1 x=1")
    ]
    mock_ai.return_value = AiReviewResult(
        commit_score=15, ai_score=15, has_tests=False, summary="ok"
    )
    mock_score.return_value = ScoreResult(total=80, grade="B", breakdown={})

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        MagicMock(id=1),  # repo
        None,             # no existing analysis
    ]
    mock_db.query.return_value.filter_by.return_value.count.return_value = 0
    analysis_mock = MagicMock()
    analysis_mock.id = 99
    mock_db.add = MagicMock()
    mock_db.commit = MagicMock()
    mock_session_cls.return_value = mock_db

    with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate:
        await run_analysis_pipeline("pull_request", PR_DATA)
        mock_gate.assert_called_once()


async def test_pipeline_skips_gate_engine_for_push_event(mock_deps):
    (mock_push, mock_pr, mock_ai, mock_score, mock_telegram,
     mock_comment, mock_session_cls, mock_settings) = mock_deps

    from src.analyzer.static import StaticAnalysisResult
    from src.analyzer.ai_review import AiReviewResult
    from src.scorer.calculator import ScoreResult

    mock_push.return_value = [
        MagicMock(filename="a.py", content="x=1", patch="@@ +1 x=1")
    ]
    mock_ai.return_value = AiReviewResult(
        commit_score=15, ai_score=15, has_tests=False, summary="ok"
    )
    mock_score.return_value = ScoreResult(total=80, grade="B", breakdown={})

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.side_effect = [
        MagicMock(id=1),
        None,
    ]
    mock_session_cls.return_value = mock_db

    with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock) as mock_gate:
        await run_analysis_pipeline("push", PUSH_DATA)
        mock_gate.assert_not_called()
```

- [ ] **Step 2: Run to verify failure**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_pipeline.py -k "gate" -v
```

Expected: FAIL (run_gate_check not imported)

- [ ] **Step 3: Modify pipeline.py to call gate engine**

`src/worker/pipeline.py`의 import 섹션에 추가:
```python
from src.gate.engine import run_gate_check
```

pipeline 함수의 notify_tasks 블록 바로 앞에 추가 (db.close() 전):
```python
        # Gate Engine (PR 이벤트만)
        if pr_number is not None and analysis.id is not None:
            try:
                await run_gate_check(
                    db=db,
                    github_token=settings.github_token,
                    telegram_bot_token=settings.telegram_bot_token,
                    repo_full_name=repo_name,
                    pr_number=pr_number,
                    analysis_id=analysis.id,
                    score_result=score_result,
                )
            except Exception as exc:
                logger.error("Gate check failed: %s", exc)
```

전체 수정된 pipeline.py의 DB 블록:
```python
        db: Session = SessionLocal()
        analysis_id_saved: int | None = None
        try:
            repo = db.query(Repository).filter_by(full_name=repo_name).first()
            if not repo:
                repo = Repository(
                    full_name=repo_name,
                    telegram_chat_id=settings.telegram_chat_id,
                )
                db.add(repo)
                db.flush()

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

            # Gate Engine (PR 이벤트만)
            if pr_number is not None:
                try:
                    await run_gate_check(
                        db=db,
                        github_token=settings.github_token,
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
```

- [ ] **Step 4: Run full test suite**

```bash
cd D:/Source/SCAManager && python -m pytest tests/ -q
```

Expected: all passed (65개 + 신규 테스트)

- [ ] **Step 5: Commit**

```bash
git add src/worker/pipeline.py tests/test_pipeline.py
git commit -m "feat: integrate Gate Engine into analysis pipeline for PR events"
```

---

### Task 8: 전체 Phase 3 검증 및 문서 업데이트

- [ ] **Step 1: 전체 테스트 실행**

```bash
cd D:/Source/SCAManager && python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: 모든 테스트 통과

- [ ] **Step 2: CLAUDE.md Phase 현황 업데이트**

`CLAUDE.md`의 `## 구현 Phase 현황` 테이블에서:
```
| Phase 3 | PR Gate Engine (자동/반자동) + Config Manager | ✅ 완료 | 테스트 수 |
```

- [ ] **Step 3: 최종 커밋 및 푸시**

```bash
git add CLAUDE.md
git commit -m "docs: Phase 3 완료 상태 반영"
git push origin main
```
