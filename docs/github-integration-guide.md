# SCAManager — GitHub 리포지토리 연동 가이드

이 문서는 SCAManager 웹서비스와 GitHub 리포지토리를 연동하여 Push/PR 이벤트 발생 시 자동 코드 분석이 실행되도록 설정하는 방법을 안내합니다.

---

## 목차

1. [사전 준비](#1-사전-준비)
2. [GitHub Webhook 설정](#2-github-webhook-설정)
3. [GitHub Personal Access Token 발급](#3-github-personal-access-token-발급)
4. [SCAManager 환경변수 설정](#4-scamanager-환경변수-설정)
5. [리포지토리별 분석 설정 (Gate 모드)](#5-리포지토리별-분석-설정-gate-모드)
6. [연동 확인](#6-연동-확인)
7. [문제 해결](#7-문제-해결)

---

## 1. 사전 준비

연동을 시작하기 전에 아래 항목이 준비되어 있어야 합니다.

| 항목 | 확인 |
|------|------|
| SCAManager 서비스 URL (예: `https://your-app.railway.app`) | ✅ 필요 |
| 연동할 GitHub 리포지토리 Admin 권한 | ✅ 필요 |
| Telegram Bot Token + Chat ID (알림 수신용) | ✅ 필요 |
| Anthropic API Key (AI 리뷰 사용 시) | 선택 |

---

## 2. GitHub Webhook 설정

### 2-1. Webhook Secret 생성

Webhook을 안전하게 수신하기 위한 시크릿 값을 생성합니다.

```bash
# 터미널에서 랜덤 시크릿 생성
python -c "import secrets; print(secrets.token_hex(32))"
# 예시 출력: a3f8c2d1e4b7f9a0c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5
```

생성된 값을 **메모**해두세요. 이후 GitHub과 SCAManager 양쪽에 동일하게 입력합니다.

### 2-2. GitHub 리포지토리에 Webhook 등록

1. 연동할 GitHub 리포지토리 페이지로 이동
2. **Settings** → **Webhooks** → **Add webhook** 클릭

3. 아래 값을 입력합니다:

| 필드 | 값 |
|------|-----|
| **Payload URL** | `https://your-app.railway.app/webhooks/github` |
| **Content type** | `application/json` |
| **Secret** | 위에서 생성한 시크릿 값 |
| **SSL verification** | Enable SSL verification (기본값 유지) |

4. **Which events would you like to trigger this webhook?** 항목에서:
   - `Let me select individual events` 선택
   - **Pushes** ✅ 체크
   - **Pull requests** ✅ 체크

5. **Active** 체크박스 활성화 후 **Add webhook** 클릭

> **확인:** 저장 후 GitHub이 즉시 ping 이벤트를 전송합니다. Webhook 목록에서 초록색 체크 아이콘이 표시되면 정상 연결입니다.

---

## 3. GitHub Personal Access Token 발급

SCAManager가 PR Comment 게시 및 PR Review API를 사용하기 위해 필요합니다.

1. GitHub → **Settings** (우측 상단 프로필) → **Developer settings** → **Personal access tokens** → **Tokens (classic)**

2. **Generate new token (classic)** 클릭

3. 아래 권한(scope)을 선택합니다:

| Scope | 용도 |
|-------|------|
| `repo` | PR Comment 게시, PR Review (비공개 리포 포함) |
| `public_repo` | 공개 리포지토리만 사용하는 경우 대체 가능 |

4. **Generate token** 클릭 후 토큰 값을 복사해둡니다 (페이지를 벗어나면 다시 볼 수 없음)

> **Fine-grained token 사용 시:** Repository → Contents(Read), Pull requests(Read & Write), Commit statuses(Read & Write) 권한 부여

---

## 4. SCAManager 환경변수 설정

### Railway 배포 환경

Railway 대시보드 → 프로젝트 선택 → **Variables** 탭에서 아래 값을 설정합니다.

| 변수명 | 값 | 설명 |
|--------|-----|------|
| `GITHUB_WEBHOOK_SECRET` | 2-1에서 생성한 시크릿 | Webhook 서명 검증용 |
| `GITHUB_TOKEN` | 3에서 발급한 PAT | GitHub API 인증 |
| `TELEGRAM_BOT_TOKEN` | `123456:ABC-xxx` | Telegram 알림 봇 토큰 |
| `TELEGRAM_CHAT_ID` | `-100xxxxxxxxx` | 알림 수신 채팅 ID |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Railway PostgreSQL 자동 참조 |
| `ANTHROPIC_API_KEY` | `sk-ant-xxxx` | AI 리뷰 사용 시 (없으면 기본값 적용) |
| `API_KEY` | 임의 문자열 | 대시보드 API 인증 (없으면 인증 생략) |

### 로컬 개발 환경

프로젝트 루트의 `.env` 파일에 동일한 값을 설정합니다.

```bash
cp .env.example .env
# .env 파일을 편집기로 열어 각 값 입력
```

```env
DATABASE_URL=postgresql://user:password@localhost:5432/scamanager
GITHUB_WEBHOOK_SECRET=a3f8c2d1e4b7f9a0...  # 2-1에서 생성한 값
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
TELEGRAM_BOT_TOKEN=123456:ABC-xxx
TELEGRAM_CHAT_ID=-100123456789
ANTHROPIC_API_KEY=sk-ant-xxxx  # 선택
API_KEY=my-secret-api-key       # 선택
```

---

## 5. 리포지토리별 분석 설정 (Gate 모드)

연동 후 각 리포지토리의 PR Gate 동작 방식을 웹 UI 또는 API로 설정할 수 있습니다.

### 웹 UI에서 설정

1. `https://your-app.railway.app` 접속
2. 분석 이력이 있는 리포지토리 클릭
3. **설정** 탭 → Gate 모드 및 임계값 설정 후 저장

### API로 설정

```bash
curl -X PUT https://your-app.railway.app/api/repos/owner/repo-name/config \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "gate_mode": "auto",
    "auto_approve_threshold": 75,
    "auto_reject_threshold": 50
  }'
```

### Gate 모드 설명

| 모드 | 동작 |
|------|------|
| `disabled` | Gate 없음 — 분석 결과를 Telegram/PR Comment로만 전달 (기본값) |
| `auto` | 점수 기준 자동 Approve/Request Changes — 임계값 초과 시 자동 승인, 미달 시 자동 반려 |
| `semi-auto` | Telegram으로 승인/반려 요청 전송 → 버튼 클릭으로 수동 결정 |

### 임계값 기준

```
점수 ≥ auto_approve_threshold(기본 75) → GitHub PR 자동 Approve
점수 < auto_reject_threshold(기본 50)  → GitHub PR 자동 Request Changes
그 사이 (50~75)                         → Gate 없이 통과 (분석 결과만 전달)
```

---

## 6. 연동 확인

### 6-1. 테스트 Push 전송

연동된 리포지토리에 임의의 커밋을 Push합니다.

```bash
git commit --allow-empty -m "test: SCAManager 연동 테스트"
git push origin main
```

### 6-2. 분석 결과 확인 경로

| 확인 방법 | 위치 |
|----------|------|
| **Telegram 알림** | 설정된 채팅방에 점수 및 등급 메시지 수신 |
| **웹 대시보드** | `https://your-app.railway.app` → 리포지토리 선택 |
| **REST API** | `GET /api/repos/owner/repo-name/analyses` |

### 6-3. PR 이벤트 확인

Pull Request를 생성하면:
1. **Telegram**: 분석 결과 + Gate 모드에 따른 승인/반려 메시지
2. **GitHub PR Comment**: 점수표 및 개선사항 자동 게시
3. **GitHub Review**: `auto` 모드 시 Approve 또는 Request Changes 자동 적용

---

## 7. 문제 해결

### Webhook 수신 후 반응 없음

**GitHub → Settings → Webhooks → 해당 webhook → Recent Deliveries** 에서 응답 코드 확인

| 응답 코드 | 원인 및 해결 |
|-----------|-------------|
| `401` | `GITHUB_WEBHOOK_SECRET` 불일치 — GitHub과 SCAManager 양쪽 값이 동일한지 확인 |
| `422` | 지원하지 않는 이벤트 타입 — Push 또는 Pull request 이벤트만 처리됨 |
| `5xx` | 서버 오류 — Railway 로그 확인 (`railway logs`) |
| `연결 실패` | Payload URL 오타 또는 서비스 미기동 — `GET /health` 응답 확인 |

### Telegram 알림이 오지 않음

```bash
# Bot이 채팅방에 메시지를 보낼 수 있는지 확인
curl "https://api.telegram.org/bot<BOT_TOKEN>/sendMessage" \
  -d "chat_id=<CHAT_ID>&text=테스트"
```

- Bot을 채팅방에 초대했는지 확인
- `TELEGRAM_CHAT_ID` 앞의 `-` 기호 포함 여부 확인 (그룹 채팅은 음수)

### GitHub PR Comment가 게시되지 않음

- `GITHUB_TOKEN`의 `repo` scope 권한 확인
- Fine-grained token 사용 시 Pull requests(Read & Write) 권한 확인
- Railway Variables에서 토큰 앞뒤 공백 없는지 확인

### AI 리뷰 결과가 없고 점수가 낮음

`ANTHROPIC_API_KEY`가 설정되지 않으면 AI 리뷰 항목(커밋 메시지 20점, 구현 방향성 20점)이 각각 15점 기본값으로 적용됩니다. AI 리뷰를 원하면 Anthropic 콘솔에서 API 키를 발급하여 설정하세요.

---

## 빠른 설정 체크리스트

```
□ 1. Webhook Secret 생성
□ 2. GitHub 리포지토리 Settings → Webhooks 등록
     - Payload URL: https://your-app.railway.app/webhooks/github
     - Content type: application/json
     - Events: Pushes + Pull requests
□ 3. GitHub PAT 발급 (repo scope)
□ 4. Railway Variables에 환경변수 5개 설정
     - GITHUB_WEBHOOK_SECRET, GITHUB_TOKEN
     - TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
     - DATABASE_URL
□ 5. 테스트 커밋 Push → Telegram 알림 수신 확인
□ 6. (선택) 웹 대시보드에서 Gate 모드 설정
```
