"""Auto-merge 실패 사유별 권장 조치 텍스트 — Phase F.3."""
from src.gate import merge_reasons

_ADVICE: dict[str, str] = {
    merge_reasons.BRANCH_PROTECTION_BLOCKED: (
        "Branch Protection Rules 요건 미충족 — 필수 리뷰어 승인 또는 필수 CI 체크를 완료하세요."
    ),
    merge_reasons.DIRTY_CONFLICT: (
        "기반 브랜치와 충돌(Conflict) — `git pull origin main` 후 충돌을 해소하고 다시 push 하세요."
    ),
    merge_reasons.BEHIND_BASE: (
        "기반 브랜치보다 뒤처져 있음 — PR 페이지에서 'Update branch' 버튼을 눌러 최신화하세요."
    ),
    merge_reasons.DRAFT_PR: (
        "Draft PR은 자동 Merge 대상이 아닙니다 — 'Ready for review'로 전환 후 다시 push 하세요."
    ),
    merge_reasons.UNSTABLE_CI: (
        "CI 체크가 실패하거나 아직 실행 중입니다 — 모든 필수 상태 체크가 통과된 후 다시 시도하세요."
    ),
    merge_reasons.UNKNOWN_STATE_TIMEOUT: (
        "GitHub mergeable 상태 계산이 완료되지 않았습니다 — 잠시 후 PR 페이지를 새로고침하고 재시도하세요."
    ),
    merge_reasons.PERMISSION_DENIED: (
        "GitHub 토큰에 `pull_requests: write` 권한이 없습니다 — Fine-grained PAT 또는 GitHub App 권한을 확인하세요."
    ),
    merge_reasons.NOT_MERGEABLE: (
        "GitHub API가 Merge 불가 상태로 응답했습니다 — PR 페이지에서 상세 사유를 확인하세요."
    ),
    merge_reasons.UNPROCESSABLE: (
        "병합 조건이 충족되지 않았습니다 (422) — PR의 모든 체크와 보호 규칙을 확인하세요."
    ),
    merge_reasons.CONFLICT_SHA_CHANGED: (
        "Head SHA가 변경되었습니다 (409) — 다른 push가 선행된 경우 다음 push 시 자동 재시도됩니다."
    ),
    merge_reasons.NETWORK_ERROR: (
        "GitHub API 네트워크 오류 — 일시적 문제일 수 있습니다. PR 페이지에서 직접 Merge를 시도하세요."
    ),
}

_DEFAULT_ADVICE = "PR 페이지에서 Merge 조건을 확인하고 필요한 조치를 취하세요."


def get_advice(reason: str | None) -> str:
    """reason tag 로 권장 조치 텍스트를 반환. 알 수 없는 tag 는 기본 문구 반환.

    reason 은 'tag' 또는 'tag: user-facing text' 형식 모두 허용.
    """
    if not reason:
        return _DEFAULT_ADVICE
    tag = reason.split(":")[0].strip()
    return _ADVICE.get(tag, _DEFAULT_ADVICE)
