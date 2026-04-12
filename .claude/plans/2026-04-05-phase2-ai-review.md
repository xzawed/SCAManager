# Phase 2 — AI Review + Commit Score + GitHub PR Comment

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude AI로 코드 diff + 커밋 메시지를 리뷰하여 점수를 실제 계산하고, PR에 마크다운 코멘트로 결과를 게시한다.

**Architecture:** `review_code()` (AI 리뷰)와 `_run_static_analysis()` (정적 분석)을 `asyncio.gather`로 병렬 실행한다. Scorer는 AI 리뷰 결과를 받아 커밋 메시지(20점)·구현 방향성(20점)·테스트(10점) 점수를 실제 계산한다. PR 이벤트 시 GitHub REST API로 분석 결과 마크다운 코멘트를 게시한다.

**Tech Stack:** `anthropic` SDK (Claude Haiku), `httpx` (GitHub API), `asyncio.gather` + `asyncio.to_thread`

---

## 파일 구조

| 파일 | 작업 |
|------|------|
| `requirements.txt` | `anthropic>=0.25.0` 추가 |
| `src/config.py` | `anthropic_api_key: str = ""` 필드 추가 |
| `tests/conftest.py` | `ANTHROPIC_API_KEY` 환경변수 추가 |
| `src/analyzer/ai_review.py` | **신규** — `AiReviewResult`, `review_code()` |
| `src/scorer/calculator.py` | `calculate_score(ai_review=)` 파라미터 추가, 점수 실제 계산 |
| `src/notifier/github_comment.py` | **신규** — `post_pr_comment()`, `_build_comment_body()` |
| `src/worker/pipeline.py` | 병렬 실행, commit_message 추출, PR Comment 발송 |
| `tests/test_ai_review.py` | **신규** |
| `tests/test_github_comment.py` | **신규** |
| `tests/test_scorer.py` | ai_review 파라미터 테스트 추가 |
| `tests/test_pipeline.py` | 새 의존성 mock 추가 |
| `CLAUDE.md` | 환경변수 표에 `ANTHROPIC_API_KEY` 추가 |

---

### Task 1: anthropic 패키지 + ANTHROPIC_API_KEY 설정

**Files:**
- Modify: `requirements.txt`
- Modify: `src/config.py`
- Modify: `tests/conftest.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: requirements.txt에 anthropic 추가**

```text
fastapi==0.115.0
uvicorn[standard]==0.30.6
pydantic-settings==2.3.4
sqlalchemy==2.0.35
alembic==1.13.3
psycopg2-binary==2.9.11
PyGithub==2.3.0
httpx==0.27.2
python-telegram-bot==21.6
anthropic>=0.25.0
pylint==3.3.1
flake8==7.1.1
bandit==1.8.0
pytest==8.3.3
pytest-asyncio==0.24.0
```

- [ ] **Step 2: src/config.py에 anthropic_api_key 필드 추가**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    github_webhook_secret: str
    github_token: str
    telegram_bot_token: str
    telegram_chat_id: str
    anthropic_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

- [ ] **Step 3: tests/conftest.py에 ANTHROPIC_API_KEY 추가**

```python
import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")

from src.main import app


@pytest.fixture
def client():
    return TestClient(app)
```

- [ ] **Step 4: CLAUDE.md 환경변수 표 업데이트**

기존 환경변수 표에 다음 행 추가:

```
| `ANTHROPIC_API_KEY` | Claude AI 리뷰 API 키 (없으면 AI 리뷰 건너뜀) | `sk-ant-xxxx` |
```

- [ ] **Step 5: anthropic 패키지 설치**

```bash
cd D:/Source/SCAManager
pip install anthropic>=0.25.0
```

- [ ] **Step 6: 기존 테스트 통과 확인**

```bash
cd D:/Source/SCAManager && pytest -x -q
```

Expected: 35 passed

- [ ] **Step 7: Commit**

```bash
git add requirements.txt src/config.py tests/conftest.py CLAUDE.md
git commit -m "feat: add ANTHROPIC_API_KEY config for Phase 2"
```

---

### Task 2: AI Review 모듈 구현

**Files:**
- Create: `src/analyzer/ai_review.py`
- Create: `tests/test_ai_review.py`

- [ ] **Step 1: tests/test_ai_review.py 작성 (테스트 먼저)**

```python
# tests/test_ai_review.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.analyzer.ai_review import (
    AiReviewResult, review_code, _parse_response, _default_result
)


