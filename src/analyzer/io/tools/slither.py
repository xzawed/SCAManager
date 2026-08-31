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
import re
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



# 🔴 주석을 먼저 지우고 찾는다 — `_PRAGMA_RE` 는 주석 문법을 모르고 `search()` 는 **첫 매치**만
#    보기 때문이다. `*` 접두가 없는 `/* … */` 가 실물 pragma 앞에 있고 그 안의 한 줄이
#    `pragma solidity …;` 로 시작하면 그 줄이 판정을 가로챈다.
#    실측(py 3.12 · semantic_version 2.10.0 · 설치 0.8.20):
#      `/*\npragma solidity ^0.4.24;\n*/\npragma solidity ^0.8.0;` → 지우기 전 None · 후 0.8.20
#      반대 배치(주석이 맞춤·실물이 못 맞춤)      → 지우기 전 0.8.20 · 후 None
#    한쪽은 Solidity 분석을 잃고 다른 쪽은 못 맞추는 컴파일러로 돌아 빈 stdout(벽)이 된다.
#
# 🔴 줄 주석도 **같은 교차에서** 지운다. `^\s*pragma` 는 `//` 뒤를 매치하지 않으므로 줄 주석
#    자체는 후보가 아니지만, 줄 주석 **안에 `/*` 가 있으면** 그것이 블록 시작으로 읽혀
#    닫는 `*/` 나 파일 끝까지를 삼킨다 — 그 사이의 **실물 pragma 가 사라진다.**
#    실측: `// 참고 /* 예전에는 0.4.x 였다\npragma solidity ^0.4.24;` 에서
#      줄 주석 미포함 → 0.8.20 (못 맞추는 컴파일러로 실행 → 빈 stdout → 벽)
#      줄 주석 포함   → None   (옳다 — 못 맞추므로 건너뛴다)
#    교차 하나로 왼쪽부터 훑으므로 `//` 가 먼저 오면 그 줄이, `/*` 가 먼저 오면 그 블록이 먹는다.
#
# 🔴 **마지막 매치로 바꾸는 것은 오답이다** — 실물 pragma 뒤에 남은 주석이 판정을 뒤집는다.
# 🔴 미종결 `/*` 는 파일 끝까지 지운다 — 컴파일러가 그렇게 읽는다. 그 결과 실물 pragma 가
#    사라지면 판단 근거가 없어져 최신 설치본으로 돈다(막지 않는다). 안전한 방향이다.
#    🔴 그 갈래를 `(?:\*/|\Z)` 로 합치지 않는다 — `.*?` 뒤에 폭 0인 `\Z` 가 오면 정적 분석이
#    「0회만 매치한다」로 읽는다(SonarCloud S6019, 실측: new_maintainability_rating 3). 동작은
#    같지만 읽는 쪽이 갈리므로 갈래를 풀어 쓴다 — 닫힌 블록을 먼저 시도하고, 실패하면
#    미종결 갈래가 끝까지 먹는다.
# 🔴 문자열 리터럴 안의 `/*`·`//` 는 구별하지 못한다 — 그러려면 렉서가 필요하다. pragma 는
#    SPDX 다음 최상단이라 그 앞에 문자열이 오는 일이 사실상 없어 남겨 둔다(알려진 잔여).
# Strip comments before matching: the regex is comment-blind and takes the first match. Line
# comments are stripped too, because a `/*` inside one would otherwise open a block that eats
# the real pragma. String literals are not distinguished — that would need a lexer.
_COMMENT_RE = re.compile(
    r"//[^\n]*"        # 줄 주석 — 줄 끝까지 / line comment, to end of line
    r"|/\*.*?\*/"      # 닫힌 블록 — 가장 가까운 `*/` 까지 / closed block, nearest `*/`
    r"|/\*.*",         # 미종결 블록 — 파일 끝까지 / unterminated block, to EOF
    re.DOTALL,
)


# `pragma solidity <범위>;` 의 범위 부분만 뽑는다. 줄 앞에 오는 **선언문 형태**만 후보다 —
# 부분문자열이 상태를 대신하지 않게 고정한다. 🔴 이 정규식만으로는 주석 안의 선언문을
# 가려내지 못한다. 그것은 위 `_COMMENT_RE` 가 담당한다.
# Only a statement-shaped `pragma solidity …;` at line start is a candidate; comments are removed
# beforehand — this regex alone cannot tell one from a real statement.
_PRAGMA_RE = re.compile(r"^\s*pragma\s+solidity\s+([^;]+);", re.MULTILINE)



def _installed_solc_versions() -> tuple[str, ...]:
    """설치된 solc 버전 — 없거나 solc-select 가 없으면 빈 튜플.

    🔴 `list` 가 아니라 `tuple` 을 돌려준다. 재고 탐지기
    (`tests/unit/analyzer/test_adapter_fail_open_inventory.py`)는 어댑터 모듈의
    `return []` 를 「분석 못 했는데 깨끗하다고 보고」로 판정한다 — 옳은 판정이다.
    여기서 도는 것은 **이슈 목록이 아니라 버전 목록**이고 빈 값은 「설치본이 없다」는
    정상 관측이므로, 그 축과 형태가 겹치지 않게 컨테이너를 바꿔 뜻을 분리한다.

    `is_enabled` 와 같은 지연 임포트를 쓴다(로컬 3.14 에는 solc-select 가 없다).
    A version list, not an issue list: the empty case is a real observation, not silence.
    """
    try:
        from solc_select.solc_select import (  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
            installed_versions,
        )
        return tuple(installed_versions())
    except (ImportError, OSError):
        return ()


