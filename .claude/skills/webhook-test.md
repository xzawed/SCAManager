---
description: GitHub Webhook 로컬 테스트 — 서명된 페이로드 전송
---

로컬 개발 서버에 GitHub Webhook 이벤트를 시뮬레이션한다.

## 사전 준비

```bash
# 서버 실행 (별도 터미널)
uvicorn src.main:app --reload --port 8000
```

## Push 이벤트 테스트

```bash
# 페이로드 준비
PAYLOAD='{"ref":"refs/heads/main","commits":[{"id":"abc123","message":"feat: add feature","added":[],"modified":["src/main.py"],"removed":[]}],"repository":{"full_name":"owner/repo"}}'
SECRET="your-webhook-secret"

# HMAC-SHA256 서명 생성
SIG=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* /sha256=/')

# Webhook 전송
curl -X POST http://localhost:8000/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -H "X-Hub-Signature-256: $SIG" \
  -d "$PAYLOAD"
```

## PR 이벤트 테스트

```bash
PAYLOAD='{"action":"opened","pull_request":{"number":1,"head":{"sha":"def456"},"base":{"sha":"abc123"}},"repository":{"full_name":"owner/repo"}}'
SECRET="your-webhook-secret"
SIG=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* /sha256=/')

curl -X POST http://localhost:8000/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -H "X-Hub-Signature-256: $SIG" \
  -d "$PAYLOAD"
```

## check_suite 이벤트 테스트 (Phase 12 — CI-aware Auto Merge 재시도)

CI 완료 시 GitHub 가 발송하는 `check_suite.completed` 이벤트로 `merge_retry_queue` 즉각 처리 트리거.

```bash
PAYLOAD='{"action":"completed","check_suite":{"head_sha":"def456","conclusion":"success"},"repository":{"full_name":"owner/repo"}}'
SECRET="your-webhook-secret"
SIG=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* /sha256=/')

curl -X POST http://localhost:8000/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: check_suite" \
  -H "X-Hub-Signature-256: $SIG" \
  -d "$PAYLOAD"
```

응답:
- `{"status":"accepted"}` — 해당 SHA 의 pending retry 행 BackgroundTask 트리거
- `{"status":"debounced"}` — 30초 내 동일 (repo, sha) 재요청 (monorepo 폭주 방어)
- `{"status":"ignored"}` — `action != "completed"` 또는 head_sha/repo 누락
- `{"status":"disabled"}` — `merge_retry_check_suite_webhook_enabled=false` 설정 시

## auto_merge_disabled 이벤트 테스트 (Phase 3 PR-B1 — MergeAttempt lifecycle)

GitHub 가 force-push / 사용자 수동 해제 등으로 auto-merge 를 자동 비활성화 시 발송. MergeAttempt state 전이 (`enabled_pending_merge` → `disabled_externally`).

```bash
PAYLOAD='{"action":"auto_merge_disabled","number":1,"pull_request":{"head":{"sha":"def456"}},"sender":{"login":"someuser"},"repository":{"full_name":"owner/repo"}}'
SECRET="your-webhook-secret"
SIG=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* /sha256=/')

curl -X POST http://localhost:8000/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -H "X-Hub-Signature-256: $SIG" \
  -d "$PAYLOAD"
```

## 응답

- `202 Accepted` — 정상 처리 (비동기 분석 시작)
- `400 Bad Request` — 페이로드 형식 오류
- `401 Unauthorized` — 서명 검증 실패 (Phase G P1-4: 200 OK 반환 금지 — 공격자 응답 노출 차단)
- `200 / "ignored"` — 처리 불필요한 이벤트 (지원하지 않는 액션, ping 등)
