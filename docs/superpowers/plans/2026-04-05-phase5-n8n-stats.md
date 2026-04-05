# Phase 5: n8n 연동 + 통계 고도화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 분석 완료 시 n8n Webhook으로 결과를 POST 전송하고, 개발자별 통계 및 점수 추이 API를 추가한다.

**Architecture:** n8n_webhook_url이 RepoConfig에 이미 저장되어 있으므로 pipeline에서 분석 완료 후 httpx로 POST만 추가하면 된다. 통계 API는 기존 analyses 테이블을 집계한다.

**Tech Stack:** Python 3.12, FastAPI, httpx, SQLAlchemy 2

---

## File Structure

```
src/
├── notifier/
│   └── n8n.py           # NEW: notify_n8n()
├── api/
│   └── stats.py         # MODIFY: /api/repos/{repo}/stats 응답 확장
└── worker/
    └── pipeline.py      # MODIFY: n8n 알림 추가

tests/
├── test_n8n_notifier.py  # NEW
```

---

### Task 1: n8n Notifier

**Files:**
- Create: `src/notifier/n8n.py`
- Test: `tests/test_n8n_notifier.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_n8n_notifier.py
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")

from unittest.mock import AsyncMock, MagicMock, patch
from src.notifier.n8n import notify_n8n
from src.scorer.calculator import ScoreResult


async def test_notify_n8n_posts_to_webhook_url():
    score_result = ScoreResult(total=82, grade="B", breakdown={})
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("src.notifier.n8n.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        await notify_n8n(
            webhook_url="https://n8n.example.com/webhook/abc",
            repo_full_name="owner/repo",
            commit_sha="abc123",
            pr_number=5,
            score_result=score_result,
        )

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        url = call_args.args[0] if call_args.args else call_args.kwargs.get("url")
        assert url == "https://n8n.example.com/webhook/abc"
        payload = call_args.kwargs.get("json") or call_args.args[1]
        assert payload["repo"] == "owner/repo"
        assert payload["score"] == 82
        assert payload["grade"] == "B"


async def test_notify_n8n_skips_when_no_url():
    score_result = ScoreResult(total=80, grade="B", breakdown={})

    with patch("src.notifier.n8n.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock()
        mock_client_cls.return_value = mock_client

        await notify_n8n(
            webhook_url=None,
            repo_full_name="owner/repo",
            commit_sha="abc123",
            pr_number=None,
            score_result=score_result,
        )

        mock_client.post.assert_not_called()


async def test_notify_n8n_handles_error_gracefully():
    score_result = ScoreResult(total=80, grade="B", breakdown={})

    with patch("src.notifier.n8n.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("Connection error")
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        # raise_for_status 예외가 전파되어야 함 (pipeline에서 return_exceptions=True로 처리)
        import pytest
        with pytest.raises(Exception, match="Connection error"):
            await notify_n8n(
                webhook_url="https://n8n.example.com/webhook/abc",
                repo_full_name="owner/repo",
                commit_sha="abc123",
                pr_number=None,
                score_result=score_result,
            )
```

- [ ] **Step 2: Run to verify failure**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_n8n_notifier.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement n8n.py**

```python
# src/notifier/n8n.py
import httpx
from src.scorer.calculator import ScoreResult


async def notify_n8n(
    webhook_url: str | None,
    repo_full_name: str,
    commit_sha: str,
    pr_number: int | None,
    score_result: ScoreResult,
) -> None:
    if not webhook_url:
        return
    payload = {
        "repo": repo_full_name,
        "commit_sha": commit_sha,
        "pr_number": pr_number,
        "score": score_result.total,
        "grade": score_result.grade,
        "breakdown": score_result.breakdown,
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(webhook_url, json=payload)
        r.raise_for_status()
```

