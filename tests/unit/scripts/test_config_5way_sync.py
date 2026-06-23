"""H3 5-way config 싱크 체커 — RepoConfig ORM↔Data↔Update 필드 집합 정합."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "scripts"))

import check_config_5way_sync as mod  # noqa: E402


def test_5way_sync_passes_on_current_repo():
    ok, msgs = mod.check_sync(_ROOT)
    assert ok, msgs


def test_orm_columns_extracts_field_names():
    src = (
        "class RepoConfig(Base):\n"
        "    id = Column(Integer)\n"
        "    auto_merge = Column(Boolean)\n"
    )
    assert mod._orm_columns(src, "RepoConfig") == {"id", "auto_merge"}


def test_annotated_fields_extracts():
    src = (
        "class RepoConfigData:\n"
        "    repo_full_name: str\n"
        "    auto_merge: bool = False\n"
    )
    assert mod._annotated_fields(src, "RepoConfigData") == {"repo_full_name", "auto_merge"}


def test_form_names_extracts():
    html = '<input name="auto_merge"><select name="approve_mode">'
    assert mod._form_names(html) == {"auto_merge", "approve_mode"}
