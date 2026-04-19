# Code Quality Audit — 2026-04-19

> **목적**: 직전 Phase(P1~P3) 완료 후 베이스라인 수치(단위 586 / E2E 26 / pylint 9.70 / 커버리지 92%)가 실측으로도 유효한지, 숨은 flakiness·lint drift·보안 회귀가 없는지 7라운드 다각도 감사.
> **범위**: Audit only — 발견된 문제는 이 보고서에 기록. 수정은 별도 Phase로 분리.

---

## Executive Summary

| 지표 | 실측값 | STATE.md 베이스라인 | Δ | 판정 |
|------|--------|-------------------|---|------|
| 단위+통합 테스트 | **586 passed** | 586개 | ±0 | ✅ |
| 커버리지 | **92%** (2052 stmts, 155 miss) | 92% | ±0 | ✅ |
| pylint | **9.70/10** | 9.70 | ±0 | ✅ |
| flake8 위반 | **1건** (E501) | 기록 없음 | — | 🟡 Minor |
| bandit | **비가용** (Python 3.14 비호환) | HIGH 0 | 미측정 | 🟠 경고 |
| Flakiness (3회) | **586/586/586** | — | 완벽한 일관성 | ✅ |
| 격리성 (역순) | **586 passed** | — | 순서 의존 없음 | ✅ |
| E2E (Appendix B) | **29 passed / 9 failed** | 26개 | settings 9건 실패 | 🔴 Major |

**Overall Verdict: 🟡 YELLOW**
- 단위·통합·커버리지·결정성·격리성 모두 GREEN
- settings E2E 9건 실패(UI 재설계 후 테스트 미업데이트) — 단위 테스트에서는 검증 불가한 영역
- bandit 도구 호환 불가 — 보안 정적 분석 공백 존재

---

## Round 1 — 정상성 + 성능 프로파일

**실행**: `python -m pytest tests/ -q --durations=25`
**결과**: 586 passed, 90.11s

### Top 10 느린 테스트

| 순위 | 테스트 | 소요(s) | 비고 |
|------|-------|---------|------|
| 1 | `test_issues_event_with_valid_signature_returns_202` | **11.16** | webhook_issues — 비동기 BackgroundTask 포함 |
| 2 | `test_scenario_b_new_sha_pr_event_creates_analysis_and_calls_gate` | 3.09 | pipeline_pr_regate — 통합 경로 |
| 3 | `test_pr_title_used_as_commit_message` | 2.73 | pipeline |
| 4 | `test_pr_event_calls_full_pipeline` | 2.63 | pipeline |
| 5 | `test_pr_body_included_in_commit_message` | 2.50 | pipeline |
| 6 | `test_db_result_stores_source_pr` | 2.50 | pipeline |
| 7 | `test_pr_empty_body_returns_title_only` | 2.43 | pipeline |
| 8 | `test_push_commit_message_extracted` | 2.16 | pipeline |
| 9 | `test_push_head_commit_preferred` | 2.05 | pipeline |
| 10 | `test_db_stores_commit_message` | 1.94 | pipeline |

**분석**: 1위(`test_issues_event_with_valid_signature_returns_202`)가 2위 대비 3.6배 느림. webhook_issues가 uvicorn BackgroundTask를 동기적으로 기다리는 구조라 긴 대기 발생. pipeline 테스트 상위권 집중은 `analyze_file` subprocess 대기 때문 — 현재 구조상 정상.

---

## Round 2 — 커버리지 분석

**실행**: `python -m pytest tests/ --cov=src --cov-report=term-missing:skip-covered -q`
**결과**: 92% (2052 stmts, 155 miss) — 38 files 100% 완전 커버

### 80% 미만 모듈 (커버리지 갭 집중 영역)

