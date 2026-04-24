# Phase F.3 Auto-Merge 실패 어드바이저 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** auto-merge 실패 시 사유별 권장 조치 텍스트를 Telegram 알림에 포함하고, 옵션 활성화 시 GitHub Issue를 자동 생성한다.

**Architecture:** `merge_failure_advisor.py`(pure function — reason tag → 권장 조치 한국어 텍스트)와 `merge_failure_issue.py`(GitHub Issue 생성, `railway_issue.py` 패턴)를 신규 모듈로 분리. `engine.py`가 두 모듈을 조합하고, `auto_merge_issue_on_failure` 설정 필드(DB + 5-way sync)로 Issue 생성을 제어한다.

**Tech Stack:** Python asyncio, httpx, SQLAlchemy, Alembic, FastAPI/Pydantic, Jinja2, pytest-asyncio

---

## File Structure

| 파일 | 변경 유형 | 책임 |
|------|----------|------|
| `src/gate/merge_failure_advisor.py` | **신규** | reason tag → 권장 조치 한국어 텍스트 (순수 함수) |
| `src/notifier/merge_failure_issue.py` | **신규** | GitHub Issue 생성 + 24h 중복 차단 |
| `src/gate/engine.py` | **수정** | `_run_auto_merge` + `_notify_merge_failure` 확장 |
| `src/models/repo_config.py` | **수정** | `auto_merge_issue_on_failure` 컬럼 추가 |
| `src/config_manager/manager.py` | **수정** | `RepoConfigData` 필드 추가 |
| `src/api/repos.py` | **수정** | `RepoConfigUpdate` 필드 추가 |
| `alembic/versions/0015_add_auto_merge_issue_on_failure.py` | **신규** | DB 스키마 마이그레이션 |
| `src/templates/settings.html` | **수정** | `mergeIssueRow` + `toggleMergeIssueOption` JS |
| `tests/unit/gate/test_merge_failure_advisor.py` | **신규** | 어드바이저 단위 테스트 3개 |
| `tests/unit/notifier/test_merge_failure_issue.py` | **신규** | notifier 단위 테스트 3개 |
| `tests/unit/gate/test_engine.py` | **수정** | engine 변경 테스트 3개 추가 |
| `CLAUDE.md` | **수정** | 5-way sync 필드 + 아키텍처 + settings 규약 갱신 |
| `docs/STATE.md` | **수정** | 수치 갱신 |

---

### Task 1: Advisor 실패 테스트 작성 (Red)

**Files:**
- Create: `tests/unit/gate/test_merge_failure_advisor.py`

- [ ] **Step 1: 실패 테스트 파일 작성**

```python
"""tests/unit/gate/test_merge_failure_advisor.py"""
import pytest
from src.gate import merge_reasons


def test_get_advice_known_reason_returns_specific_text():
    """알려진 reason tag 는 태그별 권장 조치 텍스트를 반환한다."""
    from src.gate.merge_failure_advisor import get_advice
    advice = get_advice(merge_reasons.BRANCH_PROTECTION_BLOCKED)
    assert "Branch Protection" in advice


def test_get_advice_with_colon_suffix_extracts_tag():
    """engine 이 'tag: user-facing text' 형식으로 전달해도 태그 부분만 추출해 매핑한다."""
    from src.gate.merge_failure_advisor import get_advice
    full_reason = f"{merge_reasons.DIRTY_CONFLICT}: 머지 조건 미충족 (state=dirty)"
    advice = get_advice(full_reason)
    assert "충돌" in advice


def test_get_advice_unknown_or_none_returns_default():
    """알 수 없는 태그와 None 은 기본 문구를 반환한다."""
    from src.gate.merge_failure_advisor import get_advice, _DEFAULT_ADVICE
    assert get_advice("completely_unknown_tag") == _DEFAULT_ADVICE
    assert get_advice(None) == _DEFAULT_ADVICE
```

