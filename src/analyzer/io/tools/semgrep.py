"""Semgrep static analysis tool — 30+ 언어 baseline 정적분석.

_SemgrepAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
semgrep 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess  # nosec B404

from src.analyzer.pure.registry import AnalyzeContext, AnalysisIssue, Category, Severity, register
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)

_ERR_EXCERPT = 200


def _fail(ctx, r) -> RuntimeError:
    """실패를 예외로 만든다 — `static.py` 는 `run()` 이 **올릴 때만** `incomplete` 로 승격한다.

    🔴 `[]` 를 돌려주면 그 실패가 «이슈 0건 · 완전» 이 되어 미분석 코드가 auto-merge 된다.
    semgrep 은 java·scala·elixir·clojure 의 **유일한** 분석기라 그 언어에서는 대체 관측면도
    없다(실측). 형제 `python.py::_fail` 과 같은 관용구다.

    Returning [] would record the failure as a clean, complete run; semgrep is the only
    analyzer for four languages, so nothing else would notice.
    """
    detail = str(getattr(r, "stderr", "") or r.stdout or "").strip()[:_ERR_EXCERPT]
    return RuntimeError(
        f"semgrep did not analyze {ctx.tmp_path} (exit={r.returncode}): {detail}"
    )


class _SemgrepAnalyzer:
    name = "semgrep"
    category = Category.CODE_QUALITY
    # 🔴 **범용 대체 관측면** — 한 언어의 전담 분석기가 아니라 22개 언어의 폭넓은 fallback 이다.
    #    그래서 「전담 관측면이 돌았는가」를 셀 때 이것은 세지 않는다
    #    (`static.py::no_dedicated_observer`). 규칙 밀도가 언어마다 크게 다르므로
    #    (자체 보고: elixir 0 · cpp 0 · swift 2 · rust 4) semgrep 이 돌았다는 사실만으로
    #    그 언어를 봤다고 말할 수 없다 — 그 판단이 이 표식의 이유다.
    # The generic multi-language fallback: running it does not mean the language was observed.
    is_generic = True

    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({
        # Tier 1
        "python", "javascript", "typescript", "java", "go", "rust",
        "c", "cpp", "csharp", "ruby",
        # Tier 2
        "php", "scala", "kotlin", "swift", "elixir",
        "clojure", "solidity", "shell", "dockerfile",
        # Config / Markup
        "yaml", "html", "terraform",
    })

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Semgrep 지원 언어 여부 확인."""
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """semgrep 바이너리 설치 여부 확인."""
        return shutil.which("semgrep") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """semgrep p/default 룰셋으로 분석 후 이슈 목록 반환.
        Analyze with semgrep p/default ruleset and return issue list.
        """
        try:
            r = subprocess.run(  # nosec B603 B607
                ["semgrep", "scan", "--config=p/default", "--json",
                 "--timeout", str(STATIC_ANALYSIS_TIMEOUT), ctx.tmp_path],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            # 🔴 stdout 이 JSON 이 아니면 semgrep 이 **분석하지 않은** 것이다.
            # `--json` 의 정상 «이슈 없음» 도 `{"results": []}` 라 `{` 로 시작한다 —
            # 비-`{` 가 정당한 «이슈 0건» 인 경우는 없다.
            # Non-JSON stdout means semgrep did not analyze; a clean --json run still
            # starts with '{'.
            if not r.stdout.strip().startswith("{"):
                raise _fail(ctx, r)
            try:
                data = json.loads(r.stdout)
            except json.JSONDecodeError as exc:
                raise _fail(ctx, r) from exc
            issues = []
            for item in data.get("results", []):
                extra = item.get("extra", {})
                metadata = extra.get("metadata", {})
                raw_severity = extra.get("severity", "WARNING").upper()
                severity = Severity.ERROR if raw_severity == "ERROR" else Severity.WARNING
                category = (
                    Category.SECURITY
                    if metadata.get("category") == "security"
                    else Category.CODE_QUALITY
                )
                issues.append(AnalysisIssue(
                    tool="semgrep",
                    severity=severity,
                    message=extra.get("message", item.get("check_id", "")),
                    line=item.get("start", {}).get("line", 0),
                    category=category,
                    language=ctx.language,
                ))
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("semgrep timed out for %s", ctx.tmp_path)
            return []
        except FileNotFoundError as exc:
            # 바이너리 부재 — 크래시와 **다른 축**이다. `static.py` 가
            # `unavailable_tools` 로 따로 보고하므로 여기서 예외로 올리지 않는다.
            # Missing binary is reported separately via unavailable_tools.
            logger.warning("semgrep binary missing for %s: %s", ctx.tmp_path, exc)
            return []


def _register_semgrep_analyzers() -> None:
    register(_SemgrepAnalyzer())


_register_semgrep_analyzers()
