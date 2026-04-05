# SCAManager — 시스템 설계 문서

**작성일:** 2026-04-05  
**최종 업데이트:** 2026-04-05  
**상태:** Phase 1+2 완료, Phase 3 예정  
**기술 스택:** Python 3.12 + FastAPI, PostgreSQL, Railway

---

## 1. 프로젝트 개요

GitHub Repository에 Push 또는 PR 이벤트가 발생하면 자동으로 코드를 정적 분석하고 AI 리뷰를 수행하여 점수와 개선사항을 개발자에게 전달하는 서비스.

### 핵심 목표

- GitHub Webhook으로 코드 변경을 실시간 감지
- 정적 분석 도구 + Claude API를 병렬로 실행하여 코드 품질 검토
- 커밋 메시지, 코드 품질, 구현 방향성을 항목별로 점수화
- 리포지토리별로 PR 승인/반려 규칙을 커스터마이징 가능
- 분석 결과를 Telegram으로 즉시 통보, 대시보드에서 이력/통계 조회

---

## 2. 대상 규모

- 리포지토리: 10~100개
- 일일 커밋/PR: 수백 건
- 배포 플랫폼: Railway (클라우드)

---

## 3. 기술 스택

| 영역 | 기술 |
|------|------|
| 언어 | Python 3.12 |
| 웹 프레임워크 | FastAPI |
| 비동기 작업 | ARQ (Redis 기반 작업 큐) 또는 FastAPI BackgroundTasks |
| 데이터베이스 | PostgreSQL (Railway 기본 제공) |
| ORM | SQLAlchemy + Alembic (마이그레이션) |
| AI 리뷰 | Anthropic Claude API (`anthropic` SDK) |
| 정적 분석 | pylint, bandit, flake8 (subprocess 호출, 언어별 확장 가능) |
| GitHub 연동 | PyGithub + Webhook 수신 |
| 텔레그램 | python-telegram-bot |
| 대시보드 UI | FastAPI로 서빙 (Jinja2 템플릿 또는 단일 HTML + JS) |
| 배포 | Railway (Docker 또는 Python buildpack) |

---

## 4. 시스템 아키텍처

### 컴포넌트 구성

```
① Webhook Handler      — GitHub 이벤트 수신 및 서명(HMAC) 검증
② 작업 큐 (비동기)     — 이벤트를 큐에 등록, 워커가 백그라운드 처리
③ Analyzer             — 정적 분석 도구 + Claude API 병렬 실행
④ Scorer               — 항목별 점수 산정 및 등급 부여
⑤ PR Gate Engine       — 리포별 규칙에 따라 자동/반자동 승인·반려 처리
⑥ Config Manager       — 리포지토리별 분석 규칙, 임계값, 모드 관리
⑦ Notifier             — Telegram 및 GitHub Review 멀티채널 전송
⑧ Dashboard API        — 분석 이력 조회, 통계, 설정 변경 REST API
⑨ 대시보드 Web UI      — 브라우저 기반 관리 및 통계 페이지
```

### 데이터 흐름

```
GitHub Push/PR
  → ① Webhook Handler (서명 검증)
  → ② 작업 큐 등록
  → ③ Analyzer (pylint/bandit/flake8 + Claude API 병렬)
  → ④ Scorer (커밋 메시지 + 코드 품질 + 구현 방향 점수 합산)
  → PostgreSQL 결과 저장
  → ⑤ PR Gate Engine (Config 기반 자동/반자동 판단)
      [자동 모드]  → GitHub Approve / Request Changes 즉시 실행
      [반자동 모드] → Telegram 버튼 메시지 전송 → 담당자 응답 → GitHub 처리
  → ⑦ Notifier → Telegram 분석 결과 알림 + GitHub PR Comment
```

---

## 5. 컴포넌트 상세 설계

### ① Webhook Handler

- 엔드포인트: `POST /webhooks/github`
- GitHub HMAC-SHA256 서명 검증 (`X-Hub-Signature-256`)
- 처리 이벤트: `push`, `pull_request` (opened, synchronize, reopened)
- 검증 통과 후 즉시 202 응답 → 비동기 큐에 작업 등록

### ② 작업 큐

- 중규모 트래픽(수백 건/일) 대응을 위해 비동기 처리 필수
- Phase 1~3: FastAPI `BackgroundTasks`로 시작 (별도 인프라 불필요)
- Phase 4 이후 트래픽 증가 시: ARQ (Redis) 로 전환
- 중복 이벤트 방지: 커밋 SHA 기반 idempotency 키

### ③ Analyzer

- **정적 분석**: pylint, bandit, flake8을 subprocess로 실행
  - 언어 감지 후 해당 도구 선택 (Python 외 언어는 추후 확장)
  - diff 기준으로 변경된 파일만 분석
- **AI 리뷰**: Claude API에 diff + 커밋 메시지 전달
  - 커밋 메시지 품질, 구현 방향, 보안 이슈, 개선 제안 요청
  - 응답은 구조화된 JSON 형태로 파싱
- 두 분석을 `asyncio.gather`로 병렬 실행

### ④ Scorer

점수 항목 (합계 100점):

| 항목 | 배점 | 기준 |
|------|------|------|
| 커밋 메시지 품질 | 20점 | 컨벤션 준수, 변경 범위 일치성 |
| 코드 품질 | 30점 | 정적 분석 에러/경고 수 |
| 보안 | 20점 | bandit 취약점 수준 |
| 구현 방향성 | 20점 | Claude AI 평가 |
| 테스트 | 10점 | 테스트 코드 존재 여부 |

- 등급: A(90+), B(75+), C(60+), D(45+), F(44-)
- 점수 기준은 Config Manager에서 리포별로 조정 가능

