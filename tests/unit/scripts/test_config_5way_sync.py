"""H3 3-way config 싱크 체커 — RepoConfig ORM↔Data↔Update 필드 집합 정합."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "scripts"))

import check_config_5way_sync as mod  # noqa: E402


def test_5way_sync_passes_on_current_repo():
    # 현재 레포가 3-way 정합을 통과하는지 통합 검증.
    # Integration check: current repo must pass the 3-way parity check.
    ok, msgs = mod.check_sync(_ROOT)
    assert ok, msgs


def test_orm_columns_extracts_field_names():
    # ORM Column 할당에서 필드명만 추출하는지 단위 검증.
    # Unit check: only Column-assigned names are extracted from the ORM class.
    src = (
        "class RepoConfig(Base):\n"
        "    id = Column(Integer)\n"
        "    auto_merge = Column(Boolean)\n"
    )
    assert mod._orm_columns(src, "RepoConfig") == {"id", "auto_merge"}


def test_annotated_fields_extracts():
    # 어노테이션 필드명이 올바르게 추출되는지 단위 검증.
    # Unit check: annotated field names are correctly extracted from a Pydantic/dataclass.
    src = (
        "class RepoConfigData:\n"
        "    repo_full_name: str\n"
        "    auto_merge: bool = False\n"
    )
    assert mod._annotated_fields(src, "RepoConfigData") == {"repo_full_name", "auto_merge"}
