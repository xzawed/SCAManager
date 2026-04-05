# Phase 4: Dashboard API + Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 분석 이력·통계 조회 REST API와 Jinja2 기반 웹 대시보드를 구현한다. API Key 인증으로 엔드포인트를 보호하고, Chart.js로 점수 추이와 개발자별 통계를 시각화한다.

**Architecture:** `src/api/` 에 FastAPI 라우터를 분리하고, `src/templates/` 에 Jinja2 HTML 파일을 두어 서버 렌더링한다. API Key는 `X-API-Key` 헤더로 검증하는 FastAPI Dependency로 구현한다. 통계는 SQLAlchemy 쿼리로 집계한다.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLAlchemy 2, Chart.js (CDN), pytest + TestClient

---

## File Structure

```
src/
├── api/
│   ├── __init__.py           # NEW
│   ├── auth.py               # NEW: API Key dependency
│   ├── repos.py              # NEW: GET /api/repos, GET /api/repos/{repo}/analyses, PUT /api/repos/{repo}/config
│   └── stats.py              # NEW: GET /api/repos/{repo}/stats, GET /api/analyses/{id}
├── templates/
│   ├── base.html             # NEW: 공통 레이아웃
│   ├── overview.html         # NEW: 전체 리포 현황
│   ├── repo_detail.html      # NEW: 리포별 분석 이력 + 점수 차트
│   └── settings.html         # NEW: 리포 Gate 설정
├── ui/
│   ├── __init__.py           # NEW
│   └── router.py             # NEW: GET /, GET /repos/{repo}, GET /repos/{repo}/settings
├── config.py                 # MODIFY: api_key 추가
└── main.py                   # MODIFY: api_router, ui_router, StaticFiles 등록

tests/
├── test_api_auth.py          # NEW
├── test_api_repos.py         # NEW
├── test_api_stats.py         # NEW
└── test_ui_router.py         # NEW
```

---

### Task 1: API Key 인증 Dependency

**Files:**
- Create: `src/api/__init__.py`
- Create: `src/api/auth.py`
- Modify: `src/config.py` (api_key 필드 추가)
- Test: `tests/test_api_auth.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_api_auth.py
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "test-api-key-12345")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.auth import require_api_key

app = FastAPI()

@app.get("/protected", dependencies=[require_api_key])
def protected():
    return {"data": "secret"}

client = TestClient(app, raise_server_exceptions=False)


def test_require_api_key_allows_valid_key():
    r = client.get("/protected", headers={"X-API-Key": "test-api-key-12345"})
    assert r.status_code == 200


def test_require_api_key_rejects_missing_key():
    r = client.get("/protected")
    assert r.status_code == 401


def test_require_api_key_rejects_wrong_key():
    r = client.get("/protected", headers={"X-API-Key": "wrong-key"})
    assert r.status_code == 401


def test_require_api_key_allows_when_api_key_not_set(monkeypatch):
    monkeypatch.setattr("src.api.auth.settings.api_key", "")
    r = client.get("/protected")
    assert r.status_code == 200
```

- [ ] **Step 2: Run to verify failure**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_api_auth.py -v
```

Expected: FAIL

- [ ] **Step 3: Add api_key to config.py**

`src/config.py` 수정 — `anthropic_api_key` 아래에 추가:
```python
    api_key: str = ""  # 빈 문자열이면 인증 건너뜀
```

- [ ] **Step 4: Implement auth.py**

```python
# src/api/__init__.py
```

```python
# src/api/auth.py
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from src.config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _check_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    if not settings.api_key:
        return
    if api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


