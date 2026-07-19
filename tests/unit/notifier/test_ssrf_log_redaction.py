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
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

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


@contextlib.contextmanager
def _ctx(value):
    """`with SessionLocal() as db:` 를 흉내내는 최소 컨텍스트 매니저.
    Minimal context manager standing in for `with SessionLocal() as db:`."""
    yield value


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


# ── 알림 실패 집계 로그 (pipeline `_send_notifications`) ──────────────────
#
# 🔴 위 5 호출처와 **다른 축**이다. 위쪽은 "SSRF 로 차단했을 때" 의 로그를 잠그지만, 여기는
# "발송을 시도했고 HTTP 로 실패했을 때" 의 로그다. httpx `raise_for_status()` 예외는
# 메시지에 URL 전문을 담으므로(`Client error '404 Not Found' for url '<...>'`),
# `%s`(=str(exc)) 나 `exc_info` 트레이스백으로 찍으면 경로 시크릿이 그대로 나간다.
#
# Telegram/Slack/Discord 는 `logging_config._SECRET_URL_PATTERNS` 가 마스킹하지만
# **n8n·custom webhook 은 임의 호스트라 정규식으로 열거할 수 없다** — 즉 이 축에서는
# 호출처(`_send_notifications`)가 유일한 통제다.


async def test_notification_failure_log_omits_webhook_secret(caplog):
    """🔴 알림 실패 로그가 webhook URL 경로(=credential)를 남기지 않는다.

    `caplog` 는 리댁션 필터를 거치지 않으므로, 이 단언은 호출처가 실제로 넘긴 것을 본다 —
    필터 강화로는 통과시킬 수 없다(n8n/custom 은 애초에 필터가 알 수 없는 호스트다).
    """
    # 지역 import — 모듈 로드 순서 오염 방지 (기존 pipeline 테스트 관용구).
    from src.worker.pipeline import _send_notifications  # pylint: disable=import-outside-toplevel

    request = httpx.Request("POST", _FAKE_WEBHOOK_URL)
    response = httpx.Response(404, request=request)

    async def _failing_channel() -> None:
        response.raise_for_status()

    caplog.set_level(logging.DEBUG)
    await _send_notifications([_failing_channel()], ["n8n"])

    text = caplog.text
    assert text, "실패 로그가 아예 없다 — 관측이 죽으면 알림 장애를 진단할 수 없다"
    assert _FAKE_WEBHOOK_TAIL not in text, (
        f"🔴 알림 실패 로그에 webhook URL 시크릿 경로가 남았다 — httpx 예외 메시지가 URL "
        f"전문을 담는데 str(exc)/exc_info 로 찍고 있다.\n로그: {text!r}"
    )
    assert "n8n" in text, (
        f"채널명이 사라졌다 — 어느 채널이 실패했는지 판독 불가.\n로그: {text!r}"
    )


async def test_n8n_issue_background_task_is_guarded(caplog):
    """🔴 n8n issue 릴레이가 **가드된 래퍼**로 디스패치돼 예외가 ASGI 밖으로 새지 않는다.

    무가드면 예외가 uvicorn 까지 올라가 `exc_info` 트레이스백으로 로깅되고, 그 안에
    시크릿 URL 이 실린다(리댁션 필터는 임의 호스트를 열거할 수 없어 못 막는다).
    Unguarded → uvicorn logs the traceback with the secret URL; the filter cannot cover it.
    """
    # 지역 import — 모듈 로드 순서 오염 방지.
    # 🔴 `from ... import` 가 아니라 **모듈 객체**로 받는다 — 아래 배선 테스트가 같은 모듈을
    # `import ... as _gh` 로 쓰므로, 두 형식을 섞으면 CodeQL `py/import-and-import-from`
    # (CI C2 가드)에 걸린다. 한 파일 안에서는 한 형식으로 통일한다.
    import src.webhook.providers.github as _gh  # pylint: disable=import-outside-toplevel

    request = httpx.Request("POST", _FAKE_WEBHOOK_URL)
    failing = httpx.HTTPStatusError(
        f"Client error '404 Not Found' for url '{_FAKE_WEBHOOK_URL}'",
        request=request,
        response=httpx.Response(404, request=request),
    )

    caplog.set_level(logging.DEBUG)
    with patch(
        "src.webhook.providers.github.notify_n8n_issue", AsyncMock(side_effect=failing)
    ):
        # 예외가 밖으로 나오면 여기서 터진다 = 가드 부재 (ASGI 탈출과 동형).
        # 🔴 전 인자 명시 — 래퍼가 `**kwargs` 가 아니라 명시 파라미터라 누락 시 TypeError 다
        # (그 엄격함이 `notify_n8n_issue` 시그니처 drift 를 잡아준다).
        await _gh._notify_n8n_issue_guarded(  # pylint: disable=protected-access
            webhook_url=_FAKE_WEBHOOK_URL,
            repo_full_name="owner/repo",
            action="opened",
            issue={"number": 1, "title": "t", "body": "b"},
            sender={"login": "john"},
        )

    text = caplog.text
    assert _FAKE_WEBHOOK_TAIL not in text, (
        f"🔴 가드가 예외 객체를 그대로 로깅해 시크릿 경로가 남았다 — 타입명만 남겨야 한다.\n"
        f"로그: {text!r}"
    )
    assert "HTTPStatusError" in text, (
        f"실패 사실이 로그에 없다 — 조용한 실패는 진단 불가.\n로그: {text!r}"
    )