async def test_empty_api_key_returns_default():
    result = await review_code("", "feat: test", ["+ x = 1"])
    assert isinstance(result, AiReviewResult)
    assert result.commit_score == 15
    assert result.ai_score == 15


async def test_empty_patches_returns_default():
    result = await review_code("sk-key", "feat: test", [])
    assert result.commit_score == 15
    assert result.ai_score == 15


def test_parse_response_valid_json():
    text = '{"commit_message_score": 18, "direction_score": 16, "has_tests": true, "summary": "Good refactoring", "suggestions": ["Add type hints"]}'
    result = _parse_response(text)
    assert result.commit_score == 18
    assert result.ai_score == 16
    assert result.has_tests is True
    assert result.summary == "Good refactoring"
    assert "Add type hints" in result.suggestions


def test_parse_response_clamps_above_max():
    text = '{"commit_message_score": 99, "direction_score": 99, "has_tests": false, "summary": "", "suggestions": []}'
    result = _parse_response(text)
    assert result.commit_score == 20
    assert result.ai_score == 20


def test_parse_response_clamps_below_min():
    text = '{"commit_message_score": -5, "direction_score": -3, "has_tests": false, "summary": "", "suggestions": []}'
    result = _parse_response(text)
    assert result.commit_score == 0
    assert result.ai_score == 0


def test_parse_response_invalid_json_returns_default():
    result = _parse_response("not valid json at all")
    assert result.commit_score == 15
    assert result.ai_score == 15


def test_parse_response_json_in_markdown_code_block():
    text = '```json\n{"commit_message_score": 17, "direction_score": 19, "has_tests": true, "summary": "ok", "suggestions": []}\n```'
    result = _parse_response(text)
    assert result.commit_score == 17
    assert result.ai_score == 19


def test_default_result_values():
    result = _default_result()
    assert result.commit_score == 15
    assert result.ai_score == 15
    assert result.has_tests is False
    assert isinstance(result.suggestions, list)


async def test_review_code_calls_anthropic_and_parses():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"commit_message_score": 18, "direction_score": 17, "has_tests": true, "summary": "ok", "suggestions": []}')]

    with patch("src.analyzer.ai_review.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        result = await review_code("sk-test", "feat: add feature", ["+ x = 1"])

    assert result.commit_score == 18
    assert result.ai_score == 17
    assert result.has_tests is True


async def test_review_code_returns_default_on_api_exception():
    with patch("src.analyzer.ai_review.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API error"))
        mock_cls.return_value = mock_client

        result = await review_code("sk-test", "feat: add", ["+ x = 1"])

    assert result.commit_score == 15
    assert result.ai_score == 15
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd D:/Source/SCAManager && pytest tests/test_ai_review.py -v
```

Expected: ERROR — `ModuleNotFoundError: No module named 'src.analyzer.ai_review'`

- [ ] **Step 3: src/analyzer/ai_review.py 구현**

```python
# src/analyzer/ai_review.py
import json
import logging
from dataclasses import dataclass, field

import anthropic

logger = logging.getLogger(__name__)

MAX_DIFF_CHARS = 8000  # Claude API 토큰 비용 제어


@dataclass
class AiReviewResult:
    commit_score: int        # 0-20: 커밋 메시지 품질
    ai_score: int            # 0-20: 구현 방향성
    has_tests: bool
    summary: str
    suggestions: list[str] = field(default_factory=list)


_PROMPT_TEMPLATE = """\
다음 코드 diff와 커밋 메시지를 분석하고 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요.

커밋 메시지:
{commit_message}

코드 변경사항:
{diff_text}

다음 JSON만 응답 (추가 텍스트 없이):
{{
  "commit_message_score": <0~20 정수, 컨벤션 준수/명확성/변경범위 일치성>,
  "direction_score": <0~20 정수, 구현 방향성/패턴/설계 적합성>,
  "has_tests": <true/false, 테스트 코드 변경 포함 여부>,
  "summary": "<변경사항 한 줄 요약>",
  "suggestions": ["<개선 제안1>", "<개선 제안2>"]
}}"""