require_api_key = Depends(_check_api_key)
```

- [ ] **Step 5: Run tests**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_api_auth.py -v
```

Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add src/api/ src/config.py tests/test_api_auth.py
git commit -m "feat: add API Key auth dependency and api_key config"
```

---

### Task 2: Repos API (리포 목록, 분석 이력, 설정 변경)

**Files:**
- Create: `src/api/repos.py`
- Test: `tests/test_api_repos.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_api_repos.py
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_get_repos_returns_list():
    mock_repos = [
        MagicMock(id=1, full_name="owner/repo1", created_at=None),
        MagicMock(id=2, full_name="owner/repo2", created_at=None),
    ]
    with patch("src.api.repos.SessionLocal") as mock_session_cls:
        mock_db = MagicMock()
        mock_db.query.return_value.order_by.return_value.all.return_value = mock_repos
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        r = client.get("/api/repos")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_get_repo_analyses_returns_list():
    mock_analyses = [
        MagicMock(id=1, commit_sha="abc123", pr_number=1,
                  score=85, grade="B", created_at=None),
    ]
    with patch("src.api.repos.SessionLocal") as mock_session_cls:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(id=1)
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = mock_analyses
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        r = client.get("/api/repos/owner%2Frepo1/analyses")
    assert r.status_code == 200


def test_get_repo_analyses_404_when_repo_not_found():
    with patch("src.api.repos.SessionLocal") as mock_session_cls:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        r = client.get("/api/repos/nonexistent%2Frepo/analyses")
    assert r.status_code == 404


def test_put_repo_config_updates_settings():
    with patch("src.api.repos.SessionLocal") as mock_session_cls:
        with patch("src.api.repos.upsert_repo_config") as mock_upsert:
            mock_upsert.return_value = MagicMock(
                repo_full_name="owner/repo1", gate_mode="auto",
                auto_approve_threshold=80, auto_reject_threshold=45,
                notify_chat_id=None, n8n_webhook_url=None, analysis_rules={}
            )
            mock_db = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
            r = client.put("/api/repos/owner%2Frepo1/config", json={
                "gate_mode": "auto",
                "auto_approve_threshold": 80,
                "auto_reject_threshold": 45,
            })
    assert r.status_code == 200
    assert r.json()["gate_mode"] == "auto"
```

- [ ] **Step 2: Run to verify failure**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_api_repos.py -v
```

Expected: FAIL (404 — routes not registered)

- [ ] **Step 3: Implement repos.py**

```python
# src/api/repos.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from src.api.auth import require_api_key
from src.database import SessionLocal
from src.models.repository import Repository
from src.models.analysis import Analysis
from src.config_manager.manager import upsert_repo_config, RepoConfigData

router = APIRouter(prefix="/api", dependencies=[require_api_key])


class RepoConfigUpdate(BaseModel):
    gate_mode: str = "disabled"
    auto_approve_threshold: int = 75
    auto_reject_threshold: int = 50
    notify_chat_id: str | None = None
    n8n_webhook_url: str | None = None


@router.get("/repos")
def list_repos():
    with SessionLocal() as db:
        repos = db.query(Repository).order_by(Repository.created_at.desc()).all()
        return [
            {"id": r.id, "full_name": r.full_name,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in repos
        ]


@router.get("/repos/{repo_name:path}/analyses")
def list_repo_analyses(repo_name: str, skip: int = 0, limit: int = 20):
    with SessionLocal() as db:
        repo = db.query(Repository).filter(Repository.full_name == repo_name).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        analyses = (
            db.query(Analysis)
            .filter(Analysis.repo_id == repo.id)
            .order_by(Analysis.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [
            {
                "id": a.id,
                "commit_sha": a.commit_sha,
                "pr_number": a.pr_number,
                "score": a.score,
                "grade": a.grade,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in analyses
        ]


@router.put("/repos/{repo_name:path}/config")
def update_repo_config(repo_name: str, body: RepoConfigUpdate):
    with SessionLocal() as db:
        record = upsert_repo_config(
            db,
            RepoConfigData(
                repo_full_name=repo_name,
                gate_mode=body.gate_mode,
                auto_approve_threshold=body.auto_approve_threshold,
                auto_reject_threshold=body.auto_reject_threshold,
                notify_chat_id=body.notify_chat_id,
                n8n_webhook_url=body.n8n_webhook_url,
            ),
        )
        return {
            "repo_full_name": record.repo_full_name,
            "gate_mode": record.gate_mode,
            "auto_approve_threshold": record.auto_approve_threshold,
            "auto_reject_threshold": record.auto_reject_threshold,
            "notify_chat_id": record.notify_chat_id,
            "n8n_webhook_url": record.n8n_webhook_url,
            "analysis_rules": record.analysis_rules,
        }
```

