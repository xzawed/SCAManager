"""TDD Red 상태 테스트 — Phase C: ESLint Analyzer.

신설 대상:
  src/analyzer/tools/eslint.py  — _ESLintAnalyzer (Analyzer Protocol 구현)

ESLint는 JavaScript/TypeScript 파일의 코드 품질 분석을 담당한다.
subprocess.run mock으로 실제 eslint 바이너리 호출 없이 모든 경로를 검증한다.
"""
import json
import os
import subprocess

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
from unittest.mock import patch, MagicMock


# ──────────────────────────────────────────────────────────────────────────────
# REGISTRY 격리 픽스처 — 각 테스트 실행 전후 REGISTRY를 원래 상태로 복원한다.
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolate_registry():
    """테스트 간 REGISTRY 오염 방지 — 테스트 전후 REGISTRY를 격리한다."""
    try:
        import src.analyzer.tools.python  # noqa: F401 — Python 도구 먼저 등록
        from src.analyzer.registry import REGISTRY
        original = list(REGISTRY)
        REGISTRY.clear()
        yield
        REGISTRY.clear()
        REGISTRY.extend(original)
    except ImportError:
        # registry.py 미생성 상태(Red)에서도 다른 테스트가 실행되도록 허용
        yield


# ──────────────────────────────────────────────────────────────────────────────
# 공용 헬퍼 — eslint subprocess mock 생성
# ──────────────────────────────────────────────────────────────────────────────

def _mock_eslint_proc(stdout: str, returncode: int = 0) -> MagicMock:
    """subprocess.run 반환값을 모방하는 MagicMock을 생성한다."""
    mock = MagicMock()
    mock.stdout = stdout
    mock.returncode = returncode
    return mock


# ESLint JSON 출력 샘플 — severity 2(error) + severity 1(warning) 혼합
SAMPLE_OUTPUT_MIXED = json.dumps([
    {
        "filePath": "/tmp/test.js",
        "messages": [
            {
                "ruleId": "no-unused-vars",
                "severity": 1,
                "message": "'x' is defined but never used.",
                "line": 5,
                "column": 3,
            },
            {
                "ruleId": "no-eval",
                "severity": 2,
                "message": "eval() can be harmful.",
                "line": 10,
                "column": 1,
            },
        ],
    }
])

# ESLint JSON 출력 샘플 — severity 2(error)만 포함
SAMPLE_OUTPUT_ERROR_ONLY = json.dumps([
    {
        "filePath": "/tmp/app.js",
        "messages": [
            {
                "ruleId": "no-eval",
                "severity": 2,
                "message": "eval() can be harmful.",
                "line": 10,
                "column": 1,
            },
        ],
    }
])

# ESLint JSON 출력 샘플 — severity 1(warning)만 포함
SAMPLE_OUTPUT_WARNING_ONLY = json.dumps([
    {
        "filePath": "/tmp/app.ts",
        "messages": [
            {
                "ruleId": "no-unused-vars",
                "severity": 1,
                "message": "'y' is defined but never used.",
                "line": 5,
                "column": 3,
            },
        ],
    }
])

# ESLint JSON 출력 샘플 — messages 비어 있음
SAMPLE_OUTPUT_NO_MESSAGES = json.dumps([
    {
        "filePath": "/tmp/clean.js",
        "messages": [],
    }
])


# ──────────────────────────────────────────────────────────────────────────────
# 픽스처 — AnalyzeContext 생성 헬퍼
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def make_ctx():
    """언어와 파일명을 받아 AnalyzeContext를 생성하는 팩토리 픽스처."""
    from src.analyzer.registry import AnalyzeContext

    def _factory(language: str, filename: str = "test_file.js",
                 is_test: bool = False, tmp_path: str = "/tmp/test_file.js"):
        return AnalyzeContext(
            filename=filename,
            content="some content",
            language=language,
            is_test=is_test,
            tmp_path=tmp_path,
        )
    return _factory


