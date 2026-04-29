# Phase 4 Critical 테스트 갭 5 PR 회고 (2026-04-29)

## 개요

14-에이전트 다각도 감사(2026-04-29, 그룹 52) Round 1-B "테스트 커버리지 66/100" 가 식별한 8개 사각지대를 5개 PR 시리즈로 메운 작업의 회고.

신규 테스트 197건 추가 (단위 +172 + 통합 +25), 모든 PR 이 SonarCloud Quality Gate 통과 후 머지 완료.

---

## 배경 — 14-에이전트 감사가 가리킨 갭

| 영역 | 갭 | 위험 |
|------|----|------|
| `analyzer/io/tools/python.py` | _PylintAnalyzer / _Flake8Analyzer / _BanditAnalyzer subprocess + 출력 파싱 + graceful degradation 미검증 | 도구 설치 누락 / 출력 포맷 변경 시 silent fail |
| `analyzer/io/ai_review.py` | httpx ConnectError/Timeout/RuntimeError 폴백, log_claude_api_call kwargs, _extract_json_payload codeblock 분기 | API 장애 시 점수 산정 미작동 |
| `scorer/calculator.py` | 등급 경계(44/45/59/60/74/75/89/90), CQ_WARNING_CAP 경계, AI status enum 4종 | 점수 1점 차이로 등급 잘못 → 머지 결정 오류 |
| `gate/engine.py` 가드 | _enqueue_merge_retry / _handle_terminal_merge_failure / _notify_merge_deferred 격리 try/except | 알림 1회 실패가 파이프라인 중단 유발 |
| `worker/pipeline.py` 헬퍼 | _extract_commit_message 11개 분기 미검증 | 빈 PR body / commits=[] 등 엣지에서 silent error |
| `services/merge_retry_service.py` 헬퍼 | _resolve_github_token / _get_pr_data / _notify_* / _create_failure_issue_safe 격리 | 토큰 폴백 누락 시 워커 무한 실패 |
| `gate/native_automerge.py` PR-A | 이중 enable (PR-B2 가드), force-push detail rstrip, merge_method 전파 | 잘못된 advice 발송 / 사용자 혼란 |
| 종단간 webhook→pipeline→gate 통합 | E2E 35/100 — UI 만 검증, webhook→merge zero coverage | 회귀 발생 시 단위 테스트가 못 잡음 |

---

## 5개 PR 결과

| PR | 브랜치 | 신규 테스트 | 누적 단위 |
|----|----|----|----|
| **PR-T1** | `test/phase4-t1-critical-coverage` | +106 (analyzer/tools/python 55 + ai_review_errors 20 + scorer/calculator_edges 31) | 1864 → 1970 |
| **PR-T2** | `test/phase4-t2-defensive-guards` | +26 (engine_defensive_guards 15 + pipeline_extract_helpers 11) | 1970 → 1996 |
| **PR-T3** | `test/phase4-t3-merge-retry-service` | +16 (merge_retry_service_helpers — 4 helper 함수 격리) | 1996 → 2012 |
| **PR-T4** | `test/phase4-t4-pr-a-scenarios` | +24 (pr_a_scenarios — 이중 enable PR-B2 / force-push / merge_method 전파) | 2012 → 2036 |
| **PR-T5** | `test/phase4-t5-e2e-integration` | +25 통합 (e2e_pipeline_scenarios — 9개 영역 25 시나리오) | 통합 47 → 72 |
| **합계** | | **+197** | **단위 1931 + 통합 72** |

---

## 잘 된 것

### 사전 갭 식별 → 시리즈화 → 머지 패턴이 효율적이었다

14-에이전트 감사가 8개 영역을 명확히 분리해 준 덕에 PR 단위로 쪼개 순차 머지가 가능했다. 각 PR 이 독립적이라 리뷰 부담이 작았고, 한 PR 머지 후 다음 PR 의 자료(테스트 수치 등)를 즉시 활용했다.

**교훈**: 다음 대형 갭 작업도 "감사 → 영역 분할 → PR 시리즈" 패턴 유지.

### 테스트만 추가, src/ 변경 0

5개 PR 모두 테스트 파일만 추가하고 src/ 코드는 건드리지 않았다. 결과적으로:
- pylint 10.00/10 유지 (검증 코드 영향 없음)
- bandit HIGH 0 유지
- SonarCloud Quality Gate 5번 연속 OK
- 운영 회귀 위험 0

**교훈**: "갭 메우기" 작업은 src/ 변경 욕망을 의식적으로 차단할 때 안전성과 속도가 모두 좋아진다. 코드 결함 발견 시 별도 PR 로 분리.

### 사전 발견된 src/ 결함은 후속 PR 로 분리

PR-T5 작성 중 `src/webhook/providers/github.py:279` 의 `data.get("head_commit", {}).get("message")` 가 `head_commit=None` 일 때 AttributeError 를 던지는 방어 갭을 발견. 즉시 수정하지 않고 테스트 시나리오를 빈 dict 로 변경 + 회고에 기록 → 별도 후속 PR 로 처리하도록 분리.

### 환경변수 격리 (.env stash) 패턴 활용

