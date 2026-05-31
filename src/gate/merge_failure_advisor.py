"""Auto-merge 실패 사유별 권장 조치 텍스트 — Phase F.3 + Tier 3 PR-A.

Auto-merge failure advice text per reason — Phase F.3 + Tier 3 PR-A.

사이클 149 Sprint 3: 조언 텍스트를 i18n 처리 — `notifier.merge_advice.<tag>` 키로
ko/en/ja 번역 제공. GitHub Issue/Telegram 알림에 사용자 언어로 노출.
Cycle 149 Sprint 3: advice text is now i18n — `notifier.merge_advice.<tag>` keys
provide ko/en/ja translations, shown in the user's language in GitHub Issues/Telegram.
"""
from src.gate import merge_reasons
from src.github_client.graphql import (
    ENABLE_API_ERROR,
    ENABLE_DISABLED_IN_REPO,
    ENABLE_FORCE_PUSHED,
    ENABLE_PERMISSION_DENIED,
)
from src.i18n.loader import get_text

# 알려진 reason tag 집합 — i18n 키 (`notifier.merge_advice.<tag>`) 와 1:1 대응.
# Known reason-tag set — maps 1:1 to i18n keys (`notifier.merge_advice.<tag>`).
# 미등재 tag 는 default 문구로 fallback (안전한 명시적 판정 — get_text 미존재 키 동작 의존 X).
# Unknown tags fall back to the default text (explicit safe check — no reliance on get_text miss behavior).
_KNOWN_TAGS: frozenset[str] = frozenset({
    merge_reasons.BRANCH_PROTECTION_BLOCKED,
    merge_reasons.DIRTY_CONFLICT,
    merge_reasons.BEHIND_BASE,
    merge_reasons.DRAFT_PR,
    merge_reasons.UNSTABLE_CI,
    merge_reasons.UNKNOWN_STATE_TIMEOUT,
    merge_reasons.PERMISSION_DENIED,
    merge_reasons.NOT_MERGEABLE,
    merge_reasons.UNPROCESSABLE,
    merge_reasons.CONFLICT_SHA_CHANGED,
    merge_reasons.NETWORK_ERROR,
    ENABLE_DISABLED_IN_REPO,
    ENABLE_PERMISSION_DENIED,
    ENABLE_FORCE_PUSHED,
    ENABLE_API_ERROR,
})


def get_advice(reason: str | None, language: str = "ko") -> str:
    """reason tag 로 권장 조치 텍스트를 언어별로 반환. 알 수 없는 tag 는 기본 문구 반환.

    Return localized advice text for a reason tag. Unknown tags return the default text.

    reason 은 'tag' 또는 'tag: user-facing text' 형식 모두 허용.
    reason accepts either 'tag' or 'tag: user-facing text' formats.

    Args:
        reason: 정규 reason tag (또는 'tag: 설명' 형식). None 시 default.
        language: 알림 언어 코드 ("ko"/"en"/"ja"). 미전달 시 "ko" (하위 호환).
    """
    if not reason:
        return get_text("notifier.merge_advice.default", language)
    tag = reason.split(":")[0].strip()
    if tag in _KNOWN_TAGS:
        return get_text(f"notifier.merge_advice.{tag}", language)
    return get_text("notifier.merge_advice.default", language)