- [ ] **Step 2: 테스트 실패 확인**

```
pytest tests/unit/gate/test_merge_failure_advisor.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.gate.merge_failure_advisor'`

---

### Task 2: Advisor 구현 (Green) + 커밋

**Files:**
- Create: `src/gate/merge_failure_advisor.py`

- [ ] **Step 1: 구현 파일 작성**

```python
"""Auto-merge 실패 사유별 권장 조치 텍스트 — Phase F.3."""
from src.gate import merge_reasons

_ADVICE: dict[str, str] = {
    merge_reasons.BRANCH_PROTECTION_BLOCKED: (
        "Branch Protection Rules 요건 미충족 — 필수 리뷰어 승인 또는 필수 CI 체크를 완료하세요."
    ),
    merge_reasons.DIRTY_CONFLICT: (
        "기반 브랜치와 충돌(Conflict) — `git pull origin main` 후 충돌을 해소하고 다시 push 하세요."
    ),
    merge_reasons.BEHIND_BASE: (
        "기반 브랜치보다 뒤처져 있음 — PR 페이지에서 'Update branch' 버튼을 눌러 최신화하세요."
    ),
    merge_reasons.DRAFT_PR: (
        "Draft PR은 자동 Merge 대상이 아닙니다 — 'Ready for review'로 전환 후 다시 push 하세요."
    ),
    merge_reasons.UNSTABLE_CI: (
        "CI 체크가 실패하거나 아직 실행 중입니다 — 모든 필수 상태 체크가 통과된 후 다시 시도하세요."
    ),
    merge_reasons.UNKNOWN_STATE_TIMEOUT: (
        "GitHub mergeable 상태 계산이 완료되지 않았습니다 — 잠시 후 PR 페이지를 새로고침하고 재시도하세요."
    ),
    merge_reasons.PERMISSION_DENIED: (
        "GitHub 토큰에 `pull_requests: write` 권한이 없습니다 — Fine-grained PAT 또는 GitHub App 권한을 확인하세요."
    ),
    merge_reasons.NOT_MERGEABLE: (
        "GitHub API가 Merge 불가 상태로 응답했습니다 — PR 페이지에서 상세 사유를 확인하세요."
    ),
    merge_reasons.UNPROCESSABLE: (
        "병합 조건이 충족되지 않았습니다 (422) — PR의 모든 체크와 보호 규칙을 확인하세요."
    ),
    merge_reasons.CONFLICT_SHA_CHANGED: (
        "Head SHA가 변경되었습니다 (409) — 다른 push가 선행된 경우 다음 push 시 자동 재시도됩니다."
    ),
    merge_reasons.NETWORK_ERROR: (
        "GitHub API 네트워크 오류 — 일시적 문제일 수 있습니다. PR 페이지에서 직접 Merge를 시도하세요."
    ),
}

_DEFAULT_ADVICE = "PR 페이지에서 Merge 조건을 확인하고 필요한 조치를 취하세요."


def get_advice(reason: str | None) -> str:
    """reason tag 로 권장 조치 텍스트를 반환. 알 수 없는 tag 는 기본 문구 반환.

    reason 은 'tag' 또는 'tag: user-facing text' 형식 모두 허용.
    """
    if not reason:
        return _DEFAULT_ADVICE
    tag = reason.split(":")[0].strip()
    return _ADVICE.get(tag, _DEFAULT_ADVICE)
```

- [ ] **Step 2: 테스트 통과 확인**

```
pytest tests/unit/gate/test_merge_failure_advisor.py -v
```
Expected: `3 passed`

- [ ] **Step 3: 커밋**

```bash
git add src/gate/merge_failure_advisor.py tests/unit/gate/test_merge_failure_advisor.py
git commit -m "feat(gate): add merge_failure_advisor — reason tag → 권장 조치 텍스트 (Phase F.3)"
```

---

### Task 3: Merge Failure Issue Notifier 실패 테스트 작성 (Red)

