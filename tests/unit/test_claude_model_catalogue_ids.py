"""모델 카탈로그는 별칭으로 부르고, 설정 기본값도 그 카탈로그 이름을 쓴다 (회고 원장 이관 K11 P2-38 · P2-55).

## 사고

카탈로그의 Haiku 항목이 날짜 스냅샷 id(`claude-haiku-4-5-20251001`)였고 인사이트 기본값은 별칭(`claude-haiku-4-5`)이었다 —
같은 모델을 앱이 두 이름으로 불렀다. Anthropic 모델 참조는 «별칭을 쓰라» 고 한다(별칭과 전체 id 는 같은 모델).
사용자 11-17 결정 «별칭 통일+5개 이전 (Recommended)».

## 이 파일이 잠그는 것

1. 카탈로그 id 에 날짜 접미사(`-YYYYMMDD`)가 없다.
2. 설정의 기본 리뷰 · 인사이트 모델이 카탈로그 id 다 — 한 모델 한 이름.
"""
from __future__ import annotations

import re

import pytest

from src.config import Settings
from src.constants import CLAUDE_MODELS

_DATED = re.compile(r"-\d{8}$")

# witness-corpus: 별칭 · 날짜 스냅샷 id · 날짜가 아닌 숫자 꼬리
_SAMPLES = (
    ("claude-haiku-4-5", False),
    ("claude-sonnet-5", False),
    ("claude-opus-4-7", False),
    ("claude-haiku-4-5-20251001", True),
    ("claude-3-5-haiku-20241022", True),
    ("claude-model-1234567", False),
)


@pytest.mark.parametrize(("model_id", "dated"), _SAMPLES)
def test_the_dated_suffix_detector(model_id, dated):
    """판정식 뒤집기 — 8자리 날짜 꼬리만 잡고, 버전 숫자 · 짧은 숫자 꼬리는 잡지 않는다."""
    assert bool(_DATED.search(model_id)) is dated


def test_catalogue_ids_are_aliases():
    """🔴 카탈로그 id 에 날짜 스냅샷이 없다 — 별칭과 섞이면 같은 모델이 두 이름이 된다."""
    ids = [m["id"] for m in CLAUDE_MODELS]
    assert ids, "카탈로그가 비었다 — 이 검사가 공허하다"
    dated = [i for i in ids if _DATED.search(i)]
    assert not dated, f"날짜 스냅샷 id 가 카탈로그에 있다: {dated} — 별칭으로 부른다"


@pytest.mark.parametrize("field", ["claude_review_model", "claude_insight_model"])
def test_the_default_models_are_catalogue_ids(field):
    """🔴 설정 기본값이 카탈로그와 같은 이름이다 — 다르면 셀렉터 · 비용 · 기록이 한 모델을 두 이름으로 다룬다."""
    default = Settings.model_fields[field].default
    assert default in {m["id"] for m in CLAUDE_MODELS}, f"{field} 기본값 {default!r} 가 카탈로그 id 가 아니다"
