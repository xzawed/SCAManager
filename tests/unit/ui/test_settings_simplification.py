"""설정 간소화 UI 재구성 정적 가드 (2026-07-09).

Settings simplification (UI-only reorg) static guards: assert the DOM structure /
CSS / JS changes are present on the raw template, without any backend field change.
"""
from __future__ import annotations

import re
from pathlib import Path

_SETTINGS = Path("src/templates/settings.html")


def _read() -> str:
    return _SETTINGS.read_text(encoding="utf-8")


def test_ai_review_group_hierarchy():
    """카드 ②: ai_review_enabled(상위)가 pr_review_comment(종속)보다 앞 + 종속 래퍼 존재."""
    # ai_review_enabled comes before pr_review_comment, wrapped as a parent group with a dependent block.
    html = _read()
    i_group = html.find('class="ai-review-group"')
    # CSS :has() 셀렉터(문서 상단 <style>)에도 동일 문자열이 등장하므로 i_group 이후로 검색 범위 한정.
    # The CSS :has() selector (top-of-doc <style> block) also contains this literal string, so scope the search to after i_group.
    i_ai = html.find('name="ai_review_enabled"', i_group)
    i_dep = html.find('class="ai-review-dependent"')
    i_pr = html.find('name="pr_review_comment"')
    assert i_group != -1, "ai-review-group 래퍼 없음"
    assert i_dep != -1, "ai-review-dependent 종속 래퍼 없음"
    # 상위(ai_review_enabled)가 종속(pr_review_comment)보다 문서상 앞
    assert i_group < i_ai < i_dep < i_pr, (
        "계층 순서 위반 — ai_review_enabled(상위)가 pr_review_comment(종속) 앞, 종속 래퍼 안에 pr_review_comment"
    )


def test_ai_review_dependent_greyout_css_has():
    """AI 리뷰 OFF 시 종속 블록 회색·비활성 = CSS :has() (JS 0)."""
    # Grey-out on AI-off via CSS :has() — no JS handler.
    html = _read()
    assert 'ai-review-group:has(' in html and 'ai_review_enabled"]:not(:checked)' in html, (
        "CSS :has() 회색 셀렉터 없음 — .ai-review-group:has(input[name=ai_review_enabled]:not(:checked)) .ai-review-dependent"
    )
    m = re.search(r"\.ai-review-group:has\([^{]*ai_review_enabled[^{]*\)\s*\.ai-review-dependent\s*\{([^}]*)\}", html)
    assert m, "종속 회색 규칙 셀렉터 매칭 실패"
    body = m.group(1)
    assert "pointer-events" in body and "opacity" in body, "회색(opacity)+비활성(pointer-events) 누락"


def test_pr_review_comment_not_disabled_attr():
    """종속 회색은 pointer-events(시각)만 — pr_review_comment 는 disabled 속성 없이 폼 제출 정상."""
    # Grey-out must NOT use the disabled attribute (value must still submit).
    html = _read()
    m = re.search(r'<input[^>]*name="pr_review_comment"[^>]*>', html)
    assert m, "pr_review_comment input 없음"
    assert "disabled" not in m.group(0), "pr_review_comment 에 disabled 속성 — 회색은 CSS pointer-events 로만"


def test_review_model_folded_into_ai_group():
    """review_model select 이 단독 카드가 아니라 카드 ② .ai-review-group 안에 위치 (7→6 카드)."""
    # review_model lives inside the AI-review group, not as a standalone orphan card.
    html = _read()
    i_group = html.find('class="ai-review-group"')
    # CSS :has() 셀렉터(문서 상단 <style>)에도 동일 문자열이 등장하므로 i_group 이후로 검색 범위 한정.
    # The CSS :has() selector (top-of-doc <style> block) also contains this literal string, so scope the search to after i_group.
    i_model = html.find('name="review_model"', i_group)
    # ai-review-group 다음, 그리고 그 그룹 종료(다음 s-divider) 전에 위치
    i_divider = html.find('s-divider', i_group)
    assert i_group != -1 and i_model != -1, "그룹 또는 review_model 없음"
    assert i_group < i_model < i_divider, "review_model 이 AI 그룹(s-divider 앞) 안에 없음"
    # review_model 은 여전히 form=settingsForm 로 메인 폼 연결 보존
    m = re.search(r'<select[^>]*name="review_model"[^>]*>', html)
    assert m and 'form="settingsForm"' in m.group(0), "review_model select 의 form=settingsForm 속성 소실"


def test_review_model_orphan_card_removed():
    """단독 review_model 카드(🤖 모델 카드) 가 제거되어 카드 수가 줄었다."""
    # The standalone model card wrapper is gone (folded into card ②) — assert deterministically
    # that no s-card header exposes model_card_title as its hdr-title (the old orphan card's shape),
    # rather than relying on a brittle quoting/replace chain.
    # 단독 카드 제거를 결정론적으로 단언 — 취약한 quoting/replace 체인 대신, model_card_title 을
    # hdr-title 로 노출하는 s-card 헤더가 더 이상 없음을 검사.
    html = _read()
    header_blocks = re.findall(r'<div class="s-card-hdr[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
    orphan_headers = [h for h in header_blocks if "settings.model_card_title" in h]
    assert not orphan_headers, "review_model 단독 카드 헤더(model_card_title)가 여전히 존재 — 흡수 미완"
