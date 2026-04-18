# SCAManager

> **문서 작성 원칙**: 이 프로젝트의 모든 문서는 Claude가 가장 읽기 쉽고 이해하기 편한 구조로 작성한다.
> 새 문서를 작성하거나 기존 문서를 수정할 때 이 원칙을 반드시 따른다.

GitHub Push/PR 이벤트 시 정적 분석 + AI 코드 리뷰를 자동 수행하고, 점수와 개선사항을 Telegram·GitHub PR Comment·Discord·Slack·Email·n8n으로 전달하며, 점수 기반 PR 자동/반자동 Gate(Approve + 자동 Merge 포함)와 웹 대시보드를 제공하는 서비스. `git push` 시 Claude Code CLI 기반 자동 코드리뷰(pre-push hook)도 지원한다.

## 핵심 명령

```bash
cp .env.example .env   # 최초 설정
make install           # 의존성 설치 (requirements-dev.txt)
make run               # 개발 서버 (port 8000, DB 마이그레이션 자동)
```

| 명령 | 동작 |
|------|------|
| `make install` | 의존성 설치 |
| `make test` | 전체 테스트 (빠른 출력) |
| `make test-v` | 전체 테스트 (상세 출력) |
| `make test-cov` | 테스트 + 커버리지 |
| `make test-file f=tests/test_pipeline.py` | 특정 파일 테스트 |
| `make lint` | pylint + flake8 + bandit 검사 |
| `make review` | 로컬 코드리뷰 CLI 실행 (HEAD~1 기준) |
| `make run` | 개발 서버 실행 (port 8000) |
| `make migrate` | DB 마이그레이션 실행 |
| `make revision m="설명"` | 새 마이그레이션 파일 생성 |
| `make install-playwright` | Playwright + Chromium 설치 |
| `make test-e2e` | E2E 테스트 실행 (headless) |
| `make test-e2e-headed` | E2E 테스트 실행 (브라우저 표시) |

## 아키텍처

```
src/
├── main.py                     # FastAPI 앱, lifespan(DB 마이그레이션), 전체 라우터 등록
├── config.py                   # pydantic-settings 환경변수 관리, postgres:// URL 자동 변환
├── constants.py                # GRADE_EMOJI, GRADE_COLOR_* 상수 단일 출처
├── crypto.py                   # encrypt_token()/decrypt_token() — TOKEN_ENCRYPTION_KEY
├── database.py                 # SQLAlchemy engine, Base, FailoverSessionFactory
├── auth/
│   ├── session.py              # get_current_user() + require_login Depends
│   └── github.py               # /login, /auth/github, /auth/callback, /auth/logout
├── models/
│   ├── repository.py           # Repository ORM (user_id FK nullable)
│   ├── analysis.py             # Analysis ORM (commit_message 포함)
│   ├── repo_config.py          # RepoConfig ORM (pr_review_comment, approve_mode, approve/reject_threshold, auto_merge, merge_threshold, hook_token)
│   ├── gate_decision.py        # GateDecision ORM
│   └── user.py                 # User ORM (github_id, github_login, github_access_token, email, display_name)
├── webhook/
│   ├── validator.py            # HMAC-SHA256 서명 검증
│   └── router.py               # POST /webhooks/github, POST /api/webhook/telegram
├── github_client/
│   ├── models.py               # ChangedFile dataclass 단일 출처
│   ├── helpers.py              # github_api_headers() 공용 헬퍼
│   ├── diff.py                 # get_pr_files, get_push_files
│   └── repos.py                # list_user_repos(), create_webhook(), delete_webhook(), commit_scamanager_files()
├── analyzer/
│   ├── static.py               # analyze_file — pylint/flake8/bandit (.py만, 테스트 bandit 제외)
│   └── ai_review.py            # review_code() — Claude API, AiReviewResult
├── scorer/
│   └── calculator.py           # calculate_score(ai_review), ScoreResult, _grade
├── config_manager/
│   └── manager.py              # get_repo_config(), upsert_repo_config(), RepoConfigData
├── gate/
│   ├── engine.py               # run_gate_check() — 3-옵션 독립 처리
│   ├── github_review.py        # post_github_review(), merge_pr()
│   └── telegram_gate.py        # send_gate_request() — 인라인 키보드 메시지
├── notifier/
│   ├── telegram.py             # send_analysis_result(), telegram_post_message() 공용 헬퍼
│   ├── github_comment.py       # post_pr_comment_from_result() — result dict 기반
│   ├── discord.py, slack.py, webhook.py, email.py, n8n.py
├── api/
│   ├── auth.py                 # require_api_key Depends (X-API-Key 헤더)
│   ├── deps.py                 # get_repo_or_404(repo_name, db) 공용 헬퍼
│   ├── repos.py                # GET/PUT /api/repos, /api/repos/{repo}/analyses, /config
│   ├── stats.py                # GET /api/analyses/{id}, /api/repos/{repo}/stats
│   └── hook.py                 # GET /api/hook/verify, POST /api/hook/result (hook_token 인증)
├── ui/
│   └── router.py               # Jinja2 Web UI — require_login + user_id 필터
├── templates/                  # add_repo, base, login, overview, repo_detail, analysis_detail, settings
├── cli/
│   ├── __main__.py             # python -m src.cli review
│   ├── git_diff.py             # 로컬 git diff 수집
│   └── formatter.py            # 터미널 출력 포맷 (ANSI 색상)
└── worker/
    └── pipeline.py             # run_analysis_pipeline, _build_result_dict
```

