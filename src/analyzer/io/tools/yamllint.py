"""yamllint — YAML 정적 분석기.
yamllint YAML static analyzer.

_YamllintAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
yamllint 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
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


# yamllint `-f parsable` 한 줄: `<path>:<line>:<col>: [<level>] <message> (<rule>)`
# One `-f parsable` line: `<path>:<line>:<col>: [<level>] <message> (<rule>)`
_PARSABLE = re.compile(
    r"^.*?:(?P<line>\d+):\d+:\s*\[(?P<level>\w+)\]\s*(?P<message>.*?)(?:\s*\((?P<rule>[\w-]+)\))?$"
)

# 🔴 yamllint 종료코드는 「0=깨끗 / 1=문제」가 아니다 (1.38.0 `cli.py:245-252` 실측):
#   0 = 문제 없음 **또는 warning 만**(--strict 아닐 때) · 1 = error 있음
#   2 = argparse 오류, **또는 --strict + warning 만**(이때 결과는 정상 출력된다)
#   -1(255) = 설정 파일 오류
# 그래서 종료코드만으로 실패를 판정하면 --strict 를 켜는 순간 정상 결과를 버리게 된다.
# 판정은 tsc 어댑터와 같게 한다(`tsc.py:99-103`) — **먼저 파싱하고**, 결과가 하나도
# 없는데 종료코드가 0이 아니면 그때 실패다. usage 오류(빈 출력 + 비정상 종료)를 잡으면서
# --strict 경로에서도 결과를 버리지 않는다.
# Exit codes are not a clean failure signal here (--strict makes warnings exit 2 *with*
# findings). Parse first, then treat 'nonzero and nothing parsed' as the failure.
_ERR_EXCERPT = 200


class _YamllintAnalyzer:
    """yamllint YAML 분석기 — `-f parsable` 출력 파싱.

    🔴 **`-f json` 을 쓰지 않는다.** `requirements.txt` 가 핀한 yamllint 1.38.0 의
    `-f` 선택지는 `{parsable,standard,colored,github,auto}` 뿐이고 `json` 이 없다.
    그 값을 넘기면 매 호출이 usage 에러(exit 2, stdout 빈값)로 끝나는데, 예전 구현은
    그 빈 출력을 «문제 없음» 으로 돌려줘서 **이 계약 분석기는 운영에서 한 번도 YAML 을
    분석한 적이 없었다** — 그러면서 모든 YAML 파일이 만점으로 집계됐다.

    The pinned yamllint has no `json` formatter, so the old argv failed on every call and
    the empty output was reported as "no problems".
    """

    name = "yamllint"
    category = Category.CODE_QUALITY
    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"yaml"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """YAML 파일 여부 확인.
        Check whether the file is a YAML file.
        """
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """yamllint 바이너리 설치 여부 확인.
        Check whether the yamllint binary is installed.
        """
        return shutil.which("yamllint") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """`yamllint -f parsable` 출력을 파싱해 이슈 반환.

        🔴 실패는 삼키지 않는다 — `RuntimeError` 를 올리면 `static.py` 가 그것을 받아
        `incomplete` 로 승격하고 미분석 코드의 auto-merge 를 막는다. `[]` 를 돌려주면
        같은 실패가 «깨끗» 이 된다(이 어댑터의 원래 결함).
        Failures raise: static.py promotes that to `incomplete`, blocking auto-merge.
        """
        try:
            r = subprocess.run(  # nosec B603 B607
                ["yamllint", "-f", "parsable", ctx.tmp_path],
                capture_output=True, text=True,
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("yamllint timed out for %s", ctx.tmp_path)
            return []
        except FileNotFoundError as exc:
            # which() 통과 뒤 사라진 바이너리 — 조달 축(`unavailable_tools`)이 담당한다.
            # 그 밖의 OSError(깨진 shebang · 권한)는 미분석이므로 올라간다.
            # A binary that vanished after the which() gate; procurement owns it.
            logger.warning("yamllint unavailable for %s: %s", ctx.tmp_path, exc)
            return []

        issues: list[AnalysisIssue] = []
        for raw_line in r.stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            m = _PARSABLE.match(line)
            if m is None:
                # 형식을 못 읽었다 = 파서 계약이 깨졌다. 조용히 버리면 그만큼 «깨끗» 이 된다.
                # An unreadable line means the parser contract broke; dropping it fakes cleanliness.
                raise RuntimeError(
                    f"yamllint produced an unparseable line for {ctx.tmp_path}: {line[:_ERR_EXCERPT]}"
                )
            level = (m.group("level") or "warning").lower()
            rule = m.group("rule") or ""
            issues.append(AnalysisIssue(
                tool="yamllint",
                severity=Severity.ERROR if level == "error" else Severity.WARNING,
                message=f"[{rule}] {m.group('message')}".strip(),
                line=int(m.group("line")),
                category=Category.CODE_QUALITY,
                language=ctx.language,
            ))

        if not issues and r.returncode != 0:
            # 아무것도 못 읽었는데 비정상 종료 = 분석을 못 했다(usage/설정 오류).
            # Nothing parsed + nonzero exit = the tool never analyzed the file.
            raise RuntimeError(
                f"yamllint did not analyze {ctx.tmp_path} "
                f"(exit={r.returncode}): {(r.stderr or r.stdout).strip()[:_ERR_EXCERPT]}"
            )
        return issues


register(_YamllintAnalyzer())
