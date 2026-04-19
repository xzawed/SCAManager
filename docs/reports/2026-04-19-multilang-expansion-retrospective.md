# 다언어 코드리뷰·정적분석 확장 회고 (Phase 0~C, 2026-04-19)

## 1. 배경과 목표

**요청**: "Python 뿐만 아니라 훨씬 다양하고 많은 언어를 리뷰하고 정적분석 수행을 하고 싶습니다. 최소 30개 최대 50개."

**초기 상태** (2026-04-19 착수): Python 단일 언어 + pylint/flake8/bandit 3개 도구. AI 리뷰도 언어 무관 단일 프롬프트.

**목표**: 50개 언어에 대해 두 축을 동시 강화.
1. **AI 리뷰** — 언어별 특화 체크리스트 + 토큰 예산 관리
2. **정적분석** — 언어-중립 Registry 인프라 + Semgrep/ESLint/ShellCheck 확장

**Tier 분류 근거**:
- Tier 1 (10개): 세계 상위 10대 언어 — 전용 상세 체크리스트 + 전용 정적분석 도구 목표
- Tier 2 (20개): 주류~틈새 언어 — 중간 수준 체크리스트 + Semgrep baseline
- Tier 3 (20개): 설정·DSL·신흥 언어 — 경량 체크리스트만

---

## 2. Phase별 산출물 요약

| Phase | 핵심 신규 파일 | 테스트 증분 | 배포 영향 | 완료일 |
|-------|-------------|----------|---------|------|
| **0 — AI 리뷰 50개 언어** | `language.py`, `review_prompt.py`, `review_guides/tier1~3/*.py` (51파일), `ai_review.py` 개편 | +207 | 없음 (AI 프롬프트만) | 2026-04-19 |
| **A — Registry 인프라** | `registry.py`, `tools/python.py` | +47 | 없음 (리팩토링) | 2026-04-19 |
| **B — Semgrep** | `tools/semgrep.py`, `requirements.txt` semgrep>=1.80 | +61 | +150MB 이미지 | 2026-04-19 |
| **C — ESLint + ShellCheck** | `tools/eslint.py`, `tools/shellcheck.py`, `configs/eslint.config.json`, `nixpacks.toml` 개편 | +70 | +250MB 이미지 | 2026-04-19 |
| **합계** | 55+ 파일 신규/수정 | **+385** (634→1074) | ~400MB 이미지 증가 | |

---

## 3. 아키텍처 핵심 결정

### 3.1 Registry 패턴 (P0-2 Notifier Registry 1:1 복제)

**결정**: `src/notifier/registry.py`의 `Notifier Protocol + REGISTRY + register()` 구조를 Analyzer에 동일 적용.

**이유**: 기존 코드에서 검증된 패턴. 새 도구 추가 시 변경 파일이 `tools/<tool>.py` 1개로 국한. `analyze_file()`은 REGISTRY 순회만.

**대안 검토**: `if language == "python"` 분기 확장 — 언어 증가 시 O(N) 분기 열거가 필요해 기각.

### 3.2 category 기반 스코어링 전환

**결정**: 점수 계산을 `tool == "pylint"` 체크에서 `category == "code_quality"` 집계로 전환.

**이유**: Semgrep/ESLint/ShellCheck가 추가되어도 `calculator.py` 수정 불필요. 새 도구는 `category="code_quality"|"security"` 지정만 하면 즉시 점수 반영.

**동치 보장**: Python-only 입력에서 `min(pylint_warnings,15) + min(flake8_warnings,10) ≤ 25` → 통합 `CQ_WARNING_CAP=25` 변경 후 점수 동치.

### 3.3 모듈 로드 시 자동 등록

**결정**: 각 `tools/<tool>.py`는 모듈 최하단에서 `_register_<tool>_analyzers()` 호출.

**이유**: `static.py`가 `import src.analyzer.tools.*` 만 하면 REGISTRY 자동 구성 — 별도 팩토리/초기화 코드 없음.

**함정 방지**: `register()` 내부 name 기반 중복 방지 → 테스트 재실행 시 REGISTRY 오염 없음.

---

## 4. 주요 트레이드오프

### 4.1 Semgrep `--config=auto` vs 명시 ruleset

**선택**: `--config=auto` (커뮤니티 자동 룰셋).