`make test-isolated` 가 `.env` 를 stash + 관련 env vars unset 후 실행하는 패턴 덕에 로컬 환경(.env 로드)에서도 1999 passed 검증 가능. 이전에 `make test` 가 env 영향으로 7건 실패하던 트랩을 회피.

---

## 어려웠던 것

### settings 객체 mocking 트랩

`src.gate.engine` / `src.services.merge_retry_service` 의 헬퍼 함수들이 `settings.telegram_bot_token`, `settings.github_token` 을 직접 참조 — `os.environ.setdefault` 로 환경변수를 주입해도 .env 에서 값이 비어있으면 settings 객체 자체가 빈 문자열을 보유.

**해결**: `with patch("src.gate.engine.settings") as mock_settings: mock_settings.telegram_bot_token = "..."` 패턴으로 직접 mocking.

**교훈**: 모듈 import 시점에 `settings = Settings()` 가 인스턴스화되면 환경변수 주입은 늦다 — 단위 테스트는 `settings` 객체를 직접 patch.

### 통합 테스트의 SQLite 가시성

`tests/integration/` 의 SessionLocal override 패턴은 `pipeline.py` + `webhook/providers/github.py` 두 군데를 모두 patch 해야 한다. `_helpers.py::get_webhook_secret` 도 SessionLocal 을 직접 import 하지만, OperationalError 시 settings.github_webhook_secret fallback 이 있어 우회 가능 — graceful degradation 덕에 patch 1곳 누락이 critical 하지 않았다.

### E2E 통합 테스트 시 로컬 환경 의존성

PR-T5 의 E2E 통합 테스트는 `make test-isolated` 외 환경에서 401 응답을 받아 실패. 로컬 `.env` 의 `GITHUB_WEBHOOK_SECRET` 가 `dev_secret` 으로 설정돼 있어 `test_secret` 으로 서명한 페이로드 검증이 실패한다.

**현재 권장**: 통합/E2E 테스트는 항상 `make test-isolated` 로 실행. CI 환경에는 env 가 설정되지 않아 자동 통과.

---

## 발견된 잔여 결함 (fix 완료)

### `src/webhook/providers/github.py:279` head_commit=None NPE — 머지 완료

`_loop_guard_check` 가 `data.get("head_commit", {}).get("message", "")` 패턴 사용 — `head_commit` 키가 존재하고 값이 `None` 이면 `.get` 체이닝이 깨진다.

```python
# 수정 전 (취약)
commit_msg = (
    data.get("head_commit", {}).get("message", "")
    or data.get("pull_request", {}).get("title", "")
    or ""
)

# 수정 후 — None 정규화 (브랜치 `fix/loop-guard-head-commit-none`, 머지 완료)
commit_msg = (
    (data.get("head_commit") or {}).get("message", "")
    or (data.get("pull_request") or {}).get("title", "")
    or ""
)
```

`_extract_commit_message` (pipeline.py) 는 `data.get("head_commit")` 후 `if head:` 체크로 동일 패턴을 안전하게 처리하고 있었음 — 두 위치의 패턴 일관성 확보 완료. `tests/unit/webhook/test_router.py::test_loop_guard_handles_head_commit_none_without_npe` 회귀 방지 테스트도 함께 등록.

---

## 다음 단계

### PR-B3 (1주일 dogfooding 후)

Tier 3 PR-A (PR #103) 머지 후 1주일이 되는 ~2026-05-06 시점에 `merge_retry_service` 폐기 평가 예정. 평가 기준:
- native auto-merge enable 후 `pull_request.closed merged=true` webhook 도달률
- `enabled_pending_merge` → `actually_merged` 전이 평균 latency
- `disabled_externally` 발생 빈도 + 사유 분포
- 폴백 경로 (REST merge_pr) 사용 비율

**기준 충족 시**: `merge_retry_queue` 단순화 또는 폐기, `src/services/merge_retry_service.py` + 관련 cron 제거 (~500줄 코드 감소).

**기준 미충족 시**: PR-A + retry 양립 유지, retry 횟수만 점진적 축소.

### head_commit=None NPE 수정 (별도 fix PR)

위 §발견된 잔여 결함 참조.

---

## 수치

| 지표 | Phase 4 시작 | Phase 4 종료 | 증감 |
|------|----|----|----|
| 단위 테스트 | 1864 | **1931** | +67 (실제 +172, 다른 PR 정리분 차감) |
| 통합 테스트 | 47 | **72** | +25 |
| E2E | 53 | 53 | 0 |
| pylint | 10.00 | 10.00 | 0 |
| bandit HIGH | 0 | 0 | 0 |
| SonarCloud QG | OK | OK | 0 |

> 실제 PR 별 신규 테스트 합계는 197건이지만 STATE.md 합계는 1864→1931(+67) — 일부 사전 정리 PR 의 영향 차감 결과.

---

## 회고 요약

5개 PR 시리즈 전체가 무사고 머지 + src/ 변경 0 + Quality Gate 5연속 통과로 종료. 14-에이전트 감사가 식별한 갭이 명확했고 영역별로 분리 가능했던 점이 결정적이었다.

다음 작업은 PR-B3 dogfooding 평가 (~2026-05-06) 와 head_commit=None 방어 fix.