async def test_issues_event_queues_a_guarded_task(caplog):
    """🔴 **배선** 단언 — `_handle_issues_event` 가 큐에 넣은 태스크를 실제로 실행해도 예외가 새지 않는다.

    위 테스트는 래퍼 함수만 검증한다. 래퍼를 만들어 놓고 `add_task` 가 여전히 무가드
    `notify_n8n_issue` 를 가리키면 래퍼는 **dead code** 이고 운영은 그대로 샌다
    (미배선 dead code 인데 전 스위트 green — 2026-07-17 학습).
    🔴 산문 grep 이 아니라 **큐에 등록된 태스크를 실제 실행**해 관측한다 (telegram 가드와 동일 관용구).
    Executes the queued task rather than grepping source — a wrapper that is never wired is dead code.
    """
    from fastapi import BackgroundTasks  # pylint: disable=import-outside-toplevel
    import src.webhook.providers.github as _gh  # pylint: disable=import-outside-toplevel

    request = httpx.Request("POST", _FAKE_WEBHOOK_URL)
    failing = AsyncMock(side_effect=httpx.HTTPStatusError(
        f"Client error '404 Not Found' for url '{_FAKE_WEBHOOK_URL}'",
        request=request, response=httpx.Response(404, request=request),
    ))

    config = MagicMock(n8n_webhook_url=_FAKE_WEBHOOK_URL)
    payload = {
        "repository": {"full_name": "owner/repo"},
        "action": "opened",
        "issue": {"number": 1, "title": "t", "body": "b"},
        "sender": {"login": "john"},
    }

    bg = BackgroundTasks()
    caplog.set_level(logging.DEBUG)
    # 🔴 patch 를 태스크 실행까지 유지 — 래퍼가 실행 시점에 모듈 전역을 해석하기 때문
    # (풀면 실제 함수가 나가 네트워크 계층에서 실패한다 — telegram 가드 테스트 학습).
    with patch.object(_gh, "SessionLocal", return_value=_ctx(MagicMock())), \
         patch.object(_gh, "get_repo_config", return_value=config), \
         patch.object(_gh, "notify_n8n_issue", failing):
        result = await _gh._handle_issues_event(payload, bg)  # pylint: disable=protected-access
        assert result == {"status": "accepted"}
        assert bg.tasks, "릴레이 태스크가 큐에 없다 — 배선 검증 전제 붕괴"
        # 실제 실행 — 여기서 예외가 새면 운영에서 uvicorn 이 시크릿 트레이스백을 남긴다.
        await bg()

    # 흡수하되 발송 자체는 시도해야 한다 — 가드가 발신을 없애면 기능 회귀다.
    failing.assert_awaited_once()
    assert _FAKE_WEBHOOK_TAIL not in caplog.text, (
        f"🔴 배선된 경로에서 시크릿 경로가 로그에 남았다.\n로그: {caplog.text!r}"
    )
