> ⚠️ **ARCHIVED — 2026-04-27**: 이 문서는 해당 시점에 완료된 작업을 기록한 것으로, 현재 코드베이스와 일치하지 않을 수 있습니다. 현재 상태는 [docs/STATE.md](../STATE.md)를 참조하세요.

# Railway 배포 실패 → GitHub Issue 자동 등록 Implementation Plan

> **Status:** ✅ **완료** (2026-04-20). 전 Task 커밋 `8dcbe38` … `022e371` 범위에 반영됨. 후속 수정 `7d3a086`(HTTP 상수) · `0c4bfd0`(hmac no-op 제거) 포함.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Railway 빌드 실패 시 해당 GitHub 리포에 빌드 로그(최대 200줄) 포함 Issue 를 자동으로 생성한다.

**Architecture:** Railway Project Webhook → `POST /webhooks/railway/{token}` → BackgroundTask → Railway GraphQL API (로그 조회) → GitHub Issue 생성 (dedup 포함). 신규 `src/railway_client/` 패키지 + `src/notifier/railway_issue.py` 를 신설하고, 기존 `src/webhook/router.py` 에 엔드포인트 1개를 추가. `RepoConfig` 에 필드 3개(`railway_deploy_alerts`, `railway_webhook_token`, `railway_api_token`) 를 추가하며, 토큰 2개는 `hook_token` 과 동일하게 ORM 직접 관리한다.

**Tech Stack:** FastAPI BackgroundTasks, httpx (async), SQLAlchemy + Alembic, GitHub Issues API (`/search/issues` + `POST /repos/{repo}/issues`), Railway GraphQL API (`backboard.railway.app/graphql/v2`), Fernet 암호화 (`src/crypto.py`)

---

## File Map

| 상태 | 파일 | 역할 |
|------|------|------|
| 수정 | `src/models/repo_config.py` | 필드 3개 추가 |
| 신규 | `alembic/versions/0012_add_railway_fields.py` | 마이그레이션 |
| 수정 | `src/config_manager/manager.py` | `RepoConfigData`에 `railway_deploy_alerts` 추가 |
| 수정 | `src/api/repos.py` | `RepoConfigUpdate`에 `railway_deploy_alerts` 추가 |
| 신규 | `src/railway_client/__init__.py` | 빈 패키지 마커 |
| 신규 | `src/railway_client/models.py` | `RailwayDeployEvent` frozen dataclass |
| 신규 | `src/railway_client/webhook.py` | `parse_railway_payload()` |
| 신규 | `src/railway_client/logs.py` | `fetch_deployment_logs()` + `RailwayLogFetchError` |
| 신규 | `src/notifier/railway_issue.py` | `create_deploy_failure_issue()`, `_build_issue_body()` |
| 수정 | `src/webhook/router.py` | `POST /webhooks/railway/{token}` 엔드포인트 |
| 수정 | `src/ui/router.py` | settings GET/POST 핸들러 — Railway 필드 추가 |
| 수정 | `src/templates/settings.html` | 카드 ⑤ Railway 알림 + PRESETS 3개 블록 |
| 신규 | `tests/test_railway_client.py` | payload 파싱 + 로그 조회 (mock httpx) |
| 신규 | `tests/test_railway_issue_notifier.py` | Issue 생성·중복 체크 (mock httpx) |
| 신규 | `tests/test_railway_webhook.py` | 엔드포인트 — token 인증·alerts 필터·dedup |
| 수정 | `CLAUDE.md` | Railway webhook 토큰 인증, 5-way 동기화 주의사항 |
| 수정 | `docs/STATE.md` | 그룹 7 이력 + 테스트 수치 갱신 |

---

## Task 1: ORM 모델 + Alembic 마이그레이션

**Files:**
- Modify: `src/models/repo_config.py`
- Create: `alembic/versions/0012_add_railway_fields.py`
- Test: `tests/test_railway_client.py` (import 검증)

- [x] **Step 1: `src/models/repo_config.py` 에 필드 3개 추가**

기존 `hook_token = Column(...)` 아래에 추가:

```python
railway_deploy_alerts = Column(Boolean, default=False, nullable=False)
railway_webhook_token = Column(String(64), nullable=True, unique=True)
railway_api_token = Column(String, nullable=True)  # Fernet 암호화 저장
```

`__init__` 의 `kwargs.setdefault` 에도 추가:

```python
kwargs.setdefault("railway_deploy_alerts", False)
```

- [x] **Step 2: Alembic 마이그레이션 파일 생성**

`alembic/versions/0012_add_railway_fields.py` 를 생성한다:

```python
"""add railway_deploy_alerts, railway_webhook_token, railway_api_token to repo_configs

Revision ID: 0012railwayfields
Revises: 0011ccandissue
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa

revision = '0012railwayfields'
down_revision = '0011ccandissue'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('repo_configs', sa.Column(
        'railway_deploy_alerts', sa.Boolean(), nullable=False, server_default='false'
    ))
    op.add_column('repo_configs', sa.Column(
        'railway_webhook_token', sa.String(64), nullable=True
    ))
    op.add_column('repo_configs', sa.Column(
        'railway_api_token', sa.String(), nullable=True
    ))
    op.create_unique_constraint(
        'uq_repo_config_railway_webhook_token',
        'repo_configs',
        ['railway_webhook_token']
    )


def downgrade() -> None:
    op.drop_constraint('uq_repo_config_railway_webhook_token', 'repo_configs', type_='unique')
    op.drop_column('repo_configs', 'railway_api_token')
    op.drop_column('repo_configs', 'railway_webhook_token')
    op.drop_column('repo_configs', 'railway_deploy_alerts')
```

- [x] **Step 3: import 검증 테스트 (`tests/test_railway_client.py` 신규 생성)**

```python
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

from src.models.repo_config import RepoConfig


def test_repo_config_has_railway_fields():
    """RepoConfig ORM 에 Railway 필드 3개가 존재해야 한다."""
    assert hasattr(RepoConfig, "railway_deploy_alerts")
    assert hasattr(RepoConfig, "railway_webhook_token")
    assert hasattr(RepoConfig, "railway_api_token")


def test_repo_config_railway_alerts_default():
    """RepoConfig 기본값 — railway_deploy_alerts=False."""
    config = RepoConfig(repo_full_name="owner/repo")
    assert config.railway_deploy_alerts is False
```

