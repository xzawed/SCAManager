"""TDD Red 상태 테스트 — Phase D.3: RuboCop Analyzer.

신설 대상:
  src/analyzer/io/tools/rubocop.py  — _RuboCopAnalyzer (Analyzer Protocol 구현)

RuboCop은 Ruby 파일의 코드 품질 + 보안 분석을 담당한다.
subprocess.run mock으로 실제 rubocop 바이너리 호출 없이 모든 경로를 검증한다.
"""
from __future__ import annotations

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

import pytest  # noqa: E402
from unittest.mock import patch, MagicMock  # noqa: E402


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
# 공용 헬퍼 — rubocop subprocess mock 생성
# ──────────────────────────────────────────────────────────────────────────────

def _mock_rubocop_proc(stdout: str, returncode: int = 0) -> MagicMock:
    """subprocess.run 반환값을 모방하는 MagicMock을 생성한다."""
    mock = MagicMock()
    mock.stdout = stdout
    mock.stderr = ""
    mock.returncode = returncode
    return mock


# RuboCop JSON 출력 샘플 — warning + convention 혼합
SAMPLE_RUBOCOP_OUTPUT = json.dumps({
    "metadata": {"rubocop_version": "1.50.0", "ruby_engine": "ruby"},
    "files": [
        {
            "path": "example.rb",
            "offenses": [
                {
                    "severity": "warning",
                    "message": "Use `Array.new` instead of empty array literal.",
                    "cop_name": "Style/EmptyArrayLiteral",
                    "location": {"start_line": 10, "start_column": 5},
                },
                {
                    "severity": "convention",
                    "message": "Line is too long.",
                    "cop_name": "Layout/LineLength",
                    "location": {"start_line": 25, "start_column": 1},
                },
            ],
        }
    ],
    "summary": {"offense_count": 2, "target_file_count": 1, "inspected_file_count": 1},
})

# RuboCop JSON 출력 샘플 — error 레벨만
SAMPLE_OUTPUT_ERROR_ONLY = json.dumps({
    "files": [
        {
            "path": "broken.rb",
            "offenses": [
                {
                    "severity": "error",
                    "message": "Syntax error detected.",
                    "cop_name": "Lint/Syntax",
                    "location": {"start_line": 3, "start_column": 1},
                },
            ],
        }
    ],
    "summary": {"offense_count": 1},
})

# RuboCop JSON 출력 샘플 — fatal 레벨 (ERROR 로 매핑되어야 함)
SAMPLE_OUTPUT_FATAL = json.dumps({
    "files": [
        {
            "path": "fatal.rb",
            "offenses": [
                {
                    "severity": "fatal",
                    "message": "Fatal parse error.",
                    "cop_name": "Lint/Syntax",
                    "location": {"start_line": 1, "start_column": 1},
                },
            ],
        }
    ],
    "summary": {"offense_count": 1},
})

# RuboCop JSON 출력 샘플 — refactor / convention / warning (전부 WARNING 으로 매핑)
SAMPLE_OUTPUT_NON_ERROR = json.dumps({
    "files": [
        {
            "path": "mix.rb",
            "offenses": [
                {
                    "severity": "refactor",
                    "message": "Assignment branch condition too high.",
                    "cop_name": "Metrics/AbcSize",
                    "location": {"start_line": 5, "start_column": 1},
                },
                {
                    "severity": "convention",
                    "message": "Prefer double-quoted strings.",
                    "cop_name": "Style/StringLiterals",
                    "location": {"start_line": 8, "start_column": 3},
                },
                {
                    "severity": "warning",
                    "message": "Useless assignment.",
                    "cop_name": "Lint/UselessAssignment",
                    "location": {"start_line": 12, "start_column": 1},
                },
            ],
        }
    ],
    "summary": {"offense_count": 3},
})

# RuboCop JSON 출력 샘플 — Security/ cop (category=security 매핑 검증용)
SAMPLE_OUTPUT_SECURITY = json.dumps({
    "files": [
        {
            "path": "unsafe.rb",
            "offenses": [
                {
                    "severity": "warning",
                    "message": "Prefer using `YAML.safe_load` over `YAML.load`.",
                    "cop_name": "Security/YAMLLoad",
                    "location": {"start_line": 7, "start_column": 1},
                },
                {
                    "severity": "warning",
                    "message": "Prefer `File.open` over `Kernel#open`.",
                    "cop_name": "Security/Open",
                    "location": {"start_line": 15, "start_column": 1},
                },
                {
                    "severity": "convention",
                    "message": "Prefer double-quoted strings.",
                    "cop_name": "Style/StringLiterals",
                    "location": {"start_line": 20, "start_column": 3},
                },
            ],
        }
    ],
    "summary": {"offense_count": 3},
})

