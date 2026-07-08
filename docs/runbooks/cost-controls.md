# 비용 제어 (Anthropic API) 운영·검증 런북

Anthropic API(Claude) 호출 비용을 통제하는 3종 스위치(전역 kill-switch 2개 + 리포별 컬럼 1개)의 운영·검증 가이드. 메트릭이 로그 전용(DB 미영속)이라 "비용이 실제로 줄었는지"는 자동 회귀 검증이 불가능 — 이 문서가 **살아있는 수동 검증 절차**의 단일 출처다.

## 1. 제어 수단 요약

| 스위치 | 종류 | 효과 | 대상 경로 |
|--------|------|------|-----------|
| `AI_REVIEW_DISABLED` | 전역 kill-switch (env, 기본 off) | `1` 설정 시 AI 코드리뷰(Sonnet) 전역 차단 — 웹훅 파이프라인 + CLI pre-push hook 공통. 정적분석·게이트·인사이트는 영향 없음 | `src/analyzer/io/ai_review.py::review_code` 진입부 |
| `INSIGHT_DISABLED` | 전역 kill-switch (env, 기본 off) | `1` 설정 시 대시보드 인사이트 + 리포별 인사이트 내러티브(Haiku) 전역 차단 | `dashboard_service.insight_narrative` + `repo_insight_service.repo_insight_narrative` 진입부 |
| `RepoConfig.ai_review_enabled` | DB 컬럼 (기본 `True`) | 리포별로 AI 코드리뷰만 on/off — 정적분석·게이트는 계속 동작 | `src/worker/pipeline.py` (`review_code(..., enabled=_ai_review_enabled)`) |

**우선순위**: 전역 `AI_REVIEW_DISABLED` > 리포별 `ai_review_enabled`. 실행 조건은 **AND** — `review_code(*, enabled)` 파라미터가 `False`이거나 `is_disabled("AI_REVIEW")`가 `True`이면(둘 중 하나만 성립해도) 즉시 disabled 반환. 즉 전역이 켜져 있으면 리포별 설정과 무관하게 전부 차단되고, 전역이 꺼져 있어도 리포별 `ai_review_enabled=False`면 해당 리포만 차단된다.

> `AI_REVIEW_DISABLED` / `INSIGHT_DISABLED` 는 pydantic `Settings` 필드가 **아니라** `src/shared/feature_kill_switch.py::is_disabled(feature)` 가 `os.environ` 을 직접 읽는 패턴(`SECURITY_AUTO_PROCESS_DISABLED` 등과 동일 — 사용처 ≥3 helper 추출 정책 16 4번 원칙 정합).

## 2. 3-레이어 검증 전략

- **L1 단위 (Anthropic 클라이언트 mock → 호출 0 assert)**:
  - `tests/unit/analyzer/io/test_ai_review_disabled.py` — `test_enabled_false_returns_disabled_without_api_call` / `test_env_ai_review_disabled_returns_disabled` / `test_disabled_precedes_no_api_key`
  - `tests/unit/services/test_insight_disabled.py` — `test_dashboard_insight_disabled` / `test_repo_insight_disabled`
  - `tests/unit/worker/test_pipeline.py` — `test_pipeline_passes_enabled_false_when_repo_ai_disabled` / `test_pipeline_passes_enabled_true_by_default` / `test_pipeline_enabled_true_when_repo_config_fetch_raises`(조회 실패 시 fail-safe default `True` 유지)
  - `tests/unit/gate/test_disabled_status_not_failure.py` — `test_disabled_is_not_a_failure` / `test_disabled_absent_from_failed_statuses`
- **L2 통합**: `ai_review_enabled=False` 인 리포는 `review_code(enabled=False)` 로 호출되어 API 호출 없이 `disabled` 상태를 반환하고, 파이프라인은 정적분석 점수를 정상 저장한다. `disabled` 는 `AI_REVIEW_FAILED_STATUSES`(`api_error`/`parse_error`) 에 **포함되지 않으므로** auto-merge/auto-approve 를 차단하지 않고, 점수 컬럼도 NULL 이 되지 않는다(§4 참조).
- **L3 운영**: env 설정 후 Railway 로그에서 `claude_api_call model=...sonnet`(AI 리뷰) 또는 `model=...haiku`(인사이트) 라인이 **신규로 발생하지 않는지** 확인 + Anthropic Console 사용량 대시보드에서 호출 건수 정체 관찰.
  - 예시: `AI_REVIEW_DISABLED=1` 설정 후 Railway Logs 에서 `claude_api_call` 검색 → 설정 시각 이후 신규 라인이 없어야 정상.