- [x] **Step 4: 테스트 실행 — PASS 확인**

```bash
python -m pytest tests/test_railway_client.py::test_repo_config_has_railway_fields tests/test_railway_client.py::test_repo_config_railway_alerts_default -v
```

기대: PASS 2개

- [x] **Step 5: 전체 테스트 회귀 확인**

```bash
python -m pytest tests/ -q --tb=short
```

기대: 기존 1076개 PASS, 신규 2개 PASS = 1078개

- [x] **Step 6: 커밋**

```bash
git add src/models/repo_config.py alembic/versions/0012_add_railway_fields.py tests/test_railway_client.py
git commit -m "feat(model): RepoConfig 에 Railway 필드 3개 + 마이그레이션 추가"
```

---

## Task 2: RepoConfigData + RepoConfigUpdate 확장

**Files:**
- Modify: `src/config_manager/manager.py`
- Modify: `src/api/repos.py`
- Test: `tests/test_railway_client.py` (append)

- [x] **Step 1: `RepoConfigData` 에 `railway_deploy_alerts` 추가**

`src/config_manager/manager.py` 의 `RepoConfigData` 마지막 필드 아래에 추가:

```python
railway_deploy_alerts: bool = False
```

`_config_field_names()` 가 자동으로 포함하므로 `get_repo_config` / `upsert_repo_config` 는 변경 불필요.

> **NOTE**: `railway_webhook_token` 과 `railway_api_token` 은 `RepoConfigData` 에 포함하지 않는다. `hook_token` 과 동일 패턴 — ORM 직접 관리.

- [x] **Step 2: `RepoConfigUpdate` 에 `railway_deploy_alerts` 추가**

`src/api/repos.py` 의 `RepoConfigUpdate` 마지막 필드 아래에 추가:

```python
railway_deploy_alerts: bool = False
```

`update_repo_config` 함수에서 `RepoConfigData(...)` 생성 시 `railway_deploy_alerts=body.railway_deploy_alerts` 도 추가:

```python
upsert_repo_config(db, RepoConfigData(
    repo_full_name=repo_name,
    pr_review_comment=body.pr_review_comment,
    ...
    create_issue=body.create_issue,
    railway_deploy_alerts=body.railway_deploy_alerts,
))
```

- [x] **Step 3: 테스트 추가 (`tests/test_railway_client.py` append)**

```python
from src.config_manager.manager import RepoConfigData


def test_repo_config_data_has_railway_alerts():
    """RepoConfigData 에 railway_deploy_alerts 필드 기본값 False."""
    data = RepoConfigData(repo_full_name="owner/repo")
    assert data.railway_deploy_alerts is False


def test_repo_config_data_railway_alerts_settable():
    """RepoConfigData 에 railway_deploy_alerts=True 설정 가능."""
    data = RepoConfigData(repo_full_name="owner/repo", railway_deploy_alerts=True)
    assert data.railway_deploy_alerts is True
```

- [x] **Step 4: 테스트 실행 — PASS 확인**

```bash
python -m pytest tests/test_railway_client.py -v
```

기대: 4개 모두 PASS

- [x] **Step 5: 커밋**

```bash
git add src/config_manager/manager.py src/api/repos.py tests/test_railway_client.py
git commit -m "feat(config): RepoConfigData/RepoConfigUpdate 에 railway_deploy_alerts 추가"
```

---

## Task 3: RailwayDeployEvent dataclass + payload 파서

**Files:**
- Create: `src/railway_client/__init__.py`
- Create: `src/railway_client/models.py`
- Create: `src/railway_client/webhook.py`
- Test: `tests/test_railway_client.py` (append)

- [x] **Step 1: 패키지 파일 생성**

`src/railway_client/__init__.py` — 빈 파일 생성.

- [x] **Step 2: `src/railway_client/models.py` 생성**

```python
"""Railway webhook 이벤트 데이터 모델."""
from dataclasses import dataclass

# 클래스 외부 상수 — frozen dataclass 내 어노테이션 필드로 두면 dataclass field 로 취급됨
RAILWAY_FAILURE_STATUSES: frozenset = frozenset({"FAILED", "BUILD_FAILED"})


@dataclass(frozen=True)
class RailwayDeployEvent:
    """Railway deployment webhook 에서 파싱된 이벤트."""

    deployment_id: str
    project_id: str
    project_name: str
    environment_name: str
    status: str          # "FAILED" | "BUILD_FAILED"
    commit_sha: str | None
    commit_message: str | None
    repo_full_name: str | None   # Railway payload 제공 GitHub repo (검증용)
    timestamp: str
```

- [x] **Step 3: `src/railway_client/webhook.py` 생성**

```python
"""Railway webhook payload 파싱."""
import logging
from src.railway_client.models import RailwayDeployEvent, RAILWAY_FAILURE_STATUSES

logger = logging.getLogger(__name__)


def parse_railway_payload(body: dict) -> RailwayDeployEvent | None:
    """Railway webhook JSON 을 RailwayDeployEvent 로 파싱.

    Returns:
        RailwayDeployEvent — 빌드 실패 이벤트인 경우.
        None — 빌드 성공, 비DEPLOY 타입, 필수 필드 누락인 경우.
    """
    if body.get("type") != "DEPLOY":
        return None

    status = body.get("status", "")
    if status not in RAILWAY_FAILURE_STATUSES:
        return None

    deployment = body.get("deployment") or {}
    deployment_id = deployment.get("id")
    if not deployment_id:
        logger.warning("parse_railway_payload: deployment.id 누락 — payload 무시")
        return None

    project = body.get("project") or {}
    environment = body.get("environment") or {}
    commit = deployment.get("meta") or {}

    return RailwayDeployEvent(
        deployment_id=deployment_id,
        project_id=project.get("id", ""),
        project_name=project.get("name", ""),
        environment_name=environment.get("name", ""),
        status=status,
        commit_sha=commit.get("commitSha") or None,
        commit_message=commit.get("commitMessage") or None,
        repo_full_name=commit.get("repo") or None,
        timestamp=body.get("timestamp", ""),
    )
```