- [ ] **Step 4: Register router in main.py**

`src/main.py`에 import와 `app.include_router` 추가:
```python
from src.api.repos import router as api_repos_router
app.include_router(api_repos_router)
```

- [ ] **Step 5: Run tests**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_api_repos.py -v
```

Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add src/api/repos.py src/main.py tests/test_api_repos.py
git commit -m "feat: add repos REST API (list, analyses, config update)"
```

---

### Task 3: Stats API (분석 상세 + 통계)

**Files:**
- Create: `src/api/stats.py`
- Test: `tests/test_api_stats.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_api_stats.py
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_get_analysis_detail_returns_data():
    mock_analysis = MagicMock(
        id=1, commit_sha="abc123", pr_number=1,
        score=85, grade="B", result={"breakdown": {}},
        created_at=None,
    )
    with patch("src.api.stats.SessionLocal") as mock_session_cls:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_analysis
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        r = client.get("/api/analyses/1")
    assert r.status_code == 200
    assert r.json()["score"] == 85


def test_get_analysis_detail_404():
    with patch("src.api.stats.SessionLocal") as mock_session_cls:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        r = client.get("/api/analyses/999")
    assert r.status_code == 404


def test_get_repo_stats_returns_summary():
    from datetime import datetime, timezone
    mock_analyses = [
        MagicMock(score=85, grade="B",
                  created_at=datetime(2026, 4, 1, tzinfo=timezone.utc)),
        MagicMock(score=70, grade="C",
                  created_at=datetime(2026, 4, 2, tzinfo=timezone.utc)),
        MagicMock(score=90, grade="A",
                  created_at=datetime(2026, 4, 3, tzinfo=timezone.utc)),
    ]
    with patch("src.api.stats.SessionLocal") as mock_session_cls:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(id=1)
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_analyses
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        r = client.get("/api/repos/owner%2Frepo/stats")
    assert r.status_code == 200
    data = r.json()
    assert "average_score" in data
    assert "total_analyses" in data
    assert "trend" in data
```

- [ ] **Step 2: Run to verify failure**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_api_stats.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement stats.py**

```python
# src/api/stats.py
from fastapi import APIRouter, HTTPException
from src.api.auth import require_api_key
from src.database import SessionLocal
from src.models.repository import Repository
from src.models.analysis import Analysis

router = APIRouter(prefix="/api", dependencies=[require_api_key])


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: int):
    with SessionLocal() as db:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return {
            "id": analysis.id,
            "commit_sha": analysis.commit_sha,
            "pr_number": analysis.pr_number,
            "score": analysis.score,
            "grade": analysis.grade,
            "result": analysis.result,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        }


@router.get("/repos/{repo_name:path}/stats")
def get_repo_stats(repo_name: str, limit: int = 30):
    with SessionLocal() as db:
        repo = db.query(Repository).filter(Repository.full_name == repo_name).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        analyses = (
            db.query(Analysis)
            .filter(Analysis.repo_id == repo.id)
            .order_by(Analysis.created_at.asc())
            .limit(limit)
            .all()
        )

        if not analyses:
            return {"total_analyses": 0, "average_score": 0, "trend": []}

        scores = [a.score for a in analyses if a.score is not None]
        average = sum(scores) / len(scores) if scores else 0
        trend = [
            {
                "date": a.created_at.isoformat() if a.created_at else None,
                "score": a.score,
                "grade": a.grade,
            }
            for a in analyses
        ]

        return {
            "total_analyses": len(analyses),
            "average_score": round(average, 1),
            "trend": trend,
        }
```

- [ ] **Step 4: Register router in main.py**

```python
from src.api.stats import router as api_stats_router
app.include_router(api_stats_router)
```