| 모듈 | 커버리지 | 미커버 라인 | 비고 |
|------|---------|------------|------|
| `notifier/payload.py` | **0%** | 2–21 전체 | 코드 존재하나 단 1건도 테스트 없음 |
| `analyzer/static.py` | **71%** | 68, 84–89, 97, 113–121, 140–145 | subprocess 실행 분기, Windows/Linux 경로 |
| `crypto.py` | **71%** | 30–32, 39, 43, 53–58 | 암호화 키 없는 경우, 복호화 실패 경로 |

### 80%~90% 모듈 (주목 영역)

| 모듈 | 커버리지 | 미커버 라인 |
|------|---------|------------|
| `database.py` | 81% | Failover SSL/probe 분기, 에러 핸들러 |
| `ui/router.py` | 84% | 일부 분기, 274–299(삭제 흐름), 321–325 |

### 100% 완전 커버 모듈 (주요)

`webhook/validator.py`, `scorer/calculator.py`, `models/*`, `github_client/models.py`, `github_client/helpers.py`, `notifier/email.py`, `notifier/telegram.py` 등 38개.

---

## Round 3 — 결정성 (3회 반복 실행)

**방법**: 동일 명령(`python -m pytest tests/ -q`) 3회 연속 실행

| 회차 | 결과 | 소요 |
|------|------|------|
| Run 1 (R1 포함) | 586 passed | 90.11s |
| Run 2 | 586 passed | 96.77s |
| Run 3 | 586 passed | 94.80s |

**판정**: ✅ 완벽한 결정성 — 실패 0, 경고 수 57,331건으로 동일. 소요 시간 편차 ±7% (비동기 I/O 정상 범위).

---

## Round 4 — 격리성 (테스트 파일 역순 실행)

**방법**: `ls tests/*.py | sort -r`로 파일 역순 지정 + `tests/integration/` 포함
**결과**: 586 passed, 92.62s

**판정**: ✅ 순서 의존 실패 없음 — 모든 테스트가 서로 독립적으로 실행됨. `asyncio_mode=auto` 환경에서도 fixture 누수 없음.

---

## Round 5 — pylint 의미 기반 정적 분석

**실행**: `pylint src/`
**결과**: **9.70/10** (previous run: 9.70/10, ±0.00)

### 경고 분포 (57건)

| 코드 | 건수 | 설명 | 심각도 |
|------|------|------|--------|
| C0116 | 12 | Missing function docstring | Convention |
| W0718 | 9 | Catching too general Exception | Warning |
| R0917 | 9 | Too many positional arguments (>5) | Refactor |
| R0903 | 6 | Too few public methods in ORM models | Refactor |
| R0914 | 5 | Too many local variables | Refactor |
| R0801 | 3 | Duplicate code (notifier/slack+webhook, dataclass 필드) | Refactor |
| C0115 | 3 | Missing class docstring | Convention |
| R0913 | 2 | Too many arguments | Refactor |
| R0902 | 2 | Too many instance attributes | Refactor |
| **E1102** | **1** | **`func.count is not callable` — `ui/router.py:170`** | **Error** |
| 기타 | 5 | C0415, C0412, C0411, C0301, R0912 | Convention/Refactor |

### 주목 항목

- **E1102 (`ui/router.py:170`)**: pylint가 `func.count` 호출을 "not callable"로 진단. SQLAlchemy `func.count()`는 실제로 호출 가능하나 pylint가 타입 정보 부재로 false-positive 발생. 기능 영향 없음 — 향후 `# pylint: disable=not-callable` nosec 또는 타입 스텁으로 해결 가능.
- **W0718 × 9**: `broad-exception-caught` — `except Exception` 사용. `src/crypto.py`, `src/database.py`, `src/main.py`, `src/analyzer/ai_review.py`. 현재 의도적 설계(알림 파이프라인 견고성)이나 개별 예외 세분화 검토 권장.
- **R0917 × 9**: notifier 함수들의 positional args > 5. keyword-only 강제(`*`) 이미 적용된 함수들 — pylint 설정(max-positional-arguments) 업데이트 또는 dataclass payload 패턴으로 리팩토링 후보.

