"""Static code analysis — runs registered analyzers on source files via Registry."""
import logging
import os
import tempfile
from dataclasses import dataclass, field

from src.analyzer.language import detect_language, is_test_file

logger = logging.getLogger(__name__)


@dataclass
class AnalysisIssue:
    """A single issue reported by a static analysis tool."""

    tool: str
    severity: str       # "error" | "warning"
    message: str
    line: int = 0
    category: str = "code_quality"  # "code_quality" | "security"
    language: str = ""              # detect_language() 반환값


@dataclass
class StaticAnalysisResult:
    """Aggregated static analysis result for one source file."""

    filename: str
    issues: list[AnalysisIssue] = field(default_factory=list)


def analyze_file(filename: str, content: str) -> StaticAnalysisResult:
    """Run all applicable registered analyzers on a single file."""
    if not content.strip():
        return StaticAnalysisResult(filename=filename)

    from src.analyzer.registry import REGISTRY, AnalyzeContext  # noqa: PLC0415
    import src.analyzer.tools.python  # noqa: PLC0415,F401 — 모듈 로드 시 자동 등록

    language = detect_language(filename, content)
    is_test = is_test_file(filename, language)

    result = StaticAnalysisResult(filename=filename)

    # Python 도구는 .py 확장자를 임시 파일에 써야 올바르게 작동
    suffix = ".py" if language == "python" else os.path.splitext(filename)[1] or ".tmp"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        ctx = AnalyzeContext(
            filename=filename,
            content=content,
            language=language,
            is_test=is_test,
            tmp_path=tmp_path,
        )
        for analyzer in REGISTRY:
            if analyzer.supports(ctx) and analyzer.is_enabled(ctx):
                result.issues.extend(analyzer.run(ctx))
    finally:
        os.unlink(tmp_path)

    return result


# ── 하위 호환 re-export (기존 코드가 static.py에서 직접 import 하는 경우 지원) ──

def _is_test_file(filename: str, language: str = "python") -> bool:
    """Deprecated: use is_test_file() from src.analyzer.language. Kept for backward compatibility."""
    return is_test_file(filename, language)

def _run_pylint(path: str, is_test: bool = False) -> list[AnalysisIssue]:
    """Deprecated: use Registry pattern. Kept for backward compatibility."""
    from src.analyzer.tools.python import _PylintAnalyzer  # noqa: PLC0415
    from src.analyzer.registry import AnalyzeContext  # noqa: PLC0415
    ctx = AnalyzeContext(filename=path, content="", language="python",
                         is_test=is_test, tmp_path=path)
    return _PylintAnalyzer().run(ctx)


def _run_flake8(path: str, is_test: bool = False) -> list[AnalysisIssue]:
    """Deprecated: use Registry pattern. Kept for backward compatibility."""
    from src.analyzer.tools.python import _Flake8Analyzer  # noqa: PLC0415
    from src.analyzer.registry import AnalyzeContext  # noqa: PLC0415
    ctx = AnalyzeContext(filename=path, content="", language="python",
                         is_test=is_test, tmp_path=path)
    return _Flake8Analyzer().run(ctx)


def _run_bandit(path: str) -> list[AnalysisIssue]:
    """Deprecated: use Registry pattern. Kept for backward compatibility."""
    from src.analyzer.tools.python import _BanditAnalyzer  # noqa: PLC0415
    from src.analyzer.registry import AnalyzeContext  # noqa: PLC0415
    ctx = AnalyzeContext(filename=path, content="", language="python",
                         is_test=False, tmp_path=path)
    return _BanditAnalyzer().run(ctx)