- [ ] **Step 5: Run tests**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_api_stats.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/api/stats.py src/main.py tests/test_api_stats.py
git commit -m "feat: add stats API (analysis detail and repo score trend)"
```

---

### Task 4: Jinja2 Web UI

**Files:**
- Create: `src/ui/__init__.py`
- Create: `src/ui/router.py`
- Create: `src/templates/base.html`
- Create: `src/templates/overview.html`
- Create: `src/templates/repo_detail.html`
- Create: `src/templates/settings.html`
- Modify: `src/main.py`
- Test: `tests/test_ui_router.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ui_router.py
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_overview_page_returns_200():
    with patch("src.ui.router.SessionLocal") as mock_session_cls:
        mock_db = MagicMock()
        mock_db.query.return_value.order_by.return_value.all.return_value = []
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_repo_detail_page_returns_200():
    with patch("src.ui.router.SessionLocal") as mock_session_cls:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
            id=1, full_name="owner/repo"
        )
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        r = client.get("/repos/owner%2Frepo")
    assert r.status_code == 200


def test_repo_detail_page_404_when_not_found():
    with patch("src.ui.router.SessionLocal") as mock_session_cls:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        r = client.get("/repos/nonexistent%2Frepo")
    assert r.status_code == 404


def test_settings_page_returns_200():
    with patch("src.ui.router.SessionLocal") as mock_session_cls:
        with patch("src.ui.router.get_repo_config") as mock_config:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
                id=1, full_name="owner/repo"
            )
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
            from src.config_manager.manager import RepoConfigData
            mock_config.return_value = RepoConfigData(repo_full_name="owner/repo")
            r = client.get("/repos/owner%2Frepo/settings")
    assert r.status_code == 200
```

- [ ] **Step 2: Run to verify failure**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_ui_router.py -v
```

Expected: FAIL

- [ ] **Step 3: Install Jinja2 and add to requirements.txt**

```bash
pip install jinja2
```

`requirements.txt`에 추가:
```
jinja2==3.1.4
```

- [ ] **Step 4: Create templates**

```html
<!-- src/templates/base.html -->
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}SCAManager{% endblock %}</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; background: #f5f5f5; }
    nav { background: #1a1a2e; color: white; padding: 1rem 2rem; display: flex; align-items: center; gap: 2rem; }
    nav a { color: #eee; text-decoration: none; }
    nav a:hover { color: white; }
    .container { max-width: 1200px; margin: 2rem auto; padding: 0 1rem; }
    .card { background: white; border-radius: 8px; padding: 1.5rem; margin-bottom: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .grade { display: inline-block; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
    .grade-A { background: #d4edda; color: #155724; }
    .grade-B { background: #cce5ff; color: #004085; }
    .grade-C { background: #fff3cd; color: #856404; }
    .grade-D { background: #ffd0b3; color: #7a3000; }
    .grade-F { background: #f8d7da; color: #721c24; }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #eee; }
    th { background: #f8f9fa; font-weight: 600; }
    .btn { padding: 0.4rem 1rem; border-radius: 4px; border: none; cursor: pointer; }
    .btn-primary { background: #0066cc; color: white; }
  </style>
</head>
<body>
  <nav>
    <strong>🔍 SCAManager</strong>
    <a href="/">Overview</a>
  </nav>
  <div class="container">
    {% block content %}{% endblock %}
  </div>
  {% block scripts %}{% endblock %}
</body>
</html>
```

```html
<!-- src/templates/overview.html -->
{% extends "base.html" %}
{% block title %}Overview — SCAManager{% endblock %}
{% block content %}
<h2>리포지토리 현황</h2>
{% if repos %}
<div class="card">
  <table>
    <thead><tr><th>리포지토리</th><th>분석 수</th><th>최근 점수</th><th>등급</th><th></th></tr></thead>
    <tbody>
    {% for item in repos %}
    <tr>
      <td><a href="/repos/{{ item.full_name | urlencode }}">{{ item.full_name }}</a></td>
      <td>{{ item.analysis_count }}</td>
      <td>{{ item.latest_score if item.latest_score else "—" }}</td>
      <td>
        {% if item.latest_grade %}
        <span class="grade grade-{{ item.latest_grade }}">{{ item.latest_grade }}</span>
        {% endif %}
      </td>
      <td><a href="/repos/{{ item.full_name | urlencode }}/settings">설정</a></td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% else %}
<div class="card"><p>등록된 리포지토리가 없습니다. GitHub Webhook을 설정하면 자동으로 등록됩니다.</p></div>
{% endif %}
{% endblock %}
```

