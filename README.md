# SCAManager

GitHub 리포지토리에 Push 또는 Pull Request 이벤트가 발생하면 자동으로 코드를 분석하고, 점수와 개선사항을 Telegram·GitHub PR Comment·Discord·Slack·Email·n8n으로 전달하는 코드 품질 관리 서비스입니다.  
`git push` 시 Claude Code CLI 기반 **로컬 pre-push 자동 코드리뷰**와 터미널에서 바로 실행하는 **CLI 코드리뷰 도구**도 제공합니다.

---

## 주요 기능

### GitHub OAuth 로그인
- GitHub 계정으로 로그인 — 별도 가입 없이 바로 사용
- 로그인한 사용자가 직접 리포지토리를 추가하고 Webhook을 자동 생성

### 자동 코드 분석 (서버 Webhook)
- Push 및 PR 이벤트 발생 시 **모든 변경 파일**을 분석 대상으로 수집
  - PR은 `opened` / `synchronize` / `reopened` action만 처리
- **정적 분석** (`.py` 파일): pylint, flake8, bandit
  - 테스트 파일(`test_*.py`)은 bandit 제외 (assert 오탐 방지)
- **AI 리뷰** (모든 파일): Claude AI를 통한 커밋 메시지 품질 및 구현 방향성 평가
- 100점 만점의 점수 및 A~F 등급 산출

### CLI 코드리뷰 도구 (터미널 직접 실행)
- `python -m src.cli review` 명령으로 로컬 git diff를 즉시 분석
- 정적 분석 + AI 리뷰 + 점수/등급 터미널 출력
- GitHub Actions · Codespaces · 일반 터미널 모두 지원
- `ANTHROPIC_API_KEY` 환경변수 필요

```bash
# 최근 커밋과 비교 (기본)
python -m src.cli review

# 특정 브랜치 기준 비교
python -m src.cli review --base main

# 스테이징된 변경사항만 분석
python -m src.cli review --staged

# JSON 형식 출력
python -m src.cli review --json
```

### CLI Hook 자동 코드리뷰 (로컬 pre-push)
- 리포 등록 시 `.scamanager/` 설정 파일을 Repo에 자동 커밋
- `git pull && bash .scamanager/install-hook.sh` 1회 실행으로 pre-push 훅 설치
- 이후 `git push` 시 자동으로 코드리뷰 실행 — **ANTHROPIC_API_KEY 불필요**
  - 설치된 Claude Code CLI(`claude -p`)를 활용하므로 별도 API 요금 없음
- 결과는 터미널 출력 + SCAManager 대시보드에 동시 저장

> **주의:** CLI Hook은 Claude Code CLI(`claude`)가 설치된 **데스크탑 환경 전용**입니다.  
> GitHub Codespaces · 모바일 환경에서는 `claude` CLI가 없으므로 조용히 건너뜁니다.  
> 모바일/Codespaces에서 코드리뷰를 사용하려면 **CLI 코드리뷰 도구**(`python -m src.cli review`)를 이용하세요.

### 알림 전달
- **Telegram** (HTML 파싱): 점수 상세(5개 카테고리별), AI 요약, 개선 제안, 정적 분석 이슈
- **GitHub PR Comment**: 카테고리별 피드백, 파일별 피드백, 개선 제안
- **Discord**: Embed 형식 알림 (선택)
- **Slack**: Attachment 형식 알림 (선택)
- **Generic Webhook**: 범용 JSON POST (선택)
- **Email**: SMTP HTML 이메일 (선택)
- **n8n**: 외부 n8n 워크플로우로 분석 결과 전달 (선택)

### PR Gate Engine
- 점수 기반으로 PR Approve / Request Changes 자동 적용
- **자동 모드**: 임계값에 따라 즉시 GitHub Review 실행, `auto_merge` 설정 시 squash merge까지 자동
- **반자동 모드**: Telegram 인라인 버튼으로 수동 승인/반려, 승인 시 `auto_merge` 설정에 따라 merge 자동

### 웹 대시보드
- GitHub OAuth 로그인 후 사용자별 리포지토리 현황 확인
- 리포지토리 추가 — GitHub 드롭다운에서 선택 시 Webhook + CLI Hook 파일 자동 생성
- 리포지토리별 점수 추이 차트 (Chart.js) + 분석 이력
- 분석 이력 클릭 → 상세 AI 리뷰·피드백·정적 분석 이슈 확인
- 설정 페이지: Gate 모드·임계값(슬라이더+숫자 인라인)·알림 채널 설정, Webhook 재등록 버튼
  - 2컬럼 그리드 레이아웃, 카드별 그라디언트 헤더, Dark/Light/Glass 3테마 완전 대응

