# SCAManager

GitHub Repository에 Push/PR 이벤트 발생 시 정적 분석 + AI 코드 리뷰를 자동 수행하고, 점수와 개선사항을 Telegram·GitHub PR Comment·Discord·Slack·Email·n8n으로 전달하며, 점수 기반 PR 자동/반자동 Gate(Approve + 자동 Merge 포함)와 웹 대시보드를 제공하는 서비스. `git push` 시 Claude Code CLI 기반 자동 코드리뷰(pre-push hook)도 지원한다.

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
| `make review` | 로컬 코드리뷰 CLI 실행 (HEAD~1 기준) |
| `make run` | 개발 서버 실행 (port 8000) |
| `make migrate` | DB 마이그레이션 실행 |
| `make revision m="설명"` | 새 마이그레이션 파일 생성 |
| `make install-playwright` | Playwright + Chromium 설치 |
| `make test-e2e` | E2E 테스트 실행 (headless) |
| `make test-e2e-headed` | E2E 테스트 실행 (브라우저 표시) |

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
> 단위 테스트 전체(296개)는 API 키 없이 실행됩니다.

## DB 마이그레이션

`make revision m="설명"` / `make migrate` 사용 (위 Makefile 표 참조)

### 현재 마이그레이션 파일

| 파일 | 내용 |
|------|------|
| `3b8216565fed_create_repositories_and_analyses_tables.py` | 초기 테이블 생성 |
| `0002_phase3_add_repo_config_gate_decision.py` | RepoConfig + GateDecision 추가 |
| `0003_drop_analysis_rules.py` | analysis_rules 컬럼 제거 |
| `0004_add_auto_merge.py` | RepoConfig에 auto_merge Boolean 컬럼 추가 |
| `0005_add_users_and_user_id.py` | users 테이블 생성 + repositories.user_id FK 추가 |
| `0006_phase8b_github_oauth.py` | github_id 컬럼 rename + github_login/access_token 추가 + webhook_secret/id 추가 |
| `0007_add_notification_channels.py` | RepoConfig에 discord/slack/webhook/email 컬럼 추가 |
| `0008_add_commit_message.py` | Analysis에 commit_message 컬럼 추가 |
| `0009_add_hook_token.py` | RepoConfig에 hook_token 컬럼 추가 (CLI Hook 인증) |

## 환경 변수

| 변수 | 설명 | 예시 | 필수 |
|------|------|------|------|
| `DATABASE_URL` | PostgreSQL 연결 URL | `postgresql://user:pass@host/db` | ✅ |
| `GITHUB_WEBHOOK_SECRET` | GitHub Webhook HMAC 서명 시크릿 | `your-secret-here` | ❌ (Phase 8B 이후 선택적, 리포 자동 등록 시 사용) |
| `GITHUB_TOKEN` | GitHub API Personal Access Token | `ghp_xxxx` | ❌ (레거시 리포 fallback, Phase 8B 이후 선택적) |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API 토큰 | `123456:ABC-xxx` | ✅ |
| `TELEGRAM_CHAT_ID` | Telegram 알림 수신 Chat ID | `-100xxxxxxxxx` | ✅ |
| `ANTHROPIC_API_KEY` | Claude AI 리뷰 API 키 | `sk-ant-xxxx` | ❌ (없으면 AI 리뷰 건너뜀) |
| `API_KEY` | Dashboard API 인증 키 | `any-secret-string` | ❌ (없으면 인증 건너뜀) |
| `GITHUB_CLIENT_ID` | GitHub OAuth 앱 클라이언트 ID | `Ov23li...` | ✅ |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth 앱 클라이언트 시크릿 | `github_...` | ✅ |
| `SESSION_SECRET` | 세션 쿠키 서명 키 (32자 이상 랜덤 문자열 권장) | `random-secret-key` | ✅ |
| `APP_BASE_URL` | Railway 등 리버스 프록시에서 HTTPS redirect_uri 강제 지정 | `https://your-app.railway.app` | ❌ (Railway 배포 시 권장) |
| `SMTP_HOST` | SMTP 메일 서버 호스트 | `smtp.gmail.com` | ❌ (Email 알림 시 필요) |
| `SMTP_PORT` | SMTP 포트 (기본 587) | `587` | ❌ |
| `SMTP_USER` | SMTP 인증 사용자 | `user@gmail.com` | ❌ |
| `SMTP_PASS` | SMTP 인증 비밀번호 | `app-password` | ❌ |