**Files:**
- Create: `tests/unit/notifier/test_merge_failure_issue.py`

- [ ] **Step 1: 실패 테스트 파일 작성**

```python
"""tests/unit/notifier/test_merge_failure_issue.py"""
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_resp(status_code: int, json_data: dict):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


async def test_create_merge_failure_issue_success():
    """중복 없으면 Issue 생성 후 Issue number 반환."""
    from src.notifier.merge_failure_issue import create_merge_failure_issue
    search_resp = _mock_resp(200, {"total_count": 0})
    create_resp = _mock_resp(201, {"number": 42})

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=search_resp)
    mock_client.post = AsyncMock(return_value=create_resp)

    with patch("src.notifier.merge_failure_issue.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await create_merge_failure_issue(
            github_token="tok",
            repo_name="owner/repo",
            pr_number=7,
            score=60,
            threshold=75,
            reason="branch_protection_blocked: 머지 조건 미충족",
            advice="Branch Protection 확인 필요",
        )

    assert result == 42
    mock_client.post.assert_called_once()


async def test_create_merge_failure_issue_dedup_skip():
    """24h 내 동일 PR Issue 이미 있으면 None 반환, POST 미호출."""
    from src.notifier.merge_failure_issue import create_merge_failure_issue
    search_resp = _mock_resp(200, {"total_count": 1})

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=search_resp)

    with patch("src.notifier.merge_failure_issue.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await create_merge_failure_issue(
            github_token="tok",
            repo_name="owner/repo",
            pr_number=7,
            score=60,
            threshold=75,
            reason="branch_protection_blocked: 머지 조건 미충족",
            advice="Branch Protection 확인 필요",
        )

    assert result is None
    mock_client.post.assert_not_called()


async def test_create_merge_failure_issue_http_error_returns_none():
    """네트워크 오류 시 None 반환 (파이프라인 미중단)."""
    from src.notifier.merge_failure_issue import create_merge_failure_issue

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.NetworkError("연결 실패"))

    with patch("src.notifier.merge_failure_issue.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await create_merge_failure_issue(
            github_token="tok",
            repo_name="owner/repo",
            pr_number=7,
            score=60,
            threshold=75,
            reason="network_error: 연결 실패",
            advice="잠시 후 재시도하세요",
        )

    assert result is None
```

- [ ] **Step 2: 테스트 실패 확인**

```
pytest tests/unit/notifier/test_merge_failure_issue.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.notifier.merge_failure_issue'`

---

### Task 4: Merge Failure Issue Notifier 구현 (Green) + 커밋

**Files:**
- Create: `src/notifier/merge_failure_issue.py`

- [ ] **Step 1: 구현 파일 작성**

