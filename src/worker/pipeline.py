import logging
from sqlalchemy.orm import Session
from src.database import SessionLocal
from src.config import settings
from src.github_client.diff import get_pr_files, get_push_files
from src.analyzer.static import analyze_file
from src.scorer.calculator import calculate_score
from src.notifier.telegram import send_analysis_result
from src.models.repository import Repository
from src.models.analysis import Analysis

logger = logging.getLogger(__name__)


async def run_analysis_pipeline(event: str, data: dict) -> None:
    try:
        repo_name: str = data["repository"]["full_name"]

        if event == "pull_request":
            pr_number: int | None = data["number"]
            commit_sha: str = data["pull_request"]["head"]["sha"]
            files = get_pr_files(settings.github_token, repo_name, pr_number)
        else:
            pr_number = None
            commit_sha = data["after"]
            files = get_push_files(settings.github_token, repo_name, commit_sha)

        if not files:
            logger.info("No Python files changed in %s @ %s", repo_name, commit_sha)
            return

        analysis_results = [analyze_file(f.filename, f.content) for f in files]
        score_result = calculate_score(analysis_results)

        db: Session = SessionLocal()
        try:
            repo = db.query(Repository).filter_by(full_name=repo_name).first()
            if not repo:
                repo = Repository(
                    full_name=repo_name,
                    telegram_chat_id=settings.telegram_chat_id,
                )
                db.add(repo)
                db.flush()

            existing = db.query(Analysis).filter_by(
                commit_sha=commit_sha, repo_id=repo.id
            ).first()
            if existing:
                logger.info("Commit %s already analyzed, skipping", commit_sha)
                return

            analysis = Analysis(
                repo_id=repo.id,
                commit_sha=commit_sha,
                pr_number=pr_number,
                score=score_result.total,
                grade=score_result.grade,
                result={
                    "breakdown": score_result.breakdown,
                    "issues": [
                        {
                            "tool": i.tool,
                            "severity": i.severity,
                            "message": i.message,
                            "line": i.line,
                        }
                        for r in analysis_results
                        for i in r.issues
                    ],
                },
            )
            db.add(analysis)
            db.commit()
        finally:
            db.close()

        await send_analysis_result(
            bot_token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id,
            repo_name=repo_name,
            commit_sha=commit_sha,
            score_result=score_result,
            analysis_results=analysis_results,
            pr_number=pr_number,
        )

    except Exception:
        logger.exception("Analysis pipeline failed for event=%s", event)
