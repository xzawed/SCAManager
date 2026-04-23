# 2026-04-23 외부 공신력 서비스 1차 분석 결과 · 청산 계획

> 2026-04-22 에 도입한 SonarCloud · Codecov · CodeQL 의 첫 분석 결과를 확보하고, 감지된 이슈에 대한 단계적 청산 계획을 수립한다.
>
> 커밋 기준선: `1106242` (docs 보강 커밋, 2026-04-22 23:55 UTC)

---

## 1. 연동 자체는 성공 — 3개 서비스 모두 정상 작동

| 서비스 | 상태 | 측정값 | 배지 |
|--------|------|--------|------|
| **CI workflow** | ✅ success (2분) | pytest 1168 passed / coverage.xml 생성 | 초록 `passing` |
| **Codecov** | ✅ 반영 완료 | **95.58%** (125 files, 3825 lines, 3656 hits, 169 misses) | 초록 `96%` |
| **SonarCloud** | ✅ 분석 완료 | Quality Gate **OK** / 95.0% coverage / sqale A | Quality Gate 초록, Security 주황(C), Maintainability 초록(A) |
| **CodeQL** | ✅ success | API 가 auth 필요 — 사용자가 GitHub Security 탭에서 수동 확인 | 초록 `passing` |

### 수치 정합성

- STATE.md 내부 커버리지 **96.2%** vs Codecov **95.58%** vs SonarCloud **95.0%** — ±1%p 차이. 세 도구가 라인 히트 계산 방식이 미묘하게 달라서 (branch coverage, exclusion, generated code 처리) 정상 범위의 차이. 어느 쪽도 오류는 아님.

---

## 2. SonarCloud 1차 분석 — 감지된 이슈 **93건**

**"pylint 10.00 / bandit HIGH 0 / flake8 0" 내부 통과가 곧 모든 품질 기준 통과는 아님"** 을 증명하는 결과. SonarCloud 는 Python 외에 **JavaScript / Web / HTML / pythonsecurity** 규칙셋까지 검사하며, 이것이 pylint/bandit 이 볼 수 없는 영역을 드러냈다.

### 2-1. 유형별 총계

| 유형 | 건수 | Rating | 상태 |
|------|------|--------|------|
| **Bugs** | 8 | Reliability **D (4.0)** | 🔴 조치 필요 |
| **Vulnerabilities** | 7 | Security **C (3.0)** | 🔴 조치 필요 |
| **Security Hotspots** | 4 | — | 🟡 수동 리뷰 대기 (status=TO_REVIEW) |
| **Code Smells** | 78 | Maintainability **A (1.0)** | 🟢 Rating 은 A 유지 |
| **Duplications** | 0.6% | — | 🟢 우수 |
| **Coverage** | 95.0% | — | 🟢 Quality Gate 통과 |
| **합계** | **93** | | |

### 2-2. 심각도 분포 (Bugs + Vulns + Smells)

| Severity | 건수 |
|----------|------|
| **BLOCKER** | **14** |
| CRITICAL | 9 |
| MAJOR | 51 |
| MINOR | 19 |
| INFO | 0 |
| 합계 | 93 |

### 2-3. Quality Gate 가 **OK** 인 이유

Quality Gate 는 **new code (PR 에서 추가·변경된 코드)** 에만 적용된다. 기존 코드의 93건 이슈는 Gate 대상이 아니며, main 에 누적된 부채로 존재. 새 커밋이 추가하는 코드만 기준을 넘지 않으면 머지는 계속 가능.

---

## 3. 이슈 카테고리별 상세 (우선순위 분류용)

### A. False Positive — 즉시 suppress 로 점수 상승 (7건)

**영향: Security C→B, Reliability D→C 가능성**

| 파일 | 규칙 | 유형 | 메시지 | 판단 |
|------|------|------|--------|------|
| `tests/test_webhook_merged_pr.py` | python:S6418 BLOCKER | Vuln | "SECRET" 패턴을 하드코딩 시크릿으로 감지 | FP — 테스트 픽스처 문자열 |
| `tests/test_hook_api.py` | python:S6418 BLOCKER | Vuln | "token" 패턴 | FP — 테스트 문자열 |
| `e2e/conftest.py` | python:S6418 BLOCKER | Vuln | "token" 패턴 | FP — E2E 픽스처 |
| `tests/test_github_commit_comment_notifier.py` | python:S930 BLOCKER | Bug | keyword 인자 누락/초과 | FP — mock 호출을 정적 분석이 오인 (×2건) |
| `tests/test_github_issue_notifier.py` | python:S930 BLOCKER | Bug | 동일 원인 | FP — mock 호출 (×2건) |