### ⑤ PR Gate Engine

- 리포별 설정에서 모드 확인:
  - **자동 모드**: 점수 ≥ 임계값 → GitHub Approve, 미달 → Request Changes 즉시 실행
  - **반자동 모드**: Telegram으로 분석 결과 + [승인] / [반려] 인라인 버튼 전송 → 담당자 선택 → GitHub 처리
- 반자동 모드의 Telegram 응답은 Callback Query Handler로 수신
- PR Gate 결과(자동/수동, 결정자, 시각)를 DB에 기록

### ⑥ Config Manager

리포지토리별 설정 항목:

```json
{
  "repo": "owner/repo-name",
  "gate_mode": "auto" | "semi-auto",
  "auto_approve_threshold": 75,
  "auto_reject_threshold": 50,
  "notify_telegram_chat_id": "-100xxxxxxxxx",
  "n8n_webhook_url": "https://your-n8n-instance/webhook/xxx",
  "analysis_rules": {
    "enable_bandit": true,
    "enable_pylint": true,
    "max_line_length": 120
  }
}
```

- 설정은 PostgreSQL에 저장, Dashboard UI에서 변경 가능
- 기본값(default config) 상속 구조: 글로벌 → 리포별 오버라이드

### ⑦ Notifier

- **Telegram**: 분석 요약 + 점수 + 등급 + 주요 이슈 메시지
- **GitHub PR Comment**: 상세 분석 결과 및 개선 제안 마크다운 코멘트
- **GitHub Commit Status**: Check API로 통과/실패 상태 표시

### ⑧ Dashboard API

주요 엔드포인트:

```
GET  /api/repos                        — 등록된 리포 목록
GET  /api/repos/{repo}/analyses        — 분석 이력 (페이지네이션)
GET  /api/repos/{repo}/stats           — 점수 추이, 개발자별 통계
GET  /api/analyses/{id}                — 분석 상세 결과
PUT  /api/repos/{repo}/config          — 리포 설정 변경
POST /api/webhook/telegram             — Telegram Callback 수신
```

- 인증: API Key 방식 (초기), JWT 확장 가능
- n8n 연동: Notifier가 분석 완료 시 n8n Webhook URL로 결과 POST

### ⑨ 대시보드 Web UI

페이지 구성:

- **Overview**: 전체 리포 점수 현황 카드, 최근 분석 피드
- **Repository 상세**: 점수 추이 차트, 커밋별 분석 이력
- **개발자 통계**: 개발자별 평균 점수, 개선 추이
- **설정**: 리포별 Gate 모드, 임계값, 분석 규칙 설정
- 구현: FastAPI Jinja2 + Chart.js (서버 렌더링, 별도 프론트엔드 빌드 불필요)

---

## 6. 데이터 모델 (주요 테이블)

```
repositories     — repo 식별자, 설정, 등록일
analyses         — repo_id, commit_sha, pr_number, 점수, 등급, 분석 결과 JSON, 생성일
gate_decisions   — analysis_id, 결정(approve/reject), 모드(auto/manual), 결정자, 시각
repo_configs     — repo_id, 설정 JSON, 수정일
```

---

## 7. 외부 연동

| 대상 | 연동 방식 |
|------|----------|
| GitHub | Webhook 수신 + PyGithub API (Review, Comment, Status) |
| Claude API | `anthropic` Python SDK, 스트리밍 없이 단건 호출 |
| Telegram | `python-telegram-bot` (Bot API, Callback Query) |
| n8n | 분석 완료 시 설정된 Webhook URL로 HTTP POST |
| Railway | 환경 변수로 시크릿 관리, PostgreSQL 플러그인 연결 |

---

## 8. 보안 고려사항

- GitHub Webhook 서명 검증 필수 (HMAC-SHA256)
- 모든 시크릿은 Railway 환경 변수로 관리 (코드에 하드코딩 금지)
- 코드 diff에 포함된 민감 정보가 로그에 남지 않도록 처리
- Dashboard API 인증 필수 (API Key 최소 적용)
- Claude API 호출 시 diff 크기 제한 (토큰 비용 및 속도 관리)

---

## 9. 구현 순서 (단계별)

| Phase | 내용 | 상태 | 테스트 |
|-------|------|------|--------|
| Phase 1 | Webhook 수신 → 정적 분석 → Telegram 알림 (MVP) | ✅ 완료 | 35개 |
| Phase 2 | Claude AI 리뷰 + Scorer + GitHub PR Comment | ✅ 완료 | 65개 |
| Phase 3 | PR Gate Engine (자동/반자동) + Config Manager | 예정 | — |
| Phase 4 | Dashboard API + Web UI (Jinja2 + Chart.js) | 예정 | — |
| Phase 5 | n8n 연동 + 외부 REST API + 통계 고도화 | 예정 | — |

### Phase 2 구현 내용 (2026-04-05 완료)

- `src/analyzer/ai_review.py`: Claude Haiku API로 diff + 커밋 메시지 분석, JSON 응답 파싱
- `src/notifier/github_comment.py`: httpx로 GitHub REST API 호출, PR에 마크다운 리포트 게시
- `src/scorer/calculator.py`: AI 리뷰 점수(커밋20 + 방향성20 + 테스트10) 실제 반영
- `src/worker/pipeline.py`: `asyncio.gather` 병렬 분석, `return_exceptions=True` 알림 독립성
- `src/config.py`: `ANTHROPIC_API_KEY` 추가, `postgres://` → `postgresql://` 자동 변환
- `src/main.py`: FastAPI lifespan으로 DB 마이그레이션 자동화 (Railway 배포 안정성)
