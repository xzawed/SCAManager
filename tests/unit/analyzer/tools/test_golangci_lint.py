"""TDD Red 상태 테스트 — Phase D.4: golangci-lint Analyzer.

신설 대상:
  src/analyzer/io/tools/golangci_lint.py  — _GolangciLintAnalyzer (Analyzer Protocol 구현)

golangci-lint 는 Go 용 메타 정적 분석 도구 (errcheck/govet/staticcheck/gosec 등 통합).
subprocess.run mock 으로 실제 바이너리 호출 없이 모든 경로를 검증한다.

Go 특유 요구사항:
  ctx.tmp_path 가 단일 .go 파일이면 주변에 go.mod 가 없어서 "no Go files" 오류 발생.
  run() 은 tmp_path 의 디렉토리에 최소 go.mod 를 자동 생성해 golangci-lint 가 모듈을
  인식하도록 한다 (test 7 에서 검증).

severity / category 매핑:
  FromLinter="gosec" / "gas"  → Category.SECURITY,     Severity.ERROR
  그 외 (errcheck, govet, …) → Category.CODE_QUALITY, Severity.WARNING
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile

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
# 공용 헬퍼 — golangci-lint subprocess mock 생성
# ──────────────────────────────────────────────────────────────────────────────

def _mock_proc(stdout: str, returncode: int = 0, stderr: str = "") -> MagicMock:
    """subprocess.run 반환값을 모방하는 MagicMock을 생성한다."""
    mock = MagicMock()
    mock.stdout = stdout
    mock.stderr = stderr
    mock.returncode = returncode
    return mock


# golangci-lint JSON 출력 샘플 — errcheck(코드품질) + govet(코드품질) 혼합
SAMPLE_GOLANGCI_OUTPUT = json.dumps({
    "Issues": [
        {
            "FromLinter": "errcheck",
            "Text": "Error return value of `json.Unmarshal` is not checked",
            "Severity": "",
            "SourceLines": ["    json.Unmarshal(data, &v)"],
            "Replacement": None,
            "Pos": {
                "Filename": "example.go",
                "Offset": 0,
                "Line": 15,
                "Column": 5,
            },
        },
        {
            "FromLinter": "govet",
            "Text": "shadow: declaration of \"err\" shadows declaration",
            "Severity": "",
            "SourceLines": [],
            "Replacement": None,
            "Pos": {
                "Filename": "example.go",
                "Offset": 0,
                "Line": 28,
                "Column": 9,
            },
        },
    ],
    "Report": {},
})

# golangci-lint JSON 출력 샘플 — gosec 보안 이슈 (category=SECURITY, severity=ERROR)
SAMPLE_OUTPUT_GOSEC = json.dumps({
    "Issues": [
        {
            "FromLinter": "gosec",
            "Text": "G304: Potential file inclusion via variable",
            "Severity": "",
            "SourceLines": ["    f, _ := os.Open(path)"],
            "Replacement": None,
            "Pos": {
                "Filename": "secret.go",
                "Offset": 0,
                "Line": 7,
                "Column": 14,
            },
        },
        {
            "FromLinter": "gosec",
            "Text": "G101: Potential hardcoded credentials",
            "Severity": "",
            "SourceLines": [],
            "Replacement": None,
            "Pos": {
                "Filename": "secret.go",
                "Offset": 0,
                "Line": 12,
                "Column": 2,
            },
        },
    ],
    "Report": {},
})

# golangci-lint JSON 출력 샘플 — 일반 linters (errcheck·staticcheck·unused → code_quality + WARNING)
SAMPLE_OUTPUT_NON_SECURITY = json.dumps({
    "Issues": [
        {
            "FromLinter": "errcheck",
            "Text": "Error return value is not checked",
            "Severity": "",
            "SourceLines": [],
            "Pos": {"Filename": "a.go", "Line": 10, "Column": 1},
        },
        {
            "FromLinter": "staticcheck",
            "Text": "SA1000: invalid regular expression",
            "Severity": "",
            "SourceLines": [],
            "Pos": {"Filename": "a.go", "Line": 20, "Column": 3},
        },
        {
            "FromLinter": "unused",
            "Text": "U1000: func `helper` is unused",
            "Severity": "",
            "SourceLines": [],
            "Pos": {"Filename": "a.go", "Line": 33, "Column": 1},
        },
    ],
    "Report": {},
})

# golangci-lint JSON 출력 샘플 — security(gosec) + code_quality(errcheck) 혼합
SAMPLE_OUTPUT_MIXED = json.dumps({
    "Issues": [
        {
            "FromLinter": "gosec",
            "Text": "G404: Use of weak random",
            "Severity": "",
            "SourceLines": [],
            "Pos": {"Filename": "mix.go", "Line": 5, "Column": 1},
        },
        {
            "FromLinter": "errcheck",
            "Text": "Error return value is not checked",
            "Severity": "",
            "SourceLines": [],
            "Pos": {"Filename": "mix.go", "Line": 18, "Column": 2},
        },
    ],
    "Report": {},
})

# golangci-lint JSON 출력 샘플 — 빈 Issues
SAMPLE_OUTPUT_EMPTY = json.dumps({"Issues": [], "Report": {}})


# ──────────────────────────────────────────────────────────────────────────────
# 픽스처 — AnalyzeContext 생성 헬퍼
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def make_ctx():
    """언어와 파일명을 받아 AnalyzeContext를 생성하는 팩토리 픽스처."""
    from src.analyzer.pure.registry import AnalyzeContext

    def _factory(language: str = "go", filename: str = "example.go",
                 is_test: bool = False, tmp_path: str = "/tmp/example.go"):
        return AnalyzeContext(
            filename=filename,
            content="package main\n\nfunc main() {}\n",
            language=language,
            is_test=is_test,
            tmp_path=tmp_path,
        )
    return _factory


# ──────────────────────────────────────────────────────────────────────────────
# Test 1 — REGISTRY 자동 등록 검증
# ──────────────────────────────────────────────────────────────────────────────

def test_golangci_lint_analyzer_registered():
    # 모듈 import 시 REGISTRY 에 _GolangciLintAnalyzer 가 자동 등록되어야 한다
    import importlib
    from src.analyzer.pure.registry import REGISTRY
    import src.analyzer.io.tools.golangci_lint  # noqa: F401
    importlib.reload(src.analyzer.io.tools.golangci_lint)
    names = [a.name for a in REGISTRY]
    assert "golangci-lint" in names


# ──────────────────────────────────────────────────────────────────────────────
# Test 2 — supports() 언어별 분기 검증
# ──────────────────────────────────────────────────────────────────────────────

def test_golangci_lint_supports_go_language(make_ctx):
    # ctx.language="go" 일 때만 supports() 가 True 를 반환해야 한다
    from src.analyzer.io.tools.golangci_lint import _GolangciLintAnalyzer
    analyzer = _GolangciLintAnalyzer()
    assert analyzer.supports(make_ctx(language="go")) is True
    for lang in ("python", "javascript", "typescript", "ruby", "shell", "unknown"):
        assert analyzer.supports(make_ctx(language=lang)) is False


# ──────────────────────────────────────────────────────────────────────────────
# Test 3 — is_enabled() 바이너리 존재 여부 반영
# ──────────────────────────────────────────────────────────────────────────────

def test_golangci_lint_is_enabled_when_binary_present(make_ctx):
    # shutil.which("golangci-lint") 결과에 따라 is_enabled() 가 True/False 를 반환해야 한다
    from src.analyzer.io.tools.golangci_lint import _GolangciLintAnalyzer
    ctx = make_ctx(language="go")
    with patch("src.analyzer.io.tools.golangci_lint.shutil.which",
               return_value="/usr/bin/golangci-lint"):
        assert _GolangciLintAnalyzer().is_enabled(ctx) is True
    with patch("src.analyzer.io.tools.golangci_lint.shutil.which", return_value=None):
        assert _GolangciLintAnalyzer().is_enabled(ctx) is False


# ──────────────────────────────────────────────────────────────────────────────
# Test 4 — JSON 출력 → AnalysisIssue 목록 파싱
# ──────────────────────────────────────────────────────────────────────────────

def test_golangci_lint_parses_issues(make_ctx):
    # 샘플 JSON 에 담긴 2개 Issue 가 AnalysisIssue 2개로 변환되며 필드가 정확히 채워져야 한다
    from src.analyzer.io.tools.golangci_lint import _GolangciLintAnalyzer
    with tempfile.TemporaryDirectory() as d:
        go_file = os.path.join(d, "example.go")
        with open(go_file, "w", encoding="utf-8") as f:
            f.write("package main\n")
        ctx = make_ctx(language="go", tmp_path=go_file)
        with patch(
            "src.analyzer.io.tools.golangci_lint.subprocess.run",
            return_value=_mock_proc(SAMPLE_GOLANGCI_OUTPUT),
        ):
            issues = _GolangciLintAnalyzer().run(ctx)
    assert len(issues) == 2
    for issue in issues:
        assert issue.tool == "golangci-lint"
        assert issue.language == "go"
    lines = sorted(i.line for i in issues)
    assert lines == [15, 28]
    messages = [i.message for i in issues]
    assert any("json.Unmarshal" in m for m in messages)
    assert any("shadow" in m for m in messages)


# ──────────────────────────────────────────────────────────────────────────────
# Test 5 — FromLinter="gosec" → category=SECURITY, severity=ERROR
# ──────────────────────────────────────────────────────────────────────────────

def test_golangci_lint_gosec_is_security(make_ctx):
    # gosec linter 결과는 모두 category=SECURITY 이며 severity=ERROR 로 매핑되어야 한다
    from src.analyzer.io.tools.golangci_lint import _GolangciLintAnalyzer
    with tempfile.TemporaryDirectory() as d:
        go_file = os.path.join(d, "secret.go")
        with open(go_file, "w", encoding="utf-8") as f:
            f.write("package main\n")
        ctx = make_ctx(language="go", tmp_path=go_file)
        with patch(
            "src.analyzer.io.tools.golangci_lint.subprocess.run",
            return_value=_mock_proc(SAMPLE_OUTPUT_GOSEC),
        ):
            issues = _GolangciLintAnalyzer().run(ctx)
    assert len(issues) == 2
    for issue in issues:
        assert issue.category == "security"
        assert issue.severity == "error"


# ──────────────────────────────────────────────────────────────────────────────
# Test 6 — 일반 linter(errcheck/staticcheck/unused) → CODE_QUALITY + WARNING
# ──────────────────────────────────────────────────────────────────────────────

def test_golangci_lint_other_linters_are_code_quality(make_ctx):
    # gosec 외의 linter 는 모두 category=CODE_QUALITY, severity=WARNING 으로 매핑된다
    from src.analyzer.io.tools.golangci_lint import _GolangciLintAnalyzer
    with tempfile.TemporaryDirectory() as d:
        go_file = os.path.join(d, "a.go")
        with open(go_file, "w", encoding="utf-8") as f:
            f.write("package main\n")
        ctx = make_ctx(language="go", tmp_path=go_file)
        with patch(
            "src.analyzer.io.tools.golangci_lint.subprocess.run",
            return_value=_mock_proc(SAMPLE_OUTPUT_NON_SECURITY),
        ):
            issues = _GolangciLintAnalyzer().run(ctx)
    assert len(issues) == 3
    for issue in issues:
        assert issue.category == "code_quality"
        assert issue.severity == "warning"

    # 혼합 샘플: gosec=security+error, errcheck=code_quality+warning 동시 검증
    with tempfile.TemporaryDirectory() as d:
        go_file = os.path.join(d, "mix.go")
        with open(go_file, "w", encoding="utf-8") as f:
            f.write("package main\n")
        ctx = make_ctx(language="go", tmp_path=go_file)
        with patch(
            "src.analyzer.io.tools.golangci_lint.subprocess.run",
            return_value=_mock_proc(SAMPLE_OUTPUT_MIXED),
        ):
            issues = _GolangciLintAnalyzer().run(ctx)
    assert len(issues) == 2
    by_linter = {i.message.split(":")[0]: i for i in issues}
    assert by_linter["G404"].category == "security"
    assert by_linter["G404"].severity == "error"
    # errcheck 메시지는 "Error return value..." 로 시작
    err_issue = next(i for i in issues if "Error return" in i.message)
    assert err_issue.category == "code_quality"
    assert err_issue.severity == "warning"


# ──────────────────────────────────────────────────────────────────────────────
# Test 7 — .go 파일 주변에 go.mod 가 없으면 run() 이 자동 생성해야 한다
# ──────────────────────────────────────────────────────────────────────────────

def test_golangci_lint_creates_go_mod_if_missing(make_ctx):
    # tmp_path 디렉토리에 go.mod 가 없으면 run() 이 최소 go.mod 파일을 자동 생성해야 한다
    from src.analyzer.io.tools.golangci_lint import _GolangciLintAnalyzer
    with tempfile.TemporaryDirectory() as d:
        go_file = os.path.join(d, "example.go")
        with open(go_file, "w", encoding="utf-8") as f:
            f.write("package main\n\nfunc main() {}\n")
        # 사전 조건: go.mod 가 아직 없다
        go_mod_path = os.path.join(d, "go.mod")
        assert not os.path.exists(go_mod_path)

        ctx = make_ctx(language="go", tmp_path=go_file)
        with patch(
            "src.analyzer.io.tools.golangci_lint.subprocess.run",
            return_value=_mock_proc(SAMPLE_OUTPUT_EMPTY),
        ):
            _GolangciLintAnalyzer().run(ctx)

        # run() 호출 후 go.mod 가 생성되었어야 한다
        assert os.path.exists(go_mod_path), "go.mod 파일이 자동 생성되지 않았다"
        content = open(go_mod_path, encoding="utf-8").read()
        assert "module" in content, "go.mod 에 module 지시어가 없다"
        assert "go " in content, "go.mod 에 go 버전 지시어가 없다"


# ──────────────────────────────────────────────────────────────────────────────
# Test 8 — subprocess TimeoutExpired → 빈 리스트 (graceful degradation)
# ──────────────────────────────────────────────────────────────────────────────

def test_golangci_lint_handles_timeout(make_ctx):
    # subprocess.TimeoutExpired 발생 시 파이프라인 미중단 — 빈 리스트 반환
    from src.analyzer.io.tools.golangci_lint import _GolangciLintAnalyzer
    with tempfile.TemporaryDirectory() as d:
        go_file = os.path.join(d, "slow.go")
        with open(go_file, "w", encoding="utf-8") as f:
            f.write("package main\n")
        ctx = make_ctx(language="go", tmp_path=go_file)
        with patch(
            "src.analyzer.io.tools.golangci_lint.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="golangci-lint", timeout=30),
        ):
            assert _GolangciLintAnalyzer().run(ctx) == []


# ──────────────────────────────────────────────────────────────────────────────
# Test 9 — JSON 파싱 실패 시 빈 리스트
# ──────────────────────────────────────────────────────────────────────────────

def test_golangci_lint_handles_invalid_json(make_ctx):
    # stdout 이 유효하지 않은 JSON → JSONDecodeError → 빈 리스트 반환
    from src.analyzer.io.tools.golangci_lint import _GolangciLintAnalyzer
    with tempfile.TemporaryDirectory() as d:
        go_file = os.path.join(d, "broken.go")
        with open(go_file, "w", encoding="utf-8") as f:
            f.write("package main\n")
        ctx = make_ctx(language="go", tmp_path=go_file)
        with patch(
            "src.analyzer.io.tools.golangci_lint.subprocess.run",
            return_value=_mock_proc("{not valid json"),
        ):
            assert _GolangciLintAnalyzer().run(ctx) == []
