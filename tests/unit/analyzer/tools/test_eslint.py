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
    from src.analyzer.pure.registry import AnalyzeContext

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
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        assert _ESLintAnalyzer().name == "eslint"

    def test_category_is_code_quality(self):
        # _ESLintAnalyzer.category는 "code_quality"이어야 한다
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        assert _ESLintAnalyzer().category == "code_quality"

    def test_supported_languages_is_frozenset(self):
        # SUPPORTED_LANGUAGES는 frozenset 타입이어야 한다
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        assert isinstance(_ESLintAnalyzer.SUPPORTED_LANGUAGES, frozenset)

    def test_supported_languages_contains_javascript_and_typescript(self):
        # SUPPORTED_LANGUAGES에 "javascript"와 "typescript" 양쪽이 포함되어야 한다
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        assert "javascript" in _ESLintAnalyzer.SUPPORTED_LANGUAGES
        assert "typescript" in _ESLintAnalyzer.SUPPORTED_LANGUAGES

    def test_supported_languages_contains_exactly_two_entries(self):
        # SUPPORTED_LANGUAGES는 정확히 javascript와 typescript 두 언어만 포함해야 한다
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        assert _ESLintAnalyzer.SUPPORTED_LANGUAGES == frozenset({"javascript", "typescript"})


# ──────────────────────────────────────────────────────────────────────────────
# TestESLintSupports — supports() 언어별 반환값 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestESLintSupports:
    def test_supports_returns_true_for_javascript(self, make_ctx):
        # javascript 파일에서 supports()는 True를 반환해야 한다
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript")
        assert _ESLintAnalyzer().supports(ctx) is True

    def test_supports_returns_true_for_typescript(self, make_ctx):
        # typescript 파일에서 supports()는 True를 반환해야 한다
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="typescript", filename="app.ts", tmp_path="/tmp/app.ts")
        assert _ESLintAnalyzer().supports(ctx) is True

    @pytest.mark.parametrize("language", [
        "python", "go", "shell", "unknown", "java", "rust",
    ])
    def test_supports_returns_false_for_non_js_languages(self, language, make_ctx):
        # javascript/typescript 외 언어에서 supports()는 False를 반환해야 한다
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language=language)
        assert _ESLintAnalyzer().supports(ctx) is False


