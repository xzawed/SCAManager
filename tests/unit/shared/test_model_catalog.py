"""메모리 모델 카탈로그의 해석 규칙 — 계열(auto:<line>) · 판 고정 · 기본값 (Issue #1905 ①a Task 1).

Resolution rules of the in-memory model catalog: line choices, pinned ids and the default value.
기대값은 손으로 적은 리터럴이다 — 해석 함수의 결과로 기대값을 만들지 않는다.
Expected values are hand-written literals, never derived from the code under test.
"""
from datetime import datetime, timezone

import pytest

from src.shared import model_catalog as mc


def _d(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


def _entry(model_id: str, line: str, created: datetime, *, lifecycle: str = "active",
           retires: datetime | None = None, structured: bool = True, effort: bool = True) -> mc.ModelEntry:
    return mc.ModelEntry(
        id=model_id, line=line, display_name=model_id, created_at=created,
        deprecated_at=None, retires_at=retires,
        supports_structured_outputs=structured, supports_effort=effort, lifecycle=lifecycle,
    )


# 카탈로그 상태는 tests/unit/conftest.py 의 autouse fixture 가 시험마다 처음 꼴로 되돌린다.
# tests/unit/conftest.py resets the catalog state before every test.


def test_parse_auto_value():
    assert mc.parse_model_value("auto:haiku") == mc.ModelChoice("auto", line="haiku")
    assert mc.parse_model_value(" auto:Sonnet ") == mc.ModelChoice("auto", line="sonnet")
    assert mc.parse_model_value("claude-sonnet-5") == mc.ModelChoice("pinned", model_id="claude-sonnet-5")
    assert mc.parse_model_value(None) == mc.ModelChoice("default")
    assert mc.parse_model_value("  ") == mc.ModelChoice("default")
    with pytest.raises(ValueError):
        mc.parse_model_value("auto:gpt")
    with pytest.raises(ValueError):
        mc.parse_model_value("auto:")


# witness-corpus: 목록 API 의 line 로 SDK ModelLine 의 다른 계열(mythos)과 사람이 쓰는 대문자 · 접두사 꼴 — 네 계열 문자열 밖
_LINE_SPELLINGS = [("mythos", None), ("Haiku", "haiku"), ("Claude-Sonnet", "sonnet"), (" OPUS ", "opus")]


@pytest.mark.parametrize(("raw", "want"), _LINE_SPELLINGS + [
    ("haiku", "haiku"), ("claude-haiku", "haiku"), ("fable", "fable"), ("", None), (None, None),
])
def test_normalise_line(raw, want):
    assert mc.normalise_line(raw) == want


def test_line_of_prefers_snapshot_then_id_shape():
    mc.install_snapshot([_entry("claude-x-special", "opus", _d(2026, 1, 1))], source="api")
    assert mc.line_of("claude-x-special") == "opus"
    assert mc.line_of("claude-haiku-4-5") == "haiku"
    assert mc.line_of("gpt-4o") is None


def test_fallback_catalog_covers_every_known_line_and_default():
    assert {e.line for e in mc.FALLBACK_CATALOG} == mc.KNOWN_LINES
    assert set(mc.FALLBACK_DEFAULT_BY_LINE.values()) <= {e.id for e in mc.FALLBACK_CATALOG}


def test_latest_candidate_is_the_newest_active_model_we_can_call():
    mc.install_snapshot([
        _entry("claude-haiku-4-5", "haiku", _d(2025, 10, 1)),
        _entry("claude-haiku-5-5", "haiku", _d(2026, 10, 1)),
        # 가장 새것이지만 폐기 예정 / newest but deprecated
        _entry("claude-haiku-6-preview", "haiku", _d(2026, 11, 1), lifecycle="deprecated"),
        # 5-5 보다 새것이지만 내려갔다 / newer than 5-5 but retired
        _entry("claude-haiku-5-1", "haiku", _d(2026, 10, 15), lifecycle="retired"),
        # 5-5 보다 새것이지만 구조화 출력이 없다 — 우리 호출 꼴로 부를 수 없다 / newer but no structured outputs
        _entry("claude-haiku-5-9", "haiku", _d(2026, 10, 20), structured=False),
        _entry("claude-sonnet-5-5", "sonnet", _d(2026, 12, 1)),
    ], source="api")
    assert mc.latest_candidate("haiku").id == "claude-haiku-5-5"
    assert mc.latest_candidate("opus") is None


def test_resolve_auto_prefers_verified_over_newest():
    mc.install_snapshot([
        _entry("claude-haiku-4-5", "haiku", _d(2025, 10, 1)),
        _entry("claude-haiku-5-5", "haiku", _d(2026, 10, 1)),
    ], source="api")
    mc.set_verified("haiku", "claude-haiku-4-5")
    assert mc.resolve_model("auto:haiku", default_value="auto:sonnet") == "claude-haiku-4-5"


def test_resolve_without_api_or_history_uses_fallback_default():
    assert mc.snapshot_source() == "fallback"
    assert mc.resolve_model("auto:sonnet", default_value="auto:haiku") == "claude-sonnet-5"
    assert mc.resolve_model("auto:haiku", default_value="auto:haiku") == "claude-haiku-4-5"


def test_resolve_default_uses_setting_value():
    mc.set_verified("haiku", "claude-haiku-5-5")
    assert mc.resolve_model(None, default_value="auto:haiku") == "claude-haiku-5-5"
    assert mc.resolve_model("", default_value="claude-opus-5") == "claude-opus-5"
    with pytest.raises(ValueError):
        mc.resolve_model(None, default_value="  ")


def test_unreadable_value_resolves_to_the_default():
    # 저장값이 모르는 계열이면 기본값으로 — 기본값 자체가 그렇다면 설정 오류로 올린다.
    # An unknown line in a stored value falls back to the default; an unknown line in the default itself raises.
    assert mc.resolve_model("auto:gpt", default_value="auto:haiku") == "claude-haiku-4-5"
    with pytest.raises(ValueError):
        mc.resolve_model(None, default_value="auto:gpt")


def test_pinned_listed_id_passes_through():
    mc.install_snapshot([_entry("claude-opus-5", "opus", _d(2026, 6, 1))], source="api")
    assert mc.resolve_model("claude-opus-5", default_value="auto:haiku") == "claude-opus-5"


def test_pinned_retired_moves_to_line_latest():
    mc.install_snapshot([
        _entry("claude-sonnet-4-5", "sonnet", _d(2025, 9, 29), lifecycle="retired"),
        _entry("claude-sonnet-5-5", "sonnet", _d(2026, 10, 1)),
    ], source="api")
    mc.set_verified("sonnet", "claude-sonnet-5-5")
    assert mc.resolve_model("claude-sonnet-4-5", default_value="auto:haiku") == "claude-sonnet-5-5"


def test_deprecated_pin_stays_even_past_its_retirement_date():
    # SDK 계약: 폐기 예정 판의 지난 retires_at 은 «늦어진 은퇴» 이지 은퇴가 아니다 — 판정은 lifecycle 로만.
    # SDK contract: a past retires_at on a deprecated model means overdue, not retired; lifecycle decides.
    mc.install_snapshot([
        _entry("claude-sonnet-4-5", "sonnet", _d(2025, 9, 29), lifecycle="deprecated", retires=_d(2026, 11, 1)),
        _entry("claude-sonnet-5-5", "sonnet", _d(2026, 10, 1)),
    ], source="api")
    mc.set_verified("sonnet", "claude-sonnet-5-5")
    assert mc.resolve_model("claude-sonnet-4-5", default_value="auto:haiku") == "claude-sonnet-4-5"


def test_pinned_id_missing_from_listing_is_kept():
    # 목록에 없다 ≠ 내려갔다(내려간 판도 기록으로 목록에 남는다) — 별칭 불일치 · 조직 가시성일 수 있어 그대로 부른다.
    # Absent is not retired (retired models stay listed); it may be an alias mismatch or visibility, so keep it.
    mc.install_snapshot([_entry("claude-sonnet-5-5", "sonnet", _d(2026, 10, 1))], source="api")
    mc.set_verified("sonnet", "claude-sonnet-5-5")
    assert mc.resolve_model("claude-sonnet-4-6", default_value="auto:haiku") == "claude-sonnet-4-6"
    assert mc.resolve_model("gpt-4o", default_value="auto:haiku") == "gpt-4o"


def test_dated_listing_ids_match_alias_pins():
    # 목록 API 는 옛 판을 날짜 붙은 전체 id 로 준다 — 저장값 · 기록은 별칭이다(마이그레이션 0050).
    # The listing gives older models their dated full id; stored values and history use the alias.
    mc.install_snapshot([
        _entry("claude-haiku-4-5-20251001", "haiku", _d(2025, 10, 1)),
        _entry("claude-haiku-5-5", "haiku", _d(2026, 10, 1)),
        _entry("claude-sonnet-4-5-20250929", "sonnet", _d(2025, 9, 29), lifecycle="retired"),
        _entry("claude-sonnet-5-5", "sonnet", _d(2026, 10, 1)),
    ], source="api")
    mc.set_verified("haiku", "claude-haiku-5-5")
    mc.set_verified("sonnet", "claude-sonnet-5-5")
    assert mc.entry_for("claude-haiku-4-5").id == "claude-haiku-4-5-20251001"
    assert mc.line_of("claude-haiku-4-5") == "haiku"
    assert mc.resolve_model("claude-haiku-4-5", default_value="auto:sonnet") == "claude-haiku-4-5"
    # 별칭으로 찾은 판이 내려갔으면 그 계열의 검증판으로 / an alias whose listed model is retired moves on
    assert mc.resolve_model("claude-sonnet-4-5", default_value="auto:haiku") == "claude-sonnet-5-5"


def test_failed_model_is_never_resolved():
    mc.set_verified("haiku", "claude-haiku-4-5")
    mc.set_verified("haiku", "claude-haiku-5-5")
    assert mc.verified_latest("haiku") == "claude-haiku-5-5"
    assert mc.previous_verified("haiku") == "claude-haiku-4-5"
    mc.mark_failed("claude-haiku-5-5")
    assert mc.is_failed("claude-haiku-5-5")
    assert mc.resolve_model("auto:haiku", default_value="auto:sonnet") == "claude-haiku-4-5"


def test_server_fallback_support_is_recorded_per_model():
    assert mc.server_fallback_supported("claude-sonnet-5-5") is None
    mc.set_server_fallback("claude-sonnet-5-5", True)
    mc.set_server_fallback("claude-sonnet-5", False)
    assert mc.server_fallback_supported("claude-sonnet-5-5") is True
    assert mc.server_fallback_supported("claude-sonnet-5") is False


def test_failed_without_previous_uses_fallback_default():
    mc.set_verified("haiku", "claude-haiku-5-5")
    mc.mark_failed("claude-haiku-5-5")
    assert mc.resolve_model("auto:haiku", default_value="auto:sonnet") == "claude-haiku-4-5"
