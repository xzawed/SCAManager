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
from src.analyzer.io.tools._common import analysis_failed
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



def _parse_clippy_json(line: str) -> bool:
    """이 줄이 JSONL 로 읽히는가 — 읽힌 **내용**이 아니라 읽혔는지만 본다.

    `_parse_clippy_line` 은 「compiler-message 가 아니면 None」도 돌려주므로 그것만으로는
    「깨진 출력」과 「깨끗한 빌드」를 가를 수 없다. 이 함수가 그 둘을 가른다.
    Did this line parse as JSON at all — regardless of what it contained.
    """
    try:
        json.loads(line)
        return True
    except json.JSONDecodeError:
        return False


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
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
                cwd=tmp_dir,
            )
            # 🔴 exit code 는 판별식이 **아니다** — 실측(clippy 0.1.97, 임시 cargo 프로젝트):
            #      깨끗 · 린트 있음        exit=0   · stdout **비지 않음**(compiler-artifact ·
            #                                        build-finished. 줄 수는 캐시 상태에 따라 다르다)
            #      컴파일 오류(정당한 발견)  exit=**101** · stdout **비지 않음**
            #      Cargo.toml 없음(크래시)  exit=**101** · stdout **0줄**
            #    정당한 컴파일 오류와 크래시가 같은 exit 을 낸다. 줄 수도 세지 않는다 —
            #    불변식은 「성공하면 무언가를 낸다」 하나이므로 판별식은 **빈 stdout** 이다.
            # Measured: a legitimate compile error and a crash share exit 101; line counts vary
            # with cache state; only emptiness separates them.
            if not (r.stdout or "").strip():
                raise analysis_failed("clippy", ctx, r, "produced no output")
            issues = []
            parsed_any = False
            for line in (r.stdout or "").splitlines():
                if not line.strip():
                    continue
                parsed_any = _parse_clippy_json(line) or parsed_any
                issue = _parse_clippy_line(line, ctx)
                if issue is not None:
                    issues.append(issue)
            # 🔴 stdout 이 **비어 있지 않은데** 한 줄도 JSONL 로 읽히지 않았다 = 미분석이다.
            #    위 빈-stdout 가드는 이 입력을 건드리지 않는다(내용은 있으니까). 그래서
            #    깨진 출력이 그대로 「이슈 0건 · 깨끗함」이 됐다 — `_parse_clippy_line` 이
            #    `json.JSONDecodeError` 를 `None` 으로 삼키기 때문이다(조용한 누산기).
            #    실측: 재고 탐지기 축 C 가 이 자리를 지목했고, 축 A·B 는 못 봤다.
            #    🔴 「JSONL 은 읽혔는데 compiler-message 가 0건」은 **정상**이다 —
            #    깨끗한 빌드가 그렇다(compiler-artifact · build-finished 만 나온다).
            #    그래서 판별식은 「이슈 0건」이 아니라 「**읽어 낸 JSON 0건**」이다.
            # Non-empty stdout that yields no parsable JSONL at all is unanalyzed; zero
            # compiler-messages with valid JSONL is a clean build and must stay clean.
            if not parsed_any:
                raise analysis_failed(
                    "clippy", ctx, r, "produced output that is not JSONL")
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("clippy timed out for %s", ctx.tmp_path)
            return []
        except FileNotFoundError as exc:
            # which() 통과 뒤 사라진 바이너리 — 조달 축(`unavailable_tools`)이 담당한다.
            # 그 밖의 OSError(깨진 shebang · 권한)는 미분석이므로 올라간다.
            # A binary that vanished after the which() gate; procurement owns it.
            logger.warning("clippy unavailable for %s: %s", ctx.tmp_path, exc)
            return []
        finally:
            # 임시 Cargo 프로젝트 정리 — OSError는 무시
            # Clean up temporary Cargo project — ignore OSError
            if tmp_dir and os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)


register(_ClippyAnalyzer())
