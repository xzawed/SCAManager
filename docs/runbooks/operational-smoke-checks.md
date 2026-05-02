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
