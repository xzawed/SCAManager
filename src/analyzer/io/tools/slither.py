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

from src.analyzer.pure.registry import AnalyzeContext, AnalysisIssue, Category, Severity, register
from src.analyzer.io.tools._common import analysis_failed
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
            # 🔴 exit code 는 판별식이 **아니다** — 성공해도 0 이 아니다(실측: 같은 성공을
            #    두 호스트에서 재니 127 과 4294967295 로 **달랐다**. 값은 우연이고 불변식은
            #    「성공도 비-0 일 수 있다」 하나뿐이라 exit 으로 판정하면 정상 실행이 차단된다).
            #      유효한 .sol   비-0 · stdout 에 `{"success": true, ...}`
            #      구문 오류·없는 파일   stdout **0자**
            #    성공하면 항상 JSON 을 내므로 판별식은 **빈 stdout** 이다.
            # Measured: a successful slither run exits nonzero (the value varies by host) but
            # always writes JSON; a crash writes nothing.
            if not r.stdout.strip():
                raise analysis_failed("slither", ctx, r, "produced no output")
            return _parse_slither_json(r.stdout, ctx.language)
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("slither timed out for %s", ctx.tmp_path)
            return []
        except FileNotFoundError as exc:
            # which() 통과 뒤 사라진 바이너리 — 조달 축(`unavailable_tools`)이 담당한다.
            # A binary that vanished after the which() gate; procurement owns it.
            logger.warning("slither unavailable for %s: %s", ctx.tmp_path, exc)
            return []
        except (json.JSONDecodeError, ValueError,
                AttributeError, TypeError) as exc:
            # slither 가 JSON 을 냈는데 이 어댑터가 읽을 수 있는 모양이 아니다 = 미분석이다.
            # Output that this adapter cannot read is unanalyzed, not clean.
            raise analysis_failed(
                "slither", ctx, r, "produced JSON this adapter cannot read") from exc


def _map_severity(impact: str) -> Severity:
    """slither impact 문자열을 Severity enum 으로 매핑."""
    return Severity.ERROR if impact in ("High", "Medium") else Severity.WARNING


def _map_category(check: str) -> Category:
    """slither detector 이름 기준 category 매핑 (security vs code_quality)."""
    return Category.SECURITY if check in _SECURITY_DETECTORS else Category.CODE_QUALITY


def _extract_line_number(elements: list) -> int:
    """slither detector elements 에서 첫 line 번호 추출. 실패 시 0."""
    if not elements:
        return 0
    source = elements[0].get("source_mapping", {}) or {}
    lines = source.get("lines", []) or []
    if not lines:
        return 0
    try:
        return int(lines[0])
    except (TypeError, ValueError):
        return 0


def _parse_slither_json(json_text: str, language: str) -> list[AnalysisIssue]:
    """slither JSON 결과를 AnalysisIssue 목록으로 변환한다.

    subprocess mock 없이 JSON 픽스처만으로 검증 가능하도록 분리된 모듈 레벨 함수.

    🔴 `success=false` 는 slither 가 **분석하지 못했다**는 자기 보고다 — 그것을 `[]` 로
    돌려주면 미분석이 «이슈 0건 · 완전» 이 된다. `ValueError` 로 올리면 `run()` 의
    핸들러가 `analysis_failed` 로 바꿔 `static.py` 가 incomplete 로 승격한다.
    `success=false` is slither reporting that it did not analyze; returning [] would record
    that silence as a clean file.
    """
    data = json.loads(json_text)
    if not data.get("success", False):
        raise ValueError(
            f"slither reported success=false: {str(data.get('error'))[:200]}")
    detectors = data.get("results", {}).get("detectors", []) or []
    issues: list[AnalysisIssue] = []
    for det in detectors:
        check = det.get("check", "")
        message = det.get("description", "").strip().split("\n")[0] or check
        issues.append(AnalysisIssue(
            tool="slither",
            severity=_map_severity(det.get("impact", "Informational")),
            message=message,
            line=_extract_line_number(det.get("elements", []) or []),
            category=_map_category(check),
            language=language,
        ))
    return issues


def _register_slither_analyzers() -> None:
    register(_SlitherAnalyzer())


_register_slither_analyzers()
