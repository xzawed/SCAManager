import httpx
from src.scorer.calculator import ScoreResult


async def send_gate_request(
    bot_token: str,
    chat_id: str,
    analysis_id: int,
    repo_full_name: str,
    pr_number: int,
    score_result: ScoreResult,
) -> None:
    text = (
        f"🔍 *PR 검토 요청*\n"
        f"리포: `{repo_full_name}` — PR #{pr_number}\n"
        f"점수: *{score_result.total}점* ({score_result.grade}등급)\n\n"
        f"승인 또는 반려를 선택하세요."
    )
    reply_markup = {
        "inline_keyboard": [[
            {"text": "✅ 승인", "callback_data": f"gate:approve:{analysis_id}"},
            {"text": "❌ 반려", "callback_data": f"gate:reject:{analysis_id}"},
        ]]
    }
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": reply_markup,
        })
        r.raise_for_status()
