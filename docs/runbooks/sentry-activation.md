# Sentry 운영 활성화 — 사이클 80 PR 1

> **작업일**: 2026-05-05 (사이클 80 영역 🅔 운영 모니터링 묶음 PR 1)
> **5+1 cross-verify P0-1**: Sentry PII 노출 위험 — 신규 헤더 스크러빙 candidate 검증 의무

---

## 1. 배경

**Phase 1 baseline (사이클 72 PR 2 #242)** = Sentry SDK 인프라 구현 (`src/shared/observability.py`) — `SENTRY_DSN` 미설정 시 silent skip. 운영 활성화 = Railway 환경변수 등록 의무.

**Phase 2 진입 (사이클 80 PR 1)** = PII 스크러빙 검증 + 운영 활성화 가이드.

---

## 2. PII 스크러빙 사양 (Cycle 80 PR 1 강화)

### 2-1. 헤더 화이트리스트 (10건)

| 헤더 | 사유 |
|------|------|
| `Authorization` | Bearer / Basic 토큰 |
| `X-API-Key` | admin API key |
| `X-Hub-Signature` | 구 GitHub HMAC 서명 |
| `X-Hub-Signature-256` | GitHub HMAC SHA-256 서명 |
| `X-GitHub-Token` | GitHub API 호출 헤더 |
| `X-Telegram-Bot-Api-Secret-Token` | Telegram webhook secret_token |
| `X-Webhook-Token` | custom webhook 인증 |
| `X-Forwarded-For` | 사용자 IP — PII |
| `X-Real-IP` | 사용자 IP — PII |
| `Cookie` | 세션 쿠키 |

→ Sentry 이벤트 본문에서 `[Filtered]` 로 치환 (대소문자 무관).

### 2-2. URL 스크러빙

- query string 제거: `?token=xxx` → 제거
- fragment 제거: `#token=xxx` → 제거 (사이클 80 신규)

### 2-3. body data + cookies

- `request["data"]` → `[Filtered]` 명시
- `request["cookies"]` → `{}` 비움
- `send_default_pii=False` SDK 옵션 (기본값 + 명시 방어)

---

## 3. Railway 운영 활성화 절차

### 3-1. Sentry 프로젝트 생성

1. [sentry.io](https://sentry.io) 가입 + 프로젝트 신설
2. Project Type = `Python` 선택
3. DSN 발급 = `https://<key>@<org>.ingest.sentry.io/<project_id>` 형식

### 3-2. Railway 환경변수 등록

Railway dashboard → SCAManager service → Variables 탭:

```
SENTRY_DSN=https://<key>@<org>.ingest.sentry.io/<project_id>
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
```

→ 변경 즉시 Railway 자동 재배포.

### 3-3. 활성화 검증 (정책 13 smoke check 페어)

배포 완료 후 manual 검증:

```bash
# 1. 로그 확인 — "Sentry initialized (env=production)" INFO 메시지
curl -sf https://<APP_BASE_URL>/health
# Railway logs 에서 `Sentry initialized` 검색

# 2. test event 발사 (수동 — 운영 실수 회피)
# Sentry dashboard → Settings → Projects → SCAManager → Test Notification
# → 이벤트 수신 확인 (수 분 내)

# 3. 운영 endpoint 1회 의도적 fail 테스트 (admin only)
# → Sentry dashboard 이벤트 본문에서 [Filtered] 확인 의무
```

### 3-4. PII 스크러빙 운영 검증 (의무)

Sentry dashboard 첫 이벤트 수신 시:

- [ ] `request.url` 에 `?token=`, `#token=` 부재 검증
- [ ] `request.headers.Authorization` = `[Filtered]` 검증
- [ ] `request.cookies` = `{}` 검증
- [ ] `request.data` = `[Filtered]` 검증
- [ ] 사용자 IP (`X-Forwarded-For` / `X-Real-IP`) = `[Filtered]` 검증

**누설 발견 시**: `_SENSITIVE_HEADERS` 추가 + 회귀 가드 추가 (`tests/unit/shared/test_observability_before_send.py` 패턴) + 후속 PR 진행.

---

## 4. 운영 사용량 baseline (사이클 81+ 의무)

### 4-1. Sentry SaaS free tier 한계

- **5,000 events / 월** (free tier — 2026-05 기준)
- `traces_sample_rate=0.1` (10% 샘플링) default — 운영 트래픽 ↑ 시 한계 도달

### 4-2. 1주 baseline 측정 (사이클 81+ 진행)

PR 1 머지 + Sentry 활성화 후 1주 운영 시점:

```bash
# Sentry dashboard → Projects → SCAManager → Stats
# 7-day total events 측정 + 월간 추정 (× 4.3) + free tier 5K 대비 검증
```

**임계 도달 시 결정**:
- 임계 80% 도달 = `traces_sample_rate=0.05` (5%) 조정
- 임계 100% 도달 = team plan 업그레이드 또는 self-hosted Sentry 고려

---

## 5. 관련 문서

- `src/shared/observability.py` (Phase E.2a + 사이클 80 PR 1 강화)
- `tests/unit/shared/test_observability_before_send.py` (Cycle 80 PR 1 신규 회귀 가드 23건)
- `tests/unit/shared/test_observability.py` (Phase E.2a 기존 9건)
- 메모리 `feedback-phase4-area-entry-pattern.md` Phase 4 영역 진입 패턴 (안전 default 4건)
- 정책 13 운영 smoke check (사이클 62 신설)
- 사이클 78 PR 1 helper 모듈 (kill-switch 패턴 페어)

---

## 6. 자율 판단 보고 (정책 3)

1. **`_before_send` = sentry-sdk 의존 0** (단순 dict 변환) → 회귀 가드 importorskip 제거 (devcontainer 도 PASS — 23/23)
2. **헤더 화이트리스트 frozenset** = O(1) lookup + immutable (정책 16 단순화 default — 추상화 0)
3. **body data 영구 필터** = SDK 기본값 + 명시 방어 (defence in depth)
4. **운영 적용 시점** = 사용자 명시 (Railway 환경변수 등록 — Claude 진입 X)
5. **Phase 2 baseline 측정** = 사이클 81+ 1주 운영 후 별도 사이클 진행 default