### REST API
- 리포지토리 목록 및 분석 이력 조회
- 점수 통계 (평균, 추이)
- X-API-Key 헤더 인증

---

## 점수 체계

| 항목 | 배점 | 분석 도구 |
|------|------|----------|
| 코드 품질 | 25점 | pylint + flake8 (error -3, warning -1) |
| 보안 | 20점 | bandit (HIGH -7, LOW/MED -2) |
| 커밋 메시지 품질 | 15점 | Claude AI (0-20 → 0-15 스케일링) |
| 구현 방향성 | 25점 | Claude AI (0-20 → 0-25 스케일링) |
| 테스트 코드 | 15점 | Claude AI (0-10 → 0-15 스케일링, 비-코드 파일 면제) |
| **합계** | **100점** | |

**등급 기준:** A (90점+) / B (75점+) / C (60점+) / D (45점+) / F (44점 이하)

> `ANTHROPIC_API_KEY` 미설정 시 AI 항목은 중립 기본값(커밋13 + 방향21 + 테스트10 = 44/55)으로 처리 — AI 없이도 최대 89점(B등급) 가능  
> CLI Hook 리뷰는 정적 분석 없이 AI 점수만 산출 (코드품질·보안은 만점 적용)

---

## 기술 스택

| 분류 | 사용 기술 |
|------|----------|
| 언어 | Python 3.13 |
| 웹 프레임워크 | FastAPI |
| 인증 | GitHub OAuth2 (authlib) + SessionMiddleware |
| 데이터베이스 | PostgreSQL + SQLAlchemy 2 + Alembic + FailoverSessionFactory |
| AI (서버) | Anthropic Claude API (claude-haiku-4-5) |
| AI (로컬 CLI) | Anthropic API (직접 호출) / Claude Code CLI (`claude -p`, Hook 전용) |
| 정적 분석 | pylint, flake8, bandit |
| 알림 | Telegram, GitHub, Discord, Slack, Webhook, Email, n8n |
| 웹 UI | Jinja2 템플릿, Chart.js, CSS Variables (3테마) |
| 배포 | Railway / 온프레미스 (systemd · nginx · Docker Compose) |

---

## 화면 구성

```
/login                          → GitHub OAuth 로그인 페이지
/repos/add                      → 리포지토리 추가 (GitHub 드롭다운 + Webhook/Hook 자동 생성)
/                               → 리포지토리 현황 목록 (최신 점수, 등급, 평균 점수)
/repos/{repo}                   → 점수 추이 차트 + 분석 이력
/repos/{repo}/analyses/{id}     → 분석 상세 (AI 리뷰·피드백·정적 분석 이슈)
/repos/{repo}/settings          → Gate 모드·임계값·알림 채널 설정 + Webhook 재등록
```

> 모든 UI 페이지는 로그인 필수 — 미로그인 시 `/login` 자동 리다이렉트

---

## API 엔드포인트

```
GET  /health                              → 헬스체크 {"status":"ok","active_db":"primary"|"fallback"}
GET  /login                               → 로그인 페이지
GET  /auth/github                         → GitHub OAuth 인증 시작
GET  /auth/callback                       → GitHub OAuth 콜백
POST /auth/logout                         → 로그아웃
GET  /repos/add                           → 리포 추가 페이지
GET  /api/github/repos                    → 사용자 GitHub 리포 목록 (드롭다운용)
POST /repos/add                           → 리포 등록 + Webhook + CLI Hook 파일 자동 생성
POST /repos/{repo}/settings               → 리포 설정 저장 (Gate 모드, 알림 채널 등)
POST /repos/{repo}/reinstall-hook         → CLI Hook 파일 재커밋
POST /repos/{repo}/reinstall-webhook      → GitHub Webhook 재등록 (URL 변경 시)
POST /webhooks/github                     → GitHub Webhook 수신
POST /api/webhook/telegram                → Telegram 반자동 Gate 콜백 수신
GET  /api/repos                           → 리포지토리 목록 (API Key 인증)
GET  /api/repos/{repo}/analyses           → 분석 이력 (페이지네이션)
PUT  /api/repos/{repo}/config             → 리포지토리 설정 변경
GET  /api/repos/{repo}/stats              → 점수 통계 및 추이
GET  /api/analyses/{id}                   → 분석 상세 조회
GET  /api/hook/verify                     → CLI Hook 등록 확인 (hook_token 인증)
POST /api/hook/result                     → CLI Hook 코드리뷰 결과 저장
```

