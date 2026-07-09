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


def test_ai_review_dependent_hidden_when_off_css_has():
    """AI 리뷰 OFF 시 종속 블록(.ai-review-dependent) + 모델 선택(.ai-review-model) 모두 숨김 = CSS :has() (JS 0)."""
    # Hide-on-AI-off via CSS :has() — no JS handler. The dependent (PR-comment toggle) + folded
    # model select are display:none when AI review is off (consistent with the auto_merge /
    # approve_mode hide-when-off pattern), so a disabled toggle shows no cluttering detail.
    html = _read()
    assert 'ai-review-group:has(' in html and 'ai_review_enabled"]:not(:checked)' in html, (
        "CSS :has() 숨김 셀렉터 없음 — .ai-review-group:has(input[name=ai_review_enabled]:not(:checked)) .ai-review-dependent"
    )
    m = re.search(
        r"\.ai-review-group:has\([^{]*ai_review_enabled[^{]*\)\s*\.ai-review-dependent\s*,\s*"
        r"\.ai-review-group:has\([^{]*ai_review_enabled[^{]*\)\s*\.ai-review-model\s*"
        r"\{([^}]*)\}",
        html,
    )
    assert m, "종속+모델 숨김 규칙 셀렉터(콤마 그룹) 매칭 실패"
    # 비-공허(non-vacuous) 검증 — .ai-review-model 이 실제로 매칭 문자열 안에 포함됐는지 별도 재확인.
    # Non-vacuous check — re-assert .ai-review-model literally appears in the matched selector group.
    assert ".ai-review-model" in m.group(0), (
        ".ai-review-model 이 AI OFF 시 숨김 셀렉터에 포함되지 않음 — 모델 선택이 여전히 노출됨"
    )
    body = m.group(1)
    # 🔴 회색(opacity/pointer-events)이 아니라 완전 숨김(display:none) — 비활성 세부 노출 clutter 제거.
    # Full hide (display:none), not grey-out — removes clutter of showing detail while disabled.
    assert "display" in body and "none" in body, "숨김(display:none) 누락 — AI OFF 시 종속 세부 완전 숨김 의무"
    assert "opacity" not in body and "pointer-events" not in body, (
        "회색(opacity/pointer-events) 잔존 — 숨김(display:none)으로 교체 의무 (회색-보임 clutter 제거)"
    )


def test_pr_review_comment_not_disabled_attr():
    """종속 숨김은 display:none(값 보존) — pr_review_comment 는 disabled 속성 없이 폼 제출 정상."""
    # Hide via display:none must NOT use the disabled attribute (value must still submit when re-shown).
    html = _read()
    m = re.search(r'<input[^>]*name="pr_review_comment"[^>]*>', html)
    assert m, "pr_review_comment input 없음"
    assert "disabled" not in m.group(0), "pr_review_comment 에 disabled 속성 — 숨김은 CSS display:none 로만(값 보존)"


def test_ai_review_model_stacks_select_and_hint():
    """AI 리뷰 모델 블록(.ai-review-model)은 select 위·설명(field-hint) 아래로 세로 배치 — 같은 줄 흐름 방지."""
    # The folded review_model block must stack the select over its long model_hint (column layout,
    # like .field-row) — otherwise select + hint render inline on the same line (awkward, user-reported).
    html = _read()
    # 독립 규칙 `.ai-review-model { ... }`(줄 시작) 매칭 — `:has() ... .ai-review-model`(숨김) 규칙과 구별.
    # Match the standalone `.ai-review-model { ... }` rule (line-start), not the `:has()` hide rule.
    m = re.search(r"^\s*\.ai-review-model\s*\{([^}]*)\}", html, re.MULTILINE)
    assert m, ".ai-review-model 세로 배치 규칙 없음 — select/설명이 같은 줄에 inline 노출됨"
    body = m.group(1)
    assert "flex-direction" in body and "column" in body, (
        ".ai-review-model 세로 배치(flex-direction:column) 누락 → select 와 model_hint 가 같은 줄 inline"
    )


def test_review_model_folded_into_ai_group():
    """review_model select 이 단독 카드가 아니라 카드 ② .ai-review-group 안에 위치 (7→6 카드)."""
    # review_model lives inside the AI-review group, not as a standalone orphan card.
    html = _read()
    i_group = html.find('class="ai-review-group"')
    # i_group 이후로 검색 범위 한정 — 단, review_model 은 CSS :has() 셀렉터에 등장하지 않는다
    # (그 셀렉터는 ai_review_enabled 만 참조). 위 test_ai_review_group_hierarchy 의
    # ai_review_enabled 검색과 달리 여기서는 CSS 중복 매치를 피하려는 목적이 아니라,
    # 검색 anchor 를 AI 리뷰 그룹 마크업 내부로 한정하기 위함이다.
    # Scope the search to after i_group — but unlike the ai_review_enabled search above,
    # review_model never appears in the CSS :has() selector (which only references
    # ai_review_enabled), so there's no CSS literal to dodge here. i_group scoping simply
    # anchors the lookup inside the AI-review group markup.
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