# ──────────────────────────────────────────────────────────────────────────────
# TestESLintIsEnabled — is_enabled() eslint 바이너리 존재 여부 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestESLintIsEnabled:
    def test_is_enabled_returns_true_when_eslint_binary_exists(self, make_ctx):
        # shutil.which("eslint")이 경로를 반환하면 is_enabled()는 True를 반환한다
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript")
        with patch("shutil.which", return_value="/usr/local/bin/eslint"):
            assert _ESLintAnalyzer().is_enabled(ctx) is True

    def test_is_enabled_returns_false_when_eslint_binary_missing(self, make_ctx):
        # shutil.which("eslint")이 None을 반환하면 is_enabled()는 False를 반환한다
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript")
        with patch("shutil.which", return_value=None):
            assert _ESLintAnalyzer().is_enabled(ctx) is False

    def test_is_enabled_checks_eslint_binary_specifically(self, make_ctx):
        # is_enabled()가 shutil.which를 "eslint" 인자로 호출하는지 검증한다
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
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
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_NO_MESSAGES)) as mock_run:
            _ESLintAnalyzer().run(ctx)
        call_args = mock_run.call_args[0][0]
        assert any("--format=json" in arg or arg == "--format=json" for arg in call_args)

    def test_run_passes_tmp_path_to_eslint(self, make_ctx):
        # eslint 실행 시 ctx.tmp_path가 인자에 포함되어야 한다
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/specific_app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_NO_MESSAGES)) as mock_run:
            _ESLintAnalyzer().run(ctx)
        call_args = mock_run.call_args[0][0]
        assert "/tmp/specific_app.js" in call_args

    def test_run_does_not_pass_no_eslintrc_flag(self, make_ctx):
        # 🔴 #1226: `--no-eslintrc` 는 eslint 9+ 에서 **무효 옵션**이다. 넘기면 eslint 가
        # "Invalid option '--eslintrc'" + exit 2 로 죽어 stdout 이 비고, 분석기는 조용히 [] 를
        # 반환했다 = JS/TS 이슈 항상 0 → 점수 인플레. 이전 판 테스트는 이 플래그를 **요구**해
        # 결함을 고정하고 있었다.
        # 🔴 #1226: `--no-eslintrc` is an invalid option on eslint 9+. Passing it kills eslint with
        # exit 2 and empty stdout, so the analyzer silently returned [] — JS/TS issues were always
        # zero, inflating scores. The previous version of this test *required* the broken flag.
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_NO_MESSAGES)) as mock_run:
            _ESLintAnalyzer().run(ctx)
        call_args = mock_run.call_args[0][0]
        assert "--no-eslintrc" not in call_args

    def test_run_executes_in_the_temp_files_own_directory(self, make_ctx):
        # 🔴 #1226 결함 5: eslint 는 **base path 밖의 파일을 린트하지 않는다**(9·10 공통 실측).
        # 분석 대상은 `tempfile.TemporaryDirectory()` 안에 있고(static.py) 앱 cwd 는 리포 루트라,
        # cwd 를 지정하지 않으면 모든 JS/TS 파일이 "File ignored because outside of base path" 로
        # 스킵된다 — 경로·플래그·설정형식을 다 고쳐도 분석은 여전히 0건이었다.
        # 🔴 #1226 defect 5: eslint refuses to lint files outside its base path (measured on both 9
        # and 10). The target lives in a TemporaryDirectory (static.py) while the app cwd is the repo
        # root, so without an explicit cwd every JS/TS file is skipped as "outside of base path" —
        # analysis stayed at zero even after fixing the path, the flag and the config format.
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path=os.path.join("/tmp", "sub", "app.js"))
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_NO_MESSAGES)) as mock_run:
            _ESLintAnalyzer().run(ctx)
        assert mock_run.call_args.kwargs["cwd"] == os.path.dirname(ctx.tmp_path)

    def test_run_includes_no_config_lookup_flag(self, make_ctx):
        # `--no-eslintrc` 의 flat-config 대응물 — 임베디드 설정만 쓰겠다는 원래 의도를 보존한다
        # (분석 대상은 임시 디렉토리라 상위 탐색이 무관한 설정을 주워올 수 있다).
        # The flat-config counterpart of `--no-eslintrc`, preserving the original intent of using
        # only the embedded config (the target lives in a temp dir where lookup could pick up
        # an unrelated config).
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_NO_MESSAGES)) as mock_run:
            _ESLintAnalyzer().run(ctx)
        call_args = mock_run.call_args[0][0]
        assert "--no-config-lookup" in call_args


