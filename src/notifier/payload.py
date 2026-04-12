"""분석 알림 공통 페이로드 — notifier 함수 파라미터 단일화."""
from dataclasses import dataclass, field

from src.scorer.calculator import ScoreResult
from src.analyzer.static import StaticAnalysisResult
from src.analyzer.ai_review import AiReviewResult


@dataclass
class NotificationPayload:
    """분석 알림에 필요한 공통 데이터를 묶는 dataclass.

    모든 notifier 공개 함수에 개별 positional 파라미터 대신 이 객체를 전달한다.
    """

    repo_name: str
    commit_sha: str
    score_result: ScoreResult
    analysis_results: list[StaticAnalysisResult] = field(default_factory=list)
    pr_number: int | None = None
    ai_review: AiReviewResult | None = None
