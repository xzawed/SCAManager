"""메모리 모델 카탈로그의 해석 규칙 — 계열(auto:<line>) · 판 고정 · 기본값 (Issue #1905 ①a Task 1).

Resolution rules of the in-memory model catalog: line choices, pinned ids and the default value.
기대값은 손으로 적은 리터럴이다 — 해석 함수의 결과로 기대값을 만들지 않는다.
Expected values are hand-written literals, never derived from the code under test.
"""
from datetime import datetime, timezone

import pytest

from src.shared import model_catalog as mc

_NOW = datetime(2026, 11, 21, tzinfo=timezone.utc)


def _d(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


def _entry(model_id: str, line: str, created: datetime, *, deprecated: datetime | None = None,
           retires: datetime | None = None, effort: bool = True) -> mc.ModelEntry:
    return mc.ModelEntry(
        id=model_id, line=line, display_name=model_id, created_at=created,
        deprecated_at=deprecated, retires_at=retires,
        supports_structured_outputs=True, supports_effort=effort,
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


@pytest.mark.parametrize(("raw", "want"), [
    ("haiku", "haiku"), ("claude-haiku", "haiku"), ("Sonnet", "sonnet"), (" OPUS ", "opus"),
    ("fable", "fable"), ("mythos", None), ("", None), (None, None),
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


def test_latest_candidate_skips_deprecated_and_retired():
    mc.install_snapshot([
        _entry("claude-haiku-4-5", "haiku", _d(2025, 10, 1)),
        _entry("claude-haiku-5-5", "haiku", _d(2026, 10, 1)),
        # 가장 새것이지만 폐기 예정 / newest but deprecated
        _entry("claude-haiku-6-preview", "haiku", _d(2026, 11, 1), deprecated=_d(2026, 11, 10)),
        # 5-5 보다 새것이지만 폐기일이 지났다 / newer than 5-5 but already retired
        _entry("claude-haiku-5-1", "haiku", _d(2026, 10, 15), retires=_d(2026, 11, 20)),
        _entry("claude-sonnet-5-5", "sonnet", _d(2026, 12, 1)),
    ], source="api")
    assert mc.latest_candidate("haiku", now=_NOW).id == "claude-haiku-5-5"
    assert mc.latest_candidate("opus", now=_NOW) is None


def test_resolve_auto_prefers_verified_over_newest():
    mc.install_snapshot([
        _entry("claude-haiku-4-5", "haiku", _d(2025, 10, 1)),
        _entry("claude-haiku-5-5", "haiku", _d(2026, 10, 1)),
    ], source="api")
    mc.set_verified("haiku", "claude-haiku-4-5")
    assert mc.resolve_model("auto:haiku", default_value="auto:sonnet", now=_NOW) == "claude-haiku-4-5"


def test_resolve_without_api_or_history_uses_fallback_default():
    assert mc.snapshot_source() == "fallback"
    assert mc.resolve_model("auto:sonnet", default_value="auto:haiku", now=_NOW) == "claude-sonnet-5"
    assert mc.resolve_model("auto:haiku", default_value="auto:haiku", now=_NOW) == "claude-haiku-4-5"


def test_resolve_default_uses_setting_value():
    mc.set_verified("haiku", "claude-haiku-5-5")
    assert mc.resolve_model(None, default_value="auto:haiku", now=_NOW) == "claude-haiku-5-5"
    assert mc.resolve_model("", default_value="claude-opus-5", now=_NOW) == "claude-opus-5"
    with pytest.raises(ValueError):
        mc.resolve_model(None, default_value="  ", now=_NOW)


def test_unreadable_value_resolves_to_the_default():
    # 저장값이 모르는 계열이면 기본값으로 — 기본값 자체가 그렇다면 설정 오류로 올린다.
    # An unknown line in a stored value falls back to the default; an unknown line in the default itself raises.
    assert mc.resolve_model("auto:gpt", default_value="auto:haiku", now=_NOW) == "claude-haiku-4-5"
    with pytest.raises(ValueError):
        mc.resolve_model(None, default_value="auto:gpt", now=_NOW)


def test_pinned_listed_id_passes_through():
    mc.install_snapshot([_entry("claude-opus-5", "opus", _d(2026, 6, 1))], source="api")
    assert mc.resolve_model("claude-opus-5", default_value="auto:haiku", now=_NOW) == "claude-opus-5"


def test_pinned_retired_moves_to_line_latest():
    mc.install_snapshot([
        _entry("claude-sonnet-4-5", "sonnet", _d(2025, 9, 29), deprecated=_d(2026, 8, 1), retires=_d(2026, 11, 20)),
        _entry("claude-sonnet-5-5", "sonnet", _d(2026, 10, 1)),
    ], source="api")
    mc.set_verified("sonnet", "claude-sonnet-5-5")
    assert mc.resolve_model("claude-sonnet-4-5", default_value="auto:haiku", now=_NOW) == "claude-sonnet-5-5"
    # 폐기일 전이면 고정 그대로 / before the retirement date the pin stays
    assert mc.resolve_model("claude-sonnet-4-5", default_value="auto:haiku", now=_d(2026, 11, 1)) == "claude-sonnet-4-5"


def test_pinned_id_missing_from_listing_moves_to_line_latest():
    mc.install_snapshot([_entry("claude-sonnet-5-5", "sonnet", _d(2026, 10, 1))], source="api")
    mc.set_verified("sonnet", "claude-sonnet-5-5")
    assert mc.resolve_model("claude-sonnet-4-6", default_value="auto:haiku", now=_NOW) == "claude-sonnet-5-5"
    # 계열을 모르는 id 는 그대로 둔다 / an id of no known line is left as is
    assert mc.resolve_model("gpt-4o", default_value="auto:haiku", now=_NOW) == "gpt-4o"


def test_pinned_id_stays_when_listing_is_only_the_fallback():
    mc.set_verified("sonnet", "claude-sonnet-5-5")
    assert mc.snapshot_source() == "fallback"
    assert mc.resolve_model("claude-sonnet-4-6", default_value="auto:haiku", now=_NOW) == "claude-sonnet-4-6"


def test_failed_model_is_never_resolved():
    mc.set_verified("haiku", "claude-haiku-4-5")
    mc.set_verified("haiku", "claude-haiku-5-5")
    assert mc.verified_latest("haiku") == "claude-haiku-5-5"
    assert mc.previous_verified("haiku") == "claude-haiku-4-5"
    mc.mark_failed("claude-haiku-5-5")
    assert mc.is_failed("claude-haiku-5-5")
    assert mc.resolve_model("auto:haiku", default_value="auto:sonnet", now=_NOW) == "claude-haiku-4-5"


def test_server_fallback_support_is_recorded_per_model():
    assert mc.server_fallback_supported("claude-sonnet-5-5") is None
    mc.set_server_fallback("claude-sonnet-5-5", True)
    mc.set_server_fallback("claude-sonnet-5", False)
    assert mc.server_fallback_supported("claude-sonnet-5-5") is True
    assert mc.server_fallback_supported("claude-sonnet-5") is False


def test_failed_without_previous_uses_fallback_default():
    mc.set_verified("haiku", "claude-haiku-5-5")
    mc.mark_failed("claude-haiku-5-5")
    assert mc.resolve_model("auto:haiku", default_value="auto:sonnet", now=_NOW) == "claude-haiku-4-5"