```python
"""Auto-merge 실패 시 GitHub Issue 자동 생성 — Phase F.3."""
import logging
import httpx
from src.constants import GITHUB_API, HTTP_CLIENT_TIMEOUT
from src.github_client.helpers import github_api_headers

logger = logging.getLogger(__name__)

ISSUE_LABELS = ["scamanager", "auto-merge-failure"]


def _build_issue_body(
    *,
    repo_name: str,
    pr_number: int,
    score: int,
    threshold: int,
    reason: str,
    advice: str,
) -> str:
    """Auto-merge 실패 Issue 본문을 조립한다."""
    marker = f"<!-- scamanager-auto-merge-pr:{pr_number} -->"
    pr_url = f"https://github.com/{repo_name}/pull/{pr_number}"
    return "\n".join([
        marker,
        "",
        "## ⚠️ Auto-Merge 실패",
        "",
        f"- **리포**: `{repo_name}`",
        f"- **PR**: [#{pr_number}]({pr_url})",
        f"- **점수**: {score}점 (기준 {threshold}점 이상)",
        f"- **실패 사유**: `{reason}`",
        "",
        "### 권장 조치",
        "",
        advice,
        "",
        "---",
        "<sub>Auto-generated by SCAManager auto-merge advisor</sub>",
    ])


async def create_merge_failure_issue(
    *,
    github_token: str,
    repo_name: str,
    pr_number: int,
    score: int,
    threshold: int,
    reason: str,
    advice: str,
) -> int | None:
    """24h 내 중복 체크 후 Issue 생성. 이미 존재하면 None, 생성 성공 시 Issue number."""
    dedup_marker = f"scamanager-auto-merge-pr:{pr_number}"
    title = f"[SCAManager] Auto-Merge 실패: #{pr_number} ({reason.split(':')[0].strip()})"
    body = _build_issue_body(
        repo_name=repo_name,
        pr_number=pr_number,
        score=score,
        threshold=threshold,
        reason=reason,
        advice=advice,
    )
    headers = github_api_headers(github_token)

    try:
        async with httpx.AsyncClient(timeout=HTTP_CLIENT_TIMEOUT) as client:
            search_resp = await client.get(
                f"{GITHUB_API}/search/issues",
                params={
                    "q": (
                        f'repo:{repo_name} "{dedup_marker}" in:body '
                        f"label:auto-merge-failure is:open"
                    )
                },
                headers=headers,
            )
            search_resp.raise_for_status()
            if search_resp.json().get("total_count", 0) > 0:
                logger.info("Auto-merge failure Issue 이미 존재 (pr=%d)", pr_number)
                return None

            create_resp = await client.post(
                f"{GITHUB_API}/repos/{repo_name}/issues",
                json={"title": title, "body": body, "labels": ISSUE_LABELS},
                headers=headers,
            )
            create_resp.raise_for_status()
            number = create_resp.json().get("number")
            logger.info("Auto-merge failure Issue 생성 완료 #%s (pr=%d)", number, pr_number)
            return number
    except httpx.HTTPError as exc:
        logger.error("create_merge_failure_issue 실패 (%s, pr=%d): %s", repo_name, pr_number, exc)
        return None
```

- [ ] **Step 2: 테스트 통과 확인**

```
pytest tests/unit/notifier/test_merge_failure_issue.py -v
```
Expected: `3 passed`

- [ ] **Step 3: 커밋**

```bash
git add src/notifier/merge_failure_issue.py tests/unit/notifier/test_merge_failure_issue.py
git commit -m "feat(notifier): add merge_failure_issue — auto-merge 실패 GitHub Issue 생성 (Phase F.3)"
```

---

### Task 5: Engine 변경 실패 테스트 작성 (Red)

**Files:**
- Modify: `tests/unit/gate/test_engine.py` (3개 테스트 추가)

- [ ] **Step 1: 기존 파일 끝에 3개 테스트 추가**

파일 맨 끝에 아래 코드를 추가한다 (기존 import에 `MagicMock`이 없으면 추가):

