# 운영 endpoint smoke check Runbook

**목적**: 정책 13 (운영 endpoint smoke check 의무) 의 default 실행 가이드.
**기획 근거**: [`docs/reports/2026-05-02-oauth-redirect-uri-incident.md`](../reports/2026-05-02-oauth-redirect-uri-incident.md) — P0 OAuth 사고 후속.

**정책 13 적용 시점**:
- 매 사이클 종료 시 (또는 Phase 종료 시) — 최소 3-endpoint
- 인증/외부 통합 변경 PR — 확장 4-endpoint
- 운영 사고 의심 시 — 즉시 진단 절차

---

## 1. 최소 3-endpoint smoke check

```bash
APP_URL="https://scamanager-production.up.railway.app"

# 1) /health (liveness)
curl -sf -o /dev/null -w "/health: HTTP %{http_code}\n" "$APP_URL/health"

# 2) /auth/github → 302 + Location redirect_uri 정합성
curl -s -L --max-redirs 0 -o /dev/null -w "/auth/github: %{redirect_url}\n" "$APP_URL/auth/github"

# 3) /login (200 또는 302 — 로그인 상태 의존)
curl -sf -o /dev/null -w "/login: HTTP %{http_code}\n" "$APP_URL/login"
```

**기대 결과**:
```
/health: HTTP 200
/auth/github: https://github.com/login/oauth/authorize?response_type=code&client_id=...&redirect_uri=https%3A%2F%2Fscamanager-production.up.railway.app%2Fauth%2Fcallback&scope=...&state=...
/login: HTTP 200
```

**실패 처리**:
- `/health` 200 외 → SCAManager 프로세스 자체 문제 (Railway 로그 확인)
- `/auth/github` redirect_uri 가 예상과 다름 → `APP_BASE_URL` 환경변수 확인
- `/login` 5xx → 템플릿 렌더링 또는 세션 미들웨어 오류

---

## 2. 인증/외부 통합 변경 PR 확장 4-endpoint

```bash
# 위 3-endpoint + 다음 추가:

# 4) /auth/callback (state 검증으로 401 또는 302 — 직접 호출 시 의도된 거부 OK)
curl -sf -o /dev/null -w "/auth/callback: HTTP %{http_code}\n" "$APP_URL/auth/callback"

# 5) POST /webhooks/github (서명 헤더 누락 → 401, 정상)
curl -sf -o /dev/null -w "/webhooks/github: HTTP %{http_code}\n" \
  -X POST "$APP_URL/webhooks/github" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**기대 결과**:
```
/auth/callback: HTTP 401  (또는 302 — state 검증 실패 = 정상 거부)
/webhooks/github: HTTP 401  (서명 누락 = 정상 거부)
```

---

## 3. GitHub OAuth App 설정 정합성 진단

P0 OAuth 사고 (2026-05-02) 같은 mismatch 진단:

### 단계 1: SCAManager 가 보내는 redirect_uri 확인
```bash
curl -s -L --max-redirs 0 -o /dev/null -w "%{redirect_url}\n" \
  "$APP_URL/auth/github" | grep -oP 'redirect_uri=[^&]+' | sed 's/%3A/:/g; s/%2F/\//g'
```

### 단계 2: GitHub OAuth App 등록값 확인 (사용자 의무)
1. https://github.com/settings/developers
2. OAuth Apps → SCAManager (client_id 매칭)
3. "Authorization callback URL" 필드 = 단계 1 결과와 정확히 일치 (trailing slash 없이, https)

### 단계 3: 단계 1 ↔ 단계 2 mismatch 시 fix
- (a) GitHub OAuth App callback URL 정정 (사용자 30초)
- (b) 또는 Railway `APP_BASE_URL` 환경변수 정정 (운영 도메인 변경 시)

---

## 4. Railway 환경변수 검증 (Supabase MCP 패턴 차용)

Railway MCP 가용 시 자율 검증:
```
mcp__railway__list_variables(project_id, service_id) → APP_BASE_URL 값 확인
```

Railway MCP 부재 시 사용자 의무:
- Railway Dashboard → Variables 탭 → `APP_BASE_URL` 값 = `https://<운영도메인>` 정확
- 환경변수 변경 후 redeploy 자동 완료까지 ~3분 대기

