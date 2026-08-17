"""Python static analysis tools — pylint, flake8, bandit.

각 클래스는 Analyzer 프로토콜을 구현하며 registry.register()로 등록된다.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess  # nosec B404

from src.analyzer.pure.registry import AnalyzeContext, AnalysisIssue, Category, Severity, register
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)


class _PylintAnalyzer:
    name = "pylint"
    category = Category.CODE_QUALITY

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Python 파일 여부 확인."""
        return ctx.language == "python"

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """pylint 바이너리 설치 여부 확인.

        🔴 `shutil.which` 로 **바이너리를 관측**한다. `return True` 였을 때
        `pylint` 은 부재해도 `unavailable_tools` 에 들어가지 않아 `static.py` 의
        조달 회귀 승격이 도달하지 못했다 — 파이썬 파일이 분석기 없이 만점을 받고
        auto-merge 됐다. `PROVISIONED_ANALYZERS` 안 도구이므로 부재는 배포 회귀다.
        Observe the binary: returning True kept this tool out of `unavailable_tools`,
        so the provisioned-regression promotion could never reach it.
        """
        return shutil.which("pylint") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """pylint JSON 출력을 파싱해 AnalysisIssue 목록 반환."""
        disable = (
            "C0114,C0115,C0116,C0301,C0411,"
            "E0401,"
            "R0801,R0902,R0903,R0912,R0913,R0914,R0915,R0917,"
            "W0511,W0613,W0621,W0718"
        )
        if ctx.is_test:
            disable += ",W0611,W0212,C0302,R0401"
        try:
            r = subprocess.run(  # nosec B603 B607
                ["pylint", ctx.tmp_path, "--output-format=json",
                 f"--disable={disable}"],
                capture_output=True, text=True, timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            items = json.loads(r.stdout) if r.stdout.strip().startswith("[") else []
            # C10: item.get() 방어 접근 — 도구가 키 누락 JSON 을 내도 KeyError 로 analyzer 전체가
            # 중단(이슈 전량 무음 폐기 + incomplete 미설정 = fail-open)되지 않게 한다(golangci_lint 패턴).
            # C10: defensive .get() — a missing key must not raise KeyError and silently drop the whole
            # analyzer's issues without an incomplete marker (golangci_lint pattern).
            return [
                AnalysisIssue(
                    tool="pylint",
                    severity=Severity.ERROR if item.get("type") in ("error", "fatal") else Severity.WARNING,
                    message=str(item.get("message") or ""),  # None/비-str 도 안전
                    line=item.get("line") or 0,              # None → 0
                    category=self.category,
                    language=ctx.language,
                )
                for item in items
            ]
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("pylint timed out for %s", ctx.tmp_path)
            return []
        except (json.JSONDecodeError, FileNotFoundError) as exc:
            logger.warning("pylint failed for %s: %s", ctx.tmp_path, exc)
            return []


class _Flake8Analyzer:
    name = "flake8"
    category = Category.CODE_QUALITY

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Python 파일 여부 확인."""
        return ctx.language == "python"

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """flake8 바이너리 설치 여부 확인.

        🔴 `shutil.which` 로 **바이너리를 관측**한다. `return True` 였을 때
        `flake8` 은 부재해도 `unavailable_tools` 에 들어가지 않아 `static.py` 의
        조달 회귀 승격이 도달하지 못했다 — 파이썬 파일이 분석기 없이 만점을 받고
        auto-merge 됐다. `PROVISIONED_ANALYZERS` 안 도구이므로 부재는 배포 회귀다.
        Observe the binary: returning True kept this tool out of `unavailable_tools`,
        so the provisioned-regression promotion could never reach it.
        """
        return shutil.which("flake8") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """flake8 출력을 파싱해 AnalysisIssue 목록 반환."""
        cmd = ["flake8", ctx.tmp_path, "--max-line-length=120",
               "--format=%(row)d:%(col)d: %(text)s"]
        if ctx.is_test:
            cmd.append("--ignore=E302,E402,E128,E127,F401,F841,E305")
        try:
            r = subprocess.run(  # nosec B603 B607
                cmd,
                capture_output=True, text=True, timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            issues = []
            for line in r.stdout.strip().splitlines():
                parts = line.split(":", 2)
                if len(parts) == 3:
                    try:
                        issues.append(AnalysisIssue(
                            tool="flake8",
                            severity=Severity.WARNING,
                            message=parts[2].strip(),
                            line=int(parts[0]),
                            category=self.category,
                            language=ctx.language,
                        ))
                    except ValueError:
                        continue
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("flake8 timed out for %s", ctx.tmp_path)
            return []
        except FileNotFoundError as exc:
            logger.warning("flake8 failed for %s: %s", ctx.tmp_path, exc)
            return []


class _BanditAnalyzer:
    name = "bandit"
    category = Category.SECURITY

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Python **생산** 파일 여부 — 테스트 파일은 애초에 대상이 아니다.

        🔴 「이 파일엔 정책상 해당 없음」은 `supports` 이지 `is_enabled` 가 아니다.
        `is_enabled` 가 False 면 `static.py` 가 그 도구를 `unavailable_tools` 에 넣고,
        bandit 은 `PROVISIONED_ANALYZERS` 안이라 **모든 테스트 파일이 조달 회귀로 승격**된다
        (테스트를 건드리는 PR 전부 auto-merge 차단 — 그 회귀가 실제로 났다).
        `supports` 로 옮기면 그 파일에서 bandit 은 «지원 대상 아님» 이 되어 두 집합 어디에도
        들어가지 않는다. `static.py:75-90` 이 이 구별을 계약으로 적어 두었다.
        Policy non-applicability belongs in `supports`: `is_enabled=False` means "binary absent",
        which promotes provisioned tools to a deployment regression.
        """
        return ctx.language == "python" and not ctx.is_test

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """bandit 바이너리 설치 여부 확인.

        🔴 `shutil.which` 로 **바이너리를 관측**한다. `not ctx.is_test` 만 보던 동안
        `bandit` 은 부재해도 `unavailable_tools` 에 들어가지 않아 `static.py` 의
        조달 회귀 승격이 도달하지 못했다 — 파이썬 파일이 분석기 없이 만점을 받고
        auto-merge 됐다. `PROVISIONED_ANALYZERS` 안 도구이므로 부재는 배포 회귀다.
        Observe the binary: the old predicate kept this tool out of `unavailable_tools`,
        so the provisioned-regression promotion could never reach it.
        """
        return shutil.which("bandit") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """bandit JSON 출력을 파싱해 보안 이슈 목록 반환."""
        try:
            r = subprocess.run(  # nosec B603 B607
                ["bandit", "-f", "json", "-q", ctx.tmp_path],
                capture_output=True, text=True, timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            data = json.loads(r.stdout) if r.stdout.strip().startswith("{") else {}
            # C10: item.get() 방어 접근 (pylint 대칭) — 키 누락 JSON 의 KeyError fail-open 차단.
            # C10: defensive .get() (mirrors pylint) — block the KeyError fail-open on missing keys.
            return [
                AnalysisIssue(
                    tool="bandit",
                    severity=(Severity.ERROR if str(item.get("issue_severity") or "").upper() == "HIGH"
                              else Severity.WARNING),
                    message=str(item.get("issue_text") or ""),  # None/비-str 도 안전
                    line=item.get("line_number") or 0,          # None → 0
                    category=self.category,
                    language=ctx.language,
                )
                for item in data.get("results", [])
            ]
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("bandit timed out for %s", ctx.tmp_path)
            return []
        except (json.JSONDecodeError, FileNotFoundError) as exc:
            logger.warning("bandit failed for %s: %s", ctx.tmp_path, exc)
            return []


# 모듈 로드 시 자동 등록
# Auto-registered when this module is imported.
def _register_python_analyzers() -> None:
    register(_PylintAnalyzer())
    register(_Flake8Analyzer())
    register(_BanditAnalyzer())


_register_python_analyzers()
