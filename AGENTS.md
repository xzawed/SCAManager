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
| `doc-consistency-reviewer` | 문서 변경 일관성 검토 (AGENTS.md·CLAUDE.md·STATE.md 수치 대조) |
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

**예외 없음** — `.codex/` 내부 파일, `AGENTS.md`, `docs/` 변경도 모두 브랜치 + PR 방식.
