# Claude + Codex 협업 문서 구조 정리 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AGENTS.md를 Codex 역할에 맞는 ~120줄 문서로 재작성하고, `.codex/rules/` 8개 파일을 신설하여 CLAUDE.md를 단일 정책 권위로 확립한다.

**Architecture:** CLAUDE.md(17개 정책, 단일 권위) + AGENTS.md(Codex 역할·핵심 규칙 + CLAUDE.md 참조 포인터) + `.codex/rules/`(path-scoped 코딩 규칙만, 협업 정책 제외)

**Tech Stack:** Markdown, TOML (에이전트 파일), Git/GitHub (PR)

---

## 병렬 작업 구조

- **Task 1**: 브랜치 생성 (선행 필수)
- **Task 2 (Agent A)**: AGENTS.md 재작성
- **Task 3-10 (Agent B)**: `.codex/rules/` 8개 파일 생성
- **Task 11 (Agent C)**: `.codex/agents/` 정합성 검증·수정
- **Task 12**: 최종 검증
- **Task 13**: 커밋 + PR

---

## Task 1: 브랜치 생성

**Files:**
- 없음 (git 작업)

- [ ] **Step 1: 최신 main 기반 브랜치 생성**

```bash
cd "f:\DEVELOPMENT\SOURCE\CLAUDE\SCAManager"
git checkout main
git pull origin main
git checkout -b chore/codex-docs-setup
```

Expected: `Switched to a new branch 'chore/codex-docs-setup'`

---

## Task 2 (Agent A): AGENTS.md 완전 재작성

**Files:**
- Modify: `AGENTS.md` (루트, 439줄 → ~120줄 재작성)

- [ ] **Step 1: AGENTS.md 재작성**

아래 내용으로 `AGENTS.md` 전체를 교체한다:

```markdown
# SCAManager

> **문서 작성 원칙**: 이 프로젝트의 모든 문서는 AI가 가장 읽기 쉽고 이해하기 편한 구조로 작성한다.
> 새 문서를 작성하거나 기존 문서를 수정할 때 이 원칙을 반드시 따른다.

> **코드 주석 원칙 (이중 언어)**: 모든 코드 주석은 **한국어와 영어를 병행**하여 작성한다.
> 한국어를 먼저 쓰고, 바로 다음 줄에 영어를 추가한다.
> 신규 코드 작성 시 즉시 적용하고, 기존 파일은 해당 파일을 수정할 때 함께 갱신한다.
> 예외: `# TODO`, `# FIXME`, `# type: ignore` 등 단어 하나짜리 표준 태그는 영어 단독 사용 허용.
>
> ```python
> # 레이트 리밋 초과 시 재시도
> # Retry on rate limit exceeded
> ```

GitHub Push/PR 이벤트 시 정적 분석 + AI 코드 리뷰를 자동 수행하고, 점수와 개선사항을 Telegram·GitHub PR Comment·Discord·Slack·Email·n8n으로 전달하며, 점수 기반 PR 자동/반자동 Gate(Approve + 자동 Merge 포함)와 웹 대시보드를 제공하는 서비스.

---

## Codex 역할

Codex는 **반복 구현 전담** 에이전트다:

- 테스트 코드 작성 (TDD Red 단계 — 실패하는 테스트 먼저)
- 리팩토링 및 코드 단순화
- 반복적인 파일 수정 (번역 키 추가, 필드명 변경, 일괄 수정 등)
- 명확하게 명세된 기능 구현

**Claude에게 위임할 작업** (Codex 단독 처리 금지):
- 아키텍처·설계 결정, 협업 정책 해석
- 회고, 멀티에이전트 디스패치 기획
- Phase 계획 수립 및 사이클 관리

> **전체 협업 정책 17개, 회고 패턴, 사이클 관리**: `CLAUDE.md` §"사용자 협업 정책 (2026-05-01 합의)" 참조.

---

## 핵심 명령

```bash
cp .env.example .env   # 최초 설정
make install           # 의존성 설치 (requirements-dev.txt)
make run               # 개발 서버 (port 8000, DB 마이그레이션 자동)
```

| 명령 | 동작 |
|------|------|
| `make test` | 전체 테스트 (빠른 출력) |
| `make test-v` | 전체 테스트 (상세 출력) |
| `make test-fast` | 단위 테스트만 (`tests/integration/` 제외) |
| `make lint` | pylint + flake8 + bandit |
| `make test-e2e` | E2E 테스트 (headless) |
| `make migrate` | DB 마이그레이션 실행 |
| `make revision m="설명"` | 새 마이그레이션 파일 생성 |