```html
<!-- src/templates/repo_detail.html -->
{% extends "base.html" %}
{% block title %}{{ repo_name }} — SCAManager{% endblock %}
{% block content %}
<h2>{{ repo_name }}</h2>
<div class="card">
  <canvas id="scoreChart" height="80"></canvas>
</div>
<div class="card">
  <h3>분석 이력</h3>
  <table>
    <thead><tr><th>날짜</th><th>커밋</th><th>PR</th><th>점수</th><th>등급</th></tr></thead>
    <tbody>
    {% for a in analyses %}
    <tr>
      <td>{{ a.created_at[:10] if a.created_at else "—" }}</td>
      <td><code>{{ a.commit_sha[:7] }}</code></td>
      <td>{% if a.pr_number %}#{{ a.pr_number }}{% else %}—{% endif %}</td>
      <td>{{ a.score }}</td>
      <td><span class="grade grade-{{ a.grade }}">{{ a.grade }}</span></td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
{% block scripts %}
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
const labels = {{ chart_labels | tojson }};
const scores = {{ chart_scores | tojson }};
new Chart(document.getElementById('scoreChart'), {
  type: 'line',
  data: {
    labels,
    datasets: [{
      label: '점수',
      data: scores,
      borderColor: '#0066cc',
      backgroundColor: 'rgba(0,102,204,0.1)',
      tension: 0.3,
      fill: true,
    }]
  },
  options: {
    scales: { y: { min: 0, max: 100 } },
    plugins: { legend: { display: false } }
  }
});
</script>
{% endblock %}
```

```html
<!-- src/templates/settings.html -->
{% extends "base.html" %}
{% block title %}설정 — {{ repo_name }}{% endblock %}
{% block content %}
<h2>{{ repo_name }} 설정</h2>
<div class="card">
  <form method="post" action="/repos/{{ repo_name | urlencode }}/settings">
    <div style="margin-bottom:1rem">
      <label><strong>Gate 모드</strong></label><br>
      <select name="gate_mode" style="padding:0.4rem;margin-top:0.3rem">
        <option value="disabled" {% if config.gate_mode == "disabled" %}selected{% endif %}>비활성화</option>
        <option value="auto" {% if config.gate_mode == "auto" %}selected{% endif %}>자동</option>
        <option value="semi-auto" {% if config.gate_mode == "semi-auto" %}selected{% endif %}>반자동 (Telegram)</option>
      </select>
    </div>
    <div style="margin-bottom:1rem">
      <label><strong>자동 승인 임계값</strong></label><br>
      <input type="number" name="auto_approve_threshold" value="{{ config.auto_approve_threshold }}"
             min="0" max="100" style="padding:0.4rem;margin-top:0.3rem">
    </div>
    <div style="margin-bottom:1rem">
      <label><strong>자동 반려 임계값</strong></label><br>
      <input type="number" name="auto_reject_threshold" value="{{ config.auto_reject_threshold }}"
             min="0" max="100" style="padding:0.4rem;margin-top:0.3rem">
    </div>
    <div style="margin-bottom:1rem">
      <label><strong>Telegram Chat ID (반자동 모드)</strong></label><br>
      <input type="text" name="notify_chat_id" value="{{ config.notify_chat_id or '' }}"
             placeholder="-100xxxxxxxxx" style="padding:0.4rem;margin-top:0.3rem;width:300px">
    </div>
    <button type="submit" class="btn btn-primary">저장</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 5: Create UI router**

```python
# src/ui/__init__.py
```

```python
# src/ui/router.py
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from src.database import SessionLocal
from src.models.repository import Repository
from src.models.analysis import Analysis
from src.config_manager.manager import get_repo_config, upsert_repo_config, RepoConfigData

