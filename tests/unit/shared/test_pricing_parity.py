"""Claude 모델 가격 3-소스 정합성 회귀 가드 (정책 4 — 회고 2026-07-03 C3).
Claude model pricing 3-source parity regression guard (policy 4 — retro 2026-07-03 C3).

🔴 **PARITY GUARD**: Claude 가격이 3곳에 중복 존재 — 하나만 수정하면 이 테스트가 즉시 fail.
🔴 **PARITY GUARD**: Claude pricing lives in 3 places — editing only one makes this test fail.

  1. `src/shared/claude_metrics.py::_PRICING_USD_PER_MTOK` — SSOT (실제 비용 계산, family별 튜플)
     SSOT — actual cost calculation, per-family (input, output) tuple.
  2. `src/constants.py::CLAUDE_MODELS` — 모델 셀렉터 카탈로그 (model-id별 input/output_price)
     model selector catalog, per model-id input/output_price.
  3. `src/i18n/translations/{en,ko,ja}.json` `settings.model_hint` — UI 힌트 "$N/1M" (input만 노출)
     UI hint text "$N/1M" (input rate only).

배경: #1015 가 (1)만 갱신하고 (2)(3) 을 stale 로 남겨 #1019 split-fix 를 유발 (한 곳만 수정 안티패턴).
가격 변경 시 3곳 전수 수정 의무 — 본 가드가 turn-0/CI 에서 drift 를 즉시 차단.
Context: #1015 updated only (1), leaving (2)(3) stale → #1019 split-fix. This guard blocks that drift.
"""
import re

import pytest

from src.constants import CLAUDE_MODELS
from src.i18n.loader import load_translations
from src.shared.claude_metrics import _PRICING_USD_PER_MTOK


def setup_function():
    """각 테스트 전 i18n LRU 캐시 초기화 (테스트 격리).
    Clear i18n LRU cache before each test (test isolation)."""
    load_translations.cache_clear()


def _family_of(model_id: str) -> str:
    """모델 id → pricing family 키 (haiku/sonnet/opus) 추출 — SSOT 매칭 로직과 동일.
    Map a model id to its pricing family key, mirroring the SSOT lookup logic."""
    model_lower = model_id.lower()
    for family in _PRICING_USD_PER_MTOK:
        if family in model_lower:
            return family
    raise AssertionError(
        f"모델 id {model_id!r} 가 어떤 pricing family({list(_PRICING_USD_PER_MTOK)}) 에도 매칭 안 됨"
    )


def test_constants_catalog_matches_metrics_ssot():
    """constants.CLAUDE_MODELS 각 모델의 (input, output) 가 claude_metrics SSOT 와 일치.
    Every CLAUDE_MODELS entry's (input, output) must equal the claude_metrics SSOT rate."""
    for model in CLAUDE_MODELS:
        family = _family_of(model["id"])
        in_rate, out_rate = _PRICING_USD_PER_MTOK[family]
        assert model["input_price"] == in_rate, (
            f"{model['id']} input_price={model['input_price']} 가 "
            f"claude_metrics {family} input={in_rate} 와 불일치 (3-소스 drift)"
        )
        assert model["output_price"] == out_rate, (
            f"{model['id']} output_price={model['output_price']} 가 "
            f"claude_metrics {family} output={out_rate} 와 불일치 (3-소스 drift)"
        )


def test_every_family_has_a_catalog_model():
    """모든 pricing family 가 CLAUDE_MODELS 에 최소 1개 대표 모델 보유 (셀렉터 커버리지).
    Every pricing family must have at least one representative model in the catalog."""
    families_in_catalog = {_family_of(m["id"]) for m in CLAUDE_MODELS}
    assert families_in_catalog == set(_PRICING_USD_PER_MTOK), (
        f"카탈로그 family {sorted(families_in_catalog)} 가 "
        f"SSOT family {sorted(_PRICING_USD_PER_MTOK)} 와 불일치"
    )


@pytest.mark.parametrize("locale", ["en", "ko", "ja"])
def test_i18n_model_hint_input_price_matches_ssot(locale):
    """각 언어 model_hint 의 'Haiku/Sonnet/Opus $N/1M' input 단가가 SSOT input rate 와 일치.
    Each locale's model_hint '$N/1M' per family must equal the SSOT input rate."""
    trans = load_translations(locale)
    hint = trans.get("settings", {}).get("model_hint", "")
    assert hint, f"{locale}.json 에 settings.model_hint 부재 — i18n 키 회귀"

    for family, (in_rate, _out_rate) in _PRICING_USD_PER_MTOK.items():
        # 힌트 텍스트에서 'Haiku ... ($N/1M)' 패턴의 N 추출 (family 명은 3 언어 공통 영문).
        # Extract N from 'Haiku ... ($N/1M)' (family names are English across all 3 locales).
        match = re.search(rf"{family.capitalize()}[^$]*\$(\d+(?:\.\d+)?)\s*/\s*1M", hint)
        assert match, (
            f"{locale} model_hint 에서 {family.capitalize()} '$N/1M' 패턴 미발견 "
            f"(힌트 구조 변경 시 본 가드·정책 4 재검토): {hint[:80]}"
        )
        hint_rate = float(match.group(1))
        assert hint_rate == in_rate, (
            f"{locale} model_hint {family} 표기 ${hint_rate}/1M 가 "
            f"SSOT input=${in_rate} 와 불일치 (3-소스 drift — 가격 변경 시 i18n 3언어 동시 갱신 의무)"
        )
