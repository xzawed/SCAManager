# SCAManager

GitHub Repository에 Push/PR 이벤트 발생 시 정적 분석 + AI 코드 리뷰를 자동 수행하고, 점수와 개선사항을 Telegram으로 전달하는 서비스.

## 빠른 시작

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정 (아래 환경 변수 섹션 참고)
cp .env.example .env  # 없으면 직접 .env 생성

# DB 마이그레이션
alembic upgrade head

# 개발 서버 실행
uvicorn src.main:app --reload --port 8000
```

## 테스트

```bash
# 전체 테스트 실행
pytest

# 특정 모듈 테스트
pytest tests/test_pipeline.py -v
pytest tests/test_static_analyzer.py -v

# 커버리지 포함
pytest --cov=src --cov-report=term-missing
```

## 코드 품질 검사

```bash
pylint src/
flake8 src/
bandit -r src/
```

## DB 마이그레이션

```bash
# 새 모델 변경 후 마이그레이션 파일 생성
alembic revision --autogenerate -m "설명"

# 마이그레이션 적용
alembic upgrade head

# 롤백
alembic downgrade -1
```

## 환경 변수

| 변수 | 설명 | 예시 |
|------|------|------|
| `DATABASE_URL` | PostgreSQL 연결 URL | `postgresql://user:pass@host/db` |
| `GITHUB_WEBHOOK_SECRET` | GitHub Webhook HMAC 서명 시크릿 | `your-secret-here` |
| `GITHUB_TOKEN` | GitHub API Personal Access Token | `ghp_xxxx` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API 토큰 | `123456:ABC-xxx` |
| `TELEGRAM_CHAT_ID` | Telegram 알림 수신 Chat ID | `-100xxxxxxxxx` |

**주의:** `.env` 파일은 절대 git commit 하지 말 것 (`.gitignore`에 포함됨)

## 프로젝트 구조

```
src/
├── main.py                  # FastAPI 앱 진입점, webhook_router 등록
├── config.py                # pydantic-settings 환경변수 관리
├── database.py              # SQLAlchemy engine, Base, get_db()
├── models/
│   ├── repository.py        # Repository ORM 모델
│   └── analysis.py          # Analysis ORM 모델
├── webhook/
│   ├── validator.py         # HMAC-SHA256 서명 검증
│   └── router.py            # POST /webhooks/github 엔드포인트
├── github_client/
│   └── diff.py              # get_pr_files, get_push_files, ChangedFile
├── analyzer/
│   └── static.py            # analyze_file — pylint/flake8/bandit subprocess 호출
├── scorer/
│   └── calculator.py        # calculate_score, ScoreResult, _grade
├── notifier/
│   └── telegram.py          # send_analysis_result, _build_message
└── worker/
    └── pipeline.py          # run_analysis_pipeline (전체 파이프라인 오케스트레이션)

tests/
├── conftest.py              # 환경변수 주입, TestClient fixture
├── test_config.py
├── test_github_diff.py
├── test_models.py
├── test_notifier_telegram.py
├── test_pipeline.py
├── test_scorer.py
├── test_static_analyzer.py
├── test_webhook_router.py
└── test_webhook_validator.py

docs/
└── superpowers/
    ├── specs/2026-04-05-scamanager-design.md    # 전체 시스템 설계 문서
    └── plans/2026-04-05-phase1-mvp.md           # Phase 1 구현 계획
```

## 핵심 데이터 흐름

```
GitHub Push/PR
  → POST /webhooks/github (HMAC 서명 검증)
  → BackgroundTasks 비동기 등록
  → run_analysis_pipeline()
      → get_pr_files / get_push_files (변경 파일 목록)
      → analyze_file() 각 파일 (pylint + flake8 + bandit)
      → calculate_score() (코드품질30 + 보안20 + 테스트10 등)
      → DB 저장 (Analysis 레코드)
      → send_analysis_result() (Telegram 알림)
```

## 점수 체계

| 항목 | 배점 | 도구 |
|------|------|------|
| 커밋 메시지 품질 | 20점 | 컨벤션 검사 |
| 코드 품질 | 30점 | pylint + flake8 |
| 보안 | 20점 | bandit |
| 구현 방향성 | 20점 | Claude AI (Phase 2) |
| 테스트 | 10점 | 테스트 파일 존재 여부 |

등급: A(90+), B(75+), C(60+), D(45+), F(44-)

## 알려진 주의사항 (Gotchas)

- **테스트 환경 변수**: `tests/conftest.py`가 `os.environ.setdefault`로 5개 환경변수를 주입함. src 모듈은 import 시점에 `Settings()`를 인스턴스화하므로 conftest가 반드시 먼저 실행되어야 함
- **psycopg2 버전**: Python 3.13에서는 `psycopg2-binary==2.9.11` 이상 필요 (2.9.9는 빌드 실패)
- **멱등성**: `run_analysis_pipeline`은 commit SHA로 중복 체크 — 같은 SHA는 재분석 건너뜀
- **비동기 테스트**: `pytest.ini`의 `asyncio_mode = auto` 필수 (없으면 async 테스트 실패)
- **Alembic**: `alembic/env.py`가 `settings.database_url`을 사용함 — DB 마이그레이션 시 환경변수 필요
- **Webhook 서명**: `X-Hub-Signature-256` 헤더 없으면 403 반환 — 로컬 테스트 시 서명 생성 필요

## Railway 배포

```bash
# Procfile (이미 설정됨)
web: alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port $PORT
```

Railway 대시보드에서 설정할 환경변수: `DATABASE_URL`, `GITHUB_WEBHOOK_SECRET`, `GITHUB_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

헬스체크 엔드포인트: `GET /health`

## Agent 작업 규칙

모든 AI 에이전트(Claude Code 및 서브에이전트)는 SCAManager 작업 시 아래 규칙을 **반드시** 따른다.
`.claude/` 디렉토리에 정의된 스킬과 에이전트는 선택이 아닌 의무적 도구다.

### 필수 원칙

- **TDD 우선**: 구현 코드 작성 전 반드시 `test-writer` 에이전트로 테스트를 먼저 작성한다.
- **Hook 신뢰**: `src/` 파일 편집 후 PostToolUse Hook이 자동 실행하는 pytest 결과를 확인한다. 실패 시 다음 단계로 진행하지 않는다.
- **Phase 완료 조건**: 테스트 전체 통과 + `/lint` 통과 + (파이프라인 변경 시 `pipeline-reviewer` 승인) 세 조건이 모두 충족될 때만 Phase 완료를 선언한다.

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
| Phase 2 | Claude AI 리뷰 + 커밋 메시지 점수 + GitHub PR Comment | 예정 |
| Phase 3 | PR Gate Engine (자동/반자동) + Config Manager | 예정 |
| Phase 4 | Dashboard API + Web UI (Jinja2 + Chart.js) | 예정 |
| Phase 5 | n8n 연동 + 외부 REST API + 통계 고도화 | 예정 |
