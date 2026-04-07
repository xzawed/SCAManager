import httpx
from src.scorer.calculator import ScoreResult
from src.analyzer.static import StaticAnalysisResult
from src.analyzer.ai_review import AiReviewResult

GRADE_EMOJI = {"A": "🟢", "B": "🔵", "C": "🟡", "D": "🟠", "F": "🔴"}


def _build_comment_body(
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    ai_review: AiReviewResult | None,
) -> str:
    grade_emoji = GRADE_EMOJI.get(score_result.grade, "⚪")
    bd = score_result.breakdown

    lines = [
        f"## {grade_emoji} SCAManager 분석 결과",
        "",
        f"**총점: {score_result.total}/100** (등급 {score_result.grade})",
        "",
        "### 점수 상세",
        "| 항목 | 점수 | 만점 |",
        "|------|------|------|",
        f"| 커밋 메시지 | {bd['commit_message']} | 15 |",
        f"| 코드 품질 | {bd['code_quality']} | 25 |",
        f"| 보안 | {bd['security']} | 20 |",
        f"| 구현 방향성 (AI) | {bd['ai_review']} | 25 |",
        f"| 테스트 | {bd['test_coverage']} | 15 |",
    ]

    if ai_review and ai_review.summary:
        lines += ["", "### AI 요약", ai_review.summary]

    # 카테고리별 상세 피드백
    if ai_review:
        feedback_items = [
            ("커밋 메시지", ai_review.commit_message_feedback),
            ("코드 품질", ai_review.code_quality_feedback),
            ("보안", ai_review.security_feedback),
            ("구현 방향성", ai_review.direction_feedback),
            ("테스트", ai_review.test_feedback),
        ]
        has_feedback = any(fb for _, fb in feedback_items)
        if has_feedback:
            lines += ["", "### 카테고리별 피드백"]
            for label, fb in feedback_items:
                if fb:
                    lines.append(f"- **{label}**: {fb}")

    # 파일별 피드백
    if ai_review and ai_review.file_feedbacks:
        lines += ["", "### 파일별 피드백"]
        for ff in ai_review.file_feedbacks:
            lines.append(f"#### `{ff.get('file', '?')}`")
            for issue in ff.get("issues", []):
                lines.append(f"- {issue}")

    if ai_review and ai_review.suggestions:
        lines += ["", "### 개선 제안"]
        for s in ai_review.suggestions:
            lines.append(f"- {s}")

    all_issues = [i for r in analysis_results for i in r.issues]
    if all_issues:
        lines += ["", "### 정적 분석 이슈 (상위 10건)"]
        for issue in all_issues[:10]:
            lines.append(f"- **[{issue.tool}]** {issue.message} (line {issue.line})")

    return "\n".join(lines)


async def post_pr_comment(
    github_token: str,
    repo_name: str,
    pr_number: int,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    ai_review: AiReviewResult | None,
) -> None:
    body = _build_comment_body(score_result, analysis_results, ai_review)
    url = f"https://api.github.com/repos/{repo_name}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={"body": body}, headers=headers)
        r.raise_for_status()
