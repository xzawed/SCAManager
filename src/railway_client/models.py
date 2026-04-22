"""Railway webhook 이벤트 데이터 모델 (3-그룹 nested)."""
from dataclasses import dataclass

# 클래스 외부 상수 — frozen dataclass 내 어노테이션 필드로 두면 dataclass field 로 취급됨
RAILWAY_FAILURE_STATUSES: frozenset = frozenset({"FAILED", "BUILD_FAILED"})


@dataclass(frozen=True)
class RailwayProjectInfo:
    """Railway 프로젝트 식별 정보 (어디서 실패했나)."""

    project_id: str
    project_name: str
    environment_name: str


@dataclass(frozen=True)
class RailwayCommitInfo:
    """배포 대상 커밋 정보 (무엇을 배포하려 했나). 모두 Optional."""

    commit_sha: str | None
    commit_message: str | None
    repo_full_name: str | None


@dataclass(frozen=True)
class RailwayDeployEvent:
    """Railway deployment webhook 이벤트 (3-그룹 nested).

    Top-level(3): deployment_id · status · timestamp — 이벤트 본질
    project(3):   project_id · project_name · environment_name
    commit(3):    commit_sha · commit_message · repo_full_name
    """

    deployment_id: str
    status: str          # "FAILED" | "BUILD_FAILED"
    timestamp: str
    project: RailwayProjectInfo
    commit: RailwayCommitInfo