# ──────────────────────────────────────────────────────────────────────────────
# TestESLintRunOutputParsing — run() JSON 출력 파싱 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestESLintRunOutputParsing:
    def test_run_maps_severity_2_to_error(self, make_ctx):
        # ESLint severity 2는 AnalysisIssue.severity="error"로 매핑되어야 한다
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_ERROR_ONLY)):
            issues = _ESLintAnalyzer().run(ctx)
        assert len(issues) == 1
        assert issues[0].severity == "error"

    def test_run_maps_severity_1_to_warning(self, make_ctx):
        # ESLint severity 1은 AnalysisIssue.severity="warning"으로 매핑되어야 한다
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_WARNING_ONLY)):
            issues = _ESLintAnalyzer().run(ctx)
        assert len(issues) == 1
        assert issues[0].severity == "warning"

    def test_run_parses_multiple_messages_correctly(self, make_ctx):
        # 복수 messages가 있는 출력에서 모든 이슈를 반환해야 한다
        # All issues must be returned when the output contains multiple messages.
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/test.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_MIXED)):
            issues = _ESLintAnalyzer().run(ctx)
        assert len(issues) == 2
        severities = {i.severity for i in issues}
        assert "error" in severities
        assert "warning" in severities

    def test_run_returns_empty_list_for_empty_messages(self, make_ctx):
        # messages 배열이 비어 있으면 빈 이슈 목록을 반환해야 한다
        # An empty messages array must return an empty issue list.
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/clean.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_NO_MESSAGES)):
            issues = _ESLintAnalyzer().run(ctx)
        assert issues == []

    def test_run_raises_for_empty_stdout(self, make_ctx):
        # 🔴 #1226 fail-closed: stdout 이 비었다 = eslint 가 죽었다 = **분석 안 됨**.
        # 조용한 [] 는 "이슈 0건" 과 구별 불가라 점수 인플레로 직결됐다. 이제 예외를 올려
        # static.py 가 `incomplete=True` 로 승격 → auto-merge/auto-approve 차단(#805/#806 대칭).
        # 🔴 #1226 fail-closed: empty stdout means eslint died, i.e. the file was NOT analyzed.
        # A silent [] was indistinguishable from "zero issues" and inflated scores. Raising lets
        # static.py promote it to incomplete and block auto-merge (symmetric with #805/#806).
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        analyzer = _ESLintAnalyzer()
        with patch("subprocess.run", return_value=_mock_eslint_proc("")):
            with pytest.raises(RuntimeError):
                analyzer.run(ctx)

    def test_run_raises_when_stdout_not_starts_with_bracket(self, make_ctx):
        # 🔴 #1226: 이것이 **운영에서 실제로 일어난 경로**다 — 설정 경로 부재/무효 플래그로
        # eslint 가 에러 텍스트만 뱉었고, 이전 판 테스트는 바로 이 입력에 [] 를 단언해
        # "설정을 못 찾음" 을 정상으로 인증하고 있었다.
        # 🔴 #1226: this is the path that actually happened in production — eslint emitted only
        # error text (missing config path / invalid flag), and the previous test asserted [] for
        # exactly this input, certifying "config not found" as a healthy result.
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        analyzer = _ESLintAnalyzer()
        with patch("subprocess.run", return_value=_mock_eslint_proc("Error: cannot find eslint config")):
            with pytest.raises(RuntimeError):
                analyzer.run(ctx)

    def test_run_raises_when_file_not_matched_by_config(self, make_ctx):
        # 🔴 #1226 결함 4: flat config 의 기본 매칭은 `**/*.js|mjs|cjs` 뿐이라 `files` glob 이 없으면
        # .jsx/.ts/.tsx 가 ruleId=null 인 "File ignored" 경고 1건을 낳는다. 그 가짜 경고를 이슈로
        # 집계하면 **점수를 부당하게 깎는다**(침묵보다 나쁨). 미분석 신호이므로 fail-closed 처리.
        # 🔴 #1226 defect 4: flat config only matches js/mjs/cjs by default, so without a `files`
        # glob a .jsx/.ts/.tsx file yields a ruleId=null "File ignored" warning. Counting that bogus
        # warning as an issue wrongly deducts points — worse than silence. It signals "not analyzed".
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ignored_output = json.dumps([{
            "filePath": "/tmp/app.tsx",
            "messages": [{
                "ruleId": None, "fatal": False, "severity": 1,
                "message": "File ignored because no matching configuration was supplied.",
            }],
        }])
        ctx = make_ctx(language="typescript", filename="app.tsx", tmp_path="/tmp/app.tsx")
        analyzer = _ESLintAnalyzer()
        with patch("subprocess.run", return_value=_mock_eslint_proc(ignored_output)):
            with pytest.raises(RuntimeError):
                analyzer.run(ctx)

    def test_run_keeps_fatal_parse_error_as_issue(self, make_ctx):
        # 대비 축: fatal 파싱 오류는 ruleId 가 없어도 **분석 대상 코드의 실제 결함**이므로
        # 이슈로 보존한다 (위의 "File ignored" 메타 메시지와 구별).
        # Contrast axis: a fatal parse error has no ruleId but is a genuine defect in the analyzed
        # code, so it is kept as an issue — distinct from the "File ignored" meta message above.
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        fatal_output = json.dumps([{
            "filePath": "/tmp/broken.js",
            "messages": [{
                "ruleId": None, "fatal": True, "severity": 2,
                "message": "Parsing error: Unexpected token }", "line": 3,
            }],
        }])
        ctx = make_ctx(language="javascript", tmp_path="/tmp/broken.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(fatal_output)):
            issues = _ESLintAnalyzer().run(ctx)
        assert len(issues) == 1
        assert issues[0].severity == "error"

    def test_run_sets_category_to_code_quality(self, make_ctx):
        # 모든 ESLint 이슈의 category는 "code_quality"이어야 한다
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_MIXED)):
            issues = _ESLintAnalyzer().run(ctx)
        for issue in issues:
            assert issue.category == "code_quality"

    def test_run_sets_language_from_ctx(self, make_ctx):
        # AnalysisIssue.language는 ctx.language 값으로 설정되어야 한다
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
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
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_ERROR_ONLY)):
            issues = _ESLintAnalyzer().run(ctx)
        assert issues[0].tool == "eslint"

    def test_run_sets_line_number_from_message(self, make_ctx):
        # AnalysisIssue.line은 ESLint message의 line 필드에서 가져와야 한다
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_ERROR_ONLY)):
            issues = _ESLintAnalyzer().run(ctx)
        assert issues[0].line == 10

    def test_run_sets_message_text_from_eslint_message(self, make_ctx):
        # AnalysisIssue.message는 ESLint message 객체의 message 필드에서 가져와야 한다
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
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
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", side_effect=FileNotFoundError("eslint not found")):
            issues = _ESLintAnalyzer().run(ctx)
        assert issues == []

    def test_run_returns_empty_on_timeout_expired(self, make_ctx):
        # eslint subprocess가 TimeoutExpired → 빈 이슈 목록 반환 (파이프라인 미중단)
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="eslint", timeout=30)):
            issues = _ESLintAnalyzer().run(ctx)
        assert issues == []

    def test_run_raises_on_json_decode_error(self, make_ctx):
        # 🔴 #1226: 깨진 JSON = 분석 실패. 위 두 축(바이너리 부재·타임아웃)은 **의도적 미수행**이라
        # [] 가 맞지만, 여기는 eslint 가 실행됐는데 결과를 못 낸 **진짜 실패**라 fail-closed 다.
        # 🔴 #1226: broken JSON means the analysis failed. The two axes above (missing binary,
        # timeout) are intentional non-execution and correctly return []; this one is a genuine
        # failure of an eslint that did run, so it must fail closed.
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        analyzer = _ESLintAnalyzer()
        with patch("subprocess.run", return_value=_mock_eslint_proc("[{broken")):
            with pytest.raises(RuntimeError):
                analyzer.run(ctx)

    def test_run_raises_on_non_json_output(self, make_ctx):
        # 🔴 #1226: 이 입력("Oops, something went wrong")은 **eslint 9 가 실제로 뱉는 문구**다
        # (`Oops! Something went wrong! :(`). 즉 이 테스트는 운영 무동작 상태를 그대로 재현하면서
        # [] 를 단언해 **결함을 정상으로 인증**하고 있었다.
        # 🔴 #1226: this input is verbatim what eslint 9 actually emits (`Oops! Something went
        # wrong! :(`). The test reproduced the exact production dead-state and asserted [],
        # certifying the defect as healthy behaviour.
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        ctx = make_ctx(language="javascript", tmp_path="/tmp/app.js")
        analyzer = _ESLintAnalyzer()
        with patch("subprocess.run", return_value=_mock_eslint_proc("Oops, something went wrong")):
            with pytest.raises(RuntimeError):
                analyzer.run(ctx)


