# SCAManager — GitHub 리포지토리 연동 가이드

이 문서는 SCAManager와 GitHub 리포지토리를 연동하여 Push/PR 이벤트 발생 시 자동 코드 분석이 실행되도록 설정하는 방법을 안내합니다.

---

## 목차

1. [연동 방법 선택](#1-연동-방법-선택)
2. [방법 A — 웹 UI 자동 연동 (권장)](#2-방법-a--웹-ui-자동-연동-권장)
3. [방법 B — 수동 Webhook 연동 (레거시)](#3-방법-b--수동-webhook-연동-레거시)
4. [CLI Hook 설치 (로컬 pre-push 자동 코드리뷰)](#4-cli-hook-설치-로컬-pre-push-자동-코드리뷰)
5. [Gate 모드 및 임계값 설정](#5-gate-모드-및-임계값-설정)
6. [연동 확인](#6-연동-확인)
7. [Phase 12 — check_suite 이벤트 구독 확인](#7-phase-12--check_suite-이벤트-구독-확인)
8. [문제 해결](#8-문제-해결)

---

## 1. 연동 방법 선택

| 방법 | 설명 | 권장 여부 |
|------|------|-----------|
| **방법 A — 웹 UI 자동 연동** | GitHub OAuth 로그인 후 드롭다운에서 리포 선택 → Webhook 자동 생성 | ✅ 권장 |
| **방법 B — 수동 Webhook 연동** | GitHub 설정에서 직접 Webhook 등록 + 환경변수 수동 입력 | 레거시 / 고급 사용자 |

> **신규 연동은 방법 A를 사용하세요.** Webhook 생성, 시크릿 관리, CLI Hook 파일 배포까지 모두 자동으로 처리됩니다.

---

## 2. 방법 A — 웹 UI 자동 연동 (권장)

### 2-1. GitHub OAuth App 설정 (최초 1회)

SCAManager 서버에 GitHub OAuth App을 연결해야 합니다.

1. GitHub → **Settings → Developer settings → OAuth Apps → New OAuth App**
2. 아래 값 입력:

| 항목 | 값 |
|------|-----|
| Application name | SCAManager |
| Homepage URL | `https://your-app.railway.app` |
| Authorization callback URL | `https://your-app.railway.app/auth/callback` |

3. 생성 후 **Client ID**와 **Client Secret**을 서버 환경변수에 설정:

```
GITHUB_CLIENT_ID=Ov23li...
GITHUB_CLIENT_SECRET=github_...
SESSION_SECRET=랜덤-32자-이상-문자열
APP_BASE_URL=https://your-app.railway.app
```

> `APP_BASE_URL` 미설정 시 OAuth redirect_uri와 Webhook URL이 `http://`로 등록되어 실패합니다. Railway 배포 시 반드시 설정하세요.

### 2-2. 리포지토리 추가

1. `https://your-app.railway.app/login` 접속 → **GitHub으로 로그인**
2. 대시보드에서 **+ 리포 추가** 클릭
3. GitHub 드롭다운에서 연동할 리포지토리 선택
4. **Webhook 생성 + 리포 추가** 클릭

자동으로 처리되는 항목:
- GitHub Webhook 생성 (HTTPS URL, `application/json`, Pushes + Pull requests)
- Webhook Secret 자동 생성 및 RepoConfig에 저장
- `.scamanager/config.json` + `install-hook.sh` Repo에 커밋 (CLI Hook용)

> 리포 추가 완료 즉시 Push/PR 이벤트 수신이 시작됩니다.

### 2-3. Webhook URL 변경 시

배포 URL이 변경되었거나 기존에 HTTP로 등록된 경우:

1. 대시보드 → 해당 리포지토리 → **설정** 탭
2. CLI Hook 카드 → **🔗 Webhook 재등록** 버튼 클릭
3. 기존 Webhook이 삭제되고 현재 `APP_BASE_URL` 기준으로 재생성됩니다

---

## 3. 방법 B — 수동 Webhook 연동 (레거시)

> 방법 A(웹 UI)를 사용할 수 없는 환경이거나, 레거시 리포를 관리하는 경우에만 사용합니다.

### 3-1. Webhook Secret 생성

```bash
python -c "import secrets; print(secrets.token_hex(32))"
# 예시: a3f8c2d1e4b7f9a0c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5
```

생성된 값을 메모해 두세요. GitHub과 SCAManager 양쪽에 동일하게 입력합니다.

### 3-2. GitHub 리포지토리에 Webhook 등록

1. 연동할 리포 → **Settings → Webhooks → Add webhook**
2. 아래 값 입력:

| 필드 | 값 |
|------|-----|
| Payload URL | `https://your-app.railway.app/webhooks/github` |
| Content type | `application/json` |
| Secret | 3-1에서 생성한 시크릿 |
| SSL verification | Enable (기본값 유지) |

3. **Which events?** → `Let me select individual events` 선택
   - **Pushes** ✅ / **Pull requests** ✅
4. **Active** 체크 후 **Add webhook** 클릭

> 저장 후 GitHub이 ping 이벤트를 전송합니다. 초록색 체크 아이콘이 표시되면 정상 연결입니다.

### 3-3. GitHub Personal Access Token 발급

PR Comment 및 PR Review API 사용에 필요합니다.

1. GitHub → **Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. **Generate new token (classic)** 클릭
3. Scope 선택:

| Scope | 용도 |
|-------|------|
| `repo` | PR Comment, PR Review (비공개 리포 포함) |
| `public_repo` | 공개 리포만 사용하는 경우 대체 가능 |

> Fine-grained token: Repository → Contents(Read), Pull requests(Read & Write) 권한 부여

### 3-4. 서버 환경변수 설정

```
GITHUB_WEBHOOK_SECRET=3-1에서-생성한-시크릿
GITHUB_TOKEN=3-3에서-발급한-PAT
```

> 방법 B로 등록된 리포는 `user_id = NULL`로 저장되어 모든 로그인 사용자에게 표시됩니다.

---

## 4. CLI Hook 설치 (로컬 pre-push 자동 코드리뷰)

> 방법 A로 리포를 추가한 경우 `.scamanager/` 파일이 이미 Repo에 커밋되어 있습니다.

### 요구사항

| 항목 | 설명 |
|------|------|
| Claude Code CLI | `claude` 명령어 — 데스크탑 환경 필수 |
| bash, python3, curl | 훅 스크립트 실행에 필요 |
| git | 버전 관리 |

> **GitHub Codespaces · 모바일 환경에서는 CLI Hook이 동작하지 않습니다.**  
> `command -v claude` 체크 후 조용히 건너뛰므로 push 자체는 정상 진행됩니다.  
> 해당 환경에서는 `python -m src.cli review` CLI 도구를 사용하세요.

### 설치 방법

로컬 클론에서 1회만 실행합니다.

```bash
git pull
bash .scamanager/install-hook.sh
# ✅ SCAManager pre-push 훅 설치 완료
```

이후 `git push` 시마다 자동으로 코드리뷰가 실행됩니다.

```
🔍 [SCAManager] 코드리뷰 실행 중...

📊 코드리뷰 결과:
  요약: 기능 구현 완료, 전반적으로 양호
  커밋 메시지: 명확하고 표준적인 형식
  코드 품질: 주요 문제 없음
  보안: 특이사항 없음
```

결과는 터미널 출력과 동시에 SCAManager 대시보드에 저장됩니다.

### 훅 재설치

훅 파일이 삭제되거나 서버 URL이 변경된 경우:

```bash
# 서버에서 최신 파일 재커밋 (설정 페이지 → 훅 파일 재커밋 버튼)
git pull
bash .scamanager/install-hook.sh
```

---

## 5. Gate 모드 및 임계값 설정

### 웹 UI에서 설정

1. 대시보드 → 리포지토리 클릭 → **설정** 탭
2. Gate 엔진 카드에서 모드 선택 및 임계값 슬라이더/숫자 입력으로 설정
3. **설정 저장** 클릭

### API로 설정

```bash
curl -X PUT https://your-domain/api/repos/owner/repo-name/config \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "pr_review_comment": true,
    "approve_mode": "auto",
    "approve_threshold": 75,
    "reject_threshold": 50,
    "auto_merge": false,
    "merge_threshold": 80
  }'
```

### Gate 3-옵션 설명

설정 페이지의 세 옵션은 완전히 독립적으로 동작합니다.

| 옵션 | 설정값 | 동작 |
|------|--------|------|
| **PR 리뷰 댓글** | `pr_review_comment=on` | PR에 AI 코드리뷰 댓글 자동 게시 |
| **Approve 모드** | `approve_mode="disabled"` | Gate 없음 (기본값) |
| | `approve_mode="auto"` | 점수 기준 자동 Approve / Request Changes |
| | `approve_mode="semi"` | Telegram 인라인 버튼으로 수동 승인/반려 |
| **Auto Merge** | `auto_merge=on` + `merge_threshold` | 점수 통과 시 squash merge 자동 실행 (approve_mode 무관) |

### 임계값 기준

```
점수 ≥ approve_threshold (기본 75) → GitHub PR Approve
점수 < reject_threshold  (기본 50) → GitHub PR Request Changes
점수 ≥ merge_threshold   (기본 80) → squash merge 자동 (auto_merge=on 시)
그 사이 (50~75)                     → Gate 없이 통과 (알림만 전달)
```

---

## 6. 연동 확인

### 테스트 Push 전송

```bash
git commit --allow-empty -m "test: SCAManager 연동 테스트"
git push origin main
```

### 분석 결과 확인

| 확인 방법 | 위치 |
|----------|------|
| Telegram 알림 | 설정된 채팅방에 점수 및 등급 메시지 수신 |
| 웹 대시보드 | `https://your-domain` → 리포지토리 클릭 |
| REST API | `GET /api/repos/owner/repo-name/analyses` |

### PR 이벤트 확인

Pull Request를 생성하면:
1. **Telegram**: 분석 결과 + Gate 모드에 따른 승인/반려 메시지
2. **GitHub PR Comment**: 점수표 및 개선사항 자동 게시
3. **GitHub Review**: `auto` 모드 시 Approve 또는 Request Changes 자동 적용

---

## 7. Phase 12 — check_suite 이벤트 구독 확인

**Phase 12 이후 신규 등록 리포**는 `check_suite` 이벤트가 자동으로 포함된다.

**기존 등록 리포 (Phase 12 이전에 추가한 리포)**는 다음 절차로 업데이트해야 CI-aware 자동 재시도가 동작한다:

1. SCAManager 대시보드 → 해당 리포 **Settings**
2. Card ⑤ (시스템 & 토큰) → **"Webhook 재등록"** 버튼 클릭
3. GitHub 리포 **Settings → Webhooks** 에서 이벤트 목록에 `Check suites` 포함 여부 확인

> `check_suite` 미구독 상태에서도 5분 cron fallback으로 재시도가 동작하지만, 즉각 트리거가 비활성화되어 최대 5분 지연이 발생한다.

---

## 8. 문제 해결

### Webhook 수신 후 반응 없음

**GitHub → Settings → Webhooks → 해당 webhook → Recent Deliveries** 에서 응답 코드 확인

| 응답 코드 | 원인 및 해결 |
|-----------|-------------|
| `403` | Webhook Secret 불일치 — 방법 A: 설정 페이지에서 Webhook 재등록 / 방법 B: `GITHUB_WEBHOOK_SECRET` 값 확인 |
| `422` | 지원하지 않는 이벤트 타입 — Pushes + Pull requests 이벤트만 처리됨 |
| `5xx` | 서버 오류 — 서버 로그 확인 (`railway logs` 또는 `journalctl -u scamanager`) |
| 연결 실패 | Payload URL 오타 또는 서비스 미기동 — `GET /health` 응답 확인 |

### Webhook URL이 HTTP로 등록됨

Railway 등 리버스 프록시 환경에서 `APP_BASE_URL` 미설정 시 발생합니다.

1. 환경변수에 `APP_BASE_URL=https://your-domain` 추가 (Railway 또는 온프레미스 도메인)
2. 설정 페이지 → **🔗 Webhook 재등록** 클릭

### Telegram 알림이 오지 않음

```bash
# Bot이 채팅방에 메시지를 보낼 수 있는지 확인
curl "https://api.telegram.org/bot<BOT_TOKEN>/sendMessage" \
  -d "chat_id=<CHAT_ID>&text=테스트"
```

- Bot을 채팅방에 초대했는지 확인
- `TELEGRAM_CHAT_ID` 앞의 `-` 기호 포함 여부 확인 (그룹 채팅은 음수)

### GitHub PR Comment가 게시되지 않음

- 방법 A: 리포 추가 시 사용한 GitHub 계정의 토큰 스코프 확인 (`repo user:email`)
- 방법 B: `GITHUB_TOKEN`의 `repo` scope 권한 확인
- Railway Variables에서 토큰 앞뒤 공백 없는지 확인

### CLI Hook이 실행되지 않음

```bash
# Claude Code CLI 설치 여부 확인
command -v claude

# 훅 파일 존재 여부 확인
cat .git/hooks/pre-push

# 서버 연결 확인
curl https://your-domain/api/hook/verify?repo=owner/repo&token=TOKEN
```

- `claude` 미설치 → Claude Code CLI 설치 필요 (데스크탑 환경만 지원)
- GitHub Codespaces · 모바일 → `python -m src.cli review` 사용

### AI 리뷰 결과가 없고 점수가 낮음

`ANTHROPIC_API_KEY`가 설정되지 않으면 AI 항목(커밋 메시지·방향성·테스트)이 기본값으로 처리됩니다. AI 리뷰를 원하면 Anthropic Console에서 API 키를 발급하여 설정하세요.

---

## 빠른 설정 체크리스트

### 방법 A (권장)

```
□ 1. GitHub OAuth App 생성 → Client ID / Secret 발급
□ 2. 서버 환경변수 설정
     - GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, SESSION_SECRET
     - APP_BASE_URL=https://your-domain  ← 리버스 프록시 필수
     - TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
     - DATABASE_URL
     - (선택) DATABASE_URL_FALLBACK=...supabase.co...  ← DB Failover
□ 3. 웹 UI에서 GitHub 로그인
□ 4. 리포지토리 추가 → Webhook 자동 생성 확인
□ 5. 테스트 Push → Telegram 알림 + 대시보드 확인
□ 6. GET /health → {"status":"ok","active_db":"primary"} 확인
□ 7. (선택) 로컬 클론에서 bash .scamanager/install-hook.sh 실행
□ 8. (선택) 설정 탭에서 PR 리뷰 댓글 · Gate 모드 · Auto Merge 설정
□ 9. (기존 리포) Webhook 재등록 → check_suite 이벤트 구독 확인 (Phase 12 check_suite 섹션 참조)
```

### 방법 B (레거시)

```
□ 1. Webhook Secret 생성
□ 2. GitHub 리포 Settings → Webhooks 등록
     - Payload URL: https://your-domain/webhooks/github
     - Content type: application/json / Events: Pushes + Pull requests
□ 3. GitHub PAT 발급 (repo scope)
□ 4. 서버 환경변수 설정
     - GITHUB_WEBHOOK_SECRET, GITHUB_TOKEN
     - TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
     - DATABASE_URL
□ 5. 테스트 Push → Telegram 알림 확인
```