- [x] **Step 4: payload 파서 테스트 추가 (`tests/test_railway_client.py` append)**

```python
from src.railway_client.webhook import parse_railway_payload


_VALID_PAYLOAD = {
    "type": "DEPLOY",
    "status": "BUILD_FAILED",
    "timestamp": "2026-04-20T10:00:00Z",
    "deployment": {
        "id": "deploy-abc123",
        "meta": {
            "commitSha": "deadbeef1234567890abcdef",
            "commitMessage": "feat: add feature",
            "repo": "owner/repo",
        },
    },
    "project": {"id": "proj-123", "name": "my-project"},
    "environment": {"name": "production"},
}


def test_parse_valid_build_failed():
    """BUILD_FAILED 이벤트는 RailwayDeployEvent 를 반환해야 한다."""
    event = parse_railway_payload(_VALID_PAYLOAD)
    assert event is not None
    assert event.deployment_id == "deploy-abc123"
    assert event.status == "BUILD_FAILED"
    assert event.commit_sha == "deadbeef1234567890abcdef"
    assert event.repo_full_name == "owner/repo"


def test_parse_failed_status():
    """FAILED 상태도 유효 이벤트로 파싱되어야 한다."""
    payload = dict(_VALID_PAYLOAD, status="FAILED")
    event = parse_railway_payload(payload)
    assert event is not None
    assert event.status == "FAILED"


def test_parse_success_returns_none():
    """SUCCESS 상태는 None 을 반환해야 한다."""
    payload = dict(_VALID_PAYLOAD, status="SUCCESS")
    assert parse_railway_payload(payload) is None


def test_parse_non_deploy_type_returns_none():
    """type != DEPLOY 이면 None 을 반환해야 한다."""
    payload = dict(_VALID_PAYLOAD, type="BUILD")
    assert parse_railway_payload(payload) is None


def test_parse_missing_deployment_id_returns_none():
    """deployment.id 누락 시 None 을 반환해야 한다."""
    payload = dict(_VALID_PAYLOAD)
    payload["deployment"] = {}
    assert parse_railway_payload(payload) is None


def test_parse_missing_optional_fields():
    """project/commit 정보 없어도 파싱은 성공해야 한다."""
    payload = {
        "type": "DEPLOY",
        "status": "FAILED",
        "timestamp": "2026-04-20T10:00:00Z",
        "deployment": {"id": "deploy-xyz"},
    }
    event = parse_railway_payload(payload)
    assert event is not None
    assert event.project_name == ""
    assert event.commit_sha is None
```

- [x] **Step 5: 테스트 실행 — 6개 추가 PASS 확인**

```bash
python -m pytest tests/test_railway_client.py -v
```

기대: 10개 PASS (기존 4 + 신규 6)

- [x] **Step 6: 커밋**

```bash
git add src/railway_client/ tests/test_railway_client.py
git commit -m "feat(railway): RailwayDeployEvent dataclass + payload 파서"
```

---

## Task 4: Railway GraphQL 로그 조회

**Files:**
- Create: `src/railway_client/logs.py`
- Test: `tests/test_railway_client.py` (append)

- [x] **Step 1: `src/railway_client/logs.py` 생성**

```python
"""Railway GraphQL API 로 deployment 로그를 조회한다."""
import logging
import httpx
from src.constants import HTTP_CLIENT_TIMEOUT

logger = logging.getLogger(__name__)

RAILWAY_GRAPHQL_URL = "https://backboard.railway.app/graphql/v2"

_LOGS_QUERY = """
query DeploymentLogs($deploymentId: String!, $limit: Int!) {
  deploymentLogs(deploymentId: $deploymentId, limit: $limit) {
    message
    timestamp
    severity
  }
}
"""


class RailwayLogFetchError(Exception):
    """Railway API 로그 조회 실패."""


async def fetch_deployment_logs(
    api_token: str,
    deployment_id: str,
    tail_lines: int = 200,
) -> str:
    """Railway GraphQL `deploymentLogs` 조회 → 마지막 N줄을 단일 문자열로 반환.

    Raises:
        RailwayLogFetchError: API 호출 실패 또는 응답 파싱 오류.
    """
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": _LOGS_QUERY,
        "variables": {"deploymentId": deployment_id, "limit": tail_lines},
    }
    try:
        async with httpx.AsyncClient(timeout=HTTP_CLIENT_TIMEOUT) as client:
            resp = await client.post(RAILWAY_GRAPHQL_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise RailwayLogFetchError(f"HTTP 오류: {exc}") from exc

    errors = data.get("errors")
    if errors:
        raise RailwayLogFetchError(f"GraphQL 오류: {errors}")

    logs = data.get("data", {}).get("deploymentLogs") or []
    lines = [entry.get("message", "") for entry in logs if entry.get("message")]
    return "\n".join(lines)
```

- [x] **Step 2: 로그 조회 테스트 추가 (`tests/test_railway_client.py` append)**

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.railway_client.logs import fetch_deployment_logs, RailwayLogFetchError