### 핵심 데이터 흐름

```
GitHub Push/PR
  → POST /webhooks/github (HMAC 서명 검증)
  → PR action 필터링 (opened/synchronize/reopened만 처리)
  → BackgroundTasks 비동기 등록
  → run_analysis_pipeline()
      → Repository DB 등록 (API 호출 전, 실패해도 목록 노출 보장)
      → _extract_commit_message() — PR: title+body, Push: head_commit 우선
      → get_pr_files / get_push_files (모든 변경 파일 수집)
      → asyncio.gather() 병렬 실행:
          ├─ analyze_file() × N  (.py만 정적 분석, 테스트 파일은 bandit 제외)
          └─ review_code()       (Claude AI — 모든 파일의 diff + 파일명 분석)
      → calculate_score(ai_review)
          (코드품질25 + 보안20 + 커밋15 + AI방향성25 + 테스트15)
      → DB 저장 (Analysis 레코드)
      → run_gate_check() [PR 이벤트만] — 3-옵션 완전 독립 처리
          [pr_review_comment=on] → post_pr_comment_from_result() — PR에 AI 코드리뷰 댓글 발송
          [approve_mode=auto]    → score ≥ approve_threshold → GitHub APPROVE
                                   score < reject_threshold → GitHub REQUEST_CHANGES
          [approve_mode=semi]    → Telegram 인라인 키보드 전송 → POST /api/webhook/telegram 콜백 수신
          [auto_merge=on, score ≥ merge_threshold] → squash merge (approve_mode 무관)
      → _build_notify_tasks() — RepoConfig 기반 채널 디스패처
      → asyncio.gather(return_exceptions=True):
          ├─ send_analysis_result()        (Telegram — notify_chat_id 또는 global fallback)
          ├─ send_discord_notification()   (discord_webhook_url 설정 시)
          ├─ send_slack_notification()     (slack_webhook_url 설정 시)
          ├─ send_webhook_notification()   (custom_webhook_url 설정 시)
          ├─ send_email_notification()     (email_recipients + SMTP 설정 시)
          └─ notify_n8n()                  (n8n_webhook_url 설정 시)

Telegram 반자동 콜백:
  → POST /api/webhook/telegram
  → gate:{decision}:{id}:{token} 파싱 (HMAC 인증 포함)
  → post_github_review() + GateDecision DB 저장
  → auto_merge=on, score ≥ merge_threshold → squash merge (approve_mode 무관하게 독립 동작)

대시보드:
  → GET /                              (리포 현황 Web UI)
  → GET /repos/{repo}                  (점수 차트 + 이력 Web UI)
  → GET /repos/{repo}/analyses/{id}    (분석 상세 — AI 리뷰·피드백·이슈)
  → GET /api/repos                     (REST API)
  → GET /api/repos/{repo}/stats        (통계 API)

CLI Hook (로컬 pre-push 자동 코드리뷰):
  Repo 등록 시 (POST /repos/add):
    → hook_token = secrets.token_hex(32) 생성 → RepoConfig 저장
    → GitHub Contents API로 .scamanager/config.json + install-hook.sh 커밋
    → 개발자: git pull && bash .scamanager/install-hook.sh (1회)
  git push 시 (.git/hooks/pre-push 자동 실행):
    → GET /api/hook/verify?repo=...&token=... (미등록 시 조용히 skip)
    → git diff로 push 대상 diff 수집
    → claude -p "[프롬프트+diff]" 실행 (Claude Code CLI — ANTHROPIC_API_KEY 불필요)
    → 터미널에 결과 출력
    → POST /api/hook/result → Analysis DB 저장 + 대시보드 반영
    → exit 0 (push 항상 진행)
```