def _matching_solc(content: str, installed) -> str | None:
    """이 계약의 pragma 를 만족하는 설치본 중 **가장 높은 것** — 없으면 None.

    🔴 bool 이 아니라 **버전을 돌려준다.** `run()` 이 그 값을 `--solc-solcs-select` 로
    넘기기 때문이다. 넘기지 않으면 slither 는 전역 핀(`global-version`)만 보고, `install` 은
    됐는데 `use` 가 실패한 상태에서 **빈 stdout** 을 내 모든 Solidity 가 `incomplete` 가 된다.
    실측(상태 U): 기본 호출 stdout **0자** · `--solc-solcs-select 0.8.36` stdout 16069자.
    조달을 넓혀도 이 값을 넘기지 않으면 추가 컴파일러가 놀게 된다.

    🔴 `is_enabled` 를 `current_version()` 으로 게이트하지 **않는다** — 아티팩트가 있으면
    컴파일러는 돌 수 있고, 그 함수는 `argparse.ArgumentTypeError` 를 내는데 그것은
    `ImportError`·`OSError` 가 아니라 `is_enabled` 밖으로 샌다. 그러면 `pipeline.py` 가
    파일 단위로 삼켜 미분석 Solidity 가 **깨끗함**으로 채점된다 — 벽보다 나쁘다.

    🔴 왜 **실행 전**에 고르는가 — slither 는 pragma 를 못 맞추면 **빈 stdout** 을 내는데,
    그것은 구문 오류·크래시와 구별되지 않는다(실측: 셋 다 exit 1 · stdout 0자).
    사후 판정이 원리적으로 불가능하므로 사전 점검만이 「환경 핀 때문에 못 돌렸다」와
    「이 코드가 분석에 실패했다」를 가른다. `railway.toml` 은 solc **0.8.20 하나만** 핀한다.
    못 고르면 `is_enabled` 가 False → 조달 축으로 가고, 그 파일은 semgrep 만 보게 되므로
    `static.py::no_dedicated_observer` 가 그 사실을 기록한다.

    🔴 판단 근거가 없으면 **막지 않는다** — pragma 부재·파싱 실패는 최신 설치본을 돌려
    기존 동작(실행 후 결과로 판정)을 유지한다. 여기서 None 을 내면 판정하지 못한 파일이
    조용히 건너뛰어진다.

    🔴 `packaging` 은 쓸 수 없다 — `SpecifierSet("^0.8.0")` 이 `InvalidSpecifier` 다(실측).
    `semantic_version` 은 semgrep 의 전이 의존이라 프로덕션에 있으나 로컬 3.14 에는 없어
    **지연 임포트**한다.

    Pick the newest installed compiler satisfying the pragma; None when none can.
    """
    if not installed:
        return None
    match = _PRAGMA_RE.search(_COMMENT_RE.sub("", content or ""))
    try:
        from semantic_version import (  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
            NpmSpec, Version,
        )
        parsed = sorted((Version(v) for v in installed), reverse=True)
        if not match:
            # pragma 가 없으면 판단 근거가 없다 — 막지 않고 최신 설치본으로 돈다.
            # No pragma: nothing to judge against; run with the newest installed compiler.
            return str(parsed[0])
        spec = NpmSpec(match.group(1).strip())
        return next((str(v) for v in parsed if v in spec), None)
    except (ImportError, ValueError, TypeError):
        # 파싱 실패·의존 부재는 「못 맞춘다」가 아니다 — 판단하지 못했을 뿐이다.
        # 그때는 막지 않고 설치본 하나로 돈다. 결과는 실행 후 판정한다.
        # 🔴 이것은 「최신」이 **아니다.** solc-select 1.2.0 정본 실측:
        #      `[f.replace("solc-","") for f in sorted(os.listdir(ARTIFACTS_DIR)) …]`
        #    디렉터리명 **사전순**이라 설치본이 {0.4.24, 0.8.20} 이면 `installed[0]` 은
        #    **0.4.24**(가장 낮은 것)다. 여기서는 버전을 파싱할 수단(`semantic_version`)이
        #    없어서 이 갈래에 들어온 것이므로 정렬할 수 없다 — 손으로 파싱하면 그것이
        #    두 번째 판정식이 된다.
        # Not "the newest": solc-select sorts directory names lexically, and this branch exists
        # precisely because version parsing is unavailable — sorting here would be a second,
        # hand-rolled version predicate.
        return installed[0]


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
            installed = installed_versions()
            if not installed:
                return False
            return _matching_solc(ctx.content, installed) is not None
        except (ImportError, OSError):
            # solc-select 가 없는 환경(네이티브 solc) — 그때는 바이너리 존재가 최선의 신호다.
            # Without solc-select (a native solc install), presence is the best available signal.
            return shutil.which("solc") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """slither JSON 출력을 파싱해 이슈 목록 반환."""
        try:
            # 🔴 고른 컴파일러를 **명시**한다 — 안 넘기면 slither 는 전역 핀만 보고,
            # `install` 성공 + `use` 실패 상태에서 빈 stdout 을 내 벽이 된다(실측).
            # Pass the matched compiler explicitly; the global pin alone walls in state U.
            argv = ["slither", ctx.tmp_path, "--json", "-"]
            chosen = _matching_solc(ctx.content, _installed_solc_versions())
            if chosen:
                argv += ["--solc-solcs-select", chosen]
            r = subprocess.run(  # nosec B603 B607
                argv,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
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