@pytest.mark.asyncio
async def test_fetch_deployment_logs_success():
    """정상 응답 시 로그 줄을 합쳐서 반환해야 한다."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "data": {
            "deploymentLogs": [
                {"message": "Installing dependencies", "severity": "INFO"},
                {"message": "Build failed: exit code 1", "severity": "ERROR"},
            ]
        }
    }
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("src.railway_client.logs.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await fetch_deployment_logs("tok", "deploy-123")

    assert "Installing dependencies" in result
    assert "Build failed" in result


@pytest.mark.asyncio
async def test_fetch_deployment_logs_http_error():
    """HTTP 오류 시 RailwayLogFetchError 를 raise 해야 한다."""
    import httpx as _httpx
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=_httpx.RequestError("timeout"))

    with patch("src.railway_client.logs.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(RailwayLogFetchError):
            await fetch_deployment_logs("tok", "deploy-123")


@pytest.mark.asyncio
async def test_fetch_deployment_logs_graphql_error():
    """GraphQL errors 필드 존재 시 RailwayLogFetchError 를 raise 해야 한다."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"errors": [{"message": "Unauthorized"}]}
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("src.railway_client.logs.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(RailwayLogFetchError):
            await fetch_deployment_logs("tok", "deploy-123")
```

- [x] **Step 3: 테스트 실행 — 3개 추가 PASS 확인**

```bash
python -m pytest tests/test_railway_client.py -v
```

기대: 13개 PASS

- [x] **Step 4: 커밋**

```bash
git add src/railway_client/logs.py tests/test_railway_client.py
git commit -m "feat(railway): Railway GraphQL 로그 조회 클라이언트"
```

---

## Task 5: Railway Issue 생성 + 중복 방지

**Files:**
- Create: `src/notifier/railway_issue.py`
- Create: `tests/test_railway_issue_notifier.py`

- [x] **Step 1: failing 테스트 먼저 작성 (`tests/test_railway_issue_notifier.py` 신규 생성)**

```python
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.railway_client.models import RailwayDeployEvent
from src.notifier.railway_issue import create_deploy_failure_issue, _build_issue_body


_EVENT = RailwayDeployEvent(
    deployment_id="deploy-abc",
    project_id="proj-123",
    project_name="my-project",
    environment_name="production",
    status="BUILD_FAILED",
    commit_sha="deadbeef1234567890abcdef",
    commit_message="feat: add feature",
    repo_full_name="owner/repo",
    timestamp="2026-04-20T10:00:00Z",
)


def test_build_issue_body_contains_marker():
    """Issue 본문에 deployment_id 마커가 포함되어야 한다."""
    body = _build_issue_body(event=_EVENT, logs_tail="log line 1\nlog line 2")
    assert "<!-- scamanager-railway-deployment-id:deploy-abc -->" in body


def test_build_issue_body_contains_commit():
    """Issue 본문에 커밋 SHA 축약(7자)이 포함되어야 한다."""
    body = _build_issue_body(event=_EVENT, logs_tail=None)
    assert "deadbee" in body


def test_build_issue_body_no_log_fallback():
    """logs_tail=None 이면 대체 문자열이 포함되어야 한다."""
    body = _build_issue_body(event=_EVENT, logs_tail=None)
    assert "로그를 가져오지 못했습니다" in body


def test_build_issue_body_with_logs():
    """logs_tail 이 있으면 본문에 포함되어야 한다."""
    body = _build_issue_body(event=_EVENT, logs_tail="ERROR: build failed")
    assert "ERROR: build failed" in body


@pytest.mark.asyncio
async def test_create_deploy_failure_issue_creates_issue():
    """중복 없을 때 Issue 번호를 반환해야 한다."""
    search_resp = MagicMock()
    search_resp.raise_for_status = MagicMock()
    search_resp.json.return_value = {"total_count": 0, "items": []}

    create_resp = MagicMock()
    create_resp.raise_for_status = MagicMock()
    create_resp.json.return_value = {"number": 42}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=search_resp)
    mock_client.post = AsyncMock(return_value=create_resp)

    with patch("src.notifier.railway_issue.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await create_deploy_failure_issue(
            github_token="ghp_test",
            repo_full_name="owner/repo",
            event=_EVENT,
            logs_tail="build log",
        )

    assert result == 42


@pytest.mark.asyncio
async def test_create_deploy_failure_issue_dedup():
    """동일 deployment_id Issue 가 이미 존재하면 None 을 반환해야 한다."""
    search_resp = MagicMock()
    search_resp.raise_for_status = MagicMock()
    search_resp.json.return_value = {
        "total_count": 1,
        "items": [{"number": 10}],
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=search_resp)

    with patch("src.notifier.railway_issue.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await create_deploy_failure_issue(
            github_token="ghp_test",
            repo_full_name="owner/repo",
            event=_EVENT,
            logs_tail=None,
        )

    assert result is None
    mock_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_create_deploy_failure_issue_github_error_returns_none():
    """GitHub Issue 생성 실패 시 None 반환 (파이프라인 무중단)."""
    import httpx as _httpx
    search_resp = MagicMock()
    search_resp.raise_for_status = MagicMock()
    search_resp.json.return_value = {"total_count": 0, "items": []}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=search_resp)
    mock_client.post = AsyncMock(side_effect=_httpx.HTTPStatusError(
        "403", request=MagicMock(), response=MagicMock()
    ))

    with patch("src.notifier.railway_issue.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await create_deploy_failure_issue(
            github_token="ghp_test",
            repo_full_name="owner/repo",
            event=_EVENT,
            logs_tail=None,
        )

    assert result is None
```

- [x] **Step 2: 테스트 실행 — 7개 FAIL 확인 (모듈 없음)**

```bash
python -m pytest tests/test_railway_issue_notifier.py -v
```

기대: ImportError 또는 7개 FAIL

- [x] **Step 3: `src/notifier/railway_issue.py` 구현**

```python
"""Railway 빌드 실패 시 GitHub Issue 자동 생성."""
import logging
import httpx
from src.config import settings
from src.github_client.helpers import github_api_headers
from src.railway_client.models import RailwayDeployEvent

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
ISSUE_LABELS = ["scamanager", "deploy-failure", "railway"]


def _build_issue_body(*, event: RailwayDeployEvent, logs_tail: str | None) -> str:
    """Railway 빌드 실패 Issue 본문을 조립한다."""
    marker = f"<!-- scamanager-railway-deployment-id:{event.deployment_id} -->"
    sha_short = event.commit_sha[:7] if event.commit_sha else "unknown"
    base_url = (settings.app_base_url or "https://railway.app").rstrip("/")
    commit_url = (
        f"https://github.com/{event.repo_full_name}/commit/{event.commit_sha}"
        if event.repo_full_name and event.commit_sha
        else "#"
    )
    commit_line = event.commit_message.splitlines()[0] if event.commit_message else ""
    log_content = logs_tail if logs_tail else "로그를 가져오지 못했습니다. Railway 대시보드에서 확인해주세요."

    return "\n".join([
        marker,
        "",
        "## 🚨 Railway Build Failed",
        "",
        f"- **Project**: {event.project_name} (`{event.project_id}`)",
        f"- **Environment**: {event.environment_name}",
        f"- **Status**: {event.status}",
        f"- **Commit**: [`{sha_short}`]({commit_url}) — {commit_line}",
        f"- **Time**: {event.timestamp}",
        "",
        "### Build Log (last 200 lines)",
        "```",
        log_content,
        "```",
        "",
        "---",
        f'<sub>Auto-generated by SCAManager · <a href="https://railway.app/project/{event.project_id}">Railway 대시보드 열기</a></sub>',
    ])