### 점수 체계

| 항목 | 배점 | 도구 | 감점 규칙 |
|------|------|------|----------|
| 코드 품질 | 25점 | pylint + flake8 | error -3, warning -1 (pylint 15개·flake8 10개 cap) |
| 보안 | 20점 | bandit | HIGH -7, LOW/MED -2 |
| 커밋 메시지 품질 | 15점 | Claude AI (0-20 → 0-15 스케일링) | — |
| 구현 방향성 | 25점 | Claude AI (0-20 → 0-25 스케일링) | — |
| 테스트 | 15점 | Claude AI (0-10 → 0-15 스케일링, 비-코드 파일 면제) | — |

등급: A(90+), B(75+), C(60+), D(45+), F(44-)

> `ANTHROPIC_API_KEY` 미설정 시 AI 항목은 중립적 기본값(커밋13 + 방향21 + 테스트10 = 44/55)으로 fallback, AI 없이도 최대 89점(B등급) 가능

## 환경변수 (필수만)

| 변수 | 설명 |
|------|------|
| `DATABASE_URL` | PostgreSQL 연결 URL (`postgres://`는 `postgresql://`로 자동 변환) |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API 토큰 |
| `TELEGRAM_CHAT_ID` | Telegram 알림 수신 Chat ID |
| `GITHUB_CLIENT_ID` | GitHub OAuth 앱 클라이언트 ID |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth 앱 클라이언트 시크릿 |
| `SESSION_SECRET` | 세션 쿠키 서명 키 (32자 이상 랜덤 문자열 필수) |
| `APP_BASE_URL` | Railway 배포 시 HTTPS URL 강제 (OAuth + Webhook 양쪽 적용) — Railway 필수 |
| `ANTHROPIC_API_KEY` | Claude AI 리뷰 (없으면 기본값 fallback) |

전체 환경변수 목록: `docs/reference/env-vars.md`

## Railway 배포

```bash
# 시작 명령 (railway.toml에 설정됨 — --proxy-headers 포함)
uvicorn src.main:app --host 0.0.0.0 --port $PORT --proxy-headers
# DB 마이그레이션은 앱 lifespan에서 자동 실행
```

Railway 대시보드 설정:
- **PostgreSQL 플러그인** 추가 (`DATABASE_URL` 자동 생성)
- **Variables** 탭에서 나머지 환경변수 설정 (`${{Postgres.DATABASE_URL}}`)
- `APP_BASE_URL` 반드시 설정 — OAuth redirect_uri HTTPS 보장

헬스체크: `GET /health` → `{"status":"ok","active_db":"primary"|"fallback"}` (timeout: 60초)

### NIXPACKS 빌드 설정 우선순위

| 우선순위 | 설정 위치 | 적용 범위 |
|---------|----------|---------|
| 1 | `railway.toml`의 `buildCommand` | 빌드 명령 최상위 오버라이드 |
| 2 | `nixpacks.toml`의 `[phases.build]` | NIXPACKS 빌드 단계 설정 |
| 3 | `nixpacks.toml`의 `providers` | NIXPACKS 언어 감지 오버라이드 |
| 4 | NIXPACKS 자동 감지 | `requirements.txt`, `package.json` 등 파일 기반 |

현재: `railway.toml`에 `buildCommand = "echo 'Python project — no build step'"` 설정됨.

```
requirements.txt      ← Railway(프로덕션) 전용 — pytest/playwright 제외
requirements-dev.txt  ← 로컬 개발 환경 — pytest, playwright 포함 (-r requirements.txt 포함)
```

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
4. 서명 검증 로직 변경 시 401/202 응답 코드 직접 확인

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

## 주의사항 (카테고리별)

### 테스트

