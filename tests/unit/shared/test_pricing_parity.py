"""Claude 모델 가격 3-소스 정합성 회귀 가드 (정책 4 — 회고 2026-07-03 C3).
Claude model pricing 3-source parity regression guard (policy 4 — retro 2026-07-03 C3).

🔴 **PARITY GUARD**: Claude 가격이 3곳에 중복 존재 — 하나만 수정하면 이 테스트가 즉시 fail.
🔴 **PARITY GUARD**: Claude pricing lives in 3 places — editing only one makes this test fail.

  1. `src/shared/claude_metrics.py::_MODEL_RATES` — SSOT (실제 비용 계산, 판 id 별 요율 — #1905 ②)
     SSOT — actual cost calculation, one rate per model id.
  2. `src/constants.py::CLAUDE_MODELS` — 모델 셀렉터 카탈로그 (model-id별 input/output_price)
     model selector catalog, per model-id input/output_price.
  3. `src/i18n/translations/{en,ko,ja}.json` `settings.model_hint` — UI 힌트 "$N/1M" (input만 노출) — 선택지 판의 요율
     UI hint text "$N/1M" (input rate only) — the rate of the selector's model for each line.

배경: #1015 가 (1)만 갱신하고 (2)(3) 을 stale 로 남겨 #1019 split-fix 를 유발 (한 곳만 수정 안티패턴).
가격 변경 시 3곳 전수 수정 의무 — 본 가드가 turn-0/CI 에서 drift 를 즉시 차단.
Context: #1015 updated only (1), leaving (2)(3) stale → #1019 split-fix. This guard blocks that drift.
"""
import re

import pytest

from src.constants import CLAUDE_MODELS
from src.i18n.loader import load_translations
from src.shared.claude_metrics import _MODEL_RATES
from src.shared.model_catalog import KNOWN_LINES, line_of


def setup_function():
    """각 테스트 전 i18n LRU 캐시 초기화 (테스트 격리).
    Clear i18n LRU cache before each test (test isolation)."""
    load_translations.cache_clear()


def _selector_model_of(line: str) -> dict:
    """그 계열의 선택지 판 — 선택지는 계열마다 하나다 / the selector's model for a line (one per line)."""
    models = [m for m in CLAUDE_MODELS if line_of(m["id"]) == line]
    assert len(models) == 1, f"{line} 계열 선택지가 {len(models)}개 — 힌트가 어느 판의 가격인지 모른다"
    return models[0]


def test_constants_catalog_matches_metrics_ssot():
    """constants.CLAUDE_MODELS 각 모델의 (input, output) 가 그 판의 claude_metrics 요율과 일치.
    Every CLAUDE_MODELS entry's (input, output) must equal that model's claude_metrics rate."""
    for model in CLAUDE_MODELS:
        rate = _MODEL_RATES.get(model["id"])
        assert rate is not None, f"{model['id']} 가 요율표에 없다 — 선택지 판이 «추정» 요율로 매겨진다"
        assert (model["input_price"], model["output_price"]) == (rate.input, rate.output), (
            f"{model['id']} 선택지 가격 ${model['input_price']}/${model['output_price']} 가 "
            f"요율표 ${rate.input}/${rate.output} 와 불일치 (3-소스 drift)"
        )


def test_every_line_has_a_selector_model():
    """아는 계열마다 선택지 판이 하나 — 힌트가 계열마다 그 판의 가격을 말한다.
    Every known line has one selector model; the hint states that model's price per line."""
    assert {line_of(m["id"]) for m in CLAUDE_MODELS} == set(KNOWN_LINES)


@pytest.mark.parametrize("locale", ["en", "ko", "ja"])
def test_i18n_model_hint_input_price_matches_ssot(locale):
    """각 언어 model_hint 의 'Haiku/Sonnet/Opus $N/1M' input 단가가 SSOT input rate 와 일치.
    Each locale's model_hint '$N/1M' per family must equal the SSOT input rate."""
    trans = load_translations(locale)
    hint = trans.get("settings", {}).get("model_hint", "")
    assert hint, f"{locale}.json 에 settings.model_hint 부재 — i18n 키 회귀"

    for family in sorted(KNOWN_LINES):
        in_rate = _MODEL_RATES[_selector_model_of(family)["id"]].input
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


# ── 내린 모델 요율 (Grok 반증 01a07e4b — BROKEN 판정에서 드러난 사각) ─────────────
#
# `constants.CLAUDE_RETIRED_MODEL_PRICING` — 카탈로그에서 «내렸지만» 여전히 흐르는 id.
# `RepoConfig.review_model` 은 `String(50)` 이고 저장 시 카탈로그 검증이 없다
# (`src/api/repos.py::review_model: str | None`·`src/ui/routes/settings.py::review_model=form.get(`).
# 그래서 예전에 저장된 `claude-sonnet-4-6` 은 운영자가 아무것도 안 해도 계속 흐른다 —
# family 요율(sonnet=$2/$10)로 매기면 그 호출만 33% 과소 계상된다.
#
# 🔴 화면(리포 상세 월 비용)은 이제 요율표를 따로 들지 않고 기록 함수를 그대로 쓴다 — 예전의
#    화면 전용 표·fallback 이 `claude-opus-4-7` 을 2.5× 과소 계상했다(회고 2026-09-16 K09).
#    화면 == 기록 은 `tests/unit/ui/test_monthly_cost_single_price_path.py` 가 id 무관하게 잠근다.

def test_retired_model_rates_are_honored_by_the_recording_path():
    """🔴 내린 모델은 계열 요율이 아니라 표의 세대 요율로 매긴다 — 입력·출력 둘 다."""
    from src.constants import CLAUDE_RETIRED_MODEL_PRICING  # noqa: PLC0415
    from src.shared.claude_metrics import estimate_claude_cost_usd  # noqa: PLC0415

    assert CLAUDE_RETIRED_MODEL_PRICING, (
        "내린 모델 요율표가 비었다 — 계열 요율과 다른 모델을 내릴 때 여기 옮기지 않으면 "
        "저장된 값이 family 요율로 잘못 매겨진다")
    for model_id, rates in CLAUDE_RETIRED_MODEL_PRICING.items():
        recorded_in = estimate_claude_cost_usd(
            model=model_id, input_tokens=1_000_000, output_tokens=0)
        recorded_out = estimate_claude_cost_usd(
            model=model_id, input_tokens=0, output_tokens=1_000_000)
        assert (recorded_in, recorded_out) == pytest.approx((rates["input"], rates["output"])), (
            f"{model_id} 기록 경로 ${recorded_in}/${recorded_out} 가 표의 "
            f"${rates['input']}/${rates['output']} 와 다르다 — family 요율로 덮여 세대 차이를 잃었다")


def test_retired_models_are_not_offered_in_the_selector():
    """🔴 대조군 — 내린 모델이 «선택지» 로 되살아나면 안 된다(요율만 남긴다)."""
    from src.constants import CLAUDE_RETIRED_MODEL_PRICING  # noqa: PLC0415

    offered = {m["id"] for m in CLAUDE_MODELS}
    overlap = offered & set(CLAUDE_RETIRED_MODEL_PRICING)
    assert not overlap, f"내린 모델이 셀렉터에 다시 올라와 있다: {sorted(overlap)}"
