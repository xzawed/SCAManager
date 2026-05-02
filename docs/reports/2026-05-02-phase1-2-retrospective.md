# Phase 1+2 (Insight Dashboard 재설계 + Auto-merge KPI + feedback CTA) 12 PR 회고

**기간**: 2026-05-02 (단일 작업일 ~6시간)
**범위**: PR #188 ~ #200 (12 PR 머지)
**결과**: `/insights` 폐기 4종 + 신규 `/dashboard` (KPI 5 + 차트 + 자주 이슈 + 실패 사유 + CTA banner) + pre-existing 7 fail 완전 해소 + 정책 진화 4건 (정책 11 신설 + 정책 2/3/7 진화) + Supabase MCP 검증
**다음 사이클**: Phase 3 (Insight 모드 — Anthropic SDK + caching) 또는 P0 #3 (Auto-merge KPI swap) 우선

본 문서는 정책 8 (다중 에이전트 회고) + 정책 9 (Claude 자유 발언) 적용 결과 + 사용자 응답 ("회고 OK" — 정책 2 진화 첫 검증 완료).

---

## 1. 정량 결과

| 지표 | 값 |
|------|-----|
| PR 수 | 12 (#188 ~ #200) |
| 작업 시간 | ~6 시간 (Phase 1: 13:13~16:43 / Phase 2: 18:29~19:39) |
| 누적 LOC | 폐기 -2175 + 신규 +2018 (코드 1119 + Auto-merge 461 + CTA 259 + 검증 도구 183) + 정책/회고/Supabase docs +345 = **순 +188 LOC** |
| 단위 테스트 변동 | Phase 1 +1 + 7 fail 해소 + Phase 2 +17 = 1986 → **2004 passed / 0 failed** |
| 회귀 가드 신규 | +13 (`test_analytics_service_deprecations.py` 단일 모듈 누적) + +36 (Phase 2 service 36) = +49 |
| 운영 사고 | 0건 (Railway CI 빌드 차단 + Copilot Autofix 1건 자동 보호) |
| pre-existing 7 fail | 5 PR 보존 → B-1/B-2 완전 해소 |
| MCP 직접 실행 | Supabase project 발견 + 5 SELECT (시간 87% 절감) |

---

## 2. 5-에이전트 병렬 회고 결과 (정책 8) — Phase 1+2 누적

### P0 — 다음 사이클 적용 의무

1. **정책 7 강화 본문 = "응집 = URL + 화면 + 데이터 3종"** — Phase 1 PR 4+5 분리 (nav 일시 404) → Phase 2 응집 100% 적용으로 nav 깨짐 0건. **본 PR 으로 정책 본문 추가 적용**.

2. **MCP 가 카드 설계 분기 결정** — Phase 2 PR 1 의 `_simple_success` + `_retry_aware_success` 양쪽 도입은 MCP 검증 (success_rate 16.6%) 결과. MCP 없으면 단순 success rate 만 → 부정 인상 위험. Phase 2 PR 2 의 CTA banner 도 동일 (feedback row=0 발견 → CTA 자체 결정).

3. **🚨 Auto-merge KPI 16.6% 메인/서브 swap 검토** — 시각 우선순위 부정 숫자 (36px) > 정확한 숫자 (12px). retry-aware final 을 메인으로 swap 권장. **다음 PR 즉시 적용**.

4. **glass 테마 backdrop-filter ↔ scoped 토큰 충돌 미검증** — `var(--card-bg, var(--bg-surface, ...))` fallback chain 의존, glass 의 backdrop-filter 미적용. **정책 11 8 조합 중 glass 우선 사용자 검증 부탁**.

5. **정책 진화 형식 충족, 행동 변화 0** — 정책 3 진화 (PR 본문 최상단) 3/3 + 정책 11 2/2 적용. 사용자 응답 "머지 수행" 패턴 동일. **정책 2 진화 (Phase 종료 일괄 회신) 첫 검증 = 본 회고 응답 ("회고 OK")** — ✅ 효과 입증.

### P1 — 권장

1. **누적 회귀 가드 = 사용자 결정 영구 보존** — 부활 차단 사례 0이지만 Q3 leaderboard_opt_in 보존 결정 영구 기록 (`test_analytics_service_deprecations.py:131`). **🔴 2026-05-02 후속 정정**: 사용자 명시 요청 *"팀 리더보드 기능 삭제"* + SaaS 전환 의도로 **Q3 결정 (보존) → 정정 폐기** (그룹 61 — alembic 0025). 회고 시점의 결정이 사용자 우선순위 변경에 따라 정정될 수 있음을 보여주는 사례 — **회귀 가드는 결정의 영구 기록이 아닌 "현재 결정의 가시화"** 로 의미 재정의.
2. **정통 TDD Red bug 차단 1건 (UNIQUE 제약)** — TDD 일반화 X, **외부 제약 (FK/UNIQUE) 검증 시 ROI 집중**
3. **회고 자발 요청 = 정책 8 내재화 신호** — *"요청하신대로 ... 여러 에이전트가 같이 병렬로"* (정책 본문 직접 인용)
4. **자발 정보 공유 (Supabase + MCP) = 회고 ROI 입증** — Phase 1 P0 #4 → Phase 2 자발 해소 (회고→정책→행동 사이클 1회 완주)
5. **MCP scope 제한 의무 정책화** — SELECT-only OK, INSERT/DELETE 사전 승인 (본 PR 정책 12 신설)

### P2 — 참고

- 분할 PR 22분 부담 vs 통합 PR review 포기 위험 → 분할 우위
- 사용자 패턴 (`importlib + AttributeError`) default 100% 보존
- CTA banner 위치 검토 (KPI 위 → KPI 아래 + 차트 위 가능성)
- `list_projects` 자동 식별 패턴 default 화

### 정량 매트릭스

| 지표 | Phase 1 (PR 1~5) | Phase 2 (PR 1~3) | 변화 |
|------|---------|---------|------|
| PR 수 | 5 | 7 (Phase 2 PR 1/2 + Supabase fix + 4 docs/test) | — |
| 평균 PR LOC | 670.8 | 175.7 | -73% |
| 정책 7 강화 적용 | 0/5 | 6/7 | +100% |
| nav/링크 임시 깨짐 | 1건 | **0건** | -100% |
| Red 단계 차단 bug | 0 | 1 (UNIQUE) | +1 |
| pre-existing 7 fail | 5 PR 보존 | **7/7 해결** | +7 |
| 정책 3 진화 적용 | — | 3/3 | 100% |
| 정책 11 적용 | — | 2/2 | 100% |
| 자발 정보 공유 | 0건 | 1건 (Supabase MCP) | +1 |
| 회고 자발 요청 | X | ✅ | 정책 8 내재화 |
| MCP 시간 절감 | — | 87% (15분 → 2분) | — |
| 사용자 응답 패턴 | "머지 수행"×5 | "머지 수행"×3 | 동일 |
| **회고 응답 (정책 2 진화 검증)** | (Phase 1 회고에서 진화 결정) | **✅ "회고 OK"** | 첫 검증 완료 |

---

## 3. Claude 자유 발언 결과 (정책 9) — 사용자 응답 반영

### Claude 자성 항목 (회고 시)
1. **MCP 결과 사용자 별도 노출 부족** → **정책 3 강화** (MCP 자율 실행 결과 별도 섹션) 본 PR 신설
2. **Auto-merge KPI 부정 인상 위험 사전 인지 못 함** → **P0 #3 Auto-merge swap 다음 PR 즉시 적용**
3. **glass 테마 호환성 코드 단계 가드 못 함** → 다음 사이클 "테마별 시각 회귀 가드" 검토

### 사용자 응답 — 정책 진화 + 행동 변화
- *"회고 OK"* (2026-05-02) → **정책 2 진화 (Phase 종료 일괄 회신) 첫 검증 완료** ✅
- *"B단계를 승인합니다"* → P0 #3 swap PR 진행 OK + 본 회고 PR 진행 OK 동시
- 정보 비대칭 3건 (Anthropic 비용 / 트래픽 / single-tenant 의도) 회신 보류 — Phase 3 진입 시점 확인 의무

---

## 4. 정책 본문 진화 (CLAUDE.md 본 PR 적용)

| 정책 | 변경 내용 | 적용 위치 |
|------|----------|----------|
| **정책 7 강화 추가** | "응집 = URL + 화면 + 데이터 3종 동시 묶음" 한 줄 추가 + 응집 분할 사례 (Phase 2 PR 1/2 + Supabase fix) 갱신 | CLAUDE.md L617~ |
| **정책 3 강화 (신규)** | MCP 자율 실행 결과 별도 §"MCP 자율 실행 결과" 섹션 의무 + 사용자 acknowledge 요청 | CLAUDE.md (정책 11 후) |
| **정책 12 신설** | MCP scope 제한 의무 — SELECT-only 자율, INSERT/DELETE PII 사전 승인 + 본 사이클 검증 사례 명시 | CLAUDE.md (정책 11 후, 강화 사이) |

---

## 5. Phase 3 진입 전 의무 (사용자 회신 대기)

| # | 의무 | 진행 주체 | 회신 형식 |
|---|------|----------|----------|
| 1 | Anthropic API 토큰 비용 추정 (caching 전략 입력) | 사용자 | 월 $ 또는 token 수 |
| 2 | /dashboard telemetry 24~48h 누적 (Phase 3 우선순위) | 사용자 (Railway 로그) | 일 평균 dashboard_view 횟수 |
| 3 | single-tenant 보존 vs SaaS 전환 의도 (Phase 3 사용자별 노트 가치) | 사용자 | 보존 / SaaS / 미정 |

---

## 6. 다음 사이클 default 패턴 (정책 진화 적용)

- 모든 PR 본문 Summary 직후 "자율 판단 보고" 섹션 (정책 3 진화)
- **MCP 호출 시 §"MCP 자율 실행 결과" 별도 섹션** (정책 3 강화 — 본 PR 신설)
- **MCP scope SELECT-only 자율 / INSERT/DELETE/PII 사전 승인** (정책 12 — 본 PR 신설)
- UI/시각 변경 PR 은 정책 11 의 8 조합 체크리스트 의무
- PR 분할은 응집 단위 — **URL + 화면 + 데이터 3종 동시 묶음** (정책 7 강화 — 본 PR 갱신)
- Phase 종료 시 누적 검증 항목 단일 회신 표 묶음 (정책 2 진화)
- 회귀 가드 누적 모듈 패턴 (`test_*_deprecations.py`) 모든 폐기 사이클 default
- 신규 service 모듈은 in-memory SQLite + 자체 fixture 패턴

---

## 부록 — 사용자 발화 인용 (정책 변경 근거 보존)

- 정책 7 강화 본문 갱신 (P0 #1): Phase 1 회고 시 *"PR 4+5 분리 결정 = 잘못된 판단"* (Claude 자성)
- 정책 12 신설 (P1 #5 + 자성): MCP 활용 검증 시 *"MCP접근 가능합니다"* (사용자) → 5 SELECT 자율 실행 + scope 제한 의무 인지
- 정책 3 강화 (자성 #1): MCP 결과 PR 본문 묻혀버림 → "사용자 별도 노출 의무"
- 회고 자발 요청 (P1 #3): *"다음작업이 큰 내용이라 ... 여러 에이전트가 같이 병렬로 확인 및 검토 해주셨으면 합니다"* (정책 8 본문 직접 인용)
- 회고 응답 (정책 2 진화 첫 검증): *"B단계를 승인합니다. 회고는 OK 입니다"* — 일괄 회신 첫 사례

(Phase 2 종료. P0 #3 Auto-merge swap PR 후 Phase 3 진입 결정.)