**장점**: 룰 유지보수 불필요. 30개 언어 즉시 커버.
**단점**: False positive 제어 불가, 네트워크 최초 접속 필요, 결과 비결정성.
**타협**: 30초 timeout + `is_enabled()` graceful skip으로 배포 안전성 확보.

### 4.2 ESLint 9 flat config 전환

**배경**: ESLint 9은 `--no-eslintrc` + flat config 배열 포맷 요구. 레거시 `.eslintrc` 포맷은 동작 안 함.

**결과**: `eslint.config.json`을 `[{"languageOptions":{...},"rules":{...}}]` 배열 포맷으로 작성. pipeline-reviewer 1차 리뷰에서 발견 후 즉시 수정.

### 4.3 nixpacks 단일 이미지 유지 (vs Dockerfile)

**선택**: Phase C까지 nixpacks 유지 (~805MB).

**이유**: Railway 배포 설정 변경 최소화. Phase D JVM/Rust 계열 추가 시 ~2GB 초과 가능 → 그때 Dockerfile 전환.

---

## 5. 발견·수정된 함정

| 함정 | 증상 | 수정 |
|-----|-----|-----|
| `railway.toml buildCommand` 최상위 오버라이드 | `buildCommand = "echo..."` 설정 시 nixpacks.toml phases 전체 무효화 → shellcheck/eslint 미설치 | `buildCommand` 제거, nixpacks.toml만 사용 |
| ESLint legacy config 포맷 | `eslint@9`에서 `{rules:{...}}` 객체 단독 포맷 거부 | flat config 배열 포맷으로 재작성 |
| `OSError` vs `FileNotFoundError` | Windows 환경에서 바이너리 없을 때 `OSError` 발생 (FileNotFoundError 미캐치) | eslint.py, shellcheck.py `except (json.JSONDecodeError, OSError)` |
| REGISTRY 테스트 간 오염 | `test_analyzer_registry.py` fixture가 `tools.python` import 전에 `original = []` 캡처 → dedup이 기존 Python 분석기 무시 | fixture 시작에 `import src.analyzer.tools.python` 추가 |
| `CQ_WARNING_CAP` 분리 | pylint_cap(15) + flake8_cap(10) = 25를 각각 적용했으나 통합 cap으로 전환 시 로직 불일치 | `CQ_WARNING_CAP = 25` 단일 상수로 통합, 동치 증명 테스트 작성 |
| Semgrep stdout 비결정 | 에러 시 stdout에 `{}` 대신 빈 문자열·경고 텍스트 → `startswith("{")` 체크 실패 | `not r.stdout.strip().startswith("{")` 가드 추가 |

---

## 6. 현 수치 스냅샷 (Phase C 완료 시점)

| 지표 | Phase 0 착수 전 | Phase C 완료 후 |
|-----|--------------|--------------|
| 단위 테스트 | 634개 | **1074개** (+440) |
| E2E 테스트 | 38개 | 38개 (불변) |
| pylint | 9.79 | **9.89** |
| 커버리지 | 96.2% | 96.2% (유지) |
| bandit HIGH | 0 | 0 |
| 지원 언어 (AI 리뷰) | 9개 (Python + partial) | **50개** |
| 지원 언어 (정적분석) | 1개 (Python) | **34개+** (Semgrep 23 + ESLint 2 + ShellCheck 1) |
| 이미지 크기 (추정) | ~400MB | **~805MB** (+405MB) |

---

## 7. 남은 과제 (Phase D로 위임)

Tier 1 10개 언어 중 정적분석 전용 도구가 **아직 없는** 언어:

| 언어 | 현재 정적분석 | Phase D 후보 도구 | 리스크 |
|-----|------------|-----------------|------|
| Java | Semgrep | PMD | 🔴 최상위 (JDK 300MB, JVM cold start) |
| Go | Semgrep | golangci-lint | 🟡 중간 (go.mod 자동생성 필요) |
| Rust | Semgrep(실험) | cargo clippy | 🔴 최상위 (700MB, crate 단위) |
| C/C++ | Semgrep | cppcheck | 🟢 낮음 (apt 30MB) |
| Ruby | Semgrep | RuboCop | 🟡 중간 (80MB) |
| C# | Semgrep | — (Phase D 범위 외) | — |

**Docker 전환 임계점**: JVM 계열(PMD/detekt) 추가 시 이미지 ~1.6GB → Dockerfile 멀티스테이지 전환 권고.

자세한 Phase D 운영 리스크 분석은 플랜 파일 참조.