def test_preset_diff_omits_inert_thresholds():
    """renderPresetDiff 가 무효(inert) 임계값 행 2종을 모두 생략한다.

    (1) approve_mode==='disabled' 시 approve/reject_threshold 행 생략
    (2) auto_merge===false 시 merge_threshold 행 생략
    """
    # The diff JS skips inert threshold rows: approve/reject when the preset's mode is
    # 'disabled' AND merge_threshold when auto_merge is false.
    html = _read()
    i_fn = html.find("function renderPresetDiff")
    assert i_fn != -1, "renderPresetDiff 없음 — 테스트 stale"
    body = html[i_fn:html.find("function applyPreset", i_fn)]
    # (1) disabled 시 approve/reject 임계 skip 가드 존재 (approve_mode 값 'disabled' 참조 + threshold 키 skip)
    assert "disabled" in body and "approve_threshold" in body and "reject_threshold" in body, (
        "임계값 생략 로직 없음 — mode=disabled 시 approve/reject_threshold 행 skip 필요"
    )
    assert re.search(r"approve_mode\s*===?\s*'disabled'|p\.approve_mode\s*===?\s*'disabled'", body), (
        "approve_mode=='disabled' 조건 가드 부재"
    )
    # (2) auto_merge=false 시 merge_threshold 임계 skip 가드 존재
    assert "merge_threshold" in body and "auto_merge" in body, (
        "merge_threshold 임계값 생략 로직 없음 — auto_merge=false 시 merge_threshold 행 skip 필요"
    )
    assert re.search(r"auto_merge\s*===?\s*false|p\.auto_merge\s*===?\s*false", body), (
        "auto_merge===false 조건 가드 부재 — merge_threshold 행 skip 브랜치 없음"
    )


def test_preset_diff_summary_keys_exist_3locales():
    """프리셋별 1줄 차이 요약 i18n 키가 ko/en/ja 3로케일에 존재."""
    import json
    for loc in ("ko", "en", "ja"):
        data = json.loads(Path(f"src/i18n/translations/{loc}.json").read_text(encoding="utf-8"))
        pc = data.get("settings_page", {}).get("preset_card", {})
        for k in ("minimal_diff_summary", "standard_diff_summary", "strict_diff_summary"):
            assert k in pc and pc[k].strip(), f"{loc}: preset_card.{k} 누락/빈값"


def test_railway_controls_in_single_block():
    """Railway 3항목(deploy_alerts·api_token·webhook_url)이 단일 railway 블록에 인접.

    게이팅 제거 정정(리뷰 Fix 2): 배포 알림은 Railway API 토큰이 아니라 인바운드
    Webhook 토큰으로 동작하므로 railway_api_token_set 조건부는 제거됐다 — 토큰
    미설정 상태에서도 3항목 모두 노출된다.
    """
    # The three Railway controls are grouped in one block, unconditionally (Fix 2:
    # the token gating was removed — deploy alerts don't require the Railway API token).
    html = _read()
    i_block = html.find('class="railway-group"')
    assert i_block != -1, "railway-group 단일 블록 없음"
    block = html[i_block:i_block + 2500]
    assert 'name="railway_api_token"' in block, "블록에 railway_api_token 없음"
    assert 'name="railway_deploy_alerts"' in block, "블록에 railway_deploy_alerts 없음"
    assert 'id="railway-webhook-url"' in block, "블록에 Railway Webhook URL 없음"
    # 🔴 CRITICAL fix (리뷰 Fix 1): railway_deploy_alerts 토글이 카드 밖(railway-group)으로
    # 이동하며 #settingsForm 밖에 위치 — form="settingsForm" 없이는 제출되지 않아 저장 시
    # 매번 False 로 덮어써지는 데이터 유실 버그가 있었다. 형제 railway_api_token 과 동일하게
    # form 속성을 명시적으로 부여했는지 정적 검증한다.
    # The railway_deploy_alerts toggle moved outside #settingsForm (into the card-level
    # railway-group) — without form="settingsForm" it is never submitted, silently
    # overwriting the saved value with False on every save. Assert it carries the same
    # form attribute as its sibling railway_api_token input.
    i_input = block.find('name="railway_deploy_alerts"')
    input_tag_end = block.find('>', i_input)
    input_tag = block[i_input:input_tag_end + 1]
    assert 'form="settingsForm"' in input_tag, (
        "railway_deploy_alerts input 에 form=\"settingsForm\" 없음 (데이터 유실 버그)"
    )


def test_setup_actions_collapsed_in_details():
    """카드 ⑤ 일회성 셋업 액션(Webhook 재등록·Hook 재커밋)이 <details> 접힘 안에 있다."""
    # One-time setup actions (webhook re-register, hook re-commit) are wrapped in a collapsed <details>.
    html = _read()
    i_det = html.find('class="setup-actions"')
    assert i_det != -1, "setup-actions <details> 접힘 래퍼 없음"
    # <details> 요소인지 + 두 액션 form 참조 포함
    seg = html[i_det:i_det + 2500]
    assert 'reinstall_webhook_form' in seg, "접힘 안에 Webhook 재등록 액션 없음"
    assert 'reinstall_hook_form' in seg, "접힘 안에 Hook 재커밋 액션 없음"
    # <details 태그로 감쌈 확인 (setup-actions 가 details 클래스)
    assert re.search(r'<details[^>]*class="[^"]*setup-actions', html), "setup-actions 가 <details> 요소 아님"
