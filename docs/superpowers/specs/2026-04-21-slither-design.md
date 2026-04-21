# slither (Solidity 정적분석) — 설계 스펙 (Phase D.2)

**작성일**: 2026-04-21
**상태**: Draft — 사용자 GO/NO-GO 승인 대기
**Phase**: D.2 (Phase D.1 cppcheck 직후 연속, 동일 패턴 재사용)
**리스크**: 🟢 낮음

## 1. Context

Phase D.1 cppcheck 완료 이후 Phase D.2 의 다음 후보가 **slither** (Solidity 전용 정적분석). STATE.md 잔여 과제 표 기준:

| 우선순위 | 도구 | 언어 | 이미지 증가 | 리스크 | 상태 |
|---------|-----|-----|------------|-------|------|
| D.1 | cppcheck | C/C++ | +30MB | 🟢 | ✅ 완료 |
| D.2 | **slither** | **Solidity** | **+100MB** | **🟢** | **대기** |
| D.3 | RuboCop | Ruby | +80MB | 🟡 | 대기 |

### slither 선정 이유

- 🟢 낮은 리스크: **pip install slither-analyzer** 로 단순 설치 (Python 패키지 — apt 또는 Docker 불필요)
- Solidity(`.sol`) 는 이미 `language.py:45` 에 감지 등록됨 (Tier 2)
- 현재 Semgrep 이 Solidity 를 부분 지원하지만 smart-contract 특유의 reentrancy / gas 취약점은 커버 부족
- slither 는 Trail of Bits 에서 유지 관리, detector 약 **90+ 종** (reentrancy, uninitialized state variables, suicidal contracts 등)

### 이번 도구의 차별점

- D.1 cppcheck 가 apt 패키지였다면, D.2 slither 는 **pip 패키지** — `requirements.txt` 수정으로 설치 (nixpacks 수정 불필요)
- **CLI 대신 Python API 직접 호출 가능** (slither-analyzer 패키지가 library API 노출) — but subprocess 호출이 더 격리됨 (기존 Analyzer 패턴 유지)

## 2. 범위 결정 사항

| 항목 | 결정 |
|------|------|
| 도구 선정 | slither-analyzer (Phase D.2 — STATE.md 잔여 과제 2순위, 🟢 낮은 리스크) |
| 설치 방식 | pip — `requirements.txt` 에 `slither-analyzer>=0.10.0` 추가 |
| 대상 언어 | `solidity` (`language.py` 에 이미 감지 등록) |
| 출력 포맷 | `--json -` (stdout JSON, `-` 은 stdin 또는 파일) — slither 는 `--json <path>` 로 파일 출력 |
| 활성화 detector | **기본 모든 detector** (`--detect` 옵션 없음) — Phase D.1 `--enable=warning,style,...` 선례와 달리 Solidity 는 noise 가 적음 |
| Severity 매핑 | slither detector impact: `High`/`Medium` → `error`, `Low`/`Informational`/`Optimization` → `warning` |
| Category 분류 | **Solidity 특성상 security 와 code_quality 양쪽 필요**. `impact == "High"` + detector name 이 `reentrancy`/`suicidal`/`arbitrary-send` 등 보안 관련이면 `category="security"`, 그 외는 `code_quality` |
| 타임아웃 | `STATIC_ANALYSIS_TIMEOUT` 상수 재사용 (30초) — Solidity 파일은 통상 소규모 |
| 바이너리 미존재 대응 | `shutil.which("slither") is None` → `is_enabled()=False` → 조용히 skip |

## 3. 아키텍처

단일 파일 신설 + 자동 등록. **shellcheck.py / cppcheck.py 와 동일 패턴**.

```
src/analyzer/tools/slither.py            ← 신규
src/analyzer/static.py                   ← import 1줄 추가
requirements.txt                         ← slither-analyzer>=0.10.0 추가
tests/test_analyzer_tools_slither.py     ← 신규 — subprocess mock + JSON 파싱
```

**불변 제약**:
- `registry.py` (Analyzer Protocol) 불변
- `static.py::analyze_file()` 로직 불변
- `AnalysisIssue` dataclass 구조 불변
- `language.py` 감지 규칙 불변 (`solidity` 이미 존재)
- 점수 계산 불변 (`CQ_WARNING_CAP=25` 통합 cap)

## 4. 컴포넌트 — `_SlitherAnalyzer` 상세