async def review_code(
    api_key: str,
    commit_message: str,
    patches: list[str],
) -> AiReviewResult:
    """Claude API로 코드를 리뷰하고 점수를 반환한다. API key가 없으면 기본값 반환."""
    if not api_key:
        return _default_result()

    diff_text = "\n".join(patches)[:MAX_DIFF_CHARS]
    if not diff_text.strip():
        return _default_result()

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": _PROMPT_TEMPLATE.format(
                    commit_message=commit_message or "(없음)",
                    diff_text=diff_text,
                ),
            }],
        )
        return _parse_response(response.content[0].text)
    except Exception:
        logger.exception("AI review failed, using default scores")
        return _default_result()


def _parse_response(text: str) -> AiReviewResult:
    try:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            parts = cleaned.split("```")
            cleaned = parts[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        data = json.loads(cleaned)
        return AiReviewResult(
            commit_score=max(0, min(20, int(data.get("commit_message_score", 15)))),
            ai_score=max(0, min(20, int(data.get("direction_score", 15)))),
            has_tests=bool(data.get("has_tests", False)),
            summary=str(data.get("summary", "")),
            suggestions=[str(s) for s in data.get("suggestions", [])],
        )
    except (json.JSONDecodeError, ValueError, KeyError):
        logger.warning("Failed to parse AI review response: %s", text[:200])
        return _default_result()


def _default_result() -> AiReviewResult:
    """API key 없음, 빈 diff, 또는 오류 시 반환하는 기본값."""
    return AiReviewResult(
        commit_score=15,
        ai_score=15,
        has_tests=False,
        summary="AI 리뷰 불가 (기본값 적용)",
        suggestions=[],
    )
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd D:/Source/SCAManager && pytest tests/test_ai_review.py -v
```

Expected: 11 passed

- [ ] **Step 5: 전체 테스트 통과 확인**

```bash
cd D:/Source/SCAManager && pytest -x -q
```

Expected: 46 passed (기존 35 + 신규 11)

- [ ] **Step 6: Commit**

```bash
git add src/analyzer/ai_review.py tests/test_ai_review.py
git commit -m "feat: implement AI review module with Claude API"
```

---

### Task 3: Scorer 업데이트 — AI 리뷰 결과 반영

**Files:**
- Modify: `src/scorer/calculator.py`
- Modify: `tests/test_scorer.py`

- [ ] **Step 1: tests/test_scorer.py에 새 테스트 추가**

기존 파일 끝에 다음을 추가한다:

```python
# 기존 테스트 아래에 추가
from src.analyzer.ai_review import AiReviewResult


def _make_ai_review(commit_score=18, ai_score=17, has_tests=True):
    return AiReviewResult(
        commit_score=commit_score,
        ai_score=ai_score,
        has_tests=has_tests,
        summary="ok",
        suggestions=[],
    )


def test_calculate_score_uses_ai_review_scores():
    result = calculate_score([_make_result([])], ai_review=_make_ai_review(commit_score=18, ai_score=17))
    assert result.breakdown["commit_message"] == 18
    assert result.breakdown["ai_review"] == 17


def test_calculate_score_test_coverage_10_when_has_tests():
    result = calculate_score([_make_result([])], ai_review=_make_ai_review(has_tests=True))
    assert result.breakdown["test_coverage"] == 10


def test_calculate_score_test_coverage_0_when_no_tests():
    result = calculate_score([_make_result([])], ai_review=_make_ai_review(has_tests=False))
    assert result.breakdown["test_coverage"] == 0


def test_calculate_score_fallback_when_no_ai_review():
    result = calculate_score([_make_result([])], ai_review=None)
    assert result.breakdown["commit_message"] == 15
    assert result.breakdown["ai_review"] == 15
    assert result.breakdown["test_coverage"] == 5


def test_calculate_score_total_with_ai_review():
    result = calculate_score(
        [_make_result([])],
        ai_review=_make_ai_review(commit_score=20, ai_score=20, has_tests=True),
    )
    # code_quality=30, security=20, commit=20, ai=20, test=10 = 100
    assert result.total == 100
    assert result.grade == "A"
```

- [ ] **Step 2: 새 테스트 실패 확인**

```bash
cd D:/Source/SCAManager && pytest tests/test_scorer.py -v
```

Expected: 5개 새 테스트 FAIL — `calculate_score() got unexpected keyword argument 'ai_review'`

- [ ] **Step 3: src/scorer/calculator.py 업데이트**

```python
# src/scorer/calculator.py
from __future__ import annotations
from dataclasses import dataclass
from src.analyzer.static import StaticAnalysisResult
from src.analyzer.ai_review import AiReviewResult


@dataclass
class ScoreResult:
    total: int
    grade: str
    code_quality_score: int
    security_score: int
    breakdown: dict


def calculate_score(
    analysis_results: list[StaticAnalysisResult],
    ai_review: AiReviewResult | None = None,
) -> ScoreResult:
    all_issues = [issue for r in analysis_results for issue in r.issues]

    pylint_errors = sum(1 for i in all_issues if i.tool == "pylint" and i.severity == "error")
    pylint_warnings = sum(1 for i in all_issues if i.tool == "pylint" and i.severity == "warning")
    flake8_warnings = sum(1 for i in all_issues if i.tool == "flake8")
    bandit_errors = sum(1 for i in all_issues if i.tool == "bandit" and i.severity == "error")
    bandit_warnings = sum(1 for i in all_issues if i.tool == "bandit" and i.severity == "warning")

    code_quality_score = max(0, 30 - pylint_errors * 5 - pylint_warnings * 1 - flake8_warnings * 1)
    security_score = max(0, 20 - bandit_errors * 10 - bandit_warnings * 3)

    if ai_review is not None:
        commit_score = ai_review.commit_score
        ai_score = ai_review.ai_score
        test_score = 10 if ai_review.has_tests else 0
    else:
        # AI 리뷰 없을 때 Phase 1 호환 기본값
        commit_score = 15
        ai_score = 15
        test_score = 5

    total = code_quality_score + security_score + commit_score + ai_score + test_score

    return ScoreResult(
        total=total,
        grade=_grade(total),
        code_quality_score=code_quality_score,
        security_score=security_score,
        breakdown={
            "code_quality": code_quality_score,
            "security": security_score,
            "commit_message": commit_score,
            "ai_review": ai_score,
            "test_coverage": test_score,
        },
    )


def _grade(score: int) -> str:
    if score >= 90: return "A"
    if score >= 75: return "B"
    if score >= 60: return "C"
    if score >= 45: return "D"
    return "F"
```

- [ ] **Step 4: 전체 scorer 테스트 통과 확인**

```bash
cd D:/Source/SCAManager && pytest tests/test_scorer.py -v
```

Expected: 전부 passed (기존 5 + 신규 5 = 10)

- [ ] **Step 5: 전체 테스트 통과 확인**

```bash
cd D:/Source/SCAManager && pytest -x -q
```

Expected: 51 passed

- [ ] **Step 6: Commit**

```bash
git add src/scorer/calculator.py tests/test_scorer.py
git commit -m "feat: update scorer to use AI review scores for commit/direction/test"
```

---

### Task 4: GitHub PR Comment 구현

**Files:**
- Create: `src/notifier/github_comment.py`
- Create: `tests/test_github_comment.py`

- [ ] **Step 1: tests/test_github_comment.py 작성**

```python
# tests/test_github_comment.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.notifier.github_comment import _build_comment_body, post_pr_comment
from src.scorer.calculator import ScoreResult
from src.analyzer.static import StaticAnalysisResult, AnalysisIssue
from src.analyzer.ai_review import AiReviewResult


def _make_score(total=82, grade="B"):
    return ScoreResult(
        total=total, grade=grade,
        code_quality_score=28, security_score=20,
        breakdown={
            "code_quality": 28, "security": 20,
            "commit_message": 17, "ai_review": 15, "test_coverage": 2,
        },
    )


def _make_ai_review():
    return AiReviewResult(
        commit_score=17, ai_score=15, has_tests=True,
        summary="좋은 리팩토링입니다.",
        suggestions=["타입 힌트 추가 권장", "메서드 분리 고려"],
    )


def test_comment_body_contains_total_score():
    body = _build_comment_body(_make_score(), [], None)
    assert "82/100" in body
    assert "등급 B" in body


def test_comment_body_contains_grade_emoji():
    body = _build_comment_body(_make_score(total=82, grade="B"), [], None)
    assert "🔵" in body


def test_comment_body_contains_breakdown_table():
    body = _build_comment_body(_make_score(), [], None)
    assert "커밋 메시지" in body
    assert "코드 품질" in body
    assert "보안" in body
    assert "구현 방향성" in body
    assert "테스트" in body


def test_comment_body_includes_ai_summary_and_suggestions():
    body = _build_comment_body(_make_score(), [], _make_ai_review())
    assert "좋은 리팩토링입니다." in body
    assert "타입 힌트 추가 권장" in body
    assert "메서드 분리 고려" in body


def test_comment_body_includes_static_issues():
    issues = [AnalysisIssue(tool="pylint", severity="error", message="undefined-variable", line=5)]
    r = StaticAnalysisResult(filename="app.py", issues=issues)
    body = _build_comment_body(_make_score(), [r], None)
    assert "undefined-variable" in body
    assert "pylint" in body
    assert "line 5" in body


def test_comment_body_no_issues_section_when_empty():
    body = _build_comment_body(_make_score(), [], None)
    assert "주요 이슈" not in body


def test_comment_body_limits_issues_to_10():
    issues = [
        AnalysisIssue(tool="flake8", severity="warning", message=f"issue-{i}", line=i)
        for i in range(20)
    ]
    r = StaticAnalysisResult(filename="app.py", issues=issues)
    body = _build_comment_body(_make_score(), [r], None)
    assert body.count("flake8") <= 10


async def test_post_pr_comment_calls_github_api():
    with patch("src.notifier.github_comment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await post_pr_comment(
            github_token="ghp_test",
            repo_name="owner/repo",
            pr_number=42,
            score_result=_make_score(),
            analysis_results=[],
            ai_review=None,
        )

    mock_client.post.assert_called_once()
    url = mock_client.post.call_args[0][0]
    assert "owner/repo" in url
    assert "42" in url


async def test_post_pr_comment_sets_auth_header():
    with patch("src.notifier.github_comment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await post_pr_comment(
            github_token="ghp_test",
            repo_name="owner/repo",
            pr_number=1,
            score_result=_make_score(),
            analysis_results=[],
            ai_review=None,
        )

    headers = mock_client.post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer ghp_test"
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd D:/Source/SCAManager && pytest tests/test_github_comment.py -v
```

Expected: ERROR — `ModuleNotFoundError: No module named 'src.notifier.github_comment'`

- [ ] **Step 3: src/notifier/github_comment.py 구현**

```python
# src/notifier/github_comment.py
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
        f"| 커밋 메시지 | {bd['commit_message']} | 20 |",
        f"| 코드 품질 | {bd['code_quality']} | 30 |",
        f"| 보안 | {bd['security']} | 20 |",
        f"| 구현 방향성 (AI) | {bd['ai_review']} | 20 |",
        f"| 테스트 | {bd['test_coverage']} | 10 |",
    ]

    if ai_review and ai_review.summary:
        lines += ["", "### AI 요약", ai_review.summary]

    if ai_review and ai_review.suggestions:
        lines += ["", "### 개선 제안"]
        for s in ai_review.suggestions:
            lines.append(f"- {s}")

    all_issues = [i for r in analysis_results for i in r.issues]
    if all_issues:
        lines += ["", "### 주요 이슈 (상위 10건)"]
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
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd D:/Source/SCAManager && pytest tests/test_github_comment.py -v
```

Expected: 10 passed

- [ ] **Step 5: 전체 테스트 통과 확인**

```bash
cd D:/Source/SCAManager && pytest -x -q
```

Expected: 61 passed

- [ ] **Step 6: Commit**

```bash
git add src/notifier/github_comment.py tests/test_github_comment.py
git commit -m "feat: add GitHub PR comment notifier with markdown score report"
```

---

### Task 5: Pipeline 통합 — 병렬 실행 + commit message + PR Comment

**Files:**
- Modify: `src/worker/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: tests/test_pipeline.py 업데이트**