- **테스트 환경 변수**: `tests/conftest.py`가 `os.environ.setdefault`로 환경변수를 주입함. src 모듈은 import 시점에 `Settings()`를 인스턴스화하므로 conftest가 반드시 먼저 실행되어야 함.
- **asyncio_mode = auto**: `pytest.ini`의 `asyncio_mode = auto` 필수 — 없으면 async 테스트 실패.
- **E2E 격리**: `e2e/`를 최상위 별도 디렉토리로 분리 (`tests/` 아래 금지) — `tests/e2e/`가 있으면 `asyncio_mode=auto`와 `sys.modules` 삭제가 충돌해 단위 테스트 98개 실패. E2E 서버는 `uvicorn.Server.serve()`를 `asyncio.new_event_loop()` + `loop.run_until_complete()`로 실행.
- **require_login 우회**: `tests/test_ui_router.py`는 `app.dependency_overrides[require_login] = lambda: _test_user`로 의존성 override. 신규 UI 라우트 테스트 작성 시 동일 패턴 사용.
- **Mock side_effect 재귀**: `mock.add.side_effect = fn` 설정 후 fn 내에서 `original_add(obj)` 호출 시 재귀 발생. side_effect 함수에서는 원본 mock을 호출하지 말 것 — 캡처만 하고 return None.
- **psycopg2 버전**: Python 3.13에서는 `psycopg2-binary==2.9.11` 이상 필요.

### DB / 마이그레이션

- **Alembic batch_alter_table 금지**: SQLite 전용 패턴. PostgreSQL에서는 `op.create_unique_constraint('이름', '테이블', ['컬럼'])` 직접 사용. 잘못 사용 시 lifespan 마이그레이션 실패 → Railway 헬스체크 실패.
- **DB 세션 expunge**: `get_current_user()`는 `db.expunge(user)` 후 세션 반환 — 세션 종료 후에도 컬럼 속성 안전하게 접근 가능. 관계 lazy-load 사용 금지.
- **N+1 쿼리 방지**: overview에서 분석 수·최신 분석·평균 점수를 배치 쿼리(subquery + GROUP BY)로 조회.
- **SQLite hostaddr 제외**: `_ipv4_connect_args`는 hostname이 None(SQLite URL)이면 빈 dict 반환 — 그렇지 않으면 `sqlite3.connect(hostaddr=...)` TypeError 발생.
- **FailoverSessionFactory**: `DATABASE_URL_FALLBACK` 설정 시 Primary `OperationalError` → Fallback DB 자동 전환. `_probe_primary_loop` daemon 스레드가 복구 확인 후 자동 복귀. 미설정 시 단일 엔진 모드(probe 스레드 없음). 소비자 코드(`SessionLocal()`)는 변경 없이 그대로 사용. `engine = SessionLocal._primary_engine`으로 alembic/env.py 호환성 유지.
- **Supabase Fallback SSL 중복 방지**: `_build_connect_args`가 `parse_qs`로 URL query를 검사해 `connect_args`에 `sslmode` 중복 설정 방지. URL query `sslmode` 우선.
- **ThreadPoolExecutor with 블록 금지**: `with` 문은 `shutdown(wait=True)` 호출 → DNS hang 시 무기한 블록. `try/finally` + `executor.shutdown(wait=False)` 패턴 사용 (database.py 참조).

### 파이프라인 / 비즈니스 로직

- **멱등성**: `run_analysis_pipeline`은 commit SHA로 중복 체크 — 같은 SHA는 재분석 건너뜀.
- **AI 리뷰 JSON 파싱**: Claude가 JSON 앞에 설명 텍스트를 붙이는 경우 `re.search`로 코드 블록 내 JSON만 추출.
- **AI 점수 스케일링**: Claude는 commit 0-20, direction 0-20, test 0-10으로 반환 → calculator가 commit 0-15, direction 0-25, test 0-15로 스케일링. `round()` 사용으로 banker's rounding 적용.
- **PR action 필터링**: `pull_request` 이벤트 중 `opened`/`synchronize`/`reopened`만 처리, `closed`/`labeled` 등은 무시.
- **커밋 메시지 추출**: `_extract_commit_message()`는 PR 이벤트 시 `title + "\n\n" + body`, Push 이벤트 시 `head_commit["message"]` 우선 사용.
- **분석 source 필드**: `pipeline.py`가 result JSON에 `"source": "pr"|"push"` 저장. 기존 레코드 대응으로 `result.get("source") or ("pr" if pr_number else "push")` fallback 파생.
- **CLI Hook 인증/점수**: `GET /api/hook/verify`, `POST /api/hook/result`는 `hook_token` 파라미터로 인증(X-API-Key 불필요). pre-push 훅은 정적 분석 없이 AI 리뷰만 실행 → `calculate_score([], ai_review)` 호출 (code_quality=25, security=20 만점 적용).
- **commit_scamanager_files**: GitHub Contents API `PUT /repos/{owner}/{repo}/contents/{path}` 사용. 파일 이미 있으면 GET으로 sha 조회 후 body에 포함해야 200 성공 (sha 누락 시 422 에러).
- **비-Python 파일 AI 리뷰**: `.md`, `.cfg`, `.yml` 등도 AI 리뷰 대상 — 정적 분석은 `.py`만 실행, 비-코드 파일만 변경 시 테스트 점수 면제(test_score=10 → 15/15).

