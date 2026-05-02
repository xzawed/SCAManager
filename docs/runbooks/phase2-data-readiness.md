# Phase 2 진입 전 데이터 충분성 검증 Runbook

**목적**: Phase 1 (`/dashboard` MVP-B) 출시 후 Phase 2 (차별 KPI 카드 — Auto-merge 성공률 + AI 정합도) 진입 전 운영 데이터가 의미 있는 카드를 만들 수 있을지 검증.

**기획 근거**: [`docs/design/2026-05-02-insight-dashboard-rework.md`](../design/2026-05-02-insight-dashboard-rework.md) §6.1 Q4 — *"Phase 2 시작 전 데이터 검증 의무"*.

**사용자 결정 (2026-05-02)**: ✅ 동의 — Phase 2 진입 전 데이터 검증 의무화.

---

## 1. 실행

```bash
# Railway PostgreSQL psql 또는 로컬 .env 의 DATABASE_URL
psql "$DATABASE_URL" -f scripts/dev/verify_phase2_data.sql
```

또는 Railway 대시보드 → Database → Query → 위 SQL 파일 내용 직접 실행.

**5건의 SELECT** 결과를 회신.

---

## 2. 결과 해석 매트릭스

### 검증 1: `analysis_feedbacks` (AI 정합도 KPI 후보)

| `total_feedbacks` | `last_30d` | 결정 |
|------|------|------|
| ≥ 30 | ≥ 10 | 🅐 **Phase 2 AI 정합도 카드 진입 OK** — 통계적으로 의미 있음 |
| 10 ~ 29 | ≥ 5 | 🅑 **Phase 2 진입 가능 (데이터 부족 표시 필요)** — "최근 N건 기반" 명시 |
| < 10 | < 5 | 🅒 **AI 정합도 카드 보류** — Phase 3 우선 (Insight 모드) — 사용자 행동 유도 후 데이터 누적 |

### 검증 2: `merge_attempts` (Auto-merge 성공률 KPI 후보)

| `total_attempts` | `last_30d` | `success_rate_pct` | 결정 |
|------|------|------|------|
| ≥ 50 | ≥ 20 | (any) | 🅐 **Phase 2 Auto-merge 성공률 카드 진입 OK** |
| 20 ~ 49 | ≥ 10 | (any) | 🅑 **진입 가능 (samples 표시)** |
| < 20 | < 10 | — | 🅒 **카드 보류** — auto_merge 사용자 비활성 가능 |
| ≥ 20 | < 5 | — | 🅓 **사용 빈도 ↓** — 카드 보류 + auto_merge 운영 promotion 우선 |

### 검증 3: `failure_reason` 분포 (Phase 3 advisor 활용)

- `branch_protection_blocked` 등 Top 3 실패 사유 — Phase 3 의 `merge_failure_advisor` 카드에서 가장 많은 사용자 영향 사유 노출 가치.
- 실패 0건 = `merge_failure_issue` 자동 생성 효과 — Phase 3 advisor 자체 보류 가능.

### 검증 4: `analyses` (현재 KPI 카드 보강)

- `total_analyses` ≥ 100 = 운영 의미 있음
- `last_7d` ≥ 5 = 활성 운영 (Phase 1 KPI 카드의 "분석 건수" delta 의미 있음)

### 검증 5: `author_login` 분포 (Q5 모드 토글 Phase 3 가치 측정)

- `distinct_authors` ≥ 3 = 멀티 사용자 운영 → Insight 모드 (Claude 톤 노트) 의 "AI 가 사용자별 흐름 분석" 가치 ↑
- `distinct_authors` = 1 (단독 운영) = Insight 모드 우선순위 ↓ (1인 사용 시 노트 가치 미미)

---

## 3. Phase 2 진입 결정 (사용자)

위 5 검증 결과를 종합하여 다음 4 옵션 중 결정:

| 옵션 | 조건 | 다음 작업 |
|------|------|----------|
| 🅐 **Phase 2 즉시 진입** | 검증 1+2 모두 🅐 또는 🅑 | Phase 2 PR 시리즈 착수 (Auto-merge 성공률 + AI 정합도 카드) |
| 🅑 **Phase 2 부분 진입** | 검증 1 🅒 + 검증 2 🅐/🅑 | Auto-merge 카드만 (AI 정합도는 Phase 3 후속) |
| 🅒 **Phase 3 우선** | 검증 1+2 모두 🅒 | Insight 모드 (Claude 톤 노트) 먼저 — 사용자 참여 유도 후 데이터 누적 |
| 🅓 **운영 promotion 우선** | 검증 4 `last_7d` 0 또는 5 미만 | Phase 2/3 모두 보류, /dashboard 사용 promotion (사용자 알림 / 가이드) |

---

## 4. Claude 가 자율 판단 가능한 부분 (사용자 결과 회신 후)

본 runbook 결과 ↔ Phase 2 PR 시리즈 분할 안 (3 PR 권장 — 정책 7 강화):
- 옵션 🅐 진입 시: PR 1 (service 함수 추가) + PR 2 (KPI 카드 2 추가 + 가드) + PR 3 (모바일 / claude-dark / 회귀 가드 정리)
- 옵션 🅑 진입 시: PR 1+2 통합 (Auto-merge 카드만) + PR 3 (정리)
- 옵션 🅒/🅓 진입 시: 별도 기획 사이클 (Phase 3 또는 promotion 작업)

---

## 5. 보안 / 개인정보 보호 (정책 11 + sanitize_for_log)

- 본 SQL 결과는 row 수 + 카운트 + 비율만 — **사용자 개인 데이터 (코멘트 본문 / commit message / repo 이름) 노출 0**.
- Railway 콘솔에서 직접 실행 시 결과 화면 캡처 시 정상 (PII 없음).
- 회신 시 row 수만 알려주셔도 충분.

---

## 부록 — Railway 운영 환경 접근 방법

### 옵션 A: Railway Dashboard
1. Railway 프로젝트 → Database (PostgreSQL) → Query 탭
2. SQL 내용 paste + Run
3. 결과 표 회신

### 옵션 B: psql CLI
```bash
# Railway DATABASE_URL 가져오기
railway variables --service Postgres
# 또는 Railway 대시보드 Variables 탭에서 복사

psql "$DATABASE_URL" -f scripts/dev/verify_phase2_data.sql > phase2_results.txt
cat phase2_results.txt  # 회신 내용
```

### 옵션 C: Claude Code (Bash via SCAManager DEV 환경)
- `.env` 의 `DATABASE_URL` 이 운영 DB 인 경우만 가능
- 일반적으로 dev 환경 = 별도 DB → 의미 있는 결과 안 나옴 (옵션 A/B 권장)