- [ ] **Step 4: Run tests**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_n8n_notifier.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/notifier/n8n.py tests/test_n8n_notifier.py
git commit -m "feat: add n8n webhook notifier"
```

---

### Task 2: Pipeline에 n8n 연동

**Files:**
- Modify: `src/worker/pipeline.py`
- Test: `tests/test_pipeline.py` (기존 파일에 테스트 추가)

- [ ] **Step 1: Write failing test (test_pipeline.py에 추가)**

```python
# tests/test_pipeline.py 끝에 추가

async def test_pipeline_calls_n8n_when_webhook_url_set(mock_deps):
    (mock_push, mock_pr, mock_ai, mock_score, mock_telegram,
     mock_comment, mock_session_cls, mock_settings) = mock_deps

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

    from src.config_manager.manager import RepoConfigData
    with patch("src.worker.pipeline.get_repo_config", return_value=RepoConfigData(
        repo_full_name="owner/repo",
        n8n_webhook_url="https://n8n.example.com/webhook/test",
    )):
        with patch("src.worker.pipeline.notify_n8n", new_callable=AsyncMock) as mock_n8n:
            with patch("src.worker.pipeline.run_gate_check", new_callable=AsyncMock):
                await run_analysis_pipeline("push", PUSH_DATA)
                mock_n8n.assert_called_once()
```

- [ ] **Step 2: Run to verify failure**

```bash
cd D:/Source/SCAManager && python -m pytest tests/test_pipeline.py -k "n8n" -v
```

Expected: FAIL

- [ ] **Step 3: Add n8n call to pipeline.py**

`src/worker/pipeline.py`에 import 추가:
```python
from src.notifier.n8n import notify_n8n
from src.config_manager.manager import get_repo_config
```

notify_tasks 리스트에 n8n 태스크 추가:
```python
        # n8n 연동
        n8n_config = get_repo_config(db, repo_name)
        if n8n_config.n8n_webhook_url:
            notify_tasks.append(
                notify_n8n(
                    webhook_url=n8n_config.n8n_webhook_url,
                    repo_full_name=repo_name,
                    commit_sha=commit_sha,
                    pr_number=pr_number,
                    score_result=score_result,
                )
            )
```

> 주의: DB 세션이 close된 후에 `get_repo_config`를 호출하면 세션 에러 발생. `notify_tasks` 구성은 `db.close()` *전*에 해야 함.
> pipeline.py의 DB 블록 안에서 n8n_webhook_url만 추출하고, 태스크는 밖에서 추가한다:

수정된 pipeline 내 DB 블록 끝부분:
```python
            # n8n webhook url 추출 (DB 세션 종료 전)
            n8n_config = get_repo_config(db, repo_name)
            n8n_url = n8n_config.n8n_webhook_url

        # Gate Engine은 DB 세션 내에서 이미 처리됨
        notify_tasks = [
            send_analysis_result(...),
        ]
        if pr_number is not None:
            notify_tasks.append(post_pr_comment(...))
        if n8n_url:
            notify_tasks.append(notify_n8n(
                webhook_url=n8n_url,
                repo_full_name=repo_name,
                commit_sha=commit_sha,
                pr_number=pr_number,
                score_result=score_result,
            ))
```

- [ ] **Step 4: Run tests**

```bash
cd D:/Source/SCAManager && python -m pytest tests/ -q
```

Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add src/worker/pipeline.py tests/test_pipeline.py
git commit -m "feat: integrate n8n webhook notification into analysis pipeline"
```

---

### Task 3: Phase 5 문서 업데이트 및 최종 Push

- [ ] **Step 1: CLAUDE.md 업데이트**

`## 구현 Phase 현황` 전체를 완료 상태로 업데이트.

- [ ] **Step 2: 설계 문서 업데이트**

`docs/superpowers/specs/2026-04-05-scamanager-design.md`의 Phase 테이블을 전체 완료로 업데이트.

- [ ] **Step 3: Push**

```bash
git add CLAUDE.md docs/
git commit -m "docs: Phase 3-5 전체 완료 상태 반영"
git push origin main
```