---

## Round 6 — flake8 스타일/PEP8 검사

**실행**: `flake8 src/ --count --statistics`
**결과**: **1건** 위반

| 파일 | 라인 | 코드 | 내용 |
|------|------|------|------|
| `src/ui/router.py` | 16 | E501 | line too long (123 > 120) |

**판정**: 🟡 Minor — 단 1건, 3자 초과. setup.cfg per-file-ignores에서 `src/ui/router.py`는 E501 예외 처리되어 있지 않음. Quick-fix 가능.

---

## Round 7 — bandit 보안 정적 분석

**실행**: `bandit -r src/ -x alembic -ll -iii`
**결과**: **비가용** — 46개 파일 전체 스캔 실패

### 원인

```
AttributeError: 'Constant' object has no attribute 's'
```

**Python 3.14**에서 `ast.Constant` 노드의 `.s` 속성이 제거됨(Python 3.8 deprecated, 3.14 removed). **bandit 1.8.0**이 해당 속성에 의존하여 전체 AST 방문 중 예외 발생.

### 영향 평가

| 항목 | 내용 |
|------|------|
| 이전 STATE.md 기록 | "bandit HIGH 0" — 이전 Python 버전(3.12 추정)에서 측정 |
| 현재 보안 측정 | **불가** — 스캔 결과 없음 |
| 보안 커버 대안 | 단위 테스트의 보안 관련 테스트(test_auth_github.py CSRF·Jinja2 autoescape, test_telegram_notifier.py HTML escape 등)가 일부 커버 |

### 권장 조치

```bash
# bandit 2.x 이상 (Python 3.14 지원) 설치
pip install "bandit>=2.0.0"
# 또는 requirements.txt 업데이트
bandit==2.0.0  # 버전 확인 후 적용
```

> **CRITICAL**: 현재 Python 3.14 환경에서 보안 정적 분석이 완전히 공백 상태. bandit 업그레이드 또는 대체 도구(Semgrep, Ruff security rules) 도입이 시급.

---

## Appendix A — 환경

| 항목 | 버전 |
|------|------|
| Python | 3.14.2 (MSC v.1944 64-bit, Windows 10) |
| pytest | 8.3.3 |
| pytest-asyncio | 0.24.0 |
| pytest-cov | 설치됨 (버전 미기록) |
| pytest-randomly | **미설치** |
| pylint | 3.3.1 |
| flake8 | 7.1.1 |
| bandit | 1.8.0 (**Python 3.14 비호환**) |
| Playwright | >= 1.44.0 |
| OS | Windows 10 Pro 10.0.19045 |

### Artifact 로그 목록

```
docs/reports/artifacts/2026-04-19/
├── round-1-normal.log          (R1: 기본 통과 + durations)
├── round-2-coverage.log        (R2: 커버리지)
├── round-3-flakiness-run2.log  (R3: 2회차)
├── round-3-flakiness-run3.log  (R3: 3회차)
├── round-4-order.log           (R4: 역순 실행)
├── round-5-pylint.log          (R5: pylint 전체 출력)
├── round-6-flake8.log          (R6: flake8)
├── round-7-bandit.log          (R7: bandit 오류 출력)
└── appendix-b-e2e.log          (Appendix B: E2E)
```

---

## Appendix B — E2E 스모크 (Playwright)

**실행**: `python -m pytest e2e/ -v -p no:asyncio`
**결과**: **29 passed, 9 failed** (393.47s / 6분 33초)

### 실패 목록 (모두 `test_settings.py`)