```python
# ── Phase F.3 테스트 ────────────────────────────────────────────────────────


async def test_run_auto_merge_creates_issue_when_enabled():
    """auto_merge_issue_on_failure=True 이면 merge 실패 시 create_merge_failure_issue 호출."""
    config = _config(
        auto_merge=True,
        merge_threshold=75,
        auto_merge_issue_on_failure=True,
        notify_chat_id=None,
    )
    with (
        patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge,
        patch("src.gate.engine.create_merge_failure_issue", new_callable=AsyncMock) as mock_issue,
        patch("src.gate.engine.log_merge_attempt"),
        patch("src.gate.engine._notify_merge_failure", new_callable=AsyncMock),
    ):
        mock_merge.return_value = (False, "branch_protection_blocked: blocked")
        mock_issue.return_value = 42
        await _run_auto_merge(
            config, "tok", "owner/repo", 1, 80, analysis_id=1, db=MagicMock()
        )
    mock_issue.assert_awaited_once()


async def test_run_auto_merge_skips_issue_when_disabled():
    """auto_merge_issue_on_failure=False 이면 merge 실패해도 create_merge_failure_issue 미호출."""
    config = _config(
        auto_merge=True,
        merge_threshold=75,
        auto_merge_issue_on_failure=False,
        notify_chat_id=None,
    )
    with (
        patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge,
        patch("src.gate.engine.create_merge_failure_issue", new_callable=AsyncMock) as mock_issue,
        patch("src.gate.engine.log_merge_attempt"),
        patch("src.gate.engine._notify_merge_failure", new_callable=AsyncMock),
    ):
        mock_merge.return_value = (False, "branch_protection_blocked: blocked")
        await _run_auto_merge(
            config, "tok", "owner/repo", 1, 80, analysis_id=1, db=MagicMock()
        )
    mock_issue.assert_not_awaited()


async def test_notify_merge_failure_includes_advice_in_telegram():
    """_notify_merge_failure 가 Telegram 메시지에 advice 텍스트를 포함한다."""
    with patch("src.gate.engine.telegram_post_message", new_callable=AsyncMock) as mock_tg:
        await _notify_merge_failure(
            repo_name="owner/repo",
            pr_number=1,
            score=60,
            threshold=75,
            reason="dirty_conflict: 충돌",
            advice="충돌을 해소하세요",
            chat_id="123",
        )
    sent_text = mock_tg.call_args[0][2]["text"]
    assert "충돌을 해소하세요" in sent_text
```

- [ ] **Step 2: 기존 test_engine.py imports 확인**

`test_engine.py` 상단에 `from unittest.mock import MagicMock`이 있는지 확인. 없으면 import 줄에 `MagicMock` 추가.

`from src.gate.engine import _run_auto_merge, _notify_merge_failure`가 import되어 있는지 확인. 없으면 추가.

- [ ] **Step 3: 테스트 실패 확인**

```
pytest tests/unit/gate/test_engine.py::test_run_auto_merge_creates_issue_when_enabled tests/unit/gate/test_engine.py::test_run_auto_merge_skips_issue_when_disabled tests/unit/gate/test_engine.py::test_notify_merge_failure_includes_advice_in_telegram -v
```
Expected: `ImportError` 또는 `AttributeError` — `_notify_merge_failure`에 `advice` 파라미터 미존재, `create_merge_failure_issue` engine에 미import

---

### Task 6: Engine 변경 구현 (Green) + 커밋

**Files:**
- Modify: `src/gate/engine.py`

- [ ] **Step 1: import 추가**

`src/gate/engine.py` 파일 상단 import 블록에 두 줄 추가:

```python
from src.gate.merge_failure_advisor import get_advice
from src.notifier.merge_failure_issue import create_merge_failure_issue
```

(기존 `from src.gate.github_review import post_github_review, merge_pr` 바로 아래에 추가)

- [ ] **Step 2: `_notify_merge_failure` 시그니처에 `advice` 파라미터 추가 + 메시지에 포함**

기존 함수를 아래로 교체:

```python
async def _notify_merge_failure(
    *,
    repo_name: str,
    pr_number: int,
    score: int,
    threshold: int,
    reason: str,
    advice: str,
    chat_id: str | None,
) -> None:
    """auto_merge 실패를 Telegram 으로 알린다. chat_id 없으면 스킵."""
    if not chat_id or not settings.telegram_bot_token:
        return
    pr_url = f"https://github.com/{repo_name}/pull/{pr_number}"
    text = (
        "⚠️ <b>Auto Merge 실패</b>\n"
        f"📁 <code>{escape(repo_name)}</code> — PR #{pr_number}\n"
        f"점수: {score}점 (기준 {threshold}점 이상)\n"
        f"사유: <code>{escape(reason)}</code>\n"
        f"💡 {escape(advice)}\n"
        f"🔗 <a href=\"{escape(pr_url)}\">GitHub 에서 보기</a>"
    )
    try:
        await telegram_post_message(
            settings.telegram_bot_token,
            chat_id,
            {"text": text, "parse_mode": "HTML"},
        )
    except httpx.HTTPError as exc:
        logger.warning("Telegram merge-failure 알림 실패: %s", exc)
```

