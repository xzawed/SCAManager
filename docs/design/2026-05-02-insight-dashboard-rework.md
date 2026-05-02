# Insight Dashboard 근본 재설계 기획서 — 2026-05-02

> **사용자 발화 (2026-05-02)**:
> *"현재 Insights 탭은 한정적이고 해당 컨셉과 페이지는 다 폐기 후 가장 근본이 되는 대시보드와 정보를 보여주거나 제시하는 무언가 있어야 한다 — 이 내용에 대해 여러 에이전트는 현재 프로젝트 서비스의 사활이 걸린만큼 아주 깊고 많이 토론해도 됩니다."*
>
> **상태**: 5-에이전트 병렬 분석 완료 (2026-05-02). 사용자 검토 + 결정 대기.
> **변경 영향 (예상)**: 코드 826 LOC 폐기 + 250~1100 LOC 신규 (MVP 선정 따라 다름).
> **회귀 위험**: 보존 함수 (`weekly_summary`, `moving_average`, `top_issues`, `resolve_chat_id`) 미파괴 검증 의무.

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
| 개인별 productivity surveillance | GitPrime | 팀 단위 + opt-in 만 (이미 `leaderboard_opt_in` 으로 처리 중) |
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

### 5.3 5-Phase 로드맵

| Phase | 목표 | 핵심 변경 | 예상 PR | 시간 |
|-------|------|---------|--------|------|
| **Phase 1** | MVP-B 출시 | 신규 `/dashboard` + 폐기 자원 정리 + 회귀 가드 + telemetry 1줄 | 2~3 | **1~2일** |
| Phase 2 | 차별 KPI 추가 | Auto-merge 성공률 + AI 정합도 카드 (FB row 수 ≥10 검증 후) | 2 | 1~2일 |
| Phase 3 | 모드 토글 (Claude 톤) | 데이터 모드 ↔ 노트 모드 (Anthropic SDK + caching) | 2 | 2일 |
| Phase 4 | 모바일 우월 + 단축키 | scroll-snap + 키보드 (`g d`, `?`) | 2 | 1~2일 |
| Phase 5 | Telegram 미러링 | `/dashboard` Telegram 명령 (`_handle_stats` 패턴 차용) | 1 | 1일 |

**총 합계**: 9~10 PR · **6~9 작업일**

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

| 옵션 | 장점 | 단점 | 위험 |
|------|------|------|------|
| 🅐 **컬럼 보존 ★** | downgrade 위험 0, Phase 5 재개 가능 | 미사용 컬럼 잔존 | **저** |
| 🅑 0025 마이그레이션 drop | 스키마 정리 | downgrade 손실 + 5-way sync 동기화 의무 | 중 |

**고려했으나 제시 안 한 안**: "soft-deprecate (코멘트만 추가, 향후 drop)" — 결정 미루는 패턴.

#### Q4: Phase 2 시작 전 데이터 검증 의무

| 항목 | 측정 방법 | 결정 입력 |
|------|---------|---------|
| `analysis_feedbacks` row 수 | `SELECT COUNT(*) FROM analysis_feedbacks` 1회 | < 10 시 Phase 2 보류, Phase 3 (Claude narrative) 우선 |
| `merge_attempts WHERE state != 'legacy'` 수 | 동일 | < 20 시 "Auto-merge 성공률" 카드 가치 ↓ |

### 6.2 자율 판단 보고 (정책 3)

본 기획 작성 중 Claude 가 자율 판단한 항목:

1. **`top_issues` 함수 보존 권장** — 사용자가 명시 폐기 대상 3개만 지정. `top_issues` 는 폐기 페이지에서만 사용되지만 신규 dashboard 의 Phase 2 입력으로 가치 있음. **이의 있으시면 알려주세요.**
2. **C+E 모드 토글 권장** — 사용자가 단일 컨셉 요청했으나 "사활 결정" 명시로 단일 베팅 위험 회피. **단일 C 만 채택도 가능.**
3. **Phase 1 에 telemetry 1줄 의무 추가 권장** — `logger.info("dashboard_view ...")` 만으로 Phase 2 우선순위 결정 가능. 신설 비용 0.

---

## 7. 사용자 검증 필요 (정책 2 — PR 본문 의무)

본 기획 PR 머지 전 결정:

- [ ] Q1 MVP 옵션 (🅐/🅑/🅒/🅓) — 권장 🅑
- [ ] Q2 URL 정책 (🅐/🅑/🅒) — 권장 🅒
- [ ] Q3 leaderboard_opt_in 처리 (🅐/🅑) — 권장 🅐
- [ ] Q4 Phase 2 데이터 검증 의무 동의 여부
- [ ] 별도 PR — `Analysis.result["issues"]` JSON 에 `category/language/rule_id` 직렬화 (1줄 fix, 데이터 손실 방지)
- [ ] `top_issues` 함수 보존 결정 (자율 판단 항목 1)

---

## 8. 다음 단계

1. **본 기획 PR 머지** — 사용자 결정 반영
2. **Phase 1 PR 시리즈 착수** — TDD Red → Green → Refactor (CLAUDE.md L583)
3. **Phase 1 출시 후 회고** — 정책 8 (다중 에이전트) + 정책 9 (Claude 자유 발언) 적용
4. **Phase 2~5 결정** — 회고 결과로 우선순위 조정

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