# ──────────────────────────────────────────────────────────────────────────────
# TestESLintAnalyzerAttributes — 클래스 속성 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestESLintAnalyzerAttributes:
    def test_name_is_eslint(self):
        # _ESLintAnalyzer.name은 "eslint"이어야 한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        assert _ESLintAnalyzer().name == "eslint"

    def test_category_is_code_quality(self):
        # _ESLintAnalyzer.category는 "code_quality"이어야 한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        assert _ESLintAnalyzer().category == "code_quality"

    def test_supported_languages_is_frozenset(self):
        # SUPPORTED_LANGUAGES는 frozenset 타입이어야 한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        assert isinstance(_ESLintAnalyzer.SUPPORTED_LANGUAGES, frozenset)

    def test_supported_languages_contains_javascript_and_typescript(self):
        # SUPPORTED_LANGUAGES에 "javascript"와 "typescript" 양쪽이 포함되어야 한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        assert "javascript" in _ESLintAnalyzer.SUPPORTED_LANGUAGES
        assert "typescript" in _ESLintAnalyzer.SUPPORTED_LANGUAGES

    def test_supported_languages_contains_exactly_two_entries(self):
        # SUPPORTED_LANGUAGES는 정확히 javascript와 typescript 두 언어만 포함해야 한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        assert _ESLintAnalyzer.SUPPORTED_LANGUAGES == frozenset({"javascript", "typescript"})


# ──────────────────────────────────────────────────────────────────────────────
# TestESLintSupports — supports() 언어별 반환값 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestESLintSupports:
    def test_supports_returns_true_for_javascript(self, make_ctx):
        # javascript 파일에서 supports()는 True를 반환해야 한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript")
        assert _ESLintAnalyzer().supports(ctx) is True

    def test_supports_returns_true_for_typescript(self, make_ctx):
        # typescript 파일에서 supports()는 True를 반환해야 한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="typescript", filename="app.ts", tmp_path="/tmp/app.ts")
        assert _ESLintAnalyzer().supports(ctx) is True

    @pytest.mark.parametrize("language", [
        "python", "go", "shell", "unknown", "java", "rust",
    ])
    def test_supports_returns_false_for_non_js_languages(self, language, make_ctx):
        # javascript/typescript 외 언어에서 supports()는 False를 반환해야 한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language=language)
        assert _ESLintAnalyzer().supports(ctx) is False


# ──────────────────────────────────────────────────────────────────────────────
# TestESLintIsEnabled — is_enabled() eslint 바이너리 존재 여부 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestESLintIsEnabled:
    def test_is_enabled_returns_true_when_eslint_binary_exists(self, make_ctx):
        # shutil.which("eslint")이 경로를 반환하면 is_enabled()는 True를 반환한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript")
        with patch("shutil.which", return_value="/usr/local/bin/eslint"):
            assert _ESLintAnalyzer().is_enabled(ctx) is True

    def test_is_enabled_returns_false_when_eslint_binary_missing(self, make_ctx):
        # shutil.which("eslint")이 None을 반환하면 is_enabled()는 False를 반환한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript")
        with patch("shutil.which", return_value=None):
            assert _ESLintAnalyzer().is_enabled(ctx) is False

    def test_is_enabled_checks_eslint_binary_specifically(self, make_ctx):
        # is_enabled()가 shutil.which를 "eslint" 인자로 호출하는지 검증한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript")
        with patch("shutil.which", return_value="/usr/local/bin/eslint") as mock_which:
            _ESLintAnalyzer().is_enabled(ctx)
        mock_which.assert_called_once_with("eslint")