async def create_deploy_failure_issue(
    *,
    github_token: str,
    repo_full_name: str,
    event: RailwayDeployEvent,
    logs_tail: str | None,
) -> int | None:
    """Issue 중복 체크 후 생성. 이미 존재하면 None, 생성 성공 시 Issue number."""
    marker = f"scamanager-railway-deployment-id:{event.deployment_id}"
    title = f"[SCAManager] Railway 빌드 실패: {event.project_name} ({event.status})"
    body = _build_issue_body(event=event, logs_tail=logs_tail)
    headers = github_api_headers(github_token)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # 중복 체크
            search_url = f"{GITHUB_API}/search/issues"
            search_resp = await client.get(
                search_url,
                params={"q": f'repo:{repo_full_name} "{marker}" in:body is:issue'},
                headers=headers,
            )
            search_resp.raise_for_status()
            if search_resp.json().get("total_count", 0) > 0:
                logger.info("Railway Issue 이미 존재 (deployment_id=%s)", event.deployment_id)
                return None

            # Issue 생성
            create_resp = await client.post(
                f"{GITHUB_API}/repos/{repo_full_name}/issues",
                json={"title": title, "body": body, "labels": ISSUE_LABELS},
                headers=headers,
            )
            create_resp.raise_for_status()
            number = create_resp.json().get("number")
            logger.info("Railway Issue 생성 완료 #%s (%s)", number, repo_full_name)
            return number
    except httpx.HTTPError as exc:
        logger.error("create_deploy_failure_issue 실패 (%s): %s", repo_full_name, exc)
        return None
```

- [x] **Step 4: 테스트 실행 — 7개 PASS 확인**

```bash
python -m pytest tests/test_railway_issue_notifier.py -v
```

기대: 7개 PASS

- [x] **Step 5: 전체 테스트 회귀**

```bash
python -m pytest tests/ -q --tb=short
```

기대: 1085개 PASS (1076 + 13 누계)

- [x] **Step 6: 커밋**

```bash
git add src/notifier/railway_issue.py tests/test_railway_issue_notifier.py
git commit -m "feat(notifier): Railway 빌드 실패 GitHub Issue 자동 생성 + 중복 방지"
```

---

## Task 6: Webhook 엔드포인트

**Files:**
- Modify: `src/webhook/router.py`
- Create: `tests/test_railway_webhook.py`

- [x] **Step 1: failing 테스트 먼저 작성 (`tests/test_railway_webhook.py` 신규 생성)**

```python
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

_TOKEN = "abc123valid_token_hex_32chars_xxxxxx"

_PAYLOAD = json.dumps({
    "type": "DEPLOY",
    "status": "BUILD_FAILED",
    "timestamp": "2026-04-20T10:00:00Z",
    "deployment": {
        "id": "deploy-abc",
        "meta": {
            "commitSha": "deadbeef",
            "commitMessage": "feat: something",
            "repo": "owner/repo",
        },
    },
    "project": {"id": "proj-1", "name": "my-project"},
    "environment": {"name": "production"},
}).encode()


def _mock_config(alerts=True, token=_TOKEN, api_token=None):
    c = MagicMock()
    c.railway_deploy_alerts = alerts
    c.railway_webhook_token = token
    c.railway_api_token = api_token
    return c


def _ctx(db_mock):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_mock)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _db_with_config(config_mock):
    """RepoConfig 쿼리 → config_mock, Repository/User 쿼리 → None 으로 세팅된 mock_db."""
    mock_db = MagicMock()
    # side_effect 리스트 — query().filter().first() 호출 순서대로 반환
    # 1: RepoConfig, 2: Repository, 3: User (있으면)
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        config_mock,
        None,  # Repository (user_id 없음 → github_token=settings fallback)
    ]
    return mock_db


