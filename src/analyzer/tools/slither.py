"""slither static analysis tool — Solidity 전용 정적분석 (Phase D.2).

_SlitherAnalyzer 는 Analyzer Protocol 을 구현하며 registry.register() 로
등록된다. slither 바이너리가 없으면 is_enabled() 가 False 를 반환해 조용히
skip 된다. slither 는 `--json -` 옵션 시 stdout 에 JSON 을 출력한다.

detector impact High/Medium → error, Low/Informational/Optimization → warning.
detector name 이 _SECURITY_DETECTORS 화이트리스트에 포함되면 category=security,
외는 code_quality 로 분류 (mixed-category analyzer).
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess  # nosec B404

from src.analyzer.registry import AnalyzeContext, AnalysisIssue, Category, Severity, register
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)

# detector name → security 분류 기준 (smart-contract 취약점 화이트리스트)
_SECURITY_DETECTORS: frozenset[str] = frozenset({
    "reentrancy-eth", "reentrancy-no-eth", "reentrancy-benign",
    "reentrancy-events", "reentrancy-unlimited-gas",
    "suicidal", "arbitrary-send-eth", "arbitrary-send-erc20",
    "uninitialized-state", "uninitialized-storage", "tx-origin",
    "controlled-delegatecall", "controlled-array-length",
    "unchecked-transfer", "unchecked-send", "unchecked-lowlevel",
    "weak-prng", "timestamp",
})


class _SlitherAnalyzer:
    name = "slither"
    category = Category.SECURITY  # 기본 security, detector 별로 override

    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"solidity"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Solidity 파일 여부 확인."""
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """slither 바이너리 설치 여부 확인."""
        return shutil.which("slither") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """slither JSON 출력을 파싱해 이슈 목록 반환."""
        try:
            r = subprocess.run(  # nosec B603 B607
                ["slither", ctx.tmp_path, "--json", "-"],
                capture_output=True, text=True, timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            if not r.stdout.strip():
                return []
            return _parse_slither_json(r.stdout, ctx.language)
        except subprocess.TimeoutExpired:
            logger.warning("slither timed out for %s", ctx.tmp_path)
            return []
        except (OSError, json.JSONDecodeError, ValueError,
                AttributeError, TypeError) as exc:
            # slither JSON 스키마 변형(results 가 list 등)에 대비한 방어
            logger.warning("slither failed for %s: %s", ctx.tmp_path, exc)
            return []


def _parse_slither_json(json_text: str, language: str) -> list[AnalysisIssue]:
    """slither JSON 결과를 AnalysisIssue 목록으로 변환한다.

    subprocess mock 없이 JSON 픽스처만으로 검증 가능하도록 분리된 모듈 레벨 함수.
    success=false (Solidity 컴파일 실패) 인 경우 빈 목록 반환.
    """
    data = json.loads(json_text)
    if not data.get("success", False):
        return []
    detectors = data.get("results", {}).get("detectors", []) or []
    issues: list[AnalysisIssue] = []
    for det in detectors:
        check = det.get("check", "")
        impact = det.get("impact", "Informational")
        severity = Severity.ERROR if impact in ("High", "Medium") else Severity.WARNING
        category = Category.SECURITY if check in _SECURITY_DETECTORS else Category.CODE_QUALITY
        message = det.get("description", "").strip().split("\n")[0] or check
        line = 0
        elements = det.get("elements", []) or []
        if elements:
            source = elements[0].get("source_mapping", {}) or {}
            lines = source.get("lines", []) or []
            if lines:
                try:
                    line = int(lines[0])
                except (TypeError, ValueError):
                    line = 0
        issues.append(AnalysisIssue(
            tool="slither",
            severity=severity,
            message=message,
            line=line,
            category=category,
            language=language,
        ))
    return issues


def _register_slither_analyzers() -> None:
    register(_SlitherAnalyzer())


_register_slither_analyzers()