### API / 알림 채널

- **알림 독립성**: `_build_notify_tasks()` 디스패처, `asyncio.gather(return_exceptions=True)`로 실행 — 한 채널 실패해도 나머지 채널은 정상 전송. `repo_config` 로드 실패 시에도 Telegram은 global fallback으로 항상 발송.
- **알림 채널 추가 체크리스트**: `RepoConfig` ORM → `RepoConfigData` dataclass → `RepoConfigUpdate` API body → UI 폼 4곳 반드시 동기화. 누락 시 REST API 업데이트 시 해당 필드가 NULL로 덮어써지는 버그 발생.
- **GRADE 상수 단일 출처**: `src/constants.py`에 `GRADE_EMOJI`, `GRADE_COLOR_DISCORD`, `GRADE_COLOR_HTML`, `GRADE_COLOR_ANSI` 정의. 각 모듈에 로컬 정의 금지.
- **ChangedFile / github_api_headers 단일 출처**: `src/github_client/models.py`가 ChangedFile 정의 출처. `src/github_client/helpers.py`의 `github_api_headers(token)` 사용 — 새 GitHub API 호출 시 직접 dict를 만들지 말 것.
- **keyword-only 강제 (`*`)**: 모든 `send_*` notifier 함수와 `run_gate_check()` 등은 `def fn(*, arg1, arg2)` 형태. 테스트에서 positional 호출 시 TypeError — 반드시 키워드 인자로 호출.
- **get_repo_or_404**: `src/api/deps.py`의 `get_repo_or_404(repo_name, db)` 사용. 신규 API 엔드포인트에서 Repository 조회 시 동일 패턴 사용.
- **_build_result_dict**: `src/worker/pipeline.py` 모듈 레벨 함수. pipeline과 hook.py 두 곳에서 Analysis.result dict를 생성할 때 사용. `score`·`grade` 필드 포함 — gate engine이 이를 기반으로 결정.
- **PR Gate 3-옵션 독립**: `pr_review_comment`·`approve_mode`·`auto_merge+merge_threshold` 완전 독립. `post_pr_comment_from_result(result: dict, ...)` 사용 — `AiReviewResult` 객체 불필요. `run_gate_check` 시그니처: `(repo_name, pr_number, analysis_id, result, github_token, db)`.
- **RepoConfig 필드명**: `approve_mode`(구 `gate_mode`), `approve_threshold`(구 `auto_approve_threshold`), `reject_threshold`(구 `auto_reject_threshold`) — 구 필드명 사용 시 AttributeError.
- **auto_merge GitHub 권한**: `merge_pr()`은 `repo` 스코프 또는 Fine-grained `pull_requests: write` 권한 필요 — 권한 부족 시 False 반환(파이프라인 미중단). Branch Protection Rules가 있으면 APPROVE 후에도 Merge 실패 가능.
- **Webhook 서명**: `X-Hub-Signature-256` 헤더 없거나 서명 불일치 시 401 반환 — 로컬 테스트 시 서명 생성 필요. 빈 시크릿(`GITHUB_WEBHOOK_SECRET` 미설정)이면 즉시 401.
- **telegram_post_message**: `src/notifier/telegram.py`의 공용 헬퍼. `src/gate/telegram_gate.py`도 이 헬퍼 사용 — `httpx` 직접 import 금지.

### 보안

- **hook_token 비교**: `!=` 연산자는 타이밍 공격에 취약. `hmac.compare_digest(config.hook_token or "", token)` 사용 필수.
- **Telegram 게이트 콜백 HMAC 인증**: 콜백 데이터 형식 `gate:{decision}:{id}:{token}` — token은 `hmac(bot_token, str(analysis_id), sha256)[:16]`. `telegram_gate.py`의 `_gate_callback_token()` 참조. 테스트 시 HMAC 토큰을 직접 계산해 픽스처에 포함해야 함.
- **GitHub Access Token 암호화**: `src/crypto.py`의 `encrypt_token()`/`decrypt_token()` — `TOKEN_ENCRYPTION_KEY` 미설정 시 평문 저장. `User.plaintext_token` property가 DB 읽기 시 자동 복호화. `user.github_access_token` 직접 사용 금지 — `user.plaintext_token` 사용.
- **SESSION_SECRET 강도**: `warn_weak_session_secret` validator가 32자 미만 또는 기본값이면 WARNING 출력. 프로덕션에서는 32자 이상 랜덤 문자열 필수.

