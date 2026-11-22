"""판 단위 요율 — 프롬프트 길이 구간 · 판별 캐시 읽기 · 모르는 판은 같은 계열의 가장 새 판 요율로 «추정» (Issue #1905 ②).

Per-model rates: prompt-size tiers, per-model cache reads, and an "estimated" rate for unknown models.
값은 Anthropic 요율(claude-api 참조 2026-11) — 표는 `src/shared/claude_metrics.py::_MODEL_RATES` 하나다.
"""
import pytest

from src.repositories import claude_api_cost_repo
from src.shared import claude_metrics as cm
from src.shared import model_catalog as mc


def _cost(model: str, *, input_tokens: int = 0, output_tokens: int = 0, cache_read: int = 0,
          cache_creation: int = 0) -> float:
    return cm.estimate_claude_cost_usd(model=model, input_tokens=input_tokens, output_tokens=output_tokens,
                                       cache_read_tokens=cache_read, cache_creation_tokens=cache_creation)


def test_haiku_5_5_tier_by_prompt_size():
    # 프롬프트 ≤100K 토큰이면 $0.10/$0.50, 넘으면 요청 전체가 $0.50/$2.50 — 캐시 토큰도 프롬프트 길이에 든다
    # ≤100K prompt tokens bills $0.10/$0.50; above that the whole request bills $0.50/$2.50 (cached tokens count).
    assert _cost("claude-haiku-5-5", input_tokens=50_000, output_tokens=1_000) == pytest.approx(
        (50_000 * 0.10 + 1_000 * 0.50) / 1e6)
    assert _cost("claude-haiku-5-5", input_tokens=150_000, output_tokens=1_000) == pytest.approx(
        (150_000 * 0.50 + 1_000 * 2.50) / 1e6)
    assert _cost("claude-haiku-5-5", input_tokens=60_000, cache_read=60_000) == pytest.approx(
        (60_000 * 0.50 + 60_000 * 0.50 * 0.1) / 1e6)
    assert _cost("claude-haiku-5-5", input_tokens=100_000) == pytest.approx(100_000 * 0.10 / 1e6)  # 경계는 아래 구간


def test_cache_read_uses_model_rate_when_given():
    assert _cost("claude-sonnet-5-5", cache_read=1_000_000) == pytest.approx(0.10)
    assert _cost("claude-opus-5-5", cache_read=1_000_000) == pytest.approx(0.20)
    assert _cost("claude-fable-5-2", cache_read=1_000_000) == pytest.approx(0.20)
    # 표에 캐시 읽기가 없으면 입력 × 0.1 · 캐시 쓰기는 입력 × 1.25 / default read = input × 0.1, write = × 1.25
    assert _cost("claude-sonnet-5", cache_read=1_000_000) == pytest.approx(0.20)
    assert _cost("claude-sonnet-5", cache_creation=1_000_000) == pytest.approx(2.50)


def test_unknown_model_uses_newest_line_rate_and_is_estimated():
    # 같은 계열의 가장 새 확정 판(기본 카탈로그 순) — haiku 는 Haiku 5.5 요율 / the line's newest rated model
    assert _cost("claude-haiku-6", input_tokens=50_000) == pytest.approx(50_000 * 0.10 / 1e6)
    assert _cost("claude-haiku-6", input_tokens=150_000) == pytest.approx(150_000 * 0.50 / 1e6)  # 그 판의 구간도 따른다
    assert cm.is_estimated_rate("claude-haiku-6")
    # 계열을 모르면 sonnet 계열의 가장 새 판 / an unknown line falls back to the newest sonnet
    assert _cost("some-other-model", input_tokens=1_000_000, cache_read=1_000_000) == pytest.approx(2.0 + 0.10)
    assert cm.is_estimated_rate("some-other-model")
    assert cm.is_estimated_rate("")


def test_known_models_are_not_estimated():
    assert cm._MODEL_RATES  # pylint: disable=protected-access
    for model_id in cm._MODEL_RATES:  # pylint: disable=protected-access
        assert not cm.is_estimated_rate(model_id), model_id
    # 날짜 붙은 id 는 그 별칭의 요율 — 운영 기록에 실제로 있다(claude-haiku-4-5-20251001)
    # A dated id takes its alias's rate; production rows really carry one.
    assert not cm.is_estimated_rate("claude-haiku-4-5-20251001")
    assert _cost("claude-haiku-4-5-20251001", input_tokens=1_000_000) == pytest.approx(1.0)
    assert _cost(" Claude-Sonnet-5 ", input_tokens=1_000_000) == pytest.approx(2.0)


def test_every_fallback_model_has_a_confirmed_rate():
    # 목록이 없을 때 부르는 판이 «추정» 이면 안 된다 / models called without a listing must not be estimated
    unrated = [entry.id for entry in mc.FALLBACK_CATALOG if cm.is_estimated_rate(entry.id)]
    assert not unrated, unrated


