# SCAManager

GitHub Repository에 Push/PR 이벤트 발생 시 정적 분석 + AI 코드 리뷰를 자동 수행하고, 점수와 개선사항을 Telegram·GitHub PR Comment·n8n으로 전달하며, 점수 기반 PR 자동/반자동 Gate와 웹 대시보드를 제공하는 서비스.

## 빠른 시작

```bash
# 의존성 설치
pip install -r requirements.txt
# 또는 단축 명령
make install

# 환경 변수 설정 (테스트는 .env 없어도 실행됨 — conftest.py가 SQLite로 대체)
cp .env.example .env

# 개발 서버 실행 (DB 마이그레이션 자동 실행됨)
make run
# 또는: uvicorn src.main:app --reload --port 8000
```

> DB 마이그레이션은 앱 시작 시 `lifespan` 이벤트로 자동 실행됩니다.
> 수동 실행이 필요한 경우: `make migrate`

## Makefile 단축 명령

| 명령 | 동작 |
|------|------|
| `make install` | 의존성 설치 |
| `make test` | 전체 테스트 (빠른 출력) |
| `make test-v` | 전체 테스트 (상세 출력) |
| `make test-cov` | 테스트 + 커버리지 |
| `make test-file f=tests/test_pipeline.py` | 특정 파일 테스트 |
| `make lint` | pylint + flake8 + bandit 검사 |
| `make run` | 개발 서버 실행 (port 8000) |
| `make migrate` | DB 마이그레이션 실행 |
| `make revision m="설명"` | 새 마이그레이션 파일 생성 |

## GitHub Codespaces (모바일/원격 개발)

브라우저 또는 모바일 터미널에서 완전한 개발 환경을 사용하려면:

1. GitHub 리포지토리 페이지 → **Code** 버튼 → **Codespaces** 탭 → **Create codespace**
2. 컨테이너 시작 후 `pip install -r requirements.txt` 자동 실행됨
3. 테스트 즉시 실행 가능 — `.env` 불필요 (conftest.py가 SQLite 인메모리 DB 사용)

```bash
# Codespaces 또는 모바일 터미널에서
make test        # 테스트 전체 실행
make lint        # 코드 품질 검사
make run         # 개발 서버 (포트 8000 자동 포워딩)
```

> **주의:** 실제 GitHub·Telegram 연동 기능은 `.env`에 API 키 설정 후 사용 가능합니다.
> 단위 테스트 전체(110개)는 API 키 없이 실행됩니다.

## DB 마이그레이션

`make revision m="설명"` / `make migrate` 사용 (위 Makefile 표 참조)

### 현재 마이그레이션 파일

| 파일 | 내용 |
|------|------|
| `3b8216565fed_create_repositories_and_analyses_tables.py` | 초기 테이블 생성 |
| `0002_phase3_add_repo_config_gate_decision.py` | RepoConfig + GateDecision 추가 |

## 환경 변수

| 변수 | 설명 | 예시 | 필수 |
|------|------|------|------|
| `DATABASE_URL` | PostgreSQL 연결 URL | `postgresql://user:pass@host/db` | ✅ |
| `GITHUB_WEBHOOK_SECRET` | GitHub Webhook HMAC 서명 시크릿 | `your-secret-here` | ✅ |
| `GITHUB_TOKEN` | GitHub API Personal Access Token | `ghp_xxxx` | ✅ |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API 토큰 | `123456:ABC-xxx` | ✅ |
| `TELEGRAM_CHAT_ID` | Telegram 알림 수신 Chat ID | `-100xxxxxxxxx` | ✅ |
| `ANTHROPIC_API_KEY` | Claude AI 리뷰 API 키 | `sk-ant-xxxx` | ❌ (없으면 AI 리뷰 건너뜀) |
| `API_KEY` | Dashboard API 인증 키 | `any-secret-string` | ❌ (없으면 인증 건너뜀) |

**주의:** `.env` 파일은 절대 git commit 하지 말 것 (`.gitignore`에 포함됨)

## 프로젝트 구조