# ──────────────────────────────────────────────────────────────────────────────
# TestESLintRunSubprocessCall — subprocess 호출 인자 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestESLintRunSubprocessCall:
    def test_run_includes_format_json_flag(self, make_ctx):
        # eslint 실행 시 --format=json 플래그가 포함되어야 한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_NO_MESSAGES)) as mock_run:
            _ESLintAnalyzer().run(ctx)
        call_args = mock_run.call_args[0][0]
        assert any("--format=json" in arg or arg == "--format=json" for arg in call_args)

    def test_run_passes_tmp_path_to_eslint(self, make_ctx):
        # eslint 실행 시 ctx.tmp_path가 인자에 포함되어야 한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/specific_app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_NO_MESSAGES)) as mock_run:
            _ESLintAnalyzer().run(ctx)
        call_args = mock_run.call_args[0][0]
        assert "/tmp/specific_app.js" in call_args

    def test_run_includes_no_eslintrc_flag(self, make_ctx):
        # eslint 실행 시 --no-eslintrc 플래그가 포함되어야 한다 (임베디드 config만 사용)
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_NO_MESSAGES)) as mock_run:
            _ESLintAnalyzer().run(ctx)
        call_args = mock_run.call_args[0][0]
        assert "--no-eslintrc" in call_args


# ──────────────────────────────────────────────────────────────────────────────
# TestESLintRunOutputParsing — run() JSON 출력 파싱 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestESLintRunOutputParsing:
    def test_run_maps_severity_2_to_error(self, make_ctx):
        # ESLint severity 2는 AnalysisIssue.severity="error"로 매핑되어야 한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_ERROR_ONLY)):
            issues = _ESLintAnalyzer().run(ctx)
        assert len(issues) == 1
        assert issues[0].severity == "error"

    def test_run_maps_severity_1_to_warning(self, make_ctx):
        # ESLint severity 1은 AnalysisIssue.severity="warning"으로 매핑되어야 한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_WARNING_ONLY)):
            issues = _ESLintAnalyzer().run(ctx)
        assert len(issues) == 1
        assert issues[0].severity == "warning"

    def test_run_parses_multiple_messages_correctly(self, make_ctx):
        # 복수 messages가 있는 출력에서 모든 이슈를 반환해야 한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/test.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_MIXED)):
            issues = _ESLintAnalyzer().run(ctx)
        assert len(issues) == 2
        severities = {i.severity for i in issues}
        assert "error" in severities
        assert "warning" in severities

    def test_run_returns_empty_list_for_empty_messages(self, make_ctx):
        # messages 배열이 비어 있으면 빈 이슈 목록을 반환해야 한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/clean.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_NO_MESSAGES)):
            issues = _ESLintAnalyzer().run(ctx)
        assert issues == []

    def test_run_returns_empty_list_for_empty_stdout(self, make_ctx):
        # stdout이 빈 문자열이면 빈 이슈 목록을 반환해야 한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc("")):
            issues = _ESLintAnalyzer().run(ctx)
        assert issues == []

    def test_run_returns_empty_list_when_stdout_not_starts_with_bracket(self, make_ctx):
        # stdout이 "[" 로 시작하지 않으면 빈 이슈 목록을 반환해야 한다 (ESLint가 에러 텍스트 출력 시)
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc("Error: cannot find eslint config")):
            issues = _ESLintAnalyzer().run(ctx)
        assert issues == []

    def test_run_sets_category_to_code_quality(self, make_ctx):
        # 모든 ESLint 이슈의 category는 "code_quality"이어야 한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_MIXED)):
            issues = _ESLintAnalyzer().run(ctx)
        for issue in issues:
            assert issue.category == "code_quality"

    def test_run_sets_language_from_ctx(self, make_ctx):
        # AnalysisIssue.language는 ctx.language 값으로 설정되어야 한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="typescript", filename="app.ts", tmp_path="/tmp/app.ts")
        output = json.dumps([
            {
                "filePath": "/tmp/app.ts",
                "messages": [
                    {"ruleId": "no-unused-vars", "severity": 1, "message": "unused", "line": 3, "column": 1},
                ],
            }
        ])
        with patch("subprocess.run", return_value=_mock_eslint_proc(output)):
            issues = _ESLintAnalyzer().run(ctx)
        assert len(issues) == 1
        assert issues[0].language == "typescript"

    def test_run_sets_tool_name_to_eslint(self, make_ctx):
        # 모든 AnalysisIssue.tool 값은 "eslint"이어야 한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_ERROR_ONLY)):
            issues = _ESLintAnalyzer().run(ctx)
        assert issues[0].tool == "eslint"

    def test_run_sets_line_number_from_message(self, make_ctx):
        # AnalysisIssue.line은 ESLint message의 line 필드에서 가져와야 한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_ERROR_ONLY)):
            issues = _ESLintAnalyzer().run(ctx)
        assert issues[0].line == 10

    def test_run_sets_message_text_from_eslint_message(self, make_ctx):
        # AnalysisIssue.message는 ESLint message 객체의 message 필드에서 가져와야 한다
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_ERROR_ONLY)):
            issues = _ESLintAnalyzer().run(ctx)
        assert "eval" in issues[0].message