기존 파일을 아래 내용으로 완전히 교체한다:

```python
# tests/test_pipeline.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


PUSH_DATA = {
    "repository": {"full_name": "owner/repo"},
    "after": "abc123def456",
    "commits": [{"id": "abc123def456", "message": "feat: add awesome feature"}],
}

PR_DATA = {
    "repository": {"full_name": "owner/repo"},
    "number": 7,
    "pull_request": {"head": {"sha": "def456abc123"}, "title": "feat: new PR title"},
}


@pytest.fixture
def mock_deps():
    with (
        patch("src.worker.pipeline.get_push_files") as mock_push,
        patch("src.worker.pipeline.get_pr_files") as mock_pr,
        patch("src.worker.pipeline.review_code", new_callable=AsyncMock) as mock_ai,
        patch("src.worker.pipeline.calculate_score") as mock_score,
        patch("src.worker.pipeline.send_analysis_result", new_callable=AsyncMock) as mock_telegram,
        patch("src.worker.pipeline.post_pr_comment", new_callable=AsyncMock) as mock_comment,
        patch("src.worker.pipeline.SessionLocal") as mock_session_cls,
        patch("src.worker.pipeline.settings") as mock_settings,
    ):
        from src.analyzer.static import StaticAnalysisResult
        from src.scorer.calculator import ScoreResult
        from src.github_client.diff import ChangedFile
        from src.analyzer.ai_review import AiReviewResult

        mock_settings.github_token = "ghp_test"
        mock_settings.telegram_bot_token = "123:ABC"
        mock_settings.telegram_chat_id = "-100123"
        mock_settings.anthropic_api_key = "sk-test"

        mock_push.return_value = [ChangedFile("app.py", "x = 1\n", "@@ +1 @@")]
        mock_pr.return_value = [ChangedFile("app.py", "x = 1\n", "@@ +1 @@")]
        mock_ai.return_value = AiReviewResult(
            commit_score=17, ai_score=16, has_tests=True,
            summary="Good change", suggestions=[]
        )
        mock_score.return_value = ScoreResult(
            total=85, grade="B",
            code_quality_score=28, security_score=20,
            breakdown={
                "code_quality": 28, "security": 20,
                "commit_message": 17, "ai_review": 16, "test_coverage": 4,
            },
        )

        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = None
        mock_db.flush = MagicMock()
        mock_db.commit = MagicMock()
        mock_session_cls.return_value = mock_db

        yield {
            "push": mock_push, "pr": mock_pr,
            "ai": mock_ai, "score": mock_score,
            "telegram": mock_telegram, "comment": mock_comment,
            "db": mock_db,
        }


async def test_push_event_calls_full_pipeline(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    mock_deps["push"].assert_called_once()
    mock_deps["ai"].assert_called_once()
    mock_deps["score"].assert_called_once()
    mock_deps["telegram"].assert_called_once()
    mock_deps["db"].commit.assert_called_once()


async def test_pr_event_calls_full_pipeline(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("pull_request", PR_DATA)

    mock_deps["pr"].assert_called_once()
    mock_deps["ai"].assert_called_once()
    mock_deps["telegram"].assert_called_once()


async def test_pr_event_posts_github_comment(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("pull_request", PR_DATA)

    mock_deps["comment"].assert_called_once()
    call_kwargs = mock_deps["comment"].call_args[1]
    assert call_kwargs["pr_number"] == 7
    assert call_kwargs["repo_name"] == "owner/repo"


async def test_push_event_does_not_post_github_comment(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    mock_deps["comment"].assert_not_called()


async def test_no_python_files_skips_pipeline(mock_deps):
    mock_deps["push"].return_value = []
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    mock_deps["ai"].assert_not_called()
    mock_deps["telegram"].assert_not_called()


async def test_duplicate_commit_is_skipped(mock_deps):
    existing = MagicMock()
    mock_deps["db"].query.return_value.filter_by.return_value.first.side_effect = [
        None,
        existing,
    ]
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    mock_deps["telegram"].assert_not_called()


async def test_push_commit_message_extracted(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    call_args = mock_deps["ai"].call_args
    assert call_args[0][1] == "feat: add awesome feature"


async def test_pr_title_used_as_commit_message(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("pull_request", PR_DATA)

    call_args = mock_deps["ai"].call_args
    assert call_args[0][1] == "feat: new PR title"


async def test_ai_review_result_passed_to_scorer(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    from src.analyzer.ai_review import AiReviewResult
    await run_analysis_pipeline("push", PUSH_DATA)

    score_call = mock_deps["score"].call_args
    ai_review_arg = score_call[1].get("ai_review") or score_call[0][1]
    assert isinstance(ai_review_arg, AiReviewResult)


async def test_db_result_stores_ai_summary(mock_deps):
    from src.worker.pipeline import run_analysis_pipeline
    await run_analysis_pipeline("push", PUSH_DATA)

    analysis_added = mock_deps["db"].add.call_args_list[-1][0][0]
    assert "ai_summary" in analysis_added.result
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd D:/Source/SCAManager && pytest tests/test_pipeline.py -v
```

