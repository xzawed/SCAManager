> ⚠️ **ARCHIVED — 2026-04-27**: 이 문서는 해당 시점에 완료된 작업을 기록한 것으로, 현재 코드베이스와 일치하지 않을 수 있습니다. 현재 상태는 [docs/STATE.md](../STATE.md)를 참조하세요.

# cppcheck (C/C++ 정적분석) — 설계 스펙 (Phase D.1)

**작성일**: 2026-04-21
**상태**: ✅ 완료 (2026-04-21) — STATE.md 그룹 10 참조
**Phase**: D.1 (Tier 1 전용 정적분석 확장의 첫 도구)
**리스크**: 🟢 낮음

## 1. Context

현재 SCAManager 의 C/C++ 정적분석은 **Semgrep** 만 작동한다. Semgrep 은 다언어 baseline 규칙 기반이라 C/C++ 특유의 메모리 안전성·정의되지 않은 동작(UB)·포인터 오남용 같은 언어 고유 결함을 완전히 커버하지 못한다. Tier 1 언어인 C/C++ 에 전용 정적분석 도구를 하나 추가해 분석 커버리지를 넓힌다.

**cppcheck** 는 C/C++ 전용 오픈소스 정적분석기로:

- `apt-get install cppcheck` 로 단일 바이너리 설치 (이미지 증가 +30MB)
- 컴파일 없이(`parse-only`) 분석 가능 — 빌드 시스템 의존성 없음
- JSON/XML 출력 지원
- **Semgrep 과 독립적으로 동작** — 서로의 결과를 오염시키지 않음
- 운영 리스크 🟢 낮음 (apt 단순 설치, Docker 전환 불필요)

SCAManager 의 기존 정적분석 확장 패턴(Phase C 의 eslint/shellcheck)을 그대로 재사용한다. 신규 파일 1개(`src/analyzer/tools/cppcheck.py`) + import 1줄 추가 + nixpacks.toml aptPkgs 1줄 추가. 백엔드 데이터 모델·API·UI 전부 불변.

## 2. 범위 결정 사항 (브레인스토밍 결과)

| 항목 | 결정 |
|------|------|
| 도구 선정 | cppcheck (Phase D.1 — STATE.md 잔여 과제 표 1순위) |
| 설치 방식 | apt `cppcheck` (nixpacks.toml `aptPkgs` 에 추가) |
| 대상 언어 | `c` + `cpp` (이미 `language.py` 에 감지됨) |
| 출력 포맷 | `--xml --xml-version=2` (JSON 포맷은 버전별 차이가 크고 stdlib `xml.etree` 로 견고하게 파싱 가능) |
| 활성화 체크 | `--enable=warning,style,performance,portability` (정보성 낮은 `information`/`unusedFunction`/ `missingInclude` 는 제외 — 노이즈 방지) |
| Severity 매핑 | `error` → `error`, 그 외(`warning`/`style`/`performance`/`portability`) → `warning` |
| Category 분류 | `category="code_quality"` 고정 (cppcheck 는 보안 특화 도구가 아님. 보안 분석은 Semgrep security rules 담당) |
| 타임아웃 | `STATIC_ANALYSIS_TIMEOUT` 상수 재사용 (Semgrep·ESLint·ShellCheck 와 동일 30초) |
| 플랫폼 지정 | `--platform=unix64` 고정 — 멀티 플랫폼 분석은 Phase D 범위 밖 |
| stderr 용도 | cppcheck 는 결과를 **stderr** 에 출력(XML 포함). stdout 은 progress bar. `stderr` 를 파싱 |
| 바이너리 미존재 대응 | `shutil.which("cppcheck") is None` → `is_enabled()=False` → 조용히 skip (기존 Analyzer 패턴) |

## 3. 아키텍처

단일 파일 신설 + 도구 자동 등록 재사용.

```
src/analyzer/tools/cppcheck.py   ← 신규 (shellcheck.py 와 대칭)
src/analyzer/static.py            ← import 1줄 추가
nixpacks.toml                     ← aptPkgs 에 "cppcheck" 1줄 추가
tests/test_analyzer_tools_cppcheck.py  ← 신규 — subprocess mock 기반 단위 테스트
```

**불변 제약**:

- `registry.py` (Analyzer Protocol) 불변
- `static.py` 의 `analyze_file()` 로직 불변 — cppcheck 이 자동으로 REGISTRY 에 합류
- `AnalysisIssue` dataclass 구조 불변
- 점수 계산(`calculator.py`) 불변 — `CQ_WARNING_CAP=25` 통합 cap 이 cppcheck 이슈도 동일 처리
- `language.py` 감지 규칙 불변 (`c` / `cpp` 이미 존재)

## 4. 컴포넌트 — `_CppCheckAnalyzer` 상세

`src/analyzer/tools/cppcheck.py` 구조 (shellcheck.py 와 거의 동일, XML 파싱만 차이):

```python
"""cppcheck static analysis tool — C/C++ 정적분석 (Phase D.1)."""
from __future__ import annotations

import logging
import shutil
import subprocess  # nosec B404
import xml.etree.ElementTree as ET

from src.analyzer.registry import AnalyzeContext, AnalysisIssue, register
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)


class _CppCheckAnalyzer:
    name = "cppcheck"
    category = "code_quality"

    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"c", "cpp"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        return shutil.which("cppcheck") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """cppcheck XML 출력을 파싱해 이슈 목록 반환.

        - stderr 가 XML 출력 채널(cppcheck 관례)
        - `--enable=warning,style,performance,portability` — information 제외
        - severity=error 만 error, 나머지는 warning
        """
        try:
            r = subprocess.run(  # nosec B603 B607
                [
                    "cppcheck",
                    "--xml", "--xml-version=2",
                    "--enable=warning,style,performance,portability",
                    "--platform=unix64",
                    "--inline-suppr",   # 파일 내부 주석 suppress 존중
                    "--quiet",
                    ctx.tmp_path,
                ],
                capture_output=True, text=True, timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            # cppcheck XML 은 stderr 로 출력
            if not r.stderr.strip():
                return []
            return _parse_cppcheck_xml(r.stderr, ctx.language)
        except subprocess.TimeoutExpired:
            logger.warning("cppcheck timed out for %s", ctx.tmp_path)
            return []
        except (OSError, ET.ParseError) as exc:
            logger.warning("cppcheck failed for %s: %s", ctx.tmp_path, exc)
            return []


def _parse_cppcheck_xml(xml_text: str, language: str) -> list[AnalysisIssue]:
    """cppcheck XML v2 결과를 AnalysisIssue 목록으로 변환한다."""
    root = ET.fromstring(xml_text)  # nosec B314 — 로컬 생성 XML 신뢰 가능
    issues: list[AnalysisIssue] = []
    for err in root.findall(".//error"):
        sev = err.get("severity", "warning")
        severity = "error" if sev == "error" else "warning"
        message = err.get("msg", "") or err.get("verbose", "") or err.get("id", "")
        line = 0
        loc = err.find("location")
        if loc is not None:
            try:
                line = int(loc.get("line", "0"))
            except (TypeError, ValueError):
                line = 0
        issues.append(AnalysisIssue(
            tool="cppcheck",
            severity=severity,
            message=message,
            line=line,
            category="code_quality",
            language=language,
        ))
    return issues


def _register_cppcheck_analyzers() -> None:
    register(_CppCheckAnalyzer())


_register_cppcheck_analyzers()
```

**핵심 포인트**:

- **stderr 파싱**: cppcheck 의 XML 은 stdout 이 아니라 **stderr** 로 출력됨 (도구 관례). 이 점이 Semgrep/ShellCheck 와 달라 주의 필요.
- **`xml.etree.ElementTree` 사용**: Python 표준 라이브러리. 외부 의존성 없음. `<error>` 요소 내 `severity`/`msg`/`<location line=>` 속성 추출.
- **`_parse_cppcheck_xml` 분리**: 테스트 용이성을 위해 파싱 함수를 모듈 레벨 private 함수로 추출. subprocess mock 없이도 XML 픽스처로 직접 검증 가능.
- **nosec B314**: cppcheck 는 로컬에서 생성한 XML 이므로 XXE 공격 불가 — Bandit 경고 억제.

## 5. 데이터 플로우 (변경 없음)

cppcheck 는 기존 파이프라인에 **자동 합류** — 별도 호출 필요 없음.

