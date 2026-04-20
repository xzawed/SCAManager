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
