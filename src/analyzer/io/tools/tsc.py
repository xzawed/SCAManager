"""tsc — TypeScript 타입체크 분석기.
tsc TypeScript type-checker analyzer.

_TscAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
tsc 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
"""
from __future__ import annotations

import logging
import re
import shutil
import subprocess  # nosec B404

from src.analyzer.pure.registry import (
    AnalyzeContext, AnalysisIssue, Category, Severity, register,
)
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)

# tsc 출력 형식: /path/file.ts(LINE,COL): error|warning TSxxxx: message
# tsc output format: /path/file.ts(LINE,COL): error|warning TSxxxx: message
# 실패 사유 발췌 길이 — eslint.py 와 동일 값(로그·예외 메시지 폭주 방지).
# Failure-reason excerpt length; mirrors eslint.py.
_ERR_EXCERPT = 200

_TSC_DIAG_RE = re.compile(
    r'^[^\n(]+\((\d+),\d+\):\s+(error|warning)\s+TS\d+:[ \t]+(\S[^\n]*)$',
    re.MULTILINE,
)


class _TscAnalyzer:
    """TypeScript 타입체크 분석기 — tsc --noEmit 실행 후 진단 파싱.
    TypeScript type-checker — runs tsc --noEmit and parses diagnostics.
    """

    name = "tsc"
    category = Category.CODE_QUALITY

    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"typescript"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """TypeScript 파일 여부 확인.
        Check whether the file is a TypeScript file.
        """
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """tsc 바이너리 설치 여부 확인.
        Check whether the tsc binary is installed.
        """
        return shutil.which("tsc") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """tsc 진단 출력을 파싱해 AnalysisIssue 목록 반환.
        Parse tsc diagnostic output and return AnalysisIssue list.
        """
        # .tsx 파일은 React JSX 컴파일 플래그 추가
        # Add React JSX compile flag for .tsx files
        jsx_flag = ["--jsx", "react"] if ctx.filename.endswith(".tsx") else []
        try:
            r = subprocess.run(  # nosec B603 B607
                [
                    "tsc", "--noEmit", "--strict", "--skipLibCheck",
                    "--lib", "dom,es2020", "--target", "es2020",
                    "--module", "esnext",
                    "--allowJs",
                ] + jsx_flag + [ctx.tmp_path],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            output = r.stderr or r.stdout
            issues = []
            for m in _TSC_DIAG_RE.finditer(output):
                line_no = int(m.group(1))
                level = m.group(2)
                message = m.group(3).strip()
                severity = Severity.ERROR if level == "error" else Severity.WARNING
                issues.append(AnalysisIssue(
                    tool="tsc",
                    severity=severity,
                    message=message,
                    line=line_no,
                    category=Category.CODE_QUALITY,
                    language=ctx.language,
                ))
            # 🔴 fail-closed (#1238, #1226 동일 클래스) — tsc 가 **비정상 종료했는데 진단을 하나도
            # 파싱하지 못했으면** 무슨 일이 났는지 모르는 상태다. 이때 `[]` 를 반환하면 "분석했더니
            # 깨끗함" 과 구별되지 않아 정적 만점 → 점수 인플레 → auto-merge 로 전파된다.
            # 실측(2026-07-31): 정상=exit 0 · 타입오류=exit 2(+진단 매치) · **무효 플래그=exit 1 이고
            # 출력이 `error TS5023: Unknown compiler option '--x'.` 라 `file(line,col):` 접두가 없어
            # 정규식에 안 걸린다** → 조용히 `[]`. major 버전 drift 로 플래그가 바뀌면 그대로 재현된다
            # (`railway.toml` 은 `npm install -g typescript` 를 **버전 핀 없이** 설치한다).
            # exit 0 + 진단 0 = 진짜 깨끗함이므로 raise 하지 않는다(정상 경로 보존).
            # 🔴 Fail-closed: a non-zero exit with ZERO parsed diagnostics means we do not know what
            # happened; returning [] would be indistinguishable from "analyzed, clean" and inflate the
            # score. exit 0 + no diagnostics is genuinely clean and is left alone.
            if r.returncode != 0 and not issues:
                raise RuntimeError(
                    f"tsc produced no parsable diagnostics for {ctx.tmp_path} "
                    f"(exit={r.returncode}): {output.strip()[:_ERR_EXCERPT]}"
                )
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("tsc timed out for %s", ctx.tmp_path)
            return []
        except FileNotFoundError as exc:
            # which() 통과 뒤 사라진 바이너리 — 조달 축(`unavailable_tools`)이 담당한다.
            # 그 밖의 OSError(깨진 shebang · 권한)는 미분석이므로 올라간다.
            # A binary that vanished after the which() gate; procurement owns it.
            logger.warning("tsc unavailable for %s: %s", ctx.tmp_path, exc)
            return []


def _register_tsc_analyzers() -> None:
    register(_TscAnalyzer())


_register_tsc_analyzers()