```
run_analysis_pipeline
  → analyze_file(filename=".c"/.cpp", content=...)
      → detect_language() → "c" / "cpp"
      → tempfile 생성 (suffix=".c"/".cpp")
      → for analyzer in REGISTRY:       # semgrep, cppcheck, ...
          if analyzer.supports(ctx) and analyzer.is_enabled(ctx):
              result.issues.extend(analyzer.run(ctx))
      → StaticAnalysisResult
  → calculate_score()
      → CQ_WARNING_CAP=25 통합 cap — cppcheck 이슈도 동일 처리
```

**점수 영향**:

- cppcheck `error` → `code_quality -3`
- cppcheck `warning`/`style`/`performance`/`portability` → `code_quality -1`
- `CQ_WARNING_CAP=25` 에 Semgrep·cppcheck 합산 감점이 한도에 도달하면 중단

## 6. 배포 (nixpacks.toml 1줄 변경)

```toml
# nixpacks.toml
[phases.setup]
aptPkgs = ["nodejs", "npm", "shellcheck", "cppcheck"]   # cppcheck 추가
```

- 이미지 크기 증가: **+30MB** (Ubuntu 22.04 기준)
- Docker 전환 불필요 — nixpacks aptPkgs 로 충분
- `railway.toml` 의 `buildCommand` 불변 (eslint 전역 설치만 담당)

**주의사항 (CLAUDE.md 규약)**:

- `nixpacks.toml` 변경 시 `nixPkgs` 배열을 **추가하지 않음** — Python provider 의 nix 자동 설치(python3 + pip) 를 완전히 교체하는 함정이 있음. 반드시 `aptPkgs` 사용.

## 7. 테스트

### 7-1. 단위 테스트 — `tests/test_analyzer_tools_cppcheck.py` (신규)

XML 픽스처 기반으로 `_parse_cppcheck_xml` 을 검증하고, `subprocess.run` mock 으로 `_CppCheckAnalyzer.run` 의 end-to-end 동작을 검증한다.

**필수 테스트 케이스 (최소 7개)**:

| 테스트 | 검증 대상 |
|--------|----------|
| `test_supports_c_and_cpp` | `supports(ctx)` 가 `c`/`cpp` 에만 True |
| `test_supports_rejects_other_langs` | `supports(ctx)` 가 `python`/`shell`/`unknown` 에 False |
| `test_is_enabled_when_binary_missing` | `shutil.which("cppcheck") is None` → `is_enabled()=False` |
| `test_is_enabled_when_binary_present` | `shutil.which` mock return → `is_enabled()=True` |
| `test_parse_xml_extracts_error_severity` | `<error severity="error">` → `AnalysisIssue.severity="error"` |
| `test_parse_xml_maps_style_to_warning` | `severity="style"`/`"performance"` → `"warning"` 로 매핑 |
| `test_parse_xml_extracts_line_from_location` | `<location line="42">` → `AnalysisIssue.line=42` |
| `test_parse_xml_empty_input_returns_empty` | stderr=`""` 또는 `<results><errors/></results>` → `[]` |
| `test_run_returns_empty_on_timeout` | `subprocess.TimeoutExpired` → `[]` + warning log |
| `test_run_returns_empty_on_oserror` | `OSError` → `[]` + warning log |
| `test_run_uses_stderr_not_stdout` | mock 의 stderr 에 XML, stdout 비어있어도 파싱 성공 |

**XML 픽스처 예시**:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<results version="2">
  <errors>
    <error id="nullPointer" severity="error" msg="Null pointer dereference">
      <location file="test.c" line="10"/>
    </error>
    <error id="variableScope" severity="style" msg="Variable scope can be reduced">
      <location file="test.c" line="25"/>
    </error>
  </errors>
