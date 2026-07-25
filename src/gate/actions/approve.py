"""ApproveAction — score 기반 GitHub Approve/Reject 또는 Telegram 반자동 요청 Gate 액션.
ApproveAction — approves/rejects PRs via GitHub review or sends Telegram semi-auto request.

Sprint E-final: 구현이 이 모듈에 직접 포함됨 (engine.py 위임 제거).
Sprint E-final: Implementation lives here directly (delegation to engine.py removed).
"""
import logging

import httpx

from src.config import settings
from src.database import WorkerSessionLocal as SessionLocal
from src.gate._common import ai_review_failed
from src.gate._common import score_from_result as _score_from_result
from src.gate.actions import GateAction, GateContext, register
from src.gate.github_review import HeadMovedError, post_github_review
from src.gate.telegram_gate import send_gate_request
from src.i18n.loader import get_text
from src.notifier._language import resolve_notification_language
from src.repositories import gate_decision_repo
from src.shared.log_safety import sanitize_for_log

logger = logging.getLogger(__name__)


class ApproveAction(GateAction):
    """Approve Gate 옵션 — auto/semi-auto 분기.
    Auto mode: approves/rejects via GitHub review based on score thresholds.
    Semi-auto mode: sends Telegram inline keyboard for human decision.

    P0-H: 독립 SessionLocal() 사용 — asyncio.gather 병렬 실행 시 Session 공유 금지.
    P0-H: Uses independent SessionLocal() — do not share with gather siblings.
    """

    def is_applicable(self, config) -> bool:
        """approve_mode가 'disabled'가 아닐 때 실행."""
        return config.approve_mode != "disabled"

    async def execute(self, ctx: GateContext) -> None:
        """설정 모드에 따라 auto/semi-auto 분기를 실행한다."""
        if ctx.config.approve_mode == "auto":
            await self._run_auto(ctx)
        elif ctx.config.approve_mode == "semi-auto":
            await self._run_semi_auto(ctx)

    async def _run_auto(self, ctx: GateContext) -> None:
        """Auto Approve — score 기준 approve/reject/skip.

        정적분석 불완전(타임아웃) 시 자동 approve 보류 — 미분석 코드는 점수가 인플레이션될 수
        있고, auto-approve 가 branch-protection "approval 시 자동머지" 를 간접 트리거할 수
        있으므로 결정을 내리지 않는다 (#779 auto-merge 가드의 approve 경로 확장).
        Hold auto-approve when static analysis is incomplete (timeout) — unanalyzed code may have an
        inflated score, and an auto-approve could indirectly trigger branch-protection
        "auto-merge on approval", so make no decision (#779 auto-merge guard extended to approve).
        """
        if ctx.result.get("static_analysis_incomplete"):
            logger.warning(
                "static analysis incomplete — auto-approve skipped (repo=%s, pr=%s)",
                ctx.repo_name, ctx.pr_number,
            )
            return
        # C22: AI 리뷰 diff 절단(truncated) 시 보류 — 잘린 부분 미검토로 점수가 인플레될 수
        # 있고, auto-approve 가 branch-protection 자동머지를 간접 트리거할 수 있어 결정하지 않는다.
        # C22: hold auto-approve when the AI-review diff was truncated — the unseen part may inflate
        # the score and auto-approve could indirectly trigger branch-protection auto-merge.
        if ctx.result.get("ai_review_truncated"):
            logger.warning(
                "AI review diff truncated — auto-approve skipped (repo=%s, pr=%s)",
                ctx.repo_name, ctx.pr_number,
            )
            return
        # AI 리뷰 실제 실패(api_error/parse_error) 시도 보류 — 중립-고점 기본값이 점수를
        # 인플레이션하고, auto-approve 가 branch-protection "approval 시 자동머지" 를 간접
        # 트리거할 수 있으므로 결정을 내리지 않는다 (#8, auto-merge 가드의 approve 경로 확장).
        # Also hold auto-approve when the AI review genuinely failed — inflated defaults could
        # indirectly trigger branch-protection "auto-merge on approval" (#8, extends the merge guard).
        if ai_review_failed(ctx.result):
            logger.warning(
                "AI review failed (%s) — auto-approve skipped (repo=%s, pr=%s)",
                ctx.result.get("ai_review_status"), ctx.repo_name, ctx.pr_number,
            )
            return
        # 알림 언어 결정 (3-layer fallback) — GitHub PR 댓글을 리포 소유자 언어로 게시
        # Resolve notification language (3-layer fallback) — post PR review in owner's language
        with SessionLocal() as db:
            language = resolve_notification_language(db, config=ctx.config)
        if ctx.score >= ctx.config.approve_threshold:
            decision = "approve"
            body = get_text(
                "notifier.gate.auto_approve", language,
                score=ctx.score, threshold=ctx.config.approve_threshold,
            )
        elif ctx.score < ctx.config.reject_threshold:
            decision = "reject"
            body = get_text(
                "notifier.gate.auto_reject", language,
                score=ctx.score, threshold=ctx.config.reject_threshold,
            )
        else:
            with SessionLocal() as db:
                gate_decision_repo.upsert(db, ctx.analysis_id, "skip", "auto")
            return
        try:
            await post_github_review(
                ctx.github_token, ctx.repo_name, ctx.pr_number, decision, body,
                # 🔴 분석 SHA 결속 (준비도 감사 #8) — 강제는 post_github_review 가 POST 전 head 를
                # 조회해 직접 한다. **GitHub 은 막아주지 않는다**(owed #1072 실측: 구 SHA 200 수락).
                # 🔴 Enforced client-side by post_github_review; GitHub does NOT reject a stale SHA.
                commit_id=ctx.commit_sha,
            )
            with SessionLocal() as db:
                gate_decision_repo.upsert(db, ctx.analysis_id, decision, "auto")
        except HeadMovedError as exc:
            # 🔴 분석 SHA ≠ 현재 head — **정상 fail-closed** 이므로 INFO(ERROR 아님).
            # force-push 잦은 리포에서 매 드리프트마다 ERROR 가 쌓여 진짜 실패를 은폐하지 않도록 강등.
            # gate_decision 은 upsert 미도달로 미기록 — 새 head 는 자신의 synchronize 웹훅이 재게이트.
            # 🔴 Expected fail-closed (analyzed SHA != current head) — INFO, not ERROR.
            logger.info(
                "GitHub Review skipped — head moved since analysis (fail-closed): %s (%s)",
                ctx.repo_name, exc,
            )
        except (httpx.HTTPError, KeyError) as exc:
            # 🔴 422 를 'head 이동'으로 단정하지 않는다 — 실측상 422 는 head 이동에서 오지 **않는다**
            # (owed #1072: 구 SHA 도 GitHub 은 200 으로 수락). 실제 422 사유는 self-approval
            # (`Can not approve your own pull request`)·존재하지 않는 commitOID 등이며, head 드리프트는
            # 위 HeadMovedError 가 POST 전에 잡는다. 원인을 모르는 채 특정 원인을 적으면 운영자가
            # 엉뚱한 곳을 파므로 사유를 지어내지 않고 WARNING 으로 남긴다.
            # 🔴 Do NOT attribute a 422 to a moved head — measurements disproved that (owed #1072).
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status == 422:
                logger.warning(
                    "GitHub Review 거부됨 — HTTP 422 (사유는 응답 본문: self-approval·commitOID 부재 등): %s",
                    ctx.repo_name,
                )
            else:
                logger.error("GitHub Review 실패: %s", type(exc).__name__)

    async def _run_semi_auto(self, ctx: GateContext) -> None:
        """Semi-auto Approve — Telegram 인라인 키보드 발송.

        🔴 정적분석 불완전·AI 리뷰 실패 시 가드(_run_auto 와 대칭): 인플레 기본 점수를 사람에게
        승인 버튼으로 노출하면 오해된 점수로 approve+merge 될 수 있으므로 발송하지 않는다
        (#8/#779 fail-open 봉인의 semi-auto 경로 — 이전엔 자동 경로에만 가드 존재).
        Hold the semi-auto approval request when static analysis is incomplete or the AI review
        genuinely failed (mirrors _run_auto): showing an inflated default score on a human approval
        button could lead to approve+merge of unvetted code (#8/#779 fail-open seal for the semi-auto
        path — previously only the auto path had the guard).
        """
        if ctx.result.get("static_analysis_incomplete"):
            logger.warning(
                "static analysis incomplete — semi-auto approve skipped (repo=%s, pr=%s)",
                ctx.repo_name, ctx.pr_number,
            )
            return
        # C22: AI 리뷰 diff 절단(truncated) 시 미발송 — 절단된 일부만 보고 매긴 인플레 점수를
        # 사람 승인 버튼으로 노출하면 오해된 점수로 approve+merge 될 수 있다 (_run_auto 가드 대칭).
        # C22: don't send when the AI-review diff was truncated — showing a partial-diff inflated
        # score on a human approval button could lead to approve+merge (mirrors _run_auto).
        if ctx.result.get("ai_review_truncated"):
            logger.warning(
                "AI review diff truncated — semi-auto approve skipped (repo=%s, pr=%s)",
                ctx.repo_name, ctx.pr_number,
            )
            return
        if ai_review_failed(ctx.result):
            logger.warning(
                "AI review failed (%s) — semi-auto approve skipped (repo=%s, pr=%s)",
                ctx.result.get("ai_review_status"), ctx.repo_name, ctx.pr_number,
            )
            return
        if not ctx.config.notify_chat_id:
            logger.warning(
                "semi-auto 모드이나 notify_chat_id 미설정: %s",
                sanitize_for_log(ctx.repo_name),
            )
            return
        # 알림 언어 결정 (3-layer fallback) — Telegram 검토 요청을 수신자 언어로 발송
        # Resolve notification language (3-layer fallback) — send Telegram request in recipient's language
        with SessionLocal() as db:
            language = resolve_notification_language(db, config=ctx.config)
        try:
            score_result = _score_from_result(ctx.result)
            await send_gate_request(
                bot_token=settings.telegram_bot_token,
                chat_id=ctx.config.notify_chat_id,
                analysis_id=ctx.analysis_id,
                repo_full_name=ctx.repo_name,
                pr_number=ctx.pr_number,
                score_result=score_result,
                language=language,
            )
        except (httpx.HTTPError, KeyError) as exc:
            logger.error("Telegram Gate 요청 실패: %s", type(exc).__name__)


register(ApproveAction())
