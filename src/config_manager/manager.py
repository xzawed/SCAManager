"""Repository configuration manager — get and upsert RepoConfig records."""
from dataclasses import dataclass, field, fields
from sqlalchemy.orm import Session
from src.constants import (
    GATE_DEFAULT_APPROVE_THRESHOLD,
    GATE_DEFAULT_REJECT_THRESHOLD,
    GATE_DEFAULT_MERGE_THRESHOLD,
)
from src.models.repo_config import RepoConfig


@dataclass
class RepoConfigData:  # pylint: disable=too-many-instance-attributes
    """RepoConfig ORM 레코드를 Python 데이터클래스로 표현한다 (단일 출처)."""

    repo_full_name: str
    pr_review_comment: bool = True
    approve_mode: str = "disabled"
    approve_threshold: int = GATE_DEFAULT_APPROVE_THRESHOLD
    reject_threshold: int = GATE_DEFAULT_REJECT_THRESHOLD
    notify_chat_id: str | None = None
    n8n_webhook_url: str | None = None
    discord_webhook_url: str | None = None
    slack_webhook_url: str | None = None
    custom_webhook_url: str | None = None
    email_recipients: str | None = None
    auto_merge: bool = False
    merge_threshold: int = GATE_DEFAULT_MERGE_THRESHOLD
    commit_comment: bool = False
    create_issue: bool = False
    railway_deploy_alerts: bool = False
    auto_merge_issue_on_failure: bool = False
    # Phase 1 PR-1c (사이클 84) — 다국어 지원 리포별 알림 언어 override
    # NULL = 사용자 preferred_language fallback (Phase 3 PR-9~11 알림 채널 영역)
    notification_language: str | None = None
    # 리포별 Claude 코드리뷰 모델 override (Alembic 0032)
    # NULL = settings.claude_review_model 전역 기본값 사용
    review_model: str | None = None
    # per-repo 비활성화 도구 목록 — JSON 배열, 기본값 빈 배열 (Alembic 0036)
    # Per-repo disabled analyzer names — JSON array, defaults to empty list (Alembic 0036)
    disabled_tools: list = field(default_factory=list)
    # 리포별 AI 코드리뷰 on/off (Alembic 0042) — default True (기존 동작 보존)
    # Per-repo AI code review on/off — default True (preserves existing behavior)
    ai_review_enabled: bool = True
    # leaderboard_opt_in 폐기 (그룹 60 사용자 결정 정정 — alembic 0025)


def _config_field_names() -> list[str]:
    """RepoConfigData의 필드명 목록 (repo_full_name 제외). 새 채널은 RepoConfigData에만 추가."""
    return [f.name for f in fields(RepoConfigData) if f.name != "repo_full_name"]


def get_repo_config(db: Session, repo_full_name: str) -> RepoConfigData:
    """DB에서 RepoConfig를 조회하여 RepoConfigData로 반환. 미존재 시 기본값 반환."""
    record = db.query(RepoConfig).filter_by(repo_full_name=repo_full_name).first()
    if record is None:
        return RepoConfigData(repo_full_name=repo_full_name)
    kwargs = {name: getattr(record, name) for name in _config_field_names()}
    return RepoConfigData(repo_full_name=record.repo_full_name, **kwargs)


def _validate_thresholds(data: RepoConfigData) -> None:
    """threshold 3종의 범위(0~100)와 상호 불변식을 검증한다. 위반 시 ValueError.

    Validate the three thresholds' range (0-100) and mutual invariants; raises ValueError.

    🔴 여기가 **유일한 choke point** — UI 폼(`ui/routes/settings.py`)과 REST API(`api/repos.py`)가
    모두 `upsert_repo_config` 를 지난다. REST 는 `RepoConfigUpdate` 의 `Field(ge=0, le=100)` 로
    이미 범위를 막지만 UI 폼은 `int(form.get(...))` 뿐이라 -999/101 이 그대로 저장됐다
    (계층 비대칭). UI 라우트는 기존 `except ValueError → ?save_error=1` 로 표면화한다.

    🔴 This is the single choke point — both the UI form and the REST API funnel through
    `upsert_repo_config`. REST already bounds values via pydantic; the UI form did not.
    """
    for name in ("approve_threshold", "reject_threshold", "merge_threshold"):
        value = getattr(data, name)
        if not 0 <= value <= 100:
            raise ValueError(f"{name}({value})은 0~100 범위여야 합니다 (점수 범위와 정합)")

    if data.approve_threshold < data.reject_threshold:
        raise ValueError(
            f"approve_threshold({data.approve_threshold})는 "
            f"reject_threshold({data.reject_threshold}) 이상이어야 합니다"
        )

    # 🔴 반려할 점수를 머지하는 것은 자기모순 — 이 불변식이 이 가드의 **보안적 의미**다.
    # 범위 검증만으로는 부족하다: `merge_threshold=0` 은 0~100 **안**이고 `score >= 0` 은
    # 항상 참이라 `-999` 와 효과가 같다. reject 와의 관계로만 모순을 잡을 수 있다.
    # 단, reject_threshold=0(= 아무것도 반려 안 함) 이면 merge_threshold=0 은 모순이 아니라
    # 의도적 "전부 머지" 다 — 이 가드는 모순을 막는 것이지 관대한 설정을 금지하지 않는다.
    # 🔴 Merging a score you would reject is self-contradictory — this is the security-meaningful
    # part. A range check alone is not enough: 0 is in range and behaves like -999. When
    # reject_threshold is 0 the user rejects nothing, so merge_threshold=0 is intent, not a
    # contradiction.
    if data.merge_threshold < data.reject_threshold:
        raise ValueError(
            f"merge_threshold({data.merge_threshold})는 "
            f"reject_threshold({data.reject_threshold}) 이상이어야 합니다 "
            f"(반려할 점수를 머지할 수 없음)"
        )


def upsert_repo_config(db: Session, data: RepoConfigData) -> RepoConfig:
    """RepoConfig를 INSERT 또는 UPDATE(Upsert)한다.

    Raises:
        ValueError: threshold 가 0~100 밖이거나 approve < reject / merge < reject 인 경우
    """
    _validate_thresholds(data)
    field_names = _config_field_names()
    record = db.query(RepoConfig).filter_by(repo_full_name=data.repo_full_name).first()
    if record is None:
        kwargs = {name: getattr(data, name) for name in field_names}
        record = RepoConfig(repo_full_name=data.repo_full_name, **kwargs)
        db.add(record)
    else:
        for name in field_names:
            setattr(record, name, getattr(data, name))
    db.commit()
    db.refresh(record)
    return record