```
src/
├── main.py                     # FastAPI 앱, lifespan(DB 마이그레이션), 전체 라우터 등록
├── config.py                   # pydantic-settings 환경변수 관리, postgres:// URL 자동 변환
├── database.py                 # SQLAlchemy engine, Base, SessionLocal
├── models/
│   ├── repository.py           # Repository ORM
│   ├── analysis.py             # Analysis ORM
│   ├── repo_config.py          # RepoConfig ORM (gate_mode, threshold, n8n_url)
│   └── gate_decision.py        # GateDecision ORM (analysis_id, decision, mode)
├── webhook/
│   ├── validator.py            # HMAC-SHA256 서명 검증
│   └── router.py               # POST /webhooks/github, POST /api/webhook/telegram
├── github_client/
│   └── diff.py                 # get_pr_files, get_push_files, ChangedFile
├── analyzer/
│   ├── static.py               # analyze_file — pylint/flake8/bandit
│   └── ai_review.py            # review_code() — Claude API, AiReviewResult
├── scorer/
│   └── calculator.py           # calculate_score(ai_review), ScoreResult, _grade
├── config_manager/
│   └── manager.py              # get_repo_config(), upsert_repo_config(), RepoConfigData
├── gate/
│   ├── engine.py               # run_gate_check() — auto/semi-auto 분기
│   ├── github_review.py        # post_github_review() — GitHub Review API
│   └── telegram_gate.py        # send_gate_request() — 인라인 키보드 메시지
├── notifier/
│   ├── telegram.py             # send_analysis_result()
│   ├── github_comment.py       # post_pr_comment()
│   └── n8n.py                  # notify_n8n() — n8n Webhook POST
├── api/
│   ├── auth.py                 # require_api_key Depends (X-API-Key 헤더)
│   ├── repos.py                # GET/PUT /api/repos, /api/repos/{repo}/analyses, /config
│   └── stats.py                # GET /api/analyses/{id}, /api/repos/{repo}/stats
├── ui/
│   └── router.py               # Jinja2 Web UI — /, /repos/{repo}, /repos/{repo}/settings
├── templates/
│   ├── base.html               # 공통 레이아웃
│   ├── overview.html           # 리포 현황 목록
│   ├── repo_detail.html        # 점수 차트(Chart.js) + 분석 이력
│   └── settings.html           # Gate 모드·임계값 설정 폼
└── worker/
    └── pipeline.py             # run_analysis_pipeline — 전체 파이프라인

tests/                          # 110개 테스트 (Phase 1~5)
├── conftest.py
├── test_config.py, test_models.py, test_repo_config_model.py
├── test_github_diff.py, test_webhook_router.py, test_webhook_validator.py
├── test_webhook_telegram.py    # Telegram callback endpoint
├── test_static_analyzer.py, test_ai_review.py
├── test_scorer.py, test_pipeline.py
├── test_notifier_telegram.py, test_github_comment.py, test_n8n_notifier.py
├── test_config_manager.py
├── test_gate_engine.py, test_github_review.py, test_telegram_gate.py
├── test_api_auth.py, test_api_repos.py, test_api_stats.py
└── test_ui_router.py

docs/superpowers/
├── specs/2026-04-05-scamanager-design.md
└── plans/ (phase1~5 구현 계획)
```

## 핵심 데이터 흐름

```
GitHub Push/PR
  → POST /webhooks/github (HMAC 서명 검증)
  → BackgroundTasks 비동기 등록
  → run_analysis_pipeline()
      → get_pr_files / get_push_files (변경 파일 목록)
      → asyncio.gather() 병렬 실행:
          ├─ analyze_file() × N  (pylint + flake8 + bandit)
          └─ review_code()       (Claude AI — 커밋 메시지 + diff 분석)
      → calculate_score(ai_review)
          (커밋20 + 코드품질30 + 보안20 + AI방향성20 + 테스트10)
      → DB 저장 (Analysis 레코드)
      → run_gate_check() [PR 이벤트만]
          [auto]      → GitHub Approve / Request Changes 즉시 실행
          [semi-auto] → Telegram 인라인 키보드 전송 → POST /api/webhook/telegram 콜백 수신
      → asyncio.gather(return_exceptions=True):
          ├─ send_analysis_result()  (Telegram 알림)
          ├─ post_pr_comment()       (PR 이벤트 시 GitHub PR Comment)
          └─ notify_n8n()            (n8n_webhook_url 설정 시)

Telegram 반자동 콜백:
  → POST /api/webhook/telegram
  → gate:approve:{id} or gate:reject:{id} 파싱
  → post_github_review() + GateDecision DB 저장

대시보드:
  → GET /              (리포 현황 Web UI)
  → GET /repos/{repo}  (점수 차트 + 이력 Web UI)
  → GET /api/repos     (REST API)
  → GET /api/repos/{repo}/stats (통계 API)
```