**주의:** `.env` 파일은 절대 git commit 하지 말 것 (`.gitignore`에 포함됨)

## 프로젝트 구조

```
src/
├── main.py                     # FastAPI 앱, lifespan(DB 마이그레이션), 전체 라우터 등록
├── config.py                   # pydantic-settings 환경변수 관리, postgres:// URL 자동 변환
├── database.py                 # SQLAlchemy engine, Base, SessionLocal (SQLite는 hostaddr 제외)
├── auth/
│   ├── __init__.py
│   ├── session.py              # get_current_user() + require_login Depends
│   └── github.py               # /login, /auth/github, /auth/callback, /auth/logout (authlib GitHub OAuth2)
├── models/
│   ├── repository.py           # Repository ORM (user_id FK nullable)
│   ├── analysis.py             # Analysis ORM (commit_message 포함)
│   ├── repo_config.py          # RepoConfig ORM (gate_mode, threshold, 알림 채널 URL, auto_merge, hook_token)
│   ├── gate_decision.py        # GateDecision ORM (analysis_id, decision, mode)
│   └── user.py                 # User ORM (github_id, github_login, github_access_token, email, display_name)
├── webhook/
│   ├── validator.py            # HMAC-SHA256 서명 검증
│   └── router.py               # POST /webhooks/github, POST /api/webhook/telegram
├── github_client/
│   ├── models.py               # ChangedFile dataclass 단일 출처 정의
│   ├── helpers.py              # github_api_headers() 공용 헬퍼
│   ├── diff.py                 # get_pr_files, get_push_files (models.py에서 ChangedFile import)
│   └── repos.py                # list_user_repos(), create_webhook(), delete_webhook(), commit_scamanager_files()
├── analyzer/
│   ├── static.py               # analyze_file — pylint/flake8/bandit (.py만, 테스트 bandit 제외)
│   └── ai_review.py            # review_code() — Claude API, AiReviewResult (파일명+diff 분석)
├── scorer/
│   └── calculator.py           # calculate_score(ai_review), ScoreResult, _grade
├── config_manager/
│   └── manager.py              # get_repo_config(), upsert_repo_config(), RepoConfigData
├── gate/
│   ├── engine.py               # run_gate_check() — auto/semi-auto 분기, auto_merge 처리
│   ├── github_review.py        # post_github_review(), merge_pr() — GitHub Review/Merge API (github_api_headers 사용)
│   └── telegram_gate.py        # send_gate_request() — 인라인 키보드 메시지
├── notifier/
│   ├── telegram.py             # send_analysis_result() — HTML 파싱 모드
│   ├── github_comment.py       # post_pr_comment()
│   ├── discord.py              # send_discord_notification() — Discord Embed
│   ├── slack.py                # send_slack_notification() — Slack Attachment
│   ├── webhook.py              # send_webhook_notification() — 범용 JSON POST
│   ├── email.py                # send_email_notification() — SMTP HTML 이메일
│   └── n8n.py                  # notify_n8n() — n8n Webhook POST
├── api/
│   ├── auth.py                 # require_api_key Depends (X-API-Key 헤더)
│   ├── repos.py                # GET/PUT /api/repos, /api/repos/{repo}/analyses, /config
│   ├── stats.py                # GET /api/analyses/{id}, /api/repos/{repo}/stats
│   └── hook.py                 # GET /api/hook/verify, POST /api/hook/result (hook_token 인증, X-API-Key 불필요)
├── ui/
│   └── router.py               # Jinja2 Web UI — /, /repos/{repo}, /repos/{repo}/settings, POST /repos/{repo}/reinstall-hook, POST /repos/{repo}/reinstall-webhook (require_login + user_id 필터, analyses_data에 commit_message + source 포함, limit 100)
├── templates/
│   ├── add_repo.html           # 리포 추가 페이지 (GitHub 드롭다운 + Webhook 자동 생성)
│   ├── base.html               # 공통 레이아웃 (nav 사용자 정보 + 로그아웃 버튼)
│   ├── login.html              # 로그인 페이지 ("GitHub로 로그인" 버튼)
│   ├── overview.html           # 리포 현황 목록
│   ├── repo_detail.html        # 점수 차트(Chart.js) + 분석 이력 (검색·등급/소스 필터·정렬·페이지네이션·점수 슬라이더, 소스 컬럼)
│   ├── analysis_detail.html    # 분석 상세 — AI 리뷰·피드백·정적 분석 이슈 + 날짜·시간·소스(CLI/PR/Push)·SHA title
│   └── settings.html           # Gate 모드·임계값·알림 채널 설정 폼 + CLI Hook 재설치 섹션
├── cli/
│   ├── __main__.py             # CLI entry point — python -m src.cli review
│   ├── git_diff.py             # 로컬 git diff 수집 (ChangedFile, get_diff_files)
│   └── formatter.py            # 터미널 출력 포맷 (ANSI 색상, JSON)
└── worker/
    └── pipeline.py             # run_analysis_pipeline — 전체 파이프라인 (result에 source 필드 "push"/"pr" 포함)

e2e/                            # Playwright E2E 테스트 26개 (브라우저 기반 JS 동작 검증)
├── conftest.py                 # uvicorn 스레드 서버 + Playwright browser/page fixture
├── pytest.ini                  # asyncio_mode 없는 별도 설정 (tests/ 와 격리)
├── test_theme.py               # 3-테마 전환 E2E (localStorage, data-theme, dropdown)
├── test_settings.py            # 설정 페이지 E2E (Gate 모드 토글, 슬라이더, 폼 제출)
└── test_navigation.py          # 네비게이션 E2E (로고, 뒤로가기, 설정 버튼)

tests/                          # 296개 단위 테스트 (Phase 1~8B + 점수 개선 + 알림 확장 + 분석 상세 + 커밋 메시지 + CLI + Hook + 보안 강화 + Webhook 재등록 + 분석 상세 표시 개선 + 이력 조회 강화 + nav 로그인/로그아웃 + 코드품질 강화)
├── conftest.py
├── test_config.py, test_models.py, test_repo_config_model.py
├── test_user_model.py          # User ORM + Repository.user_id FK 테스트
├── test_auth_session.py        # get_current_user() + require_login 단위 테스트
├── test_auth_github.py         # GitHub OAuth 라우트 단위 테스트
├── test_github_diff.py, test_github_repos.py, test_webhook_router.py, test_webhook_validator.py
├── test_webhook_telegram.py    # Telegram callback endpoint
├── test_static_analyzer.py, test_ai_review.py
├── test_scorer.py, test_pipeline.py
├── test_notifier_telegram.py, test_github_comment.py, test_n8n_notifier.py
├── test_discord_notifier.py, test_slack_notifier.py
├── test_generic_webhook.py, test_email_notifier.py
├── test_config_manager.py
├── test_gate_engine.py, test_github_review.py, test_telegram_gate.py
├── test_api_auth.py, test_api_repos.py, test_api_stats.py
├── test_ui_router.py
├── test_cli_git_diff.py        # CLI 로컬 git diff 수집 테스트
├── test_cli_formatter.py       # CLI 터미널 출력 포맷 테스트
├── test_cli_main.py            # CLI entry point 오케스트레이션 테스트
└── test_hook_api.py            # Hook verify/result 엔드포인트 테스트

setup.cfg                       # flake8/pylint 프로젝트 설정 (테스트 파일별 규칙 포함)

docs/
├── github-integration-guide.md       # GitHub OAuth 설정 가이드
├── code-quality-report-2026-04-09.md # 코드품질 강화 보고서 (버그·중복·docstring·lint)
└── superpowers/
    ├── specs/
    │   ├── 2026-04-05-scamanager-design.md
    │   ├── 2026-04-07-phase8a-auth-user-design.md
    │   └── 2026-04-07-phase8b-github-oauth-repo-add-design.md
    └── plans/
        ├── 2026-04-05-phase1-mvp.md
        ├── 2026-04-05-phase2-ai-review.md
        ├── 2026-04-05-phase3-gate-engine.md
        ├── 2026-04-05-phase4-dashboard.md
        ├── 2026-04-05-phase5-n8n-stats.md
        ├── 2026-04-07-phase8a-auth-user.md
        └── 2026-04-07-phase8b-github-oauth-repo-add.md

.devcontainer/
└── devcontainer.json               # GitHub Codespaces 개발 컨테이너 설정
```

