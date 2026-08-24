"""build_analysis_result_dict 회귀 가드 — Analysis.result JSON 직렬화 보강.

Issue: Phase 11 시점 build_analysis_result_dict 가 issues JSON 에 category /
language 필드를 직렬화하지 않았음 (pipeline.py:75-79). dashboard 재설계
기획 (PR #181) 의 데이터 자산 정찰에서 발견 — 향후 언어별·카테고리별
사후 분석 차단 위험.

본 모듈은 직렬화 필드 6 종 (tool, severity, message, line, category, language)
보존을 회귀 가드로 검증.

Regression guard for build_analysis_result_dict — ensures issues JSON contains
all 6 fields so future dashboards can slice by language/category.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from src.worker.pipeline import build_analysis_result_dict


# ─── 더블 (의존성 모킹) ─────────────────────────────────────────────────────


@dataclass
class _StubIssue:
    tool: str = "pylint"
    severity: str = "warning"
    message: str = "unused import"
    line: int = 12
    category: str = "code_quality"
    language: str = "python"


@dataclass
class _StubAnalysisResult:
    issues: list[_StubIssue] = field(default_factory=list)
    # 🔴 실제 `StaticAnalysisResult` 에는 `filename` 이 있다(src/analyzer/io/static.py:104).
    #   더블이 그 필드를 빠뜨리고 있어서, 투영이 filename 을 버리는 것을 아무도 못 봤다.
    #   The real dataclass has `filename`; the double omitted it, hiding the dropped projection.
    filename: str = "app.py"


def _make_ai_review() -> SimpleNamespace:
    """AiReviewResult 형 더블 — pipeline 함수가 attribute 만 사용하므로 SimpleNamespace 충분."""
    return SimpleNamespace(
        status="success",
        error_type=None,
        error_status_code=None,
        summary="ok",
        suggestions=[],
        commit_message_feedback="commit ok",
        code_quality_feedback="cq ok",
        security_feedback="sec ok",
        direction_feedback="dir ok",
        test_feedback="test ok",
        file_feedbacks=[],
    )


def _make_score_result(total: int = 80) -> SimpleNamespace:
    return SimpleNamespace(
        total=total,
        grade="B",
        breakdown={"code_quality": 25, "security": 18, "commit_message": 13, "ai_review": 21, "test_coverage": 8},
    )


# ─── 회귀 가드 ──────────────────────────────────────────────────────────────


def test_issues_json_contains_seven_fields() -> None:
    """issues JSON 의 각 항목은 7 필드 (tool/severity/message/line/category/language/file) 모두 포함.

    Phase 11 ~ 그룹 58 사이에는 4 필드 (tool/severity/message/line) 만 직렬화됐었다.
    PR (그룹 58 후속) 에서 category + language 추가. #1488 에서 `file` 추가 —
    그전까지 분석 상세 화면이 이슈의 파일 경로를 **영원히** 보여주지 못했다
    (템플릿 가드 `iss.get('path') or iss.get('file')` 가 항상 False 였다).
    본 가드가 silent 회귀 차단.
    """
    issue = _StubIssue(category="security", language="ruby")
    result = build_analysis_result_dict(
        ai_review=_make_ai_review(),
        score_result=_make_score_result(),
        analysis_results=[_StubAnalysisResult(issues=[issue])],
        source="pr",
    )

    assert "issues" in result, "issues 키 자체 누락"
    assert len(result["issues"]) == 1, f"issues 개수 불일치: {len(result['issues'])}"

    issue_dict: dict[str, Any] = result["issues"][0]
    expected_keys = {"tool", "severity", "message", "line", "category", "language", "file"}
    actual_keys = set(issue_dict.keys())
    missing = expected_keys - actual_keys
    extra = actual_keys - expected_keys
    assert not missing, f"필수 필드 누락 (silent 회귀): {missing}"
    assert not extra, f"예상 외 필드 추가 (스키마 검증 필요): {extra}"

    # 값 보존 검증
    assert issue_dict["tool"] == "pylint"
    assert issue_dict["severity"] == "warning"
    assert issue_dict["message"] == "unused import"
    assert issue_dict["line"] == 12
    assert issue_dict["category"] == "security"
    assert issue_dict["language"] == "ruby"
    assert issue_dict["file"] == "app.py"


def test_issues_json_multi_results_preserves_order() -> None:
    """여러 analysis_result 의 issues 가 모두 순서대로 직렬화."""
    r1 = _StubAnalysisResult(issues=[
        _StubIssue(tool="pylint", message="A", language="python", category="code_quality"),
        _StubIssue(tool="bandit", message="B", language="python", category="security"),
    ])
    r2 = _StubAnalysisResult(issues=[
        _StubIssue(tool="rubocop", message="C", language="ruby", category="code_quality"),
    ])

    result = build_analysis_result_dict(
        ai_review=_make_ai_review(),
        score_result=_make_score_result(),
        analysis_results=[r1, r2],
        source="push",
    )

    assert len(result["issues"]) == 3
    assert [i["message"] for i in result["issues"]] == ["A", "B", "C"]
    assert [i["language"] for i in result["issues"]] == ["python", "python", "ruby"]
    assert [i["category"] for i in result["issues"]] == ["code_quality", "security", "code_quality"]


def test_issues_json_empty_when_no_issues() -> None:
    """이슈 0건일 때 issues 는 빈 리스트 (None 아님)."""
    result = build_analysis_result_dict(
        ai_review=_make_ai_review(),
        score_result=_make_score_result(),
        analysis_results=[_StubAnalysisResult(issues=[])],
        source="cli",
    )
    assert result["issues"] == [], "이슈 0건 시 빈 리스트여야 함 (None 또는 누락 X)"


# ─── C22: ai_review_truncated 마커 전파 ──────────────────────────────────────


def test_result_dict_propagates_ai_review_truncated() -> None:
    """🔴 C22: ai_review.truncated=True → result["ai_review_truncated"]=True (auto-merge 차단 마커)."""
    ai = _make_ai_review()
    ai.truncated = True
    result = build_analysis_result_dict(
        ai_review=ai,
        score_result=_make_score_result(),
        analysis_results=[_StubAnalysisResult(issues=[])],
        source="pr",
    )
    assert result["ai_review_truncated"] is True


def test_result_dict_truncated_defaults_false_when_attr_absent() -> None:
    """🔴 C22: ai_review 에 truncated 속성이 없어도(구 더블/레코드) getattr 기본 False."""
    # _make_ai_review() 더블은 truncated 속성 미보유 → getattr 기본값 검증
    result = build_analysis_result_dict(
        ai_review=_make_ai_review(),
        score_result=_make_score_result(),
        analysis_results=[_StubAnalysisResult(issues=[])],
        source="pr",
    )
    assert result["ai_review_truncated"] is False


# ─── 실패 원인이 result dict 까지 간다 (#1446) ──────────────────────────────
#
# 🔴 `AiReviewResult` 에 필드를 넣는 것만으로는 아무것도 관측되지 않는다.
#    분석 행에 남는 것은 이 dict 뿐이고(`analyses.result`), 여기 실리지 않으면
#    사후 분류는 여전히 불가능하다 — 이슈가 요구한 것이 바로 이 축이다.


class TestErrorCauseReachesTheStoredDict:
    """원인 필드가 저장 dict 에 실리는가."""

    def test_error_fields_are_emitted(self) -> None:
        ai = _make_ai_review()
        ai.status = "api_error"
        ai.error_type = "OverloadedError"
        ai.error_status_code = 529

        result = build_analysis_result_dict(
            ai_review=ai, score_result=_make_score_result(),
            analysis_results=[], source="pr",
        )

        assert result["ai_review_error_type"] == "OverloadedError"
        assert result["ai_review_error_status_code"] == 529

    def test_success_emits_the_keys_as_none_not_absent(self) -> None:
        """🔴 키는 **항상** 나온다 — 성공 시에도 `None` 으로.

        조건부로 넣으면 「키 없음」이 두 가지를 뜻하게 된다: 실패가 아니었거나,
        이 필드가 생기기 전의 낡은 행이거나. 운영 DB 에 이미 그 모호함이 있다
        (2026-04-12 이전 129행은 `ai_review_status` 키 자체가 없다). 같은 모호함을
        새로 만들지 않는다.
        """
        result = build_analysis_result_dict(
            ai_review=_make_ai_review(), score_result=_make_score_result(),
            analysis_results=[], source="pr",
        )

        assert "ai_review_error_type" in result
        assert "ai_review_error_status_code" in result
        assert result["ai_review_error_type"] is None
        assert result["ai_review_error_status_code"] is None

    def test_the_dict_fields_exist_on_the_real_dataclass(self) -> None:
        """🔴 더블 표류 차단 — 위 두 테스트는 `SimpleNamespace` 더블을 쓴다.

        더블에만 필드를 붙이고 실제 `AiReviewResult` 에는 안 붙여도 통과한다.
        진짜 dataclass 를 직접 확인해 그 구멍을 막는다.
        """
        from dataclasses import fields  # pylint: disable=import-outside-toplevel

        from src.analyzer.io.ai_review import AiReviewResult  # pylint: disable=import-outside-toplevel

        names = {f.name for f in fields(AiReviewResult)}
        assert {"error_type", "error_status_code"} <= names, (
            f"AiReviewResult 에 원인 필드가 없다 — 더블만 앞서 있다: {sorted(names)}"
        )


def test_issues_from_different_files_are_distinguishable() -> None:
    """🔴 파일이 다른 동일 메시지 이슈가 **구별돼야** 한다.

    `file` 이 없던 동안, 서로 다른 파일의 같은 메시지 이슈는 직렬화 결과가 **바이트 동일**했다.
    화면에서도 구별 불가였고, 이슈 등록 dedup 키도 같은 이유로 붕괴한다(#1488 본문 참조).

    Without `file`, two findings from different files serialized byte-identically.
    """
    same = dict(tool="pylint", severity="warning", message="unused import", line=12)
    result = build_analysis_result_dict(
        ai_review=_make_ai_review(),
        score_result=_make_score_result(),
        analysis_results=[
            _StubAnalysisResult(issues=[_StubIssue(**same)], filename="src/auth/login.py"),
            _StubAnalysisResult(issues=[_StubIssue(**same)], filename="src/api/hook.py"),
        ],
        source="pr",
    )

    issues = result["issues"]
    assert len(issues) == 2
    assert issues[0] != issues[1], "서로 다른 파일의 이슈가 바이트 동일하다 — 구별 불가"
    assert {i["file"] for i in issues} == {"src/auth/login.py", "src/api/hook.py"}
