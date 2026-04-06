# SCAManager

GitHub 리포지토리에 Push 또는 Pull Request 이벤트가 발생하면 자동으로 코드를 분석하고, 점수와 개선사항을 알림으로 전달하는 코드 품질 관리 서비스입니다.

---

## 주요 기능

### 자동 코드 분석
- Push 및 PR 이벤트 발생 시 변경된 파일을 자동으로 분석 (PR은 `opened`/`synchronize`/`reopened` action만 처리)
- **정적 분석**: pylint, flake8, bandit을 사용한 코드 품질 및 보안 검사
- **AI 리뷰**: Claude AI를 통한 커밋 메시지 품질 및 구현 방향성 평가
  - 카테고리별 상세 피드백 (커밋 메시지, 코드 품질, 보안, 구현 방향성, 테스트)
  - 파일별 라인 단위 피드백
  - 구체적 개선 제안
- 100점 만점의 점수 및 A~F 등급 산출

### 알림 전달
- **Telegram**: 점수 상세(5개 카테고리별), AI 요약, 개선 제안, 정적 분석 이슈 포함
- **GitHub PR Comment**: 카테고리별 피드백, 파일별 피드백, 개선 제안, 정적 분석 이슈 포함
- **n8n**: 외부 n8n 워크플로우로 분석 결과 전달 (선택)

### PR Gate Engine
- 점수 기반으로 PR Approve/Request Changes 자동 적용
- **자동 모드**: 임계값에 따라 즉시 GitHub Review 실행, `auto_merge` 설정 시 squash merge까지 자동 수행
- **반자동 모드**: Telegram 인라인 버튼으로 수동 승인/반려, 승인 시 `auto_merge` 설정에 따라 merge 자동 실행

### 웹 대시보드
- 리포지토리별 점수 추이 차트 (Chart.js)
- 분석 이력 조회
- Gate 모드 및 임계값 설정 UI

### REST API
- 리포지토리 목록 및 분석 이력 조회
- 점수 통계 (평균, 추이)
- X-API-Key 헤더 인증

---

## 점수 체계

| 항목 | 배점 | 분석 도구 |
|------|------|----------|
| 커밋 메시지 품질 | 20점 | Claude AI |
| 코드 품질 | 30점 | pylint + flake8 |
| 보안 | 20점 | bandit |
| 구현 방향성 | 20점 | Claude AI |
| 테스트 코드 | 10점 | Claude AI |
| **합계** | **100점** | |

**등급 기준:** A (90점+) / B (75점+) / C (60점+) / D (45점+) / F (44점 이하)

---

## 기술 스택

| 분류 | 사용 기술 |
|------|----------|
| 언어 | Python 3.12 |
| 웹 프레임워크 | FastAPI |
| 데이터베이스 | PostgreSQL + SQLAlchemy 2 + Alembic |
| AI | Anthropic Claude API |
| 정적 분석 | pylint, flake8, bandit |
| 알림 | Telegram Bot API, GitHub REST API |
| 웹 UI | Jinja2 템플릿, Chart.js |
| 배포 | Railway |

---

## 화면 구성

```
/                          → 리포지토리 현황 목록 (최신 점수 및 등급)
/repos/{repo}              → 점수 추이 차트 + 분석 이력
/repos/{repo}/settings     → Gate 모드 및 임계값 설정
```

---

## API 엔드포인트

```
GET  /health                              → 헬스체크
POST /webhooks/github                     → GitHub Webhook 수신
POST /api/webhook/telegram                → Telegram 반자동 Gate 콜백 수신
GET  /api/repos                           → 리포지토리 목록
GET  /api/repos/{repo}/analyses           → 분석 이력 (페이지네이션)
PUT  /api/repos/{repo}/config             → 리포지토리 설정 변경 (gate_mode, threshold, auto_merge)
GET  /api/repos/{repo}/stats              → 점수 통계 및 추이
GET  /api/analyses/{id}                   → 분석 상세 조회
```

---

## 서비스 URL

| 환경 | URL |
|------|-----|
| 운영 | https://scamanager-production.up.railway.app/ |

---

## 시작하기

### 요구사항

- Python 3.12 이상
- PostgreSQL
- GitHub 리포지토리 Admin 권한 (Webhook 등록용)

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
| `GITHUB_WEBHOOK_SECRET` | ✅ | GitHub Webhook 서명 검증용 시크릿 |
| `GITHUB_TOKEN` | ✅ | GitHub API Personal Access Token (`repo` 또는 `pull_requests: write` 권한 필요) |
| `TELEGRAM_BOT_TOKEN` | ✅ | Telegram Bot API 토큰 |
| `TELEGRAM_CHAT_ID` | ✅ | 알림 수신 채팅 ID |
| `ANTHROPIC_API_KEY` | - | Claude AI 리뷰 API 키 (미설정 시 AI 항목 기본값 적용) |
| `API_KEY` | - | 대시보드 REST API 인증 키 (미설정 시 인증 생략) |

### 실행

```bash
uvicorn src.main:app --reload --port 8000
```

> DB 마이그레이션은 앱 시작 시 자동으로 실행됩니다.

---

## GitHub 연동

GitHub 리포지토리 **Settings → Webhooks → Add webhook** 에서 아래와 같이 설정합니다.

| 항목 | 값 |
|------|-----|
| Payload URL | `https://scamanager-production.up.railway.app/webhooks/github` |
| Content type | `application/json` |
| Secret | 환경변수에 설정한 `GITHUB_WEBHOOK_SECRET` 값 |
| Events | Pushes, Pull requests (`opened`/`synchronize`/`reopened`만 처리) |

자세한 연동 절차는 [GitHub 연동 가이드](docs/github-integration-guide.md)를 참고하세요.

### PR 자동 Merge 설정

대시보드 Settings 또는 API에서 리포지토리별로 `auto_merge`를 활성화할 수 있습니다.

| 설정 | 동작 |
|------|------|
| `gate_mode=auto` + `auto_merge=true` | 점수 통과 시 GitHub Review Approve → squash merge 자동 실행 |
| `gate_mode=semi` + `auto_merge=true` | Telegram 승인 버튼 클릭 시 → squash merge 자동 실행 |
| `auto_merge=false` (기본값) | GitHub Review만 수행, merge는 수동 |

> **주의:** `GITHUB_TOKEN`에 `repo` 스코프 또는 Fine-grained `pull_requests: write` 권한이 필요합니다.
> Branch Protection Rules가 설정된 브랜치는 APPROVE 후에도 merge가 거부될 수 있습니다.

---

## Railway 배포

Railway에서 바로 배포할 수 있습니다.

1. Railway 프로젝트 생성 후 이 리포지토리 연결
2. PostgreSQL 플러그인 추가
3. 환경변수 설정 (Variables 탭)
4. 배포 완료 — DB 마이그레이션은 자동 실행

---

## 라이선스

MIT
