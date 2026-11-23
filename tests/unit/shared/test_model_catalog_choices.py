"""설정 화면의 리뷰 모델 선택지 — «최신 계열» 넷과 판 고정 (Issue #1905 ③b).

The settings screen's review-model choices: four «latest of a line» options and the pinned models.
카탈로그 상태는 tests/unit/conftest.py 의 autouse fixture 가 시험마다 처음 꼴(기본 카탈로그)로 되돌린다.
The catalog state is reset to the fallback catalog before every test.
"""
from datetime import datetime, timezone

from src.shared import model_catalog as mc


def _d(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


def _entry(model_id: str, line: str, created: datetime, *, lifecycle: str = "active",
           structured: bool = True) -> mc.ModelEntry:
    return mc.ModelEntry(
        id=model_id, line=line, display_name=f"Claude {model_id}", created_at=created, deprecated_at=None,
        retires_at=None, supports_structured_outputs=structured, supports_effort=True, lifecycle=lifecycle,
    )


def test_fallback_choices_offer_the_four_lines_and_the_fallback_models():
    auto, pinned = mc.catalog_choices()
    assert [(c.value, c.line, c.current_id) for c in auto] == [
        ("auto:haiku", "haiku", "claude-haiku-4-5"), ("auto:sonnet", "sonnet", "claude-sonnet-5"),
        ("auto:opus", "opus", "claude-opus-5"), ("auto:fable", "fable", "claude-fable-5-1"),
    ]
    assert sorted(c.value for c in pinned) == sorted(e.id for e in mc.FALLBACK_CATALOG)
    assert all(c.current_name for c in auto)


def _listing():
    mc.install_snapshot([
        _entry("claude-haiku-4-5-20251001", "haiku", _d(2025, 10, 1)),
        _entry("claude-haiku-5-5", "haiku", _d(2026, 9, 1)),
        _entry("claude-sonnet-4-5-20250929", "sonnet", _d(2025, 9, 29), lifecycle="deprecated"),
        _entry("claude-sonnet-4-6", "sonnet", _d(2026, 2, 1), lifecycle="retired"),
        _entry("claude-sonnet-5-5", "sonnet", _d(2026, 10, 1)),
        _entry("claude-opus-x", "opus", _d(2026, 1, 1), structured=False),
        _entry("gpt-unknown", "unknown", _d(2026, 1, 1)),
    ], source="api")


def test_dated_models_are_offered_by_the_alias_stored_values_use():
    _listing()
    _auto, pinned = mc.catalog_choices()
    values = [c.value for c in pinned]
    assert "claude-haiku-4-5" in values and "claude-haiku-4-5-20251001" not in values


def test_retired_unstructured_and_unknown_line_models_are_not_offered():
    _listing()
    _auto, pinned = mc.catalog_choices()
    assert {c.value for c in pinned} == {"claude-haiku-5-5", "claude-haiku-4-5", "claude-sonnet-5-5",
                                         "claude-sonnet-4-5"}


def test_pinned_models_run_line_by_line_newest_first():
    _listing()
    _auto, pinned = mc.catalog_choices()
    assert [c.value for c in pinned] == ["claude-haiku-5-5", "claude-haiku-4-5", "claude-sonnet-5-5",
                                         "claude-sonnet-4-5"]


def test_flags_say_retiring_unverified_and_failed():
    _listing()
    mc.set_verified("haiku", "claude-haiku-5-5")
    mc.mark_failed("claude-haiku-4-5-20251001")
    _auto, pinned = mc.catalog_choices()
    flags = {c.value: (c.retiring, c.unverified, c.failed) for c in pinned}
    assert flags == {
        "claude-haiku-5-5": (False, False, False),   # 검증판 / verified
        "claude-haiku-4-5": (False, False, True),    # 시험 · 실제 호출에서 실패 / failed
        "claude-sonnet-5-5": (False, True, False),   # 계열 최신 후보 · 아직 검증 전 / newest, not yet verified
        "claude-sonnet-4-5": (True, False, False),   # 폐기 예정 / deprecated
    }


def test_auto_choices_name_the_model_each_line_runs_now():
    _listing()
    mc.set_verified("haiku", "claude-haiku-5-5")
    auto, _pinned = mc.catalog_choices()
    current = {c.value: (c.current_id, c.current_name) for c in auto}
    assert current["auto:haiku"] == ("claude-haiku-5-5", "Claude claude-haiku-5-5")
    # 검증판이 없는 계열은 기본 판 — 목록에 없으면 기본 카탈로그의 이름 / an unverified line runs its fallback default
    fallback_names = {e.id: e.display_name for e in mc.FALLBACK_CATALOG}
    assert current["auto:sonnet"] == ("claude-sonnet-5", fallback_names["claude-sonnet-5"])


def test_a_dated_model_whose_alias_is_another_real_model_keeps_its_own_id():
    mc.install_snapshot([
        _entry("claude-opus-9", "opus", _d(2026, 5, 1)),
        _entry("claude-opus-9-20260101", "opus", _d(2026, 1, 1)),
    ], source="api")
    _auto, pinned = mc.catalog_choices()
    assert [c.value for c in pinned] == ["claude-opus-9", "claude-opus-9-20260101"]
    assert all(mc.validate_model_value(c.value) == c.value for c in pinned)


def test_the_line_order_covers_every_known_line():
    # 순서표에 없는 계열이 목록에 오면 설정 화면이 KeyError 로 500 이 된다(③b 검토 Minor 4)
    # A known line missing from the order would make the settings page fail.
    assert set(mc._LINE_ORDER) == set(mc.KNOWN_LINES)  # pylint: disable=protected-access


def test_an_id_whose_value_would_be_empty_is_not_offered():
    # 날짜만 있는 id 는 별칭이 빈 값이 되어 «전역 기본값»(값 "")과 겹친다 — 선택지로 만들지 않는다(Grok 583c612c)
    # An id that is only a date suffix would alias to "" and collide with the global-default option.
    mc.install_snapshot([_entry("-20260101", "opus", _d(2026, 1, 1)), _entry("claude-opus-9", "opus", _d(2026, 2, 1))],
                        source="api")
    _auto, pinned = mc.catalog_choices()
    assert [c.value for c in pinned] == ["claude-opus-9"]