# ──────────────────────────────────────────────────────────────────────────────
# TestESLintRegistration — 모듈 로드 시 REGISTRY 자동 등록 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestESLintRegistration:
    # 🔴 `import src.analyzer.io.tools.eslint` 문 대신 `importlib.import_module` 를 쓴다 —
    #    같은 파일의 `from ...eslint import ...` 와 공존하면 CodeQL `py/import-and-import-from`
    #    을 자초하고 `scripts/check_dual_import.py` 가 신규 diff 를 차단한다
    #    (testing.md '모듈 패치 시 이중 import 회피 — string-path 우선').
    # 🔴 Use importlib.import_module instead of a bare `import <module>` statement: coexisting with
    #    `from <module> import ...` in the same file trips CodeQL py/import-and-import-from and the
    #    repo's dual-import guard.
    _MODULE = "src.analyzer.io.tools.eslint"

    def test_module_import_registers_eslint_in_registry(self):
        # src.analyzer.io.tools.eslint 임포트 시 REGISTRY에 _ESLintAnalyzer가 자동 등록된다
        import importlib
        from src.analyzer.pure.registry import REGISTRY
        importlib.reload(importlib.import_module(self._MODULE))
        names = [a.name for a in REGISTRY]
        assert "eslint" in names

    def test_double_import_does_not_duplicate_registry_entry(self):
        # 동일 모듈을 두 번 로드해도 REGISTRY에 "eslint"가 중복 등록되지 않아야 한다
        import importlib
        from src.analyzer.pure.registry import REGISTRY
        module = importlib.import_module(self._MODULE)
        importlib.reload(module)
        importlib.reload(module)
        eslint_entries = [a for a in REGISTRY if a.name == "eslint"]
        assert len(eslint_entries) == 1

    def test_eslint_analyzer_satisfies_analyzer_protocol(self):
        # _ESLintAnalyzer 인스턴스가 Analyzer Protocol을 충족하는지 검증한다
        from src.analyzer.pure.registry import Analyzer
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer
        assert isinstance(_ESLintAnalyzer(), Analyzer)


