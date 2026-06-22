"""clippy — Rust 정적 분석기.
clippy Rust static analyzer.

단일 .rs 파일을 임시 Cargo 프로젝트에 넣어 cargo clippy를 실행한다.
Wraps a single .rs file in a temporary Cargo project and runs cargo clippy.
_ClippyAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess  # nosec B404
import tempfile

from src.analyzer.pure.registry import (
    AnalyzeContext, AnalysisIssue, Category, Severity, register,
)
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)

# 임시 Cargo 프로젝트의 최소 Cargo.toml 내용
# Minimal Cargo.toml content for the temporary Cargo project
_CARGO_TOML_TEMPLATE = (
    '[package]\nname = "tmpclippy"\nversion = "0.1.0"\nedition = "2021"\n'
)


def _build_temp_cargo_project(rs_content: str) -> str:
    """임시 Cargo 프로젝트를 만들고 .rs 내용을 src/lib.rs에 쓴다.
    Create a temporary Cargo project and write rs_content to src/lib.rs.
    """
    tmp_dir = tempfile.mkdtemp(prefix="clippy_")
    src_dir = os.path.join(tmp_dir, "src")
    os.makedirs(src_dir)
    with open(os.path.join(tmp_dir, "Cargo.toml"), "w", encoding="utf-8") as f:
        f.write(_CARGO_TOML_TEMPLATE)
    with open(os.path.join(src_dir, "lib.rs"), "w", encoding="utf-8") as f:
        f.write(rs_content)
    return tmp_dir


def _parse_clippy_line(line: str, ctx: AnalyzeContext) -> AnalysisIssue | None:
    """cargo clippy JSON 행 1개를 AnalysisIssue 로 파싱 (compiler-message 아니면 None).

    Parse one cargo clippy JSON line into an AnalysisIssue (None if not a compiler-message).
    """
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    # compiler-message 이외의 행(build-script-executed 등)은 무시
    # Skip non-compiler-message lines (e.g. build-script-executed)
    if obj.get("reason") != "compiler-message":
        return None
    msg = obj.get("message", {})
    level = msg.get("level", "warning").lower()
    severity = Severity.ERROR if level == "error" else Severity.WARNING
    spans = msg.get("spans", [{}])
    line_no = spans[0].get("line_start", 0) if spans else 0
    return AnalysisIssue(
        tool="clippy",
        severity=severity,
        message=msg.get("message", ""),
        line=line_no,
        category=Category.CODE_QUALITY,
        language=ctx.language,
    )


class _ClippyAnalyzer:
    """cargo clippy Rust 분석기 — JSONL compiler-message 파싱.
    cargo clippy Rust analyzer — parses JSONL compiler-message output.
    """

    name = "clippy"
    category = Category.CODE_QUALITY
    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"rust"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Rust 파일 여부 확인.
        Check whether the file is a Rust file.
        """
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """cargo 바이너리 설치 여부 확인.
        Check whether the cargo binary is installed.
        """
        return shutil.which("cargo") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """cargo clippy --message-format=json 출력에서 compiler-message만 파싱.
        Parse only compiler-message lines from cargo clippy --message-format=json output.
        """
        tmp_dir = None
        try:
            tmp_dir = _build_temp_cargo_project(ctx.content)
            r = subprocess.run(  # nosec B603 B607
                ["cargo", "clippy", "--message-format=json", "--quiet"],
                capture_output=True, text=True,
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
                cwd=tmp_dir,
            )
            issues = []
            for line in (r.stdout or "").splitlines():
                issue = _parse_clippy_line(line, ctx)
                if issue is not None:
                    issues.append(issue)
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("clippy timed out for %s", ctx.tmp_path)
            return []
        except OSError as exc:
            logger.warning("clippy failed for %s: %s", ctx.tmp_path, exc)
            return []
        finally:
            # 임시 Cargo 프로젝트 정리 — OSError는 무시
            # Clean up temporary Cargo project — ignore OSError
            if tmp_dir and os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)


register(_ClippyAnalyzer())