```python
"""slither static analysis tool — Solidity 전용 정적분석 (Phase D.2)."""
from __future__ import annotations

import json
import logging
import shutil
import subprocess  # nosec B404

from src.analyzer.registry import AnalyzeContext, AnalysisIssue, register
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)

# detector name → security 분류 기준 (부분 집합)
_SECURITY_DETECTORS: frozenset[str] = frozenset({
    "reentrancy-eth", "reentrancy-no-eth", "reentrancy-benign",
    "suicidal", "arbitrary-send-eth", "arbitrary-send-erc20",
    "uninitialized-state", "uninitialized-storage", "tx-origin",
    "controlled-delegatecall", "controlled-array-length",
    "unchecked-transfer", "unchecked-send", "unchecked-lowlevel",
    "weak-prng", "timestamp",
})


class _SlitherAnalyzer:
    name = "slither"
    category = "security"  # 기본 security, detector 별로 override

    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"solidity"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        return shutil.which("slither") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """slither JSON 출력을 파싱해 이슈 목록 반환.

        - slither 는 stdout 에 JSON 출력 (--json - 옵션)
        - detector impact High/Medium → error, 나머지 → warning
        - detector name 이 _SECURITY_DETECTORS 에 포함되면 category=security
        """
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
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("slither failed for %s: %s", ctx.tmp_path, exc)
            return []


def _parse_slither_json(json_text: str, language: str) -> list[AnalysisIssue]:
    """slither JSON 결과를 AnalysisIssue 목록으로 변환."""
    data = json.loads(json_text)
    if not data.get("success", False):
        # compilation failure 등 — 빈 결과
        return []
    detectors = data.get("results", {}).get("detectors", []) or []
    issues: list[AnalysisIssue] = []
    for det in detectors:
        check = det.get("check", "")
        impact = det.get("impact", "Informational")
        severity = "error" if impact in ("High", "Medium") else "warning"
        category = "security" if check in _SECURITY_DETECTORS else "code_quality"
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
```

**핵심 포인트**:

- **stdout 파싱** (cppcheck 의 stderr 와 다름) — slither 는 `--json -` 옵션 시 JSON 을 stdout 에 출력
- **mixed category 처리**: 한 analyzer 가 `security` 와 `code_quality` 이슈를 모두 생성. 기존 `_SemgrepAnalyzer` 가 `metadata.category == "security"` 로 분류하는 패턴과 동일
- **`success` 필드 체크**: slither 는 Solidity 컴파일 실패 시 `success=false` 를 반환. 이런 경우 결과 무시 (사용자 소스 오류이므로 정적분석 대상 아님)

## 5. 데이터 플로우 (변경 없음)

```
run_analysis_pipeline
  → analyze_file(filename=".sol", content=...)
      → detect_language() → "solidity"
      → tempfile 생성 (suffix=".sol")
      → for analyzer in REGISTRY:
          semgrep (solidity 부분) + slither → 각자 이슈 추가
      → StaticAnalysisResult
  → calculate_score()
      → CQ_WARNING_CAP=25 통합 cap — slither/semgrep 합산 감점
      → security 이슈는 별도 SEC_ERROR=-7 감점 (기존 규칙)
```

## 6. 배포

### 6-1. `requirements.txt` 1줄 추가

```diff
  # requirements.txt (프로덕션)
  ...
  psycopg2-binary>=2.9.9
+ slither-analyzer>=0.10.0
  ...
```

**이미지 크기 증가**: **+100MB** (slither + 의존성: crytic-compile, solc-select, prettytable, packaging 등)

### 6-2. solc 컴파일러

slither 는 **solc (Solidity 컴파일러) 런타임 필요**. slither-analyzer 설치 시 자동으로 solc-select 도 포함되며 `.sol` 파일 의 `pragma solidity` 버전에 맞는 solc 를 런타임에 다운로드.

- **첫 실행 시** solc 다운로드 비용 (~5MB, 한 번만)
- devcontainer DNS 제약 환경에서는 첫 실행 실패 가능 → `is_enabled()=False` 경로로 조용히 skip (기존 패턴)

### 6-3. `nixpacks.toml` 변경 없음

`aptPkgs` 는 그대로 (`shellcheck`, `nodejs`, `npm`, `cppcheck`). slither 는 pip 경로라 Python provider 가 자동 설치.

## 7. 테스트

### 7-1. 단위 테스트 — `tests/test_analyzer_tools_slither.py` (신규)