## 점수 체계

| 항목 | 배점 | 도구 |
|------|------|------|
| 커밋 메시지 품질 | 20점 | Claude AI 분석 |
| 코드 품질 | 30점 | pylint + flake8 |
| 보안 | 20점 | bandit |
| 구현 방향성 | 20점 | Claude AI 분석 |
| 테스트 | 10점 | AI가 테스트 코드 존재 여부 판단 |

등급: A(90+), B(75+), C(60+), D(45+), F(44-)

> `ANTHROPIC_API_KEY` 미설정 시 AI 항목은 기본값(커밋15 + 방향15, 테스트5)으로 fallback

## 알려진 주의사항 (Gotchas)

- **테스트 환경 변수**: `tests/conftest.py`가 `os.environ.setdefault`로 환경변수를 주입함. src 모듈은 import 시점에 `Settings()`를 인스턴스화하므로 conftest가 반드시 먼저 실행되어야 함
- **psycopg2 버전**: Python 3.13에서는 `psycopg2-binary==2.9.11` 이상 필요
- **멱등성**: `run_analysis_pipeline`은 commit SHA로 중복 체크 — 같은 SHA는 재분석 건너뜀
- **비동기 테스트**: `pytest.ini`의 `asyncio_mode = auto` 필수 (없으면 async 테스트 실패)
- **postgres:// URL**: Railway PostgreSQL이 `postgres://`로 제공하는 경우 config.py에서 `postgresql://`로 자동 변환
- **AI 리뷰 JSON 파싱**: Claude가 JSON 앞에 설명 텍스트를 붙이는 경우 `re.search`로 코드 블록 내 JSON만 추출
- **알림 독립성**: `asyncio.gather(return_exceptions=True)` — Telegram 또는 GitHub Comment 중 하나 실패해도 나머지는 계속 실행
- **Webhook 서명**: `X-Hub-Signature-256` 헤더 없으면 403 반환 — 로컬 테스트 시 서명 생성 필요

## Railway 배포

```bash
# 시작 명령 (railway.toml에 설정됨)
uvicorn src.main:app --host 0.0.0.0 --port $PORT
# DB 마이그레이션은 앱 lifespan에서 자동 실행
```

Railway 대시보드 설정:
- **PostgreSQL 플러그인** 추가 (`DATABASE_URL` 자동 생성)
- **Variables** 탭에서 나머지 환경변수 설정
- `DATABASE_URL` 참조: `${{Postgres.DATABASE_URL}}`

헬스체크 엔드포인트: `GET /health` (healthcheckTimeout: 60초)

## Agent 작업 규칙

모든 AI 에이전트(Claude Code 및 서브에이전트)는 SCAManager 작업 시 아래 규칙을 **반드시** 따른다.
`.claude/` 디렉토리에 정의된 스킬과 에이전트는 선택이 아닌 의무적 도구다.

### 필수 원칙

- **TDD 우선**: 구현 코드 작성 전 반드시 `test-writer` 에이전트로 테스트를 먼저 작성한다.
- **Hook 신뢰**: `src/` 파일 편집 후 PostToolUse Hook이 자동 실행하는 pytest 결과를 확인한다. 실패 시 다음 단계로 진행하지 않는다.
- **Phase 완료 조건**: 테스트 전체 통과 + `/lint` 통과 + (파이프라인 변경 시 `pipeline-reviewer` 승인) 세 조건이 모두 충족될 때만 Phase 완료를 선언한다.

### 모바일 환경 보호 — 수정 금지 파일

아래 파일들은 자동화 테스트로 검증이 불가능한 고위험 영역이다.
**`pytest, fastapi, sqlalchemy`가 import 불가능한 환경(테스트 환경 미구성)에서는 절대 수정하지 않는다.**
PreToolUse Hook(`.claude/hooks/check_edit_allowed.py`)이 자동으로 차단한다.