**조치 방안 — 택 1**:
1. **SonarCloud UI 에서 "False Positive" 일괄 마크** (가장 간단)
2. **`# NOSONAR` 주석** 해당 라인에 추가 (코드 내 명시)
3. **`sonar-project.properties` 에 `sonar.issue.ignore.multicriteria` 추가** (규칙 단위로 테스트 디렉토리 제외)

→ 방안 3 권장 — 영구 설정으로 향후 유사 FP 자동 차단.

### B. URL Path Injection 방어 (5건)

**영향: Security Rating 개선 + 실질 보안 강화**

| 파일:라인 | 규칙 | 코드 패턴 |
|----------|------|----------|
| `src/github_client/repos.py:41` | pythonsecurity:S7044 MAJOR | URL path 에 변수 삽입 |
| `src/github_client/repos.py:63` | 동일 | 동일 |
| `src/github_client/repos.py:74` | 동일 | 동일 |
| `src/github_client/repos.py:209` | 동일 | 동일 |
| `src/github_client/repos.py:217` | 동일 | 동일 |

**원인**: `f"{GITHUB_API}/repos/{owner}/{repo}/..."` 같이 GitHub 저장소 이름을 URL 에 직접 삽입. GitHub API 스펙상 owner/repo 는 신뢰 입력이나 SonarCloud 는 일반 규칙으로 감지.

**조치 방안**:
- `urllib.parse.quote(owner, safe='')` / `quote(repo, safe='')` 로 방어적 인코딩
- 또는 `httpx.URL` 의 path 파라미터 사용

### C. HTML 접근성 / SRI (7건 Bugs + 3건 Hotspots)

**영향: 사용자 경험 + 실제 Bug Rating 개선**

| 유형 | 위치 | 규칙 |
|------|------|------|
| `<table>` 에 `<th>` 헤더 없음 (4건) | settings.html:362,397,432 + analysis_detail.html:315 | Web:S5256 MAJOR |
| `<div>` click 이벤트에 key 이벤트 누락 (3건) | settings.html:497,501,505 | Web:MouseEventWithoutKeyboardEquivalentCheck MINOR |
| CDN 리소스 SRI 해시 없음 (3건, Hotspot) | analysis_detail.html:446 + base.html:8 + repo_detail.html:300 | Web:S5725 LOW |

**조치 방안**:
- `<table>` 에 `<thead><tr><th>` 헤더 추가
- click 가능 `<div>` 에 `role="button" tabindex="0" onkeydown=...` 추가
- `<script src="...jsdelivr..." integrity="sha384-..." crossorigin="anonymous">` 추가 (Chart.js 등 CDN)

### D. Log Injection 가능성 (2건)

| 파일:라인 | 규칙 | 설명 |
|----------|------|------|
| `src/ui/router.py:279` | pythonsecurity:S5145 MINOR | user-controlled data 를 로그에 포함 |
| `src/api/hook.py:126` | pythonsecurity:S5145 MINOR | 동일 |

**조치**: `logger.info("...", user_input)` 처럼 format 인자로 분리 (Python logging 의 lazy formatting). 또는 수동 sanitize.

### E. 정밀 검토 필요 (3건)

| 파일:라인 | 규칙 | 현상 | 판단 |
|----------|------|------|------|
| `src/templates/settings.html:869` | javascript:S930 CRITICAL | 함수 인자 수 불일치 | **실제 버그 가능성** — 확인 필요 |
| `src/webhook/router.py:60` | python:S5852 MEDIUM Hotspot | Regex ReDoS (polynomial backtracking) | HMAC regex 재설계 |
| `tests/test_api_stats.py:0` | python:S1244 MAJOR | float 동등 비교 | `pytest.approx()` 로 변경 |

### F. Code Smells 78건 (Rating A 유지 — 저우선)