- [ ] **Step 3: `_run_auto_merge` 에 advice 계산 + Issue 생성 로직 추가**

`_run_auto_merge` 함수에서 `if ok:` 블록 이후 부분을 아래로 교체:

```python
        if ok:
            logger.info("PR #%d auto-merged: %s", pr_number, repo_name)
            return

        advice = get_advice(reason)

        logger.warning(
            "PR #%d auto-merge 실패 (repo=%s): %s", pr_number, repo_name, reason
        )
        await _notify_merge_failure(
            repo_name=repo_name,
            pr_number=pr_number,
            score=score,
            threshold=config.merge_threshold,
            reason=reason or "unknown",
            advice=advice,
            chat_id=config.notify_chat_id or settings.telegram_chat_id,
        )
        if config.auto_merge_issue_on_failure:
            try:
                await create_merge_failure_issue(
                    github_token=github_token,
                    repo_name=repo_name,
                    pr_number=pr_number,
                    score=score,
                    threshold=config.merge_threshold,
                    reason=reason or "unknown",
                    advice=advice,
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(
                    "create_merge_failure_issue 실패 (pr=%d): %s", pr_number, exc
                )
```

- [ ] **Step 4: 전체 테스트 통과 확인**

```
pytest tests/unit/gate/test_engine.py -v
```
Expected: 기존 테스트 + 3개 신규 테스트 모두 `passed`

- [ ] **Step 5: 커밋**

```bash
git add src/gate/engine.py tests/unit/gate/test_engine.py
git commit -m "feat(gate): engine — advice 포함 Telegram 알림 + Issue 생성 통합 (Phase F.3)"
```

---

### Task 7: Alembic 마이그레이션 + 5-way 동기화 + 커밋

**Files:**
- Create: `alembic/versions/0015_add_auto_merge_issue_on_failure.py`
- Modify: `src/models/repo_config.py`
- Modify: `src/config_manager/manager.py`
- Modify: `src/api/repos.py`

- [ ] **Step 1: Alembic 마이그레이션 파일 작성**

```python
"""add auto_merge_issue_on_failure to repo_configs (Phase F.3)

Revision ID: 0015automergeissue
Revises: 0014mergeattempts
Create Date: 2026-04-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0015automergeissue"
down_revision = "0014mergeattempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add auto_merge_issue_on_failure column to repo_configs."""
    op.add_column(
        "repo_configs",
        sa.Column(
            "auto_merge_issue_on_failure",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Drop auto_merge_issue_on_failure column from repo_configs."""
    op.drop_column("repo_configs", "auto_merge_issue_on_failure")
```

- [ ] **Step 2: ORM — `src/models/repo_config.py` 에 컬럼 추가**

`railway_api_token` 줄 바로 뒤에 추가:

```python
    auto_merge_issue_on_failure = Column(Boolean, default=False, nullable=False)
```

그리고 `__init__` 메서드의 `super().__init__(**kwargs)` 바로 위에 추가:

```python
        kwargs.setdefault("auto_merge_issue_on_failure", False)
```

- [ ] **Step 3: RepoConfigData — `src/config_manager/manager.py` 에 필드 추가**

`railway_deploy_alerts: bool = False` 줄 바로 뒤에 추가:

```python
    auto_merge_issue_on_failure: bool = False
```

- [ ] **Step 4: RepoConfigUpdate — `src/api/repos.py` 에 필드 추가**

`railway_deploy_alerts: bool = False` 줄 바로 뒤에 추가:

```python
    auto_merge_issue_on_failure: bool = False
```

- [ ] **Step 5: 전체 테스트 통과 확인**