---

## 5. 사고 발생 시 즉시 진단 절차

| 사고 유형 | 즉시 진단 명령 | 예상 fix 시간 |
|----------|-------------|-------------|
| 로그인 불가 (OAuth) | `curl ... /auth/github` → redirect_uri 확인 + GitHub OAuth App 비교 | ~30초 (사용자 OAuth App 수정) |
| /health 5xx | Railway 로그 (Sentry 알람) | ~5분 (rollback) |
| Webhook 미수신 | GitHub webhook delivery 페이지 + `/webhooks/github` 401 응답 확인 | ~10분 |
| 알림 미발송 | Telegram/Discord/Slack URL + 토큰 검증 (Settings 페이지) | ~5분 |
| 분석 실패 | Anthropic API key + Sentry 알람 | ~10분 |

---

## 6. PR 본문 §"운영 smoke check 결과" 섹션 default 형식

```markdown
## 운영 smoke check (정책 13)

- ✅ /health 200
- ✅ /auth/github 302 redirect_uri = https://scamanager-production.up.railway.app/auth/callback (정합)
- ✅ /login 200
- (확장: 인증/외부 통합 변경 시)
- ✅ /auth/callback 401 (state 검증 = 정상 거부)
- ✅ /webhooks/github 401 (서명 누락 = 정상 거부)

실행: 2026-05-02 (Phase 종료 시점) / Claude curl 자율 실행
```

---

## 7. 정책 11 강화 — 인증 flow 4 endpoint 종단간 검증

UI 변경 PR 외에도 **인증/외부 통합 변경 PR** 시 의무:

```markdown
## 🚨 인증 flow 종단간 검증 (정책 11 강화)

- [ ] /login 페이지 200 응답 + 로그인 버튼 표시
- [ ] /auth/github 302 + GitHub 동의 화면 진입
- [ ] GitHub 동의 후 /auth/callback → / redirect + 세션 생성
- [ ] /auth/logout → /login redirect + 세션 제거

(Claude 정적 검증 불가 — 사용자 직접 브라우저 검증 부탁드립니다)
```

---

## 부록 — 본 사고 (2026-05-02) 진단 명령 복기

```bash
APP_URL="https://scamanager-production.up.railway.app"

# 진단 1: SCAManager 정상 동작
curl -sf -o /dev/null -w "/health: HTTP %{http_code} | size %{size_download}\n" "$APP_URL/health"
# 결과: HTTP 200 | size 15

# 진단 2: SCAManager 가 보내는 redirect_uri
curl -s -L --max-redirs 0 -o /dev/null -w "%{redirect_url}\n" "$APP_URL/auth/github"
# 결과: https://github.com/login/oauth/authorize?...&redirect_uri=https%3A%2F%2Fscamanager-production.up.railway.app%2Fauth%2Fcallback&...
# = 정확함

# → 결론: SCAManager 측 100% 정상. GitHub OAuth App callback URL mismatch.
# → fix: 사용자가 GitHub OAuth App 설정에서 callback URL 정정 (30초)
```

---

## 8. 자동화 가드 (그룹 61 PR #208) — manual smoke 와 상호 보완

본 runbook 의 manual smoke check 와 페어로 동작하는 자동화 회귀 가드.
**CI / Railway 빌드 자동 실행 → 다음 OAuth/redirect_uri 같은 외부 변경 사고 즉시 발견**.

### 8.1 통합 테스트 — `tests/integration/test_oauth_flow_smoke.py` (10건)
- TestSmokeCheckMinimal (3): /health 200 + /auth/github 302 + /login 200|302
- TestAuthFlowEndpoints (3): redirect_uri 정합성 + /auth/callback 거부 + webhook 서명 누락 401
- TestInsightsRedirect (3): /insights, /insights/me 301 redirect + 쿼리 파라미터 보존
- TestPolicyThirteenAutomation (1): 3-endpoint 성능 < 3초

```bash
# 로컬 실행
pytest tests/integration/test_oauth_flow_smoke.py -v
```

