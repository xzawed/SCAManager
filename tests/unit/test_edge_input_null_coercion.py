"""AI 리뷰 소비처의 null/비-dict edge-input 방어 (종합감사 P2).

Consumer-side guards against null / non-dict AI-review fields (comprehensive audit P2).

LLM(또는 CLI ai_result)이 유효-JSON 이지만 `file_feedbacks` 원소를 dict 대신 str 로, `issues` 를
[] 대신 null 로 emit 하면, 소비처가 `.get()` AttributeError / `for x in None` TypeError 로 크래시해
PR 코멘트·CLI 리뷰 출력이 무음 붕괴한다. 원천 필터(_parse_response)와 belt+suspenders 로 소비처도
방어한다. 이 파일은 두 소비처(CLI formatter · GitHub PR 코멘트)를 실행 관측으로 잠근다.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")

# pylint: disable=wrong-import-position
from src.analyzer.io.ai_review import AiReviewResult
from src.cli.formatter import _ai_file_feedback_section
from src.notifier.github_comment import _build_comment_from_result


def _ai_with_bad_file_feedbacks() -> AiReviewResult:
    """file_feedbacks 에 비-dict 원소 + present-null issues 를 섞은 AiReviewResult.
    An AiReviewResult mixing a non-dict element and a present-null issues list.
    """
    return AiReviewResult(
        commit_score=15, ai_score=16, test_score=8, summary="ok",
        file_feedbacks=[
            "라인 10: 개선 필요",                       # str 원소 — .get() 대상 아님 / non-dict
            {"file": "app.py", "issues": None},          # present-null issues
            {"file": "b.py", "issues": ["정상 이슈"]},   # 정상 / normal
        ],
    )


def test_cli_formatter_survives_non_dict_and_null_issues():
    """CLI(`make review`) 파일 피드백 섹션이 비-dict 원소·null issues 에도 크래시하지 않는다.
    The CLI file-feedback section must not crash on a non-dict element or null issues.
    """
    lines = _ai_file_feedback_section(_ai_with_bad_file_feedbacks(), use_color=False)
    # 정상 dict 원소는 렌더되고, 나쁜 원소는 조용히 건너뛴다
    # The valid dict element renders; the bad ones are skipped
    joined = "\n".join(lines)
    assert "b.py" in joined
    assert "정상 이슈" in joined


def test_github_comment_survives_null_issues():
    """GitHub PR 코멘트 빌더가 file_feedbacks 의 present-null issues 에도 크래시하지 않는다.
    The GitHub PR-comment builder must not crash on present-null issues.
    """
    result = {
        "total_score": 82, "grade": "B",
        "breakdown": {"code_quality": 28, "security": 20, "commit_message": 17,
                      "ai_review": 15, "test_coverage": 2},
        "ai_summary": "ok",
        "file_feedbacks": [
            "비-dict 원소",
            {"file": "app.py", "issues": None},
            {"file": "b.py", "issues": ["정상 이슈"]},
        ],
    }
    body = _build_comment_from_result(result, language="ko")
    assert isinstance(body, str) and body
    assert "b.py" in body