---

## 서비스 URL

| 환경 | URL |
|------|-----|
| 운영 (온프레미스) | 배포 환경에 따라 `APP_BASE_URL`로 설정 |

---

## 시작하기

### 요구사항

- Python 3.13 이상
- PostgreSQL
- GitHub OAuth App (Client ID / Client Secret)

### 설치

```bash
git clone https://github.com/xzawed/SCAManager.git
cd SCAManager
pip install -r requirements.txt
```

### 환경변수 설정

`.env.example`을 복사하여 `.env` 파일을 생성하고 각 값을 설정합니다.

```bash
cp .env.example .env
```

| 변수 | 필수 | 설명 |
|------|------|------|
| `DATABASE_URL` | ✅ | PostgreSQL 연결 URL (`postgres://` → `postgresql://` 자동 변환) |
| `TELEGRAM_BOT_TOKEN` | ✅ | Telegram Bot API 토큰 |
| `TELEGRAM_CHAT_ID` | ✅ | 알림 수신 채팅 ID |
| `GITHUB_CLIENT_ID` | ✅ | GitHub OAuth App 클라이언트 ID |
| `GITHUB_CLIENT_SECRET` | ✅ | GitHub OAuth App 클라이언트 시크릿 |
| `SESSION_SECRET` | ✅ | 세션 쿠키 서명 키 (32자 이상 랜덤 문자열) |
| `APP_BASE_URL` | 권장 | Railway 등 리버스 프록시에서 HTTPS redirect_uri 및 Webhook URL 강제 지정 |
| `ANTHROPIC_API_KEY` | - | Claude AI 리뷰 API 키 (미설정 시 기본값 적용, CLI Hook은 불필요) |
| `API_KEY` | - | REST API 인증 키 (미설정 시 인증 생략) |
| `GITHUB_WEBHOOK_SECRET` | - | 레거시 리포용 Webhook 시크릿 (신규 리포는 자동 생성) |
| `GITHUB_TOKEN` | - | 레거시 리포용 GitHub API 토큰 (신규 리포는 사용자 토큰 자동 사용) |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` | - | Email 알림 사용 시 SMTP 설정 |
| `DATABASE_URL_FALLBACK` | - | Failover용 Supabase URL (빈 값이면 단일 엔진 모드) |
| `DB_FAILOVER_PROBE_INTERVAL` | - | Primary DB 복구 확인 주기 초 (기본 30) |
| `DB_SSLMODE` | - | PostgreSQL SSL 모드 (`require` / `disable` 등, 빈 값=미적용) |
| `DB_FORCE_IPV4` | - | Railway IPv4 강제 연결 (`true` — 온프레미스에서는 `false`) |

### 실행

```bash
uvicorn src.main:app --reload --port 8000
```

> DB 마이그레이션은 앱 시작 시 자동으로 실행됩니다.

---

## GitHub Codespaces (모바일/원격 개발)

브라우저 또는 모바일 터미널에서 완전한 개발 환경을 사용하려면:

1. GitHub 리포지토리 → **Code** 버튼 → **Codespaces** 탭 → **Create codespace**
2. 컨테이너 시작 후 `pip install -r requirements.txt` 자동 실행
3. 테스트 즉시 실행 가능 — `.env` 불필요 (SQLite 인메모리 DB 사용)

```bash
make test        # 전체 테스트 실행
make lint        # 코드 품질 검사
make run         # 개발 서버 (포트 8000 자동 포워딩)

# CLI 코드리뷰 도구 (ANTHROPIC_API_KEY 필요)
ANTHROPIC_API_KEY=sk-ant-... python -m src.cli review
```

> Codespaces에서는 Claude Code CLI(`claude`)가 없으므로 **CLI Hook은 동작하지 않습니다.**  
> CLI 코드리뷰 도구(`python -m src.cli review`)를 대신 사용하세요.

---

## GitHub OAuth App 설정

1. GitHub → **Settings → Developer settings → OAuth Apps → New OAuth App**
2. 아래와 같이 입력:

| 항목 | 값 |
|------|-----|
| Application name | SCAManager |
| Homepage URL | `https://your-domain` |
| Authorization callback URL | `https://your-domain/auth/callback` |

