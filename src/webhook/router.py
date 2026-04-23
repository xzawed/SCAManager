"""Webhook router aggregator — `src/webhook/providers/` 의 provider router 를 include.

외부 API: `from src.webhook.router import router` (main.py 용).
실제 endpoint 구현은 공급자별 파일 참조:
- github (push/pr/issues)
- telegram (gate 콜백)
- railway (deploy 실패)

테스트 호환 re-export:
- `_webhook_secret_cache`, `get_webhook_secret` (conftest autouse 클리어)
- `HANDLED_PR_ACTIONS` (구 alias)
"""
from fastapi import APIRouter

from src.constants import PR_HANDLED_ACTIONS
from src.webhook._helpers import _webhook_secret_cache, get_webhook_secret
from src.webhook.providers import github, railway, telegram
from src.webhook.providers.github import (
    _extract_closing_issue_numbers,
    _handle_issues_event,
    _handle_merged_pr_event,
)
from src.webhook.providers.telegram import (
    _parse_gate_callback,
    handle_gate_callback,
)
from src.webhook.providers.railway import _handle_railway_deploy_failure

router = APIRouter()
router.include_router(github.router)
router.include_router(telegram.router)
router.include_router(railway.router)

# 하위 호환 별칭 (conftest.py · 기존 테스트가 참조)
HANDLED_PR_ACTIONS = PR_HANDLED_ACTIONS
_get_webhook_secret = get_webhook_secret

__all__ = [
    "router",
    "_webhook_secret_cache",
    "_get_webhook_secret",
    "get_webhook_secret",
    "HANDLED_PR_ACTIONS",
    "_extract_closing_issue_numbers",
    "_handle_issues_event",
    "_handle_merged_pr_event",
    "_parse_gate_callback",
    "handle_gate_callback",
    "_handle_railway_deploy_failure",
]
