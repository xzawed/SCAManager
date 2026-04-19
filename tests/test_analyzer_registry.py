"""TDD Red 상태 테스트 — Phase A: Static Analyzer Registry 인프라.

신설 대상:
  src/analyzer/registry.py          — AnalyzeContext, Analyzer Protocol, REGISTRY, register()
  src/analyzer/tools/__init__.py    — 빈 패키지
  src/analyzer/tools/python.py      — _PylintAnalyzer, _Flake8Analyzer, _BanditAnalyzer

수정 대상:
  src/analyzer/static.py            — AnalysisIssue에 category/language 필드 추가
  src/scorer/calculator.py          — category+severity 기반 집계
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:test")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123456")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

import pytest
from src.analyzer.static import AnalysisIssue, StaticAnalysisResult


# ──────────────────────────────────────────────────────────────────────────────
# REGISTRY 격리 픽스처 — 각 테스트 실행 전후 REGISTRY를 빈 상태로 초기화한다.
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clear_registry():
    """테스트 간 REGISTRY 오염 방지 — 테스트 전후 REGISTRY를 비운다."""
    try:
        # 실제 analyzers를 먼저 등록한 뒤 snapshot — 복원 후 다른 파일 테스트도 정상 동작
        import src.analyzer.tools.python  # noqa: F401 — 실제 등록 트리거
        from src.analyzer.registry import REGISTRY
        original = list(REGISTRY)
        REGISTRY.clear()
        yield
        REGISTRY.clear()
        REGISTRY.extend(original)
    except ImportError:
        # registry.py 미생성 상태(Red) 에서도 다른 테스트가 실행되도록 허용
        yield


# ──────────────────────────────────────────────────────────────────────────────
# TestAnalyzeContext — AnalyzeContext 데이터클래스 구조 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestAnalyzeContext:
    def test_analyzecontext_creates_with_required_fields(self):
        # AnalyzeContext가 필수 필드(filename, content, language, is_test, tmp_path)로 생성된다
        from src.analyzer.registry import AnalyzeContext
        ctx = AnalyzeContext(
            filename="foo.py",
            content="print('hello')",
            language="python",
            is_test=False,
            tmp_path="/tmp/foo.py",
        )
        assert ctx.filename == "foo.py"
        assert ctx.content == "print('hello')"
        assert ctx.language == "python"
        assert ctx.is_test is False
        assert ctx.tmp_path == "/tmp/foo.py"

    def test_analyzecontext_repo_config_defaults_to_none(self):
        # repo_config 필드는 기본값 None으로 생성된다
        from src.analyzer.registry import AnalyzeContext
        ctx = AnalyzeContext(
            filename="bar.py",
            content="x = 1",
            language="python",
            is_test=False,
            tmp_path="/tmp/bar.py",
        )
        assert ctx.repo_config is None

    def test_analyzecontext_repo_config_can_be_set(self):
        # repo_config에 임의 객체를 전달할 수 있다
        from src.analyzer.registry import AnalyzeContext
        sentinel = object()
        ctx = AnalyzeContext(
            filename="baz.py",
            content="",
            language="python",
            is_test=True,
            tmp_path="/tmp/baz.py",
            repo_config=sentinel,
        )
        assert ctx.repo_config is sentinel


# ──────────────────────────────────────────────────────────────────────────────
# TestAnalyzerProtocol — Analyzer Protocol isinstance 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestAnalyzerProtocol:
    def test_class_with_protocol_methods_is_instance_of_analyzer(self):
        # supports/is_enabled/run/name을 모두 구현한 클래스는 isinstance(obj, Analyzer) True
        from src.analyzer.registry import Analyzer, AnalyzeContext

        class MockAnalyzer:
            name = "mock"
            category = "code_quality"

            def supports(self, ctx: AnalyzeContext) -> bool:
                return True

            def is_enabled(self, ctx: AnalyzeContext) -> bool:
                return True

            def run(self, ctx: AnalyzeContext) -> list:
                return []

        obj = MockAnalyzer()
        assert isinstance(obj, Analyzer)

    def test_class_missing_run_method_is_not_instance_of_analyzer(self):
        # run() 없는 클래스는 Analyzer Protocol을 충족하지 못한다
        from src.analyzer.registry import Analyzer, AnalyzeContext

        class IncompleteAnalyzer:
            name = "incomplete"
            category = "code_quality"

            def supports(self, ctx: AnalyzeContext) -> bool:
                return True

            def is_enabled(self, ctx: AnalyzeContext) -> bool:
                return True
            # run() 없음

        obj = IncompleteAnalyzer()
        assert not isinstance(obj, Analyzer)

    def test_class_missing_supports_method_is_not_instance_of_analyzer(self):
        # supports() 없는 클래스는 Analyzer Protocol을 충족하지 못한다
        from src.analyzer.registry import Analyzer, AnalyzeContext

        class NoSupports:
            name = "no_supports"
            category = "code_quality"

            def is_enabled(self, ctx: AnalyzeContext) -> bool:
                return True

            def run(self, ctx: AnalyzeContext) -> list:
                return []

        obj = NoSupports()
        assert not isinstance(obj, Analyzer)


# ──────────────────────────────────────────────────────────────────────────────
# TestRegistry — REGISTRY list와 register() 함수 동작 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestRegistry:
    def test_registry_is_list(self):
        # REGISTRY는 list 타입이어야 한다
        from src.analyzer.registry import REGISTRY
        assert isinstance(REGISTRY, list)

    def test_registry_starts_empty_after_fixture_clear(self):
        # autouse fixture가 REGISTRY를 비운 상태로 각 테스트를 시작한다
        from src.analyzer.registry import REGISTRY
        assert len(REGISTRY) == 0

    def test_register_adds_analyzer_to_registry(self):
        # register() 호출 후 REGISTRY 길이가 1 증가한다
        from src.analyzer.registry import REGISTRY, register, AnalyzeContext

        class MockAnalyzer:
            name = "mock"
            category = "code_quality"

            def supports(self, ctx: AnalyzeContext) -> bool:
                return True

            def is_enabled(self, ctx: AnalyzeContext) -> bool:
                return True

            def run(self, ctx: AnalyzeContext) -> list:
                return []

        analyzer = MockAnalyzer()
        register(analyzer)
        assert len(REGISTRY) == 1
        assert REGISTRY[0] is analyzer

    def test_register_same_name_twice_deduplicates(self):
        # 동일 name의 Analyzer를 두 번 등록하면 첫 번째만 유지된다 (중복 방지)
        from src.analyzer.registry import REGISTRY, register, AnalyzeContext

        class MockAnalyzer:
            name = "dup"
            category = "code_quality"

            def supports(self, ctx: AnalyzeContext) -> bool:
                return True

            def is_enabled(self, ctx: AnalyzeContext) -> bool:
                return True

            def run(self, ctx: AnalyzeContext) -> list:
                return []

        analyzer = MockAnalyzer()
        register(analyzer)
        register(analyzer)
        assert len(REGISTRY) == 1

    def test_registry_analyzer_run_is_callable(self):
        # REGISTRY에 등록된 Analyzer의 run()을 호출할 수 있다
        from src.analyzer.registry import REGISTRY, register, AnalyzeContext

        class MockAnalyzer:
            name = "callable"
            category = "code_quality"

            def supports(self, ctx: AnalyzeContext) -> bool:
                return True

            def is_enabled(self, ctx: AnalyzeContext) -> bool:
                return True

            def run(self, ctx: AnalyzeContext) -> list:
                return [AnalysisIssue(tool="mock", severity="warning", message="test")]

        register(MockAnalyzer())
        ctx = AnalyzeContext(
            filename="x.py", content="x=1", language="python",
            is_test=False, tmp_path="/tmp/x.py"
        )
        result = REGISTRY[0].run(ctx)
        assert len(result) == 1
        assert result[0].tool == "mock"


# ──────────────────────────────────────────────────────────────────────────────
# TestAnalysisIssueNewFields — AnalysisIssue에 category/language 필드 추가 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestAnalysisIssueNewFields:
    def test_analysis_issue_has_category_field_with_default(self):
        # AnalysisIssue에 category 필드가 있고 기본값은 "code_quality"이다
        issue = AnalysisIssue(tool="pylint", severity="error", message="E001")
        assert hasattr(issue, "category")
        assert issue.category == "code_quality"

    def test_analysis_issue_has_language_field_with_default(self):
        # AnalysisIssue에 language 필드가 있고 기본값은 빈 문자열이다
        issue = AnalysisIssue(tool="pylint", severity="error", message="E001")
        assert hasattr(issue, "language")
        assert issue.language == ""

    def test_analysis_issue_category_can_be_set_to_security(self):
        # category를 "security"로 명시적으로 설정할 수 있다
        issue = AnalysisIssue(
            tool="bandit", severity="error", message="B602",
            category="security"
        )
        assert issue.category == "security"

    def test_analysis_issue_language_can_be_set(self):
        # language 필드를 "python"으로 설정할 수 있다
        issue = AnalysisIssue(
            tool="pylint", severity="warning", message="W0611",
            language="python"
        )
        assert issue.language == "python"

    def test_analysis_issue_existing_fields_unchanged(self):
        # 기존 필드(tool, severity, message, line)는 이전과 동일하게 동작한다
        issue = AnalysisIssue(tool="flake8", severity="warning", message="E501", line=42)
        assert issue.tool == "flake8"
        assert issue.severity == "warning"
        assert issue.message == "E501"
        assert issue.line == 42


# ──────────────────────────────────────────────────────────────────────────────
# TestPythonAnalyzers — tools/python.py 내 각 Analyzer 클래스 동작 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestPythonAnalyzers:
    @pytest.fixture
    def py_ctx(self):
        """일반 Python 파일 컨텍스트."""
        from src.analyzer.registry import AnalyzeContext
        return AnalyzeContext(
            filename="src/main.py",
            content="x = 1\n",
            language="python",
            is_test=False,
            tmp_path="/tmp/main.py",
        )

    @pytest.fixture
    def js_ctx(self):
        """JavaScript 파일 컨텍스트 — Python 도구가 지원하지 않아야 한다."""
        from src.analyzer.registry import AnalyzeContext
        return AnalyzeContext(
            filename="app.js",
            content="const x = 1;",
            language="javascript",
            is_test=False,
            tmp_path="/tmp/app.js",
        )

    @pytest.fixture
    def test_py_ctx(self):
        """테스트 파일 Python 컨텍스트 — bandit은 비활성화되어야 한다."""
        from src.analyzer.registry import AnalyzeContext
        return AnalyzeContext(
            filename="tests/test_foo.py",
            content="def test_x(): pass\n",
            language="python",
            is_test=True,
            tmp_path="/tmp/test_foo.py",
        )

    def test_pylint_analyzer_supports_python_file(self, py_ctx):
        # _PylintAnalyzer.supports()는 language="python" 컨텍스트에서 True를 반환한다
        from src.analyzer.tools.python import _PylintAnalyzer
        assert _PylintAnalyzer().supports(py_ctx) is True

    def test_pylint_analyzer_does_not_support_javascript_file(self, js_ctx):
        # _PylintAnalyzer.supports()는 language="javascript" 컨텍스트에서 False를 반환한다
        from src.analyzer.tools.python import _PylintAnalyzer
        assert _PylintAnalyzer().supports(js_ctx) is False

    def test_flake8_analyzer_supports_python_file(self, py_ctx):
        # _Flake8Analyzer.supports()는 language="python" 컨텍스트에서 True를 반환한다
        from src.analyzer.tools.python import _Flake8Analyzer
        assert _Flake8Analyzer().supports(py_ctx) is True

    def test_flake8_analyzer_does_not_support_javascript_file(self, js_ctx):
        # _Flake8Analyzer.supports()는 language="javascript" 컨텍스트에서 False를 반환한다
        from src.analyzer.tools.python import _Flake8Analyzer
        assert _Flake8Analyzer().supports(js_ctx) is False

    def test_bandit_analyzer_is_enabled_for_normal_python_file(self, py_ctx):
        # _BanditAnalyzer.is_enabled()는 일반(비-테스트) Python 파일에서 True를 반환한다
        from src.analyzer.tools.python import _BanditAnalyzer
        assert _BanditAnalyzer().is_enabled(py_ctx) is True

    def test_bandit_analyzer_is_disabled_for_test_file(self, test_py_ctx):
        # _BanditAnalyzer.is_enabled()는 is_test=True 컨텍스트에서 False를 반환한다
        from src.analyzer.tools.python import _BanditAnalyzer
        assert _BanditAnalyzer().is_enabled(test_py_ctx) is False

    def test_flake8_analyzer_category_is_code_quality(self):
        # _Flake8Analyzer.category는 "code_quality"이다
        from src.analyzer.tools.python import _Flake8Analyzer
        assert _Flake8Analyzer().category == "code_quality"

    def test_pylint_analyzer_category_is_code_quality(self):
        # _PylintAnalyzer.category는 "code_quality"이다
        from src.analyzer.tools.python import _PylintAnalyzer
        assert _PylintAnalyzer().category == "code_quality"

    def test_bandit_analyzer_category_is_security(self):
        # _BanditAnalyzer.category는 "security"이다
        from src.analyzer.tools.python import _BanditAnalyzer
        assert _BanditAnalyzer().category == "security"

    def test_pylint_analyzer_name(self):
        # _PylintAnalyzer.name은 "pylint"이다
        from src.analyzer.tools.python import _PylintAnalyzer
        assert _PylintAnalyzer().name == "pylint"

    def test_flake8_analyzer_name(self):
        # _Flake8Analyzer.name은 "flake8"이다
        from src.analyzer.tools.python import _Flake8Analyzer
        assert _Flake8Analyzer().name == "flake8"

    def test_bandit_analyzer_name(self):
        # _BanditAnalyzer.name은 "bandit"이다
        from src.analyzer.tools.python import _BanditAnalyzer
        assert _BanditAnalyzer().name == "bandit"

    def test_pylint_analyzer_is_enabled_always_true_for_python(self, py_ctx):
        # _PylintAnalyzer.is_enabled()는 Python 파일에서 항상 True이다
        from src.analyzer.tools.python import _PylintAnalyzer
        assert _PylintAnalyzer().is_enabled(py_ctx) is True

    def test_bandit_analyzer_supports_python_file(self, py_ctx):
        # _BanditAnalyzer.supports()는 language="python" 컨텍스트에서 True를 반환한다
        from src.analyzer.tools.python import _BanditAnalyzer
        assert _BanditAnalyzer().supports(py_ctx) is True

    def test_bandit_analyzer_does_not_support_javascript_file(self, js_ctx):
        # _BanditAnalyzer.supports()는 language="javascript" 컨텍스트에서 False를 반환한다
        from src.analyzer.tools.python import _BanditAnalyzer
        assert _BanditAnalyzer().supports(js_ctx) is False


# ──────────────────────────────────────────────────────────────────────────────
# TestAnalyzeFileRegistry — analyze_file이 Registry를 통해 실행됨을 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestAnalyzeFileRegistry:
    def test_python_file_returns_static_analysis_result(self):
        # .py 파일 분석 시 StaticAnalysisResult가 반환된다
        from src.analyzer.static import analyze_file
        result = analyze_file("hello.py", "x = 1\n")
        assert isinstance(result, StaticAnalysisResult)
        assert result.filename == "hello.py"

    def test_go_file_returns_empty_issues_when_no_go_analyzer_registered(self):
        # REGISTRY에 Go analyzer가 없으면 .go 파일은 빈 issues를 반환한다
        from src.analyzer.static import analyze_file
        result = analyze_file("main.go", "package main\nfunc main() {}\n")
        assert isinstance(result, StaticAnalysisResult)
        assert result.issues == []

    def test_markdown_file_returns_empty_issues(self):
        # .md 파일은 Python 도구가 지원하지 않으므로 issues가 비어 있다
        from src.analyzer.static import analyze_file
        result = analyze_file("README.md", "# Hello\n")
        assert isinstance(result, StaticAnalysisResult)
        assert result.issues == []

    def test_empty_content_returns_empty_result(self):
        # content가 빈 문자열이면 issues 없이 StaticAnalysisResult를 반환한다
        from src.analyzer.static import analyze_file
        result = analyze_file("empty.py", "")
        assert isinstance(result, StaticAnalysisResult)
        assert result.issues == []

    def test_whitespace_only_content_returns_empty_result(self):
        # 공백만 있는 content도 빈 결과로 처리된다
        from src.analyzer.static import analyze_file
        result = analyze_file("blank.py", "   \n  \n")
        assert isinstance(result, StaticAnalysisResult)
        assert result.issues == []

    def test_issues_have_category_field(self):
        # analyze_file 결과 issues에 category 필드가 있다
        from src.analyzer.static import analyze_file
        # 실제 pylint/flake8 가 이슈를 찾을 수 있는 코드
        result = analyze_file("sample.py", "import os\nimport sys\nx=1\n")
        for issue in result.issues:
            assert hasattr(issue, "category")

    def test_issues_have_language_field(self):
        # analyze_file 결과 issues에 language 필드가 있다
        from src.analyzer.static import analyze_file
        result = analyze_file("sample.py", "import os\nx=1\n")
        for issue in result.issues:
            assert hasattr(issue, "language")


# ──────────────────────────────────────────────────────────────────────────────
# TestCalculatorCategoryBased — category+severity 기반 집계 동작 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestCalculatorCategoryBased:
    def test_code_quality_errors_reduce_score_by_three_each(self):
        # code_quality + error 이슈 2개 → 25 - 2*3 = 19
        from src.scorer.calculator import calculate_score
        issues = [
            AnalysisIssue(
                tool="pylint", severity="error", message="E001",
                category="code_quality"
            ),
            AnalysisIssue(
                tool="pylint", severity="error", message="E002",
                category="code_quality"
            ),
        ]
        result = calculate_score([StaticAnalysisResult("f.py", issues)])
        assert result.code_quality_score == 19

    def test_security_error_reduces_score_by_seven(self):
        # category="security" + severity="error" 이슈 1개 → 20 - 7 = 13
        from src.scorer.calculator import calculate_score
        issues = [
            AnalysisIssue(
                tool="bandit", severity="error", message="B602",
                category="security"
            ),
        ]
        result = calculate_score([StaticAnalysisResult("f.py", issues)])
        assert result.security_score == 13

    def test_security_warning_reduces_score_by_two(self):
        # category="security" + severity="warning" 이슈 1개 → 20 - 2 = 18
        from src.scorer.calculator import calculate_score
        issues = [
            AnalysisIssue(
                tool="bandit", severity="warning", message="B101",
                category="security"
            ),
        ]
        result = calculate_score([StaticAnalysisResult("f.py", issues)])
        assert result.security_score == 18

    def test_empty_issues_returns_full_static_scores(self):
        # 이슈가 없으면 code_quality=25, security=20 만점이다
        from src.scorer.calculator import calculate_score
        result = calculate_score([StaticAnalysisResult("f.py", [])])
        assert result.code_quality_score == 25
        assert result.security_score == 20

    def test_multiple_code_quality_warnings_capped(self):
        # code_quality warning이 25개 이상이어도 감점 상한이 적용된다
        from src.scorer.calculator import calculate_score
        issues = [
            AnalysisIssue(
                tool="flake8", severity="warning", message=f"W{i:03d}",
                category="code_quality"
            )
            for i in range(30)  # 30개 → cap 적용
        ]
        result = calculate_score([StaticAnalysisResult("f.py", issues)])
        # 상한 25개 × 1점 = 25 → code_quality = max(0, 25-25) = 0
        assert result.code_quality_score >= 0

    def test_mixed_category_issues_calculated_independently(self):
        # code_quality와 security 이슈가 섞여도 각각 독립적으로 계산된다
        from src.scorer.calculator import calculate_score
        issues = [
            AnalysisIssue(
                tool="pylint", severity="error", message="E001",
                category="code_quality"
            ),
            AnalysisIssue(
                tool="bandit", severity="error", message="B602",
                category="security"
            ),
        ]
        result = calculate_score([StaticAnalysisResult("f.py", issues)])
        assert result.code_quality_score == 22  # 25 - 1*3
        assert result.security_score == 13      # 20 - 1*7

    def test_old_tool_name_based_issues_still_work_via_category(self):
        # tool 이름이 "pylint"이더라도 category 필드로 집계가 결정된다
        # category="code_quality"인 경우 code_quality 점수에 반영된다
        from src.scorer.calculator import calculate_score
        issue = AnalysisIssue(
            tool="pylint", severity="warning", message="W0611",
            category="code_quality"
        )
        result = calculate_score([StaticAnalysisResult("f.py", [issue])])
        # warning 1개 → 25 - 1 = 24
        assert result.code_quality_score == 24
        # security는 영향 없음
        assert result.security_score == 20

    def test_empty_analysis_results_list_returns_full_scores(self):
        # analysis_results 자체가 빈 목록이면 만점이다
        from src.scorer.calculator import calculate_score
        result = calculate_score([])
        assert result.code_quality_score == 25
        assert result.security_score == 20

    def test_score_result_total_sums_all_components(self):
        # 빈 issues + AI 없음(기본값) → total은 각 컴포넌트 합산과 같다
        from src.scorer.calculator import calculate_score
        from src.constants import AI_DEFAULT_COMMIT, AI_DEFAULT_DIRECTION, AI_DEFAULT_TEST
        result = calculate_score([])
        expected_total = 25 + 20 + AI_DEFAULT_COMMIT + AI_DEFAULT_DIRECTION + AI_DEFAULT_TEST
        assert result.total == min(expected_total, 100)