def test_invalid_token_returns_404():
    """토큰 불일치 시 404 를 반환해야 한다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    with patch("src.webhook.router.SessionLocal", return_value=_ctx(mock_db)):
        resp = client.post("/webhooks/railway/wrongtoken", content=_PAYLOAD)
    assert resp.status_code == 404


def test_alerts_disabled_returns_200_ignored():
    """`railway_deploy_alerts=False` 이면 200 ignored 를 반환해야 한다."""
    mock_db = _db_with_config(_mock_config(alerts=False))
    with patch("src.webhook.router.SessionLocal", return_value=_ctx(mock_db)):
        resp = client.post(f"/webhooks/railway/{_TOKEN}", content=_PAYLOAD)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_success_status_returns_200_ignored():
    """`status=SUCCESS` 이벤트는 200 ignored 를 반환해야 한다."""
    payload = json.dumps({
        "type": "DEPLOY", "status": "SUCCESS", "timestamp": "T",
        "deployment": {"id": "d1", "meta": {}},
        "project": {}, "environment": {},
    }).encode()
    mock_db = _db_with_config(_mock_config())
    with patch("src.webhook.router.SessionLocal", return_value=_ctx(mock_db)):
        resp = client.post(f"/webhooks/railway/{_TOKEN}", content=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_build_failed_returns_202_accepted():
    """빌드 실패 이벤트는 202 accepted 를 반환해야 한다."""
    mock_db = _db_with_config(_mock_config())
    with patch("src.webhook.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.router._handle_railway_deploy_failure", new_callable=AsyncMock):
            resp = client.post(f"/webhooks/railway/{_TOKEN}", content=_PAYLOAD)
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"


def test_non_deploy_type_returns_200_ignored():
    """type != DEPLOY 이면 200 ignored."""
    payload = json.dumps({"type": "BUILD", "status": "FAILED"}).encode()
    mock_db = _db_with_config(_mock_config())
    with patch("src.webhook.router.SessionLocal", return_value=_ctx(mock_db)):
        resp = client.post(f"/webhooks/railway/{_TOKEN}", content=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
```

- [x] **Step 2: 테스트 실행 — FAIL 확인 (엔드포인트 없음)**

```bash
python -m pytest tests/test_railway_webhook.py -v
```

기대: 5개 FAIL (404 from path not found)

- [x] **Step 3: `src/webhook/router.py` 에 Railway 엔드포인트 추가**

파일 상단 import 섹션에 추가:

```python
import hmac
from src.railway_client.webhook import parse_railway_payload
from src.railway_client.logs import fetch_deployment_logs, RailwayLogFetchError
from src.notifier.railway_issue import create_deploy_failure_issue
from src.models.repo_config import RepoConfig
from src.models.repository import Repository
from src.models.user import User as UserModel
from src.crypto import decrypt_token
```

파일 끝(기존 엔드포인트 아래)에 추가:

```python
@router.post("/webhooks/railway/{token}", status_code=202)
async def railway_webhook(
    token: str,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Railway 빌드 실패 Webhook 수신 → BackgroundTask 로 GitHub Issue 생성."""
    try:
        body = await request.json()
    except Exception:  # pylint: disable=broad-except
        body = {}

    with SessionLocal() as db:
        config = db.query(RepoConfig).filter(
            RepoConfig.railway_webhook_token == token
        ).first()
        if config is None or not hmac.compare_digest(config.railway_webhook_token or "", token):
            raise HTTPException(status_code=404, detail="Not Found")

        if not config.railway_deploy_alerts:
            return {"status": "ignored"}

        # 세션 종료 전 필요 값 추출 (lazy-load 금지 — CLAUDE.md 규약)
        repo_full_name = config.repo_full_name
        decrypted_api_token = (
            decrypt_token(config.railway_api_token) if config.railway_api_token else None
        )

        repo = db.query(Repository).filter(
            Repository.full_name == repo_full_name
        ).first()
        github_token = settings.github_token or ""
        if repo and repo.user_id:
            user = db.query(UserModel).filter(UserModel.id == repo.user_id).first()
            if user:
                github_token = user.plaintext_token or github_token

    event = parse_railway_payload(body)
    if event is None:
        return {"status": "ignored"}

    background_tasks.add_task(
        _handle_railway_deploy_failure,
        repo_full_name=repo_full_name,
        event=event,
        decrypted_api_token=decrypted_api_token,
        github_token=github_token,
    )
    return {"status": "accepted"}


async def _handle_railway_deploy_failure(
    *,
    repo_full_name: str,
    event,
    decrypted_api_token: str | None,
    github_token: str,
) -> None:
    """Railway 빌드 실패 이벤트를 처리하고 GitHub Issue 를 생성한다."""
    logs_tail: str | None = None
    if decrypted_api_token:
        try:
            logs_tail = await fetch_deployment_logs(decrypted_api_token, event.deployment_id)
        except RailwayLogFetchError as exc:
            logger.warning("Railway 로그 조회 실패 (%s): %s", event.deployment_id, exc)
            logs_tail = f"로그 조회 실패: {exc}"

    await create_deploy_failure_issue(
        github_token=github_token,
        repo_full_name=repo_full_name,
        event=event,
        logs_tail=logs_tail,
    )
```

> **NOTE**: `repo.owner` 관계 lazy-load 금지 (CLAUDE.md 규약). `user_id` 컬럼으로 `UserModel` 을 별도 쿼리해 `plaintext_token` 을 세션 내에서 추출한다.

- [x] **Step 4: 테스트 실행 — 5개 PASS 확인**

```bash
python -m pytest tests/test_railway_webhook.py -v
```

기대: 5개 PASS

- [x] **Step 5: 전체 테스트 회귀**

```bash
python -m pytest tests/ -q --tb=short
```

기대: 1091개 PASS (1076 + 15 누계)

- [x] **Step 6: lint 검사**

```bash
python -m pylint src/railway_client/ src/notifier/railway_issue.py
python -m flake8 src/railway_client/ src/notifier/railway_issue.py src/webhook/router.py
```

기대: pylint 에러 0건, flake8 0건

- [x] **Step 7: 커밋**

```bash
git add src/webhook/router.py tests/test_railway_webhook.py
git commit -m "feat(webhook): POST /webhooks/railway/{token} 엔드포인트 추가"
```

---

## Task 7: Settings GET/POST 핸들러 확장

**Files:**
- Modify: `src/ui/router.py`

- [x] **Step 1: `repo_settings` GET 핸들러에 Railway 필드 추가**

`src/ui/router.py` 의 `repo_settings` 함수를 수정:

```python
@router.get("/repos/{repo_name:path}/settings", response_class=HTMLResponse)
def repo_settings(  # pylint: disable=too-many-positional-arguments
    request: Request,
    repo_name: str,
    hook_ok: int = 0,
    hook_fail: int = 0,
    saved: int = 0,
    save_error: int = 0,
    current_user: CurrentUser = Depends(require_login),
):
    """리포 Gate·알림 설정 페이지를 렌더링한다."""
    with SessionLocal() as db:
        _get_accessible_repo(db, repo_name, current_user)
        config = get_repo_config(db, repo_name)
        config_orm = db.query(RepoConfig).filter(
            RepoConfig.repo_full_name == repo_name
        ).first()
        railway_webhook_token = config_orm.railway_webhook_token if config_orm else None
        railway_api_token_set = bool(config_orm and config_orm.railway_api_token)

    railway_webhook_url = ""
    if railway_webhook_token:
        base = _webhook_base_url(request)
        railway_webhook_url = f"{base}/webhooks/railway/{railway_webhook_token}"

    return templates.TemplateResponse(request, "settings.html", {
        "repo_name": repo_name, "config": config,
        "hook_ok": bool(hook_ok), "hook_fail": bool(hook_fail),
        "saved": bool(saved), "save_error": bool(save_error),
        "current_user": current_user,
        "railway_webhook_url": railway_webhook_url,
        "railway_api_token_set": railway_api_token_set,
    })