| 테스트 | 유형 | 원인 추정 |
|--------|------|---------|
| `test_gate_mode_auto_button_click` | UI 요소 탐지 실패 | settings UI 재설계 후 셀렉터 불일치 |
| `test_gate_mode_semi_auto_button_click` | UI 요소 탐지 실패 | 동일 |
| `test_approve_slider_updates_number_input` | UI 요소 탐지 실패 | Progressive Disclosure — 슬라이더 구조 변경 |
| `test_reject_slider_updates_number_input` | UI 요소 탐지 실패 | 동일 |
| `test_approve_threshold_hidden_when_disabled` | UI 요소 탐지 실패 | 프리셋 카드 도입으로 DOM 구조 변경 |
| `test_approve_threshold_visible_when_auto` | UI 요소 탐지 실패 | 동일 |
| `test_telegram_chat_row_visible_only_semi_auto` | UI 요소 탐지 실패 | 설정 카드 재그룹핑 |
| `test_settings_form_submit_redirects` | 제출 흐름 실패 | 폼 구조 변경 |
| `test_gate_mode_persists_after_save` | 상태 저장 실패 | 입력 요소 셀렉터 불일치 |

**원인**: 최근 커밋(`a1aedd1 feat(settings): 모바일 1열 레이아웃 + 프리셋 아코디언 카드 + E2E 통합`)에서 settings UI를 7카드→4카드로 재그룹핑하고 Progressive Disclosure를 도입. `test_settings.py`의 Playwright 셀렉터가 신규 DOM 구조를 반영하지 못함.

**통과 항목**: 내비게이션, 테마 전환, 개요 페이지, 리포 상세 등 29건은 정상.

---

## 발견 사항 및 권장 조치

### 🔴 Critical (즉시 대응 필요)

| # | 항목 | 위치 | 제안 |
|---|------|------|------|
| C1 | **bandit Python 3.14 비호환** | `requirements.txt` | `bandit>=2.0.0` 업그레이드 또는 Semgrep/Ruff 보안 룰셋 도입 |

### 🟠 Major (다음 Phase에서 처리)

| # | 항목 | 위치 | 제안 |
|---|------|------|------|
| M1 | **settings E2E 9건 실패** | `e2e/test_settings.py` | settings UI 재설계 이후 셀렉터 전면 업데이트 필요. 9개 테스트 모두 `test_settings.py`에 집중 |
| M2 | **`notifier/payload.py` 커버리지 0%** | `src/notifier/payload.py` | 파일 전체(2–21)가 테스트 없음 — 단위 테스트 추가 또는 dead code 확인 |

### 🟡 Minor (여유 시 개선)

| # | 항목 | 위치 | 제안 |
|---|------|------|------|
| m1 | flake8 E501 1건 | `src/ui/router.py:16` | 줄 분리 (3자 초과) — 1분 Quick-fix |
| m2 | pylint E1102 false-positive | `src/ui/router.py:170` | `# pylint: disable=not-callable` 주석 추가 |
| m3 | `analyzer/static.py` 71% | Windows/Linux 경로 분기 미커버 | subprocess 경로 테스트 추가 |
| m4 | `crypto.py` 71% | 암호화 키 없는 경우·복호화 실패 미커버 | 엣지 케이스 테스트 추가 |
| m5 | W0718 × 9 | `except Exception` 남용 | 개별 예외 타입 세분화 검토 |
| m6 | `pytest-randomly` 미설치 | `requirements-dev.txt` | `pytest-randomly>=3.15` 추가 — 자동 순서 무작위화 |

### 요약 권장 우선순위

```
P0 (즉시): bandit 업그레이드 → requirements.txt bandit>=2.0.0
P1 (다음 Phase): e2e/test_settings.py 셀렉터 업데이트 (9건 복구)
P2: notifier/payload.py 테스트 추가 또는 제거 결정
P3: flake8 E501 + pylint E1102 Quick-fix (1–2분)
```

---

*감사 수행: 2026-04-19 | 7라운드 완료 + Appendix B E2E | 도구: pytest 8.3.3 / pylint 3.3.1 / flake8 7.1.1 / bandit 1.8.0(비가용) / Playwright 1.44+*
