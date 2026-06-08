# SCAManager 사용자 협업 정책 본문 detail (사이클 88+ active archive)

> CLAUDE.md tail entry / 정책 본문 detail 분리본 (사이클 88 #338 진입, 2026-05-06).
> 본 파일 = **활성 정책 본문 detail** (default rule 외 검증 사례 / Why / How to apply / 금지 패턴 등).
> CLAUDE.md 본문 = 정책 N 표제 + 핵심 default rule 1줄 + 진화 default 1~2줄 + 본 파일 reference link.
> 정책 진화 history (이전 사이클 진화 entry) = `.claude/policies/history.md` (사이클 85 #320 + 사이클 86 #321 분리).

<a id="정책-2"></a>

## 정책 2: PR 본문 "🔍 사용자 검증 필요" 섹션 의무

이전: "tests pass" 만 적힘 → 사용자가 무엇을 봐야 할지 모름.
다음: 시각/운영 확인 항목 1~3개 명시.

```markdown
## 🔍 사용자 검증 필요
- [ ] Railway 배포 후 `/repos/{owner}/{repo}/settings` 데스크탑 + 모바일 확인
- [ ] claude-dark 테마 토글 시 카드 헤더 정상 표시
- [ ] (있다면) 운영 사고 보고
```

---

<a id="정책-10"></a>

## 정책 10: PR 직접 생성 의무 (URL 안내 X, 자동 생성 ○)

사용자 발화 (2026-05-02): *"앞으로의 작업은 PR 을 직접 생성을 부탁드립니다."*

**default 6-step 흐름**: `git checkout main && pull` → `checkout -b <type>/<scope>` → 작업+commit → `push -u origin` → **PR 직접 생성** (gh CLI / GitHub API / URL 폴백) → URL 보고.

**구현 옵션** (환경별 우선순위 — gh CLI > API + GITHUB_TOKEN > URL 안내 폴백). PR 생성은 사용자 수동 위임 금지 (정책 7 PR 단위와 모순).

🔴 **현재 SCAManager 환경**: gh CLI v2.89.0 설치 완료 + xzawed 계정 인증 완료 → **옵션 🅐 (gh pr create) default 운영**.

**기본 PR body 템플릿**: §Summary + §🔍 사용자 검증 필요 (정책 2) + §자율 판단 보고 (정책 3) + §🔍 Codex 검증 의뢰 (정책 18) + 🤖 Generated with [Claude Code](https://claude.com/claude-code) 푸터.

```markdown
## 🔍 Codex 검증 의뢰 (push 전, 정책 18)
- [ ] Codex 검증 의뢰 완료 — push 전 Codex OK 회신 대기 중
```

> 🔴 **누락 시**: 다음 응답에서 회복 의무 (자성 1줄 + 의뢰 1줄). 사이클 99 PR #441/442/443 전체 누락 → 본 항목 신설 (cross-verify 실측 확인). 예외: 사용자 명시 `mutual 생략 OK` 발화 시.

**fix-up commit 형식 default** (사이클 64 회고 P1): PR 머지 전 CI fail / 회귀 발견 시 = **동일 PR 브랜치 추가 commit** (별도 PR X — 정책 7 강화 응집 단위 부합). commit message prefix = `fix(<feature>-ci):`. PR body §자율 판단 보고에 사유 명시 의무. 머지 후 발견 시 = 별도 `fix/<feature>-<bug>` PR.

---

<a id="정책-7"></a>

## 정책 7: 위반 시 회복

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

---

<a id="정책-11"></a>

## 정책 11: PR 본문 8 조합 시각 체크리스트 템플릿

**적용 대상 파일**: `src/templates/*.html` / `src/static/**/*.css` / `base.html` `<style>` 블록 / 신규 시각 컴포넌트

```markdown
## 🚨 Claude 시각 검증 불가 — 사용자 의무 (정책 11)

본 PR 은 UI/시각 변경 포함. Claude 는 정적 코드만 검증 가능 — 다음 8 조합 시각 정합성은 사용자 직접 확인 부탁드립니다:

- [ ] dark 테마 데스크탑 (1440px+)
- [ ] light 테마 데스크탑
- [ ] pastel 테마 데스크탑
- [ ] catppuccin 테마 데스크탑
- [ ] dark 테마 모바일 (375px ~ 767px)
- [ ] light 테마 모바일
- [ ] pastel 테마 모바일
- [ ] catppuccin 테마 모바일

특히 검증 필요 (변경 영역 한정):
- {변경 영역 설명}
```

**표준 8조합 체크리스트 코드블록 (UI 변경 PR 본문 필수)**:
```
| 테마 | 데스크탑 | 모바일 |
|------|---------|--------|
| dark | [ ] | [ ] |
| light | [ ] | [ ] |
| pastel | [ ] | [ ] |
| catppuccin | [ ] | [ ] |
```

---

## 정책 11 강화 (사이클 62 P0 OAuth 사고 후속): 인증 flow 검증 추가

🔴 **진화 default 요약**: 인증/외부 통합 변경 PR 시 8 조합 시각 체크리스트 + **인증 flow 4 endpoint 종단간 검증** 의무 — `/login` 200 + `/auth/github` 302 + `/auth/callback` redirect + `/auth/logout` redirect. 상세: [.claude/policies/history.md#정책-11-강화](history.md#정책-11-강화).

---

<a id="정책-12"></a>

## 정책 12 신설 (2026-05-02 Phase 1+2 회고 후속): MCP scope 제한 의무

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

---

<a id="정책-13"></a>

## 정책 13 신설 (2026-05-02 P0 OAuth 사고 후속): 운영 endpoint smoke check 의무

회고 P0 #4 자기 예언 ("운영 사고 0 = 운 + Copilot Autofix + Railway CI") 무시 → 본 사고 발생. 사고 회고: [`docs/reports/2026-05-02-oauth-redirect-uri-incident.md`](../reports/2026-05-02-oauth-redirect-uri-incident.md).

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

---

<a id="정책-14"></a>

## 정책 14 신설 (2026-05-03 사이클 62 후속): GitHub Code Scanning 알림 운영 체크 의무

사용자 발화 (2026-05-03): *"시큐리티에서 감지하는 내용도 앞으로 프로젝트 운영시 체크사항으로 부탁드립니다."*

회고 배경: GitHub Security 탭의 Code Scanning Alert #324 (`'break' or 'return' statement in finally`) + #325 (`Unused import`) 직접 확인 (참조 메타 Issue #213 / #214 는 단순 추적 수단). SCAManager 자체 정적분석 (pylint / flake8 / bandit) 은 통과 (위반 0건) 하지만 GitHub Security 탭 (CodeQL 또는 추가 도구) 이 별도 룰셋으로 감지하는 영역이 있음. **빌드 통과 + SCAManager lint 통과 ≠ Security 탭 0 alert**. 외부 가시성 부재 시 alert 누적 → 운영 책임 이전 위험.

**default 의무**:
- **작업 시작 전 30초 체크리스트** (CLAUDE.md §작업 시작 전 필수 체크리스트) 에 GitHub Security 탭 Code Scanning open alert 카운트 1줄 추가 (이미 적용)
- **매 사이클 종료 시** (또는 Phase 종료 시) — 정책 13 smoke check 와 페어로 GitHub Security 탭 등록된 alert 직접 검토 (Issue 추적 수단 의존 X — Security 탭 자체가 단일 진실 소스)
- **GitHub Security 탭에 신규 alert 등록 시** — 분류 처리 (1회 의무):
  - (a) 실제 위반 → 코드 fix PR (정책 7 단위)
  - (b) false-positive → GitHub Security 탭에서 dismiss + 사유 기록
  - (c) 의도된 패턴 → suppress 룰 추가 + 회고에 사유 명시

**실행 방법**:
- gh CLI 가용 시: `gh api repos/<owner>/<repo>/code-scanning/alerts --jq '[.[] | select(.state=="open")] | length'`
- gh 부재 시: 사용자 GitHub `Security → Code scanning alerts` 탭 직접 확인 → Claude 에 카운트 + alert 제목 공유 의무 (gh CLI 미사용 환경 폴백 패턴)
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

---

<a id="정책-15"></a>

## 정책 15 신설 (2026-05-04 사이클 70 진입): 코드 작업 (add/edit/delete) 전 사전 사고 의무

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

---

<a id="정책-16"></a>

## 정책 16 신설 (2026-05-04 사이클 70 진입): 코드 단순화 default + 가독성 우선

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
- ✅ 진행 OK 영역 (사이클 72 검증): `review_code` prompt caching = **이미 100% 적용** (사이클 63 #218 — `src/analyzer/io/ai_review.py:100-107`) — multi-block 확장 (system + lang_guides 분리) 만 Phase 3 후보 (단 `build_review_prompt` 시그니처 변경 = High tier 사전 확인 의무) / 모델 분기 (Haiku/Sonnet/Opus) — Phase 2 (1주 운영 데이터 후 결정, AI 리뷰 품질 영향 = High tier) / 동일 SHA 결과 재사용 = **이미 100% 적용** (3-tier dedup — `src/worker/pipeline.py:206-218`) / Insight narrative 호출 빈도 제한 — Phase 2 (DB 캐싱 1h TTL 후보) / **cache hit rate 모니터링 인프라 = 사이클 72 PR 2 (#242) 도입** (`src/shared/claude_metrics.py::get_cache_stats` + cache 비용 모델 정확화 + silent fallback streak WARNING)
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
- ⚠️ 사이클 64 회고 R0914 결정 트리 (.claude/rules/testing.md §R0914 too-many-locals cleanup 결정 트리) — `dashboard_kpi` / `frequent_issues_v2` user_id 인자 추가 시 R0914 inline disable 채택 (헬퍼 추출 over-engineering 회피) — 정책 16 default 사례

**Why**: 사이클 65~67 정합성 cleanup 누적 = 100+ 줄 변경 / 10+ 패턴 — 코드량 ↑ 자체가 미래 회고 부담. 단순화 default 로 다음 cleanup 부담 ↓.

**Why (5 원칙 추가 — 사이클 72)**: 사이클 70~71 진행 후 사용자 의도 검증 = "토큰 비용 효율" 이 본래 목적이었음 (사이클 70 정책 15 위반 사례 — Claude 가 "단순화" 의도 모호 검증 안 함). 사이클 72 회고 정정으로 5번째 원칙 신설. **운영 Anthropic API 비용 ↓** 가 실 가치 — 가독성 단순화는 부가 효과.

**How to apply**: Edit/Write 도구 호출 직전 정책 15 사전 사고와 페어 — "이 변경이 가장 단순한 형태인가?" + "토큰 비용 영향은?" 2 자문 의무. CI lint (pylint R0911~R0917) 가 1차 가드, PR 본문 §"자율 판단 보고" 의 자가 리뷰 4 체크포인트 + 토큰 영향 추정이 2차 가드.

---

<a id="정책-17-why-how"></a>

## 정책 17: 문서 cleanup Why / How to apply (자가 검토 4 자문)

**Why**: SCAManager CLAUDE.md = 단순 docs 가 아닌 **운영 의무 영역** (16+ 정책 + Hook 신뢰 + 5-step 완료 + 30초 체크리스트). Anthropic 200줄 hard target 적용 시 detail 손실 → 행동 회귀 위험. 안정성 보존 우선이 사용자 의도 정합 — 사이클 88 Phase A 검증 (정책 12~16 default rule 보존 + detail external = 행동 영향 0).

**How to apply**: cleanup PR 작성 시 자가 검토 4 자문 — (a) default rule + 진화 default 보존? (b) 행동 영향 0 검증 가능? (c) 단계 분할 + 단계별 검증 의무 적용? (d) 분리 위험 영역 사용자 사전 확인 받았나? 모두 ✅ 시 진행, 1 조건이라도 ❌ 시 보류 또는 사용자 옵션 표.

---

<a id="정책-17-5번째-default"></a>

## 정책 17 5번째 default (사이클 92 신설): 누적 결함 정기 검증 의무

사이클 89 정기 5+1 다중 에이전트 검증 (#349 Round 1+2+3) 시 사이클 74/84 누적 결함 발견 (E2E i18n hardcode 3건 + integration fixture sync 누락 1건) — 시간차 결함 패턴.

**default 의무**:
- **트리거 조건**: 단일 작업일 ≥ 18 PR 영역 도입 (예: 사이클 84 i18n 18 PR) + **≥ 5 사이클 경과** 후 정기 5+1 다중 에이전트 검증 default 진입.
- **검증 영역**: 단위 + 통합 + E2E + 코드 품질 (pylint/flake8/bandit) + 기능 정확성 + 보안 (Round 1 6 영역).
- **점수 환산 + 재검증** (Round 2 cross-verify 단위 분포 실측 의무 — 정책 8 진화 (3) 페어).
- **수행 계획** (Round 3 — Tier A/B 분류 + 사용자 결정 옵션 표).

**정량 기준**:
- 단일 작업일 ≥ 18 PR 영역 도입 (사이클 84 i18n / 사이클 86 dependabot 8 자동 등 큰 영역 도입)
- 직전 정기 검증 후 ≥ 5 사이클 경과 (또는 누적 ≥ 50 PR)
- **둘 중 하나 충족 시 트리거** — 사용자 명시 결정 의무 X (정책 9 완화 default 적용 영역 — Medium tier)

**정책 8 진화 (cross-verify) 와 차별점**:
- 정책 17 5번째 = **정기 검증 트리거 (시간/PR 기반)** — Phase 종료 시점 또는 누적 임계 도달 시
- 정책 8 진화 = **매 회고 cross-verify 트리거 (사이클 단위)** — 매 회고 시 5+1 default + cross-verify ROI 정량 명시 의무
- 시점·대상 차별 명확 (혼동 시 양쪽 적용 = 토큰 낭비 — 정책 16 5번 페어)

**검증 사례 (사이클 89)**:
- 사이클 84 i18n 18 PR + 사이클 74 InsightNarrativeCache 도입 → 사이클 89 정기 검증으로 누적 결함 발견 (E2E i18n hardcode 3건 + integration fixture metadata sync 누락 1건)
- ROI 양성 검증 — 정기 검증 없이는 운영 영역 시간 누적 결함 위험 ↑

**Why**: 단일 작업일 ≥ 18 PR 영역 도입 시점 PR push 직전 검증으로는 시간차 결함 차단 불가 (E2E 영역 / fixture sync 영역). 정기 검증 default = 시간 비용 (5+1 dispatch) vs 운영 영역 누적 결함 회피 가치 (사고 차단) 균형 default.

**How to apply**:
- 사이클 종료 시점 자가 검토 — "직전 정기 검증 후 ≥ 5 사이클 경과? 또는 단일 작업일 ≥ 18 PR 도입 영역 존재?"
- 트리거 충족 시 = 사이클 89 패턴 정합 (Round 1+2+3 다중 에이전트 회의 + Tier A 즉시 정정 + Tier B 사이클 N+1+ 점진)
- 트리거 미충족 시 = default 정책 8 매 회고 cross-verify 적용 (정책 17 5번째 default 미적용)

**Cross-ref**:
- 메모리 `feedback-pr-push-direct-validation.md` 사이클 89 진화 (시간차 결함 누적 행 추가) 페어
- 메모리 `feedback-fixture-model-sync-discipline.md` (사이클 89 신설) 페어
- 정책 8 진화 (3) cross-verify Round 2 단위 분포 실측 의무 페어

---

<a id="정책-18"></a>

## 정책 18: Claude ↔ Codex 양방향 mutual 검증 의무 (사이클 93 신설)

사용자 발화 (2026-05-09, 사이클 93 CI 분석 사고 직후 — 2회 진화):
1차: *"앞으로 모든 작업의 후처리는 Codex가 검증 검토를 수행합니다. Claude 단독으로 수정 및 검증 검토에서 끝내지 않고 Codex의 동의까지 완료되야 마무리 된것으로 간주 하겠습니다."*
2차 (양방향화): *"Claude 또는 Codex가 작업을 수행시 반드시 두 LLM모델이 OK확인을 받아야 통과합니다. 상호간의 작업 내용을 검증 검토를 수행합니다. Claude 도 Codex도 이 내용은 반드시 숙지합니다."*

### 양방향 default 흐름 (대칭, push 전 검증 — 사이클 94 정정)

🔴 **사이클 94 사용자 정정 (2026-05-10)**: *"Codex에게 검토를 받으려면 PR을 올리기 전에 수행을 해야합니다. 그리고 현재는 PR이 이미 머지가 되었으므로 다음 사이클 진입을 해주세요."*

→ **검증 = PR push 전 수행 의무**. 사이클 93 안티패턴 (PR #366/#368/#369/#370 = push 후 의뢰 명시 = mutual 의도 정합 X) 학습.

| 단계 | Claude 작업 → Codex 검증 | Codex 작업 → Claude 검증 |
|------|---------------------------|--------------------------|
| 1. 작업 | Claude 수정/구현/회귀 가드 (로컬 commit 까지 — push X) | Codex 반복 구현/테스트/리팩토링 (로컬 commit 까지 — push X) |
| 2. 1차 검증 | Claude test + lint + smoke | Codex 자가 검증 |
| 3. **검증 의뢰 의무 명시 (push 전)** | "🔍 Codex 검증 의뢰 (push 전)" 1줄 — 변경 본문 + commit body + 로컬 검증 결과 첨부 | "🔍 Claude 검증 의뢰 (push 전)" 1줄 |
| 4. 검증 결과 | Codex OK / NG 회신 | Claude OK / NG 회신 |
| 5. NG 시 재진입 | Claude 수정 → 3 단계 반복 (≤ 3회) | Codex 수정 → 3 단계 반복 (≤ 3회) |
| 6. **상대 OK → push + PR 생성** | Codex OK 후 `git push` (사용자 머지 영역) | Claude OK 후 `git push` (사용자 머지 영역) |

### 운영 흐름 (현 SCAManager Codespaces 환경 default)

- Claude 가 변경 본문 작성 + 로컬 commit 까지 (`git push` 보류)
- Claude 응답 = "🔍 Codex 검증 의뢰 (push 전)" 1줄 + 변경 본문 / commit body / `make test-fast` 결과 첨부 → 사용자가 Codex 환경 (Codex CLI / Codex Web / VSCode plugin) 에서 검토 의뢰 → 결과 채팅 회신
- Codex OK 회신 → Claude `git push` + PR 생성 (사용자 머지 영역)
- Codex NG 회신 → Claude 수정 plan 옵션 표 (정책 1) + 사용자 confirm + 재진입 (회기 ≤ 3)

### 사이클 93 안티패턴 영역 (학습 보존)

사이클 93 본 정책 신설 직후 모든 PR (#366 / #368 / #369 / #370) = push 후 Codex 의뢰 명시 패턴 적용 → **사용자 정정 영역 (사이클 94)**. 사이클 93 메모리 + AGENTS.md + CLAUDE.md 정책 18 본문 = "Codex 검증 의뢰 의무" 만 명시 → 시점 (push 전 vs push 후) 명시 부재 → Claude 자율 해석 = push 후. 사이클 94 정정 = push 전 의무 명시 강화.

### 환경 통합 (현 SCAManager 기준)

- 본 환경 (Claude Code in Codespaces) = OpenAI Codex CLI / npm / OPENAI_API_KEY 모두 부재 검증 (사이클 93 환경 검증)
- **default 시나리오 A** = 사용자가 별도 환경 (Windows 호스트 / Codex Web / VSCode plugin)에서 Codex 실행 → 결과 채팅 회신
- **사용자 회신 형식 3종 표준화**: `Codex OK` / `Codex NG: <사유>` / Codex 출력 본문 채팅 붙여넣기
- **시나리오 C 보류** (Claude 가 본 환경에 nodejs+npm+Codex CLI 설치) = 사용자 사전 확인 의무 (정책 15 High tier — apt 권한 + OPENAI_API_KEY 발급 의향 + 정책 7 PR 단위 위반 위험)
- **자동화 권장 영역** (≥ 2):
  1. PR template `[ ] Codex OK 회신 받음` 체크박스 (즉시 — 위험 0)
  2. Codex GitHub App + GitHub Actions workflow `codex-mutual-review.yml` (사이클 94+ 옵션, 사용자 confirm 후)
- ⚠️ **`.codex/hooks.json` Windows hard-coded path** — `f:\DEVELOPMENT\...` 경로 → Codespaces (Linux) 환경에서 hook 0% 발화. mutual 자동화 검토 시 사전 인지 의무 (사이클 93 관점 5 발견).
- 🔴 **토큰 만료/런타임 오류 fallback 예외 (사이클 161 회고 신설)** — Codex 액세스 토큰 만료(`refresh token already used`)·샌드박스 제약·CLI 런타임 오류로 mutual 자동 검증 불능 시 = **사용자 명시 승인 하 Claude 직접검증 fallback** 정당 (정책 18 예외 "사용자 직접 결정 영역" + 사이클 119/125/161 전례). fallback PR 본문에 ① 만료/오류 사유 ② 사용자 승인 ③ 직접검증 근거(적대적 분석·TDD·lint) 3종 명시 의무.
  - 🔴 **복구 강제 가드 (mutual 2-layer 가치 회귀 차단)** — 동일 fallback 이 **≥ 2 사이클 또는 ≥ 5 PR 연속** 시 = 다음 세션 진입 전 `codex logout; codex login` 복구를 **사용자 1줄 확인으로 강제 트리거** (메모리 [[feedback-codex-post-validation-mandatory]] + [[integrity-audit-session]] 재개법 "codex login 권장" → "복구 강제"로 강화). mutual = 외부 LLM 다양성 핵심 가치이므로 장기 1-layer 운영 금지.

### 17 정책 cross-reference 표 (CLAUDE.md 정책 18 본문서 이관 — docs reorg Phase 3d)

mutual 검증이 다른 정책과 맺는 충돌/페어 7건:

| 정책 | mutual 페어 영역 |
|------|----------------|
| 3 (자율 판단) | 자율 판단 = mutual OK 받은 영역으로 한정 |
| 5 (사이클 종료) | 종료 신호 = 두 LLM 동의 의무 구성요소 (3 조건 AND) |
| 7 (PR 단위) | mutual = **push 전** Codex 검증 OK 후 push (사이클 94 정정) — push 후 의뢰 안티패턴 |
| 8 (회고 5+1) | 5+1 (Claude 내부) ↔ mutual (외부 LLM) 2-layer 격리 — cross-verify 6차 생략 시도 mutual 별도 의무 |
| 10 (PR 직접 생성) | Codex/Claude 생성 PR = **push 전 상호 검증 OK 후 push** (사이클 94 정정 — Codex NG #2 학습) — push 후 의뢰 안티패턴 |
| 12 (MCP scope) | MCP destructive = 사용자 사전 승인 우선 (mutual 면제 — 사용자 직접 결정 영역) |
| 16 (단순화 5번 토큰 효율) | mutual = 사용자 명시 의무 (단순화 5번 default 위반 면제) |

🔴 **NG 성격별 2-tier (사이클 165 회고 — CLAUDE.md 정책18 §3 페어)**: NG 처리는 NG 의 성격으로 분기한다. (a) **설계방향·트레이드오프 동반 NG** = 자율 수정 금지 → 옵션 표(정책 1) + 사용자 confirm 의무. (b) **단일 정답 버그 회귀 NG**(검증 가능한 객관 정답 1개·트레이드오프 없음) = 동일 PR 내 즉시 수정 후 재검증 OK, 옵션 표 면제. 사이클 165 사례: #811 비원자 TOCTOU = (a, 옵션 A/B 표 + confirm) / #814 overview NULL→F 오분류 = (b, 정답 avg_raw 기준 1개 → 즉시 수정). 판별 애매 시 (a) 로 보수 처리.

### NG 회기 ≤ 3회 default 가드

| 회기 | default 동작 |
|------|-------------|
| 1회차 NG | Claude 수정 plan 옵션 표 → 사용자 confirm → 재진입 |
| 2회차 NG | Claude 수정 + **1차 회기 NG 사유와 차이 분석** PR body 명시 |
| 3회차 NG | Claude 수정 + **누적 차이 분석** PR body 명시 — Claude 최종 시도 |
| **4회차 NG = 사용자 직접 결정 영역 escalation** | 옵션 표 (🅐 수용 머지 / 🅑 보류 / 🅒 다른 접근) → 사용자 결정 |

**Why ≤ 3회 default**: 정책 8 5+1 cross-verify 패턴과 정합 (5 회기 = blind spot 가능 / 3 Claude 회기 = 대화 단위 합리적 상한). 사이클 73 #244 Copilot Autofix 5 commits 사례 학습 — **3 회기 후(=4회차) escalation** 으로 자동화 안티패턴 차단. CLAUDE.md 정책18 §3 "≤ 3회 default — 4회차 escalation" 과 정합 (사이클 165 회고 Codex 적발 off-by-one 정정 — 구 표 '3회차 escalation' = 오기).

### 회복 가드 (정책 1 진화 사이클 86 Q4 페어)

작업 완료 보고 시 검증 의뢰 명시 누락 시 = **다음 응답에서 회복 의무** (자성 1줄 + 의뢰 1줄 추가). 회복 누락 시 = 다음 사이클 회고 §자성 명시 의무.

**양방향 비대칭 위험**: Claude 측 회복 가드 = 메모리 `feedback-codex-post-validation-mandatory.md` 적용. Codex 측 회복 가드 = AGENTS.md hooks 또는 Codex system prompt 영역 (SCAManager 통제 외 — Codex 측 적용 검증 불가). default 보고: AGENTS.md 본문에 "Codex 환경 진입 시 본 섹션 read 의무" 명시 (PR #368 머지) — Codex 측 강제력 = 0 (자율 적용 영역).

### 검증 사례 (사이클 93 첫 운영)

- **PR #368** (AGENTS.md mutual 신설) — Codex OK 받고 사용자 머지 ✅
- **PR #366** (Step 2-A + fix-up) — Codex OK 받고 사용자 머지 ✅
- 사용자 라운드트립 부담 정량 = PR당 ~수분 (양성 ROI 검증)
- 사이클 93 CI 분석 사고 (Claude 단독 false-positive) 차단 가치 ≫ 라운드트립 비용
- **net positive 검증** (1 사이클 데이터) — ≥ 5 사이클 누적 시 ROI 재검증 의무 (정책 17 5번 default 페어)

### 운영 P0 가드 영역 (3건 — 5+1 검토 도출)

| # | P0 영역 | 본문 명시 가드 |
|---|--------|--------------|
| 1 | mutual ↔ 5+1 cross-verify 중복 오해 | "Codex OK 받았으니 5+1 6차 생략 OK" 단정 X — 양 layer 독립 의무 |
| 2 | 5+1 dispatch 에 Codex 슬롯 추가 | self-contained 보호 깨짐 + 병렬성 손상 — 5+1 = Claude 내부 / mutual = 결과물 검증 시점 분리 |
| 3 | 사이클 종료 = 사용자 신호만으로 종료 | 정책 5 강화 회귀 — 3 조건 AND 의무 (사용자 + Claude OK + Codex OK) |

### 4-way Single Source of Truth + sync 가드

| 영역 | 본문 위치 | sync 트리거 |
|------|---------|-----------|
| default 흐름 본문 | AGENTS.md §"Claude ↔ Codex 양방향 mutual 검증 의무" | 흐름 변경 시 4-way sync 의무 |
| CLAUDE.md 정책 18 default rule | CLAUDE.md §"사용자 협업 정책" 정책 17 직후 | default rule 변경 시 sync |
| detail · 검증 사례 · Why · How | .claude/policies/active.md §"정책 18" (본 섹션) | detail 영역 변경 시 sync |
| 진화 default 추적 | .claude/policies/history.md §"보존 영역" — 정책 18 entry | 사이클 94+ 진화 시 추가 |
| Claude 측 숙지 | 메모리 `feedback-codex-post-validation-mandatory.md` | 매 사이클 30초 grep 의무 |

**5-way sync 가드** — 본문 충돌 시 **CLAUDE.md 정책 18 우선** (정책 일관성 — Claude 가 SCAManager 운영 주체).

### Cross-ref

- 정책 5 강화 페어 (사이클 종료 신호 = 두 LLM 동의 의무 구성요소)
- 정책 8 페어 (5+1 cross-verify ↔ mutual 2-layer 격리 의무)
- 정책 9 페어 (회고 자유 발언 = Claude 단독 / 회고 결과물 = Codex 검증 의뢰 의무)
- 정책 17 5번 default 페어 (정기 검증 ≥ 5 사이클 ↔ mutual 매 PR 시점 차별)
- 메모리 `feedback-codex-post-validation-mandatory.md` (Claude 측 숙지)
- 메모리 `feedback-pr-scoped-ci-endpoint-pattern.md` (사이클 93 사고 학습 페어)

---

<a id="정책-8-doc-audit-agent-domain"></a>

## 정책 8: 문서 감사 5+1 에이전트 파일 도메인 분리 (사이클 101 신설)

**배경**: 사이클 101 5+1 doc audit 시 5 에이전트가 서로 겹치는 파일 영역을 감사 → 동일 이슈 중복 보고 + false-positive 교차 발생. 비중복 도메인 분리로 커버리지 ↑ + 중복 보고 ↓.

**default 에이전트 도메인 분리 표** (문서 감사 5+1 dispatch 시 아래 5 도메인 고정 배정):

| 에이전트 # | 담당 도메인 | 주요 파일 |
|-----------|------------|---------|
| Agent-1 | 핵심 정책 문서 | `CLAUDE.md` / `.claude/` (skills, rules 제외) |
| Agent-2 | 활성 정책 + 이력 | `.claude/policies/active.md` / `.claude/policies/history.md` |
| Agent-3 | 아키텍처 + 상태 | `docs/architecture.md` / `docs/STATE.md` / `docs/cycle-history.md` |
| Agent-4 | Path-scoped rules | `.claude/rules/*.md` (8 영역 전체) |
| Agent-5 | 참조 + 운영 문서 | `docs/reference/*.md` / `docs/runbooks/*.md` / `docs/_archive/reports/` (최근 3건) |
| Agent-6 (cross-verify) | 전체 합성 | 1~5 결과 종합 + false-positive 제거 + P0/P1/P2 정렬 |

**적용 시 의무 조건** (CLAUDE.md 정책 8 기존 조건 전부 유지):
- 각 에이전트 프롬프트에 "담당 도메인 외 파일 언급 금지" 명시 (비중복 강제)
- `self-contained` (다른 에이전트 결과 의존 0)
- `line:span 인용 의무` (`grep -n` 실측 — 정책 6 페어)
- 출력 P0/P1/P2 분류

**cross-verify (Agent-6) 생략 기준**: CLAUDE.md 정책 8 정량 3 조건 동일 적용 (P0 합계 ≥ 8 + 5 관점 모두 P0 ≥ 1 + 사용자 빠른 진행 신호 명시).

**도메인 재배정 허용 조건**: 특정 사이클 작업 범위가 일부 도메인에 집중된 경우 에이전트 수 조정 가능 (예: pipeline 변경 집중 사이클 → Agent-4 `pipeline.md` 전담 / Agent-5 = `api.md` + `security.md` 페어). 단, 비중복 원칙 보존 의무.

**Why**: 사이클 101 5+1 결과 cross-verify 에서 false-positive 6건 제거됨 — 도메인 겹침이 중복 보고 주원인. 비중복 분리 시 cross-verify 부담 ↓ + 각 에이전트 집중도 ↑.

---

<a id="정책-5-phase-종료-cross-reference"></a>

## 정책 5: Phase 종료 cross-reference 4 정책 열거 상세

Phase 종료 시점 의무는 **정책 2/5/8/11 4 정책에 분산** (사이클 83 — 정책 5 cross-reference 강화):

- **정책 2 진화**: Phase 종료 일괄 회신 묶음 (sync 실측 1줄 의무)
- **정책 5 강화**: Phase 단계별 진행/종료 신호 분리 의무 (본 정책)
- **정책 8**: 회고 패턴 3 분기 (회고+sync 페어 / sync 단독 / 회고 단독)
- **정책 11 강화**: Phase 종료 누적 회신 묶음 (8 조합 시각 체크리스트 누적 의무)

---