| 테스트 | 검증 대상 |
|--------|----------|
| `test_supports_solidity` | `supports(ctx)` True for `solidity` |
| `test_supports_rejects_other_langs` | python/c/cpp 등 False |
| `test_is_enabled_when_binary_missing` | `shutil.which` None → False |
| `test_is_enabled_when_binary_present` | mock return path → True |
| `test_parse_json_extracts_detectors` | `results.detectors[]` 를 issues 로 변환 |
| `test_parse_json_maps_high_impact_to_error` | `impact=High` → `severity=error` |
| `test_parse_json_maps_low_impact_to_warning` | `impact=Low` → `severity=warning` |
| `test_parse_json_assigns_security_category_for_reentrancy` | `check="reentrancy-eth"` → `category=security` |
| `test_parse_json_assigns_code_quality_for_other_checks` | `check="pragma"` → `category=code_quality` |
| `test_parse_json_extracts_line_from_source_mapping` | `elements[0].source_mapping.lines[0]` → line |
| `test_parse_json_returns_empty_when_compilation_failed` | `success=false` → `[]` |
| `test_run_returns_empty_on_timeout` | TimeoutExpired → `[]` |
| `test_run_returns_empty_on_oserror` | OSError → `[]` |
| `test_run_returns_empty_on_json_decode_error` | 잘못된 JSON → `[]` |

### 7-2. Registry 등록 검증

`tests/test_analyzer_registry.py` 에 `TestSlitherAnalyzerRegistration` 추가 (cppcheck 선례와 동일):

```python
class TestSlitherAnalyzerRegistration:
    def test_registry_contains_slither_after_register_call(self):
        from src.analyzer.tools.slither import _register_slither_analyzers
        from src.analyzer.registry import REGISTRY
        _register_slither_analyzers()
        assert any(a.name == "slither" for a in REGISTRY)

    def test_slither_analyzer_has_correct_attributes(self):
        from src.analyzer.tools.slither import _SlitherAnalyzer
        a = _SlitherAnalyzer()
        assert a.name == "slither"
        assert a.category == "security"
        assert a.SUPPORTED_LANGUAGES == frozenset({"solidity"})
```

### 7-3. 통합 검증 (Railway 배포 후)

- 실제 `.sol` 파일(간단한 reentrancy 샘플)을 테스트 리포에 push → `slither` tool 의 `reentrancy-eth` 이슈 포함 여부 확인
- `is_enabled()=True` 확인 (Railway 배포 이미지에 slither 설치됨)

## 8. 오류 처리

| 시나리오 | 동작 |
|----------|------|
| slither 바이너리 미설치 | `is_enabled()=False` → skip |
| solc 버전 다운로드 실패 (오프라인 환경) | slither 가 compilation error 반환 → `success=false` → `[]` |
| 타임아웃 | TimeoutExpired → `[]` + warning log |
| JSON 파싱 실패 | JSONDecodeError catch → `[]` |
| Solidity 문법 오류 | `success=false` → `[]` (사용자 소스 문제, 정적분석 대상 아님) |

## 9. 범위 밖 (의도적 제외)

| 항목 | 제외 사유 |
|------|----------|
| 특정 detector 만 활성화 | 현재는 **모든 detector** 기본 실행 (noise 가 적은 편). 필요 시 Repo 별 설정으로 opt-in |
| Hardhat/Foundry 프로젝트 단위 분석 | 파일 단위 분석 설계 유지 (Phase E 이후) |
| solc 버전 고정 | slither 가 pragma 자동 감지 — 명시 옵션 불필요 |
| `--triage-mode` 인터랙티브 모드 | CI/웹훅 경로에서는 비적용 |

## 10. 자가 리뷰 체크리스트

- [x] Placeholder 없음
- [x] cppcheck 패턴 재사용 명시 (shellcheck.py ≈ cppcheck.py ≈ slither.py)
- [x] Scope 적절 — 단일 analyzer 추가 + requirements.txt 1줄 + 테스트 1파일
- [x] Category 매핑 규칙 명시 (`_SECURITY_DETECTORS` 화이트리스트)
- [x] slither 의 이미지 부담(+100MB) 수용 여부 — 🟢 낮은 리스크 범위
- [x] nixpacks 변경 없음 (pip 경로) — Docker 전환 불필요

## 11. 승인 요청

1. ✅ slither 도구 선정 승인 (STATE.md 2순위 + 🟢 낮은 리스크)
2. ✅ `requirements.txt` 에 `slither-analyzer>=0.10.0` 추가 — 이미지 +100MB 수용
3. ✅ 기본 모든 detector 활성 (noise 허용 수준)
4. ✅ category 를 detector name 화이트리스트로 security/code_quality 분류
5. ✅ solc 다운로드 비용 첫 실행 시 발생 수용

승인 후 본 스펙을 Task-by-Task 플랜(`docs/superpowers/plans/2026-04-2X-slither.md`)으로 변환. 예상 Task 7~8개 / ~2~3 시간 (cppcheck 플랜과 유사).
