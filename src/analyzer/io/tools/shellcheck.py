"""ShellCheck static analysis tool — Shell 스크립트 코드 품질 분석.

_ShellCheckAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
shellcheck 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess  # nosec B404

from src.analyzer.io.tools._common import analysis_failed, empty_output_is_a_crash
from src.analyzer.pure.registry import AnalyzeContext, AnalysisIssue, Category, Severity, register
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)


class _ShellCheckAnalyzer:
    name = "shellcheck"
    category = Category.CODE_QUALITY

    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"shell"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Shell 파일 여부 확인."""
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """shellcheck 바이너리 설치 여부 확인."""
        return shutil.which("shellcheck") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """shellcheck JSON 출력을 파싱해 이슈 목록 반환."""
        try:
            r = subprocess.run(  # nosec B603 B607
                ["shellcheck", "-f", "json", ctx.tmp_path],
                capture_output=True, text=True, timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            # 🔴 **stdout 모양은 판별식이 될 수 없다** — CI 실바이너리 실측
            #    (#1580 `W2-SHAPE`): 없는 경로에서 exit=2 인데 stdout 은 `[]` 로
            #    깨끗과 **바이트가 같다**. cppcheck·hadolint 와 다른 부류다.
            #      깨끗  exit=0 · `[]`      발견  exit=1 · JSON      크래시  exit=2 · `[]`
            #    그래서 「읽어 낸 이슈 0건 + 비정상 종료」로 가른다(공용 헬퍼).
            #    발견이 있으면 `issues` 가 비지 않아 헬퍼가 False 다 — 평범한 PR 은 막히지 않고,
            #    프로덕션은 `static.py` 가 파일을 먼저 쓰므로 exit=2 가 정상 입력에서 안 나온다.
            # Measured: the crash stdout is byte-identical to the clean stdout.
            raw = r.stdout.strip()
            data = json.loads(raw) if raw else []
            issues = []
            for item in data:
                level = item.get("level", "warning")
                severity = Severity.ERROR if level.lower() == "error" else Severity.WARNING
                issues.append(AnalysisIssue(
                    tool="shellcheck",
                    severity=severity,
                    message=item.get("message", ""),
                    line=item.get("line", 0),
                    category=Category.CODE_QUALITY,
                    language=ctx.language,
                ))
            if empty_output_is_a_crash(issues, r):
                raise analysis_failed(
                    "shellcheck", ctx, r, "produced no findings and exited nonzero")
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("shellcheck timed out for %s", ctx.tmp_path)
            return []
        except FileNotFoundError as exc:
            # which() 통과 뒤 사라진 바이너리 — 조달 축(`unavailable_tools`)이 담당한다.
            # 그 밖의 OSError(깨진 shebang · 권한)는 미분석이므로 올라간다.
            # A binary that vanished after the which() gate; procurement owns it.
            logger.warning("shellcheck unavailable for %s: %s", ctx.tmp_path, exc)
            return []
        except json.JSONDecodeError as exc:
            # 무언가를 냈는데 읽을 수 없다 = 미분석이다.
            # Output we cannot read is unanalyzed, not clean.
            raise analysis_failed(
                "shellcheck", ctx, r, "produced output this adapter cannot read") from exc


def _register_shellcheck_analyzers() -> None:
    register(_ShellCheckAnalyzer())


_register_shellcheck_analyzers()
