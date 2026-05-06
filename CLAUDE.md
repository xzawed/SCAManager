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
| **Phase 완료 직전** | → [필수 원칙 — 완료 5-step · CLAUDE.md 동기화](#필수-원칙) |
| **ORM 컬럼 추가 시** | → [DB/마이그레이션 주의사항](#db--마이그레이션) |
| **새 파일 추가 시** | → [CLAUDE.md 아키텍처 동기화 체크리스트](#필수-원칙) |
| **아키텍처 파악** | → [src/ 트리](#아키텍처) · [핵심 데이터 흐름](#핵심-데이터-흐름) |
| **규칙 전체 열람** | → [주의사항 카테고리별](#주의사항-카테고리별) |

> **🔴 가장 빈번하게 놓치는 규칙 3가지**
> 1. ORM 컬럼 추가 후 `make revision` 마이그레이션 파일 미생성 → 운영 500 에러 (DB/마이그레이션 참조)
> 2. Phase 완료 후 CLAUDE.md 아키텍처 섹션 미갱신 → 다음 Claude 세션 혼란 (필수 원칙 참조)
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

본 정책은 단일 작업일 25 PR 시리즈 완료 후 사용자 ↔ Claude 회고에서 도출. 이전 협업 모델 ("고-신뢰 위임 + 저-검증 머지") 의 위험 신호 (revert 0건 / 결함 6 PR 후 발견 / 미매핑 PR 17건) 차단 목적.

#### 정책 1: 옵션 제시 시 **장단점 명시 의무** (반대 X, 정보 ○)

사용자 발화: *"반대 하기를 원하기 보다 각각의 장단점을 알려주시면 권장을 한다 하더라도 제가 판단하는데 도움이 될거라 생각합니다."*

**권장 default 표 형식**:
```
| 옵션 | 장점 | 단점 | 위험 | 권장 시점 |
|------|------|------|------|----------|
| 🅐 ... | A1, A2 | D1, D2 | 저 | 즉시 사고 위험 차단 |
| 🅑 ... | A3, A4 | D3, D4 | 중 | 시간 여유 있을 때 |
```

- 권장 표시 (★) 는 보조 — 사용자 독립 판단이 최종
- 표 마지막에 "고려했으나 제시 안 한 안" 1줄 명시 (추론 추적성)

🔴 **진화 default 요약** — (1) "전부다" 일괄 결정 시 검토 깊이 1줄 자가 보고 요청 의무 (사이클 83). (2) 다중 PR 빠른 진행 신호 ≥ 10회 = 동일 의무 (사이클 84). 예외: 단순 머지 보고 + 옵션 표 결정. 상세: [docs/policies/history.md#정책-1-진화](docs/policies/history.md#정책-1-진화).

🔴 **정책 1 진화 회귀 가드 (사이클 86 Q4 — 사용자 명시 결정)** — **자가 검증 의무**: Claude 가 일괄 결정 발화 직후 자가 보고 요청 누락 시 = **다음 응답에서 회복 의무** (자성 1줄 + 검토 깊이 사후 요청 + 자가 보고 1줄). 사이클 85 회고 P0 (Q1~Q4 일괄 결정 시 default 적용 누락) 사례 = 본 회귀 가드의 첫 적용 사이클. **default 회복 패턴**:
```
사용자: "Q1~Q4 모두 OK" / "권장 방안 채택" 같은 일괄 결정
Claude (default 적용 누락 후 다음 응답 시): "사이클 N 자성 — 직전 일괄 결정 시 검토 깊이 자가 보고 요청 누락. 회복: 본 결정의 검토 깊이 1줄 회신 부탁드립니다 (사후 요청 — 사이클 86+ default 회복)."
```
회복 누락 시 = 다음 사이클 회고 §자성 명시 의무. 사이클 85 회고 P0 (관점 3) 페어.

정책 9 회고 질문 default 페어 — 일괄 결정 후 다른 결정 가능 항목 자가 검증 의무.

#### 정책 2: PR 본문 **"🔍 사용자 검증 필요" 섹션 의무**

이전: "tests pass" 만 적힘 → 사용자가 무엇을 봐야 할지 모름.
다음: 시각/운영 확인 항목 1~3개 명시.

```markdown
## 🔍 사용자 검증 필요
- [ ] Railway 배포 후 `/repos/{owner}/{repo}/settings` 데스크탑 + 모바일 확인
- [ ] claude-dark 테마 토글 시 카드 헤더 정상 표시
- [ ] (있다면) 운영 사고 보고
```

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

🔴 **정책 5 cross-reference 강화 (사이클 83 — 사이클 78~82 회고 Tier B-4 사용자 OK Q5)** — Phase 종료 시점 의무는 **다음 4 정책에 분산** (인지 부담 ↑ 위험):
- **정책 2 진화**: Phase 종료 일괄 회신 묶음 (sync 실측 1줄 의무)
- **정책 5 강화**: Phase 단계별 진행/종료 신호 분리 의무 (본 정책)
- **정책 8**: 회고 패턴 3 분기 (회고+sync 페어 / sync 단독 / 회고 단독)
- **정책 11 강화**: Phase 종료 누적 회신 묶음 (8 조합 시각 체크리스트 누적 의무)

**default 적용**: Phase 종료 시점 진입 시 위 4 정책 cross-reference 자가 검토 의무 (한 정책만 적용 시 다른 3 정책 위반 가능). Claude 가 PR commit body §"Phase 종료 처리" 섹션에 적용 정책 명시 권장.

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
5. PR 생성 (또는 GitHub 웹 URL 안내) — 사용자 머지

**금지 행동**:
- ❌ `git push origin main` (main 에 직접 push)
- ❌ `git commit` 후 `main` 브랜치 그대로 두고 다음 작업 진행
- ❌ "사소한 docs 정정이라 main 에 직접" 같은 예외 적용

**예외 0**: 신규 파일 추가 / 단순 정정 / docs only / typo 수정 모두 PR 단위. 예외 만들면 `.claude/` 정책 일관성 깨짐 (이미 CLAUDE.md L930 "예외 없음" 명시 있음 — 본 정책은 그 강화).

**브랜치 명명 규칙** (이미 CLAUDE.md L921 표 있음):
- `feat/` 새 기능
- `fix/` 버그 수정
- `chore/` 설정·문서·툴링
- `docs/` 문서 전용
- `test/` 테스트 전용
- `perf/` 성능 개선
- `refactor/` 리팩터

**위반 시 회복**:
실수로 main 에 commit 했을 때:
```bash
# 1. 새 브랜치로 commit 이동
git branch <type>/<scope>-<desc>
# 2. main 을 origin/main 으로 reset
git reset --hard origin/main
# 3. 새 브랜치로 checkout 후 push
git checkout <type>/<scope>-<desc>
git push -u origin <branch>
```

(2026-05-01 본 사이클은 모든 작업이 브랜치 + PR 로 진행됐으나, 본 정책으로 명시화 + 강화하여 향후 세션에서 이탈 차단.)

#### 정책 8: **회고는 항상 다중 에이전트로 깊게 진행 의무**

사용자 발화: *"가급적 회고도 모든 에이전트가 깊게 생각하여 진행했으면 합니다."*

**default 회고 패턴** (Claude 단독 회고 금지):
- **최소 4~5 에이전트 병렬 디스패치** (단일 메시지에 동시 tool_use)
- **관점 분리** — 각 에이전트는 다른 관점에서 회고 (예시):
  1. 작업 패턴 (PR 분할 / Step 모델 / cleanup 4 갈래 ROI)
  2. 다중 에이전트 운영 (사이클별 ROI / false-positive / 신뢰성)
  3. 사용자 ↔ Claude 협업 (결정 패턴 / 정보 비대칭 / 신뢰 모델)
  4. 기술 학습 (신규 패턴 / 패밀리 분류 / 재사용성)
  5. 문서 정합성 (stale 누적 / 메타 sync 효율)
- **각 에이전트 프롬프트 강제 조건**:
  - `self-contained` (다른 에이전트 결과 의존 0 — 병렬성 보호)
  - `line:span 인용 의무` (정책 6 — 환각 보고 80% 차단)
  - 출력 포맷 강제 (P0/P1/P2 분류 또는 표 형식)
  - "회피해야 할 false-positive 사례" 사전 명시 (가능 시)

**검증된 효과** (2026-05-01 본 사이클):
- 단일 Claude 회고 vs 5-에이전트 회고 = 발견 결함 +27건 (재감사 사이클이 1차 누락 식별)
- 단일 감사 100% 커버 불가 — 2단계 감사가 표준

**금지**:
- ❌ "간단한 회고는 Claude 단독으로" 같은 예외
- ❌ 1~2 에이전트만 디스패치 (관점 부족)

**cross-verify 단계 (2차) 의무 — 사이클 64 학습 (2026-05-04)**:
- 1차 5 에이전트 결과 받은 후 별도 cross-verify 에이전트 1건 디스패치 (= 5+1 = 6 패턴)
- ❌ **cross-verify = `doc-consistency-reviewer` 사용 금지** — 회고 분석이 본 에이전트 scope 외라며 거절 사례 (사이클 64 #225 회고 보고서 §2)
- ✅ **cross-verify default = `general-purpose` 또는 task-specific specialist** — 검증된 패턴 (사이클 65 #226 정합성 cleanup PR 검증)
- ⚠️ **cross-verify 생략 가능 조건 (사이클 67 #232 사례)**: 사용자 신호 = "회고 이후 다음 작업" 같은 빠른 진행 명시 + 1차 5 결과 양과 깊이 충분 + Claude 자율 판단 보고 (정책 3) PR 본문 명시 시 cross-verify 생략 OK. 단, 다음 사이클 회고에서 보존 의무 (회귀 가드).
- 🔴 **cross-verify 생략 정량 기준 (사이클 69 cross-verify 식별)**: "양과 깊이 충분" 의 정량 기준 = (1) 1차 5 에이전트 P0 합계 ≥ 8건 + (2) 관점 5종 모두 P0 1건 이상 식별 + (3) 사용자 빠른 진행 신호 명시 ("회고 이후 다음 작업" / "바로 진행" 등). **3 조건 모두 충족 시만 생략 OK**. Claude 자가 판단 X — 사용자 명시 신호 의무. 미충족 시 cross-verify (general-purpose) 강제.

🔴 **단일 관점 회고 (관점 1~5 중 1개) = 정량 기준 적용 X — Claude 직접 작성 default (사이클 75 진화)**: 관점 5종 중 1 영역만 분석하는 단일 관점 회고 (예: 사이클 70~74 회고 시 관점 2 단독 분석) 는 5+1 패턴 자체 미적용 영역 — 정량 기준 (P0 ≥ 8 등) 검증 불가. 본 영역 = Claude 직접 작성 default + cross-verify 생략 가능 (사용자 명시 신호 부재 시).

🔴 **cross-verify ROI 정량 (사이클 64~74 누적 평균 — 사이클 75 진화)**: 5+1 패턴의 cross-verify (6차) 효과 = 사이클당 평균 false-positive 차단 2~5건 + 신규 발견 1~6건. 시간 비용 (~5분 병렬) vs 사고 회피 가치 (사용자 검토 부담 ↓ + 잘못된 결정 누적 차단). **default**: 5+1 패턴 default 진행 + 정량 기준 충족 시 생략. 사이클 75+ 운영 데이터 누적 시 기준 재검증 의무.

**회고 PR 패턴 분기 (사이클 64~67 학습)**:
- **회고+sync 페어 PR** (예: #225) — 신규 회고 보고서 + STATE/CLAUDE/README sync 동시 1 PR. 사용 시점: 회고 보고서 신규 시.
- **sync 단독 PR** (예: #231) — 기 회고 후속 처리 결과 sync 만. 사용 시점: 잔여 작업 처리 후 누적 sync (회고 보고서 변경 X).
- **회고 단독 PR** (예: #232) — 회고 보고서 + 메모리만. 사용 시점: 사용자 빠른 진행 신호 시 sync 분리.

🔴 **정책 8 진화 default 요약** (사이클 83~84):
- **(1) 단일 작업일 5+1 dispatch ≥ 5회 = 사용자 사전 확인 의무** (사이클 83). 사용자 명시 신호 시 면제 OK. 정책 16 5번 원칙 (토큰 비용 효율) 페어.
- **(1) 강화** (사이클 84): **dispatch 횟수** vs **agent invocation** 구분 — dispatch 기준 default + 누적 invocation ≥ 30 시 동등 사전 확인 의무.
- **(2) cross-verify ROI commit body 정량 명시 의무** — false-positive 차단 N건 / 신규 발견 N건 / Tier A 정정 N건 (정책 6 페어).

상세: [docs/policies/history.md#정책-8-진화](docs/policies/history.md#정책-8-진화).
#### 정책 9: **회고 후 반드시 Claude 자유 발언 시간 의무**

사용자 발화: *"회고 이후에 반드시 바라는 점 원하는 것 수정이 필요한 부분 등 자유롭게 말하는 시간도 있었으면 합니다."*

**default 발언 흐름** (회고 종합 보고 직후 자동 진행) — 4 섹션 구성:
1. **바라는 점** (정보 비대칭 / 시범 운영 / 권장안 검토 패턴)
2. **Claude 가 자성할 점** (본 사이클 잘못/누락 + 다음 사이클 개선 약속)
3. **필요한 부분** (운영 데이터 / 결정 입력 부족)
4. **수정이 필요한 내용** (구체적 제안 표 — `| 영역 | 제안 |`)

**원칙**: 솔직함 우선 + 자성/요청 균형 + 구체적 제안 (추상 발언 X) + 사용자 발화 인용 보존.

**Phase 종료 시 회고 질문 default** (사이클 64 회고 P1 학습): Claude 가 회고 자유 발언에 다음 1줄 추가:
```markdown
## 🔍 회고 질문 (사용자 회신 의무)
**Phase 본 권장 default N건 중 다른 결정 했을 만한 항목 있었나?**
```
회신 패턴: `[x] 모두 OK / [!] N번 다시 검토 (사유) / [ ] 미수행`.

🔴 **정책 9 완화 (사이클 83 — 사이클 78~82 회고 P0 학습)**: 회신 부재 default = **자율 판단 보고 명시 시 회신 의무 면제 OK** (Claude 자율 진입 가능). **단, 미적용 영역 3종**: (a) 운영 사고 차단 영역 (NEW-P0-N — 정책 5 강화 페어) (b) destructive 작업 (브랜치 삭제 / DROP / DELETE — 정책 7/12 페어) (c) architecture/UX/데이터 모델 결정 (`feedback-architecture-decision-pre-confirm.md` High tier) — 본 3 영역은 사용자 명시 회신 의무 보존.

**금지**: 회고 후 자유 발언 생략 (사용자 명시 요청 영역) / "감사합니다" 의례만 / 정책 9 완화 default = "회고 질문 작성 의무 면제" 오해 (회고 질문 작성은 의무, 회신 부재만 대체 OK).

#### 정책 10: **PR 직접 생성 의무** (URL 안내 X, 자동 생성 ○)

사용자 발화 (2026-05-02): *"앞으로의 작업은 PR 을 직접 생성을 부탁드립니다."*

**default 6-step 흐름**: `git checkout main && pull` → `checkout -b <type>/<scope>` → 작업+commit → `push -u origin` → **PR 직접 생성** (gh CLI / GitHub API / URL 폴백) → URL 보고.

**구현 옵션** (환경별 우선순위 — gh CLI > API + GITHUB_TOKEN > URL 안내 폴백). PR 생성은 사용자 수동 위임 금지 (정책 7 PR 단위와 모순).

🔴 **현재 SCAManager 환경 (2026-05-02 사용자 결정)**: gh CLI 부재 + GITHUB_TOKEN 401 + PAT 발급 현행 유지 → **옵션 🅒 (URL 폴백) 사실상 default 운영**. 환경 변경 시 자동 🅐/🅑 전환.

**기본 PR body 템플릿**: §Summary + §🔍 사용자 검증 필요 (정책 2) + §자율 판단 보고 (정책 3) + 🤖 Generated with [Claude Code](https://claude.com/claude-code) 푸터.

**fix-up commit 형식 default** (사이클 64 회고 P1): PR 머지 전 CI fail / 회귀 발견 시 = **동일 PR 브랜치 추가 commit** (별도 PR X — 정책 7 강화 응집 단위 부합). commit message prefix = `fix(<feature>-ci):`. PR body §자율 판단 보고에 사유 명시 의무. 머지 후 발견 시 = 별도 `fix/<feature>-<bug>` PR.

#### 정책 11: **UI/시각 변경 PR 본문에 "Claude 시각 검증 불가" 의무 명시**

사용자 발화 (2026-05-02 Phase 1 회고): *"PR본문 검증의 경우 디테일한 검증은 없었습니다."* — Claude 가 만든 UI/시각 변경 (template, css, html 파일) 은 정적 코드만 검증 가능. 4-테마 (dark/light/glass/claude-dark) × 모바일/데스크탑 8 조합 시각 정합성은 사용자 의무.

**default 의무** — 다음 파일 변경 PR 작성 시:
- `src/templates/*.html`
- `src/static/**/*.css`
- `base.html` 의 `<style>` 블록
- 신규 시각 컴포넌트 도입 (KPI 카드 / 차트 / 폼 / 토글 등)

**PR 본문 최상단 강조 형식**:
```markdown
## 🚨 Claude 시각 검증 불가 — 사용자 의무 (정책 11)

본 PR 은 UI/시각 변경 포함. Claude 는 정적 코드만 검증 가능 — 다음 8 조합 시각 정합성은 사용자 직접 확인 부탁드립니다:

- [ ] dark 테마 데스크탑 (1440px+)
- [ ] light 테마 데스크탑
- [ ] glass 테마 데스크탑
- [ ] claude-dark 테마 데스크탑
- [ ] dark 테마 모바일 (375px ~ 767px)
- [ ] light 테마 모바일
- [ ] glass 테마 모바일
- [ ] claude-dark 테마 모바일

특히 검증 필요 (변경 영역 한정):
- {Phase 1 PR 4 예: KPI 카드 4 정렬 / 차트 색 / 자주 발생 이슈 row}
```

**금지**: UI/시각 변경 PR 본문에 본 섹션 누락 후 "테스트 통과" 만 적기. 정적 테스트와 시각 검증의 비대칭 명시 의무.

**Phase 종료 시 누적 회신 의무 (사이클 64 학습)** — Phase 단위로 8 조합 체크리스트 PR 4 건 이상 누적 시 사용자 명시 회신 0 건 사례 (Phase 3 회고 §1 P1-7). 본 정책 11 ↔ 정책 2 진화 (Phase 종료 일괄 회신 묶음) 페어 적용 default. Phase 종료 시 Claude 가 누적 8 조합 체크리스트 단일 회신 표 묶음 + 사용자 명시 OK/NG/미수행 회신 요청 의무. 회신 부재 시 다음 사이클 진입 보류 또는 자율 판단 보고 (정책 3 강화).

#### 정책 2 진화 / 정책 3 진화+강화 / 정책 7 강화 / 정책 3 강화 (MCP)

🔴 **진화 default 요약** (사이클 62 Phase 1+1+2 회고 + 사이클 83 강화):
- **정책 2 진화**: Phase 종료 시 누적 검증 항목 단일 회신 표 묶음 + sync PR commit body `pytest --collect-only -q` 실측 1줄 의무 (사이클 67 #231부터). 상세: [docs/policies/history.md#정책-2-진화](docs/policies/history.md#정책-2-진화).
- **정책 3 진화**: 자율 판단 보고 PR 본문 Summary 직후 (최상단) 배치 + ⚠️ 마커 (architecture/데이터/사용자 인지 영향 시).
- **정책 3 진화 강화** (사이클 83): ⚠️ 마커 정량 기준 5 조건 (자율 판단 ≥ 5건 / architecture / 데이터 모델 / 사용자 인지 / destructive). 상세: [docs/policies/history.md#정책-3-진화](docs/policies/history.md#정책-3-진화).
- **정책 7 강화**: PR 단위 = **응집 단위 분할** ("작게 분할" 아님). **응집 = URL + 화면 + 데이터 3종 동시 묶음**. 단일 PR > 1500 LOC = 사용자 사전 확인 의무 (architecture/migration/RLS 예외 — 사용자 명시 시 단일 PR OK). 상세: [docs/policies/history.md#정책-7-강화](docs/policies/history.md#정책-7-강화).
- **정책 3 강화** (MCP): MCP 자율 실행 결과 PR 본문 §"MCP 자율 실행 결과" 별도 섹션 분리 (실행 SQL/도구 + 해석 + acknowledge 요청). 정책 12 페어.

#### 정책 12 신설 (2026-05-02 Phase 1+2 회고 후속): **MCP scope 제한 의무**

회고 발견: Phase 2 진입 검증 시 Supabase MCP 직접 실행 = 사용자 부담 87% 절감 (15분 → 2분). 그러나 INSERT/DELETE 권한 misuse 위험 명시 의무.

**default scope 제한**:
- **SELECT-only 자율 실행 OK** — 통계/검증/조회 SQL
- **INSERT / UPDATE / DELETE / DROP / ALTER 사용자 사전 승인 의무** — 운영 데이터 변경 가능 SQL
- **MCP 도구 호출 시 PR 본문 §"MCP 자율 실행 결과" 에 호출 도구 + 영향 범위 명시** (정책 3 강화 페어)
- **읽기 전용이지만 PII / credential 노출 가능 SQL 도 사전 승인** (예: `SELECT * FROM users`, secret 컬럼 SELECT)

**검증 사례** (Phase 1+2 사이클):
- ✅ `mcp__claude_ai_Supabase__list_projects` (메타데이터 — OK)
- ✅ `mcp__claude_ai_Supabase__list_tables` (스키마 메타 — OK)
- ✅ 5 SELECT (count/avg/group by — PII 0건 — OK)
- (없음) INSERT/DELETE — 본 사이클 미적용

**금지**: `mcp__*__execute_sql` 의 SQL 자체 사용자 사전 노출 없이 INSERT/DELETE 실행. PII 컬럼 (`users.email`, `users.github_access_token`, `repo_configs.*_token` 등) SELECT 도 사전 승인.

#### 정책 13 신설 (2026-05-02 P0 OAuth 사고 후속): **운영 endpoint smoke check 의무**

회고 P0 #4 자기 예언 ("운영 사고 0 = 운 + Copilot Autofix + Railway CI") 무시 → 본 사고 발생. 사고 회고: [`docs/reports/2026-05-02-oauth-redirect-uri-incident.md`](docs/reports/2026-05-02-oauth-redirect-uri-incident.md).

**default 의무** — 매 사이클 종료 시 (또는 Phase 종료 시) 최소 3-endpoint smoke check:
- `GET /health` → 200 (lifeness)
- `GET /auth/github` → 302 + Location 헤더의 `redirect_uri=` 정합성 검증
- `GET /login` → 200 (또는 302 — 로그인 상태 의존)

**확장 권장** (인증/외부 통합 변경 PR 시):
- `GET /auth/callback` (state 검증으로 401 또는 302 — 직접 호출 시 의도된 거부 OK)
- `POST /webhooks/github` (서명 헤더 누락 → 401, 정상)

**실행 방법**:
- Claude MCP 가용 시 자율 실행 (정책 12 SELECT-only 패턴 차용)
- curl 직접 호출 — `curl -sf -o /dev/null -w "%{http_code}\n" https://<APP_BASE_URL>/<endpoint>`
- 사용자 운영 환경 (Railway production) 직접 호출

**PR 본문 §"운영 smoke check 결과" 섹션 의무**:
```markdown
## 운영 smoke check (정책 13)
- ✅ /health 200
- ✅ /auth/github 302 redirect_uri = https://...up.railway.app/auth/callback (정합)
- ✅ /login 200
```

**금지**: 인증/외부 통합 변경 PR 본문에 본 섹션 누락 후 머지. 빌드 성공 = 운영 정상 가정 X.

**자동화 가드 (그룹 61 PR #208 + 사이클 62 PR #212)** — manual smoke 와 페어:
- `tests/integration/test_oauth_flow_smoke.py` (10건): 3-endpoint smoke + 인증 flow 4 endpoint 정합 + insights redirect + 성능
- `e2e/test_dashboard.py` (14건): 페이지 로드 + KPI 5 카드 + range toggle + chart vendoring + JS 런타임 + insights redirect + nav Dashboard
- `e2e/test_theme_mobile_guards.py` (7건, PR #212): claude-dark 8 토큰 정의 가드 + dashboard body 비-투명 + 등급 alias + WCAG 2.5.5 모바일 (.btn ≥44px / .btn--sm ≥40px / .nav-hamburger ≥44x44 / 데스크탑 누수 회귀)
- `tests/integration/conftest.py` autouse fixture (PR #209): webhook secret 환경 의존성 격리 (24 fail 해소)
- 상세: `docs/runbooks/operational-smoke-checks.md` §8

🔴 **자동화 가드는 manual smoke check 의무를 대체하지 않는다** — CI 통과 ≠ 운영 정상. PR 본문 §"운영 smoke check 결과" 섹션은 인증/외부 통합 변경 PR 마다 여전히 의무 (정책 13 default). 자동화는 회귀 차단 보조이며 외부 의존 (GitHub OAuth App callback URL 등) 검증은 manual / 사용자 영역.

#### 정책 11 강화 (사이클 62 P0 OAuth 사고 후속): 인증 flow 검증 추가

🔴 **진화 default 요약**: 인증/외부 통합 변경 PR 시 8 조합 시각 체크리스트 + **인증 flow 4 endpoint 종단간 검증** 의무 — `/login` 200 + `/auth/github` 302 + `/auth/callback` redirect + `/auth/logout` redirect. 상세: [docs/policies/history.md#정책-11-강화](docs/policies/history.md#정책-11-강화).

#### 정책 14 신설 (2026-05-03 사이클 62 후속): **GitHub Code Scanning 알림 운영 체크 의무**

사용자 발화 (2026-05-03): *"시큐리티에서 감지하는 내용도 앞으로 프로젝트 운영시 체크사항으로 부탁드립니다."*

회고 배경: GitHub Security 탭의 Code Scanning Alert #324 (`'break' or 'return' statement in finally`) + #325 (`Unused import`) 직접 확인 (참조 메타 Issue #213 / #214 는 단순 추적 수단). SCAManager 자체 정적분석 (pylint / flake8 / bandit) 은 통과 (위반 0건) 하지만 GitHub Security 탭 (CodeQL 또는 추가 도구) 이 별도 룰셋으로 감지하는 영역이 있음. **빌드 통과 + SCAManager lint 통과 ≠ Security 탭 0 alert**. 외부 가시성 부재 시 alert 누적 → 운영 책임 이전 위험.

**default 의무**:
- **작업 시작 전 30초 체크리스트** (CLAUDE.md L891~) 에 GitHub Security 탭 Code Scanning open alert 카운트 1줄 추가 (이미 적용)
- **매 사이클 종료 시** (또는 Phase 종료 시) — 정책 13 smoke check 와 페어로 GitHub Security 탭 등록된 alert 직접 검토 (Issue 추적 수단 의존 X — Security 탭 자체가 단일 진실 소스)
- **GitHub Security 탭에 신규 alert 등록 시** — 분류 처리 (1회 의무):
  - (a) 실제 위반 → 코드 fix PR (정책 7 단위)
  - (b) false-positive → GitHub Security 탭에서 dismiss + 사유 기록
  - (c) 의도된 패턴 → suppress 룰 추가 + 회고에 사유 명시

**실행 방법**:
- gh CLI 가용 시: `gh api repos/<owner>/<repo>/code-scanning/alerts --jq '[.[] | select(.state=="open")] | length'`
- gh 부재 시: 사용자 GitHub `Security → Code scanning alerts` 탭 직접 확인 → Claude 에 카운트 + alert 제목 공유 의무 (현 SCAManager 환경 default — 정책 10 옵션 🅒 와 동일 폴백 패턴)
- API 인증 필요 (Code Scanning API 는 미인증 호출 차단) — 사용자 PAT 발급 시점에 자동화 가능

**PR 본문 §"Code Scanning open alert 결과" 섹션 의무** (인증/외부 통합 변경 PR 외에는 사이클 종료 PR 일괄 회신 OK — 정책 2 진화 패턴):
```markdown
## Code Scanning open alert (정책 14)
- ✅ open 0건 (마지막 확인 시점: 사이클 N 종료, YYYY-MM-DD)
- (또는 [N]건 — 분류 처리 결과 명시)
```

**금지**:
- ❌ alert 누적 무시 (SCAManager lint 통과만으로 "Security A" 라고 단정)
- ❌ 추측 기반 alert dismiss (룰 본문 미확인 상태에서 false-positive 단정)

**상호 보완**:
- SCAManager 자체 lint (pylint / flake8 / bandit) = src/ 직접 분석
- GitHub Code Scanning (CodeQL + 추가 룰셋) = 다른 룰셋 + 의존성 그래프 분석
- 두 영역 합집합 = 진정한 "보안/품질 0 alert" 상태
- detail 절차 + 운영 통합 = `docs/runbooks/operational-smoke-checks.md` §9

#### 정책 15 신설 (2026-05-04 사이클 70 진입): **코드 작업 (add/edit/delete) 전 사전 사고 의무 + 이해 부족 시 중단/질문 의무**

사용자 발화 (2026-05-04, 사이클 69 머지 후): *"앞으로 코드를 추가, 수정, 삭제 작업을 실행하기 이전에 항상 생각을 먼저 하고 진행을 합니다. 이해가 안되면 멈추거나 물어보고 하세요."*

**default 의무**:
1. **모든 코드 작업 (Edit/Write/MCP `*_sql` INSERT/DELETE 등) 직전 사전 사고 의무** — 즉각 도구 호출 X. 다음 3 질문 자문 의무:
   - (a) 본 변경의 **목적** 이 사용자 의도와 정합한가? (요청 발화 vs 내 해석)
   - (b) 본 변경이 영향 범위 (다른 파일 / 운영 / 테스트) 를 **모두 인지** 한 상태인가?
   - (c) 본 변경 후 **검증 방법** 이 명확한가? (테스트 / smoke / 사용자 의무)
2. **이해 부족 시 즉시 중단**:
   - 사용자 의도 모호 → "본 작업 의도 = X 로 해석. OK?" 1줄 사전 확인 (정책 1 옵션 표 또는 단순 yes/no)
   - 영향 범위 불명 → 영향 범위 조사 후 보고 → 사용자 결정 회신 의무
   - 검증 방법 부재 → 회귀 가드 추가 의무 또는 사용자 명시 검증 요청
3. **위반 시 회복**: 사전 사고 누락 후 진행 시 사용자 발견 → 즉시 사과 + 영향 범위 분석 + revert 결정 회신.

**위임 분류 3-tier 통합** (`feedback-architecture-decision-pre-confirm.md`):
- **High (사전 확인 의무)** = 정책 15 적용 (DB 스키마 / API / 권한 / 데이터 모델) — 옵션 표 + 사용자 1줄 명시
- **Medium (자율 + 보고)** = 정책 15 적용 (헬퍼 함수 / 정책 본문 진화) — Claude 사전 사고 후 자율 진입 + PR 본문 자율 판단 보고
- **Low (즉시 진입)** = 정책 15 면제 OK (회귀 가드 / docstring / typo) — 단 (b)/(c) 자문은 의무

**검증 사례 (사이클 69)**:
- ✅ 5+1 에이전트 정밀 검증 시 cross-verify 의 false-positive 1건 차단 = 사전 사고 의무 효과 (Claude 단독 진행 시 잘못된 fix 적용 위험 차단)
- ✅ PR # 카운트 산식 모호 → 실측 검증 후 정정 = 영향 범위 인지 의무 적용

**Why**: 사이클 64~69 누적 회고 결과 — Claude 의 "즉각 도구 호출" 패턴이 사용자 위임 신호 (75%) 와 결합 시 잘못된 결정 누적 위험. 사전 사고 1단계로 75% → 0% 위임 위험 차단 (사이클 64 → 사이클 66 검증 효과).

**How to apply**: 모든 Edit/Write/Bash (destructive) 도구 호출 직전 1줄 자문 → 명확하면 진행, 불명하면 사용자 회신 대기. PR 본문 §"자율 판단 보고" (정책 3) 페어.

#### 정책 16 신설 (2026-05-04 사이클 70 진입): **코드 단순화 default + 가독성 우선 (정확성/성능 유지)**

사용자 발화 (2026-05-04, 사이클 69 머지 후): *"코드를 단순화 하여 작성을 해주세요. 단 정확성과 성능은 유지가 되야합니다. 되도록 코드는 이해하기가 쉽게 작성을 해주세요."*

**default 의무** (5 원칙 — 우선순위 순):
1. **정확성 우선** — 단순화가 동작 변경/회귀 유발 시 단순화 포기 (회귀 0 default)
2. **성능 유지** — 단순화로 hot-path latency / memory 증가 시 단순화 포기 (실측 의무)
3. **가독성 우선** — 위 두 조건 충족 시 가독성 ↑ 패턴 채택
4. **최소 추상화** — 시스템 프롬프트 "Don't add features, refactor, or introduce abstractions beyond what the task requires" 강화
5. **🔴 토큰 비용 효율** (사이클 72 추가 — 사용자 의도 정합) — 운영 토큰 사용량 ↓ + 분산 + caching 활용. 단, **AI 리뷰 품질 영향 영역 = 단순화 금지** (사용자 명시 제외 — 아래 명시 제외 영역). **caching 4 단계 활성화 사례 (사이클 63 → 74 — 사이클 75 진화)**: 1단계 인프라 도입 (사이클 63 #218 — `build_cached_system_param`) → 2단계 baseline 정확화 (사이클 72 #242 — cache 비용 모델 + `get_cache_stats` + silent fallback streak) → 3단계 활성화 (사이클 74 #247 — 1024 토큰 패딩 + Haiku 모델 분기) → 4단계 호출 빈도 제한 (사이클 74 #248 — DB 캐싱 1h TTL). 운영 baseline 측정 의무 (1주 후 cache_hit_rate / silent_cache_fallback streak 검증).

**🚫 명시 제외 영역 (사용자 결정 — AI 리뷰 품질 보존 의무)**:
- ❌ `build_review_prompt` 토큰 예산 8000 → 축소 (사이클 72 사용자 명시 보류 — 품질 저하 원치 않음)
- ❌ `review_guides/` 50개 언어 Tier1 full ~500 토큰 압축 (사이클 72 사용자 명시 보류 — 체크리스트 ↓ → 리뷰 깊이 ↓ 위험)
- ✅ 진행 OK 영역 (사이클 72 검증): `review_code` prompt caching = **이미 100% 적용** (사이클 63 #218 — `src/analyzer/io/ai_review.py:79,89`) — multi-block 확장 (system + lang_guides 분리) 만 Phase 3 후보 (단 `build_review_prompt` 시그니처 변경 = High tier 사전 확인 의무) / 모델 분기 (Haiku/Sonnet/Opus) — Phase 2 (1주 운영 데이터 후 결정, AI 리뷰 품질 영향 = High tier) / 동일 SHA 결과 재사용 = **이미 100% 적용** (3-tier dedup — `src/worker/pipeline.py:178-181`) / Insight narrative 호출 빈도 제한 — Phase 2 (DB 캐싱 1h TTL 후보) / **cache hit rate 모니터링 인프라 = 사이클 72 PR 2 (#242) 도입** (`src/shared/claude_metrics.py::get_cache_stats` + cache 비용 모델 정확화 + silent fallback streak WARNING)
- 신규 토큰 절약 영역 도입 시 사용자 사전 확인 의무 (정책 15 + High tier — `feedback-architecture-decision-pre-confirm.md` 페어)

**default 적용 패턴**:
- **변수명** = 의도 명시 (예: `data` X → `repository_user_id` ○)
- **함수 시그니처** = 인자 ≤ 5 (R0913 임계 default)
- **함수 본문** = 단일 책임 (R0915 / R0912 임계 default)
- **타입 힌트** = 모든 public 함수/메서드 의무 (이미 default — 정책 16 강화)
- **주석** = 시스템 프롬프트 default (WHY 비명확 시만) + CLAUDE.md L7~L18 한국어/영어 병행 default
- **early return** = 중첩 깊이 ≤ 3 (R0911 임계 default)

**금지 패턴** (단순화 위반):
- ❌ 추상 베이스 클래스 / Protocol — 사용처 ≥ 3 일 때만 도입 (`feedback-architecture-decision-pre-confirm.md` Medium tier 기준 페어)
- ❌ Generic 타입 매개변수 — 사용처 ≥ 3 시점 도입
- ❌ 메타클래스 / 데코레이터 체인 — 표준 라이브러리 (functools/contextlib) 외 자체 작성 금지 (사용자 명시 시만 OK)
- ❌ "다음 확장 대비" 분기 — 현재 요건만 구현 (정책 7 강화 응집 단위 부합)

**리뷰 체크 포인트** (PR 작성 시 자가 검토 의무):
1. **줄 수 감소 가능?** — 동일 동작을 더 짧게 표현 가능 시 적용 (단 가독성 ↓ 시 보존)
2. **분기 합치 가능?** — `if/elif/else` 가 동일 결과 분기 시 합치
3. **중간 변수 제거 가능?** — 단일 사용 임시 변수 inline 가능 시 적용
4. **표준 라이브러리 활용 가능?** — `itertools / collections / functools / dataclasses` 우선 (자체 구현 금지)

**검증 사례** (사이클 64~67 — 정책 16 사후 검증):
- ✅ Phase 3 PR 5 (#223) RLS 격리 헬퍼 2건 (`_apply_*_user_filter`) — 함수 ≤ 10 줄 + 단일 책임 + 인자 3 (정합)
- ✅ 사이클 66 #228 RLS middleware ASGI 직접 작성 (BaseHTTPMiddleware 우회) — 추상화 0 + 흐름 직선 (정합)
- ⚠️ 사이클 64 회고 R0914 결정 트리 (CLAUDE.md L988~) — `dashboard_kpi` / `frequent_issues_v2` user_id 인자 추가 시 R0914 inline disable 채택 (헬퍼 추출 over-engineering 회피) — 정책 16 default 사례

**Why**: 사이클 65~67 정합성 cleanup 누적 = 100+ 줄 변경 / 10+ 패턴 — 코드량 ↑ 자체가 미래 회고 부담. 단순화 default 로 다음 cleanup 부담 ↓.

**Why (5 원칙 추가 — 사이클 72)**: 사이클 70~71 진행 후 사용자 의도 검증 = "토큰 비용 효율" 이 본래 목적이었음 (사이클 70 정책 15 위반 사례 — Claude 가 "단순화" 의도 모호 검증 안 함). 사이클 72 회고 정정으로 5번째 원칙 신설. **운영 Anthropic API 비용 ↓** 가 실 가치 — 가독성 단순화는 부가 효과.

**How to apply**: Edit/Write 도구 호출 직전 정책 15 사전 사고와 페어 — "이 변경이 가장 단순한 형태인가?" + "토큰 비용 영향은?" 2 자문 의무. CI lint (pylint R0911~R0917) 가 1차 가드, PR 본문 §"자율 판단 보고" 의 자가 리뷰 4 체크포인트 + 토큰 영향 추정이 2차 가드.

---

### 작업 시작 전 필수 체크리스트 (매 작업마다)

모든 작업 착수 전 아래 다섯 가지를 순서대로 확인한다. 30초면 충분하다.

```bash
gh run list --limit 3                                       # CI status (기존 vs 신규 실패 구분)
gh api repos/xzawed/SCAManager/code-scanning/alerts \      # Code Scanning open alert 카운트 (정책 14)
  --jq '[.[] | select(.state=="open")] | length'            # CI/auth 부재 시 GitHub Security 탭 직접 확인
ls ~/.claude/projects/-workspaces-SCAManager/memory/ | \   # 신규 fixture/테스트/패턴 작성 전 메모리 grep
  grep -E "pytest-|test-|feedback-"                         # 해당 영역 메모리 본문 read 후 default 적용 의무
ls docs/reports/ | tail -1                                  # 직전 회고 보고서 회신 회수 확인 (정책 9 강화 페어)
git status                                                  # 미커밋 변경 없는지 확인
git checkout -b <브랜치명>                                  # 브랜치 생성 (main 직접 커밋 금지)
```

**메모리 인덱스 (29건 = 활성 27 + deprecated 2)**: 상세 = `~/.claude/.../memory/MEMORY.md`. 카테고리 5종:
- 🌐 환경 (3) / 🧪 TDD/CI (7) / 🤝 협업 (7) / 📜 정책 페어 (4) / 🛠️ 기술 패턴 (6) / ⚰️ Deprecated (2 — 사이클 64/66 머지 완료)
- 신규 메모리 추가 시 MEMORY.md 인덱스 + 카테고리 카운트 동기화 의무 (사이클 75 분류 default).

GitHub Code Scanning 점검 detail 절차 + 운영 통합 = `docs/runbooks/operational-smoke-checks.md` §9 (정책 14).
메모리 grep 의무 detail = 메모리 `~/.claude/.../memory/feedback-tdd-red-full-suite-validation.md` (Phase 3 PR 4 CI #428 학습).

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
- **완료 시 필수 5-step**: 작업이 완료되면 반드시 ① 커밋 → ② PR 생성(`gh pr create`) → ③ `git push` → ④ `docs/STATE.md` 수치 갱신 → ⑤ **CLAUDE.md 아키텍처 섹션 동기화** (신규 파일 추가·삭제·이름 변경 시 `src/` 트리와 `### 핵심 데이터 흐름` 내 언급 갱신) 를 순서대로 수행한다. 예외 없음.
- **README.md 배지 동기화**: 테스트 수·pylint·커버리지 수치가 바뀌면 `README.md` 14~18줄 배지도 함께 갱신한다. 수치 출처는 항상 `docs/STATE.md`.
- **CLAUDE.md 아키텍처 동기화 체크리스트**: `src/` 하위에 파일 추가 시 아래 항목을 순서대로 확인한다. 누락 시 다음 Phase 착수 전 반드시 보완한다. **전례 3건**: (1) Phase 11에서 6개 파일 추가 후 CLAUDE.md에 5개 누락 → 3-에이전트 감사에서 발견, PR #73. (2) 2026-05-01 UI 감사 cleanup PR-D1 — `_merge_attempt_states.py` (Phase 3 PR-B1 도입분) + `static/vendor/chart.umd.min.js` (UI 감사 Step C) 트리 누락 → 5-에이전트 정합성 감사에서 발견. (3) 2026-05-05 사이클 78~82 5+1 cross-verify — 사이클 79/80/82 신규 환경변수 4건 (`CLAUDE_INSIGHT_MODEL` / `SAAS_MULTITENANT_DISABLED` / `SAAS_ADMIN_EMAILS` / `SECURITY_AUTO_PROCESS_DISABLED`) `docs/reference/env-vars.md` 미등재 → 6차 cross-verify 발견. `env-vars.md` sync 의무 본 체크리스트에 신규 추가.

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

## 주의사항 (카테고리별 — `.claude/rules/<area>.md` path-scoped)

> **사이클 85 정리**: 9 카테고리 본문은 `.claude/rules/<area>.md` 로 분리 (Anthropic 공식 path-scoped rules 패턴). Claude Code 가 해당 영역 파일 작업 시 자동 로드. 매 세션 의무 read 부담 0.

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

최신 수치는 [docs/STATE.md](docs/STATE.md) 참조 — 단위 테스트 2669개 | 통합 129개 | E2E 96개 | pylint 10.00 | 커버리지 95% | SonarCloud QG OK · Security A · Reliability A · Maintainability A · Tier1 정적분석 10종 · Observability (Claude metrics + stage timing + MergeAttempt — Sentry 통합은 사이클 85 #317 폐기 완료) · AI 점수 피드백 루프 · Settings Minimal Mode · Onboarding 3단계 튜토리얼 · **사이클 60~80 historical**: [`docs/cycle-history.md`](docs/cycle-history.md) (archive). **직전 5 사이클 (2026-05-05 ~ 2026-05-06)**:

- **사이클 81 (모바일 Phase 1 MVP, 2026-05-05)** — PWA manifest + dashboard 모바일 KPI 우선순위 + settings 모바일 + form sweep (4 PR #262~#265). 통합 84→118 (+34 회귀 가드). `<details>` Progressive Disclosure = Phase 2 보류 (High tier).
- **사이클 82 (Tier B 묶음 + NEW-P0-1, 2026-05-05)** — alembic dialect 헬퍼 추출 (사용처 12) + 메모리 신설 2건 + Telegram 봇 차단 silent skip (NEW-P0-1) (#272/#274). 메모리 25→27.
- **사이클 83 (Tier B 11건 정책 진화 묶음, 2026-05-05)** — 정책 9 완화 + 정책 8 진화 (단일 작업일 ≥ 5 dispatch 사전 확인) + 정책 3 ⚠️ 마커 정량 기준 + 정책 1 진화 + 정책 5 cross-reference 강화 + 메모리 cross-reference (#279).
- **사이클 84 (다국어 i18n 18 PR + 회고 + Tier B, 2026-05-05~06)** — Phase 1~5 18 PR (#283~#304) — 영어/한국어/일본어 + UI/알림/AI 리뷰 전 영역. 단위 2236→2709 (+473) | 통합 118→129 | E2E 82→96. 회고+sync (#306) + Tier B Q3+Q5 (#307) + Tier B Q1+Q2+Q4 (#308) — 정책 1 진화 강화 (≥ 10회 빠른 진행 신호) + 정책 8 강화 (dispatch vs invocation 구분) + 메모리 신설 2 (i18n locale fallback + 메모리 카운터 패턴). 메모리 27→29.
- **사이클 85 (Sentry 제거 + GitHub 정리 + CLAUDE.md Anthropic 200줄 정합 정정, 2026-05-06)** — Sentry 통합 완전 폐기 (40 테스트 + 105 LOC + 의존성 제거). GitHub 정리 62 branch 일괄 삭제. **CLAUDE.md cleanup**: 5+1 다중 에이전트 검토 (Anthropic 권고 6배 초과 → 3.5배) → 권장 default Q1=🅒 + Q2=🅐 + Q3=🅑 + Q4=🅑 채택 → src/ 트리 → `docs/architecture.md` / 9 카테고리 → `.claude/rules/<area>.md` (path-scoped, Anthropic 공식 패턴) / tail entry 사이클 60~80 → `docs/cycle-history.md` / Railway 배포 → `docs/runbooks/railway.md` / 점수 체계 → `docs/reference/scoring.md` / 정책 진화 history archive 영역 신설 → `docs/policies/history.md` (사이클 86+ 점진적 작업 default). LOC 1271 → ~700 (-45%) / 토큰 ~57K → ~25K (-56%).