```
pytest tests/ -v --ignore=tests/integration -m "not slow" -x
```
Expected: 모두 `passed`

- [ ] **Step 6: 커밋**

```bash
git add alembic/versions/0015_add_auto_merge_issue_on_failure.py \
        src/models/repo_config.py \
        src/config_manager/manager.py \
        src/api/repos.py
git commit -m "feat(db): add auto_merge_issue_on_failure — migration 0015 + 5-way sync (Phase F.3)"
```

---

### Task 8: Settings UI — mergeIssueRow 토글 + JS 헬퍼

**Files:**
- Modify: `src/templates/settings.html`

- [ ] **Step 1: `mergeIssueRow` HTML 추가**

`mergeThresholdRow` div (id="mergeThresholdRow") 닫는 태그(`</div>`) 바로 뒤에 삽입:

```html
          <!-- Auto-merge 실패 시 Issue 생성 (auto_merge OFF 시 숨김) -->
          <div id="mergeIssueRow" class="{% if not config.auto_merge %}is-hidden{% endif %}" style="margin-top:.75rem;">
            <div class="toggle-row">
              <div class="toggle-info">
                <div class="t-title">실패 시 Issue 자동 생성</div>
                <div class="t-desc">Auto-merge 실패 시 권장 조치를 담은<br>GitHub Issue 자동 생성</div>
              </div>
              <label class="toggle-switch">
                <input type="checkbox" name="auto_merge_issue_on_failure" value="on"
                       {% if config.auto_merge_issue_on_failure %}checked{% endif %}>
                <span class="toggle-track"></span>
              </label>
            </div>
          </div>
```

- [ ] **Step 2: `toggleMergeIssueOption` JS 함수 추가 + `toggleMergeThreshold` 확장**

기존 `toggleMergeThreshold` 함수(line ~1098):

```javascript
  function toggleMergeThreshold(checked) {
    document.getElementById('mergeThresholdRow').classList.toggle('is-hidden', !checked);
  }
```

를 아래로 교체:

```javascript
  function toggleMergeIssueOption(show) {
    const row = document.getElementById('mergeIssueRow');
    if (row) row.classList.toggle('is-hidden', !show);
  }

  function toggleMergeThreshold(checked) {
    document.getElementById('mergeThresholdRow').classList.toggle('is-hidden', !checked);
    toggleMergeIssueOption(checked);
  }
```

- [ ] **Step 3: `applyPreset` 내 `toggleMergeThreshold` 호출 확인**

`applyPreset` 함수 내에 이미 `toggleMergeThreshold(p.auto_merge)` 호출이 있으므로 (`line ~1002`), 프리셋 적용 시에도 `mergeIssueRow` 가시성이 자동으로 동기화된다. 별도 수정 불필요.

- [ ] **Step 4: 서버 실행 후 UI 수동 검증**

```
make run
```

브라우저에서 Settings 페이지 열기:
- `auto_merge` 체크박스 OFF → `mergeIssueRow`가 숨겨져 있는지 확인
- `auto_merge` 체크박스 ON → `mergeThresholdRow`와 `mergeIssueRow` 모두 나타나는지 확인
- 프리셋 "🌱 최소" 적용 → `auto_merge=OFF` → `mergeIssueRow` 숨겨지는지 확인

- [ ] **Step 5: 커밋**

```bash
git add src/templates/settings.html
git commit -m "feat(ui): settings — mergeIssueRow toggle + toggleMergeIssueOption (Phase F.3)"
```

---

