"""R46 Axis C — every score-rendering notifier discloses reliability.

Walks the notifier REGISTRY (plus github_comment + telegram_gate, which render scores
outside the registry) and asserts disclosure is present for an unreliable fixture.

Expectations are literal fingerprints — never imported from production modules.
"""
from __future__ import annotations

from types import SimpleNamespace

import src.notifier  # noqa: F401 — populate REGISTRY
from src.notifier.registry import REGISTRY
from src.scorer.calculator import ScoreResult

# 레지스트리에 등록된 점수 렌더 채널 — 리터럴 고정 (피검사 모듈에서 유도 금지).
# Score-rendering channels in REGISTRY — pinned as literals (do not read from module under test).
_EXPECTED_REGISTRY_SCORE_CHANNELS = frozenset({
    "telegram",
    "discord",
    "slack",
    "email",
    "webhook",
    "n8n",
    "commit_comment",
    "create_issue",
})

# 고지 지문 — en 로케일 경고 문구의 안정 부분 (i18n 키 값이 아니라 관측 문자열).
# Disclosure fingerprints — stable substrings of the en warning copy.
_FP_STATIC_INCOMPLETE = "Static analysis incomplete"
_FP_SCORE_UNRELIABLE_KEY = "score_unreliable"
_FP_REASONS_KEY = "reliability_reasons"
_FP_GATE = "Unverified or incomplete score"


def _unreliable_result() -> dict:
    return {
        "source": "push",
        "score": 89,
        "grade": "B",
        "breakdown": {
            "commit_message": 13,
            "code_quality": 25,
            "security": 20,
            "ai_review": 21,
            "test_coverage": 10,
            "ai_defaults_applied": True,
        },
        "ai_review_status": "disabled",
        "static_analysis_incomplete": True,
        "static_uncovered_languages": ["lua"],
        "ai_summary": "",
        "ai_suggestions": [],
        "issues": [],
    }


def _score_result() -> ScoreResult:
    r = _unreliable_result()
    return ScoreResult(
        total=r["score"],
        grade=r["grade"],
        code_quality_score=25,
        security_score=20,
        breakdown=r["breakdown"],
    )


def test_registry_contains_every_expected_score_channel():
    registered = {n.name for n in REGISTRY}
    missing = _EXPECTED_REGISTRY_SCORE_CHANNELS - registered
    assert not missing, f"REGISTRY missing score channels: {sorted(missing)}"


def test_every_registry_score_channel_discloses_reliability():
    """REGISTRY 의 점수 채널마다 신뢰도 고지가 렌더 결과에 나타난다.
    Each REGISTRY score channel must surface reliability disclosure in its render output.
    """
    result = _unreliable_result()
    score = _score_result()
    rendered: dict[str, str] = {}

    # telegram
    from src.notifier.telegram import _build_message
    rendered["telegram"] = _build_message(
        "o/r", "abc1234", score, [], None, language="en", result=result,
    )

    # discord
    from src.notifier.discord import _build_embed
    emb = _build_embed("o/r", "abc1234", score, [], None, language="en", result=result)
    rendered["discord"] = emb.get("description", "")

    # slack
    from src.notifier.slack import _build_payload
    payload = _build_payload("o/r", "abc1234", score, [], None, language="en", result=result)
    rendered["slack"] = str(payload.get("attachments", [{}])[0].get("pretext", ""))

    # email
    from src.notifier.email import _build_html_body
    rendered["email"] = _build_html_body(
        "o/r", "abc1234", score, [], None, language="en", result=result,
    )

    # webhook
    from src.notifier.webhook import _build_payload as _wh_payload
    wh = _wh_payload("o/r", "abc1234", score, [], None, result=result)
    rendered["webhook"] = str(wh)

    # n8n — build data dict the same way notify_n8n does (no network)
    from src.notifier.score_warnings import reliability_payload
    rel = reliability_payload(result)
    n8n_data = {
        "score": score.total,
        "score_unreliable": rel["score_unreliable"],
        "reliability_reasons": rel["reliability_reasons"],
    }
    rendered["n8n"] = str(n8n_data)

    # commit_comment reuses github_comment builder
    from src.notifier.github_comment import _build_comment_from_result
    rendered["commit_comment"] = _build_comment_from_result(result, language="en")

    # create_issue
    from src.notifier.github_issue import _build_issue_body
    rendered["create_issue"] = _build_issue_body(
        "o/r", "abc1234", 1, result, [], language="en",
    )

    for name in sorted(_EXPECTED_REGISTRY_SCORE_CHANNELS):
        body = rendered[name]
        if name in ("webhook", "n8n"):
            assert _FP_SCORE_UNRELIABLE_KEY in body, f"{name}: missing score_unreliable"
            assert "True" in body or "true" in body.lower(), f"{name}: score_unreliable not true"
            assert _FP_REASONS_KEY in body or "static_incomplete" in body, (
                f"{name}: missing reliability reasons"
            )
        else:
            assert _FP_STATIC_INCOMPLETE in body or "Static analysis not run" in body or (
                "AI review was not fully verified" in body
            ), f"{name}: missing human reliability disclosure\n---\n{body[:400]}"


def test_github_comment_discloses_reliability():
    """github_comment 는 REGISTRY 밖이지만 점수 표준 표면 — 고지 의무.
    github_comment is outside REGISTRY but is the score-comment standard.
    """
    from src.notifier.github_comment import _build_comment_from_result
    body = _build_comment_from_result(_unreliable_result(), language="en")
    assert _FP_STATIC_INCOMPLETE in body or "Static analysis not run" in body
    assert "AI review was not fully verified" in body or "AI review failed" in body


def test_telegram_gate_warns_next_to_approve_buttons():
    """반자동 Approve/Reject 버튼 메시지에 신뢰도 경고가 붙는다 (R46)."""
    import asyncio
    from unittest.mock import AsyncMock, patch

    from src.gate.telegram_gate import send_gate_request

    captured: dict = {}

    async def _capture(_bot_token, _chat_id, payload):
        captured["text"] = payload.get("text", "")
        captured["markup"] = payload.get("reply_markup")

    async def _run():
        with patch(
            "src.gate.telegram_gate.telegram_post_message",
            new=AsyncMock(side_effect=_capture),
        ):
            await send_gate_request(
                bot_token="t",
                chat_id="1",
                analysis_id=9,
                repo_full_name="o/r",
                pr_number=3,
                score_result=_score_result(),
                language="en",
                result=_unreliable_result(),
            )

    asyncio.run(_run())
    text = captured.get("text", "")
    assert _FP_GATE in text, f"gate message missing reliability warning: {text!r}"
    markup = captured.get("markup") or {}
    buttons = str(markup)
    assert "gate:approve" in buttons and "gate:reject" in buttons


def test_reliable_result_has_no_disclosure_noise():
    """정상 점수는 고지를 붙이지 않는다 (false warning 방지)."""
    from src.notifier.score_warnings import unreliable_score_warning_lines
    clean = {
        "source": "pr",
        "ai_review_status": "success",
        "breakdown": {},
        "static_uncovered_languages": [],
    }
    assert unreliable_score_warning_lines(clean, "en") == []
