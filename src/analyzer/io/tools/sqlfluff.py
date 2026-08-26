"""sqlfluff — SQL 정적 분석기.
sqlfluff SQL static analyzer.

_SqlfluffAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
sqlfluff 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess  # nosec B404

from src.analyzer.pure.registry import (
    AnalyzeContext, AnalysisIssue, Category, Severity, register,
)
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)

_ERR_EXCERPT = 200


def _fail(ctx, r) -> RuntimeError:
    """실패를 예외로 만든다 — `static.py` 는 `run()` 이 **올릴 때만** `incomplete` 로 승격한다.

    🔴 `[]` 를 돌려주면 그 실패가 «이슈 0건 · 완전» 이 되어 미분석 코드가 auto-merge 된다.
    `sql` 은 provisioned 분석기가 sqlfluff **하나뿐인 유일한 언어**라(실측, #1521)
    여기서 삼킨 실패에는 대체 관측면이 없다. 형제 `semgrep.py::_fail` 과 같은 관용구다.

    Returning [] would record the failure as a clean, complete run; sqlfluff is the only
    provisioned analyzer for SQL, so nothing else would notice.
    """
    detail = str(getattr(r, "stderr", "") or r.stdout or "").strip()[:_ERR_EXCERPT]
    return RuntimeError(
        f"sqlfluff did not analyze {ctx.tmp_path} (exit={r.returncode}): {detail}"
    )


def _violation_line(violation: dict) -> int:
    """위반의 줄번호 — sqlfluff 3.0 이 `line_no` 를 `start_line_no` 로 바꿨다.

    🔴 핀은 `sqlfluff==4.3.0` 이라 실물 키는 `start_line_no` 다(실측: 4.2.2 출력).
    `line_no` 만 읽던 동안 **모든 sqlfluff 이슈의 line 이 0** 이었고, 단위 테스트가
    손으로 쓴 `line_no` 픽스처를 썼기 때문에 그 어긋남이 초록 뒤에 숨어 있었다.
    Read both keys: 3.0 renamed line_no to start_line_no, and a hand-written fixture
    using the old key hid the drift behind a green test.
    """
    return int(violation.get("start_line_no") or violation.get("line_no") or 0)


class _SqlfluffAnalyzer:
    """sqlfluff SQL 분석기 — JSON 출력 파싱.
    sqlfluff SQL analyzer — parses JSON output.
    """

    name = "sqlfluff"
    category = Category.CODE_QUALITY
    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"sql"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """SQL 파일 여부 확인.
        Check whether the file is a SQL file.
        """
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """sqlfluff 바이너리 설치 여부 확인.
        Check whether the sqlfluff binary is installed.
        """
        return shutil.which("sqlfluff") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """sqlfluff lint --format=json 출력을 파싱해 이슈 반환.
        Parse sqlfluff lint --format=json output and return issues.
        """
        try:
            r = subprocess.run(  # nosec B603 B607
                ["sqlfluff", "lint", "--format=json", "--dialect=ansi", ctx.tmp_path],
                capture_output=True, text=True,
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            raw = r.stdout.strip()
            # 🔴 판별식은 **stdout 이 JSON 배열인가**이지 종료코드가 아니다(실측, sqlfluff 4.2.2):
            #      clean          exit 0  `[{… "violations": []}]`   ← 빈 출력이 아니다
            #      위반 있음      exit 1  `[{… "violations": [ … ]}]`
            #      잘못된 dialect exit 2  `Error: Unknown dialect …`  ← 비-JSON
            #      파일 없음      exit 2  빈 출력
            #    즉 「빈 출력 = 깨끗함」은 틀렸고, `returncode != 0` 을 크래시로 읽으면
            #    정상 탐지(exit 1)를 통째로 «분석 실패» 로 만든다.
            # The discriminator is JSON-ness, not the exit code: a clean run still emits a
            # document, and a nonzero exit is how sqlfluff reports that it FOUND violations.
            if not raw.startswith("["):
                raise _fail(ctx, r)
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise _fail(ctx, r) from exc
            # 🔴 엔트리 0개 = 이 경로에 대한 결과가 **없다** = 분석하지 않았다.
            #    sqlfluff 는 `large_file_skip_byte_limit`(기본 20000) 를 넘는 파일을
            #    조용히 건너뛰고 `[]` + **exit 0** 을 낸다 — 그대로 두면 20KB 넘는 SQL 이
            #    전부 «이슈 0건 · 완전» 으로 만점을 받는다(실측: 같은 내용 3.2KB=9건 →
            #    32KB=0건). 깨끗한 파일은 엔트리 **1개**(`violations: []`)를 낸다.
            #    `_fail` 이 stderr 를 실어 보내므로 사유와 해소법(설정값 상향)이 그대로 보인다.
            # Zero entries means sqlfluff produced no result for this path: it skipped the
            # file (large_file_skip_byte_limit) rather than finding it clean.
            if not data:
                raise _fail(ctx, r)
            issues = []
            for file_result in data:
                for v in file_result.get("violations", []):
                    issues.append(AnalysisIssue(
                        tool="sqlfluff",
                        severity=Severity.WARNING,
                        message=f"[{v.get('code', '')}] {v.get('description', '')}",
                        line=_violation_line(v),
                        category=Category.CODE_QUALITY,
                        language=ctx.language,
                    ))
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("sqlfluff timed out for %s", ctx.tmp_path)
            return []
        except FileNotFoundError as exc:
            # 바이너리 부재 — 크래시와 **다른 축**이다. `static.py` 가 `unavailable_tools`
            # 로 따로 보고하므로 여기서 예외로 올리지 않는다. 🔴 `OSError` 로 넓히지 마라 —
            # `shutil.which` 를 통과한 뒤의 ENOEXEC·PermissionError·TOCTOU 는 「부재」가
            # 아니라 **미분석**이라 `incomplete` 로 올라가야 한다.
            # Missing binary is the procurement axis; do not widen to OSError, which would
            # swallow spawn failures that are unanalyzed runs, not absent binaries.
            logger.warning("sqlfluff binary missing for %s: %s", ctx.tmp_path, exc)
            return []


register(_SqlfluffAnalyzer())
