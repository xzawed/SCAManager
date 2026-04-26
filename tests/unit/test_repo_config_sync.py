"""RepoConfig 5-way 동기화 정적 검사.

Static check: RepoConfig ORM, RepoConfigData dataclass, RepoConfigUpdate API body
세 계층의 필드명 집합이 서로 일치하는지 검사한다. 어느 한 곳에 필드를 추가하고
다른 곳을 빠트리면 → REST API가 해당 필드를 NULL로 덮어쓰거나 UI에서 설정이
사라지는 버그가 발생한다.

5-way sync 계층 (CLAUDE.md 정의):
  ORM(RepoConfig) ↔ dataclass(RepoConfigData) ↔ API body(RepoConfigUpdate)
  ↔ UI 폼 ↔ PRESETS

이 테스트는 기계로 검증 가능한 3개 계층을 자동으로 검사한다.
UI 폼·PRESETS 계층은 PR 리뷰 체크리스트로 보완한다.
"""

from dataclasses import fields

from src.api.repos import RepoConfigUpdate
from src.config_manager.manager import RepoConfigData
from src.models.repo_config import RepoConfig

# ORM 컬럼 중 RepoConfigData 범위 밖 컬럼 — 인프라/인증 관련으로 별도 관리됨
# ORM columns outside RepoConfigData scope — managed separately as infra/auth fields.
_ORM_INFRA_COLUMNS = frozenset({
    "id",
    "repo_full_name",
    "created_at",
    "updated_at",
    "hook_token",          # CLI hook 인증 토큰 — repo 등록 시 자동 생성
    "railway_webhook_token",  # Railway webhook 인증 — ORM 직접 관리
    "railway_api_token",   # Railway API 토큰 — Fernet 암호화 저장
})


def test_repo_config_data_matches_api_update_body():
    """RepoConfigData 필드가 RepoConfigUpdate Pydantic 모델 필드와 정확히 일치해야 한다.

    어느 한쪽에 필드를 추가하고 다른 쪽에서 빠지면 REST API PUT 요청이
    해당 필드를 기본값(예: False / None)으로 덮어쓰는 버그가 발생한다.
    """
    data_fields = {f.name for f in fields(RepoConfigData) if f.name != "repo_full_name"}
    api_fields = set(RepoConfigUpdate.model_fields.keys())

    in_data_not_api = data_fields - api_fields
    in_api_not_data = api_fields - data_fields

    assert not in_data_not_api, (
        f"\nRepoConfigData에 있지만 RepoConfigUpdate에 없는 필드: {in_data_not_api}\n"
        "수정: src/api/repos.py의 RepoConfigUpdate에 동일 필드 추가 후 PR 제출"
    )
    assert not in_api_not_data, (
        f"\nRepoConfigUpdate에 있지만 RepoConfigData에 없는 필드: {in_api_not_data}\n"
        "수정: src/config_manager/manager.py의 RepoConfigData에 동일 필드 추가 후 PR 제출"
    )


def test_orm_config_columns_covered_by_repo_config_data():
    """ORM RepoConfig 컬럼(인프라 제외)이 RepoConfigData에 모두 반영되어야 한다.

    ORM에 컬럼을 추가하고 RepoConfigData에 추가하지 않으면 upsert 시 해당 컬럼이
    항상 기본값(DEFAULT)으로 리셋된다.
    """
    orm_columns = {c.name for c in RepoConfig.__table__.columns} - _ORM_INFRA_COLUMNS
    data_fields = {f.name for f in fields(RepoConfigData) if f.name != "repo_full_name"}

    in_orm_not_data = orm_columns - data_fields
    in_data_not_orm = data_fields - orm_columns

    assert not in_orm_not_data, (
        f"\nORM 컬럼에 있지만 RepoConfigData에 없는 필드: {in_orm_not_data}\n"
        "수정: src/config_manager/manager.py의 RepoConfigData에 동일 필드 추가"
    )
    assert not in_data_not_orm, (
        f"\nRepoConfigData에 있지만 ORM 컬럼에 없는 필드: {in_data_not_orm}\n"
        "수정: src/models/repo_config.py에 Column 추가 + make revision 실행"
    )


def test_repo_config_update_field_count_matches_data():
    """필드 수가 일치하는지 추가로 검증 — 위 두 테스트의 sanity check."""
    data_count = sum(1 for f in fields(RepoConfigData) if f.name != "repo_full_name")
    api_count = len(RepoConfigUpdate.model_fields)
    assert data_count == api_count, (
        f"RepoConfigData 필드 수({data_count}) ≠ RepoConfigUpdate 필드 수({api_count})\n"
        "3-way 동기화 검사 위 두 테스트를 확인하세요."
    )