# ──────────────────────────────────────────────────────────────────────────────
# TestEslintReactSupport — JSX/TSX 파일에 React 설정 적용 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestEslintReactSupport:
    def test_jsx_file_uses_react_config(self, make_ctx):
        # .jsx 파일은 React 전용 eslint 설정(_REACT_CONFIG_PATH)을 사용해야 한다
        # .jsx files must use the React-specific eslint config (_REACT_CONFIG_PATH).
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer, _REACT_CONFIG_PATH
        ctx = make_ctx(language="javascript", filename="app.jsx", tmp_path="/tmp/app.jsx")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_NO_MESSAGES)) as mock_run:
            _ESLintAnalyzer().run(ctx)
        call_args = mock_run.call_args[0][0]
        assert _REACT_CONFIG_PATH in call_args

    def test_tsx_file_uses_react_config(self, make_ctx):
        # .tsx 파일은 React 전용 eslint 설정(_REACT_CONFIG_PATH)을 사용해야 한다
        # .tsx files must use the React-specific eslint config (_REACT_CONFIG_PATH).
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer, _REACT_CONFIG_PATH
        ctx = make_ctx(language="typescript", filename="App.tsx", tmp_path="/tmp/App.tsx")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_NO_MESSAGES)) as mock_run:
            _ESLintAnalyzer().run(ctx)
        call_args = mock_run.call_args[0][0]
        assert _REACT_CONFIG_PATH in call_args

    def test_js_file_does_not_use_react_config(self, make_ctx):
        # .js 파일은 기본 eslint 설정(_CONFIG_PATH)을 사용하고 React 설정을 사용하지 않아야 한다
        # .js files must use the base eslint config (_CONFIG_PATH), not the React config.
        from src.analyzer.io.tools.eslint import _ESLintAnalyzer, _CONFIG_PATH, _REACT_CONFIG_PATH
        ctx = make_ctx(language="javascript", filename="app.js", tmp_path="/tmp/app.js")
        with patch("subprocess.run", return_value=_mock_eslint_proc(SAMPLE_OUTPUT_NO_MESSAGES)) as mock_run:
            _ESLintAnalyzer().run(ctx)
        call_args = mock_run.call_args[0][0]
        assert _CONFIG_PATH in call_args
        assert _REACT_CONFIG_PATH not in call_args