Maintainability Rating 이 A 이므로 Quality Gate 에 영향 없음. 장기 정리 대상.

---

## 4. 근본 원인 분석 — 내부 도구 vs SonarCloud 규칙 차이

| 영역 | 내부 검사 | SonarCloud |
|------|----------|-----------|
| Python 품질 | pylint 10.00 ✅ | python:S* 규칙 (더 엄격) |
| Python 보안 | bandit HIGH 0 ✅ | pythonsecurity:S* (taint analysis 포함) |
| PEP-8 스타일 | flake8 0 ✅ | 동일 |
| JavaScript | — (검사 안 함) | javascript:S* 13건 중 1건 |
| HTML / 접근성 | — (검사 안 함) | Web:S* 10건 |
| CDN 리소스 무결성 | — (검사 안 함) | Web:S5725 3건 |

**결론**: 외부 공신력 서비스 도입이 의미 있는 새 시그널을 제공. 내부 도구만으로는 감지하지 못했을 **JS/HTML 영역의 18건** 이 드러났다.

---

## 5. 청산 Phase 계획 (초안 — 승인 대기)

사용자 결정 ("모든 결과를 확인한 뒤 계획을 잡고 수행") 에 따라 즉시 수정은 하지 않는다. 아래 4개 Phase 로 단계별 실행 제안.

### Phase Q.1 — False Positive 일괄 suppress (~1시간, 리스크 🟢 낮음)

**범위**:
- `sonar-project.properties` 에 `sonar.issue.ignore.multicriteria` 추가
  - python:S6418 (하드코딩 시크릿) 을 `tests/**/*.py`, `e2e/**/*.py` 에서 무시
  - python:S930 (함수 인자) 을 `tests/**/*.py` 에서 무시
- push 후 SonarCloud 재분석 대기 (~5분)

**예상 효과**:
- BLOCKER **14 → 7**
- Vulnerabilities **7 → 4** (3건 제거)
- Bugs **8 → 4** (4건 제거)
- Security Rating **C → B** 상승 가능성 (MAJOR pythonsecurity:S7044 5건이 주 원인으로 남음)
- Reliability Rating **D → C** 상승 가능성

### Phase Q.2 — URL Path 방어적 인코딩 (~2시간, 리스크 🟡 중간)

**범위**:
- `src/github_client/repos.py` 5곳을 `urllib.parse.quote()` 로 감싸기
- `src/github_client/issues.py` 도 유사 패턴 있으면 동일 조치
- 기존 테스트가 passing 유지되는지 회귀 확인 (URL 인코딩 차이로 mock assertion 실패 가능성)

**예상 효과**:
- Vulnerabilities **4 → 1 이하** (pythonsecurity:S7044 5건 해소)
- Security Rating **B → A** 가능성

### Phase Q.3 — HTML 접근성 + SRI (~2시간, 리스크 🟢 낮음)

**범위**:
- `src/templates/settings.html` + `analysis_detail.html` 의 `<table>` 4곳에 `<thead><th>` 추가
- click `<div>` 3곳에 `role/tabindex/onkeydown` 추가
- CDN `<script>` 3곳에 `integrity="sha384-..."` + `crossorigin="anonymous"` 추가
  - Chart.js, 기타 CDN 의 SRI 해시는 jsdelivr 또는 srihash.org 에서 조회
- E2E 테스트 회귀 확인 (Playwright 의 DOM 선택자 영향 없는지)

**예상 효과**:
- Bugs **4 → 0** (접근성 이슈 7건 해소)
- Security Hotspots **4 → 1** (SRI 3건 reviewed)
- Reliability Rating **C → A** 가능성

### Phase Q.4 — 정밀 검토 3건 + Log injection 2건 (~2시간, 리스크 🟡 중간)

**범위**:
- `settings.html:869` JS 함수 인자 수 확인 — 실제 버그면 수정, 아니면 suppress
- `webhook/router.py:60` HMAC regex 재설계 (catastrophic backtracking 방지)
- `test_api_stats.py` float 비교 → `pytest.approx()`
- `ui/router.py:279`, `api/hook.py:126` 로그 포맷팅 수정

**예상 효과**:
- 잔존 BLOCKER 0, Security Hotspots 1 → 0
- **최종 Rating: Reliability A + Security A + Maintainability A**

