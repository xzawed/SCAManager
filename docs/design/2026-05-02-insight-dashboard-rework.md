# Insight Dashboard 근본 재설계 기획서 — 2026-05-02

> **사용자 발화 (2026-05-02)**:
> *"현재 Insights 탭은 한정적이고 해당 컨셉과 페이지는 다 폐기 후 가장 근본이 되는 대시보드와 정보를 보여주거나 제시하는 무언가 있어야 한다 — 이 내용에 대해 여러 에이전트는 현재 프로젝트 서비스의 사활이 걸린만큼 아주 깊고 많이 토론해도 됩니다."*
>
> **상태**: ✅ **Phase 3 100% 완료 + postlude 완료** (2026-05-04). 사용자 회신 4건 모두 처리 (caching #218 / 카드 4종 #219 / 모드 default #221 / RLS 모델 #223). Phase 3 PR 1~6 (#218~#224) + postlude 4 PR (RLS middleware #228 / backfill #229 / cleanup #230 / sync #231) + 종결 회고 (#232) + 정책 진화 (#233) 모두 머지. 상세 진행 = `docs/design/INDEX.md` + `docs/STATE.md`.
> **변경 영향 (실측)**: Phase 1+2+3 = 누적 38+ PR 머지, 코드 826 LOC 폐기 + dashboard_service 7 함수 신규 (insight_narrative 포함) + 격리 헬퍼 2건 + alembic 0025/0026 (leaderboard drop + RLS policy) + RLS middleware (ASGI + contextvars + event listener 3-tier).
> **회귀 위험**: 보존 함수 (`weekly_summary`, `moving_average`, `resolve_chat_id`) 미파괴 — 회귀 가드 통과 (`top_issues` 는 Phase 1 PR 1 폐기 / `frequent_issues_v2` 신규 대체). pre-existing 5 fail (사이클 62~65 누적 4 사이클 보류) 사이클 66 #227 종결.

---

## 0. 배경

### 0.1 사용자 진단

> *"코드 리뷰 및 데이터가 프로젝트 내 수집되는 데이터가 제법 되는데, 사람들에게 '왜 이 서비스를 써야 하는지', '이 서비스를 이용하면 어떤 내용을 우리가 알 수 있고 개선을 할 수 있는지' 가치에 대해 근본적인 대시보드나 뷰어가 없습니다."*

핵심 문제:
- DB 에 풍부한 데이터 (Analysis × MergeAttempt × AnalysisFeedback × GateDecision 4-way join) 가 쌓이지만 **시각화 부재**
- 기존 `/insights` + `/insights/me` 는 "한정적 표 only" — 차트 0개 (`insights.html` 전체에 `<canvas>` 미존재), drill-down 부재, 비교 축 1개뿐
- **Why 답변 부재** — 사용자가 "이 서비스를 왜 써야 하는가" 한눈에 답할 화면 없음

### 0.2 프로젝트 사활 결정 명시

사용자가 "프로젝트 서비스의 사활이 걸린만큼" 으로 명시 — 단일 컨셉 베팅 위험 회피 + 사용자 검토 깊이 요구.

---

## 1. 데이터 자산 정찰 결과

### 1.1 보유 데이터 (즉시 활용 가능)

| 인사이트 | 추출 함수 / 위치 | 데이터 한계 |
|---------|----------------|------------|
| 일별/주별 평균 점수 | `analytics_service.weekly_summary:21`, `moving_average:79` | — |
| 리포별 점수·등급 분포 | `analytics_service.repo_comparison:234` | — |
| 자주 발생 이슈 Top N | `analytics_service.top_issues:124` | tool 빈도만 — `rule_id` 부재 |
| auto-merge 성공률 + 실패 사유 분포 | `merge_attempt_repo.count_failures_by_reason:72` | `state="legacy"` 행 제외 필요 |
| 사용자 ↔ AI 점수 정합도 | `analysis_feedback_repo.get_calibration_by_score_range:75` | **현재 미사용** — 샘플 수 적을 가능성 |
| Gate 응답 시간 (semi-auto) | `Analysis.created_at` ↔ `GateDecision.decided_at` 차이 | 전용 헬퍼 신규 필요 |

### 1.2 미활용 차별 데이터 (Phase 2 KPI 후보)

- **MergeAttempt** — `failure_reason` 정규 태그 (`branch_protection_blocked`, `unstable_ci` 등) — **dashboard 미노출**
- **AnalysisFeedback** — thumbs +1/-1 — **인프라만 있고 화면 미구현**
- **Claude API 비용/latency** — `claude_metrics.py` 로그만 — DB 영속화 부재
- **stage 별 latency** — `stage_metrics.py` 로그만 — DB 영속화 부재

### 1.3 데이터 손실 발견 (즉시 fix 권장)

🔴 **`Analysis.result["issues"]` JSON 에 `category` / `language` / `rule_id` 미직렬화** (`pipeline.py:75-79`) — 향후 언어별/룰별 분석 차단. **1줄 코드 수정으로 신규 데이터부터 즉시 복구 가능** — 본 기획 진행 전 별도 PR 권장.

---

## 2. 사용자 가치 제안 — Why 답변 매트릭스

### 2.1 SCAManager 만의 차별 답 5건

기존 도구가 답하지 않는 SCAManager 의 고유 질문:

1. **"노트북 없이 핸드폰 한 번 탭으로 PR 머지"** — Telegram 인박스 통합 (다른 dashboard 도구는 슬랙 webhook 만)
2. **"Push 도 분석한다"** — PR 만 분석하는 SaaS (CodeRabbit, Sourcery) 와 차별
3. **"단일 점수로 모든 것 비교"** — 정적 10종 + AI 5축 → 100점 환산 (다른 도구는 비교 불가 단위)
4. **"Merge 가 왜 막혔는지 정규 사유 + 권장 조치"** — `merge_failure_advisor.get_advice(reason)` (다른 도구는 "fail" 만 반환)
5. **"내 인프라, 내 데이터"** — 자체 호스팅 + MIT (SonarCloud/CodeRabbit SaaS 와 차별)

### 2.2 페르소나별 답변 매트릭스 (5 페르소나)

| 페르소나 | 가장 묻고 싶은 질문 | 현 답변 가능? | dashboard 가 답해야 할 것 |
|---------|------------------|------------|--------------------|
| **솔로 개발자** | "어제보다 오늘 코드가 나아졌나?" | ✅ 점수 추세 차트 | KPI 카드 + sparkline |
| **소규모 팀 리더** | "이번 주 우리 팀 평균 품질은?" | ✅ weekly_summary | Pulse 4 카드 |
| **오픈소스 메인테이너** | "외부 PR 안전한가?" | ✅ bandit + Semgrep + slither | 시각화 부재 |
| **CTO** | "Auto-merge 성공률 / 실패 사유 분포?" | ✅ MergeAttempt 집계 가능 | **dashboard 없음** |
| **신입 개발자** | "내 약한 영역 (보안/품질/테스트)?" | ✅ 점수 breakdown | 시각화 부재 |

### 2.3 dashboard 가 답해야 할 핵심 질문 Top 10

1. 이번 주 우리 팀 / 내 점수 추세는?
2. Auto-merge 성공률과 막힌 사유 분포?
3. AI 리뷰 정합도 (thumbs up/down 비율)?
4. AI 비용 (Claude API) 일/월 추적?
5. 어느 단계가 가장 느린가?
6. 자주 발생하는 이슈 Top N?
7. 팀원 별 평균 점수 (opt-in)?
8. 멀티 리포 점수 비교?
9. 개인 점수 추세 (author)?
10. 보안 위험 (bandit HIGH) 시계열?

---

## 3. 대시보드 컨셉 안건 5건 비교

### 3.1 9-차원 비교 매트릭스

| 차원 | A: Linear | B: Datadog | **C: Stripe ★** | D: GitHub | **E: AI 노트** |
|------|----------|-----------|------------|----------|----------|
| 정보 밀도 | ★ (낮음) | ★★★★★ (최고) | ★★★ (균형) | ★★★★ (높음) | ★★ (낮음) |
| 모바일 호환 | ★★★★★ | ★★ | ★★★★ | ★★★ | ★★★★★ |
| 구현 난이도 | 저 (1-2 PR) | 고 (5-7 PR) | 중 (3-4 PR) | 중 (3-4 PR) | 중-고 (3-5 PR) |
| 학습 곡선 | 0 (즉시 이해) | 높음 | 낮음 (Stripe 익숙) | 0 (gh 익숙) | 낮음 (자연어) |
| drill-down | 1단계 (얕음) | 3단계 (깊음) | 2단계 (적정) | 2단계 | 1-2단계 |
| 커스터마이징 | 없음 | 위젯 add/remove | series toggle | 탭 전환 | follow-up CTA |
| 톤 | 결정 중심 | 데이터 중심 | 균형 | 친숙 | 자연어/스토리 |
| 페르소나 적합 | 솔로/PM | CTO/SRE | **모든 페르소나** | gh 헤비 | 신규/PM/디자이너 |
| 위험 | 중 (rule 품질) | 고 (surface) | **저 (검증된)** | 중 (gh 흉내) | 중-고 (rule 품질) |

**ROI 추정**: C = 고 / E = 고 (rule 검증 후) / D = 중-고 / A = 중 / B = 저

### 3.2 권장 — 컨셉 C (Stripe-style) + 컨셉 E (AI 노트) 모드 토글

**C 단독이 아닌 C+E 권장 사유**:
- "프로젝트 사활" → 단일 컨셉 베팅 위험
- C 단독 = 기존 사용자 ok, 신규 진입 장벽 그대로
- E 단독 = 차별화 ↑, 그러나 데이터 사용자 이탈
- **C+E 모드 토글 = 양쪽 페르소나 동시 흡수 + 단일 컨셉 실패 시 회복 가능**

기존 Settings 의 `data-settings-mode` 단순/고급 토글 패턴 (`settings.html` `.adv-only` 평탄화) 을 dashboard 에도 동일 적용.

---

## 4. 경쟁 벤치마크 — 따라할 / 회피할 / 발명할

### 4.1 따라할 패턴 5건 (검증된 산업 표준)

| 패턴 | 출처 | SCAManager 적용 |
|------|------|----------------|
| **숫자 + delta + sparkline 3-요소 KPI** | Stripe | 평균 점수 카드: "78 ▲ +3 vs last week [sparkline]" |
| **Pulse 4 카드 (이번 주 요약)** | GitHub Insights | overview 최상단에 4 카드 row |
| **시간 범위 셀렉터 + vs prev 비교** | Datadog | 1d/7d/30d 토글 + delta 자동 갱신 |
| **빈 상태에 즉시 실행 가능 코드 스니펫** | Sentry | Webhook URL + install-hook.sh 즉시 노출 |
| **Quality Gate PASS/FAIL 단일 배지** | SonarCloud | 리포 카드 상단 "최근 PR Gate" 배지 |

### 4.2 회피할 패턴 4건

| 회피 패턴 | 출처 | 이유 |
|----------|------|------|
| 6+ KPI 카드 default 노출 | SonarCloud | 신규 사용자 압도 |
| 위젯 자유 배치 dashboard builder | Datadog | 우리 사용자는 dashboard 빌더가 아님 |
| 개인별 productivity surveillance | GitPrime | ~~팀 단위 + opt-in (`leaderboard_opt_in`)~~ → 그룹 61 폐기. SaaS 전환 시 별도 멀티 사용자 인사이트 모델 신설 (RLS 기반 권한) |
| dashboard 약함, PR 인라인 중심 | CodeRabbit | 우리는 dashboard 가 본질 |

### 4.3 발명할 패턴 (SCAManager 만의 차별)

🌟 **AI 점수 정합도 게이지** — "Claude 점수 ↔ 사람 판단 일치율 87%" — **어떤 경쟁사도 미보유**
🌟 **Auto-merge 성공률 + 실패 사유 분포** — `MergeAttempt.failure_reason` 정규 태그 활용
🌟 **점수 delta 사유 자연어 요약** — "이 PR 점수 -8 — 보안 이슈 2건 + 테스트 누락"

> **마케팅 가치**: "다른 도구는 AI 점수만 보여주지만, SCAManager 는 그 점수가 맞는지도 알려준다."

---

## 5. MVP 로드맵 (4 옵션 비교)

### 5.1 MVP 매트릭스

| 항목 | MVP-A (Pulse only) | **MVP-B (Pulse+Trend) ★** | MVP-C (Pulse+Trend+Compare) | MVP-D (Full) |
|------|---|---|---|---|
| 구성 | KPI 4 + sparkline | KPI 4 + 라인 차트 | KPI 4 + 차트 + 비교 표 | + Top 이슈 + 머지 성공률 + AI 정합도 |
| 신규 service 함수 | 1 | 2 | 3 | 5 |
| 신규 회귀 가드 | ~25건 | ~40건 | ~55건 | ~85건 |
| 폐기 LOC | 826 | 826 | 826 | 826 |
| 신규 LOC | ~250 | ~450 | ~650 | ~1100 |
| **순 LOC** | **-576** | **-376** | **-176** | **+274** |
| 예상 PR | 2 | **2~3** | 4 | 6~7 |
| 예상 시간 | 1일 | **1~2일** | 3일 | 5~7일 |
| 사고 위험 | 낮음 | **낮음** | 중 | 높음 |

### 5.2 권장 — MVP-B 단일 출시 → Phase 2 차별 KPI 추가

**선정 사유**:
1. **MVP-A 는 시각적 가치 부족** — sparkline 만으로 추세 인지 어려움
2. **MVP-C/D 는 사용자 검증 전 과도 투자** — 5~7일 후 "별로" 발견 시 회복 비용 ↑
3. **MVP-B 는 차별 가치 + 검증 가능성 균형** — Chart.js vendoring 재사용 (UI 감사 Step C 자산 활용)
4. **AI 정합도 / Auto-merge 성공률 은 Phase 2 차별 KPI 로 분리** — 데이터 부족 위험 (FB row 수 미상) 을 Phase 1 의존성에서 제외

### 5.3 5-Phase 로드맵 (2026-05-02 사용자 회신 후 갱신)

| Phase | 상태 | 목표 | 핵심 변경 | 예상 PR | 시간 |
|-------|-----|------|---------|--------|------|
| **Phase 1** | ✅ 완료 (그룹 60) | MVP-B 출시 | 신규 `/dashboard` + 폐기 자원 정리 + 회귀 가드 + telemetry 1줄 | 5 PR | 단일 작업일 |
| **Phase 2** | ✅ 완료 (그룹 60) | 차별 KPI + CTA | Auto-merge 성공률 (단순+retry-aware) + 실패 사유 + feedback CTA banner | 3 PR (Auto-merge + CTA + Supabase 호환) | 단일 작업일 |
| **Phase 3 (갱신)** | 진입 의무 | **SaaS 전환 토대 + Insight 모드 + caching** | (a) Anthropic prompt caching (Sonnet input 90% 절감) (b) 모드 토글 📊/💬 (c) Insight 모드 (Claude 톤 노트 — 사용자별 분기 토대) (d) RLS / 멀티 테넌트 권한 모델 (Supabase RLS 차용) | **6~8 PR** | **3~5일** |
| Phase 4 | 보류 | 모바일 우월 + 단축키 | scroll-snap + 키보드 (`g d`, `?`) | 2 | 1~2일 |
| Phase 5 | 보류 | Telegram 미러링 | `/dashboard` Telegram 명령 (`_handle_stats` 패턴 차용) | 1 | 1일 |

**총 합계 (Phase 3 갱신 후)**: ~16 PR · ~5~9 작업일 (Phase 1+2 완료 = 8 PR / 1일 = 진행 ↑)

**Phase 3 PR 분할 안 (응집 단위 — 정책 7 강화)**:
| PR # | 응집 단위 | 시간 |
|------|---------|-----|
| Phase 3 PR 1 | **Anthropic prompt caching 인프라** — `src/analyzer/io/ai_review.py` + `src/services/dashboard_service.py` (Insight 모드 함수 신설 시) Sonnet system prompt + few-shot caching 적용 | 1~2시간 |
| Phase 3 PR 2 | **Insight 모드 service** — `dashboard_service::insight_narrative(db, user_id, days, *, now)` (Claude API + caching + ✨ 잘한 것 / 🔍 신경 쓸 것 / 📊 숫자 / 💬 다음 4 카드) | 2~3시간 |
| Phase 3 PR 3 | **Insight 모드 라우트 + 템플릿** — `/dashboard?mode=insight` + `dashboard.html` 모드 토글 (📊/💬) + Insight 노트 카드 4종 + 차트 cache 보존 (모드 전환 시 재요청 X) | 1~2시간 |
| Phase 3 PR 4 | **사용자 신호 기반 default 모드** — `_detect_initial_mode` 헬퍼 (settings 패턴 차용) + `?mode` URL 파라미터 + localStorage persist | 1시간 |
| Phase 3 PR 5 | **SaaS 전환 토대 — RLS 권한 모델** (Supabase RLS 또는 SQLAlchemy session-level filter) — `Repository.user_id` 기반 dashboard 격리 | 2~3시간 |
| Phase 3 PR 6 | **Insight 모드 회귀 가드 + 통합/E2E** — Claude API mock + caching mock + 모드 토글 e2e | 1~2시간 |

---

## 6. 종합 권장안 — 최종 결정 필요 항목

### 6.1 핵심 결정 4건 (정책 1 적용 — 장단점 명시)

#### Q1: MVP 범위

| 옵션 | 장점 | 단점 | 위험 | 권장 시점 |
|------|------|------|------|----------|
| 🅐 MVP-A (Pulse only) | 가장 작음 (1일), 회귀 0 | 시각 가치 ↓ | 저 | 사용자 신뢰 낮을 때 |
| 🅑 **MVP-B ★** | 균형 + Chart.js 재사용 | Phase 2 의존 | **저** | **검증된 안전 베팅** |
| 🅒 MVP-C | 비교 가치 보존 | 멀티-리포 쿼리 회귀 위험 | 중 | 비교 KPI 사용자 다수 시 |
| 🅓 MVP-D | 한 번에 완성 | 5 영역 동시 사고 | 고 | 사용자 ↔ Claude 검증 충분 시 |

**고려했으나 제시 안 한 안**: "기존 `/insights` 부분 리네임 + KPI in-place 추가" — 826 LOC 폐기 결정과 모순.

#### Q2: URL 정책

| 옵션 | 장점 | 단점 | 위험 | 권장 시점 |
|------|------|------|------|----------|
| 🅐 `/insights` URL 유지 | 북마크 보존, nav 무변경 | "Insights" 의미 변화 혼란 | 저 | 활성 사용자 베이스 큼 |
| 🅑 `/dashboard` 신설 + `/insights` 410 | 새 시작 메시지 | 북마크 깨짐 | 중 | 활성 사용자 적음 |
| 🅒 **`/dashboard` 신설 + `/insights` 301 redirect ★** | 양쪽 보존 | redirect 라우트 1개 | **저** | **사용자 트래픽 미상 (default)** |

#### Q3: `leaderboard_opt_in` 컬럼 처리

> **🔴 결정 정정 (그룹 61 / 2026-05-02)**: 본 사이클 머지 후 사용자 명시 요청 *"팀 리더보드 기능 삭제"* + SaaS 전환 의도로 **🅑 (drop) 으로 정정** (alembic 0025). 아래 옵션 표는 결정 시점 보존, **현재 결정은 🅑**.

| 옵션 | 장점 | 단점 | 위험 |
|------|------|------|------|
| 🅐 ~~컬럼 보존 ★~~ (정정 폐기) | downgrade 위험 0, Phase 5 재개 가능 | 미사용 컬럼 잔존 | **저** |
| 🅑 **alembic 0025 drop ★ (정정 채택)** | 스키마 정리 + SaaS 전환 시 별도 멀티 사용자 모델 신설 | downgrade 손실 + 5-way sync 동기화 의무 | 중 |

**고려했으나 제시 안 한 안**: "soft-deprecate (코멘트만 추가, 향후 drop)" — 결정 미루는 패턴.

#### Q4: Phase 2 시작 전 데이터 검증 의무

| 항목 | 측정 방법 | 결정 입력 |
|------|---------|---------|
| `analysis_feedbacks` row 수 | `SELECT COUNT(*) FROM analysis_feedbacks` 1회 | < 10 시 Phase 2 보류, Phase 3 (Claude narrative) 우선 |
| `merge_attempts WHERE state != 'legacy'` 수 | 동일 | < 20 시 "Auto-merge 성공률" 카드 가치 ↓ |

### 6.2 자율 판단 보고 (정책 3) + 사용자 응답 (2026-05-02)

본 기획 작성 중 Claude 가 자율 판단한 항목 + 사용자 응답:

| # | Claude 자율 판단 | 사용자 응답 (2026-05-02) | 결정 |
|---|----------------|----------------------|------|
| 1 | `top_issues` 함수 보존 권장 | *"코드 내 사용을 하지 않거나 보류의 내용은 없었으면 합니다 — 폐기하기를 바랍니다"* | **폐기 확정** ✅ |
| 2 | C+E 모드 토글 권장 | *"컨셉의 경우 목업 디자인이 있었으면 합니다 — 확인 후 결정 가능"* | **목업 검토 후 재결정** 🔄 |
| 3 | Phase 1 telemetry 1줄 의무 추가 | (응답 보류 — 컨셉 결정 후) | 보류 |

### 6.3 사용자 결정 사항 반영 (2026-05-02 응답)

**원칙**: "근본적인 재설계 작업이기에 코드 내 사용하지 않거나 보류의 내용은 없었으면 합니다."

#### 폐기 결정 함수 4종 (확정)
- `analytics_service.author_trend` (L180-231)
- `analytics_service.repo_comparison` (L234-292)
- `analytics_service.leaderboard` (L295-346)
- **`analytics_service.top_issues` (L124-177)** ← 추가 결정 ✅

#### 폐기 보존 함수 (cron / Telegram 명령 의존성으로 유지)
- `analytics_service.weekly_summary` (L21-76) — `cron_service.run_weekly_reports`, `telegram_commands._handle_stats` 의존
- `analytics_service.moving_average` (L79-121) — `cron_service.run_trend_check` 의존
- `analytics_service.resolve_chat_id` (L349-382) — `cron_service` 다수 의존
> 위 3 함수는 **dashboard 외 운영 파이프라인 의존성** 으로 폐기 시 cron + Telegram 사망. 보존이 사용자 원칙 위반이 아님 (실제 사용 중).

#### 폐기 LOC 갱신
- 기존: 826 LOC (3 함수 + 2 페이지 + 2 라우트 + 3 테스트)
- **갱신: 880 LOC** (+`top_issues` 54 LOC + 관련 테스트)
- 신규 dashboard MVP-B 신규 LOC ~450 → 순 LOC **-430**

#### Phase 2 의존성 변경
**`top_issues` 폐기로 Phase 2 의 "자주 발생 이슈 Top N" 카드 입력 부재** → 신규 함수 작성 의무 또는 Phase 2 KPI 항목에서 제외 결정 필요.

옵션:
| 옵션 | 장점 | 단점 | 위험 |
|------|------|------|------|
| 🅐 Phase 2 에서 신규 `frequent_issues_v2()` 함수 작성 | dashboard 차별 KPI 보존 | Phase 2 작업량 +1 함수 | 저 |
| 🅑 Phase 2 KPI 에서 "자주 발생 이슈" 항목 제외 | Phase 2 단순화 | 잠재 사용자 가치 감소 | 저 |

### 6.4 목업 디자인 첨부 (사용자 요청)

사용자 발화: *"컨셉의 경우 목업 디자인이 있었으면 합니다"*

본 PR 에 시각 목업 HTML 2개 첨부:
- `docs/design/mockups/2026-05-02-dashboard-concept-c-stripe.html` — Stripe-style KPI 카드 + 차트
- `docs/design/mockups/2026-05-02-dashboard-concept-e-ai-note.html` — AI 노트 모드 (Claude 톤)

**확인 방법**:
```bash
# 로컬에서 브라우저로 직접 열기
open docs/design/mockups/2026-05-02-dashboard-concept-c-stripe.html
open docs/design/mockups/2026-05-02-dashboard-concept-e-ai-note.html
```

또는 GitHub PR 페이지에서 raw view + HTML preview 가능.

목업 데이터는 가짜 — 실제 동작 시뮬레이션 아님. 시각 컨셉 확인 전용.

### 6.5 추가 결정 항목 (목업 검토 후 — 2026-05-02 사용자 응답)

| Q | 항목 | 사용자 결정 (2026-05-02) | 사용자 발화 인용 |
|---|------|----------------------|------------------|
| 5 | 컨셉 최종 결정 | **🅒 C+E 모드 토글 채택** ✅ | *"둘다 필요해 보입니다. 하나는 사용자가 한눈에 확인하고 판단할수 있는 내용이고 하나는 AI가 흐름을 분석하여 제안하는 내용이기에 두 페이지 모두 같은 정보를 다른 용도로 각각 서비스 하는 내용입니다."* |
| 6 | (Q5=C+E 채택 시) default 모드 | **🅒 사용자 신호 기반** ✅ (settings `_detect_initial_mode` 패턴 차용) | *"그외 제게 제안주신 내용이나 방향은 모두 승인합니다."* |
| 7 | Phase 2 "자주 발생 이슈" 카드 처리 | **🅐 신규 함수 작성** ✅ (`frequent_issues_v2()`) | (동일 — 모두 승인) |

**추가 사용자 디자인 방향**:
> *"컨셉은 심플하고 모던하고 요즘 느낌이 많이 나야 합니다. 클로드 디자인이 여기에 개입하여 좀더 디자인이 고도화 되는 방안이 되었습니다."*

→ v1 목업 (concept-c-stripe / concept-e-ai-note) 은 base 디자인 시연용으로 보존, **v2 목업** (`-v2-overview` / `-v2-insight`) 에 Claude × Linear 하이브리드 디자인 시스템 적용 (그룹 55 토큰 기반 — warm beige + Anthropic orange + Crimson Pro serif heading + 채도 -20% sage/sand/muted-red 시맨틱 + claude-light/claude-dark 4-테마 정합).

### 6.6 v2 목업 (Claude × Linear 디자인 시스템)

| 파일 | 역할 | 특징 |
|------|------|------|
| `docs/design/mockups/2026-05-02-dashboard-v2-overview.html` | Overview 모드 (📊) | Stripe-style 4 KPI (숫자+delta+sparkline) + 메인 차트 (3 리포 비교) + 보조 카드 2종 |
| `docs/design/mockups/2026-05-02-dashboard-v2-insight.html` | Insight 모드 (💬) | Claude 톤 인사 + 4 카드 (✨ 잘한 것 / 🔍 신경 쓸 것 / 📊 숫자 / 💬 CTA) + mini chart 인용 |

**공통 디자인 토큰**:
- 배경: `#F5F1E8` warm cream (Anthropic-inspired)
- 액센트: `#D97757` orange
- 의미색: sage (`#9CAF88`) / sand (`#D4A574`) / muted-red (`#C84E3F`) — 채도 -20%
- 폰트: Crimson Pro (serif heading) + Inter (body) + JetBrains Mono (code)
- 모드 토글: 양 페이지 topbar 에 `[📊 Overview / 💬 Insight]` 토글 (서로 링크)
- 테마 토글: claude-light / claude-dark (Chart.js 색 동적 read + themechange 재빌드)
- 모바일 반응형: 4 KPI → 2×2 → 1, WCAG 2.5.5 (≥44px) 준수

**확인 방법**:
```bash
# 로컬 HTTP 서버 (앞서 띄워둔 8765 포트 활용)
open http://localhost:8765/2026-05-02-dashboard-v2-overview.html
open http://localhost:8765/2026-05-02-dashboard-v2-insight.html

# 또는 직접 브라우저로
open docs/design/mockups/2026-05-02-dashboard-v2-overview.html
```

목업 데이터는 모두 가짜. 컨셉 v2 시각 확인 전용.

---

## 7. 사용자 검증 필요 (정책 2 — PR 본문 의무)

본 기획 PR 머지 전 결정 — **2026-05-02 사용자 응답 반영**:

- [x] Q1 MVP 옵션 — **🅑 MVP-B 채택** (사용자 승인)
- [x] Q2 URL 정책 — **🅒 `/dashboard` 신설 + `/insights` 301 redirect 채택** (사용자 승인)
- [x] Q3 leaderboard_opt_in 처리 — ~~🅐 컬럼 보존 채택~~ → **🅑 컬럼 폐기로 정정** (그룹 61 / 2026-05-02 사용자 명시 요청 *"팀 리더보드 기능 삭제"* + SaaS 전환 의도. alembic 0025 + 5-way sync. 회귀 가드 = `tests/unit/services/test_analytics_service_deprecations.py::test_leaderboard_opt_in_column_removed`)
- [x] Q4 Phase 2 데이터 검증 의무 — **동의** (사용자 승인)
- [x] 별도 PR (`category/language` 직렬화) — **PR #185 머지 완료** ✅
- [x] `top_issues` 함수 보존 결정 — **폐기 확정** (사용자 명확 거부)
- [x] Q5 컨셉 — **🅒 C+E 모드 토글 채택**
- [x] Q6 default 모드 — **🅒 사용자 신호 기반**
- [x] Q7 자주 발생 이슈 카드 — **🅐 신규 함수 작성 (`frequent_issues_v2()`)**
- [x] **v2 목업** (Claude × Linear) 작성 — `docs/design/mockups/2026-05-02-dashboard-v2-{overview,insight}.html`
- [ ] **사용자 시각 검증** — 로컬 브라우저 새로고침 후 v2 목업 2종 확인 (대기 중)

---

## 8. 다음 단계

### 8.1 Phase 1+2 완료 (2026-05-02 그룹 60+61) ✅

- **본 기획 PR 머지** ✅
- **Phase 1 PR 시리즈** = 5 PR 머지 완료 (그룹 60 #188~#193)
- **Phase 1 회고** = 5 에이전트 병렬 회고 + Claude 자유 발언 → 정책 11/12 신설 + 정책 2/3/7 진화
- **Phase 2** = Auto-merge KPI + feedback CTA + Supabase 호환 (3 PR 머지)
- **Phase 1+2 통합 회고** = 정책 13 신설 + 정책 11 강화 (P0 OAuth 사고 후속)
- **그룹 61 후속** = leaderboard Q3 정정 폐기 + stale sync + 종단간 가드 + integration 24 fail 정리

### 8.2 사용자 회신 (2026-05-02 Phase 1+2 종료 직후)

| 정보 | 회신 | 영향 |
|------|------|------|
| Anthropic API 비용 | ~$25 (집중 사용 시) / Sonnet 4.6 주, Opus 4.7 보조 | caching 우선 (90% 절감) |
| 트래픽 / 사용자 수 | "저 혼자" (1인 운영) | dashboard_view 빈도 ↓ |
| 운영 모델 | **"SaaS 했으면 좋겠습니다"** | **Phase 3 우선순위 대전환 — SaaS 전환 토대** |
| 신규 요청 | **"팀 리더보드 기능 삭제"** | Q3 정정 폐기 (그룹 61 #206) |

### 8.3 Phase 3 진입 의무 (다음 사이클)

1. **Anthropic prompt caching 적용 패턴 확정** — 본 기획서 §5.3 Phase 3 PR 1 의 caching 전략. Sonnet system prompt + few-shot 예시 + (가능 시) tool definitions 모두 cache.
2. **Insight 모드 카드 4종 디자인 결정** — v2 목업 (`docs/design/mockups/2026-05-02-dashboard-v2-insight.html`) 의 ✨ 잘한 것 / 🔍 신경 쓸 것 / 📊 숫자 / 💬 다음 4 카드 그대로 운영 적용 vs 디자인 정정
3. **모드 토글 default 결정** — 사용자 신호 기반 (`_detect_initial_mode` 차용) 또는 단순 URL `?mode=insight` 기반
4. **RLS 권한 모델 결정** — Supabase RLS (DB level) vs SQLAlchemy session-level filter (app level) — single-tenant → multi-tenant 전환 토대

### 8.4 Phase 3 후 Phase 4/5

Phase 4 (모바일 우월) + Phase 5 (Telegram 미러링) — Phase 3 SaaS 전환 후 우선순위 재논의 (멀티 사용자 시 Telegram 봇 = 사용자별 인증 필요 등).

---

## 부록 — 5-에이전트 분석 출처

| 관점 | 분석 분량 | 핵심 출처 |
|------|---------|---------|
| 데이터 자산 정찰 | ~2000단어 | `src/models/*` 8 ORM, `pipeline.py:54-80`, `analytics_service.py` 전체 |
| 사용자 가치 제안 | ~2000단어 | README.md, CLAUDE.md, 5 페르소나 매트릭스 |
| 대시보드 컨셉 비교 | ~2500단어 | 5 컨셉 wireframe + 9-차원 매트릭스 |
| 경쟁 벤치마크 | ~2500단어 | 15 제품 (SonarCloud/CodeRabbit/Stripe/Datadog 등) |
| MVP 로드맵 | ~2500단어 | 4 MVP × 12 항목 + 12 위험 매트릭스 |

각 에이전트 보고서 원본은 본 PR 의 review thread 에 인용 가능 (필요 시 별도 첨부).