# ──────────────────────────────────────────────────────────────────────────────
# TestEslintConfigFilesExist — 🔴 #1226 결함 1·3 회귀 가드 (mock 이 원리적으로 못 잡는 축)
#
# 이 클래스는 subprocess 를 mock 하지 않는다. 위쪽 테스트들은 전부 "argv 에 경로 문자열이
# 들어갔는가" 만 보므로, 그 경로에 **파일이 없어도 40건 전건 통과**했다 — 실제로 운영 분석기가
# 100% 무동작인 채 CI 는 초록이었다. 여기서는 파일시스템 실측만 단언한다.
#
# TestEslintConfigFilesExist — regression guard for #1226 defects 1 & 3, on the axis mocks
# structurally cannot cover. The tests above only assert that a path string reached argv, so they
# all passed while the file did not exist — the analyzer was 100% dead and CI was green. These
# assert against the real filesystem.
# ──────────────────────────────────────────────────────────────────────────────

class TestEslintConfigFilesExist:
    def test_base_config_path_points_to_existing_file(self):
        # 결함 1: `..` 1개로는 src/analyzer/io/configs/ (부재) 를 가리켰다. 실제는 `..` 2개.
        # Defect 1: a single `..` resolved to src/analyzer/io/configs/ (nonexistent); two are needed.
        from src.analyzer.io.tools.eslint import _CONFIG_PATH
        assert os.path.isfile(_CONFIG_PATH), f"eslint config not found: {_CONFIG_PATH}"

    def test_react_config_path_points_to_existing_file(self):
        from src.analyzer.io.tools.eslint import _REACT_CONFIG_PATH
        assert os.path.isfile(_REACT_CONFIG_PATH), f"eslint react config not found: {_REACT_CONFIG_PATH}"

    def test_configs_are_mjs_not_json(self):
        # 결함 3: eslint 9+ flat-config 로더는 설정을 ESM 으로 import 한다. `.json` 은
        # ERR_IMPORT_ATTRIBUTE_MISSING 으로 죽어 **경로·플래그를 고쳐도 분석기가 여전히 무동작**이었다.
        # Defect 3: the eslint 9+ flat-config loader imports the config as an ES module. A `.json`
        # file dies with ERR_IMPORT_ATTRIBUTE_MISSING, so fixing the path and flag alone left the
        # analyzer just as dead.
        from src.analyzer.io.tools.eslint import _CONFIG_PATH, _REACT_CONFIG_PATH
        assert _CONFIG_PATH.endswith(".mjs")
        assert _REACT_CONFIG_PATH.endswith(".mjs")

    def test_configs_declare_files_globs_for_every_supported_extension(self):
        # 결함 4: `files` glob 이 없으면 .jsx/.ts/.tsx 가 미매칭돼 "File ignored" 가짜 경고를 낳는다.
        # language.py 가 javascript/typescript 로 매핑하는 6개 확장자를 두 설정이 모두 덮어야 한다.
        # Defect 4: without a `files` glob, .jsx/.ts/.tsx go unmatched and produce a bogus
        # "File ignored" warning. The two configs must jointly cover all 6 extensions that
        # language.py maps to javascript/typescript.
        from src.analyzer.io.tools.eslint import _CONFIG_PATH, _REACT_CONFIG_PATH
        combined = ""
        for path in (_CONFIG_PATH, _REACT_CONFIG_PATH):
            with open(path, encoding="utf-8") as fh:
                combined += fh.read()
        for ext in (".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"):
            assert f'"**/*{ext}"' in combined, f"no files glob covers {ext}"


