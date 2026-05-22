# SCAManager

> **문서 작성 원칙**: 이 프로젝트의 모든 문서는 Claude가 가장 읽기 쉽고 이해하기 편한 구조로 작성한다.
> 새 문서를 작성하거나 기존 문서를 수정할 때 이 원칙을 반드시 따른다.

> **코드 주석 원칙 (이중 언어)**: 모든 코드 주석은 **한국어와 영어를 병행**하여 작성한다.
> 한국어를 먼저 쓰고, 바로 다음 줄에 영어를 추가한다.
> 신규 코드 작성 시 즉시 적용하고, 기존 파일은 해당 파일을 수정할 때 함께 갱신한다.
> 예외: `# TODO`, `# FIXME`, `# type: ignore` 등 단어 하나짜리 표준 태그는 영어 단독 사용 허용.
>
> ```python
> # 레이트 리밋 초과 시 재시도
> # Retry on rate limit exceeded
>
> # 같은 SHA가 이미 분석된 경우 건너뜀 (멱등성 보장)
> # Skip if the same SHA was already analyzed (idempotency guard)
> ```

GitHub Push/PR 이벤트 시 정적 분석 + AI 코드 리뷰를 자동 수행하고, 점수와 개선사항을 Telegram·GitHub PR Comment·Discord·Slack·Email·n8n으로 전달하며, 점수 기반 PR 자동/반자동 Gate(Approve + 자동 Merge 포함)와 웹 대시보드를 제공하는 서비스. `git push` 시 Claude Code CLI 기반 자동 코드리뷰(pre-push hook)도 지원한다.

---

## 🧭 이 문서 탐색 가이드