```

- [x] **Step 2: `update_repo_settings` POST 핸들러에 Railway 처리 추가**

기존 `upsert_repo_config(db, RepoConfigData(...))` 호출에 `railway_deploy_alerts` 추가:

```python
upsert_repo_config(db, RepoConfigData(
    repo_full_name=repo_name,
    pr_review_comment=form.get("pr_review_comment") == "on",
    approve_mode=form.get("approve_mode", "disabled"),
    approve_threshold=int(form.get("approve_threshold", 75)),
    reject_threshold=int(form.get("reject_threshold", 50)),
    notify_chat_id=form.get("notify_chat_id") or None,
    n8n_webhook_url=form.get("n8n_webhook_url") or None,
    discord_webhook_url=form.get("discord_webhook_url", "") or None,
    slack_webhook_url=form.get("slack_webhook_url", "") or None,
    custom_webhook_url=form.get("custom_webhook_url", "") or None,
    email_recipients=form.get("email_recipients", "") or None,
    auto_merge=form.get("auto_merge") == "on",
    merge_threshold=int(form.get("merge_threshold", 75)),
    commit_comment=form.get("commit_comment") == "on",
    create_issue=form.get("create_issue") == "on",
    railway_deploy_alerts=form.get("railway_deploy_alerts") == "on",
))
```

`upsert_repo_config` 호출 직후(같은 `with SessionLocal() as db` 블록 내)에 추가:

```python
# railway_webhook_token, railway_api_token — RepoConfigData 외부 관리 (hook_token 동일 패턴)
config_orm = db.query(RepoConfig).filter(
    RepoConfig.repo_full_name == repo_name
).first()
if config_orm and not config_orm.railway_webhook_token:
    config_orm.railway_webhook_token = secrets.token_hex(32)
new_api_token = form.get("railway_api_token", "")
if config_orm and new_api_token and new_api_token != "****":
    from src.crypto import encrypt_token  # pylint: disable=import-outside-toplevel
    config_orm.railway_api_token = encrypt_token(new_api_token)
if config_orm:
    db.commit()
```

- [x] **Step 3: 전체 테스트 회귀 확인**

```bash
python -m pytest tests/ -q --tb=short
```

기대: 1091개 PASS 유지

- [x] **Step 4: 커밋**

```bash
git add src/ui/router.py
git commit -m "feat(ui): settings GET/POST 핸들러 — Railway 필드 추가 + 토큰 자동 생성"
```

---

## Task 8: Settings HTML — 카드 ⑤ + PRESETS

**Files:**
- Modify: `src/templates/settings.html`

- [x] **Step 1: 카드 ⑤ "Railway 배포 알림" HTML 추가**

`settings.html` 에서 시스템 카드(카드 ④, `hdr-hook` 헤더) 닫는 `</div>` 바로 아래에 추가:

```html
<!-- ⑤ Railway 배포 알림 -->
<div class="s-card" style="margin-top:1rem">
  <div class="s-card-hdr" style="background:linear-gradient(135deg,#7c3aed,#db2777)">
    <span class="hdr-icon">🚂</span>
    <span class="hdr-title">Railway 배포 알림</span>
  </div>
  <div class="s-card-body">
    <label class="toggle-row">
      <div class="toggle-info">
        <span class="toggle-label">빌드 실패 시 GitHub Issue 자동 생성</span>
        <span class="toggle-desc">Railway 빌드 실패 이벤트 수신 시 해당 리포에 로그 포함 Issue 를 자동으로 생성합니다.</span>
      </div>
      <input type="checkbox" name="railway_deploy_alerts" id="railway_deploy_alerts"
        {% if config.railway_deploy_alerts %}checked{% endif %}>
    </label>

    <div class="s-divider"></div>

    <div class="s-section-label">Railway API 토큰 (로그 조회용)</div>
    <input
      type="password"
      name="railway_api_token"
      class="form-control"
      style="margin-bottom:.65rem"
      placeholder="railway_api_token (설정 시 빌드 로그 200줄 포함)"
      value="{{ '****' if railway_api_token_set else '' }}"
      autocomplete="off"
    >
    <p style="font-size:12px;color:var(--text-muted);margin-bottom:1rem">
      Railway 대시보드 → Account Settings → Tokens 에서 발급. 변경하지 않으려면 그대로 두세요.
    </p>

    {% if railway_webhook_url %}
    <div class="s-section-label">Railway Webhook URL</div>
    <div style="display:flex;gap:.5rem;align-items:center;margin-bottom:.5rem">
      <input type="text" readonly class="form-control" id="railway-webhook-url"
        value="{{ railway_webhook_url }}" style="font-family:monospace;font-size:12px">
      <button type="button" class="btn btn--sm"
        onclick="navigator.clipboard.writeText(document.getElementById('railway-webhook-url').value)">📋</button>
    </div>
    <p style="font-size:12px;color:var(--text-muted)">
      Railway Project Settings → Webhooks 에 위 URL 을 추가하세요.
    </p>
    {% else %}
    <p style="font-size:12px;color:var(--text-muted)">
      설정 저장 후 Railway Webhook URL 이 자동 생성됩니다.
    </p>
    {% endif %}
  </div>