# ──────────────────────────────────────────────────────────────────────────────
# TestESLintRunGracefulDegradation — 예외 상황에서 graceful 반환 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestESLintRunGracefulDegradation:
    def test_run_returns_empty_on_file_not_found_error(self, make_ctx):
        # eslint 바이너리가 없어서 FileNotFoundError 발생 → 빈 이슈 목록 반환 (파이프라인 미중단)
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", side_effect=FileNotFoundError("eslint not found")):
            issues = _ESLintAnalyzer().run(ctx)
        assert issues == []

    def test_run_returns_empty_on_timeout_expired(self, make_ctx):
        # eslint subprocess가 TimeoutExpired → 빈 이슈 목록 반환 (파이프라인 미중단)
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="eslint", timeout=30)):
            issues = _ESLintAnalyzer().run(ctx)
        assert issues == []

    def test_run_returns_empty_on_json_decode_error(self, make_ctx):
        # stdout이 유효하지 않은 JSON → JSONDecodeError → 빈 이슈 목록 반환
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc("[{broken")):
            issues = _ESLintAnalyzer().run(ctx)
        assert issues == []

    def test_run_returns_empty_on_non_json_output(self, make_ctx):
        # stdout이 JSON이 아닌 일반 텍스트로 시작하는 경우 빈 이슈 목록 반환
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc("Oops, something went wrong")):
            issues = _ESLintAnalyzer().run(ctx)
        assert issues == []


# ──────────────────────────────────────────────────────────────────────────────
# TestESLintRegistration — 모듈 로드 시 REGISTRY 자동 등록 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestESLintRegistration:
    def test_module_import_registers_eslint_in_registry(self):
        # src.analyzer.tools.eslint 임포트 시 REGISTRY에 _ESLintAnalyzer가 자동 등록된다
        import importlib
        from src.analyzer.registry import REGISTRY
        import src.analyzer.tools.eslint  # noqa: F401
        importlib.reload(src.analyzer.tools.eslint)
        names = [a.name for a in REGISTRY]
        assert "eslint" in names

    def test_double_import_does_not_duplicate_registry_entry(self):
        # 동일 모듈을 두 번 로드해도 REGISTRY에 "eslint"가 중복 등록되지 않아야 한다
        import importlib
        from src.analyzer.registry import REGISTRY
        import src.analyzer.tools.eslint  # noqa: F401
        importlib.reload(src.analyzer.tools.eslint)
        importlib.reload(src.analyzer.tools.eslint)
        eslint_entries = [a for a in REGISTRY if a.name == "eslint"]
        assert len(eslint_entries) == 1

    def test_eslint_analyzer_satisfies_analyzer_protocol(self):
        # _ESLintAnalyzer 인스턴스가 Analyzer Protocol을 충족하는지 검증한다
        from src.analyzer.registry import Analyzer
        from src.analyzer.tools.eslint import _ESLintAnalyzer
        assert isinstance(_ESLintAnalyzer(), Analyzer)