</results>
```

### 7-2. 회귀 테스트

- `tests/test_static_analysis.py` — 기존 C/C++ 분석 테스트가 Semgrep + cppcheck 양쪽 결과 병합을 예상하도록 업데이트 (cppcheck 바이너리 없는 테스트 환경에서는 Semgrep 결과만 나옴 — `is_enabled()=False` 로 조용히 skip 되므로 기존 테스트 깨지지 않음)
- `tests/test_analyzer_registry.py` — REGISTRY 에 cppcheck 등록 여부 검증 추가

### 7-3. 통합 검증

- **로컬 수동**: 실제 `.c` 파일(예: null pointer dereference 샘플)을 `analyze_file()` 에 입력해 cppcheck 이슈가 결과에 포함되는지 확인
- **E2E**: 불필요 (analyzer 레이어는 UI 무관)

## 8. 오류 처리

| 시나리오 | 동작 |
|----------|------|
| cppcheck 바이너리 미설치 | `is_enabled()=False` → 조용히 skip (파이프라인 무중단) |
| cppcheck 실행 타임아웃 | `TimeoutExpired` → `[]` + warning log (`logger.warning("cppcheck timed out for %s")`) |
| XML 파싱 실패 | `ET.ParseError` catch → `[]` + warning log |
| cppcheck 비정상 종료 (exit code ≠ 0) | `check=False` 로 예외 미발생. stderr 에 XML 이 있으면 정상 파싱, 없으면 `[]` |
| 매우 큰 C++ 파일 | `STATIC_ANALYSIS_TIMEOUT=30s` 로 bounded. 분석 중단되어도 Semgrep 결과는 유지 |

## 9. 범위 밖 (의도적 제외)

| 항목 | 제외 사유 | 권고 |
|------|----------|------|
| `--enable=information` 활성화 | 노이즈 (unused function, missing include 등) | Repo 별 설정으로 장기적 opt-in 고려 |
| `--enable=unusedFunction` | 단일 파일 분석이므로 false positive 높음 (import 관계 파악 불가) | 범위 밖 |
| MISRA C 룰셋 | 유료 또는 별도 라이선스 파일 필요 | 엔터프라이즈 티어 고민 |
| 다중 플랫폼 (`unix32`, `win64`) | 분석 시간 2~3 배 증가 | 필요 시 Repo 설정으로 추가 |
| CMake/Make 프로젝트 단위 분석 | `static.py` 는 파일 단위 분석 설계 — 프로젝트 단위는 파이프라인 재설계 필요 | Phase E 이후 |
| C# 전용 도구 (Roslyn Analyzers) | Phase D 범위 외 (STATE.md 잔여 표) | 별도 Phase |

## 10. 자가 리뷰 체크리스트

- [x] Placeholder 없음 — 전체 섹션 완결
- [x] 내부 일관성 — stderr 파싱 선택이 "핵심 포인트"와 오류 처리 섹션에 일관 반영됨
- [x] Scope 적절 — 단일 파일 신설 + nixpacks 1줄 + 테스트 1파일. 백엔드 불변.
- [x] 모호성 없음 — `--enable` 플래그 구체 명시, severity 매핑 규칙 표 기반
- [x] Phase D 결정 사항 3개 반영 — GO/NO-GO 개별 승인 요구 / Docker 전환 불필요 명시 / 우선 착수 도구 (cppcheck) 명시
- [x] 기존 Analyzer 패턴 준수 — shellcheck.py 와 같은 `_register_*()` + 자동 import 패턴
- [x] CLAUDE.md "Analyzer tools 자동 등록" 주의사항 반영 — `static.py` 에 import 1줄 추가 명시

## 11. 승인 요청

**Phase D.1 착수 GO/NO-GO 결정 필요**:

1. ✅ cppcheck 도구 선정 승인 (STATE.md 1순위 + 🟢 낮은 리스크)
2. ✅ `nixpacks.toml aptPkgs` 에 `cppcheck` 추가 — 이미지 +30MB 수용
3. ✅ `--enable=warning,style,performance,portability` 활성 수준 수용 (노이즈 최소화)
4. ✅ category 전부 `code_quality` 로 분류 — 보안 분석은 Semgrep 에 위임

승인 후 본 스펙을 Task-by-Task 실행 플랜(`docs/superpowers/plans/2026-04-2X-cppcheck.md`)으로 변환해 TDD 순서로 구현한다. 예상 Task: 단위 테스트 선작성 → `_CppCheckAnalyzer` 구현 → `static.py` import → nixpacks.toml 갱신 → CLAUDE.md/STATE.md/language-coverage.md 갱신 → 배포 검증 (~6~8 Task, ~2~3 시간).