</div>
```

- [x] **Step 2: PRESETS JS 객체에 `railway_deploy_alerts` 추가**

`settings.html` 의 `const PRESETS = {` 블록 수정:

`minimal` 블록:
```javascript
minimal: {
  pr_review_comment: true,
  commit_comment: false,
  create_issue: false,
  railway_deploy_alerts: false,   // 추가
  approve_mode: 'disabled',
  auto_merge: false,
  approve_threshold: 75,
  reject_threshold: 50,
  merge_threshold: 75,
},
```

`standard` 블록:
```javascript
standard: {
  pr_review_comment: true,
  commit_comment: true,
  create_issue: false,
  railway_deploy_alerts: true,    // 추가
  approve_mode: 'auto',
  auto_merge: false,
  approve_threshold: 75,
  reject_threshold: 50,
  merge_threshold: 75,
},
```

`strict` 블록:
```javascript
strict: {
  pr_review_comment: true,
  commit_comment: true,
  create_issue: true,
  railway_deploy_alerts: true,    // 추가
  approve_mode: 'auto',
  auto_merge: true,
  approve_threshold: 85,
  reject_threshold: 60,
  merge_threshold: 85,
},
```

- [x] **Step 3: `applyPreset()` 함수에 Railway 토글 추가**

`applyPreset()` 함수 내 `document.querySelector('input[name="auto_merge"]')...` 줄 아래에 추가:

```javascript
const railwayAlertEl = document.querySelector('input[name="railway_deploy_alerts"]');
if (railwayAlertEl) railwayAlertEl.checked = p.railway_deploy_alerts;
```

- [x] **Step 4: 테스트 실행 — 전체 PASS 확인**

```bash
python -m pytest tests/ -q --tb=short
```

기대: 1091개 PASS 유지 (HTML 변경은 기존 unit 테스트에 영향 없음)

- [x] **Step 5: 커밋**

```bash
git add src/templates/settings.html
git commit -m "feat(ui): settings 카드 ⑤ Railway 배포 알림 + PRESETS 3개 블록 추가"
```

---

## Task 9: lint + 전체 품질 검사

**Files:** (변경 없음 — 검사만)

- [x] **Step 1: pylint 전체 실행**

```bash
python -m pylint src/
```

기대: `10.00/10` 유지. 에러 발생 시 수정 후 재실행.

- [x] **Step 2: flake8 전체 실행**

```bash
python -m flake8 src/
```

기대: 0건

- [x] **Step 3: bandit HIGH 검사**

```bash
python -m bandit -r src/ -ll -q
```

기대: HIGH 0건

- [x] **Step 4: 전체 테스트 + 커버리지**

```bash
python -m pytest tests/ -q --tb=short
python -m pytest tests/ --cov=src --cov-report=term-missing -q
```

기대: ~1091개 PASS, 커버리지 96% 이상 유지

- [x] **Step 5: 커밋**

```bash
git add -p   # pylint 수정사항이 있었다면 포함
git commit -m "style: pylint/flake8 통과 — Railway 신규 모듈 품질 검사"
```

(변경사항 없으면 이 커밋 생략)

---

## Task 10: 문서 + 완료 3-step

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/STATE.md`

- [x] **Step 1: `CLAUDE.md` 주의사항 추가**

`### 파이프라인 / 비즈니스 로직` 섹션 끝 또는 `### API / 알림 채널` 섹션 적절한 위치에 추가:

```markdown
- **Railway Webhook 토큰 인증**: `POST /webhooks/railway/{token}` 엔드포인트는 DB 에서 `railway_webhook_token == token` 조회 후 `hmac.compare_digest` 상수시간 비교. 미매칭 시 404(존재 여부 노출 방지). `railway_api_token` 은 Fernet 암호화 저장 — `decrypt_token()` 으로 백그라운드 핸들러에 전달.
- **5-way 동기화 Railway 확장**: `railway_deploy_alerts` 가 ORM/dataclass/API body/settings 폼/PRESETS 5-way 동기화 적용 대상. `railway_webhook_token`·`railway_api_token` 은 `hook_token` 동일 패턴으로 ORM 직접 관리 (RepoConfigData 미포함).
```

- [x] **Step 2: `docs/STATE.md` 갱신**

상단 수치 테이블에서 테스트 수 갱신 (`1076개` → `make test` 실행 후 실제 수치):

```markdown
| 단위 테스트 | **약 1091개** | pytest (0 failed) |
```

> 실제 수치는 `python -m pytest tests/ -q` 결과 합산값으로 교체.

`## 작업 이력` 에 그룹 7 추가:

```markdown
### 그룹 7 — Railway 배포 실패 → GitHub Issue 자동 등록 (2026-04-20)

| 작업 | 주요 내용 | 테스트 증분 |
|------|----------|-----------|
| ORM 필드 추가 | `RepoConfig` 에 `railway_deploy_alerts`/`railway_webhook_token`/`railway_api_token` + Alembic 0012 | +2 |
| railway_client 패키지 | `RailwayDeployEvent` dataclass + `parse_railway_payload()` + `fetch_deployment_logs()` | +9 |
| railway_issue notifier | `create_deploy_failure_issue()` — Search API dedup + Issue 생성 | +7 |
| Webhook 엔드포인트 | `POST /webhooks/railway/{token}` + BackgroundTask 핸들러 | +5 |
| Settings UI | 카드 ⑤ Railway 알림 + PRESETS 3개 블록 + GET/POST 핸들러 | — |
```

- [x] **Step 3: 커밋**

```bash
git add CLAUDE.md docs/STATE.md
git commit -m "docs: Railway 배포 실패 Issue 기능 — CLAUDE.md 주의사항 + STATE.md 갱신"
```

- [x] **Step 4: git push**

```bash
git push origin main
```

- [x] **Step 5: 최종 확인**

```bash
python -m pytest tests/ -q
python -m pylint src/
python -m flake8 src/
```

기대: 모든 검사 통과

---

## Verification (E2E 체크리스트)

```bash
make run   # 개발 서버 실행
```

수동 체크:
1. `/repos/{repo}/settings` 접속 → 카드 ⑤ "Railway 배포 알림" 표시 확인
2. 프리셋 🌱 클릭 → Railway 체크박스 **unchecked** 확인
3. 프리셋 ⚙️ 클릭 → Railway 체크박스 **checked** 확인
4. 프리셋 🛡️ 클릭 → Railway 체크박스 **checked** 확인
5. Railway API 토큰 입력 + 저장 → "설정 저장됨" 표시 + Webhook URL 표시 확인
6. 저장 후 재접속 → API 토큰 란에 `****` 표시 확인 (평문 미노출)
7. curl 로 Railway webhook 발송:
   ```bash
   curl -X POST http://localhost:8000/webhooks/railway/{YOUR_TOKEN} \
     -H "Content-Type: application/json" \
     -d '{"type":"DEPLOY","status":"BUILD_FAILED","timestamp":"2026-04-20T10:00:00Z","deployment":{"id":"test-deploy","meta":{"commitSha":"abc1234","commitMessage":"test","repo":"owner/repo"}},"project":{"id":"p1","name":"test-project"},"environment":{"name":"production"}}'
   ```
   기대: `{"status":"accepted"}` + GitHub Issue 자동 생성 확인
8. 동일 curl 재실행 → 두 번째 Issue 미생성 확인 (dedup)