templates = Jinja2Templates(directory="src/templates")
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def overview(request: Request):
    with SessionLocal() as db:
        repos = db.query(Repository).order_by(Repository.created_at.desc()).all()
        repo_data = []
        for r in repos:
            latest = (
                db.query(Analysis)
                .filter(Analysis.repo_id == r.id)
                .order_by(Analysis.created_at.desc())
                .first()
            )
            count = db.query(Analysis).filter(Analysis.repo_id == r.id).count()
            repo_data.append({
                "full_name": r.full_name,
                "analysis_count": count,
                "latest_score": latest.score if latest else None,
                "latest_grade": latest.grade if latest else None,
            })
    return templates.TemplateResponse("overview.html", {"request": request, "repos": repo_data})


@router.get("/repos/{repo_name:path}", response_class=HTMLResponse)
def repo_detail(request: Request, repo_name: str):
    with SessionLocal() as db:
        repo = db.query(Repository).filter(Repository.full_name == repo_name).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        analyses = (
            db.query(Analysis)
            .filter(Analysis.repo_id == repo.id)
            .order_by(Analysis.created_at.desc())
            .limit(30)
            .all()
        )
        analyses_data = [
            {
                "commit_sha": a.commit_sha,
                "pr_number": a.pr_number,
                "score": a.score,
                "grade": a.grade,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in analyses
        ]
        chart_labels = [a["created_at"][:10] if a["created_at"] else "" for a in reversed(analyses_data)]
        chart_scores = [a["score"] for a in reversed(analyses_data)]
    return templates.TemplateResponse("repo_detail.html", {
        "request": request,
        "repo_name": repo_name,
        "analyses": analyses_data,
        "chart_labels": chart_labels,
        "chart_scores": chart_scores,
    })


@router.get("/repos/{repo_name:path}/settings", response_class=HTMLResponse)
def repo_settings(request: Request, repo_name: str):
    with SessionLocal() as db:
        repo = db.query(Repository).filter(Repository.full_name == repo_name).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        config = get_repo_config(db, repo_name)
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "repo_name": repo_name,
        "config": config,
    })


@router.post("/repos/{repo_name:path}/settings")
async def update_repo_settings(request: Request, repo_name: str):
    form = await request.form()
    with SessionLocal() as db:
        upsert_repo_config(db, RepoConfigData(
            repo_full_name=repo_name,
            gate_mode=form.get("gate_mode", "disabled"),
            auto_approve_threshold=int(form.get("auto_approve_threshold", 75)),
            auto_reject_threshold=int(form.get("auto_reject_threshold", 50)),
            notify_chat_id=form.get("notify_chat_id") or None,
        ))
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/repos/{repo_name}/settings", status_code=303)
```

- [ ] **Step 6: Register in main.py**

```python
from src.ui.router import router as ui_router
app.include_router(ui_router)
```

- [ ] **Step 7: Run tests**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_ui_router.py -v
```

Expected: 4 passed

- [ ] **Step 8: Run full suite**

```bash
cd D:/Source/SCAManager && python -m pytest tests/ -q
```

Expected: all passed

- [ ] **Step 9: Commit**

```bash
git add src/api/ src/ui/ src/templates/ src/main.py requirements.txt tests/test_ui_router.py
git commit -m "feat: Phase 4 — Dashboard API + Jinja2 Web UI with Chart.js"
```

---

### Task 5: Phase 4 문서 업데이트

- [ ] **Step 1: CLAUDE.md 업데이트**

`## 구현 Phase 현황` 테이블에서 Phase 4를 완료 상태로 변경.

`## 프로젝트 구조`에 추가 파일 반영.

- [ ] **Step 2: Push**

```bash
git add CLAUDE.md
git commit -m "docs: Phase 4 완료 상태 반영"
git push origin main
```