# RuboCop JSON 출력 샘플 — 빈 offenses
SAMPLE_OUTPUT_EMPTY = json.dumps({
    "files": [{"path": "clean.rb", "offenses": []}],
    "summary": {"offense_count": 0},
})


# ──────────────────────────────────────────────────────────────────────────────
# 픽스처 — AnalyzeContext 생성 헬퍼
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def make_ctx():
    """언어와 파일명을 받아 AnalyzeContext를 생성하는 팩토리 픽스처."""
    from src.analyzer.pure.registry import AnalyzeContext

    def _factory(language: str = "ruby", filename: str = "example.rb",
                 is_test: bool = False, tmp_path: str = "/tmp/example.rb"):
        return AnalyzeContext(
            filename=filename,
            content="puts 'hello'\n",
            language=language,
            is_test=is_test,
            tmp_path=tmp_path,
        )
    return _factory


# ──────────────────────────────────────────────────────────────────────────────
# Test 1 — REGISTRY 자동 등록 검증
# ──────────────────────────────────────────────────────────────────────────────

def test_rubocop_analyzer_registered():
    # 모듈 import 시 REGISTRY 에 _RuboCopAnalyzer 가 자동 등록되어야 한다
    import importlib
    from src.analyzer.pure.registry import REGISTRY
    import src.analyzer.io.tools.rubocop  # noqa: F401
    importlib.reload(src.analyzer.io.tools.rubocop)
    names = [a.name for a in REGISTRY]
    assert "rubocop" in names


# ──────────────────────────────────────────────────────────────────────────────
# Test 2 — supports() 언어별 분기 검증
# ──────────────────────────────────────────────────────────────────────────────

def test_rubocop_supports_ruby_language(make_ctx):
    # ctx.language="ruby" 일 때만 supports() 가 True 를 반환해야 한다
    from src.analyzer.io.tools.rubocop import _RuboCopAnalyzer
    analyzer = _RuboCopAnalyzer()
    assert analyzer.supports(make_ctx(language="ruby")) is True
    for lang in ("python", "javascript", "typescript", "go", "shell", "unknown"):
        assert analyzer.supports(make_ctx(language=lang)) is False


# ──────────────────────────────────────────────────────────────────────────────
# Test 3 — is_enabled() 바이너리 존재 여부 반영
# ──────────────────────────────────────────────────────────────────────────────

def test_rubocop_is_enabled_when_binary_present(make_ctx):
    # shutil.which("rubocop") 결과에 따라 is_enabled() 가 True/False 를 반환해야 한다
    from src.analyzer.io.tools.rubocop import _RuboCopAnalyzer
    ctx = make_ctx(language="ruby")
    with patch("src.analyzer.io.tools.rubocop.shutil.which", return_value="/usr/bin/rubocop"):
        assert _RuboCopAnalyzer().is_enabled(ctx) is True
    with patch("src.analyzer.io.tools.rubocop.shutil.which", return_value=None):
        assert _RuboCopAnalyzer().is_enabled(ctx) is False


# ──────────────────────────────────────────────────────────────────────────────
# Test 4 — JSON 출력 → AnalysisIssue 목록 파싱
# ──────────────────────────────────────────────────────────────────────────────

def test_rubocop_parses_offenses(make_ctx):
    # 샘플 JSON 에 담긴 2개 offense 가 AnalysisIssue 2개로 변환되며 필드가 정확히 채워져야 한다
    from src.analyzer.io.tools.rubocop import _RuboCopAnalyzer
    ctx = make_ctx(language="ruby", tmp_path="/tmp/example.rb")
    with patch(
        "src.analyzer.io.tools.rubocop.subprocess.run",
        return_value=_mock_rubocop_proc(SAMPLE_RUBOCOP_OUTPUT),
    ):
        issues = _RuboCopAnalyzer().run(ctx)
    assert len(issues) == 2
    # 모든 이슈: tool=rubocop, language=ruby 기본 필드 설정 검증
    for issue in issues:
        assert issue.tool == "rubocop"
        assert issue.language == "ruby"
    lines = sorted(i.line for i in issues)
    assert lines == [10, 25]
    messages = [i.message for i in issues]
    assert any("Array.new" in m for m in messages)


# ──────────────────────────────────────────────────────────────────────────────
# Test 5 — severity 매핑: error/fatal→ERROR, 나머지→WARNING
# ──────────────────────────────────────────────────────────────────────────────