## 핵심 데이터 흐름

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
      → run_gate_check() [PR 이벤트만]
          [auto]      → GitHub Approve / Request Changes 즉시 실행
                         → auto_merge=True이면 squash merge 자동 실행
          [semi-auto] → Telegram 인라인 키보드 전송 → POST /api/webhook/telegram 콜백 수신
      → _build_notify_tasks() — RepoConfig 기반 채널 디스패처
      → asyncio.gather(return_exceptions=True):
          ├─ send_analysis_result()        (Telegram — notify_chat_id 또는 global fallback)
          ├─ post_pr_comment()             (PR 이벤트 시 GitHub PR Comment)
          ├─ send_discord_notification()   (discord_webhook_url 설정 시)
          ├─ send_slack_notification()     (slack_webhook_url 설정 시)
          ├─ send_webhook_notification()   (custom_webhook_url 설정 시)
          ├─ send_email_notification()     (email_recipients + SMTP 설정 시)
          └─ notify_n8n()                  (n8n_webhook_url 설정 시)

Telegram 반자동 콜백:
  → POST /api/webhook/telegram
  → gate:{decision}:{id}:{token} 파싱 (HMAC 인증 포함)
  → post_github_review() + GateDecision DB 저장
  → approve + auto_merge=True이면 squash merge 자동 실행

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