### UI / 템플릿

- **analysis_detail 템플릿 context**: `current_user`를 반드시 포함해야 함 — 누락 시 nav 사용자명·로그아웃 버튼 미표시. `analysis.result or {}` 패턴은 None → `{}` 변환으로 `{% if r %}` falsy 평가 → 모든 AI 섹션 숨김 버그 — `{% else %}` 분기로 fallback 처리 필수.
- **analysis_detail trend_data**: `trend_data`·`prev_id`·`next_id`를 template context에 추가 전달. `trend_data`는 같은 리포 최근 30건 `{id, score, label}` 리스트. `trend_data|length > 1`일 때만 차트 렌더링. `analysis_detail.html`은 Chart.js CDN을 직접 로드.
- **repo_detail 차트 동기화**: `buildChart(data)` 함수는 `data` 인자가 있으면 `_chartData`에 캐시, 없으면 캐시된 데이터 재사용. `applyFilters()` 호출마다 차트를 필터 결과와 동기화. `themechange` 이벤트는 `buildChart()` (인자 없음)으로 색상만 재빌드.
- **Telegram HTML 파싱**: `parse_mode: "HTML"` 사용 — 모든 동적 콘텐츠에 `html.escape()` 적용 필수. `_build_message()`가 4096자 초과 시 자동 절단.
- **기존 Webhook 등록 리포**: `user_id = NULL` 리포는 모든 로그인 사용자에게 표시됨. `/repos/add`로 동일 리포 재등록 시 `user_id=NULL`이면 현재 사용자 소유 이전, 이미 소유자 있으면 에러.
- **리포 추가 Webhook URL**: `_webhook_base_url(request)` 헬퍼가 `APP_BASE_URL` 설정 시 HTTPS URL 강제. Railway 배포 시 반드시 `APP_BASE_URL` 설정 — 미설정 시 `http://`로 등록되어 Webhook 전달 실패.
- **settings.html 구조 규약**: 프리셋 3버튼 카드(🌱 최소·⚙️ 표준·🛡️ 엄격) + 4카드 그리드(① PR 동작 / ② Push 동작 / ③ 알림 채널 / ④ 시스템). Progressive Disclosure는 `setApproveMode()`, `toggleMergeThreshold()`, `applyPreset()`, `_setPair()`, `_showPresetToast()` JS 헬퍼로 구현. 알림 채널 URL은 프리셋이 건드리지 않음. 백엔드 필드명(pr_review_comment, approve_mode 등) 불변 원칙 — 4-way 동기화 체크리스트(ORM→dataclass→API body→폼) 적용 대상.

### 배포

- **NIXPACKS npm 오탐**: NIXPACKS가 Python 프로젝트를 Node.js로 오인해 `npm run build` 자동 추가. `nixpacks.toml`의 `providers = ["python"]`만으로는 불충분 — `railway.toml`에 `buildCommand = "echo 'no build'"` 최상위 오버라이드 필수.
- **Railway 빌드 검증 필수**: `git push` 성공 ≠ Railway 빌드 성공. `railway.toml`, `nixpacks.toml`, `requirements.txt` 변경 후 Railway 대시보드 빌드 로그 직접 확인 후 완료 선언.
- **requirements.txt 분리**: `requirements.txt`(프로덕션 — Railway 자동 감지)와 `requirements-dev.txt`(개발 — `-r requirements.txt` 포함 + pytest/playwright) 분리. `pytest`, `playwright`는 `requirements-dev.txt`에만 유지.
- **SMTP_PORT 빈 문자열**: Railway 환경에서 `SMTP_PORT=""`로 설정 시 pydantic ValidationError 크래시. Railway Variables에서 SMTP_PORT 값을 삭제하거나 숫자로 설정.
- **postgres:// URL**: Railway PostgreSQL이 `postgres://`로 제공하는 경우 `config.py`에서 `postgresql://`로 자동 변환.
- **APP_BASE_URL**: Railway 리버스 프록시 환경. 설정 시 **OAuth redirect_uri**와 **GitHub Webhook 등록 URL** 양쪽에 HTTPS URL 강제 적용. Railway 배포 필수 설정.

## 현재 상태

단위 테스트 434개 | E2E 26개 | pylint 9.66 | 커버리지 94%
