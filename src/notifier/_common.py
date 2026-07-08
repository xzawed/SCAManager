"""notifier 모듈 공용 헬퍼 — 이슈 수집·메시지 포매팅·truncate."""
from __future__ import annotations

from src.constants import (
    COMMIT_SHA_DISPLAY_LENGTH,
    NOTIFIER_MESSAGE_TRUNCATE,
)


def format_ref(commit_sha: str, pr_number: int | None, language: str = "ko") -> str:
    """PR 번호 또는 단축 커밋 SHA 레퍼런스 문자열을 반환한다.

    Format a PR number or short commit SHA reference string.
    language: 커밋 레퍼런스 i18n (push 이벤트 — pr_number 없을 때).
    language: i18n for the commit reference (push event — when pr_number is absent).
    """
    if pr_number:
        return f"PR #{pr_number}"
    # 커밋 레퍼런스 i18n — push 이벤트 시 수신자 언어 적용 (사이클 152 P0-A)
    # Commit reference i18n — apply recipient language on push events
    from src.i18n.loader import get_text  # noqa: WPS433  # pylint: disable=import-outside-toplevel
    return get_text(
        "notifier.common.commit_ref", language, sha=commit_sha[:COMMIT_SHA_DISPLAY_LENGTH],
    )


def resolve_ai_summary(ai_review, language: str = "ko") -> "str | None":
    """AI 리뷰 summary 표시 문자열을 해소한다 — 실패 status 시 현지화 메시지로 대체.

    Resolve the AI review summary display string. When the review failed
    (status != "success"), return the localized "unavailable" message instead
    of the raw fallback — prevents hardcoded Korean leaking to notify channels
    (사이클 155 P1: AiReviewResult.summary 가 발신 경로로 흐르는 upstream 필드).
    """
    if ai_review is None:
        return None
    # 실패 fallback (no_api_key/api_error/empty_diff/parse_error) → 수신자 언어로 현지화
    # Failure fallback → localize in the recipient's language
    status = getattr(ai_review, "status", "success")
    if status != "success":
        from src.i18n.loader import get_text  # noqa: WPS433  # pylint: disable=import-outside-toplevel
        # 의도적 비활성(disabled)은 "실패/불가"가 아니라 "설정으로 끔"으로 안내 — 그 외 실패는 generic.
        # disabled (intentional off) → "turned off by config"; other non-success → generic unavailable.
        key = "notifier.common.ai_disabled" if status == "disabled" else "notifier.common.ai_unavailable"
        return get_text(key, language)
    return ai_review.summary or None


def get_all_issues(analysis_results: list) -> list:
    """analysis_results의 모든 AnalysisIssue를 평탄화한다 (호출자 캐시 권장 — hot path).

    Flatten all AnalysisIssue from analysis_results (callers should cache — hot path).
    """
    return [issue for r in analysis_results for issue in r.issues]


def truncate_message(text: str, max_length: int, suffix: str = "...") -> str:
    """텍스트를 max_length 이하로 절단하고 suffix를 붙인다 (출력 길이 ≤ max_length 보장).

    Truncate to <= max_length and append suffix (output length never exceeds max_length).
    """
    if len(text) <= max_length:
        return text
    # max_length < len(suffix) 시 음수 슬라이스 방지 + 최종 클램프로 계약 보장 (감사 notifier-004)
    # Guard against negative slice when max_length < len(suffix); final clamp enforces the contract.
    cut = max(max_length - len(suffix), 0)
    return (text[:cut] + suffix)[:max_length]


def truncate_issue_msg(msg: str) -> str:
    """이슈 메시지를 표준 표시 길이(NOTIFIER_MESSAGE_TRUNCATE)로 절단한다."""
    return msg[:NOTIFIER_MESSAGE_TRUNCATE]


# GFM/CommonMark 활성 문자 — 링크/이미지/코드/강조/표/헤딩 인젝션 차단 대상
# GFM/CommonMark active chars — neutralize link/image/code/emphasis/table/heading injection
_MD_SPECIAL_CHARS = set("\\`*_[]()<>~|#!")


def escape_markdown(text: str) -> str:
    """untrusted plain-text(정적 도구 issue.message)를 GFM/CommonMark 채널(GitHub·Discord)에
    안전하게 삽입하도록 markdown 활성 문자를 백슬래시 이스케이프한다 (감사 D — 아웃바운드 인젝션).

    Backslash-escape markdown-active chars so untrusted plain text (static-tool issue messages)
    can be safely embedded in GFM/CommonMark channels (GitHub, Discord) — blocks link/image/code/
    mention injection. 🔴 AI 요약·피드백(Claude 의도 markdown 프로즈)에는 적용 금지 — 렌더링
    품질 보존(정책 16 명시 제외). NOT for AI summary/feedback (intended markdown prose).
    """
    out = []
    for ch in text:
        if ch in _MD_SPECIAL_CHARS:
            out.append("\\")
        out.append(ch)
    return "".join(out)


def escape_slack_mrkdwn(text: str) -> str:
    """untrusted plain-text 를 Slack mrkdwn 에 안전하게 삽입 — Slack 공식 escape(`&` `<` `>`)로
    `<url|text>` 링크·`<!channel>` 멘션 인젝션 차단 (Slack 은 백슬래시 escape 미지원).

    Escape for Slack mrkdwn using Slack's documented entities (& < >) — neutralizes
    `<url|text>` links and `<!channel>` mentions (Slack does not support backslash escaping).
    `&` 를 먼저 치환해 새로 삽입한 엔티티의 `&` 가 이중 이스케이프되지 않게 한다.
    Replace `&` first so the `&` in the entities we insert is not double-escaped.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