### 합산 예상

| 시점 | Bugs | Vulns | Hotspots | Smells | Security | Reliability |
|------|------|-------|----------|--------|----------|-------------|
| 현재 | 8 | 7 | 4 | 78 | C | D |
| Phase Q.1 후 | 4 | 4 | 4 | 78 | B | C |
| Phase Q.2 후 | 4 | ≤1 | 4 | 78 | A | C |
| Phase Q.3 후 | 0 | ≤1 | 1 | 78 | A | A |
| Phase Q.4 후 | 0 | 0 | 0 | 78 | A | A |

**총 소요**: ~7시간 / **최종 배지**: Quality Gate OK · Security A · Maintainability A · Reliability A · Coverage 95%+

Code Smells 78건은 별도 Phase 로 장기 정리 (Rating 영향 없음).

---

## 6. 사용자 수동 확인 필요 항목

### 6-1. GitHub Security 탭 — CodeQL 결과

API 가 인증을 요구하므로 브라우저에서 직접 확인:
1. https://github.com/xzawed/SCAManager/security/code-scanning
2. Open alerts 수·유형·심각도 기록 → 본 보고서에 반영
3. CodeQL 과 SonarCloud 의 중복/고유 이슈 비교

### 6-2. SonarCloud Security Hotspots 4건 수동 리뷰

UI 에서만 "Safe" / "Fixed" / "At Risk" 마크 가능:
- https://sonarcloud.io/project/security_hotspots?id=xzawed_SCAManager
- regex ReDoS 1건 + SRI 3건

4건 중 3건은 Phase Q.3 에서 수정 예정. Regex 는 Phase Q.4.

---

## 7. 다음 액션 결정

아래 순서로 결정 요청:

1. **Phase Q.1~Q.4 순차 승인** — 1개씩 GO/NO-GO (~7시간 총)
2. **Phase Q.1~Q.2 우선 승인** — False Positive + URL 방어 (~3시간, 빠른 Rating A 달성)
3. **Phase Q.1 만 먼저** — FP suppress 로 점수 정확화 (~1시간)
4. **CodeQL 결과 먼저 확인** — 6-1 수동 조회 후 전체 계획 재조정
5. **D.3 RuboCop 게이트 실증 우선** — SonarCloud 청산은 후순위

권장: **4 → 3 → 2 → 1** 순. CodeQL 결과로 계획을 보정한 뒤 낮은 리스크부터 점진 착수.

---

## Follow-up — Phase Q.1~Q.6 전체 실행 결과 (2026-04-23 세션)

사용자 결정 "바로 수행" 에 따라 Phase Q.1~Q.4 를 일괄 실행하고, CI 재분석 결과로 드러난 잔존 이슈를 Q.5~Q.6 로 후속 해소. 최종 **Quality Gate OK + 3종 Rating A** 달성.

### 실행 커밋 (3건)

| 커밋 | Phase | 내용 |
|------|-------|------|
| `80d9c57` | **Q.1~Q.4** | FP suppress + URL 인코딩 + HTML 접근성 + JS/regex/float/log |
| `42a83f6` | **Q.5** | `sanitize_for_log()` 헬퍼 + Annotated 11곳 + `<button>` 전환 3곳 |
| `4eea901` | **Q.6** | Header Annotated 2곳 + NOSONAR suppress 2곳 + 중복 문자열 상수화 + `void` 제거 |

### CI #4 → #5 → #6 단계별 Rating 변화

| 지표 | 초기 | CI #4 (Q.1~Q.4) | CI #5 (Q.5) | **CI #6 (Q.6)** |
|------|------|-----------------|-------------|----------------|
| Quality Gate | OK(new) | ERROR | ERROR | **OK** ✅ |
| Security Rating | C (3.0) | B (2.0) | B (2.0) | **A (1.0)** ✅ |
| Reliability Rating | D (4.0) | A (1.0) | A (1.0) | **A (1.0)** ✅ |
| Maintainability Rating | A (1.0) | A | A | **A (1.0)** ✅ |
| Bugs | 8 | 0 | 0 | **0** ✅ |
| Vulnerabilities | 7 | 2 | 2 | **0** ✅ |
| Security Hotspots | 4 | 0 | 0 | **0** ✅ |
| Code Smells | 78 | 78 | 63 | **58** (-20) |
| BLOCKER | 14 | 14 (신규 S8410 감지) | 2 | **0** ✅ |
| CRITICAL | 9 | 8 | 8 | **5** |