| 파일/경로 | 위험 유형 | 차단 조건 |
|-----------|----------|----------|
| `alembic/versions/` | DB 스키마 손상, 데이터 손실 | 테스트 환경 없을 때 |
| `src/templates/*.html` | Jinja2 렌더링 오류 (pytest 미감지) | 테스트 환경 없을 때 |
| `railway.toml` | 프로덕션 배포 실패 | 테스트 환경 없을 때 |
| `Procfile` | 프로덕션 시작 명령 오류 | 테스트 환경 없을 때 |
| `alembic.ini` | Alembic 경로 설정 오류 | 테스트 환경 없을 때 |

**예외:** `make test` 가 정상 실행되는 환경(로컬 PC, GitHub Codespaces)에서는 모든 파일 수정이 허용된다.

### 작업 유형별 필수 실행 순서

**1. 새 기능 구현 시**
1. `test-writer` 에이전트 → 테스트 파일 작성 (Red)
2. Hook 자동 실행 → 실패 확인 (Red 검증)
3. 구현 코드 작성
4. Hook 자동 실행 → 통과 확인 (Green)
5. `/lint` → 코드 품질 검사 (Refactor)
6. `/test coverage` → 커버리지 확인

**2. 파이프라인 수정 시** (`src/worker/`, `src/analyzer/`, `src/scorer/`)
1. `test-writer` 에이전트 → 변경 대상 테스트 선작성
2. 구현 후 Hook 자동 실행 결과 확인
3. `pipeline-reviewer` 에이전트 → 멱등성·오류 처리·성능 검토
4. `/lint` → 보안(bandit) 포함 전체 검사

**3. Webhook/API 수정 시** (`src/webhook/`, `src/notifier/`, `src/main.py`)
1. `test-writer` 에이전트 → 엔드포인트 테스트 선작성
2. 구현 후 `/test webhook` 또는 `/test pipeline`으로 모듈 테스트
3. `/webhook-test` → 로컬 서버에서 실제 엔드-투-엔드 검증
4. 서명 검증 로직 변경 시 403/202 응답 코드 직접 확인

**4. 다음 Phase 착수 시**
1. 현행 Phase 완료 조건 모두 충족 확인 (`/test`, `/lint`)
2. `/phase-next` → 브레인스토밍 및 설계 시작
3. 설계 문서 작성 후 `test-writer` 에이전트로 Phase 첫 테스트 작성

### 도구 사용 시점 요약

| 도구 | 사용 시점 | 통과 기준 |
|------|----------|----------|
| PostToolUse Hook | `src/` 파일 편집 직후 자동 실행 | 0 failed |
| `/test` | Hook 실패 시 상세 분석, PR 생성 전 | 전체 통과 |
| `/test coverage` | Phase 완료 전 커버리지 확인 | 커버리지 유지 또는 향상 |
| `/lint` | 테스트 통과 후 (Refactor 단계), Phase 완료 전 | pylint 8.0+, bandit HIGH 0 |
| `/webhook-test` | Webhook·파이프라인·알림 경로 변경 후 | 202 Accepted 응답 |
| `/phase-next` | Phase 완료 조건 충족 후, 다음 Phase 착수 전 | — |
| `test-writer` 에이전트 | 모든 신규 기능·모듈 구현 착수 전 | 테스트 파일 먼저 생성 |
| `pipeline-reviewer` 에이전트 | 파이프라인 핵심 파일 변경 후 | 전 항목 ✅ |

## 구현 Phase 현황

| Phase | 내용 | 상태 |
|-------|------|------|
| Phase 1 | Webhook → 정적 분석 → Telegram 알림 (MVP) | ✅ 완료 (35 테스트) |
| Phase 2 | Claude AI 리뷰 + 커밋 메시지 점수 + GitHub PR Comment | ✅ 완료 (65 테스트) |
| Phase 3 | PR Gate Engine (자동/반자동) + Config Manager | ✅ 완료 (~30 테스트) |
| Phase 4 | Dashboard API + Web UI (Jinja2 + Chart.js) | ✅ 완료 (~15 테스트) |
| Phase 5 | n8n 연동 + 외부 REST API + 통계 고도화 | ✅ 완료 (~4 테스트, 총 110 테스트) |
