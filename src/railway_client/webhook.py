"""Railway webhook payload 파싱."""
import logging
from src.railway_client.models import (
    RAILWAY_FAILURE_STATUSES,
    RailwayCommitInfo,
    RailwayDeployEvent,
    RailwayProjectInfo,
)

logger = logging.getLogger(__name__)


def parse_railway_payload(body: dict) -> RailwayDeployEvent | None:
    """Railway webhook JSON 을 RailwayDeployEvent 로 파싱.

    Returns:
        RailwayDeployEvent — 빌드 실패 이벤트인 경우 (nested 구조).
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

    project_raw = body.get("project") or {}
    environment = body.get("environment") or {}
    commit_raw = deployment.get("meta") or {}

    return RailwayDeployEvent(
        deployment_id=deployment_id,
        status=status,
        timestamp=body.get("timestamp", ""),
        project=RailwayProjectInfo(
            project_id=project_raw.get("id", ""),
            project_name=project_raw.get("name", ""),
            environment_name=environment.get("name", ""),
        ),
        commit=RailwayCommitInfo(
            commit_sha=commit_raw.get("commitSha") or None,
            commit_message=commit_raw.get("commitMessage") or None,
            repo_full_name=commit_raw.get("repo") or None,
        ),
    )
