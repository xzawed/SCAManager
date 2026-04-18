<div align="center">

# 🛡️ SCAManager

**GitHub Push / PR 이벤트 기반 자동 코드 품질 분석 · AI 리뷰 · Gate 서비스**

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-SQLAlchemy_2-336791?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Claude AI](https://img.shields.io/badge/Claude_AI-Haiku_4.5-CC6600?style=flat-square&logo=anthropic&logoColor=white)](https://www.anthropic.com/)
[![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?style=flat-square&logo=railway&logoColor=white)](https://railway.app/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

[![Tests](https://img.shields.io/badge/Tests-504_passing-brightgreen?style=flat-square&logo=pytest&logoColor=white)](tests/)
[![pylint](https://img.shields.io/badge/pylint-9.70%2F10-brightgreen?style=flat-square&logo=python&logoColor=white)](src/)
[![bandit](https://img.shields.io/badge/bandit-HIGH_0-brightgreen?style=flat-square&logo=security&logoColor=white)](src/)
[![Coverage](https://img.shields.io/badge/Coverage-94%25-brightgreen?style=flat-square&logo=codecov&logoColor=white)](tests/)

</div>

---

## 📖 개요

**SCAManager**는 GitHub 리포지토리의 코드 품질을 자동으로 관리하는 서비스입니다.

Push 또는 PR 이벤트가 발생하면 **정적 분석(pylint · flake8 · bandit)** 과 **Claude AI 리뷰**를 병렬로 실행하고, 

100점 만점의 점수와 A~F 등급을 산출합니다. 

결과는 **Telegram · GitHub · Discord · Slack · Email · n8n** 등 다양한 채널로 즉시 전달되며, 

점수에 따라 PR을 자동 Approve/Reject하고 squash merge까지 자동화할 수 있습니다.

main 브랜치에 직접 push하는 팀을 위해 **커밋 코멘트 자동 게시**와 **GitHub Issue 자동 생성**도 지원합니다.

---

## 🗂️ 탄생 배경과 운영기

### 왜 만들었나

자꾸 Railway에서 빌드시 터져나가는 Repo를 보면서 코드리뷰를 제대로 하는 무언가 있어야겠다 생각을 했습니다. 

자동화가 답이라고 생각했었고 사람이나 혹은 AI가 구현한 버그(?)를 놓치는 걸 도구가 잡아주고, 

점수라는 숫자로 코드 상태를 객관화하면 "리뷰해줘"라는 말 없이도 품질 기준이 생기지 않을까 싶었습니다. 

거기에 Claude AI가 커밋 메시지부터 구현 방향성까지 봐준다면 정적 도구가 잡지 못하는 영역도 커버할 수 있겠다고 판단했습니다.

---

### 운영하면서 부딪힌 것들

**PR 기능이 무용지물이 되던 문제**

처음 설계는 PR 중심이었습니다. Approve 자동화, PR에 리뷰 댓글 달기, PR 점수 기반 merge 차단. 

그런데 막상 운영해보니 대부분이 `main` 브랜치에 직접 push하고 있었고 

PR을 쓰지 않으니 Gate 기능 전체가 사실상 쓸모없는 상태였습니다.(브랜치관리를 하며 운영을 하는게 정석이지만 그러지 못한게 아쉽습니다.)

결국 push 이벤트에서도 실질적인 피드백이 돌아오도록 두 가지를 추가했습니다.(이미 걸어온 길이 멀었기에...) 

점수가 임계값 아래거나 bandit HIGH가 발견되면 GitHub Issue를 자동 생성하고, 커밋에 AI 리뷰 결과를 댓글로 바로 달아주는 방식입니다. 

이제는 PR 없이도 Commit 단위로 코드 상태를 추적할 수 있게 되었습니다.


**Webhook이 두 번 날아오면 분석도 두 번 됐다**

GitHub가 Webhook을 재전달하는 경우가 있었습니다.(왜..) 응답이 조금 늦으면 같은 이벤트가 두 번 들어오고, 

그러면 분석이 중복으로 실행되면서 DB에 같은 커밋 SHA의 Analysis 레코드가 두 개 생겼습니다.

대시보드 차트가 이상하게 튀는 걸 보고서야 발견했습니다.(ㅋㅋㅋㅋㅋㅋ...)


첫 번째 세션에서 SHA 중복 체크를 하고, `_save_and_gate` 직전에 한 번 더 확인하는 이중 방어를 넣었습니다. 

두 번째 체크는 진짜 동시 요청이 레이스를 뚫고 들어오는 걸 막기 위한 것이었습니다. 

완벽한 해결은 아니지만 실제 운영에서 중복 레코드는 더 이상 생기지 않았습니다.


**SQLAlchemy 세션이 닫히면 사용자 정보가 사라졌다**

로그인한 사용자 정보를 `get_current_user()`로 가져와서 여기저기 넘겼는데, 

특정 타이밍에 `DetachedInstanceError`가 발생했습니다. 

DB 세션이 닫힌 뒤에 ORM 객체의 관계 속성에 접근하면 SQLAlchemy가 lazy load를 시도하다 실패하는 문제였습니다.

`expunge()`로 세션에서 분리해도 관계 컬럼은 여전히 문제가 되었고, 

결국 필요한 필드만 뽑아서 `CurrentUser` 데이터클래스로 변환하는 방식으로 바꿨습니다.

세션 생명주기와 완전히 분리되니 이후로는 재현되지 않았습니다.


**pre-push 훅에서 쉘 인젝션이 가능했다**

CLI Hook 스크립트가 커밋 메시지를 명령줄 인자로 `claude -p "메시지"` 에 넘기고 있었습니다. 

커밋 메시지에 백틱이나 `$()` 같은 쉘 메타문자가 들어오면 그대로 실행될 수 있다는 걸 뒤늦게 깨달았고, 

실제로 테스트해봤더니 정말 됐습니다(!).

stdin으로 넘기는 방식으로 바꿨고 `echo "$msg" | claude -p` 형태로 처리하면 메시지가 명령줄을 거치지 않으므로 

인젝션 자체가 성립하지 않았습니다. 

스크립트 전체도 `set -euo pipefail`과 변수 쿼팅을 정비했습니다.


**알림 채널 URL을 검증하지 않으면 내부망으로 요청이 나갔다**

Discord · Slack · n8n 같은 외부 Webhook URL을 DB에 저장해두고 그대로 `httpx`로 호출하는 구조였습니다. 

누군가 `http://169.254.169.254/latest/meta-data/` 같은 URL을 설정하면 

서버가 클라우드 메타데이터 엔드포인트에 요청을 보내는 SSRF가 가능했습니다.

URL을 받을 때 `https`인지 먼저 확인하고, DNS 조회 결과를 `ipaddress` 모듈로 검사해서 

사설 대역이나 루프백, 링크로컬 주소가 나오면 해당 채널을 건너뛰도록 공용 헬퍼를 만들었고, 

검증 실패해도 다른 채널에는 영향이 없도록 독립성을 유지했습니다.


**Railway에서 Python 프로젝트를 Node.js로 인식했다**

`package.json` 비슷한 파일이 있거나 특정 조건이 맞으면 NIXPACKS가 Python 프로젝트를 

Node.js로 오인해서 `npm run build`를 실행하려 했습니다.(흐음...) 

빌드 로그를 보기 전까지는 왜 배포가 실패하는지 원인을 알 수 없었습니다.


`nixpacks.toml`에 `providers = ["python"]`을 명시해도 근본적인 해결이 안 되었고, 

`railway.toml`의 `buildCommand`가 NIXPACKS 설정보다 우선순위가 높다는 걸 확인하고, 

거기에 빌드 명령을 명시적으로 덮어쓰는 방식으로 해결했습니다.


**E2E 테스트와 단위 테스트가 같은 디렉토리에 있으면 충돌했다**

Playwright E2E 테스트를 `tests/e2e/` 안에 넣었더니 `asyncio_mode=auto` 설정과 충돌해서 

단위 테스트 100개 가까이 한꺼번에 실패했습니다.(ㅋㅋㅋㅋ...) 

E2E 서버를 띄우는 방식과 pytest-asyncio의 이벤트 루프 관리 방식이 맞지 않았고, 

`e2e/`를 프로젝트 루트에 별도 디렉토리로 분리하는 것으로 해결했습니다. 

단순한 구조 변경이었는데 두 테스트 스위트가 서로 간섭 없이 독립적으로 동작하게 됐습니다.

---

## ✨ 주요 기능

### 🔍 자동 코드 분석

| 분석 항목 | 도구 | 대상 |
|-----------|------|------|
| 코드 품질 | pylint + flake8 | `.py` 파일 |
| 보안 취약점 | bandit | `.py` 파일 (테스트 제외) |
| AI 리뷰 | Claude Haiku 4.5 | 모든 변경 파일 |
| 커밋 메시지 | Claude AI | Push/PR 메시지 |

- Push(`push`) 및 PR(`opened` / `synchronize` / `reopened`) 이벤트 자동 처리
- 정적 분석과 AI 리뷰를 `asyncio.gather()`로 **병렬 실행** — 대기 시간 최소화
- `ANTHROPIC_API_KEY` 미설정 시 AI 항목은 중립 기본값 적용, **AI 없이도 최대 89점(B등급)** 가능

---

### 🏆 점수 체계

| 항목 | 배점 | 감점 규칙 |
|------|------|-----------|
| 🧹 코드 품질 | 25점 | error −3 · warning −1 (pylint 15개·flake8 10개 cap) |
| 🔒 보안 | 20점 | HIGH −7 · LOW/MED −2 |
| 📝 커밋 메시지 | 15점 | Claude AI 평가 (0→20 → 0→15 스케일링) |
| 🧠 구현 방향성 | 25점 | Claude AI 평가 (0→20 → 0→25 스케일링) |
| 🧪 테스트 코드 | 15점 | Claude AI 평가 (0→10 → 0→15 스케일링, 비코드 파일 면제) |
| **합계** | **100점** | |

**등급 기준**

| 등급 | 점수 | 의미 |
|------|------|------|
| 🥇 A | 90점 이상 | 우수 |
| 🥈 B | 75점 이상 | 양호 |
| 🥉 C | 60점 이상 | 보통 |
| ⚠️ D | 45점 이상 | 개선 필요 |
| 🚨 F | 44점 이하 | 심각 |

---

### 🔔 알림 채널

| 채널 | 내용 | 설정 |
|------|------|------|
| 📱 Telegram | 점수 상세 · AI 요약 · 개선 제안 · 정적 이슈 (HTML 파싱) | 기본 |
| 💬 GitHub PR Comment | 카테고리별·파일별 피드백 + 점수 테이블 | 리포별 설정 |
| 📌 GitHub Commit Comment | Push 커밋에 AI 리뷰 댓글 게시 | 리포별 설정 |
| 🐛 GitHub Issue | 점수 미달 또는 보안 HIGH 발견 시 자동 생성 | 리포별 설정 |
| 🎮 Discord | Embed 형식 알림 | 리포별 설정 |
| 💼 Slack | Attachment 형식 알림 | 리포별 설정 |
| 📧 Email | SMTP HTML 이메일 | 리포별 설정 |
| 🔗 Generic Webhook | 범용 JSON POST | 리포별 설정 |
| 🔄 n8n | 외부 워크플로우 트리거 | 리포별 설정 |

모든 채널은 `asyncio.gather(return_exceptions=True)`로 **독립 실행** — 한 채널의 실패가 다른 채널에 영향을 주지 않습니다.

---

### ⚡ PR Gate Engine

점수 기반으로 PR을 자동으로 처리합니다.

```
PR 분석 완료
    ├── [자동 모드]   점수 ≥ approve_threshold → GitHub APPROVE
    │                점수 < reject_threshold  → GitHub REQUEST_CHANGES
    │
    ├── [반자동 모드] Telegram 인라인 버튼 전송 → 수동 승인/반려
    │
    └── [Auto Merge] 점수 ≥ merge_threshold   → squash merge 자동 실행
                     (approve_mode와 완전 독립 동작)
```

| 설정 | 동작 |
|------|------|
| `approve_mode="auto"` | 임계값 기준 자동 Approve / Request Changes |
| `approve_mode="semi-auto"` | Telegram 버튼으로 수동 결정 |
| `auto_merge=true` | 임계값 통과 시 squash merge 자동 실행 |

---

### 🖥️ 웹 대시보드

GitHub OAuth로 로그인 후 브라우저에서 모든 기능을 사용할 수 있습니다.

- **리포지토리 추가** — GitHub 드롭다운 선택만으로 Webhook 자동 생성
- **점수 추이 차트** — Chart.js 기반 히스토리 시각화
- **분석 상세** — AI 리뷰 · 카테고리별 피드백 · 정적 분석 이슈 목록
- **설정 페이지** — Gate 모드 · 임계값 슬라이더 · 알림 채널 토글
- **테마** — Dark / Light / Glass 3가지 테마 완전 지원

---

### 💻 CLI 코드리뷰 도구

터미널에서 즉시 실행하는 로컬 코드리뷰 도구입니다.

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

> `ANTHROPIC_API_KEY` 환경변수 필요 · GitHub Actions · Codespaces · 일반 터미널 모두 지원

---

### 🪝 CLI Hook (로컬 pre-push 자동 코드리뷰)

`git push` 시 자동으로 코드리뷰가 실행되는 Git Hook입니다.

```bash
# 리포 등록 후 1회만 실행
git pull
bash .scamanager/install-hook.sh

# 이후 git push 시 자동 실행
git push origin main
# → 터미널에 AI 리뷰 결과 출력
# → SCAManager 대시보드에 자동 저장
```

- **ANTHROPIC_API_KEY 불필요** — 로컬에 설치된 Claude Code CLI(`claude -p`) 활용
- 결과는 터미널 출력 + 대시보드 동시 저장
- push 차단 없음 — 항상 `exit 0`으로 정상 진행

> **요구사항:** Claude Code CLI(`claude`)가 설치된 Mac / Linux / Windows 데스크탑 환경  
> 미설치 환경(Codespaces · 모바일 · CI)에서는 조용히 건너뜁니다.

---

## 🛠️ 기술 스택

| 분류 | 기술 |
|------|------|
| **언어** | Python 3.13 |
| **웹 프레임워크** | FastAPI + Uvicorn |
| **인증** | GitHub OAuth2 (authlib) + Starlette SessionMiddleware |
| **데이터베이스** | PostgreSQL · SQLAlchemy 2 · Alembic · FailoverSessionFactory |
| **AI (서버)** | Anthropic Claude API (claude-haiku-4-5) |
| **AI (로컬 Hook)** | Claude Code CLI (`claude -p`) |
| **정적 분석** | pylint · flake8 · bandit |
| **테스트** | pytest · pytest-asyncio · httpx TestClient |
| **E2E 테스트** | Playwright (Chromium) |
| **웹 UI** | Jinja2 · Chart.js · CSS Variables (3테마) |
| **알림** | Telegram · GitHub · Discord · Slack · Email · n8n · Webhook |
| **배포** | Railway / 온프레미스 (systemd · nginx · Docker Compose) |

---

## 🚀 시작하기

### 📋 요구사항

- Python **3.13** 이상
- PostgreSQL
- GitHub OAuth App (Client ID / Client Secret)
- (선택) Telegram Bot Token · SMTP 서버 · ANTHROPIC_API_KEY

### ⬇️ 설치

```bash
git clone https://github.com/xzawed31/SCAManager.git
cd SCAManager

# 개발 환경 (pytest + playwright 포함)
pip install -r requirements-dev.txt

# 프로덕션 환경 (Railway 자동 감지)
pip install -r requirements.txt
```

### ⚙️ 환경변수 설정

```bash
cp .env.example .env
```

**필수 환경변수**

| 변수 | 설명 |
|------|------|
| `DATABASE_URL` | PostgreSQL 연결 URL (`postgres://` → `postgresql://` 자동 변환) |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API 토큰 |
| `TELEGRAM_CHAT_ID` | 기본 알림 수신 Chat ID |
| `GITHUB_CLIENT_ID` | GitHub OAuth App 클라이언트 ID |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth App 클라이언트 시크릿 |
| `SESSION_SECRET` | 세션 쿠키 서명 키 (32자 이상 랜덤 문자열 **필수**) |

**권장 환경변수**

| 변수 | 설명 |
|------|------|
| `APP_BASE_URL` | 배포 URL (`https://your-app.railway.app`) — OAuth redirect_uri · Webhook URL에 자동 적용 |
| `ANTHROPIC_API_KEY` | Claude AI 리뷰 키 (미설정 시 기본값 적용) |

**선택 환경변수**

| 변수 | 설명 |
|------|------|
| `API_KEY` | REST API 인증 키 (X-API-Key 헤더) |
| `GITHUB_TOKEN` | 레거시 리포용 GitHub API 토큰 |
| `GITHUB_WEBHOOK_SECRET` | 레거시 리포용 Webhook 시크릿 |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` | Email 알림 SMTP 설정 |
| `DATABASE_URL_FALLBACK` | Failover용 보조 DB URL (단일 엔진 모드 시 미설정) |
| `DB_FAILOVER_PROBE_INTERVAL` | Primary DB 복구 확인 주기 초 (기본 30) |
| `DB_SSLMODE` | PostgreSQL SSL 모드 (`require` / `disable`) |
| `DB_FORCE_IPV4` | IPv4 강제 연결 (`true` — Railway 환경) |

### ▶️ 실행

```bash
# 개발 서버 (DB 마이그레이션 자동 실행)
uvicorn src.main:app --reload --port 8000

# 또는 Make 명령
make run
```

---

## 🧪 개발 명령

```bash
make install          # 의존성 설치
make test             # 전체 테스트 (빠른 출력)
make test-v           # 전체 테스트 (상세 출력)
make test-cov         # 테스트 + 커버리지
make lint             # pylint + flake8 + bandit
make review           # CLI 코드리뷰 (HEAD~1 기준)
make run              # 개발 서버 (port 8000)
make migrate          # DB 마이그레이션
make revision m="설명" # 새 마이그레이션 생성
make install-playwright # Playwright + Chromium 설치
make test-e2e         # E2E 테스트 (headless)
make test-e2e-headed  # E2E 테스트 (브라우저 표시)
```

---

## 🌐 화면 구성

```
/login                              → 🔑 GitHub OAuth 로그인
/repos/add                          → ➕ 리포지토리 추가
/                                   → 📊 전체 리포 현황 대시보드
/repos/{owner/repo}                 → 📈 점수 추이 차트 + 분석 이력
/repos/{owner/repo}/analyses/{id}   → 🔍 분석 상세 (AI 리뷰 · 피드백)
/repos/{owner/repo}/settings        → ⚙️  Gate · 알림 · Hook 설정
```

> 모든 UI 페이지는 로그인 필수 — 미로그인 시 `/login` 자동 리다이렉트

---

## 📡 API 엔드포인트

<details>
<summary>전체 엔드포인트 목록 펼치기</summary>

**인증 (OAuth)**
```
GET  /login                          로그인 페이지
GET  /auth/github                    GitHub OAuth 인증 시작
GET  /auth/callback                  GitHub OAuth 콜백
POST /auth/logout                    로그아웃
```

**웹 대시보드**
```
GET  /                               리포 현황 목록
GET  /repos/add                      리포 추가 페이지
GET  /repos/{repo}                   리포 상세 (차트 + 이력)
GET  /repos/{repo}/analyses/{id}     분석 상세
GET  /repos/{repo}/settings          설정 페이지
POST /repos/add                      리포 등록 + Webhook + Hook 파일 자동 생성
POST /repos/{repo}/settings          설정 저장
POST /repos/{repo}/reinstall-hook    CLI Hook 파일 재커밋
POST /repos/{repo}/reinstall-webhook Webhook 재등록
POST /repos/{repo}/delete            리포 삭제 (Webhook + 이력 포함)
```

**Webhook 수신**
```
POST /webhooks/github                GitHub Webhook (HMAC-SHA256 서명 검증)
POST /api/webhook/telegram           Telegram Gate 콜백 (HMAC 인증)
```

**REST API** (X-API-Key 헤더 인증)
```
GET  /api/repos                      리포지토리 목록
GET  /api/repos/{repo}/analyses      분석 이력 (skip · limit 페이지네이션)
PUT  /api/repos/{repo}/config        리포 설정 변경
DELETE /api/repos/{repo}             리포 삭제 (API 모드 — Webhook 수동 삭제)
GET  /api/repos/{repo}/stats         점수 통계 · 추이
GET  /api/analyses/{id}              분석 상세 조회
```

**CLI Hook** (hook_token 인증)
```
GET  /api/hook/verify                Hook 등록 확인
POST /api/hook/result                코드리뷰 결과 저장
```

**헬스체크**
```
GET  /health                         {"status":"ok","active_db":"primary"|"fallback"}
```

</details>

---

## 🏗️ 아키텍처

```
GitHub Push/PR
  └─ POST /webhooks/github  (HMAC-SHA256 서명 검증)
       └─ BackgroundTask: run_analysis_pipeline()
            ├─ Repository DB 등록 · SHA 중복 체크 (멱등성 보장)
            ├─ get_pr_files / get_push_files
            │
            ├─ asyncio.gather() ── 병렬 실행
            │    ├─ analyze_file() × N  (pylint · flake8 · bandit)
            │    └─ review_code()       (Claude AI)
            │
            ├─ calculate_score()  →  점수 · 등급
            ├─ Analysis DB 저장
            │
            ├─ run_gate_check()   [PR 이벤트만]
            │    ├─ pr_review_comment → GitHub PR 댓글
            │    ├─ approve_mode=auto → GitHub APPROVE / REQUEST_CHANGES
            │    ├─ approve_mode=semi → Telegram 인라인 키보드
            │    └─ auto_merge        → squash merge
            │
            └─ asyncio.gather(return_exceptions=True)  ── 독립 알림
                 ├─ Telegram
                 ├─ GitHub Commit Comment  [Push + commit_comment=on]
                 ├─ GitHub Issue           [score < threshold or bandit HIGH]
                 ├─ Discord
                 ├─ Slack
                 ├─ Generic Webhook
                 ├─ Email
                 └─ n8n
```

---

## ☁️ 배포

### 🚂 Railway 배포

1. Railway 프로젝트 생성 후 이 리포지토리 연결
2. **PostgreSQL 플러그인** 추가 (`DATABASE_URL` 자동 생성)
3. **Variables** 탭에서 환경변수 설정

```
TELEGRAM_BOT_TOKEN    = <your-token>
TELEGRAM_CHAT_ID      = <your-chat-id>
GITHUB_CLIENT_ID      = <oauth-client-id>
GITHUB_CLIENT_SECRET  = <oauth-client-secret>
SESSION_SECRET        = <random-32-chars>
APP_BASE_URL          = https://your-app.up.railway.app  ← 필수!
ANTHROPIC_API_KEY     = sk-ant-...                       ← 권장
```

4. 배포 완료 — DB 마이그레이션 자동 실행 (앱 lifespan)

> ⚠️ `APP_BASE_URL` 미설정 시 OAuth redirect_uri와 Webhook URL이 `http://`로 등록되어 인증 실패

### 🖥️ 온프레미스 배포

```bash
# 기본 시작 명령 (--proxy-headers: 리버스 프록시 IP 신뢰)
uvicorn src.main:app --host 0.0.0.0 --port 8000 --proxy-headers
```

**DB Failover 설정** — `DATABASE_URL_FALLBACK`에 보조 DB URL을 설정하면 Primary 장애 시 자동 전환됩니다.  
상태 확인: `GET /health` → `{"active_db": "primary" | "fallback"}`

자세한 내용은 [온프레미스 마이그레이션 가이드](docs/guides/onpremise-migration-guide.md)를 참고하세요.

---

## 🔧 GitHub OAuth App 설정

1. **GitHub → Settings → Developer settings → OAuth Apps → New OAuth App**
2. 항목 입력:

| 항목 | 값 |
|------|----|
| Application name | SCAManager |
| Homepage URL | `https://your-domain` |
| Authorization callback URL | `https://your-domain/auth/callback` |

3. **Client ID**와 **Client Secret**을 환경변수에 설정

> 로컬 개발 시 callback URL을 `http://localhost:8000/auth/callback`으로 추가 등록하거나, 별도 OAuth App을 생성하세요.

---

## ➕ 리포지토리 등록 방법

1. 로그인 후 대시보드 → **+ 리포 추가** 클릭
2. GitHub 드롭다운에서 리포지토리 선택
3. **Webhook 생성 + 리포 추가** 클릭
   - GitHub Webhook 자동 생성 (HMAC 시크릿 포함)
   - `.scamanager/config.json` · `install-hook.sh` 자동 커밋
4. Push 또는 PR 이벤트 발생 시 분석 자동 시작 ✅

### Webhook URL 변경 시 (배포 URL 이전 등)

**설정 탭 → CLI Hook 카드 → 🔗 Webhook 재등록** 버튼 클릭  
현재 `APP_BASE_URL` 기준으로 Webhook이 재생성됩니다.

### CLI Hook 설치 (로컬 pre-push)

```bash
git pull
bash .scamanager/install-hook.sh
# 이후 git push 시마다 자동 코드리뷰 실행
```

---

## 💻 GitHub Codespaces

```bash
# 컨테이너 시작 후 즉시 사용 가능 (.env 불필요 — SQLite 인메모리)
make test    # 전체 테스트
make lint    # 코드 품질 검사
make run     # 개발 서버 (포트 8000 자동 포워딩)

# CLI 코드리뷰 (ANTHROPIC_API_KEY 필요)
ANTHROPIC_API_KEY=sk-ant-... python -m src.cli review
```

> Codespaces에서는 Claude Code CLI가 없으므로 **CLI Hook은 동작하지 않습니다.**  
> 대신 `python -m src.cli review` 명령을 사용하세요.

---

## 📄 라이선스

[MIT License](LICENSE) © 2024 xzawed31