def test_fable_is_its_own_bucket(monkeypatch):
    assert claude_api_cost_repo._family("claude-fable-5-2") == "fable"  # pylint: disable=protected-access
    rows = [("claude-fable-5-2", 0.5), ("claude-sonnet-5", 0.25), ("claude-opus-5-5", 0.125)]
    monkeypatch.setattr(claude_api_cost_repo, "_window_cost_rows", lambda *_a, **_k: rows)
    monkeypatch.setattr(claude_api_cost_repo, "_owned_repo_ids_subquery", lambda _uid: [])
    summary = claude_api_cost_repo.user_cost_summary(None, user_id=1, days=30)
    assert summary["by_model"] == {"sonnet": 0.25, "haiku": 0.0, "opus": 0.125, "fable": 0.5, "other": 0.0}


# witness-corpus: 요율표에 없는 판 이름 — 다음 세대 · 계열만 맞는 일반 id · 다른 회사 모델 · 빈 값 · 대문자 · 앞뒤 공백
_UNLISTED_MODELS = {
    "claude-haiku-6": 0.10,      # haiku 의 가장 새 판(Haiku 5.5) / the newest haiku
    "claude-opus-4": 4.0,        # opus 의 가장 새 판(Opus 5.5) / the newest opus
    "gpt-x": 2.0,                # 계열 모름 → sonnet 의 가장 새 판(Sonnet 5.5) / unknown line -> newest sonnet
    "": 2.0,
    "CLAUDE-HAIKU-6": 0.10,
    " claude-fable-6 ": 8.0,     # fable 의 가장 새 판(Fable 5.2) / the newest fable
}


@pytest.mark.parametrize(("model", "input_rate"), _UNLISTED_MODELS.items())
def test_unlisted_models_are_estimated_at_their_line_newest_rate(model, input_rate):
    assert cm.is_estimated_rate(model)
    assert _cost(model, input_tokens=10_000) == pytest.approx(10_000 * input_rate / 1e6)


# 판마다 요율 — 표와 따로 적은 숫자(Anthropic 가격 페이지 · 2026-11-22 확인)로 잠근다. 목록(models=15)에 있는
# 옛 판도 넣었다 — 표에 없으면 같은 계열의 가장 새 판(Opus 5.5 · Fable 5.2)으로 낮게 «추정» 됐다.
# Per-model rates pinned to numbers written apart from the table (Anthropic pricing page, checked 2026-11-22),
# including the older listed models that would otherwise be estimated low from the line's newest model.
_PRICING_PAGE = [
    # (판, 입력, 출력, 캐시 읽기) — USD / 1M 토큰 / (model, input, output, cache read) in USD per 1M tokens
    ("claude-haiku-4-5", 1.0, 5.0, 0.10),
    ("claude-haiku-5-5", 0.10, 0.50, 0.01),
    ("claude-sonnet-4-5", 3.0, 15.0, 0.30),
    ("claude-sonnet-4-6", 3.0, 15.0, 0.30),
    ("claude-sonnet-5", 2.0, 10.0, 0.20),
    ("claude-sonnet-5-5", 2.0, 10.0, 0.10),
    ("claude-opus-4-5", 5.0, 25.0, 0.50),
    ("claude-opus-4-6", 5.0, 25.0, 0.50),
    ("claude-opus-4-7", 5.0, 25.0, 0.50),
    ("claude-opus-4-8", 5.0, 25.0, 0.50),
    ("claude-opus-5", 5.0, 25.0, 0.50),
    ("claude-opus-5-5", 4.0, 20.0, 0.20),
    ("claude-fable-5", 10.0, 50.0, 1.0),
    ("claude-fable-5-1", 10.0, 50.0, 0.25),
    ("claude-fable-5-2", 8.0, 40.0, 0.20),
]


@pytest.mark.parametrize(("model", "input_rate", "output_rate", "cache_read_rate"), _PRICING_PAGE)
def test_listed_model_rates_match_the_pricing_page(model, input_rate, output_rate, cache_read_rate):
    assert not cm.is_estimated_rate(model), model
    assert _cost(model, input_tokens=1_000) == pytest.approx(1_000 * input_rate / 1e6)
    assert _cost(model, output_tokens=1_000) == pytest.approx(1_000 * output_rate / 1e6)
    assert _cost(model, cache_read=1_000) == pytest.approx(1_000 * cache_read_rate / 1e6)
    assert _cost(model, cache_creation=1_000) == pytest.approx(1_000 * input_rate * 1.25 / 1e6)


def test_haiku_5_5_tier_starts_right_above_100k_and_counts_cache_writes():
    assert _cost("claude-haiku-5-5", input_tokens=100_001) == pytest.approx(100_001 * 0.50 / 1e6)
    assert _cost("claude-haiku-5-5", input_tokens=60_000, cache_creation=60_000) == pytest.approx(
        (60_000 * 0.50 + 60_000 * 0.50 * 1.25) / 1e6)


def test_retired_rates_never_shadow_a_listed_rate():
    # 내린 판 표(constants)와 판 표(claude_metrics)에 같은 id 를 두지 않는다 — 겹치면 한쪽 값(캐시 · 구간)이 조용히 사라진다
    # The retired table and the listed table never share an id; an overlap silently drops one side's fields.
    from src.constants import CLAUDE_RETIRED_MODEL_PRICING  # pylint: disable=import-outside-toplevel

    assert not set(CLAUDE_RETIRED_MODEL_PRICING) & set(cm._LISTED_RATES)  # pylint: disable=protected-access
