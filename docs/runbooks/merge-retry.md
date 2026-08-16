# Merge Retry Runbook

CI-aware Auto Merge 재시도 시스템 운영 가이드.

## 개요

PR 자동 머지가 지금 못 닫히는 이유가 **기다리면 풀릴 수 있는 태그**이면
`merge_retry_queue` 에 넣고, `MERGE_RETRY_MAX_AGE_HOURS`(기본 24) ·
`MERGE_RETRY_MAX_ATTEMPTS`(기본 30) 안에서 다시 시도한다.

재시도 멤버십 = `src/gate/merge_reasons.py` 의 `_RETRIABLE_TAGS`:
`unstable_ci` · `unknown_state_timeout` · `branch_protection_blocked`.

실제 큐잉 여부는 `retry_policy.should_retry(tag, ci_status)`:

| reason_tag | 재시도하는 `ci_status` |
|---|---|
| `unstable_ci` | `running` · `passed` · `unknown` |
| `unknown_state_timeout` | `running` |
| `branch_protection_blocked` | **`running` 만** |

`branch_protection_blocked` 는 required check 진행 중과 규칙상 충족 불가를
GitHub 이 한 상태로 준다. CI 가 도는 중일 때만 기다린다. CI 가 끝났는데도
blocked 면 종결한다(리뷰 미승인 등).

가드: `tests/unit/gate/test_retry_policy.py` ·
`tests/unit/gate/test_merge_reasons.py`.

## 트리거

| 트리거 | 지연 | 설명 |
|--------|------|------|
| `check_suite.completed` 웹훅 | 즉시 (30초 디바운스) | CI 완료 시 즉각 재시도 |
| 인앱 스케줄러 `retry-pending-merges` | 최대 1분 | 웹훅 미전달 시 fallback (`src/scheduler.py` `JOBS`) |

`MERGE_RETRY_ENABLED=false` 이면 큐 없이 한 번만 시도한다.

## 설정

- `MERGE_RETRY_ENABLED=true`
- `MERGE_RETRY_MAX_ATTEMPTS=30`
- `MERGE_RETRY_MAX_AGE_HOURS=24`
- `MERGE_RETRY_INITIAL_BACKOFF_SECONDS=60`
- `MERGE_RETRY_MAX_BACKOFF_SECONDS=600`
- `MERGE_RETRY_WORKER_BATCH_SIZE=50`
- `MERGE_RETRY_CHECK_SUITE_WEBHOOK_ENABLED=true`

정본 설명: `docs/reference/env-vars.md`.

## Webhook 구독 확인

기존 등록 리포가 `check_suite` 이벤트를 수신하지 못하면 cron fallback(1분)으로만 동작한다.
Settings 페이지에서 ⚠️ 배너 확인 → "Webhook 재등록".

## 대기 중 행 확인

```sql
SELECT id, repo_full_name, pr_number, status, attempts_count, next_retry_at, last_failure_reason
FROM merge_retry_queue
WHERE status = 'pending'
ORDER BY next_retry_at
LIMIT 20;
```

## 수동 재시도 트리거

```bash
curl -X POST -H "X-API-Key: $INTERNAL_CRON_API_KEY" \
  https://<app-url>/api/internal/cron/retry-pending-merges
```

## Stale Claim 복구

워커가 비정상 종료되면 `claimed_at IS NOT NULL` 인데 처리가 멈춘 행이 생길 수 있다.
5분 이상 지난 claim 은 다음 sweep 에서 재클레임된다.

```sql
SELECT id, repo_full_name, pr_number, claimed_at, attempts_count
FROM merge_retry_queue
WHERE claimed_at IS NOT NULL
  AND claimed_at < NOW() - INTERVAL '5 minutes'
  AND status = 'pending';
```

발견 시 위 수동 트리거로 재처리.

## 종결 사유 (재시도하지 않음)

| reason_tag | 의미 | 권장 조치 |
|------------|------|----------|
| `branch_protection_blocked` (CI 가 running 이 아님) | 규칙상 충족 불가(리뷰 미승인 등) | 사람 리뷰/규칙 확인 후 재푸시 |
| `unstable_ci` + `ci_status=failed` | CI 실패 | CI 로그 확인 후 재푸시 |
| `permission_denied` | GitHub 토큰 권한 부족 | 토큰 재발급 (`repo` 또는 `pull_requests: write`) |
| `dirty_conflict` / `behind_base` / `draft_pr` | 충돌 · base 뒤처짐 · draft | PR 상태 정리 |
| `sensitive_path_hold` | 민감 경로 — 사람 검토 전 hold | 사람이 머지. 큐가 기다리지 않음 |
| `verifier_blocked` / `verifier_error` | 2nd-LLM 검증자 거절 또는 자체 실패 | 사람 검토 |
| `sha_drift` | force-push 로 SHA 변경 | 새 푸시로 재분석 |
| `config_changed` | auto_merge 해제 또는 threshold 변경 | 설정 재확인 |
| `expired` | 나이/횟수 한도 초과 | PR 상태 수동 확인 |

## 알림

- **첫 지연 시**: Telegram 1회
- **성공 시**: Telegram 1회 (재시도 횟수 포함)
- **종결 시**: Telegram 1회 + 선택적 GitHub Issue (`auto_merge_issue_on_failure`)
