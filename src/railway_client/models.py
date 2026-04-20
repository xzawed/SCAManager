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
