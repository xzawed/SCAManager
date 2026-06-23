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


def test_repo_full_name_is_checked_in_data_comparison():
    # repo_full_name 이 ORM↔Data 비교에서는 누락 시 검출되는지 단위 검증.
    # Unit check: repo_full_name absence in Data triggers a violation (not exempt there).
    #
    # ORM 에 repo_full_name 존재, Data 에 없음 → 누락 보고 기대.
    # repo_full_name exists in ORM but not in Data → expect a missing-field violation.
    import types
    from pathlib import Path

    def _fake_read(self: Path, **_kw: object) -> str:
        # ORM: repo_full_name + auto_merge 두 컬럼 보유
        # ORM: has both repo_full_name and auto_merge columns
        if "repo_config" in self.parts[-1]:
            return (
                "class RepoConfig(Base):\n"
                "    repo_full_name = Column(String)\n"
                "    auto_merge = Column(Boolean)\n"
            )
        # Data: repo_full_name 없음 (누락 시나리오)
        # Data: repo_full_name absent (missing scenario)
        if "manager" in self.parts[-1]:
            return "class RepoConfigData:\n    auto_merge: bool = False\n"
        # Update: repo_full_name 없음 (_UPDATE_ONLY_EXEMPT 에 의해 면제)
        # Update: repo_full_name absent (exempted by _UPDATE_ONLY_EXEMPT)
        return "class RepoConfigUpdate:\n    auto_merge: bool = False\n"

    orig = Path.read_text

    class _FakeRoot:
        """경로 조합 연산자를 지원하는 가짜 루트 객체.
        Fake root object that supports path-join operators.
        """

        def __truediv__(self, other: str) -> "_FakeRoot":
            return _FakePath(other)

    class _FakePath:
        def __init__(self, name: str) -> None:
            self.parts = (name,)
            self._name = name

        def __truediv__(self, other: str) -> "_FakePath":
            p = _FakePath(other)
            p.parts = (*self.parts, other)
            return p

        def read_text(self, **_kw: object) -> str:
            return _fake_read(self, **_kw)  # type: ignore[arg-type]

    ok, msgs = mod.check_sync(_FakeRoot())  # type: ignore[arg-type]
    # Data 비교에서 repo_full_name 누락 보고 기대
    # Expect a missing-field report from the Data comparison
    assert not ok
    assert any("RepoConfigData" in m and "repo_full_name" in m for m in msgs)
    # Update 비교에서는 repo_full_name 관련 보고 없음 (_UPDATE_ONLY_EXEMPT 동작 확인)
    # No repo_full_name violation from the Update comparison (_UPDATE_ONLY_EXEMPT in effect)
    assert not any("RepoConfigUpdate" in m and "repo_full_name" in m for m in msgs)


def test_repo_full_name_is_exempt_in_update_comparison():
    # repo_full_name 이 ORM↔Update 비교에서는 면제되는지 단위 검증.
    # Unit check: repo_full_name absence in Update does NOT trigger a violation.
    #
    # ORM·Data 양쪽에 repo_full_name 존재, Update 에만 없음 → 전체 통과 기대.
    # repo_full_name in both ORM and Data, absent only in Update → expect overall pass.

    class _FakeRoot:
        """경로 조합 연산자를 지원하는 가짜 루트 객체.
        Fake root object that supports path-join operators.
        """

        def __truediv__(self, other: str) -> "_FakePath":
            return _FakePath(other)

    class _FakePath:
        def __init__(self, name: str) -> None:
            self.parts = (name,)

        def __truediv__(self, other: str) -> "_FakePath":
            p = _FakePath(other)
            p.parts = (*self.parts, other)
            return p

        def read_text(self, **_kw: object) -> str:
            last = self.parts[-1]
            if "repo_config" in last:
                # ORM: repo_full_name + auto_merge
                return (
                    "class RepoConfig(Base):\n"
                    "    repo_full_name = Column(String)\n"
                    "    auto_merge = Column(Boolean)\n"
                )
            if "manager" in last:
                # Data: repo_full_name 포함 (ORM↔Data 검사 통과)
                # Data: includes repo_full_name (ORM↔Data check passes)
                return (
                    "class RepoConfigData:\n"
                    "    repo_full_name: str\n"
                    "    auto_merge: bool = False\n"
                )
            # Update: repo_full_name 없음 — _UPDATE_ONLY_EXEMPT 로 면제돼야 함
            # Update: repo_full_name absent — must be exempt via _UPDATE_ONLY_EXEMPT
            return "class RepoConfigUpdate:\n    auto_merge: bool = False\n"

    ok, msgs = mod.check_sync(_FakeRoot())  # type: ignore[arg-type]
    # Update 에 repo_full_name 없어도 전체 통과
    # Even without repo_full_name in Update, overall check must pass
    assert ok, msgs
