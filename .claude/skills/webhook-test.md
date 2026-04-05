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

## 응답

- `202 Accepted` — 정상 처리 (비동기 분석 시작)
- `400 Bad Request` — 페이로드 형식 오류
- `403 Forbidden` — 서명 검증 실패
- `422 Ignored` — 처리 불필요한 이벤트 (지원하지 않는 액션 등)
