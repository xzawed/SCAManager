"""hadolint — Dockerfile 정적 분석기.
hadolint Dockerfile linter.

_HadolintAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
hadolint 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess  # nosec B404

from src.analyzer.io.tools._common import analysis_failed
from src.analyzer.pure.registry import (
    AnalyzeContext, AnalysisIssue, Category, Severity, register,
)
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)


class _HadolintAnalyzer:
    """hadolint Dockerfile 분석기 — JSON 출력 파싱.
    hadolint Dockerfile analyzer — parses JSON output.
    """

    name = "hadolint"
    category = Category.CODE_QUALITY
    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"dockerfile"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Dockerfile 언어 여부 확인.
        Check whether the file is a Dockerfile.
        """
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """hadolint 바이너리 설치 여부 확인.
        Check whether the hadolint binary is installed.
        """
        return shutil.which("hadolint") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """hadolint --format=json 출력을 파싱해 이슈 반환.
        Parse hadolint --format=json output and return issues.
        """
        try:
            r = subprocess.run(  # nosec B603 B607
                ["hadolint", "--format=json", ctx.tmp_path],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            raw = r.stdout.strip()
            # 🔴 **성공하면 항상 JSON 배열을 낸다** — 깨끗해도 `[]` 다. 그래서 빈 stdout 이
            #    판별식이다. CI 실바이너리 실측(#1580 `W2-SHAPE`):
            #      깨끗              exit=0 · stdout `[]`
            #      깨진 Dockerfile   exit=1 · stdout JSON + `DL1000`  ← **발견**이다
            #      없는 경로(크래시) exit=1 · stdout **0자** · stderr `withBinaryFile: …`
            #    exit code 는 판별식이 아니다 — 발견도 크래시도 exit=1 이다.
            # Measured: a successful run always emits a JSON array, `[]` when clean.
            if not raw:
                raise analysis_failed("hadolint", ctx, r, "produced no output")
            data = json.loads(raw)
            issues = []
            for item in data:
                level = item.get("level", "warning").lower()
                severity = Severity.ERROR if level == "error" else Severity.WARNING
                issues.append(AnalysisIssue(
                    tool="hadolint",
                    severity=severity,
                    message=f"{item.get('code', '')}: {item.get('message', '')}",
                    line=item.get("line", 0),
                    category=Category.CODE_QUALITY,
                    language=ctx.language,
                ))
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("hadolint timed out for %s", ctx.tmp_path)
            return []
        except FileNotFoundError as exc:
            # which() 통과 뒤 사라진 바이너리 — 조달 축이 담당한다.
            # A binary that vanished after the which() gate; procurement owns it.
            logger.warning("hadolint unavailable for %s: %s", ctx.tmp_path, exc)
            return []
        except (json.JSONDecodeError, KeyError) as exc:
            # 무언가를 냈는데 읽을 수 없다 = 미분석이다 — 조용히 `[]` 로 흘리지 않는다.
            # Output we cannot read is unanalyzed, not clean.
            raise analysis_failed(
                "hadolint", ctx, r, "produced output this adapter cannot read") from exc


register(_HadolintAnalyzer())
