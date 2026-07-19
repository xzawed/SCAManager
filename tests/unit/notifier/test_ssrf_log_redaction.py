"""SSRF 차단 로그가 webhook URL 전문(=credential)을 남기지 않는지 검증 (2026-07-19 P0 후속).

🔴 사고 배경: `validate_external_url()` 실패 시 우리 코드 **5곳**이 webhook URL 을 통째로
로깅하고 있었다.

    logger.warning("send_discord_notification: blocked unsafe URL '%s'", webhook_url)

Discord/Slack/n8n/custom webhook URL 은 **경로 자체가 credential** 이다 — URL 하나면 별도
인증 없이 해당 채널에 임의 메시지를 게시할 수 있다. 즉 이 한 줄이 시크릿을 운영 로그에
평문으로 흘린다. 사용자 설정 오류나 일시적 DNS 실패만으로도 발화하는 흔한 경로다.
Discord/Slack/n8n/custom webhook URLs *are* the credential — the path grants unauthenticated
post access — so logging the full URL leaks a secret on a path that fires on mere DNS failure.

🔴 이 파일은 `src/logging_config.py` 의 리댁션 필터와 **독립된 축**을 잠근다:
- 필터(계층 2)는 **정규식에 등재된 패턴만** 마스킹한다 — n8n/custom webhook 은 임의 호스트라
  정규식으로 열거할 수 없다. 따라서 **호출처가 애초에 시크릿을 넘기지 않는 것**이 유일한 통제다.
- 그래서 아래 테스트는 리댁션 정규식이 절대 알 수 없는 **중립 호스트** URL 을 쓴다. 필터를
  아무리 강화해도 호출처를 고치지 않으면 반드시 실패한다(축 오염 방지).
This file locks an axis independent of the redaction filter: the filter only masks enumerated
patterns, and n8n/custom webhooks live on arbitrary hosts — so the *call site* is the only control.
The URLs below use a neutral host the regex can never know, so the test cannot pass by accident.
"""
import logging
from unittest.mock import AsyncMock, patch

import pytest

from src.analyzer.io.static import StaticAnalysisResult
from src.notifier.discord import send_discord_notification
from src.notifier.n8n import notify_n8n, notify_n8n_issue
from src.notifier.slack import send_slack_notification
from src.notifier.webhook import send_webhook_notification
from src.scorer.calculator import ScoreResult

# 🔴 명백한 더미만 — 실제 시크릿 형태는 gitleaks pre-commit 훅이 차단한다.
# Obvious dummy only; a realistic secret shape would be blocked by the gitleaks hook.
# 🔴 식별자·값에 "SECRET" 금지 — CodeQL py/clear-text-logging-sensitive-data 이름 휴리스틱이
# 발화해 테스트가 자초 alert 를 만든다 (#1109 실측). 경로 꼬리표라 TAIL 로 부른다.
# Do not name it *_SECRET: CodeQL's name heuristic makes the test self-inflict an alert.
_FAKE_WEBHOOK_TAIL = "XXXXWEBHOOKTAIL"
_FAKE_WEBHOOK_HOST = "hooks.example.test"
_FAKE_WEBHOOK_URL = f"https://{_FAKE_WEBHOOK_HOST}/services/T00FAKE/{_FAKE_WEBHOOK_TAIL}"


def _score() -> ScoreResult:
    return ScoreResult(
        total=82,
        grade="B",
        code_quality_score=22,
        security_score=18,
        breakdown={
            "code_quality": 22, "security": 18,
            "commit_message": 14, "ai_review": 21, "test_coverage": 7,
        },
    )


def _analysis() -> list[StaticAnalysisResult]:
    return [StaticAnalysisResult(filename="app.py")]


async def _call_discord(url: str) -> None:
    await send_discord_notification(
        webhook_url=url, repo_name="owner/repo", commit_sha="abc1234",
        score_result=_score(), analysis_results=_analysis(),
    )


async def _call_slack(url: str) -> None:
    await send_slack_notification(
        webhook_url=url, repo_name="owner/repo", commit_sha="abc1234",
        score_result=_score(), analysis_results=_analysis(),
    )


async def _call_n8n(url: str) -> None:
    await notify_n8n(
        webhook_url=url, repo_full_name="owner/repo", commit_sha="abc1234",
        pr_number=7, score_result=_score(),
    )


async def _call_n8n_issue(url: str) -> None:
    await notify_n8n_issue(
        webhook_url=url, repo_full_name="owner/repo", action="opened",
        issue={"number": 1, "title": "t", "body": "b"}, sender={"login": "john"},
    )


async def _call_webhook(url: str) -> None:
    await send_webhook_notification(
        webhook_url=url, repo_name="owner/repo", commit_sha="abc1234",
        score_result=_score(), analysis_results=_analysis(),
    )


# (patch 대상 모듈 경로, 호출 헬퍼) — 5 호출처 전수.
# 🔴 신규 notifier 채널 추가 시 여기에 행을 추가할 것(누락 = 시크릿 로깅 재발).
# One row per call site; add a row when a new notifier channel is introduced.
_CASES = [
    ("src.notifier.discord", _call_discord),
    ("src.notifier.slack", _call_slack),
    ("src.notifier.n8n", _call_n8n),
    ("src.notifier.n8n", _call_n8n_issue),
    ("src.notifier.webhook", _call_webhook),
]
_IDS = ["discord", "slack", "n8n_analysis", "n8n_issue", "custom_webhook"]


@pytest.mark.parametrize("module_path, call", _CASES, ids=_IDS)
async def test_blocked_url_log_omits_webhook_secret(module_path, call, caplog):
    """🔴 SSRF 차단 로그에 webhook URL 전문이 남지 않는다 — 호스트만 남긴다.

    `caplog` 는 pytest 자체 핸들러로 캡처하므로 `logging_config` 의 리댁션 필터를 **거치지
    않는다** — 즉 이 단언은 호출처가 넘긴 원본 인자를 그대로 본다. 필터로는 우회할 수 없는,
    호출처 단독 책임에 대한 단언이다.
    caplog captures via pytest's own handler (no redaction filter), so this asserts on exactly
    what the call site passed — it cannot be satisfied by hardening the filter.
    """
    caplog.set_level(logging.WARNING)

    with patch(f"{module_path}.validate_external_url", AsyncMock(return_value=False)):
        await call(_FAKE_WEBHOOK_URL)

    text = caplog.text

    assert text, (
        "차단 로그가 아예 없다 — 관측이 죽으면 오설정을 운영에서 진단할 수 없다"
        "(로그를 지우는 것은 시크릿 제거의 올바른 방법이 아니다)."
    )
    assert _FAKE_WEBHOOK_TAIL not in text, (
        f"🔴 webhook URL 의 시크릿 경로가 로그에 평문으로 남았다 — URL 하나로 해당 채널에 "
        f"임의 게시가 가능하다.\n로그: {text!r}"
    )
    assert _FAKE_WEBHOOK_URL not in text, (
        f"🔴 webhook URL 전문이 로그에 남았다 — 경로 전체가 credential 이다.\n로그: {text!r}"
    )
    assert _FAKE_WEBHOOK_HOST in text, (
        f"호스트마저 사라졌다 — 어느 채널 설정이 차단됐는지 판독 불가. 유출 차단과 운영 "
        f"판독성은 양립해야 한다(호스트는 남기고 경로만 제거).\n로그: {text!r}"
    )