3. 생성 후 **Client ID**와 **Client Secret**을 환경변수에 설정

> 로컬 개발 시 callback URL을 `http://localhost:8000/auth/callback`으로 추가 등록하거나, 별도 OAuth App을 생성하세요.
> `APP_BASE_URL`이 설정된 경우 그 값이 OAuth redirect_uri와 Webhook URL에 자동 적용됩니다.

---

## 리포지토리 추가 방법

로그인 후 대시보드에서 **+ 리포 추가** 버튼을 클릭합니다.

1. GitHub 드롭다운에서 원하는 리포지토리 선택
2. **Webhook 생성 + 리포 추가** 클릭
3. GitHub Webhook이 자동으로 생성되고 대시보드에 리포가 등록됩니다
4. `.scamanager/config.json`과 `install-hook.sh`가 해당 Repo에 자동 커밋됩니다

> Push 또는 PR 이벤트가 발생하면 자동으로 분석이 시작됩니다.

### Webhook URL 변경 시 (배포 URL 이전 등)

기존에 HTTP로 등록되었거나 배포 URL이 변경된 경우:

1. 대시보드 → 해당 리포지토리 → **설정** 탭
2. CLI Hook 카드 → **🔗 Webhook 재등록** 버튼 클릭
3. 현재 `APP_BASE_URL` 기준으로 Webhook이 재생성됩니다

### CLI Hook 설치 (로컬 자동 코드리뷰)

리포 등록 완료 후 로컬 클론에서 1회 실행합니다.

```bash
git pull
bash .scamanager/install-hook.sh
```

이후 `git push` 시마다 자동으로 코드리뷰가 실행되며, 결과는 터미널과 대시보드에서 확인할 수 있습니다.

> **요구사항:** Claude Code CLI(`claude`)가 설치된 Mac/Linux/Windows 데스크탑 환경  
> 미설치 시 `command -v claude` 체크 후 조용히 건너뛰며 push는 정상 진행됩니다.

### PR 자동 Merge 설정

대시보드 설정 페이지에서 리포지토리별로 `auto_merge`를 활성화할 수 있습니다.

| 설정 | 동작 |
|------|------|
| `approve_mode="auto"` + `auto_merge=true` | 점수 통과 시 GitHub Review Approve → squash merge 자동 실행 |
| `approve_mode="semi"` + `auto_merge=true` | Telegram 승인 버튼 클릭 시 → squash merge 자동 실행 |
| `auto_merge=false` (기본값) | GitHub Review만 수행, merge는 수동 |

> **주의:** `repo` 스코프 OAuth 토큰 또는 Fine-grained `pull_requests: write` 권한이 필요합니다.  
> Branch Protection Rules가 설정된 브랜치는 APPROVE 후에도 merge가 거부될 수 있습니다.

---

## 배포

### Railway 배포

1. Railway 프로젝트 생성 후 이 리포지토리 연결
2. **PostgreSQL 플러그인** 추가 (`DATABASE_URL` 자동 생성)
3. **Variables** 탭에서 환경변수 설정
   - 필수: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `SESSION_SECRET`
   - **필수 (Railway 배포 시):** `APP_BASE_URL=https://your-app.up.railway.app`
     - 미설정 시 OAuth redirect_uri와 Webhook URL이 `http://`로 등록되어 인증 및 Webhook 수신 실패
4. 배포 완료 — DB 마이그레이션은 자동 실행

### 온프레미스 배포

온프레미스 서버에 배포하려면 [온프레미스 마이그레이션 가이드](docs/guides/onpremise-migration-guide.md)를 참고하세요.

```bash
# 기본 시작 명령
uvicorn src.main:app --host 0.0.0.0 --port 8000 --proxy-headers
```

**DB Failover:** `DATABASE_URL_FALLBACK`에 Supabase URL을 설정하면 Primary DB 장애 시 자동으로 Supabase로 전환됩니다.  
전환 상태는 `GET /health` 응답의 `active_db` 필드로 확인할 수 있습니다.

---

## 라이선스

MIT