# ── 설정 메타 메시지 드롭 (backlog R22 · Grok 019fbaa0 실측 payload) ─────
# Config-meta messages must not be counted as code defects.


def _ctx(tmp_path):
    from src.analyzer.pure.registry import AnalyzeContext
    return AnalyzeContext(
        filename="app.js", content="", language="javascript",
        tmp_path=str(tmp_path / "app.js"), is_test=False,
    )


def test_unknown_rule_in_disable_comment_is_not_counted_as_issue(tmp_path):
    """🔴 대상 리포가 **자기 설정의 룰**로 eslint-disable 을 달면 정상 코드가 감점됐다 (R22).

    우리는 `--no-config-lookup` + 10-룰 최소 설정으로 돌린다. 그래서 eslint 는 그 룰을 모르고
    다음을 보고한다 — 🔴 `ruleId` 가 **문자열**이고 `severity=2` 라 미린트 판정(ruleId=None)에
    걸리지 않은 채 그대로 ERROR 이슈가 됐다(`score-lie` — auto-merge 까지 전파).

    payload 는 Grok claim-review `019fbaa0` 의 **eslint 9.39.5 실행 실측**이다(10.8.0 동일).
    Measured payload: unknown rule names in disable comments surface with a STRING ruleId at
    severity 2 via eslint's `createDisableDirectives` → `report.addError(...)`.
    """
    from src.analyzer.io.tools.eslint import _to_issues

    data = [{"messages": [
        {"ruleId": "some-rule-not-in-our-config", "severity": 2, "line": 1,
         "message": "Definition for rule 'some-rule-not-in-our-config' was not found."},
        {"ruleId": "no-unused-vars", "severity": 1, "line": 2,
         "message": "'x' is assigned a value but never used."},
    ]}]
    issues = _to_issues(data, _ctx(tmp_path))

    assert len(issues) == 1, f"설정 메타 메시지가 이슈로 집계됐다: {[i.message for i in issues]}"
    assert issues[0].message.startswith("'x' is assigned")
    assert all("was not found" not in i.message for i in issues)


def test_config_meta_message_does_not_mask_unlinted_file(tmp_path):
    """🔴 대조군 — 메타 드롭이 **미린트 fail-closed(#1226)를 재개방하지 않는다**.

    `ruleId=None` + 비-fatal = 파일이 린트되지 않았다는 신호이므로 여전히 raise 해야 한다.
    이 단언이 없으면 R22 수정이 #1226(JS/TS 이슈 항상 0 = 점수 인플레)을 되살릴 수 있다.
    """
    import pytest

    from src.analyzer.io.tools.eslint import _to_issues

    data = [{"messages": [
        {"ruleId": None, "severity": 1, "line": 0,
         "message": "File ignored because outside of base path."},
    ]}]
    with pytest.raises(RuntimeError, match="did not lint"):
        _to_issues(data, _ctx(tmp_path))


def test_fatal_parse_error_is_still_kept(tmp_path):
    """대조군 — fatal 은 `ruleId` 가 없어도 **분석 대상 코드의 실제 결함**이라 보존한다."""
    from src.analyzer.io.tools.eslint import _to_issues

    data = [{"messages": [
        {"ruleId": None, "fatal": True, "severity": 2, "line": 3,
         "message": "Parsing error: Unexpected token"},
    ]}]
    issues = _to_issues(data, _ctx(tmp_path))
    assert len(issues) == 1 and "Parsing error" in issues[0].message