## 점수 체계

| 항목 | 배점 | 도구 | 감점 규칙 |
|------|------|------|----------|
| 코드 품질 | 25점 | pylint + flake8 | error -3, warning -1 (pylint 15개·flake8 10개 cap) |
| 보안 | 20점 | bandit | HIGH -7, LOW/MED -2 |
| 커밋 메시지 품질 | 15점 | Claude AI (0-20 → 0-15 스케일링) | — |
| 구현 방향성 | 25점 | Claude AI (0-20 → 0-25 스케일링) | — |
| 테스트 | 15점 | Claude AI (0-10 → 0-15 스케일링, 비-코드 파일 면제) | — |

등급: A(90+), B(75+), C(60+), D(45+), F(44-)

> `ANTHROPIC_API_KEY` 미설정 시 AI 항목은 중립적 기본값(커밋13 + 방향21 + 테스트10 = 44/55)으로 fallback, AI 없이도 최대 89점(B등급) 가능

## 알려진 주의사항 (Gotchas)

- **테스트 환경 변수**: `tests/conftest.py`가 `os.environ.setdefault`로 환경변수를 주입함. src 모듈은 import 시점에 `Settings()`를 인스턴스화하므로 conftest가 반드시 먼저 실행되어야 함
- **psycopg2 버전**: Python 3.13에서는 `psycopg2-binary==2.9.11` 이상 필요
- **멱등성**: `run_analysis_pipeline`은 commit SHA로 중복 체크 — 같은 SHA는 재분석 건너뜀
- **비동기 테스트**: `pytest.ini`의 `asyncio_mode = auto` 필수 (없으면 async 테스트 실패)
- **postgres:// URL**: Railway PostgreSQL이 `postgres://`로 제공하는 경우 config.py에서 `postgresql://`로 자동 변환
- **AI 리뷰 JSON 파싱**: Claude가 JSON 앞에 설명 텍스트를 붙이는 경우 `re.search`로 코드 블록 내 JSON만 추출
- **알림 독립성**: `_build_notify_tasks()` 디스패처가 활성 채널을 조합, `asyncio.gather(return_exceptions=True)`로 실행 — 한 채널 실패해도 나머지 채널은 정상 전송. `repo_config` 로드 실패 시에도 Telegram은 global fallback으로 항상 발송.
- **Webhook 서명**: `X-Hub-Signature-256` 헤더 없으면 403 반환 — 로컬 테스트 시 서명 생성 필요
- **auto_merge GitHub 권한**: `merge_pr()`은 `repo` 스코프 또는 Fine-grained `pull_requests: write` 권한 필요 — 권한 부족 시 False 반환(파이프라인 미중단)
- **Branch Protection Rules**: 보호 규칙이 있는 브랜치는 APPROVE 후에도 Merge 실패 가능 (False 반환, 경고 로그 기록)
- **테스트 파일 분석 제외**: `test_*.py`/`*_test.py` 파일은 bandit 실행 제외 (B101 assert 오탐 방지), pylint/flake8 규칙도 완화
- **Telegram HTML 파싱**: `parse_mode: "HTML"` 사용 — 모든 동적 콘텐츠(AI 요약, 이슈 메시지)에 `html.escape()` 적용 필수
- **비-Python 파일 AI 리뷰**: `.md`, `.cfg`, `.yml` 등도 AI 리뷰 대상 — 정적 분석은 `.py`만 실행, 비-코드 파일만 변경 시 테스트 점수 면제(test_score=10 → 15/15)
- **PR action 필터링**: `pull_request` 이벤트 중 `opened`/`synchronize`/`reopened`만 처리, `closed`/`labeled` 등은 무시
- **E2E 테스트 격리**: `e2e/`를 최상위 별도 디렉토리로 분리 (`tests/` 아래 금지) — `tests/e2e/`가 있으면 `asyncio_mode=auto`와 `sys.modules` 삭제가 충돌해 단위 테스트 98개 실패
- **SQLite hostaddr 제외**: `src/database.py`의 `_ipv4_connect_args`는 hostname이 None(SQLite URL)이면 빈 dict 반환 — 그렇지 않으면 `sqlite3.connect(hostaddr=...)` TypeError 발생
- **E2E 서버 asyncio**: `uvicorn.Server.serve()`를 `asyncio.new_event_loop()` + `loop.run_until_complete()`로 실행 — `server.run()` 대신 사용 (`server.run()`은 asyncio_mode=auto 환경에서 이벤트 루프 충돌)
- **Phase 8B 이후 로그인 필수**: UI 라우트(`/`, `/repos/*`)는 `require_login` Depends로 보호됨. 비로그인 시 `/login` 리다이렉트. `GITHUB_CLIENT_ID`/`GITHUB_CLIENT_SECRET`/`SESSION_SECRET` 미설정 시 OAuth 로그인 불가.
- **기존 Webhook 등록 리포**: `user_id = NULL` 리포는 대시보드에서 모든 로그인 사용자에게 표시됨. `/repos/add`로 동일 리포 재등록 시 소유권 이전 처리 (`user_id=NULL`이면 현재 사용자 소유, 이미 소유자 있으면 에러 팝업).
- **테스트 require_login 우회**: `tests/test_ui_router.py`는 `app.dependency_overrides[require_login] = lambda: _test_user`로 의존성 override. 신규 UI 라우트 테스트 작성 시 동일 패턴 사용.
- **리포 추가 Webhook URL**: `_webhook_base_url(request)` 헬퍼가 `APP_BASE_URL` 설정 시 HTTPS URL 강제, 미설정 시 `request.base_url` 사용. Railway 배포 시 반드시 `APP_BASE_URL`을 설정할 것 — 미설정 시 `http://`로 등록되어 Webhook 전달 실패. 기존 HTTP 등록 리포는 Settings 페이지의 "GitHub Webhook 재등록" 버튼으로 수정.
- **GitHub OAuth token 스코프**: `repo user:email` 스코프. 재로그인 시 토큰 자동 갱신. 100개 초과 리포는 첫 페이지(100개)만 표시.
- **APP_BASE_URL**: Railway 리버스 프록시 환경에서 `http://` 반환 문제 해결. 설정 시 **OAuth redirect_uri**와 **GitHub Webhook 등록 URL** 양쪽에 HTTPS URL 강제 적용. Railway 배포 필수 설정.
- **Telegram 메시지 길이**: `_build_message()`가 4096자 초과 시 자동 절단 (`_TELEGRAM_MAX_LEN = 4096`).
- **DB 세션 expunge**: `get_current_user()`는 `db.expunge(user)` 후 세션 반환 — 세션 종료 후에도 컬럼 속성 안전하게 접근 가능. 관계 lazy-load는 사용하지 말 것.
- **N+1 쿼리 방지**: overview에서 분석 수·최신 분석·평균 점수를 배치 쿼리(subquery + GROUP BY)로 조회. 리포가 늘어나도 쿼리 수는 일정.
- **AI 점수 스케일링**: Claude는 commit 0-20, direction 0-20, test 0-10으로 반환 → calculator가 commit 0-15, direction 0-25, test 0-15로 스케일링. `round()` 사용으로 banker's rounding 적용 (예: 10.5 → 10).
- **커밋 메시지 추출**: `_extract_commit_message()`는 PR 이벤트 시 `title + "\n\n" + body`(body 없으면 title만), Push 이벤트 시 `head_commit["message"]` 우선 사용(없으면 `commits[-1]` fallback). 기존 DB 레코드(0008 마이그레이션 이전)는 `commit_message=NULL`이므로 템플릿에서 fallback 표시.
- **커밋 메시지 CSS**: `.commit-msg-text`는 `white-space: pre-wrap` + `overflow-wrap: break-word`로 줄바꿈. `overflow-x: auto` 대신 `max-height: 300px; overflow-y: auto`로 긴 PR body 대응.
- **모바일 반응형**: `base.html`에 768px/480px 미디어 쿼리. 테이블은 `.table-wrap` 수평 스크롤 래퍼 사용. 480px 이하에서 nav 로고 텍스트 숨김.
- **CLI Hook 인증**: `GET /api/hook/verify`, `POST /api/hook/result`는 X-API-Key 없이 `hook_token` 파라미터/필드로 인증. 일반 개발자 터미널에서 실행되므로 API Key 강제 불가.
- **CLI Hook 점수**: pre-push 훅은 정적 분석 없이 AI 리뷰만 실행 → `calculate_score([], ai_review)` 호출 (code_quality=25, security=20 만점 적용).
- **commit_scamanager_files**: GitHub Contents API `PUT /repos/{owner}/{repo}/contents/{path}` 사용. 파일 이미 있으면 GET으로 sha 조회 후 body에 포함해야 200 성공 (sha 누락 시 422 에러).
- **Mock side_effect 재귀**: `mock.add.side_effect = fn` 설정 후 fn 내에서 `original_add(obj)` 호출 시 재귀 발생. side_effect 함수에서는 원본 mock을 호출하지 말 것 — 캡처만 하고 return None.
- **Alembic batch_alter_table는 PostgreSQL 금지**: `batch_alter_table`은 SQLite 전용 패턴(테이블 전체 재생성). PostgreSQL에서는 `op.create_unique_constraint('이름', '테이블', ['컬럼'])` 직접 사용. 잘못 사용 시 lifespan 마이그레이션 실패 → `/health` 응답 전 프로세스 종료 → Railway 헬스체크 실패.
- **hook_token 비교는 hmac.compare_digest() 필수**: `!=` 연산자는 타이밍 공격에 취약. `src/api/hook.py`의 verify/result 엔드포인트는 `hmac.compare_digest(config.hook_token or "", token)` 사용. 토큰 비교 시 항상 `hmac.compare_digest()` 사용.
- **Telegram 게이트 콜백 HMAC 인증**: 콜백 데이터 형식 `gate:{decision}:{id}:{token}` — token은 `hmac(bot_token, str(analysis_id), sha256)[:16]`. `telegram_gate.py`의 `_gate_callback_token()` 참조. 테스트 시 HMAC 토큰을 직접 계산해 픽스처에 포함해야 함.
- **SMTP_PORT 빈 문자열**: Railway 환경에서 `SMTP_PORT=""`로 설정 시 pydantic ValidationError로 즉시 크래시. `config.py`의 `coerce_smtp_port` validator가 처리하므로 Railway Variables에서 SMTP_PORT 값을 삭제하거나 숫자로 설정.
- **_ipv4_connect_args with 블록 금지**: `ThreadPoolExecutor`를 `with` 문으로 사용하면 `__exit__`가 `shutdown(wait=True)` 호출 → DNS hang 시 무기한 블록. `try/finally` + `executor.shutdown(wait=False)` 패턴 사용 (database.py 참조).
- **분석 source 필드**: `pipeline.py`가 result JSON에 `"source": "pr"|"push"` 저장. 기존 레코드(source 없음) 대응으로 `router.py` analysis_detail에서 `result.get("source") or ("pr" if pr_number else "push")` fallback 파생.
- **ChangedFile 단일 출처**: `src/github_client/models.py`가 정의 출처. `src/github_client/diff.py`와 `src/cli/git_diff.py`는 이곳에서 import. 새로운 파일 수집 모듈 추가 시 동일 패턴 사용.
- **GitHub API 헤더 공용 헬퍼**: `src/github_client/helpers.py`의 `github_api_headers(token)` 사용. 새 GitHub API 호출 시 직접 dict를 만들지 말 것.
- **알림 채널 추가 체크리스트**: `RepoConfig` ORM → `RepoConfigData` dataclass → `RepoConfigUpdate` API body → UI 폼 4곳 반드시 동기화. 누락 시 REST API 업데이트 시 해당 필드가 NULL로 덮어써지는 버그 발생.
- **_build_result_dict**: `src/worker/pipeline.py` 모듈 레벨 함수. pipeline과 hook.py 두 곳에서 Analysis.result dict를 생성할 때 사용. 결과 구조 변경 시 이 함수만 수정하면 됨.