def test_rubocop_error_severity_mapping(make_ctx):
    # "error" / "fatal" 은 Severity.ERROR, "refactor"/"convention"/"warning" 은 Severity.WARNING
    from src.analyzer.io.tools.rubocop import _RuboCopAnalyzer
    ctx = make_ctx(language="ruby")

    # error → ERROR
    with patch(
        "src.analyzer.io.tools.rubocop.subprocess.run",
        return_value=_mock_rubocop_proc(SAMPLE_OUTPUT_ERROR_ONLY),
    ):
        issues = _RuboCopAnalyzer().run(ctx)
    assert len(issues) == 1
    assert issues[0].severity == "error"

    # fatal → ERROR
    with patch(
        "src.analyzer.io.tools.rubocop.subprocess.run",
        return_value=_mock_rubocop_proc(SAMPLE_OUTPUT_FATAL),
    ):
        issues = _RuboCopAnalyzer().run(ctx)
    assert len(issues) == 1
    assert issues[0].severity == "error"

    # refactor/convention/warning → WARNING
    with patch(
        "src.analyzer.io.tools.rubocop.subprocess.run",
        return_value=_mock_rubocop_proc(SAMPLE_OUTPUT_NON_ERROR),
    ):
        issues = _RuboCopAnalyzer().run(ctx)
    assert len(issues) == 3
    for issue in issues:
        assert issue.severity == "warning"


# ──────────────────────────────────────────────────────────────────────────────
# Test 6 — cop_name 이 "Security/" 로 시작하면 category=SECURITY
# ──────────────────────────────────────────────────────────────────────────────

def test_rubocop_security_cop_category(make_ctx):
    # cop_name 이 "Security/" prefix 면 category=SECURITY, 그 외엔 CODE_QUALITY
    from src.analyzer.io.tools.rubocop import _RuboCopAnalyzer
    ctx = make_ctx(language="ruby", tmp_path="/tmp/unsafe.rb")
    with patch(
        "src.analyzer.io.tools.rubocop.subprocess.run",
        return_value=_mock_rubocop_proc(SAMPLE_OUTPUT_SECURITY),
    ):
        issues = _RuboCopAnalyzer().run(ctx)
    assert len(issues) == 3
    by_cop = {}
    for issue in issues:
        # message 로 식별 (cop_name 은 AnalysisIssue 에 별도 필드가 없을 수 있어 message 로 매핑)
        if "YAML" in issue.message:
            by_cop["yaml"] = issue
        elif "File.open" in issue.message:
            by_cop["open"] = issue
        else:
            by_cop["style"] = issue
    assert by_cop["yaml"].category == "security"
    assert by_cop["open"].category == "security"
    assert by_cop["style"].category == "code_quality"


# ──────────────────────────────────────────────────────────────────────────────
# Test 7 — subprocess TimeoutExpired → 빈 리스트 (graceful degradation)
# ──────────────────────────────────────────────────────────────────────────────

def test_rubocop_handles_timeout(make_ctx):
    # subprocess.TimeoutExpired 발생 시 파이프라인 미중단 — 빈 리스트 반환
    from src.analyzer.io.tools.rubocop import _RuboCopAnalyzer
    ctx = make_ctx(language="ruby")
    with patch(
        "src.analyzer.io.tools.rubocop.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="rubocop", timeout=30),
    ):
        assert _RuboCopAnalyzer().run(ctx) == []


# ──────────────────────────────────────────────────────────────────────────────
# Test 8 — JSON 파싱 실패 시 빈 리스트
# ──────────────────────────────────────────────────────────────────────────────

def test_rubocop_handles_invalid_json(make_ctx):
    # stdout 이 유효하지 않은 JSON → JSONDecodeError → 빈 리스트 반환
    from src.analyzer.io.tools.rubocop import _RuboCopAnalyzer
    ctx = make_ctx(language="ruby")
    with patch(
        "src.analyzer.io.tools.rubocop.subprocess.run",
        return_value=_mock_rubocop_proc("{not valid json"),
    ):
        assert _RuboCopAnalyzer().run(ctx) == []


# ──────────────────────────────────────────────────────────────────────────────
# Test 9 — 빈 stdout → 빈 리스트
# ──────────────────────────────────────────────────────────────────────────────

def test_rubocop_empty_stdout_returns_empty(make_ctx):
    # stdout 이 빈 문자열 혹은 offenses=[] 이면 빈 리스트 반환
    from src.analyzer.io.tools.rubocop import _RuboCopAnalyzer
    ctx = make_ctx(language="ruby")

    # 완전히 빈 stdout
    with patch(
        "src.analyzer.io.tools.rubocop.subprocess.run",
        return_value=_mock_rubocop_proc(""),
    ):
        assert _RuboCopAnalyzer().run(ctx) == []

    # offenses 가 빈 배열인 정상 JSON
    with patch(
        "src.analyzer.io.tools.rubocop.subprocess.run",
        return_value=_mock_rubocop_proc(SAMPLE_OUTPUT_EMPTY),
    ):
        assert _RuboCopAnalyzer().run(ctx) == []