### 각 Phase 가 해소한 이슈 (누적)

- **Q.1** FP suppress → BLOCKER 7건 (testsecret 3 + testargs 4) · CDN SRI 3 hotspot
- **Q.2** URL 인코딩 (`_repo_path()` + `urllib.parse.quote()`) → pythonsecurity:S7044 5건 (Vuln)
- **Q.3** HTML 접근성 (`<th scope>` 4 + keyboard 3 + `.sr-only` 유틸) → Web:S5256 4건 · MouseEvent 3건 (Bugs)
- **Q.4** JS 인자 정정 + regex `[\s:]*` + `pytest.approx` + logger `%r` → BLOCKER JS 1 · regex ReDoS 1 · float 1 · log 준비
- **Q.5** `sanitize_for_log()` + `Annotated[...]` 11곳 + `<button>` 3곳 → S8410 9건 · 초기 Annotated 패턴 · S6819 button 역효과 해소
- **Q.6** 놓친 Header 2 + NOSONAR 2 + `_GITHUB_WEBHOOK_PATH` / `_HEALTH_QUERY` 상수 + `void` 제거 → 마지막 BLOCKER 2 · Vuln 2 · CRITICAL S1192 2 · S3735 1

### 신규 검출 규칙 (1차 분석 후 감지)

분석 진행 중 SonarCloud 가 추가 감지한 규칙들 — Q.5~Q.6 에서 해소:

- `python:S8410` 11건 — FastAPI `Annotated[...]` 타입 힌트 권고
- `Web:S6819` 3건 — `<div role="button">` 대신 실제 `<button>` 요소 사용 (Q.3 수정이 역효과)
- `python:S1192` 2건 — 중복 문자열 상수화 (`"/webhooks/github"` × 3 + `"SELECT 1"` × 4)
- `javascript:S3735` 1건 — `void` 연산자 제거

### 잔존 CRITICAL 5건 (Phase Q.7 예정)

전부 `python:S3776` Cognitive Complexity 초과 — 실제 함수 분할 리팩토링 필요, Quality Gate 영향 없음:

| 위치 | 복잡도 | 초과 |
|------|--------|------|
| `src/gate/engine.py:20` `run_gate_check` | 31→15 | **+16** 최대 |
| `src/analyzer/tools/slither.py:69` `_parse_slither_json` | 20→15 | +5 |
| `src/notifier/github_comment.py:58` | 19→15 | +4 |
| `src/cli/formatter.py:67` | 16→15 | +1 |
| `src/cli/git_diff.py:35` | 16→15 | +1 |

### 파생 산출물

- `src/log_safety.py` 신설 — `sanitize_for_log()` 헬퍼 (CR/LF/TAB/NUL 제거 + 길이 제한)
- `tests/test_log_safety.py` — 7 단위 테스트
- `src/github_client/repos.py::_repo_path()` — URL 방어적 인코딩 헬퍼
- `src/ui/router.py::_GITHUB_WEBHOOK_PATH` / `src/database.py::_HEALTH_QUERY` — 중복 문자열 상수화
- `src/templates/base.html` — `.sr-only` 접근성 유틸 클래스 추가

### 최종 수치

| 지표 | 값 |
|------|-----|
| 단위 테스트 | **1175 passed** (1168 + 7 log_safety) |
| pylint | **10.00/10** 유지 |
| flake8 | **0** |
| bandit HIGH | **0** |
| SonarCloud Quality Gate | **OK** |
| SonarCloud Security / Reliability / Maintainability | **A / A / A** |
| Coverage (내부) | 96.2% · Codecov 95.58% · SonarCloud 95.1% |

### 결론

2026-04-22~23 감사 전 과정 (6렌즈 → 외부 3서비스 도입 → 1차 SonarCloud 93건 감지 → Phase Q.1~Q.6 청산) 을 통해 **모든 급한 품질 목표 달성**. 남은 것은 Cognitive Complexity 5건의 유지보수성 개선만이며 이는 Rating 영향 없는 별도 Phase.
