# Merge Retry Runbook

CI-aware Auto Merge 재시도 시스템 운영 가이드.
CI-aware Auto Merge retry system operations guide.

## 개요 / Overview

PR 자동 머지 시 `mergeable_state=unstable` (CI 진행 중) 또는 `unknown` 상태면, 단일 실패 대신 `merge_retry_queue` 에 큐잉하여 최대 24시간 동안 자동 재시도한다.
When auto-merging a PR, if `mergeable_state=unstable` (CI running) or `unknown`, the system queues to `merge_retry_queue` and retries automatically for up to 24 hours.

## 트리거 / Triggers

| 트리거 | 지연 | 설명 |
|--------|------|------|
| `check_suite.completed` 웹훅 | 즉시 (30초 디바운스) | CI 완료 시 즉각 재시도 |
| cron (`* * * * *`) | 최대 1분 | 웹훅 미전달 시 fallback (PR #99 — 5분→1분 단축) |

## 설정 / Configuration

환경변수로 조정 (기본값):
- `MERGE_RETRY_ENABLED=true` — False 시 레거시 단일 시도 동작
- `MERGE_RETRY_MAX_ATTEMPTS=30` — 큐 행당 최대 재시도 횟수
- `MERGE_RETRY_MAX_AGE_HOURS=24` — 큐 행 만료 시간
- `MERGE_RETRY_INITIAL_BACKOFF_SECONDS=60` — 첫 재시도 백오프
- `MERGE_RETRY_MAX_BACKOFF_SECONDS=600` — 최대 백오프
- `MERGE_RETRY_WORKER_BATCH_SIZE=50` — cron sweep 1회 처리 최대 행 수
- `MERGE_RETRY_CHECK_SUITE_WEBHOOK_ENABLED=true` — check_suite 웹훅 즉각 트리거 활성화

## Webhook 구독 확인 / Webhook Subscription Check

기존 등록 리포가 `check_suite` 이벤트를 수신하지 못하면 cron fallback(1분 지연)으로만 동작한다.
If an existing repo does not receive `check_suite` events, only the cron fallback (1 min delay) will work.

확인 방법: Settings 페이지에서 ⚠️ 배너 확인 → "Webhook 재등록" 버튼 클릭.
Check: Look for ⚠️ banner on the Settings page → click "Webhook 재등록" button.

## 대기 중 행 확인 / Checking Pending Rows

```sql
SELECT id, repo_full_name, pr_number, status, attempts_count, next_retry_at, last_failure_reason
FROM merge_retry_queue
WHERE status = 'pending'
ORDER BY next_retry_at
LIMIT 20;
```

## 수동 재시도 트리거 / Manual Retry Trigger

```bash
curl -X POST -H "X-API-Key: $INTERNAL_CRON_API_KEY" \
  https://<app-url>/api/internal/cron/retry-pending-merges
```

## Stale Claim 복구 / Stale Claim Recovery

워커가 비정상 종료되면 `claimed_at IS NOT NULL`이지만 처리가 멈춘 행이 생길 수 있다.
5분 이상 지난 claim은 다음 cron 실행 시 자동 재클레임된다.

수동으로 확인하려면:

```sql
SELECT id, repo_full_name, pr_number, claimed_at, attempts_count
FROM merge_retry_queue
WHERE claimed_at IS NOT NULL
  AND claimed_at < NOW() - INTERVAL '5 minutes'
  AND status = 'pending';
```

발견 시 cron 수동 트리거로 재처리:

```bash
curl -X POST -H "X-API-Key: $INTERNAL_CRON_API_KEY" \
  https://<app-url>/api/internal/cron/retry-pending-merges
```

## terminal 실패 원인 / Terminal Failure Reasons

| reason_tag | 의미 | 권장 조치 |
|------------|------|----------|
| `branch_protection_blocked` | 브랜치 보호 규칙 — 리뷰 필요 | PR에 리뷰 승인 요청 |
| `unstable_ci` | CI 실패 (비-required check 아님) | CI 로그 확인 후 재푸시 |
| `permission_denied` | GitHub 토큰 권한 부족 | 토큰 재발급 (repo scope 필요) |
| `sha_drift` | force-push 감지 — SHA 변경 | 새 푸시로 재분석 |
| `config_changed` | auto_merge 비활성 또는 threshold 변경 | 설정 재확인 |
| `expired` | 24시간 내 머지 불가 | PR 상태 수동 확인 |

## 알림 / Notifications

- **첫 지연 시**: "자동 머지 대기 중 — CI 완료 후 재시도합니다" Telegram 1회
- **성공 시**: "자동 머지 성공 (재시도) — N회 시도" Telegram 1회
- **terminal 실패 시**: "자동 머지 최종 실패 — [사유] [권장 조치]" Telegram 1회 + 선택적 GitHub Issue
