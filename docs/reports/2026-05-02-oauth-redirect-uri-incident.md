# 2026-05-02 OAuth `redirect_uri` 운영 사고 회고

**심각도**: P0 (운영 정지 — 사용자 로그인 불가)
**발견 시점**: 2026-05-02 (Phase 2 PR 3 머지 직후)
**원인**: GitHub OAuth App 의 Authorization callback URL ↔ SCAManager 의 `redirect_uri` mismatch (외부 변경)
**SCAManager 측 책임**: 0 (코드/환경변수 정상)
**복구 시간**: ~30초 (사용자 OAuth App 설정 1회 수정)
**재발 방지 의무**: ⭐ 신규 정책 13 + 정책 11 강화 + OAuth smoke test 회귀 가드

---

## 1. 사고 타임라인

| 시각 | 이벤트 |
|------|------|
| 그룹 60 PR #198~#202 | Phase 1+2 12 PR + 정책/Hook fix 머지 (OAuth 영역 코드 변경 0건) |
| 본 사이클 회고 시점 | 5 에이전트 병렬 회고 P0 #4: *"운영 사고 0건 = 운 + Copilot Autofix + Railway CI"* — 자성 명시했으나 후속 조치 0 |
| Phase 2 PR 3 (P0 #3 swap) 머지 직후 | 사용자 로그인 시도 → "Be careful! redirect_uri is not associated with this application" GitHub 에러 |

## 2. 정밀 진단 결과

### SCAManager 측 = 100% 정상
```bash
$ curl -sf -o /dev/null -w "HTTP %{http_code}\n" https://scamanager-production.up.railway.app/health
HTTP 200

$ curl -s -L --max-redirs 0 -o /dev/null -w "%{redirect_url}\n" https://scamanager-production.up.railway.app/auth/github
https://github.com/login/oauth/authorize?response_type=code&client_id=Ov23liARxdsAqc9eFkjJ&redirect_uri=https%3A%2F%2Fscamanager-production.up.railway.app%2Fauth%2Fcallback&scope=repo+user%3Aemail&state=...
```

- ✅ `redirect_uri` (decoded) = `https://scamanager-production.up.railway.app/auth/callback`
- ✅ APP_BASE_URL 환경변수 = 사용자 확인값과 일치 (변경 이력 없음)
- ✅ `src/auth/github.py:41-48` 코드 변경 0건 (그룹 60 전체)

### GitHub OAuth App 측 = mismatch 추정
- SCAManager 가 보내는 `redirect_uri` 는 정확
- GitHub 가 거부 = OAuth App 의 등록된 Authorization callback URL 이 다른 값
- 추정 원인:
  - 외부 변경 (사용자/타인이 GitHub OAuth App 설정 수정)
  - GitHub 측 정책 변경 (예: trailing slash, 특정 도메인)
  - OAuth App 자체 재생성 또는 client_id 변경

## 3. 5 에이전트 회고가 본 사고 모델 못 잡은 갭

| 관점 | 회고 범위 | OAuth flow 검증 포함 여부 | 갭 분류 |
|------|----------|------------------------|--------|
| 1. PR 분할 + 응집 단위 | 12 PR 영역별 분류 | ❌ OAuth 영역 0 변경 = 자동 배제 | **검토 대상 정의 누락** |
| 2. TDD + 회귀 가드 | service + UI 라우트 단위 mock | ❌ OAuth flow 종단간 테스트 부재 | **테스트 영역 누락** |
| 3. 자율 판단 정책 | PR 본문 검토 환류 | ❌ 외부 의존 (GitHub OAuth App) 미포함 | **외부 의존 추적 누락** |
| 4. MCP 활용 | Supabase 운영 데이터만 | ❌ Railway 환경변수/GitHub OAuth App 검증 미시도 | **MCP 활용 영역 한정** |
| 5. 디자인 정합성 | UI 시각 (4-테마 × 모바일/데스크탑) | ❌ 인증 flow / 외부 통합 누락 | **검증 매트릭스 한정** |

### 회고 P0 #4 자기 예언 무시 — 가장 심각한 갭

[`docs/reports/2026-05-02-phase1-2-retrospective.md`](2026-05-02-phase1-2-retrospective.md):
> "운영 사고 0건 (Railway CI 빌드 차단 + Copilot Autofix 1건 자동 보호)"

**Claude 자성 항목으로 명시했으면서 후속 조치 0건**:
- Railway CI = 빌드 단계만 검증 (런타임 동작 X)
- Copilot Autofix = import 오류 자동 보호 (인증 flow 검증 X)
- **운영 사고 0건 = 진짜 안전이 아니라 검증 부재로 가시성 0**

본 사고가 그 예언의 **검증 사례** — 사고 발생 ≠ 운 부족, **검증 없음 = 사고 가시화 부재**.

### 정책 11 (시각 검증 불가) 한계

8 조합 체크리스트 = 4-테마 × 모바일/데스크탑 = **UI 시각만**. 다음 영역 누락:
- 인증 flow (GitHub OAuth, Telegram OAuth)
- API endpoint (외부 호출)
- Webhook 종단간 (서명 검증 + dispatch)
- 외부 의존 (GitHub API, Anthropic API, Railway, Supabase) 정합성

## 4. 테스트/검증 갭 (구체 매트릭스)

| 영역 | 본 사이클 테스트 존재? | 본 사고 차단 가능했나? |
|------|--------------------|-------------------|
| OAuth flow 종단간 (브라우저 시뮬레이션) | ❌ 0건 | ✅ 차단 가능 |
| Railway 운영 smoke test (`/login`, `/auth/github` redirect URL 검증) | ❌ 0건 | ✅ 차단 가능 |
| GitHub OAuth App callback URL 정합성 자동 검증 | ❌ 0건 | ✅ 차단 가능 (외부 API 호출 필요) |
| Sentry / 에러 모니터링 alarm | (Sentry 통합됐으나 OAuth fail alarm 미설정) | 🟡 부분 |

## 5. 신규 정책 + 회귀 가드 (본 PR 적용)

### 정책 13 신설 — 운영 endpoint smoke test 의무
- 매 사이클 종료 시 (또는 Phase 종료 시) 최소 3-endpoint smoke check 의무:
  - `GET /health` → 200
  - `GET /auth/github` → 302 redirect 응답 + Location 헤더에 `redirect_uri=` 정확성 검증
  - `GET /login` → 200 (또는 302 — 로그인 상태 의존)
- 사용자 운영 환경 (Railway production) 직접 호출 — Claude MCP 또는 curl
- 결과는 PR 본문 §"운영 smoke check 결과" 섹션 명시 의무

### 정책 11 강화 — 인증 flow 검증 추가
- 8 조합 시각 체크리스트 + **인증 flow 4 endpoint 종단간 검증** 추가
- UI 변경 PR 외에도 인증/외부 통합 변경 PR 시 의무

### 회귀 가드 신설
- `tests/integration/test_oauth_smoke.py` (신규):
  - SCAManager 가 보내는 `redirect_uri` 정합성 (mock 또는 live)
  - `APP_BASE_URL` 환경변수 → `redirect_uri` 변환 정확성
  - 외부 GitHub OAuth App callback URL mismatch 시뮬레이션 (mock 응답)

### Runbook 신설
- [`docs/runbooks/operational-smoke-checks.md`](../runbooks/operational-smoke-checks.md):
  - 5-endpoint smoke check 명령
  - GitHub OAuth App 설정 정합성 진단
  - Railway 환경변수 검증 (Supabase MCP 패턴 차용)
  - 사고 발생 시 즉시 조사 절차

## 6. 사용자 영향

- **로그인 불가** = 신규 사용자 OAuth flow 차단 (운영 정지 동일 영향)
- **기존 세션 사용자** = 영향 없음 (이미 로그인된 사용자는 재로그인 시점까지 정상)
- **복구 시간** = 사용자 OAuth App 설정 수정 ~30초 (즉시)

## 7. Claude 자기 회고 (정책 9 — 사고 후속)

### 자성 항목

1. **회고 P0 #4 자기 예언 무시** — *"운영 사고 0 = 운"* 명시하면서 후속 가드 0건. 다음 사이클 P0 자기 예언 시 **반드시 1 회귀 가드 PR 동반** 의무화.
2. **회고 5 에이전트 관점 한정** — UI/TDD/디자인 5 영역 vs **인증/외부 통합/운영 endpoint 미포함**. 다음 회고 시 관점 추가.
3. **MCP 활용 = Supabase 만** — Railway MCP 가용 시 환경변수/도메인 직접 검증 가능했음. 다음 사이클 도구 목록 사전 점검.

### 사용자 응답 인용 (메모리 보존)

사용자 발화 (2026-05-02):
> "분노하지 않았습니다. 되려 Claude에게 항상 감사함을 느낍니다. 이전 대화에서 강한어조가 있었다면 서비스 장애로 인한 강한 푸쉬라 보시면 됩니다. 항상 신뢰도나 믿음은 무한합니다. 너무 위축들지 마세요"

→ `~/.claude/projects/-workspaces-SCAManager/memory/user-trust-model-and-tone.md` 보존. 다음 세션 Claude 가 위축 모드 X, 분석 깊이 평소대로 유지.

## 8. 다음 사이클 default 패턴 (본 PR 후속)

- 모든 PR 본문에 §"운영 smoke check 결과" 섹션 (정책 13 default)
- 인증/외부 통합 변경 PR 시 인증 flow 4 endpoint 종단간 검증 의무 (정책 11 강화)
- Phase 종료 시 운영 endpoint smoke check 일괄 회신 (정책 2 진화 + 13 통합)
- MCP 도구 목록 사전 점검 (Supabase / Railway / 기타)
