"""TDD Red 상태 테스트 — Phase B: Semgrep Analyzer.

신설 대상:
  src/analyzer/tools/semgrep.py  — _SemgrepAnalyzer (Analyzer Protocol 구현)

semgrep은 30+ 언어 baseline 정적분석을 담당한다.
subprocess.run mock으로 실제 semgrep 바이너리 호출 없이 모든 경로를 검증한다.
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
        import src.analyzer.io.tools.python  # noqa: F401 — Python 도구 먼저 등록
        from src.analyzer.pure.registry import REGISTRY
        original = list(REGISTRY)
        REGISTRY.clear()
        yield
        REGISTRY.clear()
        REGISTRY.extend(original)
    except ImportError:
        # registry.py 미생성 상태(Red)에서도 다른 테스트가 실행되도록 허용
        yield


# ──────────────────────────────────────────────────────────────────────────────
# 공용 헬퍼 — semgrep subprocess mock 생성
# ──────────────────────────────────────────────────────────────────────────────

def _mock_semgrep_proc(stdout: str, returncode: int = 0) -> MagicMock:
    """subprocess.run 반환값을 모방하는 MagicMock을 생성한다."""
    mock = MagicMock()
    mock.stdout = stdout
    mock.returncode = returncode
    return mock


# 정상 출력 샘플 — security 태그가 metadata에 포함된 ERROR 이슈
SAMPLE_OUTPUT_SECURITY_ERROR = json.dumps({
    "results": [
        {
            "check_id": "python.lang.security.audit.eval-detected",
            "extra": {
                "severity": "ERROR",
                "message": "eval() detected — arbitrary code execution risk",
                "metadata": {"category": "security"},
            },
            "path": "/tmp/test.py",
            "start": {"line": 5},
        }
    ]
})

# 정상 출력 샘플 — code_quality 태그가 없는 WARNING 이슈 (metadata 비어 있음)
SAMPLE_OUTPUT_CODE_QUALITY_WARNING = json.dumps({
    "results": [
        {
            "check_id": "python.lang.best-practice.use-isinstance",
            "extra": {
                "severity": "WARNING",
                "message": "use isinstance() instead of type()",
                "metadata": {},
            },
            "path": "/tmp/test.py",
            "start": {"line": 12},
        }
    ]
})

# 정상 출력 샘플 — results 비어 있음
SAMPLE_OUTPUT_EMPTY = json.dumps({"results": []})

# 정상 출력 샘플 — 복수 이슈 혼합 (security + code_quality)
SAMPLE_OUTPUT_MIXED = json.dumps({
    "results": [
        {
            "check_id": "java.lang.security.audit.sql-injection",
            "extra": {
                "severity": "ERROR",
                "message": "SQL injection vulnerability",
                "metadata": {"category": "security"},
            },
            "path": "/tmp/App.java",
            "start": {"line": 30},
        },
        {
            "check_id": "java.lang.best-practice.null-check",
            "extra": {
                "severity": "WARNING",
                "message": "Missing null check",
                "metadata": {},
            },
            "path": "/tmp/App.java",
            "start": {"line": 45},
        },
    ]
})


# ──────────────────────────────────────────────────────────────────────────────
# 픽스처 — AnalyzeContext 생성 헬퍼
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def make_ctx():
    """언어와 파일명을 받아 AnalyzeContext를 생성하는 팩토리 픽스처."""
    from src.analyzer.pure.registry import AnalyzeContext

    def _factory(language: str, filename: str = "test_file.py",
                 is_test: bool = False, tmp_path: str = "/tmp/test_file.py"):
        return AnalyzeContext(
            filename=filename,
            content="some content",
            language=language,
            is_test=is_test,
            tmp_path=tmp_path,
        )
    return _factory


# ──────────────────────────────────────────────────────────────────────────────
# TestSemgrepAnalyzerAttributes — 클래스 속성 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestSemgrepAnalyzerAttributes:
    def test_name_is_semgrep(self):
        # _SemgrepAnalyzer.name은 "semgrep"이어야 한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        assert _SemgrepAnalyzer().name == "semgrep"

    def test_category_is_code_quality(self):
        # _SemgrepAnalyzer.category의 기본값은 "code_quality"이어야 한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        assert _SemgrepAnalyzer().category == "code_quality"

    def test_supported_languages_is_frozenset(self):
        # SUPPORTED_LANGUAGES는 frozenset 타입이어야 한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        assert isinstance(_SemgrepAnalyzer.SUPPORTED_LANGUAGES, frozenset)

    def test_supported_languages_contains_core_languages(self):
        # SUPPORTED_LANGUAGES에 핵심 언어들이 포함되어 있어야 한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        required = {"python", "javascript", "typescript", "java", "go", "rust"}
        assert required.issubset(_SemgrepAnalyzer.SUPPORTED_LANGUAGES)


# ──────────────────────────────────────────────────────────────────────────────
# TestSemgrepSupports — supports() 언어별 반환값 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestSemgrepSupports:
    @pytest.mark.parametrize("language", [
        "python", "javascript", "typescript", "java", "go", "rust",
        "c", "cpp", "csharp", "ruby",
    ])
    def test_supports_returns_true_for_tier1_languages(self, language, make_ctx):
        # Tier1 언어(python/js/ts/java/go/rust/c/cpp/csharp/ruby)에서 supports()는 True를 반환한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language=language)
        assert _SemgrepAnalyzer().supports(ctx) is True

    @pytest.mark.parametrize("language", [
        "php", "scala", "kotlin", "swift", "elixir",
        "clojure", "solidity", "shell", "dockerfile",
    ])
    def test_supports_returns_true_for_tier2_languages(self, language, make_ctx):
        # Tier2 언어(php/scala/kotlin/swift/elixir/clojure/solidity/shell/dockerfile)에서 supports()는 True를 반환한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language=language)
        assert _SemgrepAnalyzer().supports(ctx) is True

    @pytest.mark.parametrize("language", [
        "yaml", "html", "terraform",
    ])
    def test_supports_returns_true_for_config_and_markup_languages(self, language, make_ctx):
        # YAML/HTML/Terraform 파일에서도 supports()는 True를 반환한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language=language)
        assert _SemgrepAnalyzer().supports(ctx) is True

    @pytest.mark.parametrize("language", [
        "unknown", "markdown", "binary", "text",
    ])
    def test_supports_returns_false_for_unsupported_languages(self, language, make_ctx):
        # 지원하지 않는 언어(unknown/markdown/binary 등)에서 supports()는 False를 반환한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language=language)
        assert _SemgrepAnalyzer().supports(ctx) is False


# ──────────────────────────────────────────────────────────────────────────────
# TestSemgrepIsEnabled — is_enabled() semgrep 바이너리 존재 여부 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestSemgrepIsEnabled:
    def test_is_enabled_returns_true_when_semgrep_binary_exists(self, make_ctx):
        # shutil.which("semgrep")이 경로를 반환하면 is_enabled()는 True를 반환한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python")
        with patch("shutil.which", return_value="/usr/bin/semgrep"):
            assert _SemgrepAnalyzer().is_enabled(ctx) is True

    def test_is_enabled_returns_false_when_semgrep_binary_missing(self, make_ctx):
        # shutil.which("semgrep")이 None을 반환하면 is_enabled()는 False를 반환한다 (graceful degradation)
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python")
        with patch("shutil.which", return_value=None):
            assert _SemgrepAnalyzer().is_enabled(ctx) is False

    def test_is_enabled_checks_semgrep_specifically(self, make_ctx):
        # is_enabled()가 shutil.which를 "semgrep" 인자로 호출하는지 검증한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python")
        with patch("shutil.which", return_value="/usr/local/bin/semgrep") as mock_which:
            _SemgrepAnalyzer().is_enabled(ctx)
        mock_which.assert_called_once_with("semgrep")


# ──────────────────────────────────────────────────────────────────────────────
# TestSemgrepRunSubprocessCall — subprocess 호출 인자 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestSemgrepRunSubprocessCall:
    def test_run_includes_config_auto_flag(self, make_ctx):
        # semgrep 실행 시 --config=auto 플래그가 포함되어야 한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python", tmp_path="/tmp/sample.py")
        with patch("subprocess.run", return_value=_mock_semgrep_proc(SAMPLE_OUTPUT_EMPTY)) as mock_run:
            _SemgrepAnalyzer().run(ctx)
        call_args = mock_run.call_args[0][0]
        assert any("--config=auto" in arg or arg == "--config=auto" for arg in call_args)

    def test_run_includes_json_flag(self, make_ctx):
        # semgrep 실행 시 --json 플래그가 포함되어야 한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python", tmp_path="/tmp/sample.py")
        with patch("subprocess.run", return_value=_mock_semgrep_proc(SAMPLE_OUTPUT_EMPTY)) as mock_run:
            _SemgrepAnalyzer().run(ctx)
        call_args = mock_run.call_args[0][0]
        assert "--json" in call_args

    def test_run_passes_tmp_path_to_semgrep(self, make_ctx):
        # semgrep 실행 시 ctx.tmp_path가 인자에 포함되어야 한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python", tmp_path="/tmp/specific_file.py")
        with patch("subprocess.run", return_value=_mock_semgrep_proc(SAMPLE_OUTPUT_EMPTY)) as mock_run:
            _SemgrepAnalyzer().run(ctx)
        call_args = mock_run.call_args[0][0]
        assert "/tmp/specific_file.py" in call_args

    def test_run_passes_timeout_30(self, make_ctx):
        # semgrep subprocess 호출 시 timeout=30이 전달되어야 한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python", tmp_path="/tmp/sample.py")
        with patch("subprocess.run", return_value=_mock_semgrep_proc(SAMPLE_OUTPUT_EMPTY)) as mock_run:
            _SemgrepAnalyzer().run(ctx)
        kwargs = mock_run.call_args[1]
        assert kwargs.get("timeout") == 30


# ──────────────────────────────────────────────────────────────────────────────
# TestSemgrepRunOutputParsing — run() JSON 출력 파싱 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestSemgrepRunOutputParsing:
    def test_run_parses_security_error_correctly(self, make_ctx):
        # security 태그 + ERROR severity → category="security", severity="error" AnalysisIssue 반환
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python", tmp_path="/tmp/test.py")
        with patch("subprocess.run", return_value=_mock_semgrep_proc(SAMPLE_OUTPUT_SECURITY_ERROR)):
            issues = _SemgrepAnalyzer().run(ctx)
        assert len(issues) == 1
        assert issues[0].category == "security"
        assert issues[0].severity == "error"
        assert issues[0].tool == "semgrep"
        assert issues[0].line == 5

    def test_run_parses_code_quality_warning_correctly(self, make_ctx):
        # metadata 비어 있음 + WARNING severity → category="code_quality", severity="warning" 반환
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python", tmp_path="/tmp/test.py")
        with patch("subprocess.run", return_value=_mock_semgrep_proc(SAMPLE_OUTPUT_CODE_QUALITY_WARNING)):
            issues = _SemgrepAnalyzer().run(ctx)
        assert len(issues) == 1
        assert issues[0].category == "code_quality"
        assert issues[0].severity == "warning"
        assert issues[0].line == 12

    def test_run_maps_error_severity_correctly(self, make_ctx):
        # semgrep "ERROR" severity는 AnalysisIssue.severity="error"로 매핑되어야 한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python", tmp_path="/tmp/test.py")
        with patch("subprocess.run", return_value=_mock_semgrep_proc(SAMPLE_OUTPUT_SECURITY_ERROR)):
            issues = _SemgrepAnalyzer().run(ctx)
        assert issues[0].severity == "error"

    def test_run_maps_warning_severity_correctly(self, make_ctx):
        # semgrep "WARNING" severity는 AnalysisIssue.severity="warning"으로 매핑되어야 한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python", tmp_path="/tmp/test.py")
        with patch("subprocess.run", return_value=_mock_semgrep_proc(SAMPLE_OUTPUT_CODE_QUALITY_WARNING)):
            issues = _SemgrepAnalyzer().run(ctx)
        assert issues[0].severity == "warning"

    def test_run_sets_message_from_extra_message(self, make_ctx):
        # AnalysisIssue.message는 extra.message 필드에서 가져와야 한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python", tmp_path="/tmp/test.py")
        with patch("subprocess.run", return_value=_mock_semgrep_proc(SAMPLE_OUTPUT_SECURITY_ERROR)):
            issues = _SemgrepAnalyzer().run(ctx)
        assert "eval()" in issues[0].message

    def test_run_sets_language_from_ctx(self, make_ctx):
        # AnalysisIssue.language는 ctx.language 값으로 설정되어야 한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="java", filename="App.java", tmp_path="/tmp/App.java")
        with patch("subprocess.run", return_value=_mock_semgrep_proc(SAMPLE_OUTPUT_MIXED)):
            issues = _SemgrepAnalyzer().run(ctx)
        for issue in issues:
            assert issue.language == "java"

    def test_run_returns_empty_list_for_empty_results(self, make_ctx):
        # results=[]인 정상 JSON 출력 → 빈 이슈 목록 반환
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python", tmp_path="/tmp/test.py")
        with patch("subprocess.run", return_value=_mock_semgrep_proc(SAMPLE_OUTPUT_EMPTY)):
            issues = _SemgrepAnalyzer().run(ctx)
        assert issues == []

    def test_run_returns_empty_list_for_empty_stdout(self, make_ctx):
        # stdout이 빈 문자열이면 빈 이슈 목록을 반환해야 한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python", tmp_path="/tmp/test.py")
        with patch("subprocess.run", return_value=_mock_semgrep_proc("")):
            issues = _SemgrepAnalyzer().run(ctx)
        assert issues == []

    def test_run_returns_multiple_issues_from_mixed_output(self, make_ctx):
        # 복수 이슈가 포함된 출력에서 모든 이슈를 반환해야 한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="java", filename="App.java", tmp_path="/tmp/App.java")
        with patch("subprocess.run", return_value=_mock_semgrep_proc(SAMPLE_OUTPUT_MIXED)):
            issues = _SemgrepAnalyzer().run(ctx)
        assert len(issues) == 2
        categories = {i.category for i in issues}
        assert "security" in categories
        assert "code_quality" in categories

    def test_run_returns_empty_list_when_results_key_missing(self, make_ctx):
        # JSON에 "results" 키가 없는 비정상 구조 → 빈 이슈 목록 반환
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python", tmp_path="/tmp/test.py")
        malformed = json.dumps({"errors": [], "version": "1.0"})
        with patch("subprocess.run", return_value=_mock_semgrep_proc(malformed)):
            issues = _SemgrepAnalyzer().run(ctx)
        assert issues == []


# ──────────────────────────────────────────────────────────────────────────────
# TestSemgrepRunGracefulDegradation — 예외 상황에서 graceful 반환 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestSemgrepRunGracefulDegradation:
    def test_run_returns_empty_on_file_not_found_error(self, make_ctx):
        # semgrep 바이너리가 없어서 FileNotFoundError 발생 → 빈 이슈 목록 반환 (파이프라인 미중단)
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python", tmp_path="/tmp/test.py")
        with patch("subprocess.run", side_effect=FileNotFoundError("semgrep not found")):
            issues = _SemgrepAnalyzer().run(ctx)
        assert issues == []

    def test_run_returns_empty_on_timeout_expired(self, make_ctx):
        # semgrep subprocess가 TimeoutExpired → 빈 이슈 목록 반환 (파이프라인 미중단)
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python", tmp_path="/tmp/test.py")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="semgrep", timeout=30)):
            issues = _SemgrepAnalyzer().run(ctx)
        assert issues == []

    def test_run_returns_empty_on_json_decode_error(self, make_ctx):
        # stdout이 유효하지 않은 JSON → JSONDecodeError → 빈 이슈 목록 반환
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python", tmp_path="/tmp/test.py")
        with patch("subprocess.run", return_value=_mock_semgrep_proc("{broken json: [")):
            issues = _SemgrepAnalyzer().run(ctx)
        assert issues == []

    def test_run_returns_empty_on_completely_invalid_json(self, make_ctx):
        # stdout이 JSON 형식이 아닌 일반 텍스트 → 빈 이슈 목록 반환
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python", tmp_path="/tmp/test.py")
        with patch("subprocess.run", return_value=_mock_semgrep_proc("not json at all")):
            issues = _SemgrepAnalyzer().run(ctx)
        assert issues == []

    def test_run_does_not_raise_on_nonzero_returncode(self, make_ctx):
        # semgrep이 비정상 종료코드 반환 시에도 예외 없이 파싱된 이슈를 반환해야 한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python", tmp_path="/tmp/test.py")
        # returncode=1이어도 stdout에 유효한 JSON이 있으면 정상 파싱
        with patch("subprocess.run", return_value=_mock_semgrep_proc(SAMPLE_OUTPUT_SECURITY_ERROR, returncode=1)):
            issues = _SemgrepAnalyzer().run(ctx)
        assert len(issues) == 1


# ──────────────────────────────────────────────────────────────────────────────
# TestSemgrepSecurityCategoryMapping — security 메타데이터 기반 카테고리 분류 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestSemgrepSecurityCategoryMapping:
    def test_metadata_category_security_maps_to_security_issue(self, make_ctx):
        # extra.metadata.category == "security"이면 AnalysisIssue.category="security"여야 한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python", tmp_path="/tmp/test.py")
        with patch("subprocess.run", return_value=_mock_semgrep_proc(SAMPLE_OUTPUT_SECURITY_ERROR)):
            issues = _SemgrepAnalyzer().run(ctx)
        assert issues[0].category == "security"

    def test_missing_metadata_category_defaults_to_code_quality(self, make_ctx):
        # extra.metadata에 "category" 키가 없으면 AnalysisIssue.category="code_quality"여야 한다
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="python", tmp_path="/tmp/test.py")
        with patch("subprocess.run", return_value=_mock_semgrep_proc(SAMPLE_OUTPUT_CODE_QUALITY_WARNING)):
            issues = _SemgrepAnalyzer().run(ctx)
        assert issues[0].category == "code_quality"

    def test_non_security_metadata_category_maps_to_code_quality(self, make_ctx):
        # extra.metadata.category == "correctness"처럼 security가 아닌 값 → "code_quality"로 분류
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        ctx = make_ctx(language="go", filename="main.go", tmp_path="/tmp/main.go")
        output = json.dumps({
            "results": [
                {
                    "check_id": "go.lang.correctness.nil-dereference",
                    "extra": {
                        "severity": "WARNING",
                        "message": "possible nil dereference",
                        "metadata": {"category": "correctness"},
                    },
                    "path": "/tmp/main.go",
                    "start": {"line": 20},
                }
            ]
        })
        with patch("subprocess.run", return_value=_mock_semgrep_proc(output)):
            issues = _SemgrepAnalyzer().run(ctx)
        assert issues[0].category == "code_quality"


# ──────────────────────────────────────────────────────────────────────────────
# TestSemgrepRegistration — 모듈 로드 시 REGISTRY 자동 등록 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestSemgrepRegistration:
    def test_module_import_registers_semgrep_in_registry(self):
        # src.analyzer.io.tools.semgrep 임포트 시 REGISTRY에 _SemgrepAnalyzer가 자동 등록된다
        from src.analyzer.pure.registry import REGISTRY
        import importlib
        import src.analyzer.io.tools.semgrep  # noqa: F401
        importlib.reload(src.analyzer.io.tools.semgrep)  # 재로드로 등록 트리거
        names = [a.name for a in REGISTRY]
        assert "semgrep" in names

    def test_double_import_does_not_duplicate_registry_entry(self):
        # 동일 모듈을 두 번 로드해도 REGISTRY에 "semgrep"이 중복 등록되지 않아야 한다
        from src.analyzer.pure.registry import REGISTRY, register
        import src.analyzer.io.tools.semgrep  # noqa: F401
        import importlib
        importlib.reload(src.analyzer.io.tools.semgrep)
        importlib.reload(src.analyzer.io.tools.semgrep)
        semgrep_entries = [a for a in REGISTRY if a.name == "semgrep"]
        assert len(semgrep_entries) == 1

    def test_semgrep_analyzer_satisfies_analyzer_protocol(self):
        # _SemgrepAnalyzer 인스턴스가 Analyzer Protocol을 충족하는지 검증한다
        from src.analyzer.pure.registry import Analyzer
        from src.analyzer.io.tools.semgrep import _SemgrepAnalyzer
        assert isinstance(_SemgrepAnalyzer(), Analyzer)


# ──────────────────────────────────────────────────────────────────────────────
# TestSemgrepAnalyzeFileIntegration — analyze_file 통합 경로 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestSemgrepAnalyzeFileIntegration:
    def test_semgrep_runs_for_python_file_when_installed(self):
        # semgrep 설치 환경에서 python 파일 분석 시 _SemgrepAnalyzer.run()이 호출된다
        from src.analyzer.io.static import analyze_file
        from src.analyzer.pure.registry import REGISTRY
        import src.analyzer.io.tools.semgrep  # noqa: F401

        # semgrep이 "설치된" 것으로 가장하고, run()은 빈 리스트 반환
        with patch("shutil.which", return_value="/usr/bin/semgrep"), \
             patch("subprocess.run", return_value=_mock_semgrep_proc(SAMPLE_OUTPUT_EMPTY)):
            result = analyze_file("app.py", "def foo(): pass\n")

        # StaticAnalysisResult가 정상 반환되어야 한다
        from src.analyzer.io.static import StaticAnalysisResult
        assert isinstance(result, StaticAnalysisResult)

    def test_semgrep_skipped_for_python_file_when_not_installed(self):
        # semgrep 미설치 환경에서는 _SemgrepAnalyzer가 is_enabled()=False → run() 호출 안 됨
        from src.analyzer.io.static import analyze_file

        run_called = []

        def fake_run(ctx):
            run_called.append(ctx)
            return []

        import src.analyzer.io.tools.semgrep
        from src.analyzer.pure.registry import REGISTRY

        # REGISTRY에서 semgrep analyzer를 찾아 run을 교체
        with patch("shutil.which", return_value=None):
            result = analyze_file("module.py", "x = 1\n")

        # shutil.which=None이므로 semgrep의 run()은 호출되지 않아야 한다
        from src.analyzer.io.static import StaticAnalysisResult
        assert isinstance(result, StaticAnalysisResult)

    def test_semgrep_runs_for_javascript_file_when_installed(self):
        # javascript 파일도 semgrep이 설치된 경우 분석 대상이 된다
        from src.analyzer.io.static import analyze_file
        import src.analyzer.io.tools.semgrep  # noqa: F401

        with patch("shutil.which", return_value="/usr/bin/semgrep"), \
             patch("subprocess.run", return_value=_mock_semgrep_proc(SAMPLE_OUTPUT_EMPTY)):
            result = analyze_file("app.js", "const x = 1;\n")

        from src.analyzer.io.static import StaticAnalysisResult
        assert isinstance(result, StaticAnalysisResult)
        # javascript는 python 도구(pylint/flake8/bandit)가 지원 안 하므로 issues는 비어 있어야 한다
        assert result.issues == []