| 상황 | 바로 가기 |
|------|----------|
| **작업 착수 전 (항상 30초)** | → [작업 시작 전 필수 체크리스트](#작업-시작-전-필수-체크리스트-매-작업마다) |
| **src/ 수정 후** | → [필수 원칙 — Hook 신뢰](#필수-원칙) |
| **Phase 완료 직전** | → [필수 원칙 — 완료 6-step · docs/architecture.md 동기화](#필수-원칙) |
| **ORM 컬럼 추가 시** | → [DB/마이그레이션 주의사항](.claude/rules/db.md) |
| **새 파일 추가 시** | → [CLAUDE.md 아키텍처 동기화 체크리스트](#필수-원칙) |
| **아키텍처 파악** | → [src/ 트리](#아키텍처) · [핵심 데이터 흐름](docs/architecture.md#핵심-데이터-흐름) |
| **규칙 전체 열람** | → [주의사항 카테고리별](#주의사항-카테고리별) |

> **🔴 가장 빈번하게 놓치는 규칙 3가지**
> 1. ORM 컬럼 추가 후 `make revision` 마이그레이션 파일 미생성 → 운영 500 에러 (DB/마이그레이션 참조)
> 2. Phase 완료 후 `docs/architecture.md` 동기화 누락 → 다음 Claude 세션 혼란 (필수 원칙 참조)
> 3. 경로 없이 `python -m pytest` 실행 시 e2e 혼입 → 446건 false failure (testpaths=tests로 방어됨)

---

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
| `make test-fast` | 빠른 단위 테스트만 (`tests/integration/` 제외, `-m "not slow"`) |
| `make test-slow` | 통합 테스트만 (`tests/integration/` — 실 subprocess 실행) |
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

- **src/ 트리 + 모듈 역할**: [`docs/architecture.md`](docs/architecture.md)
- **핵심 데이터 흐름** (Webhook → pipeline → notify → gate): [`docs/architecture.md#핵심-데이터-흐름`](docs/architecture.md#핵심-데이터-흐름)
- **점수 체계** (배점 + 등급 + AI 스케일링): [`docs/reference/scoring.md`](docs/reference/scoring.md)

> 🔴 **신규 파일 추가 시 [`docs/architecture.md`](docs/architecture.md) 동기화 의무** — src/ 트리 항목 + 핵심 데이터 흐름 갱신.

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
| `DISABLE_PROMPT_CACHE` | Anthropic prompt caching (5분 ephemeral) opt-out — `1` 시 비활성 (Phase 3 PR 1, default `0`) |

전체 환경변수 목록: `docs/reference/env-vars.md`

## Railway 배포 + 운영 DB 환경

- **상세 운영 가이드**: [`docs/runbooks/railway.md`](docs/runbooks/railway.md)
- **운영 DB**: Supabase + 온프레미스 PostgreSQL 이중 setup (Railway 도 호환). 모든 환경 동일 alembic 마이그레이션 적용.
- **Railway 필수 환경변수**: `DATABASE_URL` (PostgreSQL 플러그인 자동) + `APP_BASE_URL` (HTTPS, OAuth/Webhook 강제) + 나머지 [`docs/reference/env-vars.md`](docs/reference/env-vars.md) 참조.
- **헬스체크**: `GET /health` → `{"status":"ok"}`. 내부 상태 미노출 (정보 노출 방지).

## Agent 작업 규칙

모든 AI 에이전트(Claude Code 및 서브에이전트)는 SCAManager 작업 시 아래 규칙을 **반드시** 따른다.
`.claude/` 디렉토리에 정의된 스킬과 에이전트는 선택이 아닌 의무적 도구다.

> **📚 협업 회고 + 사용자 합의 정책**: 2026-05-01 회고 결과 사용자가 합의한 협업 정책 5건은 [docs/reports/2026-05-01-collaboration-retrospective.md](docs/reports/2026-05-01-collaboration-retrospective.md) 참조. 다음 세션의 Claude 는 본 정책을 default 로 적용. 핵심 5건은 아래 "사용자 협업 정책 (2026-05-01 합의)" 섹션 명시.

### 사용자 협업 정책 (2026-05-01 합의)

#### 정책 1: 옵션 제시 시 **장단점 명시 의무** (반대 X, 정보 ○)

사용자 발화: *"반대 하기를 원하기 보다 각각의 장단점을 알려주시면 권장을 한다 하더라도 제가 판단하는데 도움이 될거라 생각합니다."*

**권장 default 표 형식**: `| 옵션 | 장점 | 단점 | 위험 | 권장 시점 |` 5컬럼 + 권장 표시 (★) 보조 + "고려했으나 제시 안 한 안" 1줄 (추론 추적성). 상세 예시: [docs/policies/history.md#정책-1-진화](docs/policies/history.md#정책-1-진화).

🔴 **진화 default 요약** — (1) "전부다" 일괄 결정 시 검토 깊이 1줄 자가 보고 요청 의무 (사이클 83). (2) 다중 PR 빠른 진행 신호 ≥ 10회 = 동일 의무 (사이클 84). 예외: 단순 머지 보고 + 옵션 표 결정. 상세: [docs/policies/history.md#정책-1-진화](docs/policies/history.md#정책-1-진화).

🔴 **정책 1 진화 회귀 가드 (사이클 86 Q4 — 사용자 명시 결정)** — **자가 검증 의무**: Claude 가 일괄 결정 발화 직후 자가 보고 요청 누락 시 = **다음 응답에서 회복 의무** (자성 1줄 + 검토 깊이 사후 요청 + 자가 보고 1줄). 사이클 85 회고 P0 사례 = 본 회귀 가드 첫 적용. 회복 누락 시 = 다음 사이클 회고 §자성 명시 의무. 회복 패턴 예시: [docs/policies/history.md#정책-1-진화-회귀-가드](docs/policies/history.md#정책-1-진화-회귀-가드).

#### 정책 2: PR 본문 "🔍 사용자 검증 필요" 섹션 의무

**default**: 모든 PR 본문 §"🔍 사용자 검증 필요" 섹션 — 시각/운영 확인 항목 1~3개 명시 (Railway 배포 / 테마 토글 / 운영 사고 보고 등). "tests pass" 만 적기 금지. 템플릿 + 진화 (Phase 종료 일괄 회신 묶음) 상세: [docs/policies/active.md#정책-2](docs/policies/active.md#정책-2).

#### 정책 3: **자율 판단 결정의 사후 보고 의무**

위임받은 작업 ("권장 방향 진행", "GitHub 정리 수행" 등) 중 Claude 가 판단한 항목은 PR 본문 또는 응답 끝에 명시.

예: *"GitHub 정리 시 미매핑 PR 17건은 보류 결정했습니다 (역사 정리 가치 < 시간 부담). 이의 있으시면 알려주세요."*

#### 정책 4: **단언과 회귀 가드를 같은 PR 에 묶기**

"5-way sync 보존" 같은 단언은 회귀 가드 PR 과 동시 머지. 단언만 있고 가드 없으면 사고 시 책임 귀속 어려움.

#### 정책 5: **사이클 종료 신호 명시 + Phase 단계별 진행/종료 신호 분리**

"권장 진행" 시작된 작업의 종료 시점 모호. 사이클 끝마다 Claude 가 명시 확인:
- "다음 단계 진행할까요?" (사용자 신호 대기)
- 사용자 신호 ("여기까지 합시다" / "오늘은 그만") 시 즉시 종료

**Phase 단계별 진행/종료 신호 분리 의무 (사이클 75 진화 — 사이클 74 사고 학습)**: 사용자가 "A+B+C+D 모두 진행" 같은 다중 단계 발화 시 Claude 의 사이클 종료 (예: 회고 진입) 시점에 **잔여 단계 (예: C/D) 진행 신호 명시 회신 의무**. 사이클 74 사례 = Phase 2-A (#247) + Phase 2-B (#248) 머지 후 회고 진입 → Phase 2-C/D 진행 의도 미확인 = 사용자 발화와 Claude 종료 신호 불일치. **default 적용**: 다중 단계 발화 후 일부 단계만 진행하고 사이클 종료 시 = "Phase X-Y 완료. Phase X-Z 잔여 — 다음 사이클 진입 시 결정 회신 의무" 1줄 명시.

🔴 **정책 5 cross-reference 강화 (사이클 83)** — Phase 종료 시점 의무는 **정책 2/5/8/11 4 정책에 분산** (인지 부담 ↑ 위험). **default 적용**: Phase 종료 시점 진입 시 4 정책 cross-reference 자가 검토 의무 (한 정책만 적용 시 다른 3 정책 위반 가능). Claude 가 PR commit body §"Phase 종료 처리" 섹션에 적용 정책 명시 권장. 상세: [docs/policies/active.md#정책-5-phase-종료-cross-reference](docs/policies/active.md#정책-5-phase-종료-cross-reference).

🔴 **정책 5 NEW-P0-N 예외 명시 (사이클 83 — 사이클 78~82 회고 Tier B-5 사용자 OK Q5)** — **운영 사고 차단 영역 (NEW-P0-N) 은 Phase 단계별 보류 default 적용 X**: 사이클 78 PR 2 (NEW-P0-1 = Telegram 봇 차단 silent skip) = 정책 5 강화 default 적용 결과 = "PR 2/3/4 = 머지 대기 (사용자 영역)" 명시 → 4 사이클 누적 사용자 머지 대기 → 운영 사고 위험 누적 (메모리 `feedback-stale-blocker-policy.md` 2.5배 자기 위반).

**default 적용**: NEW-P0-N (5+1 cross-verify 신규 발견 P0) 영역 = **매 사이클 진행 신호 회신 의무** (사용자 명시 결정 받기 전까지). Phase 단계별 보류 default 적용 X. 정책 9 완화 default (회신 부재 시 자율 판단 보고로 대체 OK) **미적용 영역**.

#### 정책 6 (보조): **다중 에이전트 디스패치 시 `line:span` 인용 의무 명시 + 정책 본문/메모리 본문 작성 시 `grep -n` 실측 의무**

본 사이클 검증 — 인용 없는 보고는 false-positive 80% 발생. 모든 에이전트 프롬프트에 강제 조건으로 명시.

**정책 본문/메모리 본문 작성 시 line:span 인용 = `grep -n` 실측 의무 (사이클 75 진화 — 사이클 72 정책 16 line:span drift 학습)**: 정책 본문 또는 메모리 본문 작성 시 `src/<file>:<line>` 형식 인용은 **`grep -n` 명령 실측 후 작성 의무**. 추정 line 번호 작성 금지 (자연 drift 가능 — 사이클 72 정책 16 본문의 `ai_review.py:79` / `dashboard_service.py:546` 가 사이클 74 코드 추가로 89/571 drift 사례). **default 적용**: line:span 인용 시 함께 commit hash 명시 권장 (`ai_review.py:89 (#218)` 형식 — 자연 drift 추적 가능).

#### 정책 7: **모든 작업은 PR 단위 (main 직접 작업 지양)**

사용자 발화 (2026-05-01): *"작업 단위를 PR 로 수행해주시길 권장합니다. 가급적 main 에 직접 작업은 지양해 주셨으면 합니다."*

**default 작업 흐름** (예외 없음):
1. `git checkout main && git pull origin main` — 최신 동기화
2. `git checkout -b <type>/<scope>-<short-desc>` — 새 브랜치 생성
3. 작업 + commit
4. `git push -u origin <branch>` — 원격 push
5. **PR 직접 생성** (`gh pr create`) — 사용자 머지

**금지 행동**:
- ❌ `git push origin main` (main 에 직접 push)
- ❌ `git commit` 후 `main` 브랜치 그대로 두고 다음 작업 진행
- ❌ "사소한 docs 정정이라 main 에 직접" 같은 예외 적용

**예외 0**: 신규 파일 추가 / 단순 정정 / docs only / typo 수정 모두 PR 단위. 예외 만들면 `.claude/` 정책 일관성 깨짐.

**브랜치 명명 규칙**: [작업 시작 전 필수 체크리스트](#작업-시작-전-필수-체크리스트-매-작업마다) 표 참조.

**위반 시 회복**: [docs/policies/active.md#정책-7](docs/policies/active.md#정책-7) 참조.

#### 정책 8: **회고는 항상 다중 에이전트로 깊게 진행 의무**

사용자 발화: *"가급적 회고도 모든 에이전트가 깊게 생각하여 진행했으면 합니다."*

**default 회고 패턴** (Claude 단독 회고 금지):
- **최소 4~5 에이전트 병렬 디스패치** (단일 메시지에 동시 tool_use)
- **관점 분리** — 에이전트별 비중복 도메인 배정 (5종 예시: [docs/policies/active.md#정책-8-doc-audit-agent-domain](docs/policies/active.md#정책-8-doc-audit-agent-domain))
- **각 에이전트 프롬프트 강제 조건**:
  - `self-contained` (다른 에이전트 결과 의존 0 — 병렬성 보호)
  - `line:span 인용 의무` (정책 6 — 환각 보고 80% 차단)
  - 출력 포맷 강제 (P0/P1/P2 분류 또는 표 형식)
  - "회피해야 할 false-positive 사례" 사전 명시 (가능 시)

**금지**:
- ❌ "간단한 회고는 Claude 단독으로" 같은 예외
- ❌ 1~2 에이전트만 디스패치 (관점 부족)

**cross-verify 단계 (2차) 의무 — 사이클 64 학습 (2026-05-04)**:
- 1차 5 에이전트 결과 받은 후 별도 cross-verify 에이전트 1건 디스패치 (= 5+1 = 6 패턴)
- ❌ cross-verify 6차 에이전트로 `doc-consistency-reviewer` 사용 금지 (사이클 64: 회고 cross-verify scope 거절) / ✅ `general-purpose` 또는 task-specific specialist — 단, 문서 diff 일관성 검토 단독 목적의 호출은 허용. 상세: [history.md#정책-8-진화](docs/policies/history.md#정책-8-진화)
- 🔴 **cross-verify 생략 정량 기준 (사이클 69 cross-verify 식별)**: "양과 깊이 충분" 의 정량 기준 = (1) 1차 5 에이전트 P0 합계 ≥ 8건 + (2) 관점 5종 모두 P0 1건 이상 식별 + (3) 사용자 빠른 진행 신호 명시 ("회고 이후 다음 작업" / "바로 진행" 등). **3 조건 모두 충족 시만 생략 OK**. Claude 자가 판단 X — 사용자 명시 신호 의무. 미충족 시 cross-verify (general-purpose) 강제.
- 🔴 **cross-verify 생략 PR 본문 대조 표 default (사이클 87)**: 6차 생략 시 PR 본문 §"cross-verify 생략 사유" 에 사이클 69 정량 3 조건 대조 표 default. 3 조건 모두 ✅ 시만 생략 OK. 1 조건이라도 ❌ 시 cross-verify 강제. 표 형식 상세: [docs/policies/history.md#정책-8-진화](docs/policies/history.md#정책-8-진화).

🔴 **단일 관점 회고 (사이클 75 진화)**: 관점 1~5 중 1개 단독 회고 = 5+1 패턴 미적용 (Claude 직접 작성 default). default = 5+1 진행 + 정량 기준 충족 시 생략. 상세: [docs/policies/history.md#정책-8-진화](docs/policies/history.md#정책-8-진화).

🔴 **정책 8 진화 default 요약** (사이클 83~84, 92):
- **(1) 단일 작업일 5+1 dispatch ≥ 5회 = 사용자 사전 확인 의무** (사이클 83). 사용자 명시 신호 시 면제 OK. 정책 16 5번 원칙 (토큰 비용 효율) 페어.
- **(1) 강화** (사이클 84): **dispatch 횟수** vs **agent invocation** 구분 — dispatch 기준 default + 누적 invocation ≥ 30 시 동등 사전 확인 의무.
- **(2) cross-verify ROI commit body 정량 명시 의무** — false-positive 차단 N건 / 신규 발견 N건 / Tier A 정정 N건 (정책 6 페어).
- **(3) cross-verify Round 2 도메인 카운트 = `pytest --collect-only -q` 실측 의무** (사이클 92). 추정 카운트 보고 = 자동 false-positive 처리. 사이클 89 Round 1 추정 부정확 사례 (middleware 5/실측 17, worker 22/실측 78, github_client 15/실측 74) 학습 페어. 정책 6 (line:span `grep -n` 실측 — 정적 line 영역) 와 시점·대상 차별 (정책 8 진화 = 동적 테스트 분포 카운트).

상세: [docs/policies/history.md#정책-8-진화](docs/policies/history.md#정책-8-진화).
#### 정책 9: **회고 후 반드시 Claude 자유 발언 시간 의무**

사용자 발화: *"회고 이후에 반드시 바라는 점 원하는 것 수정이 필요한 부분 등 자유롭게 말하는 시간도 있었으면 합니다."*

**default 발언 흐름** (회고 종합 보고 직후 자동 진행) — 4 섹션 구성:
1. **바라는 점** (정보 비대칭 / 시범 운영 / 권장안 검토 패턴)
2. **Claude 가 자성할 점** (본 사이클 잘못/누락 + 다음 사이클 개선 약속)
3. **필요한 부분** (운영 데이터 / 결정 입력 부족)
4. **수정이 필요한 내용** (구체적 제안 표 — `| 영역 | 제안 |`)

**원칙**: 솔직함 우선 + 자성/요청 균형 + 구체적 제안 (추상 발언 X) + 사용자 발화 인용 보존.

**Phase 종료 시 회고 질문 default** (사이클 64 회고 P1 학습): Claude 가 회고 자유 발언에 §"🔍 회고 질문 (사용자 회신 의무)" 1줄 추가 — "Phase 본 권장 default N건 중 다른 결정 했을 만한 항목 있었나?". 회신 패턴: `[x] 모두 OK / [!] N번 다시 검토 (사유) / [ ] 미수행`. 템플릿 상세: [docs/policies/active.md](docs/policies/active.md).

🔴 **정책 9 완화 (사이클 83 — 사이클 78~82 회고 P0 학습)**: 회신 부재 default = **자율 판단 보고 명시 시 회신 의무 면제 OK** (Claude 자율 진입 가능). **단, 미적용 영역 3종**: (a) 운영 사고 차단 영역 (NEW-P0-N — 정책 5 강화 페어) (b) destructive 작업 (브랜치 삭제 / DROP / DELETE — 정책 7/12 페어) (c) architecture/UX/데이터 모델 결정 (`feedback-architecture-decision-pre-confirm.md` High tier) — 본 3 영역은 사용자 명시 회신 의무 보존.

**금지**: 회고 후 자유 발언 생략 (사용자 명시 요청 영역) / "감사합니다" 의례만 / 정책 9 완화 default = "회고 질문 작성 의무 면제" 오해 (회고 질문 작성은 의무, 회신 부재만 대체 OK).

#### 정책 10: PR 직접 생성 의무 (URL 안내 X, 자동 생성 ○)

**default 6-step**: `git checkout main && pull` → `checkout -b <type>/<scope>` → 작업+commit → `push -u origin` → **PR 직접 생성** (gh pr create) → URL 보고.

🔴 **현재 SCAManager 환경**: gh CLI v2.89.0 설치 완료 + xzawed 계정 인증 완료 → **옵션 🅐 (gh pr create) default**.

**fix-up commit default**: 머지 전 CI fail / 회귀 = 동일 PR 브랜치 추가 commit (정책 7 강화 응집 단위). 머지 후 발견 = 별도 fix PR. PR body 템플릿 + 환경별 detail: [docs/policies/active.md#정책-10](docs/policies/active.md#정책-10).

#### 정책 11: **UI/시각 변경 PR 본문에 "Claude 시각 검증 불가" 의무 명시**

사용자 발화 (2026-05-02 Phase 1 회고): *"PR본문 검증의 경우 디테일한 검증은 없었습니다."* — Claude 가 만든 UI/시각 변경 (template, css, html 파일) 은 정적 코드만 검증 가능. 4-테마 (dark/light/pastel/catppuccin) × 모바일/데스크탑 8 조합 시각 정합성은 사용자 의무.

**default 의무**: `src/templates/*.html` / `src/static/**/*.css` / `base.html` `<style>` 블록 / 신규 시각 컴포넌트 변경 PR 작성 시 — PR 본문 최상단에 8 조합 체크리스트 삽입. 템플릿: [docs/policies/active.md#정책-11](docs/policies/active.md#정책-11)

**금지**: UI/시각 변경 PR 본문에 본 섹션 누락 후 "테스트 통과" 만 적기. 정적 테스트와 시각 검증의 비대칭 명시 의무.

**Phase 종료 시 누적 회신 의무 (사이클 64 학습)** — Phase 단위로 8 조합 체크리스트 PR 4 건 이상 누적 시 사용자 명시 회신 0 건 사례 (Phase 3 회고 §1 P1-7). 본 정책 11 ↔ 정책 2 진화 (Phase 종료 일괄 회신 묶음) 페어 적용 default. Phase 종료 시 Claude 가 누적 8 조합 체크리스트 단일 회신 표 묶음 + 사용자 명시 OK/NG/미수행 회신 요청 의무. 회신 부재 시 다음 사이클 진입 보류 또는 자율 판단 보고 (정책 3 강화).

🔴 **정책 2 진화**: Phase 종료 일괄 회신 묶음 + sync PR pytest 실측 1줄 의무. **정책 3 진화**: 자율 판단 보고 최상단 + ⚠️ 마커 (정량 5 조건). **정책 7 강화**: 응집 단위 분할 (URL+화면+데이터) + PR > 1500 LOC 사전 확인. **정책 3(MCP)**: MCP 실행 결과 별도 섹션. **정책 11 강화**: 인증 변경 시 4-endpoint 종단간 검증 의무. 상세: [docs/policies/history.md](docs/policies/history.md).

#### 정책 12: MCP scope 제한 의무

**default**: SELECT-only 자율 실행 OK / **INSERT/UPDATE/DELETE/DROP/ALTER + PII·credential SELECT = 사용자 사전 승인 의무** (운영 데이터 변경 + secret 노출 차단). MCP 호출 시 PR 본문 §"MCP 자율 실행 결과" 명시 (정책 3 강화 페어). 상세 + 검증 사례 + 금지 패턴: [docs/policies/active.md#정책-12](docs/policies/active.md#정책-12).

#### 정책 13: 운영 endpoint smoke check 의무

**default**: 매 사이클/Phase 종료 시 3-endpoint smoke check — `/health` 200 + `/auth/github` 302 + Location `redirect_uri=` 정합 + `/login` 200. PR 본문 §"운영 smoke check 결과" 섹션 의무 (인증/외부 통합 변경 PR). **자동화 가드 (oauth_flow_smoke 10 + dashboard 14 + theme_mobile 7) ≠ manual smoke check 대체** — CI 통과 ≠ 운영 정상. 상세: [docs/policies/active.md#정책-13](docs/policies/active.md#정책-13).

#### 정책 14: GitHub Code Scanning 알림 운영 체크 의무

사용자 발화: *"시큐리티에서 감지하는 내용도 앞으로 프로젝트 운영시 체크사항으로 부탁드립니다."*

**default**: 매 사이클 종료 시 Security 탭 Code Scanning open alert 직접 검토. 신규 alert = (a) 실제 위반 → fix PR / (b) false-positive → dismiss + 사유 / (c) 의도 패턴 → suppress + 회고. PR 본문 §"Code Scanning open alert" 일괄 회신 OK. **SCAManager lint (pylint/flake8/bandit) 통과 ≠ Security 탭 0 alert** (CodeQL 별도 룰셋). 상세: [docs/policies/active.md#정책-14](docs/policies/active.md#정책-14).

#### 정책 15: 코드 작업 (add/edit/delete) 전 사전 사고 의무

사용자 발화: *"앞으로 코드를 추가, 수정, 삭제 작업을 실행하기 이전에 항상 생각을 먼저 하고 진행을 합니다. 이해가 안되면 멈추거나 물어보고 하세요."*

**default**: 모든 Edit/Write/MCP destructive 직전 3 자문 의무 — (a) 목적 = 사용자 의도 정합? (b) 영향 범위 인지? (c) 검증 방법 명확? 이해 부족 시 즉시 중단 (옵션 표 또는 yes/no 사전 확인). **위임 분류 3-tier**: **High** (사전 확인 의무 — DB 스키마/API/권한/데이터 모델) / **Medium** (자율+보고 — 헬퍼/정책 진화) / **Low** (즉시 진입 — 회귀 가드/docstring/typo). 상세: [docs/policies/active.md#정책-15](docs/policies/active.md#정책-15).

#### 정책 16: 코드 단순화 default + 가독성 우선

사용자 발화: *"코드를 단순화 하여 작성을 해주세요. 단 정확성과 성능은 유지가 되야합니다. 되도록 코드는 이해하기가 쉽게 작성을 해주세요."*

**default 의무 5 원칙** (우선순위 순): 1. 정확성 / 2. 성능 / 3. 가독성 / 4. 최소 추상화 (사용처 ≥ 3 시 도입) / 5. **🔴 토큰 비용 효율** (caching + 분산 + 호출 빈도 제한 — caching 4 단계 사이클 63→74 활성화).

**🚫 명시 제외 영역** (AI 리뷰 품질 보존 — 사이클 72 사용자 명시 보류): `build_review_prompt` 토큰 예산 8000 축소 / `review_guides/` Tier1 full 압축. 신규 토큰 절약 영역 도입 시 사용자 사전 확인 의무 (정책 15 High tier 페어).

**금지 패턴**: 추상 베이스 클래스 / Generic 타입 / 메타클래스 / 데코레이터 체인 / "확장 대비" 분기. 상세 + 검증 사례 + 리뷰 체크포인트: [docs/policies/active.md#정책-16](docs/policies/active.md#정책-16).

#### 정책 17 신설 (2026-05-06 사이클 88 진입): 문서 정리 시 안정성 > 권장 규격 우선순위

사용자 발화 (2026-05-06, 사이클 88 Phase A 머지 후): *"문서정리는 권장하는 규격보다 안정성이 더 우선시 되야합니다. 여러 에이전트는 해당 기준 내용을 토대로 깊게 생각하여 논의후 저에게 제안한 내용이 조건에 타당한지 검토후 진행해주세요."*

**default 의무 5 원칙** (우선순위 순):
1. **안정성 우선** — 행동 가이드 detail 보존 + 회귀 0 (Anthropic 200줄 hard target 등 외부 권장 규격은 가이드라인 — 안정성 충돌 시 거부)
2. **default rule + 진화 default 본문 보존** — 정책 본문의 default rule + 진화 default 1~2줄 = CLAUDE.md 본문 보존 의무 / detail · 검증 사례 · Why · How to apply = `docs/policies/active.md` 또는 `history.md` external (Phase A 검증 패턴)
3. **단계 분할 + 단계별 검증 의무** — 매 분리 단계마다 5+1 다중 에이전트 회의 + 운영 검증 (행동 가이드 drift 0) + 사용자 옵션 표 결정 (정책 1 + 정책 8 + 정책 7 강화 페어)
4. **분리 위험 영역 사용자 사전 확인 의무** — 매 작업/회고/PR 의무 영역 (정책 8 cross-verify 정량 기준 / 정책 11 8 조합 체크리스트 / 정책 5 NEW-P0-N 예외 / 정책 9 완화 미적용 영역) = 본문 보존 default + 분리 시 High tier 사전 확인 의무
5. **누적 결함 정기 검증 default** (사이클 92 신설 — 사이클 89 #349/#350 시간차 결함 학습) — 단일 작업일 ≥ 18 PR 영역 도입 후 **≥ 5 사이클 경과 시 정기 5+1 다중 에이전트 검증 default** (정기 검증 트리거 = 시간/PR 기반 / 매 회고 cross-verify 트리거 정책 8 진화 와 시점·대상 차별). 사이클 89 사례 = 사이클 74/84 누적 결함 (E2E i18n hardcode + integration fixture sync) 발견 — 정기 검증 ROI 양성 검증. 상세: [docs/policies/active.md#정책-17-5번째-default](docs/policies/active.md#정책-17-5번째-default).

Why + How to apply (자가 검토 4 자문) 상세: [docs/policies/active.md#정책-17-why-how](docs/policies/active.md#정책-17-why-how).

#### 정책 18 신설 (2026-05-09 사이클 93): Claude ↔ Codex 양방향 mutual 검증 의무

사용자 발화 (2026-05-09, 사이클 93 CI 분석 사고 직후): *"Claude 또는 Codex가 작업을 수행시 반드시 두 LLM모델이 OK확인을 받아야 통과합니다. 상호간의 작업 내용을 검증 검토를 수행합니다. Claude 도 Codex도 이 내용은 반드시 숙지합니다."*

🔴 **사이클 94 사용자 정정 (2026-05-10)**: Codex 검증 = PR push 전 의무. push 후 의뢰 안티패턴 상세: [docs/policies/active.md#정책-18](docs/policies/active.md#정책-18).

**default 의무 5 영역**:
1. **양방향 대칭 흐름 (push 전 검증 default)** — Claude 작업 (로컬 commit) → Codex 검증 → OK 후 push / Codex 작업 (로컬 commit) → Claude 검증 → OK 후 push. **push 전 단독 완료 금지**.
2. **검증 의뢰 1줄 명시 의무 (push 전)** — 로컬 commit 후 응답에 "🔍 <상대 LLM> 검증 의뢰 (push 전)" 1줄 의무. 누락 시 다음 응답 회복 의무 (정책 1 진화 회귀 가드 사이클 86 Q4 페어). **push 보류 default — Codex/Claude OK 회신 받기 전까지 `git push` 금지**.
3. **NG 회신 시 자율 수정 금지** — 사유 분석 + 수정 plan 옵션 표 (정책 1) + 사용자 confirm 의무. **NG 회기 ≤ 3회 default** — 4회차 = 사용자 직접 결정 영역 escalation (옵션 표 의무).
4. **사이클 종료 = 3 조건 AND 의무** (정책 5 강화 페어) — (a) 사용자 신호 + (b) Claude OK + (c) Codex OK. 1 조건 부재 시 종료 보류.
5. **5+1 cross-verify ↔ mutual = 2-layer 격리 의무** — 정책 8 5+1 = Claude 내부 self-verify (관점 다양성) / mutual = 외부 LLM (모델 다양성). "Codex OK 받았으니 5+1 6차 생략 OK" 오해 차단 — 양 layer 독립 의무 보존.

**🔴 17 정책 cross-reference 표** (충돌/페어 7건 본문 명시):

| 정책 | mutual 페어 영역 |
|------|----------------|
| 3 (자율 판단) | 자율 판단 = mutual OK 받은 영역으로 한정 |
| 5 (사이클 종료) | 종료 신호 = 두 LLM 동의 의무 구성요소 (3 조건 AND) |
| 7 (PR 단위) | mutual = **push 전** Codex 검증 OK 후 push (사이클 94 정정) — push 후 의뢰 안티패턴 |
| 8 (회고 5+1) | 5+1 (Claude 내부) ↔ mutual (외부 LLM) 2-layer 격리 — cross-verify 6차 생략 시도 mutual 별도 의무 |
| 10 (PR 직접 생성) | Codex/Claude 생성 PR = **push 전 상호 검증 OK 후 push** (사이클 94 정정 — Codex NG #2 학습) — push 후 의뢰 안티패턴 |
| 12 (MCP scope) | MCP destructive = 사용자 사전 승인 우선 (mutual 면제 — 사용자 직접 결정 영역) |
| 16 (단순화 5번 토큰 효율) | mutual = 사용자 명시 의무 (단순화 5번 default 위반 면제) |

**예외 영역 4종** (mutual 검증 면제):
- 사용자가 "mutual 생략 OK" 명시 발화 시
- 단순 read-only 보고 (수정/검증 X — 단, 결정 영역 영향 시 의뢰 의무)
- 메모리 grep / 단순 정보 제공
- **사용자 직접 결정 영역** (사용자 명시 결정 = 최종, 두 LLM 검증 면제)

상세: [docs/policies/active.md#정책-18](docs/policies/active.md#정책-18).

---

### 작업 시작 전 필수 체크리스트 (매 작업마다)

모든 작업 착수 전 아래 다섯 가지를 순서대로 확인한다. 30초면 충분하다.

```bash
gh run list --limit 3                                       # CI status (기존 vs 신규 실패 구분)
gh api repos/xzawed/SCAManager/code-scanning/alerts \      # Code Scanning open alert 카운트 (정책 14)
  --jq '[.[] | select(.state=="open")] | length'            # CI/auth 부재 시 GitHub Security 탭 직접 확인
ls ~/.claude/projects/f--DEVELOPMENT-SOURCE-CLAUDE-SCAManager/memory/ | \   # 신규 fixture/테스트/패턴 작성 전 메모리 grep
  grep -E "pytest-|test-|feedback-"                         # 해당 영역 메모리 본문 read 후 default 적용 의무
ls docs/reports/ | tail -1                                  # 직전 회고 보고서 회신 회수 확인 (정책 9 강화 페어)
git status                                                  # 미커밋 변경 없는지 확인
git checkout -b <브랜치명>                                  # 브랜치 생성 (main 직접 커밋 금지)
```

**메모리 인덱스**: `~/.claude/.../memory/MEMORY.md` 참조 (매 세션 자동 로드).
- 신규 메모리 추가 시 MEMORY.md 인덱스 + 카테고리 카운트 동기화 의무 (사이클 75 분류 default).

GitHub Code Scanning 점검 detail 절차 + 운영 통합 = `docs/runbooks/operational-smoke-checks.md` §9 (정책 14).
메모리 grep 의무 detail = 메모리 디렉토리의 `feedback_` prefix 파일 참조 (테스트/CI 패턴 기록).

**브랜치 명명 규칙**

| 접두사 | 사용 시점 |
|--------|----------|
| `feat/` | 새 기능 구현 |
| `fix/` | 버그 수정 |
| `chore/` | 설정·문서·툴링 변경 |
| `docs/` | 문서 전용 변경 |

**예외 없음** — `.claude/` 내부 파일(Hook·에이전트·스킬), `CLAUDE.md`, `docs/` 변경도 모두 브랜치 + PR 방식으로 진행한다.

### 필수 원칙

- **TDD 우선**: 구현 코드 작성 전 반드시 `test-writer` 에이전트로 테스트를 먼저 작성한다.
- **Hook 신뢰**: `src/` 파일 편집 후 PostToolUse Hook이 자동 실행하는 pytest 결과를 확인한다. 실패 시 다음 단계로 진행하지 않는다.
- **Phase 완료 조건**: 테스트 전체 통과 + `/lint` 통과 + (파이프라인 변경 시 `pipeline-reviewer` 승인) 세 조건이 모두 충족될 때만 Phase 완료를 선언한다.
- **완료 시 필수 6-step**: 작업이 완료되면 반드시 ① 커밋 → ② Codex 검증 의뢰 (push 전, 정책 18) → ③ `git push` → ④ PR 생성(`gh pr create`) → ⑤ `docs/STATE.md` 수치 갱신 + `docs/cycle-history.md` 사이클 이력 동기화 → ⑥ **docs/architecture.md 동기화** (신규 파일 추가·삭제·이름 변경 시 `src/` 트리와 `### 핵심 데이터 흐름` 내 언급 갱신) 를 순서대로 수행한다. 예외 없음.
- **README.md 배지 동기화**: 테스트 수·pylint·커버리지 수치가 바뀌면 `README.md` 21~25줄 배지도 함께 갱신한다. 수치 출처는 항상 `docs/STATE.md`.
- **CLAUDE.md 아키텍처 동기화 체크리스트**: `src/` 하위에 파일 추가 시 아래 항목을 순서대로 확인한다. 누락 시 다음 Phase 착수 전 반드시 보완한다. **전례 3건** (Phase 11 PR #73 / 2026-05-01 UI 감사 cleanup PR-D1 / 2026-05-05 사이클 78~82 5+1 cross-verify 환경변수 4건 누락).

  | 위치 | 확인 사항 |
  |------|----------|
  | `docs/architecture.md` `src/` 트리 | 신규 파일 한 줄 항목(경로 + 짧은 역할 설명) 추가 (사이클 85 #320 분리 — CLAUDE.md `src/` 트리 → `docs/architecture.md` 단일 출처) |
  | `docs/architecture.md` `templates/` 한 줄 | 신규 템플릿 파일명 목록에 추가 |
  | `docs/architecture.md` `repositories/` 한 줄 | 신규 repo 파일 "N종" 카운트 + 목록 갱신 |
  | `docs/architecture.md` `services/` 한 줄 | 신규 service 함수 목록 갱신 |
  | `docs/architecture.md` 핵심 데이터 흐름 | 신규 경로가 흐름도에 포함되어야 하면 추가 |
  | `docs/reference/env-vars.md` | **신규 환경변수 (`*_DISABLED` kill-switch / `SAAS_*` / 모델 분기 / DB 등) 추가 시 적정 섹션 등재 의무** (사이클 82 5+1 cross-verify P0 학습 — 4건 누적 누락) |
  | `.claude/rules/<area>.md` | **🔴 사이클 86 Q2 신설 (사용자 명시 결정)** — 영역별 path-scoped rules 본문 sync 의무. `tests/**` / `alembic/**` / `src/<area>/**` 등 path 매칭 영역 변경 시 해당 `.claude/rules/<area>.md` 본문 갱신 의무. 8 영역 매트릭스: testing.md (`tests/**`, `e2e/**`, `pytest.ini`) / db.md (`alembic/**`, `src/models/**`, `src/database.py`, `src/repositories/**`) / pipeline.md (`src/worker/`, `src/analyzer/`, `src/scorer/`, `src/webhook/`, `src/gate/`) / api.md (`src/api/**`, `src/notifier/**`, `src/webhook/**`, `src/gate/**`, `src/main.py`) / security.md (`src/auth/**`, `src/crypto.py`, `src/shared/log_safety.py`) / ui.md (`src/templates/**`, `src/static/**`, `src/ui/**`) / i18n.md (`src/i18n/**`, `src/middleware/locale.py`) / deploy.md (`railway.toml`, `nixpacks.toml`, `requirements.txt` 등). path 매칭 시 자동 로드 (Anthropic 공식 패턴) — 본문 stale 시 Claude rule guidance drift 위험 |

### 모바일 환경 보호 — 수정 금지 파일

🔴 수정 금지 파일(`alembic/versions/`, `src/templates/*.html`, `railway.toml`, `Procfile`, `alembic.ini`) — 테스트 환경 없을 때 PreToolUse Hook 자동 차단. 상세: [docs/runbooks/workflow.md](docs/runbooks/workflow.md#모바일-환경-보호--수정-금지-파일)

**예외:** `make test` 가 정상 실행되는 환경(로컬 PC, GitHub Codespaces)에서는 모든 파일 수정이 허용된다.

### 작업 유형별 필수 실행 순서

작업 유형별 실행 순서 (새 기능 / 파이프라인 / Webhook-API / Phase 착수): [docs/runbooks/workflow.md](docs/runbooks/workflow.md#작업-유형별-필수-실행-순서)

### 병렬 에이전트 — 브랜치 충돌 방지

독립 브랜치 + PR이 필요한 병렬 에이전트를 디스패치할 때 아래 세 가지를 반드시 지킨다.
(전례: 2026-04-27 PR-A·B·C 병렬 작업에서 3개 에이전트 모두 같은 브랜치에 커밋 → PR 3개 대신 1개 생성)

1. **`isolation: worktree` 전원 적용** — 독립 브랜치가 필요한 모든 에이전트에 예외 없이 적용.
2. **프롬프트 첫 단계에서 고유 브랜치명 명시** — 아래 형식을 프롬프트 Step 1로 고정.
   ```
   1. git checkout -b docs/phase12-state-readme  (이미 있으면 switch)
   ```
3. **완료 기준에 "PR URL 반환" 포함** — 에이전트가 분석만 하고 멈추는 사고 방지.
   ```
   완료 조건: gh pr create 성공 후 PR URL 반환
   ```

> **나쁜 방식** → 에이전트 프롬프트: "PR-B 작업을 수행해주세요"
> **좋은 방식** → 프롬프트 Step 1에 `git checkout -b docs/<고유-이름>` 명시 + `isolation: worktree` 설정

## 주의사항 (카테고리별 — `.claude/rules/<area>.md` path-scoped)

> **사이클 85 정리**: 8 카테고리 본문은 `.claude/rules/<area>.md` 로 분리 (Anthropic 공식 path-scoped rules 패턴). Claude Code 가 해당 영역 파일 작업 시 자동 로드. 매 세션 의무 read 부담 0.

| 영역 | path-scoped 파일 | 매칭 경로 |
|------|----------------|----------|
| 테스트 | [`.claude/rules/testing.md`](.claude/rules/testing.md) | `tests/**`, `e2e/**`, `**/conftest.py`, `pytest.ini` |
| DB / 마이그레이션 | [`.claude/rules/db.md`](.claude/rules/db.md) | `alembic/**`, `src/models/**`, `src/database.py`, `src/repositories/**` |
| 파이프라인 / 비즈니스 로직 | [`.claude/rules/pipeline.md`](.claude/rules/pipeline.md) | `src/worker/pipeline.py`, `src/analyzer/**`, `src/scorer/**`, `src/webhook/**`, `src/gate/**` |
| API / 알림 채널 | [`.claude/rules/api.md`](.claude/rules/api.md) | `src/api/**`, `src/notifier/**`, `src/webhook/**`, `src/gate/**`, `src/main.py` |
| 보안 | [`.claude/rules/security.md`](.claude/rules/security.md) | `src/auth/**`, `src/crypto.py`, `src/shared/log_safety.py`, `src/api/auth.py`, `src/webhook/validator.py` |
| UI / 템플릿 | [`.claude/rules/ui.md`](.claude/rules/ui.md) | `src/templates/**`, `src/static/**`, `src/ui/**` |
| 다국어 / i18n | [`.claude/rules/i18n.md`](.claude/rules/i18n.md) | `src/i18n/**`, `src/middleware/locale.py`, `src/notifier/_language.py`, `src/analyzer/pure/review_guides/**` |
| 배포 | [`.claude/rules/deploy.md`](.claude/rules/deploy.md) | `railway.toml`, `nixpacks.toml`, `requirements.txt`, `requirements-dev.txt`, `.env.example` |

🔴 표시는 과거 사고로 검증된 고위험 규칙이다 (각 `.claude/rules/<area>.md` 파일 본문 참조).


## 현재 상태

최신 수치는 [docs/STATE.md](docs/STATE.md) 참조. 사이클 이력: [`docs/cycle-history.md`](docs/cycle-history.md) (사이클 60~92 archive).
