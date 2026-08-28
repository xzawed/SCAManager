"""buf_lint — Protobuf 정적 분석기.
buf_lint Protobuf static analyzer.

_BufLintAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
buf 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess  # nosec B404

from src.analyzer.pure.registry import (
    AnalyzeContext, AnalysisIssue, Category, Severity, register,
)
from src.analyzer.io.tools._common import analysis_failed, empty_output_is_a_crash
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)


class _BufLintAnalyzer:
    """buf lint Protobuf 분석기 — JSONL 출력 파싱.
    buf lint Protobuf analyzer — parses JSONL output.
    """

    name = "buf_lint"
    category = Category.CODE_QUALITY
    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"protobuf"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Protobuf 파일 여부 확인.
        Check whether the file is a Protobuf file.
        """
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """buf 바이너리 설치 여부 확인.
        Check whether the buf binary is installed.
        """
        return shutil.which("buf") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """buf lint --error-format=json 출력(JSONL)을 파싱해 이슈 반환.
        Parse buf lint --error-format=json (JSONL) output and return issues.
        """
        try:
            r = subprocess.run(  # nosec B603 B607
                ["buf", "lint", "--error-format=json", ctx.tmp_path],
                capture_output=True, text=True,
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            issues = []
            # buf는 JSONL 형식으로 한 줄에 JSON 객체 하나씩 출력
            # buf outputs JSONL: one JSON object per line
            for line in r.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    # 🔴 건너뛰면 그 줄이 들고 있던 이슈가 조용히 사라진다.
                    #    Skipping would silently drop whatever that line reported.
                    raise analysis_failed(
                        "buf_lint", ctx, r, "produced a malformed JSONL line") from exc
                issues.append(AnalysisIssue(
                    tool="buf_lint",
                    severity=Severity.WARNING,
                    message=obj.get("message", ""),
                    line=obj.get("start_line", 0),
                    category=Category.CODE_QUALITY,
                    language=ctx.language,
                ))
            if empty_output_is_a_crash(issues, r):
                # buf 는 JSONL 이라 깨끗하면 빈 출력이다 — 빈 출력 자체는 실패가 아니다.
                # 아무것도 못 읽었는데 비정상 종료일 때만 미분석으로 본다.
                raise analysis_failed("buf_lint", ctx, r, "produced no output")
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("buf_lint timed out for %s", ctx.tmp_path)
            return []
        except FileNotFoundError as exc:
            # which() 통과 뒤 사라진 바이너리 — 조달 축이 담당한다.
            # 그 밖의 OSError(깨진 shebang · 권한)는 미분석이므로 올라간다.
            logger.warning("buf_lint unavailable for %s: %s", ctx.tmp_path, exc)
            return []


register(_BufLintAnalyzer())