---

## 항상 적용 규칙 (4개)

### 1. 이중 언어 주석
```python
# 레이트 리밋 초과 시 재시도
# Retry on rate limit exceeded

# 같은 SHA가 이미 분석된 경우 건너뜀 (멱등성 보장)
# Skip if the same SHA was already analyzed (idempotency guard)
```

### 2. TDD 우선
구현 코드 작성 전 반드시 실패하는 테스트를 먼저 작성한다. `test-writer` 에이전트 활용 권장.

### 3. 브랜치 워크플로 (main 직접 커밋 금지)
```bash
git checkout -b <type>/<scope>-<desc>   # feat/, fix/, chore/, docs/
# 작업 + commit
git push -u origin <branch>
# PR 생성 (gh pr create 또는 GitHub 웹)
```
**예외 없음** — typo 수정, docs 변경도 브랜치 + PR 방식.

### 4. 코드 단순화
정확성·성능 유지. 불필요한 추상화 금지 (헬퍼는 사용처 ≥ 3 시에만 추출).

---

## 아키텍처

- **src/ 트리 + 모듈 역할**: [`docs/architecture.md`](docs/architecture.md)
- **핵심 데이터 흐름** (Webhook → pipeline → notify → gate): [`docs/architecture.md#핵심-데이터-흐름`](docs/architecture.md#핵심-데이터-흐름)
- **점수 체계**: [`docs/reference/scoring.md`](docs/reference/scoring.md)
- **환경변수 전체 목록**: [`docs/reference/env-vars.md`](docs/reference/env-vars.md)

> 🔴 **신규 파일 추가 시 `docs/architecture.md` 동기화 의무** — src/ 트리 항목 + 핵심 데이터 흐름 갱신.

## 환경변수 (필수만)

| 변수 | 설명 |
|------|------|
| `DATABASE_URL` | PostgreSQL 연결 URL (`postgres://`는 `postgresql://`로 자동 변환) |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API 토큰 |
| `TELEGRAM_CHAT_ID` | Telegram 알림 수신 Chat ID |
| `GITHUB_CLIENT_ID` | GitHub OAuth 앱 클라이언트 ID |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth 앱 클라이언트 시크릿 |
| `SESSION_SECRET` | 세션 쿠키 서명 키 (32자 이상 랜덤 문자열 필수) |
| `APP_BASE_URL` | Railway 배포 시 HTTPS URL (OAuth + Webhook 양쪽 적용) |
| `ANTHROPIC_API_KEY` | AI 리뷰 (없으면 기본값 fallback) |

---

## .codex/ 도구 설정

### 에이전트 (`.codex/agents/`)

| 에이전트 | 역할 |
|---------|------|
| `doc-consistency-reviewer` | 문서 변경 일관성 검토 (AGENTS.md 규칙·STATE.md 수치 대조) |
| `doc-impact-analyzer` | 문서 변경의 행동 영향 분석 |
| `doc-quality-reviewer` | 문서 품질 검토 (모호한 표현·중복·불완전한 예시 식별) |
| `pipeline-reviewer` | 파이프라인 코드 리뷰 (멱등성·오류 처리 검토) |
| `test-writer` | TDD 테스트 작성 (conftest 패턴, mock 전략 숙지) |

### 규칙 (`.codex/rules/`)

path-scoped 코딩 규칙 파일 8개. 해당 경로 파일 수정 시 자동 로드.

| 파일 | 적용 경로 |
|------|----------|
| `testing.md` | `tests/**`, `e2e/**`, `**/conftest.py`, `pytest.ini` |
| `db.md` | `alembic/**`, `src/models/**`, `src/database.py`, `src/repositories/**` |
| `pipeline.md` | `src/worker/**`, `src/analyzer/**`, `src/scorer/**` |
| `api.md` | `src/api/**`, `src/notifier/**`, `src/webhook/**`, `src/gate/**` |
| `security.md` | `src/auth/**`, `src/crypto.py`, `src/shared/log_safety.py` |
| `ui.md` | `src/templates/**`, `src/static/**`, `src/ui/**` |
| `i18n.md` | `src/i18n/**`, `src/middleware/locale.py` |
| `deploy.md` | `railway.toml`, `nixpacks.toml`, `requirements.txt` |

---

## 완료 시 필수 5-step

① 커밋 → ② PR 생성 (`gh pr create`) → ③ `git push` → ④ `docs/STATE.md` 수치 갱신 → ⑤ `docs/architecture.md` 동기화 (신규 파일 추가 시)

## 브랜치 명명 규칙

| 접두사 | 사용 시점 |
|--------|----------|
| `feat/` | 새 기능 구현 |
| `fix/` | 버그 수정 |
| `chore/` | 설정·문서·툴링 변경 |
| `docs/` | 문서 전용 변경 |
```

- [ ] **Step 2: 경로 오류 없는지 확인**

```bash
grep -n "\.Codex/" AGENTS.md
```

Expected: 출력 없음 (`.Codex/` 대문자 경로 0건)

- [ ] **Step 3: 줄 수 확인**

```bash
wc -l AGENTS.md
```

Expected: 100~140줄 범위

---

## Task 3-10 (Agent B): `.codex/rules/` 8개 파일 생성

**Files:**
- Create: `.codex/rules/testing.md`
- Create: `.codex/rules/db.md`
- Create: `.codex/rules/pipeline.md`
- Create: `.codex/rules/api.md`
- Create: `.codex/rules/security.md`
- Create: `.codex/rules/ui.md`
- Create: `.codex/rules/i18n.md`
- Create: `.codex/rules/deploy.md`

- [ ] **Step 1: rules 디렉터리 생성**

```bash
mkdir -p .codex/rules
```

### Task 3: `.codex/rules/testing.md`

- [ ] **Step 2: testing.md 작성**

```markdown
---
description: Test 작성·실행 시 적용되는 SCAManager 코딩 규칙 (Codex용 — path-scoped)
paths:
  - "tests/**"
  - "e2e/**"
  - "**/conftest.py"
  - "pytest.ini"
---

# 테스트 규칙 (Codex)

## 환경 + 격리

- `asyncio_mode = auto` 필수 (`pytest.ini` 에 이미 설정됨 — 수정 금지)
- E2E는 `e2e/` 최상위 디렉터리 — `tests/` 아래 배치 금지
- 🔴 `e2e/`와 `tests/integration/` 동시 실행 금지 → `make test-e2e` 분리 실행

## conftest.py 패턴

```python
# src 모듈 임포트 전 환경변수 주입 필수
# Must inject env vars before importing src modules
import os
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:test")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123456")
```

## Mock + Fixture 패턴

- `require_login` 우회: `app.dependency_overrides[require_login] = lambda: _test_user`
- Mock `side_effect` 에서 원본 mock 호출 금지 (재귀 발생) — 캡처만 하고 `return None`
- `_webhook_secret_cache`: `tests/conftest.py` 의 `_clear_webhook_secret_cache` autouse fixture 자동 클리어
- `SessionLocal` Mock 은 ORM 속성 오류 미감지 — 핵심 라우트에 실 DB 테스트 병행 필수

## 주의사항

- `func.count/avg/min/max` 호출 시 `# pylint: disable=not-callable` 인라인 주석 필수
- 기존 hot-path 함수 시그니처 변경 금지 (`find_by_full_name` 등) — 신규 함수로 분리
- 🔴 TDD Red 단계에서 "기존 테스트가 왜 통과하는가" 자문 의무 (fixture 우회 가능성 확인)

## pylint R0914 결정 트리

1. 신규 함수 작성: 헬퍼 추출 default
2. 기존 함수 시그니처 확장: `# pylint: disable=too-many-locals` + 사유 주석
```

### Task 4: `.codex/rules/db.md`

- [ ] **Step 3: db.md 작성**

```markdown
---
description: DB / 마이그레이션 작업 시 적용되는 SCAManager 코딩 규칙 (Codex용 — path-scoped)
paths:
  - "alembic/**"
  - "src/models/**"
  - "src/database.py"
  - "src/repositories/**"
---

# DB / 마이그레이션 규칙 (Codex)

- 🔴 **ORM 컬럼 추가 시 마이그레이션 필수**: `models/*.py` 에 `Column(...)` 추가 후 반드시 `make revision m="설명"` 실행. 단위 테스트(in-memory SQLite)는 마이그레이션 없이도 통과하지만, 운영 DB에는 컬럼이 없어 500 에러 발생.
- 🔴 **`batch_alter_table` 금지**: PostgreSQL 에서 `op.create_unique_constraint('이름', '테이블', ['컬럼'])` 직접 사용.
- **dialect 분기**: `from src.shared.alembic_dialect import is_postgresql; if not is_postgresql(op.get_bind()): return`
- **DB 인덱스 이중 정의**: `models/*.py` 의 `__table_args__ = (Index(...),)` + `alembic/versions/` 의 `op.create_index(...)` 양쪽 모두 필수.
- **FK ondelete CASCADE**: `analyses.id` 참조 child 4종 모두 CASCADE — 신규 child FK 추가 시 동일.
- **DB 세션**: `get_current_user()` 는 `db.expunge(user)` 후 반환 — 관계 lazy-load 사용 금지.
- **ThreadPoolExecutor**: `with` 문 금지 (shutdown hang) — `try/finally` + `executor.shutdown(wait=False)`.
- **`(data.get("key") or {}).get(...)` 패턴**: GitHub 페이로드의 None-able 키 접근 시 `or {}` 정규화 필수.
```

### Task 5: `.codex/rules/pipeline.md`

- [ ] **Step 4: pipeline.md 작성**

```markdown
---
description: 파이프라인 / 비즈니스 로직 작업 시 적용되는 SCAManager 코딩 규칙 (Codex용 — path-scoped)
paths:
  - "src/worker/pipeline.py"
  - "src/analyzer/**"
  - "src/scorer/**"
  - "src/webhook/**"
  - "src/gate/**"
---

# 파이프라인 / 비즈니스 로직 규칙 (Codex)

- **멱등성**: `run_analysis_pipeline` 은 commit SHA 로 중복 체크 — 같은 SHA 는 재분석 건너뜀.
- **PR action 필터링**: `pull_request` 이벤트 중 `opened`/`synchronize`/`reopened` 만 처리.
- **None-able 키 정규화**: `(data.get("head_commit") or {}).get(...)` 패턴 필수 (브랜치 삭제 push 대응).
- **Analyzer Registry**: 신규 도구 추가 시 3단계 — ① `tools/` 클래스 + `register()` ② `analyze_file()` import ③ `SUPPORTED_LANGUAGES` 선언.
- **category 기반 점수**: `AnalysisIssue.category` ("code_quality"|"security") 기준. tool 이름 무관.
- **봇 PR 루프 방지**: `pr_head_ref` 가 `_BOT_PR_PREFIXES` (`claude-fix/`, `bot/`, `renovate/`, `dependabot/`) 시작 시 `create_issue` 건너뜀.
- **AI 리뷰 JSON 파싱**: `re.search` 로 코드 블록 내 JSON 만 추출 (설명 텍스트 앞에 붙을 수 있음).
- **GateDecision upsert**: `save_gate_decision()` 은 동일 `analysis_id` 존재 시 UPDATE, 없으면 INSERT.
- **build_analysis_result_dict**: `src/worker/pipeline.py` 모듈 레벨 함수 — `score`·`grade` 필드 포함. pipeline 과 hook.py 양쪽에서 사용.
```

### Task 6: `.codex/rules/api.md`

- [ ] **Step 5: api.md 작성**

```markdown
---
description: API / 알림 채널 작업 시 적용되는 SCAManager 코딩 규칙 (Codex용 — path-scoped)
paths:
  - "src/api/**"
  - "src/notifier/**"
  - "src/webhook/**"
  - "src/gate/**"
  - "src/main.py"
---

# API / 알림 채널 규칙 (Codex)

- **keyword-only 강제**: 모든 `send_*` notifier 함수와 `run_gate_check()` 는 `def fn(*, arg1, arg2)` 형태 — 테스트에서 키워드 인자로 호출 필수.
- **RepoConfig 필드명**: `approve_mode` (구 `gate_mode`), `approve_threshold` (구 `auto_approve_threshold`) — 구 필드명 사용 시 AttributeError.
- **알림 채널 추가 체크리스트**: `RepoConfig` ORM → `RepoConfigData` dataclass → `RepoConfigUpdate` API body → UI 폼 4곳 동기화 필수.
- **GRADE 상수 단일 출처**: `src/constants.py` — 로컬 재정의 금지.
- **ChangedFile / github_api_headers**: `src/github_client/models.py` / `src/github_client/helpers.py` 사용.
- **http_client 싱글톤**: 신뢰 API 는 `src/shared/http_client.py::get_http_client()`, 외부 untrusted URL 은 `src/notifier/_http.py::build_safe_client()`. `async with httpx.AsyncClient()` 매번 생성 금지.
- **알림 독립성**: `asyncio.gather(return_exceptions=True)` — 한 채널 실패해도 나머지 정상 전송.
- **Webhook 서명 실패**: `HTTPException(401)` 반환 — 200 OK 금지.
- **FastAPI Annotated 패턴**: `Annotated[Type, Depends(...)]` / `Annotated[str | None, Header()] = None` 형식.
- **get_repo_or_404**: `src/api/deps.py::get_repo_or_404(repo_name, db)` 사용.
```

### Task 7: `.codex/rules/security.md`

- [ ] **Step 6: security.md 작성**

```markdown
---
description: 보안 작업 시 적용되는 SCAManager 코딩 규칙 (Codex용 — path-scoped)
paths:
  - "src/auth/**"
  - "src/crypto.py"
  - "src/shared/log_safety.py"
  - "src/api/auth.py"
  - "src/webhook/validator.py"
---

# 보안 규칙 (Codex)

- 🔴 **hook_token 비교**: `hmac.compare_digest(config.hook_token or "", token)` — `!=` 연산자 금지 (타이밍 공격 취약).
- 🔴 **`/health` 내부 상태 미노출**: DB 연결 정보 등 내부 상태 추가 금지.
- **GitHub Access Token**: `user.plaintext_token` 사용 (`src/crypto.py` 자동 복호화) — `user.github_access_token` 직접 사용 금지.
- **Jinja2 autoescape**: `.html` 파일 자동 이스케이프 — `| safe` 필터 사용 금지. notifier HTML 은 `html.escape()` 직접 적용.
- **로그 인젝션 방어**: `src/shared/log_safety.py::sanitize_for_log(value)` — user-controlled 입력을 logger 에 전달 전 반드시 경유.
- **URL Path 방어**: `src/github_client/repos.py::_repo_path(full_name)` 으로 `urllib.parse.quote(safe='/')` 적용.
- **SonarCloud FP suppress**: `sonar-project.properties` 예외 추가 또는 `# NOSONAR <ruleKey> — 이유` 주석.
```

### Task 8: `.codex/rules/ui.md`

- [ ] **Step 7: ui.md 작성**

```markdown
---
description: UI / 템플릿 작업 시 적용되는 SCAManager 코딩 규칙 (Codex용 — path-scoped)
paths:
  - "src/templates/**"
  - "src/static/**"
  - "src/ui/**"
---

# UI / 템플릿 규칙 (Codex)

- **4-테마 지원**: dark / light / glass / claude-dark. 신규 CSS 변수는 `var(--*)` 경유, `#hex` 직접 사용 금지.
- 🔴 **환각 토큰 금지**: 정의되지 않은 CSS 변수 참조 시 브라우저 invalid → 시각 깨짐. 신규 alias 는 `base.html` `:root` 블록에 흡수.
- 🔴 **모바일 클릭 영역 ≥44px**: `@media (max-width: 768px)` 분기에서 인터랙티브 요소 `min-height: 44px` 필수.
- **safe-area-inset**: sticky/fixed 요소 (`nav`, `.save-bar`) 에 `padding: max(*, env(safe-area-inset-*))` 패턴.
- **Chart.js**: `src/static/vendor/chart.umd.min.js` 로컬 호스팅 (CDN 금지). 테마 전환 시 `buildChart()` 재호출.
- **색 semantic 토큰**: `--success` / `--warning` / `--danger` 3종 사용. hex 직접 사용 금지.
- **analysis_detail context**: `current_user` 반드시 포함 — 누락 시 nav 사용자명 미표시.
- **Telegram HTML**: `parse_mode: "HTML"` 사용 — 동적 콘텐츠에 `html.escape()` 필수.
- **Chart.js CSS 변수**: `getComputedStyle(document.documentElement).getPropertyValue('--grade-a')` 동적 추출 후 Chart 옵션 주입.
```

### Task 9: `.codex/rules/i18n.md`

- [ ] **Step 8: i18n.md 작성**

```markdown
---
description: 다국어 / i18n 작업 시 적용되는 SCAManager 코딩 규칙 (Codex용 — path-scoped)
paths:
  - "src/i18n/**"
  - "src/middleware/locale.py"
  - "src/notifier/_language.py"
  - "src/analyzer/pure/review_guides/**"
---

# 다국어 / i18n 규칙 (Codex)

- **3 언어 지원**: en / ko / ja. 번역 파일 = `src/i18n/translations/{en,ko,ja}.json`.
- **새 키 추가**: 3 언어 모두 동시 추가 의무 (en 누락 시 fallback 깨짐 — 운영 사고).
- 🔴 **Jinja2 i18n 필터**: `{{ 'key.path' | i18n_args(locale | default('ko'), arg=value) }}` — `locale` 부재 시 `'ko'` default fallback 의무.
- **5단계 locale 감지 순서**: Cookie (`locale`) > Accept-Language > User.preferred_language > settings.default_locale > "en".
- **알림 언어 fallback**: User.preferred_language → RepoConfig.notification_language → settings.default_locale → "en" 4-tier.
- **`FULL`/`COMPACT` 변수명 변경 금지**: `review_guides/` Tier1~3 의 영문 default — 50+ 사용처 회귀.
- **kill-switch**: `is_disabled("I18N")` 으로 i18n 전체 비활성화 가능 (사이클 78 페어).
```

### Task 10: `.codex/rules/deploy.md`

- [ ] **Step 9: deploy.md 작성**

```markdown
---
description: 배포 / 환경 설정 작업 시 적용되는 SCAManager 코딩 규칙 (Codex용 — path-scoped)
paths:
  - "railway.toml"
  - "nixpacks.toml"
  - "requirements.txt"
  - "requirements-dev.txt"
  - ".env.example"
  - "Procfile"
  - "alembic.ini"
---

# 배포 규칙 (Codex)

> 상세 절차: [`docs/runbooks/railway.md`](../../docs/runbooks/railway.md)

- 🔴 **NIXPACKS npm run build 억제**: `railway.toml` 의 `buildCommand` 최상위 오버라이드만 억제 가능.
- 🔴 **NIXPACKS nixPkgs 오버라이드 함정**: `nixpacks.toml` 에 `nixPkgs` 명시 시 Python provider nix 자동 설치 **완전 교체**. Python+Node.js 공존 = `aptPkgs = ["nodejs", "npm"]` 사용.
- **APP_BASE_URL**: Railway 필수 — OAuth redirect_uri + GitHub Webhook URL 양쪽 HTTPS 강제.
- **Railway 빌드 검증**: `git push` 성공 ≠ Railway 빌드 성공. `railway.toml`/`nixpacks.toml`/`requirements.txt` 변경 후 대시보드 빌드 로그 직접 확인.
- **빌드 실패 시 로그 우선**: 즉각 수정 PR 금지 — 전체 빌드 로그(실패 구간 위아래 30줄) 먼저 확인.
- **requirements.txt 분리**: 프로덕션 = `requirements.txt` / 개발 = `requirements-dev.txt`. `pytest`/`playwright` 는 dev only.
- **slither + solc**: `railway.toml` buildCommand 에 `solc-select install 0.8.20 && solc-select use 0.8.20` 체인.
- **postgres:// → postgresql://**: `config.py` 에서 자동 변환됨.
```

- [ ] **Step 10: 8개 파일 생성 확인**

```bash
ls .codex/rules/
```

Expected:
```
api.md  db.md  deploy.md  i18n.md  pipeline.md  security.md  testing.md  ui.md
```

---

## Task 11 (Agent C): `.codex/agents/` 정합성 검증·수정

**Files:**
- Modify (필요 시): `.codex/agents/*.toml`

- [ ] **Step 1: 현재 에이전트 설명에서 AGENTS.md 참조 확인**

```bash
grep -n "AGENTS.md\|CLAUDE.md\|\.Codex\|\.codex" .codex/agents/*.toml
```

Expected: `CLAUDE.md` 참조 없음, `.Codex/` (대문자) 참조 없음

- [ ] **Step 2: doc-consistency-reviewer 설명 업데이트**

`.codex/agents/doc-consistency-reviewer.toml` 의 description 줄에서 `AGENTS.md` 를 `AGENTS.md (에이전트 설정) 또는 CLAUDE.md (정책)` 로 수정:

현재:
```toml
description = "SCAManager 문서 일관성 검토 에이전트. 변경 내용이 AGENTS.md 규칙·STATE.md 수치·다른 문서와 충돌하는지 교차 검증한다."
```

수정 후:
```toml
description = "SCAManager 문서 일관성 검토 에이전트. 변경 내용이 AGENTS.md (Codex 설정)·CLAUDE.md (프로젝트 정책)·STATE.md 수치·다른 문서와 충돌하는지 교차 검증한다."
```

- [ ] **Step 3: doc-impact-analyzer 설명 업데이트**

`.codex/agents/doc-impact-analyzer.toml` 의 description 줄:

현재:
```toml
description = "SCAManager 문서 변경의 행동 영향 분석 에이전트. 문서 수정이 Codex의 작업 행동을 의도하지 않게 바꾸는지 검토한다."
```

수정 후:
```toml
description = "SCAManager 문서 변경의 행동 영향 분석 에이전트. 문서 수정이 Codex 또는 Claude의 작업 행동을 의도하지 않게 바꾸는지 검토한다."
```

- [ ] **Step 4: `.claude/agents/` 대비 누락 에이전트 확인**

```bash
echo "=== .claude/agents/ ===" && ls .claude/agents/
echo "=== .codex/agents/ ===" && ls .codex/agents/
```

Expected: 파일명 기준 5개 일치 (확장자만 다름: .md vs .toml)

---

## Task 12: 최종 검증

- [ ] **Step 1: `.Codex/` 대문자 경로 오류 전수 검사**

```bash
grep -rn "\.Codex/" AGENTS.md .codex/ 2>/dev/null
```

Expected: 출력 없음 (0건)

- [ ] **Step 2: 깨진 파일 참조 확인**

```bash
# AGENTS.md 내 .codex/ 참조가 실제 존재하는지 확인
grep -n "\.codex/" AGENTS.md
ls .codex/rules/
ls .codex/agents/
```

Expected: AGENTS.md 의 `.codex/` 참조 경로가 실제 디렉터리에 존재

- [ ] **Step 3: rules frontmatter paths 확인**

```bash
grep -h "paths:" .codex/rules/*.md
```

Expected: 8개 파일 모두 `paths:` 섹션 포함

---

## Task 13: 커밋 + PR

- [ ] **Step 1: 변경 파일 확인**

```bash
git status
git diff --stat
```

Expected: AGENTS.md (수정), .codex/rules/ (8개 신설), .codex/agents/ (수정)

- [ ] **Step 2: 스테이징 + 커밋**

```bash
git add AGENTS.md .codex/rules/ .codex/agents/
git commit -m "$(cat <<'EOF'
chore(codex-docs): AGENTS.md 재작성 + .codex/rules/ 8개 신설

- AGENTS.md: 439줄→~120줄 재작성 (Codex 역할 정의 + 핵심 4규칙 + CLAUDE.md 참조 포인터)
- .codex/rules/: path-scoped 코딩 규칙 8개 신설 (testing/db/pipeline/api/security/ui/i18n/deploy)
- .codex/agents/: doc-consistency/impact-analyzer 설명 업데이트 (CLAUDE.md 참조 추가)
- .Codex/ 대문자 경로 오류 전수 제거

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: 원격 push**

```bash
git push -u origin chore/codex-docs-setup
```

- [ ] **Step 4: PR 생성 URL 안내**

```
https://github.com/xzawed/SCAManager/compare/chore/codex-docs-setup
```

🔍 **사용자 검증 필요**:
1. AGENTS.md 내용이 Codex 역할(반복 구현)에 적합한지 확인
2. `.codex/rules/` 8개 파일이 해당 영역 작업 시 자동 로드되는지 확인
3. CLAUDE.md 정책 참조 포인터가 명확한지 확인

---

## 자가 검토 (Spec Coverage)

| 설계 요구사항 | 구현 태스크 |
|-------------|-----------|
| AGENTS.md 재작성 (~120줄) | Task 2 |
| `.Codex/` 경로 오류 수정 | Task 2 Step 2 |
| Codex 역할 정의 | Task 2 (Codex 역할 섹션) |
| CLAUDE.md 참조 포인터 | Task 2 (전체 협업 정책 17개 참조) |
| `.codex/rules/` 8개 신설 | Task 3-10 |
| `.codex/agents/` 정합성 | Task 11 |
| 최종 검증 | Task 12 |
| PR 생성 | Task 13 |