Expected: 여러 테스트 FAIL — 새 기능이 pipeline.py에 없기 때문

- [ ] **Step 3: src/worker/pipeline.py 업데이트**

```python
# src/worker/pipeline.py
import asyncio
import logging
from sqlalchemy.orm import Session
from src.database import SessionLocal
from src.config import settings
from src.github_client.diff import get_pr_files, get_push_files, ChangedFile
from src.analyzer.static import analyze_file, StaticAnalysisResult
from src.analyzer.ai_review import review_code, AiReviewResult
from src.scorer.calculator import calculate_score
from src.notifier.telegram import send_analysis_result
from src.notifier.github_comment import post_pr_comment
from src.models.repository import Repository
from src.models.analysis import Analysis

logger = logging.getLogger(__name__)


def _extract_commit_message(event: str, data: dict) -> str:
    if event == "pull_request":
        return data.get("pull_request", {}).get("title", "")
    commits = data.get("commits", [])
    return commits[0]["message"] if commits else ""


async def _run_static_analysis(files: list[ChangedFile]) -> list[StaticAnalysisResult]:
    return await asyncio.to_thread(
        lambda: [analyze_file(f.filename, f.content) for f in files]
    )


async def run_analysis_pipeline(event: str, data: dict) -> None:
    try:
        repo_name: str = data["repository"]["full_name"]
        commit_message = _extract_commit_message(event, data)

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

        patches = [f.patch for f in files if f.patch]
        analysis_results, ai_review = await asyncio.gather(
            _run_static_analysis(files),
            review_code(settings.anthropic_api_key, commit_message, patches),
        )

        score_result = calculate_score(analysis_results, ai_review=ai_review)

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
                    "ai_summary": ai_review.summary,
                    "ai_suggestions": ai_review.suggestions,
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

        notify_tasks = [
            send_analysis_result(
                bot_token=settings.telegram_bot_token,
                chat_id=settings.telegram_chat_id,
                repo_name=repo_name,
                commit_sha=commit_sha,
                score_result=score_result,
                analysis_results=analysis_results,
                pr_number=pr_number,
            )
        ]
        if pr_number is not None:
            notify_tasks.append(
                post_pr_comment(
                    github_token=settings.github_token,
                    repo_name=repo_name,
                    pr_number=pr_number,
                    score_result=score_result,
                    analysis_results=analysis_results,
                    ai_review=ai_review,
                )
            )
        await asyncio.gather(*notify_tasks)

    except Exception:
        logger.exception("Analysis pipeline failed for event=%s", event)
```

