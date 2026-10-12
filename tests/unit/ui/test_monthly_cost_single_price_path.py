"""리포 상세의 월 비용은 비용 «기록» 경로와 같은 요율로 매긴다 (회고 2026-09-16 K09 — P1-4 · 25 · 43 · 53).

## 사고

#1638 이 `claude-opus-4-7` 을 카탈로그에서 내렸다. 기록 경로(`estimate_claude_cost_usd`)는 그 id 를
계열(opus) 요율 $5/$25 로 매기는데, 화면(`_calc_monthly_cost`)은 자기 요율표에 그 id 가 없어 기본
요율 $2/$10 로 매겼다 — 같은 호출이 화면에서 40% 로 보였다. 두 경로를 묶던 가드는 «요율표에 있는
id» 만 돌아서, 표에 없는 id 는 원리적으로 못 봤다. 이 함수에는 시험이 하나도 없었다.

## 이 파일이 잠그는 것

- 화면 값 == 기록 값 — 카탈로그 id · 내린 id(표에 있음/없음) · 날짜 없는 별칭 · 모르는 id · 빈 값.
- 파생되지 않은 바닥 — 두 id 의 비용을 손으로 계산한 값과 대조한다. 기대값을 같은 함수에서
  뽑으면 둘이 함께 틀려도 초록이다.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.shared.claude_metrics import estimate_claude_cost_usd
from src.ui.routes.detail import _calc_monthly_cost


def _row(model, input_tokens, output_tokens):
    return SimpleNamespace(review_model=model, input_tokens=input_tokens,
                           output_tokens=output_tokens)


@pytest.mark.parametrize("model", [
    "claude-sonnet-5", "claude-opus-5", "claude-haiku-4-5-20251001", "claude-fable-5-1",
    "claude-sonnet-4-6",  # 내린 모델 — 요율표에 있다(세대 요율이 계열과 다르다)
    "claude-opus-4-7",    # 내린 모델 — 요율표에 없다(계열 요율과 같다)
    "claude-haiku-4-5",   # 날짜 없는 별칭 — 카탈로그 id 와 다르다
    "some-future-model",  # 모르는 id
    None, "",
])
def test_dashboard_cost_equals_the_recorded_cost_for_every_model_id(model):
    """🔴 화면이 매긴 값과 기록 경로가 매긴 값이 어떤 id 에서도 같다."""
    expected = round(estimate_claude_cost_usd(
        model=model or "", input_tokens=1_234_567, output_tokens=89_012), 4)
    assert _calc_monthly_cost([_row(model, 1_234_567, 89_012)]) == expected, (
        f"{model!r}: 화면과 기록이 다른 요율을 쓴다 — 두 번째 요율표가 생겼다")


def test_retired_opus_4_7_is_priced_at_the_opus_rate():
    """🔴 P1-4 의 실제 숫자 — 입력·출력 1M 씩이면 $5 + $25 = $30 (기본 요율로 매기면 $12)."""
    assert _calc_monthly_cost([_row("claude-opus-4-7", 1_000_000, 1_000_000)]) == 30.0


def test_retired_sonnet_4_6_keeps_its_generation_rate():
    """대조군 — 계열 요율과 다른 내린 모델은 요율표 값 $3/$15 로 매긴다: 1M+1M = $18 (계열이면 $12)."""
    assert _calc_monthly_cost([_row("claude-sonnet-4-6", 1_000_000, 1_000_000)]) == 18.0


def test_rows_are_summed_and_missing_tokens_count_as_zero():
    """행을 더하고, 토큰이 비면 0 으로 센다 — opus 입력 1M($5) + sonnet 입력 1M($2) = $7."""
    rows = [_row("claude-opus-4-7", 1_000_000, None), _row("claude-sonnet-5", 1_000_000, 0),
            _row("claude-sonnet-5", None, None)]
    assert _calc_monthly_cost(rows) == 7.0
