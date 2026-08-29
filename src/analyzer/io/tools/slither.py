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
        """slither 와 **solc 컴파일러 아티팩트**가 모두 있는지 확인.

        🔴 컴파일러가 없으면 실행하지 않는다 — 조달 실패는 벽이 아니라 게이트여야 한다.
        slither 는 pip 패키지라 `which("slither")` 는 solc 유무와 무관하게 참이다.
        `railway.toml` 은 `solc-select install` 이 실패하면 「slither analyzer will be
        disabled」라고 적지만 그 비활성화가 구현된 적이 없었다. 그래서 solc 가 없으면
        slither 가 실행되어 **빈 stdout** 을 내고, 그것을 미분석으로 올리는 순간
        모든 Solidity 파일이 `incomplete` 가 된다.

        실측(slither 0.11.5, `--solc` 로 컴파일러만 격리): 정상 solc → JSON `success=true`,
        solc 사용 불가 → stdout **0자**. 즉 `success=false` 가 아니라 빈 출력이다.

        🔴 `shutil.which("solc")` 는 프로브가 될 수 없다 — `solc` 는 solc-select 가 까는
        콘솔 스크립트이고 `slither-analyzer → crytic-compile → solc-select` 의존이라
        pip 설치만으로 항상 PATH 에 생긴다(실측: `solc_select.__main__:solc`). 그것을
        프로브로 쓰면 프로덕션에서 무동작인 채 테스트만 초록이 된다.
        🔴 `solc --version` 도 부르지 않는다 — shim 은 아티팩트가 없으면 최신판을
        **자동 내려받는다**(`always_install=True`). 파일마다 네트워크를 타게 된다.

        Gate on installed compiler artifacts, not on the pip-installed `solc` shim.
        """
        if shutil.which("slither") is None:
            return False
        try:
            # 지연 임포트 — solc-select 는 slither 의 전이 의존이라 여기서만 필요하고,
            # 없는 환경(네이티브 solc)에서도 이 모듈이 임포트되어야 한다.
            # Lazy: solc-select is a transitive dep; this module must import without it.
            from solc_select.solc_select import (  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
                installed_versions,
            )
            return bool(installed_versions())
        except (ImportError, OSError):
            # solc-select 가 없는 환경(네이티브 solc) — 그때는 바이너리 존재가 최선의 신호다.
            # Without solc-select (a native solc install), presence is the best available signal.
            return shutil.which("solc") is not None

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