## Railway 배포

```bash
# 시작 명령 (railway.toml에 설정됨 — --proxy-headers 포함)
uvicorn src.main:app --host 0.0.0.0 --port $PORT --proxy-headers
# DB 마이그레이션은 앱 lifespan에서 자동 실행
```

Railway 대시보드 설정:
- **PostgreSQL 플러그인** 추가 (`DATABASE_URL` 자동 생성)
- **Variables** 탭에서 나머지 환경변수 설정
- `DATABASE_URL` 참조: `${{Postgres.DATABASE_URL}}`
- `APP_BASE_URL` 반드시 설정 — OAuth redirect_uri HTTPS 보장

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
| Phase 5 | n8n 연동 + 외부 REST API + 통계 고도화 | ✅ 완료 (~4 테스트, 총 112 테스트) |
| Phase 6 | PR 자동 Merge (auto_merge 설정 + squash merge) | ✅ 완료 (19 테스트, 총 146 테스트) |
| Phase 7 | 3-테마 UI 리디자인 + Playwright E2E 테스트 | ✅ 완료 (단위 146개 + E2E 26개) |
| Phase 8A | Google OAuth + User 모델 + 사용자별 대시보드 | ✅ 완료 (단위 164개) |
| Phase 8B | GitHub OAuth + 리포 추가 UI + Webhook 자동 생성 + 운영 이슈 수정 | ✅ 완료 (단위 179개) |
| 코드 품질 | 전수 검토 — N+1 방지, DB expunge, 로깅 보강, Telegram 4096 절단 | ✅ 완료 |
| UI 개선 | overview 평균 점수 표시 + 전체 페이지 모바일 반응형 CSS | ✅ 완료 (단위 180개) |
| 점수 개선 | 감점 완화 + 배점 재조정 + AI 프롬프트 보정 + Diff 16K 확대 | ✅ 완료 (단위 186개) |
| 알림 확장 | Discord + Slack + Generic Webhook + Email 알림 채널 + pipeline 디스패처 | ✅ 완료 (단위 223개) |
| 분석 상세 | 분석 이력 클릭 → 상세 코드 리뷰 페이지 + commit_message DB 저장 | ✅ 완료 (단위 227개) |
| 커밋 메시지 개선 | PR body 포함 전체 캡처 + head_commit 우선 + 모바일 CSS 수평 스크롤 수정 | ✅ 완료 (단위 230개) |
| CLI 코드리뷰 | 터미널 CLI 도구 — 로컬 git diff + 정적 분석 + AI 리뷰 + 점수 산출 | ✅ 완료 (단위 259개) |
| CLI Hook 자동 코드리뷰 | git push 시 pre-push hook 자동 실행 — Claude Code CLI 기반, 대시보드 저장 | ✅ 완료 (단위 273개) |
| 보안 강화 | hook_token hmac.compare_digest + Telegram gate HMAC 콜백 인증 + 중복 분석 체크 | ✅ 완료 (단위 273개) |
| Webhook 재등록 | APP_BASE_URL 기반 HTTPS URL 강제 + POST reinstall-webhook 엔드포인트 | ✅ 완료 (단위 276개) |
| 설정 페이지 UI | 2컬럼 그리드 + 그라디언트 카드 헤더 + 슬라이더+숫자 인라인 + 3테마 CSS 변수 | ✅ 완료 (단위 276개) |
| 분석 상세 표시 개선 | source 필드 파생·표시 + commit_message 미리보기 + 날짜·시간·SHA title | ✅ 완료 (단위 284개) |
| nav 로그인/로그아웃 UI | base.html nav에 display_name + 로그아웃 버튼 (3테마·모바일 반응형) | ✅ 완료 (단위 287개) |
| 이력 페이지 조회 강화 | 텍스트 검색·등급/소스 필터·정렬·페이지네이션·점수 슬라이더·소스 컬럼 | ✅ 완료 (단위 292개) |
| 코드품질 강화 | pylint 0→9.29 + API 버그 수정 + 중복 제거 + 전 모듈 docstring + flake8 0건 | ✅ 완료 (단위 296개) |