- [ ] **Step 4: 전체 pipeline 테스트 통과 확인**

```bash
cd D:/Source/SCAManager && pytest tests/test_pipeline.py -v
```

Expected: 11 passed

- [ ] **Step 5: 전체 테스트 통과 확인**

```bash
cd D:/Source/SCAManager && pytest -x -q
```

Expected: 72+ passed (기존 35 + AI 11 + scorer 5 + comment 10 + pipeline 11 추가)

- [ ] **Step 6: lint 확인**

```bash
cd D:/Source/SCAManager && pylint src/ && flake8 src/ && bandit -r src/ -ll
```

Expected: 이슈 없음 또는 경미한 경고만

- [ ] **Step 7: Commit**

```bash
git add src/worker/pipeline.py tests/test_pipeline.py
git commit -m "feat: integrate AI review and GitHub PR comment into pipeline"
```

---

## 검증 방법

### 1. 전체 테스트 + 커버리지

```bash
cd D:/Source/SCAManager && pytest --cov=src --cov-report=term-missing
```

### 2. 로컬 서버 엔드-투-엔드 테스트

```bash
# 터미널 1: 서버 실행
cd D:/Source/SCAManager && uvicorn src.main:app --reload --port 8000

# 터미널 2: Push 이벤트 시뮬레이션
PAYLOAD='{"ref":"refs/heads/main","after":"abc123","commits":[{"id":"abc123","message":"feat: test phase2"}],"repository":{"full_name":"owner/repo"}}'
SECRET="test_secret"
SIG=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* /sha256=/')
curl -s -X POST http://localhost:8000/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -H "X-Hub-Signature-256: $SIG" \
  -d "$PAYLOAD"
```

Expected: `{"status":"accepted"}`

### 3. Railway 환경변수 추가

Railway 대시보드에서 `ANTHROPIC_API_KEY` 추가 후 재배포.
