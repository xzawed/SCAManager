"""golangci-lint static analysis tool — Go 전용 메타 정적분석 (Phase D.4).

_GolangciLintAnalyzer 는 Analyzer Protocol 을 구현하며 registry.register() 로 등록된다.
golangci-lint 바이너리가 없으면 is_enabled() 가 False 를 반환해 조용히 skip 된다.

Go 특유의 요구사항: golangci-lint 는 Go 모듈(`go.mod`) 안에서만 동작한다. 단일
`.go` 파일을 tmp_path 로 받으면 주변에 `go.mod` 가 없어 "no Go files" 오류가 난다.
→ run() 내부에서 tmp_path 디렉토리에 최소 go.mod (`module tempmod\ngo 1.21\n`) 를
자동 생성한다 (존재하지 않을 때만).

FromLinter 기준 severity / category 매핑:
  - gosec / gas → Severity.ERROR + Category.SECURITY
  - 그 외 (errcheck / govet / staticcheck / unused ...) → Severity.WARNING + Category.CODE_QUALITY
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess  # nosec B404

from src.analyzer.pure.registry import AnalyzeContext, AnalysisIssue, Category, Severity, register
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)

_SECURITY_LINTERS: frozenset[str] = frozenset({"gosec", "gas"})

# golangci-lint 가 Go 모듈 없이는 동작 안 하므로 최소 go.mod 를 자동 생성한다.
_MIN_GO_MOD = "module tempmod\n\ngo 1.21\n"


class _GolangciLintAnalyzer:
    name = "golangci-lint"
    category = Category.CODE_QUALITY  # 기본, gosec 만 override

    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"go"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Go 파일 여부 확인."""
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """golangci-lint 바이너리 설치 여부 확인."""
        return shutil.which("golangci-lint") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """golangci-lint JSON 출력을 파싱해 이슈 목록 반환.

        tmp_path 디렉토리에 go.mod 가 없으면 최소 모듈 정의를 자동 생성한다.
        """
        work_dir = os.path.dirname(ctx.tmp_path) or "."
        _ensure_go_mod(work_dir)
        try:
            r = subprocess.run(  # nosec B603 B607
                ["golangci-lint", "run", "--out-format", "json", ctx.tmp_path],
                capture_output=True, text=True,
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
                cwd=work_dir,
            )
            if not r.stdout.strip():
                return []
            return _parse_golangci_json(r.stdout, ctx.language)
        except subprocess.TimeoutExpired:
            logger.warning("golangci-lint timed out for %s", ctx.tmp_path)
            return []
        except (OSError, json.JSONDecodeError, ValueError,
                AttributeError, TypeError) as exc:
            logger.warning("golangci-lint failed for %s: %s", ctx.tmp_path, exc)
            return []


def _ensure_go_mod(dir_path: str) -> None:
    """dir_path 에 go.mod 가 없으면 최소 모듈 정의를 생성한다."""
    go_mod = os.path.join(dir_path, "go.mod")
    if os.path.exists(go_mod):
        return
    try:
        with open(go_mod, "w", encoding="utf-8") as f:
            f.write(_MIN_GO_MOD)
    except OSError as exc:
        logger.warning("go.mod 자동생성 실패 (%s): %s", dir_path, exc)


def _map_severity(from_linter: str) -> Severity:
    """FromLinter 기준 severity 매핑 — gosec 계열은 ERROR, 나머지는 WARNING."""
    return Severity.ERROR if from_linter in _SECURITY_LINTERS else Severity.WARNING


def _map_category(from_linter: str) -> Category:
    """FromLinter 기준 category 매핑 — gosec 계열은 SECURITY, 나머지는 CODE_QUALITY."""
    return Category.SECURITY if from_linter in _SECURITY_LINTERS else Category.CODE_QUALITY


def _parse_golangci_json(json_text: str, language: str) -> list[AnalysisIssue]:
    """golangci-lint JSON 결과를 AnalysisIssue 목록으로 변환한다.

    subprocess mock 없이 JSON 픽스처만으로 검증 가능하도록 분리된 모듈 레벨 함수.
    """
    data = json.loads(json_text)
    raw_issues = data.get("Issues", []) or []
    issues: list[AnalysisIssue] = []
    for item in raw_issues:
        from_linter = item.get("FromLinter", "")
        pos = item.get("Pos", {}) or {}
        issues.append(AnalysisIssue(
            tool="golangci-lint",
            severity=_map_severity(from_linter),
            message=item.get("Text", "").strip() or from_linter,
            line=int(pos.get("Line", 0) or 0),
            category=_map_category(from_linter),
            language=language,
        ))
    return issues


def _register_golangci_lint_analyzers() -> None:
    register(_GolangciLintAnalyzer())


_register_golangci_lint_analyzers()