### Task 9: 문서 갱신 + 최종 커밋

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/STATE.md`

- [ ] **Step 1: CLAUDE.md — 아키텍처 섹션 갱신**

`src/gate/` 아키텍처 섹션에 두 파일 추가:

```
│   ├── merge_failure_advisor.py # get_advice(reason) — reason tag → 권장 조치 텍스트 (Phase F.3, 순수 함수)
```

`src/notifier/` 아키텍처 섹션에 추가:

```
│   ├── merge_failure_issue.py  # create_merge_failure_issue() — auto-merge 실패 GitHub Issue (Phase F.3)
```

- [ ] **Step 2: CLAUDE.md — MergeAttempt 관측 주석 갱신**

`MergeAttempt 관측 (Phase F.1)` 항목의 마지막 문장:

```
**범위 제한**: `webhook/providers/telegram.py::handle_gate_callback`의 반자동 merge 경로는 미관측(Phase F.2 예정).
```

을 아래로 교체:

```
**범위 제한**: `webhook/providers/telegram.py::handle_gate_callback`의 반자동 merge 경로는 미관측(Phase F.2 예정). **Phase F.3**: `engine.py::_run_auto_merge` 실패 시 `get_advice(reason)` + `create_merge_failure_issue()` 호출 — `auto_merge_issue_on_failure` 필드로 Issue 생성 제어. 5-way sync 적용 대상에 `auto_merge_issue_on_failure` 포함.
```

- [ ] **Step 3: CLAUDE.md — settings.html 구조 규약 JS 헬퍼 목록 갱신**

`toggleMergeIssueOption` 을 신규 헬퍼 목록에 추가:

기존:
```
신규 헬퍼 3종(`onPresetToggle`·`renderPresetDiff`·`flashPresetChanges`)
```

을:
```
신규 헬퍼 4종(`onPresetToggle`·`renderPresetDiff`·`flashPresetChanges`·`toggleMergeIssueOption`)
```

로 교체.

- [ ] **Step 4: docs/STATE.md 수치 갱신**

```
make test-cov
```

출력에서 테스트 개수와 커버리지 읽은 후 STATE.md 갱신:
- 단위 테스트: 기존 1275 + 9개 = **1284개** (실제 수치로 교체)
- 커버리지: 실제 측정치로 교체
- 현재 상태 설명에 `Phase F.3 실패 어드바이저` 추가

- [ ] **Step 5: 최종 테스트 + lint 통과 확인**

```
pytest tests/ -x --ignore=tests/integration -m "not slow"
make lint
```
Expected: 0 failed, pylint 8.0+

- [ ] **Step 6: 커밋 + 푸시**

```bash
git add CLAUDE.md docs/STATE.md
git commit -m "docs: Phase F.3 완료 — CLAUDE.md 아키텍처·규약 갱신 + STATE.md 수치 갱신"
git push
```

---

## Self-Review Checklist

**1. Spec coverage:**
- ✅ merge_failure_advisor.py 순수 함수 모듈 (Task 2)
- ✅ merge_failure_issue.py GitHub Issue 생성 + 24h 중복 차단 (Task 4)
- ✅ engine.py — advice 계산 + Telegram에 포함 + Issue 생성 (Task 6)
- ✅ auto_merge_issue_on_failure Alembic migration 0015 (Task 7)
- ✅ 5-way sync: ORM + RepoConfigData + RepoConfigUpdate (Task 7)
- ✅ settings.html mergeIssueRow + toggleMergeIssueOption (Task 8)
- ✅ CLAUDE.md + STATE.md 갱신 (Task 9)

**2. Placeholder scan:** 없음 — 모든 step에 실제 코드 포함.

**3. Type consistency:**
- `get_advice(reason: str | None) -> str` — Task 2 정의, Task 6에서 동일 시그니처 호출 ✅
- `create_merge_failure_issue(*, github_token, repo_name, pr_number, score, threshold, reason, advice) -> int | None` — Task 4 정의, Task 6에서 동일 키워드 인자 호출 ✅
- `_notify_merge_failure(*, ..., advice: str, ...)` — Task 6 수정, Task 5 테스트에서 동일 파라미터 ✅
- `auto_merge_issue_on_failure: bool = False` — ORM/dataclass/API 모두 Task 7에서 동시 추가 ✅
