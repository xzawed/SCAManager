"""Static code analysis — runs registered analyzers on source files via Registry."""
import logging
import os
import re
import tempfile
from dataclasses import dataclass, field

import src.analyzer.io.tools.clippy  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.cppcheck  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.eslint  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.golangci_lint  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.hadolint  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.htmlhint  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.ktlint  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.phpstan  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.python  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.rubocop  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.semgrep  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.shellcheck  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.slither  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.sqlfluff  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.stylelint  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.swiftlint  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.tflint  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.tsc  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
import src.analyzer.io.tools.yamllint  # noqa: F401 — 모듈 로드 시 자동 등록  # pylint: disable=unused-import
from src.analyzer.pure.language import detect_language, is_test_file
from src.analyzer.pure.registry import REGISTRY, AnalyzeContext, AnalysisIssue
from src.analyzer.io.tools.python import _BanditAnalyzer, _Flake8Analyzer, _PylintAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class StaticAnalysisResult:
    """Aggregated static analysis result for one source file."""

    filename: str
    issues: list[AnalysisIssue] = field(default_factory=list)


def analyze_file(
    filename: str, content: str, repo_config: object | None = None
) -> StaticAnalysisResult:
    """Run all applicable registered analyzers on a single file.

    repo_config: RepoConfig ORM 인스턴스 또는 disabled_tools 속성을 가진 객체 (선택).
    repo_config: RepoConfig ORM instance or any object with disabled_tools attribute (optional).
    repo_config.disabled_tools 에 포함된 analyzer는 스킵된다.
    Analyzers whose name appears in repo_config.disabled_tools are skipped.
    """
    if not content.strip():
        return StaticAnalysisResult(filename=filename)

    language = detect_language(filename, content)
    is_test = is_test_file(filename, language)

    result = StaticAnalysisResult(filename=filename)

    # Python 도구는 .py 확장자를 임시 파일에 써야 올바르게 작동
    # Python tools require the .py extension on the temp file to function correctly.
    # 확장자 정제: 최대 10자, 영숫자·점·하이픈만 허용 — 경로 탐색/확장자 인젝션 방지
    # Sanitise extension: max 10 chars, alphanumeric/dot/hyphen only — prevent path traversal.
    raw_ext = os.path.splitext(filename)[1]
    safe_ext = re.sub(r"[^a-zA-Z0-9._-]", "", raw_ext)[:10] or ".tmp"
    suffix = ".py" if language == "python" else safe_ext

    # TemporaryDirectory 사용 — delete=False + 수동 unlink 방식의 TOCTOU 경합 조건을 제거.
    # Use TemporaryDirectory to eliminate the TOCTOU race condition present with
    # NamedTemporaryFile(delete=False) + manual os.unlink().
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = os.path.join(tmpdir, f"analyze{suffix}")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)

        ctx = AnalyzeContext(
            filename=filename,
            content=content,
            language=language,
            is_test=is_test,
            tmp_path=tmp_path,
            repo_config=repo_config,
        )
        # per-repo 비활성화 도구 목록 — 루프 외부에서 한 번만 조회
        # Fetch disabled tools list once before the loop
        _disabled = getattr(ctx.repo_config, 'disabled_tools', None) or []
        for analyzer in REGISTRY:
            if not analyzer.supports(ctx):
                continue
            if not analyzer.is_enabled(ctx):
                continue
            if analyzer.name in _disabled:
                continue
            try:
                result.issues.extend(analyzer.run(ctx))
            except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                logger.warning("analyzer %s failed for %s: %s", analyzer.name, ctx.filename, exc)

    return result


# ── 하위 호환 re-export (기존 코드가 static.py에서 직접 import 하는 경우 지원) ──

def _is_test_file(filename: str, language: str = "python") -> bool:
    """Deprecated: use is_test_file() from src.analyzer.pure.language. Kept for backward compatibility."""
    return is_test_file(filename, language)


def _run_pylint(path: str, is_test: bool = False) -> list[AnalysisIssue]:
    """Deprecated: use Registry pattern. Kept for backward compatibility."""
    ctx = AnalyzeContext(filename=path, content="", language="python",
                         is_test=is_test, tmp_path=path)
    return _PylintAnalyzer().run(ctx)


def _run_flake8(path: str, is_test: bool = False) -> list[AnalysisIssue]:
    """Deprecated: use Registry pattern. Kept for backward compatibility."""
    ctx = AnalyzeContext(filename=path, content="", language="python",
                         is_test=is_test, tmp_path=path)
    return _Flake8Analyzer().run(ctx)


def _run_bandit(path: str) -> list[AnalysisIssue]:
    """Deprecated: use Registry pattern. Kept for backward compatibility."""
    ctx = AnalyzeContext(filename=path, content="", language="python",
                         is_test=False, tmp_path=path)
    return _BanditAnalyzer().run(ctx)