## 3. 🔴 한계 & 백로그

- **메트릭은 로그 전용**(`src/shared/claude_metrics.py::log_claude_api_call` = logger 출력만, DB 미영속) — "비용이 실제로 얼마나 줄었는지"에 대한 **자동 회귀 검증이 불가능**하다. §2 L3 의 로그 grep 이 유일한 신호.
- **백로그**: 비용 메트릭 DB 영속화(향후 L3 자동화 + 예산 캡 알림 기반 마련 시 선행 과제).

## 4. disabled 상태의 gate 동작

AI 리뷰가 꺼진 리포(전역 또는 리포별)는 `_default_result("disabled")` 가 중립 AI 기본값(`AI_DEFAULT_COMMIT_RAW`/`DIRECTION_RAW`/`TEST_RAW` = 17/17/7 raw → 스케일링 후 commit 13 + direction 21 + test 10 = **44/55**)을 반환한다. 여기에 정적분석 점수(최대 45/100 배점 중 code_quality 25 + security 20)를 더해 판정하므로, disabled 리포의 **최대 총점은 89(B등급)** — 만점이 아니다. `fail-open`(인플레 만점으로 auto-merge 통과)은 없으며, `no_api_key` 상태와 동일한 특성을 공유한다(`src/constants.py` `AI_DEFAULT_*`, `.claude/rules/pipeline.md` §AI 실패 시 score/grade NULL-persist 참조 — `disabled`/`no_api_key`/`empty_diff` 는 genuine 실패가 아니라 점수 컬럼도 NULL 이 아닌 유지).

## 5. 로컬 키 경로 (서버 env 제어 불가)

아래 2개 경로는 **개발자 로컬 `ANTHROPIC_API_KEY`** 를 사용하므로 서버 env(`AI_REVIEW_DISABLED` 등)로 제어 불가 — 이번 PR 범위 밖이며, 비용 차단은 로컬에서만 가능하다(키 해제 또는 훅 제거).

| 경로 | 위치 | 모델 | 차단 방법 |
|------|------|------|-----------|
| ④ pre-push 훅 | `src/github_client/repos.py` `_INSTALL_HOOK_SH` | Haiku | 로컬 `ANTHROPIC_API_KEY` 미설정 또는 `.git/hooks/pre-push` 제거 |
| ⑤ Claude Code 문서훅 | `.claude/hooks/doc_review_gate.py` | Haiku (문서 편집마다 최대 3회) | 로컬 `ANTHROPIC_API_KEY` 미설정 또는 훅 비활성화 |

## 6. 살아있는 문서 유지 규칙

신규 Anthropic 비용 경로(새 kill-switch, 새 모델 호출 지점 등)를 도입할 때는 이 문서에 다음 3가지를 append 한다:

1. **검증 레이어** — 어느 레이어(L1/L2/L3)에서 무엇을 assert 하는지
2. **로그 시그니처** — Railway 로그에서 grep 할 패턴 (예: `claude_api_call model=...`)
3. **kill-switch 여부** — 전역/리포별 스위치 존재 여부, 없다면 왜 없는지

## 관련 / References

- 환경변수: [`docs/reference/env-vars.md`](../reference/env-vars.md#비용-제어-ai-리뷰인사이트-kill-switch)
- 코드: [`src/analyzer/io/ai_review.py`](../../src/analyzer/io/ai_review.py) · [`src/worker/pipeline.py`](../../src/worker/pipeline.py) · [`src/services/dashboard_service.py`](../../src/services/dashboard_service.py) · [`src/services/repo_insight_service.py`](../../src/services/repo_insight_service.py) · [`src/shared/feature_kill_switch.py`](../../src/shared/feature_kill_switch.py)
- 파이프라인 게이트 규칙: [`.claude/rules/pipeline.md`](../../.claude/rules/pipeline.md)
- 서비스 계층 규칙: [`.claude/rules/services.md`](../../.claude/rules/services.md)
- API/알림 규칙(5-way 동기화): [`.claude/rules/api.md`](../../.claude/rules/api.md)
- UI 규칙(설정 카드 ②): [`.claude/rules/ui.md`](../../.claude/rules/ui.md)
