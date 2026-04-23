"""n8n notifier — analysis results and GitHub Issue events via envelope payload."""
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

from src.notifier._http import build_safe_client, validate_external_url
from src.scorer.calculator import ScoreResult
from src.constants import N8N_BODY_MAX_BYTES

logger = logging.getLogger(__name__)


def _build_envelope(event_type: str, repo: str, data: dict) -> dict:
    return {
        "event_type": event_type,
        "source": "scamanager",
        "delivered_at": datetime.now(timezone.utc).isoformat(),
        "repo": repo,
        "data": data,
    }


def _signature_headers(payload_bytes: bytes, secret: str) -> dict:
    if not secret:
        return {}
    sig = hmac.new(secret.encode(), payload_bytes, digestmod=hashlib.sha256).hexdigest()
    return {"X-SCAManager-Signature-256": f"sha256={sig}"}


async def _post_to_n8n(webhook_url: str, payload: dict, secret: str) -> None:
    payload_bytes = json.dumps(payload).encode()
    headers = _signature_headers(payload_bytes, secret)
    async with build_safe_client() as client:
        r = await client.post(webhook_url, json=payload, headers=headers)
        r.raise_for_status()


async def notify_n8n(
    *,
    webhook_url: str | None,
    repo_full_name: str,
    commit_sha: str,
    pr_number: int | None,
    score_result: ScoreResult,
    n8n_secret: str = "",
) -> None:
    """n8n Webhook으로 분석 점수 페이로드를 POST한다 (envelope 구조)."""
    if not webhook_url:
        return
    if not validate_external_url(webhook_url):
        logger.warning("notify_n8n: blocked unsafe URL '%s'", webhook_url)
        return
    payload = _build_envelope(
        event_type="analysis",
        repo=repo_full_name,
        data={
            "commit_sha": commit_sha,
            "pr_number": pr_number,
            "score": score_result.total,
            "grade": score_result.grade,
            "breakdown": score_result.breakdown,
        },
    )
    await _post_to_n8n(webhook_url, payload, n8n_secret)


async def notify_n8n_issue(
    *,
    webhook_url: str | None,
    repo_full_name: str,
    action: str,
    issue: dict,
    sender: dict,
    n8n_secret: str = "",
    repo_token: str = "",
) -> None:
    """GitHub Issue 이벤트를 n8n Webhook으로 릴레이한다 (envelope 구조)."""
    if not webhook_url:
        return
    if not validate_external_url(webhook_url):
        logger.warning("notify_n8n_issue: blocked unsafe URL '%s'", webhook_url)
        return

    body = issue.get("body") or ""
    body_bytes = body.encode()
    body_truncated = len(body_bytes) > N8N_BODY_MAX_BYTES
    if body_truncated:
        body = body_bytes[:N8N_BODY_MAX_BYTES].decode(errors="replace")
        issue = {**issue, "body": body}

    payload = _build_envelope(
        event_type="issue",
        repo=repo_full_name,
        data={
            "action": action,
            "issue": issue,
            "sender": sender,
            "body_truncated": body_truncated,
            "repo_token": repo_token,
        },
    )
    await _post_to_n8n(webhook_url, payload, n8n_secret)


# ---------------------------------------------------------------------------
# Notifier Protocol 구현체 (Phase S.3-E) — pipeline.py 에서 이관
# ---------------------------------------------------------------------------
from src.config import settings  # noqa: E402  pylint: disable=wrong-import-position
from src.notifier.registry import NotifyContext, register  # noqa: E402  pylint: disable=wrong-import-position


class _N8nNotifier:
    """n8n 워크플로우 릴레이 채널 — n8n_webhook_url 설정 시 활성."""

    name = "n8n"

    def is_enabled(self, ctx: NotifyContext) -> bool:
        """채널 활성화 여부를 반환한다."""
        return bool(ctx.config and ctx.config.n8n_webhook_url)

    async def send(self, ctx: NotifyContext) -> None:
        """알림을 전송한다."""
        await notify_n8n(
            webhook_url=ctx.config.n8n_webhook_url,
            repo_full_name=ctx.repo_name,
            commit_sha=ctx.commit_sha,
            pr_number=ctx.pr_number,
            score_result=ctx.score_result,
            n8n_secret=settings.n8n_webhook_secret,
        )


register(_N8nNotifier())