### 8.2 E2E 테스트 — `e2e/test_dashboard.py` (14건)
- 페이지 로드 + 5xx 차단 (2)
- KPI 5 카드 count + 5 라벨 노출 (2)
- range toggle 4 링크 + default 7d active + 30d 클릭 navigate (3)
- chart vendoring (1)
- 자주 발생 이슈 섹션 + JS 런타임 0 (2)
- /insights → /dashboard 301 redirect (2)
- /login + nav Dashboard 링크 (2)

```bash
# 로컬 실행 (Playwright Chromium)
make test-e2e
```

### 8.3 통합 환경 의존성 격리 — `tests/integration/conftest.py` autouse fixture (그룹 61 PR #209)
- `patch("src.webhook.providers.github.get_webhook_secret", return_value="test_secret")` 일괄 적용
- 신규 webhook integration test 도 자동 격리 — devcontainer 등 환경의 `GITHUB_WEBHOOK_SECRET=dev_secret` export 영향 차단
- 효과: pre-existing 24 fail → 0 fail

### 8.4 정책 13 본문 (CLAUDE.md L660~) 자동화 가드 인용 정합

manual smoke (3-endpoint) ↔ 자동화 가드 (integration 10 + e2e 21 = test_dashboard 14 + test_theme_mobile_guards 7) 상호 보완 관계:
| 영역 | manual (정책 13 default) | 자동화 (PR #208 + #212) |
|------|----------------------|----------------|
| /health | curl | TestSmokeCheckMinimal |
| /auth/github redirect_uri | curl + decode | TestAuthFlowEndpoints |
| /login | curl | TestSmokeCheckMinimal + e2e |
| /auth/callback 거부 | curl | TestAuthFlowEndpoints |
| /webhooks/github 401 | curl + 서명 누락 | TestAuthFlowEndpoints |
| /insights → /dashboard 301 | curl | TestInsightsRedirect + e2e |
| /dashboard 페이지 시각 (KPI 5 / chart / nav) | 사용자 시각 검증 | e2e/test_dashboard.py |
| claude-dark 토큰 정의 (8 + 등급 alias) | 사용자 시각 검증 | e2e/test_theme_mobile_guards.py §A |
| WCAG 2.5.5 모바일 클릭 영역 (.btn / .nav-hamburger) | iOS / 안드 실기 | e2e/test_theme_mobile_guards.py §B |
| 외부 의존 (GitHub OAuth App callback URL) | **사용자만 가능** | (자동화 불가) |

### 8.5 E2E 테마 + 모바일 회귀 가드 — `e2e/test_theme_mobile_guards.py` (7건, 사이클 62 PR #212)
- **A. claude-dark 토큰 회귀 가드** (cleanup PR #169 사고 차단):
  - claude-dark settings 8 토큰 정의 (`--grad-gate/merge/notify/hook`, `--title-gradient`, `--save-btn-bg`, `--hint-bg`, `--hook-btn-bg`)
  - claude-dark dashboard body 비-투명 (—bg-page 미정의 회귀)
  - claude-dark 등급 alias (`--grade-a/b/c/d/f`) 정의
- **B. WCAG 2.5.5 모바일 클릭 영역 가드** (UI 감사 Step A):
  - 모바일 .btn (375px) min-height ≥44px
  - 모바일 .btn--sm (375px) min-height ≥40px
  - 모바일 .nav-hamburger (375px) ≥44x44
  - 데스크탑 .btn (1024px) min-height < 44px (모바일 분기 누수 회귀)
- **핵심 패턴**:
  - claude-dark 토큰은 `body[data-theme="claude-dark"]` 스코프 → `getComputedStyle(document.body).getPropertyValue(...)` 조회 (`document.documentElement` 는 :root 만 노출 — 빈 문자열 false-positive)
  - Playwright `page.evaluate()` 다중 statement → arrow function `() => { ... }` wrap 의무
  - DOM 주입 헬퍼 (`_measure_injected_btn_min_height`) — 정적 셀렉터 의존도 감소

```bash
# 로컬 실행
pytest e2e/test_theme_mobile_guards.py -v
```
