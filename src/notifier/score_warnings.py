"""점수 신뢰도 고지 — 채널 공통 (R46 Axis C).
Score reliability disclosure shared across notification channels (R46 Axis C).

github_comment 가 쓰던 배너를 단일 출처로 옮기고, 점수를 렌더하는 모든 채널이 경유한다.
Moves the github_comment banner to a single source; every score-rendering channel uses it.
"""
from __future__ import annotations

from html import escape

from src.gate._common import ai_review_failed
from src.i18n.loader import get_text

# i18n 키 접두 — github_pr_comment 에 기존 키가 있어 그 네임스페이스를 공유한다 (복제 drift 방지).
# i18n key prefix — reuse github_pr_comment keys to avoid duplicating copy.
_KEY_PREFIX = "notifier.github_pr_comment"


def unreliable_score_warning_lines(
    result: dict | None,
    language: str = "en",
    *,
    flavor: str = "md",
) -> list[str]:
    """점수 신뢰 불가 경고 줄 목록. 비어 있으면 고지 불필요.
    Warning lines when the rendered score is inflated/unreliable; empty when none apply.

    flavor:
      - "md": GitHub markdown blockquote
      - "html": Telegram/email HTML-safe plain emphasis
      - "plain": Discord/Slack plain text
      - "codes": machine channels — reason code strings only
    """
    if not result:
        return []
    raw: list[str] = []
    codes: list[str] = []

    if result.get("static_analysis_incomplete"):
        key = (
            "static_skipped_cli_warning"
            if result.get("source") == "cli"
            else "static_incomplete_warning"
        )
        raw.append(get_text(f"{_KEY_PREFIX}.{key}", language))
        codes.append("static_incomplete" if key == "static_incomplete_warning" else "static_skipped_cli")

    if ai_review_failed(result):
        raw.append(get_text(f"{_KEY_PREFIX}.ai_failed_warning", language))
        codes.append("ai_failed")

    # R46: AI 기본값·disabled 도 고지 — gate 차단은 안 하지만 점수는 미검증.
    # R46: also disclose AI defaults/disabled — not a gate block, but the score is unverified.
    status = result.get("ai_review_status")
    breakdown = result.get("breakdown") if isinstance(result.get("breakdown"), dict) else {}
    defaults_applied = breakdown.get("ai_defaults_applied") is True
    if status in ("disabled", "no_api_key", "empty_diff") or (
        defaults_applied and not ai_review_failed(result)
    ):
        raw.append(get_text(f"{_KEY_PREFIX}.ai_defaults_warning", language))
        codes.append("ai_defaults")

    uncovered = result.get("static_uncovered_languages") or []
    if uncovered:
        raw.append(get_text(
            f"{_KEY_PREFIX}.static_uncovered_warning", language,
            languages=", ".join(uncovered),
        ))
        codes.append("static_uncovered")

    if not raw:
        return []

    if flavor == "codes":
        return codes

    lines = [_format_line(line, flavor) for line in raw]
    if flavor == "md":
        lines.append("")  # 배너와 헤더 사이 빈 줄
    return lines


def _format_line(line: str, flavor: str) -> str:
    """채널 flavor 에 맞게 마크다운 장식을 조정한다.
    Adjust markdown decoration for the channel flavor.
    """
    if flavor == "md":
        return line
    plain = line.lstrip("> ").strip().replace("**", "")
    if flavor == "html":
        return f"⚠️ {escape(plain.lstrip('⚠️').strip())}"
    # plain / slack
    return plain


def reliability_payload(result: dict | None) -> dict:
    """기계 채널(n8n/webhook)용 구조화 신뢰도 필드.
    Structured reliability fields for machine channels (n8n/webhook).
    """
    codes = unreliable_score_warning_lines(result, "en", flavor="codes")
    return {
        "score_unreliable": bool(codes),
        "reliability_reasons": codes,
    }
