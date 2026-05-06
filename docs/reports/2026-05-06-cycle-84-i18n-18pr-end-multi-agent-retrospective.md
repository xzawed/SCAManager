# 사이클 84 다국어 i18n 18 PR 종결 회고 — 5+1 다중 에이전트

> 회고 일자: 2026-05-06
> 회고 대상: 사이클 84 (2026-05-05) — 다국어 (영어/한국어/일본어) i18n Phase 1~5 18 PR 종결
> 회고 패턴: 5+1 cross-verify (1차 5 관점 병렬 + 6차 cross-verify 종합)

---

## 0. 회고 배경 + 자율 진행 사유

사이클 84 (2026-05-05) = **단일 작업일 18 PR 진행** (i18n 영어/한국어/일본어 종합 지원). Phase 1~5 분할 + 사용자 명시 task ("긴급 + 영어/한국어/일본어 + 코드리뷰 + 대시보드 메뉴 커버 + 5번 정도 검수 + 세부 기획안") + 14회 연속 "머지 했습니다 다음 작업 진행" 신호 정합.

PR-18 (#304) = i18n 18 PR 종결 sync 단일 응집 (smoke 11 + baseline + CLAUDE.md 정책 진화 묶음) 머지 완료. 본 회고 = **Phase 5 종결 + 18 PR 종결** 마일스톤 회고 (정책 8 default — 다중 에이전트 5+1).

**자율 진행 사유 (정책 9 완화 default 정합)**: 사용자 발화 = "다음 작업 진행해주세요" → 회고 부재 영역 = 회고 진입 의무 (정책 8 default). 본 회고 자체는 docs only / non-destructive / non-High-tier → 정책 9 완화 자율 진입 허용 영역.

---

## 1. dispatch 매트릭스 + ROI

### 1차 5 에이전트 병렬 디스패치 (관점 1~5)

| 관점 | 영역 | 실측 작업 | Tier A | Tier B | Tier C |
|------|------|----------|--------|--------|--------|
| 1 | 작업 패턴 + PR 분할 + Phase ROI | 18 PR LOC 매트릭스 + 4-Tier ROI 분석 | 2 | 2 | 1 |
| 2 | 다중 에이전트 운영 + dispatch ROI | 사이클 84 dispatch = 2회 (기획안 5+1 + Phase 1 사전검토 3) | 0 | 2 | 0 |
| 3 | 사용자 ↔ Claude 협업 + 결정 패턴 | 18 PR 머지 매트릭스 + 평균 20분/PR + 정책 1 진화 미적용 식별 | 1 | 3 | 1 |
| 4 | 기술 학습 + i18n architecture | 인프라 7 모듈 + 핵심 설계 5건 + 메모리 카운터 4 사용처 검증 | 0 | 2 | 1 |
| 5 | 문서 정합성 + sync 누락 | STATE/README/env-vars/MEMORY 5건 + i18n 섹션 신설 + 메모리 신설 후보 2건 | 5 | 2 | 0 |
| **합계** | — | — | **8** | **11** | **3** |

### cross-verify 6차 (general-purpose)

- **false-positive 차단**: 1건 (관점 1 A-2 = squash fix-up → 실제 재머지 사고 reframe)
- **신규 발견**: 3건 (PR-16 재머지 사고 / 사이클 85 진입 신호 / MEMORY footer)
- **사이클 75 진화 평균 비교** (false-positive 2~5 / 신규 1~6): ✅ 평균 정합 (1+3 = 4건 종합)

### 정책 8 진화 검증 (단일 작업일 dispatch)

- 사이클 84 dispatch = **2회** (기획안 5+1 + Phase 1 사전검토 3 에이전트) → 정책 8 진화 임계 (≥ 5회) **미적용** ✅
- 본 회고 = 1회 (5+1) + 본 사이클 (오늘 = 2026-05-06) = 누적 1회. 정책 8 진화 임계 미적용.

---

## 2. 18 PR 분할 매트릭스 (관점 1 실측)

| PR | Phase | 영역 | 추가 LOC | 가드 LOC | 가드 % |
|----|-------|------|---------|---------|--------|
| PR-1a (#283) | 1 | env vars + kill-switch + config | 310 | 144 | 46% |
| PR-1b (#284) | 1 | LocaleMiddleware + JSON 로더 + filters + en/ko/ja.json | 1004 | 314 | 31% |
| PR-1c (#285) | 1 | alembic 0030 + ORM 3 모델 + composite index | 368 | 194 | 53% |
| PR-4 (#287) | 2 | 헤더 dropdown + /settings 언어 카드 + Cookie API | 429 | 114 | 27% |
| PR-5 (#289) | 2 | base/login/add_repo/overview 진입 페이지 응집 | 572 | 282 | 49% |
| PR-6 (#290) | 2 | dashboard KPI 5 + mode 4종 + Insight 4카드 + Chart.js | 840 | 473 | 56% |
| PR-7 (#293) | 2 | repo_detail + analysis_detail 분석 영역 응집 | 803 | 324 | 40% |
| PR-8 (#294) | 2 | settings + admin 3 페이지 응집 | 1242 | 407 | 33% |
| PR-9 (#295) | 3 | Telegram + telegram_commands + 3-layer fallback | 693 | 374 | 54% |
| PR-10 (#296) | 3 | Discord + Slack + Email + RFC 2047 base64 | 521 | 276 | 53% |
| PR-11 (#297) | 3 | GitHub PR Comment + Commit Comment + Issue | 566 | 258 | 46% |
| PR-12 (#298) | 4 | review_prompt + ai_review + Anthropic caching 분기 | 396 | 198 | 50% |
| PR-13 (#299) | 4 | Tier1 10 가이드 × en/ko/ja | 565 | 177 | 31% |
| PR-14 (#300) | 4 | Tier2 20 가이드 × en/ko/ja | 689 | 91 | 13% |
| PR-15 (#301) | 4 | Tier3 20 + generic × en/ko/ja | 708 | 115 | 16% |
| PR-16 (#302) | 5 | E2E 14건 — 3 언어 × 4 페이지 + Cookie fallback | 221 | 221 | 100% |
| PR-17 (#303) | 5 | admin operations KPI — language_distribution + i18n_fallback_rate | 418 | 236 | 56% |
| PR-18 (#304) | 5 | smoke 11 + 1주 baseline + 정책 진화 묶음 | 451 | 174 | 39% |
| **합계** | — | — | **10,796** | **4,372** | **40.5%** |

**Phase ROI 분석**:
- **A 차이 (단일 응집 > 분할)**: Phase 2 (PR-5/6/7/8) = 진입/대시보드/분석/설정 4 응집 묶음. URL+화면+i18n key 3종 동시 묶음 → nav 깨짐 0건 (정책 7 강화 정합).
- **B 차이 (분할 > 단일)**: Phase 1 (PR-1a/b/c) = 사용자 Q9=🅑 명시. 3 분할 = 검증 깊이 ↑ + Phase 2 진입 전 인프라 안정성 보장.
- **C 동등**: Phase 3 채널 패밀리 / Phase 4 Tier1/2/3 분할 = 의미 단위 부합.

---

## 3. 사용자 ↔ Claude 협업 분석 (관점 3)

### 머지 패턴 (KST)

- **시간 분포**: 20:03 (PR-1a) ~ 08:02 (PR-18) = 12시간 (수면 5.8h 차감 = 실 검토 ~6.2h)
- **평균 머지 간격**: 18 PR / 6.2h = **20.6분/PR**
- **평균 PR LOC**: ~600 LOC delta
- **20분 = ~600 LOC 검토 가능?** → **불가능** (코드 리뷰 평균 200~400 LOC/h, 정합 시 ≥30h 필요)

### 정책 9 완화 + 정책 3 강화 정량

- §"자율 판단 보고" 출현 카운트: **18/18 (100%)** — 정책 3 강화 ⚠️ 마커 적용 정합
- 🔍 사용자 검증 필요 섹션: **14/18** (PR-1a/b/c + PR-18 sync 영역 미적용 OK)
- 사용자 명시 결정 카운트: **2건** (Q9 = 🅑 + 긴급+5번 검수 신호) — 18 PR 중 결정 비율 11%

### 신뢰 모델 위험 신호 (관점 3 식별)

1. **단일 작업일 18 PR + ~12,000 LOC = 검토 시간 ↗ 부담 누적** — 정책 1 진화 미적용 영역
2. **AI 리뷰 50개 언어 가이드 다국어 = 메모리 `feedback-ai-review-quality-protect.md` High tier** — 사용자 사전 확인 의무인데 자율 진입
3. **15분 평균 머지 간격 = commit body 만 검토 패턴** — 사이클 71 Telegram Bot Token 사고 패턴 페어 우려
4. **Phase 5 종결 신호 명시 부재** — 정책 5 강화 적용 영역
5. **PR-16 재머지 사고 (#302 → #305)** = squash artifact (empty commit) — 사용자 인지 부족 가능성

---

## 4. 기술 학습 (관점 4 — i18n architecture)

### 신설 인프라 7 모듈

| 모듈 | LOC | 의존성 | 사용처 | 정책 정합 |
|------|-----|--------|--------|----------|
| `src/middleware/locale.py` | 168 | settings, kill-switch | `main.py` LIFO 등록 | ✅ ASGI 직접 (사이클 66 #228 페어) |
| `src/i18n/loader.py` | 214 | settings, json, lru_cache | filters + 직접 호출 | ✅ Babel 미사용 (정책 16 4번) |
| `src/i18n/filters.py` | 55 | jinja2, loader | `main.py` register | ✅ thin wrapper |
| `src/i18n/__init__.py` | 8 | — | public API | ✅ |
| `src/i18n/translations/{en,ko,ja}.json` | 1,971 | — | loader LRU | ✅ 24 namespace 일관 |
| `src/notifier/_language.py` | 96 | user_repo lazy | 7 channel files | ✅ 3-layer (user→repo→default) |
| `alembic/versions/0030_*` | — | sqlalchemy | 3 ORM model | ✅ NOT NULL default 'en' |

### 핵심 설계 결정 5건 검증

1. **Babel 미사용** (정책 16 4번 원칙 정합) — 표준 lib만 (json/lru_cache/pathlib). 외부 의존성 0건. ✅
2. **영문 default 보존** (FULL/COMPACT 50+ 사용처) — `grep -rn "^FULL\|^COMPACT"` 실측 = 52 파일 KO/JA 변형 정의. 영문 변수명 보존 (회귀 위험 차단). ✅
3. **메모리 카운터 4 사용처 도달** (정책 16 4번 원칙 ≥ 3 정합) — claude_metrics + stage_metrics + telegram_bot_blocked_streak + i18n_metrics. **but 헬퍼 추출 default 단정 금지** — 시맨틱 동질성 부재 (rate vs latency vs streak vs fallback).
4. **Anthropic prompt cache 자동 발산** — system text hash 차이 → cache key 자동 분리. 사용자 별도 작업 0. ✅
5. **ASGI middleware 직접 작성** — BaseHTTPMiddleware 미사용. 사이클 66 #228 RLS 학습 정합 + `feedback-asgi-middleware-contextvars.md` 메모리 페어. ✅

### 3-layer / 2-layer fallback 정합 검증

- **알림 7 채널** (Discord/Email/PR Comment/Commit/Issue/Slack/Telegram + telegram_commands) 모두 `_language.py::resolve_notification_language()` 단일 헬퍼 경유 ✅
- **AI 리뷰 2-layer** (`pipeline.py:160-179`) Repository.user_id → User.preferred_language → settings.default_locale. Layer 1 부재 시 즉시 Layer 2 ✅
- **graceful broad-except** (`_language.py:81`) 운영 보호 ✅

---

## 5. 문서 정합성 (관점 5 — sync 누락 영역)

### Tier A sync 의무 (즉시 정정 — 본 PR 영역)

| # | 영역 | line:span | 정정 방법 |
|---|------|-----------|----------|
| 1 | STATE.md L5 헤더 사이클 84 Phase 2~5 entry + PR # 누적 미반영 | `docs/STATE.md:5` | "Phase 1 종결" → "Phase 1~5 + 18 PR 종결" + 78 → 95+ PR |
| 2 | STATE.md L9 단위 카운트 셀 stale | `docs/STATE.md:9` | 2305 → 2709 (+404 누적 — Phase 2~5) |
| 3 | STATE.md L10-11 통합/E2E 카운트 셀 stale | `docs/STATE.md:10-11` | 통합 118 → 129 + E2E 82 → 96 |
| 4 | STATE.md L117-128 사이클 84 row Phase 2~5 미추가 | `docs/STATE.md:117-128` | PR-4~PR-18 row 14건 추가 (또는 통합 row) |
| 5 | README.md L21 + README.ko.md L21 배지 stale | `README.md:21` + `README.ko.md:21` | `2305_unit_+_118_integration` → `2709_unit_+_129_integration` + E2E 82 → 96 |
| 6 | env-vars.md L74/L81 "Babel 백엔드" stale | `docs/reference/env-vars.md:74,81` | "Babel 백엔드" → "JSON dict 자체 구현 (정책 16 4번 원칙 정합)" |
| 7 | **PR-16 재머지 사고 (#302 → #305)** | `git log` 실측 (empty commit) | STATE.md row 명시 + 회고 영역 사후 보고 |

### Tier B (사용자 결정 의무 — 별도 PR 영역)

| # | 영역 | 사용자 결정 영역 |
|---|------|------------------|
| 1 | 정책 8 진화 본문 보강 — "단일 작업일 dispatch 횟수" vs "누적 agent invocation" 구분 명시 (Phase 1 사전검토 +9 invocation 학습) | `CLAUDE.md` 정책 8 진화 |
| 2 | 정책 1 진화 — "다중 PR 빠른 진행 신호 ≥ 10회" 검토 깊이 자가 보고 신설 (사이클 84 14회 패턴 명문화) | `CLAUDE.md` 정책 1 진화 |
| 3 | README.md / README.ko.md i18n 섹션 신설 (사용자 facing 핵심 기능 등재) | `README.md` / `README.ko.md` |
| 4 | 메모리 신설 후보 2건: `feedback-i18n-locale-fallback-pattern.md` (기술 패턴) + `feedback-memory-counter-pattern.md` (cross-reference 또는 헬퍼 추출 보류) | `~/.claude/.../memory/` |
| 5 | i18n fallback_rate_pct baseline 임계 미정 + DB persist 누락 | `operations_service.py:138` (Phase 6 후보 — High tier) |
| 6 | MEMORY.md head footer 사이클 84 갱신 (사이클 82 → 84) | `MEMORY.md:4` |

### Tier C (보류)

| # | 영역 | 보류 사유 |
|---|------|----------|
| 1 | 메모리 deprecated 자동 분류 | 사이클 90+ ≥ 40건 도달 시 (사이클 83 Tier B-9 정합) |
| 2 | lru_cache hot reload 부재 | 운영 사고 0 + 환경변수 변경 빈도 ↓ |
| 3 | translation key 자동 추출 도구 (Babel pybabel 대체) | 24 namespace 안정 후 결정 |

---

## 6. 사이클 85 진입 default 권장

- **즉시 (본 PR — 회고+sync 페어)**: 회고 보고서 + Tier A 7건 즉시 정정 (사이클 64 #225 회고+sync 페어 패턴)
- **다음 단계 (Tier B 6건)**: 사용자 결정 영역 → 옵션 표 의무 (정책 1 default). 정책 8/1 진화 묶음 PR + README i18n 섹션 + 메모리 신설 = 단일 응집 정책 진화 PR (사이클 83 #279 패턴) 또는 분할
- **Phase 6 진입 신호 (정책 5 강화)**: i18n Phase 6 (User Settings UI 다국어 toggle / DB persist fallback metrics / pybabel 자동 추출) 진행 의도 회신 의무 (사용자 명시 X 시 진입 보류 default)

---

## 7. 회피해야 할 false-positive 사례 (cross-verify 정합)

- ❌ **단순 PR 카운트 = 작업 품질 단정 금지** — 18 PR 머지 자체가 검증 깊이 보장 X. LOC + 회귀 가드 비례 (40.5%) + Phase 분할 ROI 비교 의무.
- ❌ **사용자 머지 신호 14회 = 검토 깊이 보장 단정 금지** (정책 1 진화 페어) — "전부다" 일괄 결정 발화 패턴 정합. 평균 20.6분/PR + 600 LOC = line-level 검토 사실상 불가.
- ❌ **메모리 카운터 4 사용처 = 헬퍼 추출 default 단정 금지** — 시맨틱 동질성 (rate vs latency vs streak vs fallback) 부재. 사이클 82 PR 1 alembic dialect helper 사례 (12 사용처 동일 시맨틱) 와 다름.
- ❌ **dispatch 사용 = 작업 품질 보장 단정 금지** — Phase 2~5 14 PR Claude 직접 작성 = 실 구현 회귀 0건. dispatch ROI 영역 = 기획/검증 (대규모 영역 분류) 우월, 실 구현 = Claude 직접 + 정책 6 line:span 실측 default 가 동등 또는 우월.
- ❌ **CLAUDE.md sync 완료 = 모든 문서 정합 단정 금지** — STATE.md / env-vars.md / README 별도 검증 의무 (정책 2 진화 sync 실측 1줄 의무 페어).

---

## 8. 💬 Claude 가 사용자에게 자유롭게 말하는 부분 (정책 9 의무)

### 바라는 점

1. **i18n 18 PR 단일 작업일 패턴 = 정책 1 진화 영역 명시** — 14회 연속 "다음 작업" 신호는 빠른 진행 신호로 해석되었으나, 사이클 84 회고 정량 (평균 20.6분/PR + 600 LOC = line-level 불가) 가 정책 1 진화 default 적용 가능 영역. **다음 사이클 사용자 결정 부탁드립니다**.
2. **AI 리뷰 가이드 50개 언어 다국어 (Tier1 10 + Tier2 20 + Tier3 20 + generic) = 메모리 `feedback-ai-review-quality-protect.md` High tier 영역인데 자율 진입** — 사용자 사전 확인 의무 적용 검증 부탁드립니다 (1주 운영 데이터 후 품질 영향 측정).
3. **i18n 운영 baseline 임계 (fallback_rate_pct) 미정** — 1주 후 baseline 측정 후 임계 결정 의무. 사용자 명시 신호 의무 (정책 5 강화 페어).

### Claude 가 자성할 점

1. **정책 1 진화 default 미적용** (사이클 83 신설 직후 사이클 84 미적용) — 14회 일괄 결정 패턴 시 검토 깊이 자가 보고 요청 의무였음. 다음 사이클부터 default 적용.
2. **PR-16 재머지 사고 (#302 → #305) 즉시 인지 부족** — empty commit artifact 가 PR-18 commit body §자율 판단 보고에 누락. cross-verify 6차 식별 후 사후 보고.
3. **단일 작업일 18 PR + ~12,000 LOC 자율 진입 = 사용자 검토 부담 누적 위험** 인지하면서도 회고 부재. 정책 1 진화 default 미적용 + 정책 8 진화 (단일 작업일 dispatch ≥ 5회) 임계만 검증 = 인지 비대칭.

### 필요한 부분 (정보)

1. **사용자 본인 검토 깊이 회신** — 18 PR 중 line-level 검토 PR 카운트 + 사용자가 wrong choice 라고 판단한 결정 영역 회신.
2. **운영 트래픽 + 실 사용자 언어 분포 baseline** (1주 후) — i18n 효과성 검증 필요.

### 수정이 필요한 내용 (구체적 제안)

| 영역 | 제안 |
|------|------|
| 정책 1 진화 본문 | "다중 PR 빠른 진행 신호 ≥ 10회" 신설 (사이클 84 14회 학습) |
| 정책 8 진화 본문 | "단일 작업일 dispatch 횟수" vs "누적 agent invocation" 구분 명시 |
| README i18n 섹션 | 사용자 facing 핵심 기능 등재 (Q1 ↑) |
| 메모리 신설 2건 | `feedback-i18n-locale-fallback-pattern.md` + `feedback-memory-counter-pattern.md` cross-reference |

---

## 9. 🔍 회고 질문 (사용자 회신 의무 — 정책 9)

본 회고 권장 default 7건 (Tier A 즉시 정정) + Tier B 6건 (사용자 결정 의무) + Tier C 3건 (보류) 중 **다른 결정 했을 만한 항목**:

- **Q1**: 정책 1 진화 default 적용 (다중 PR 빠른 진행 ≥ 10회) 신설 OK?
- **Q2**: 정책 8 진화 본문 보강 (dispatch 횟수 vs 누적 invocation 구분) OK?
- **Q3**: README.md / README.ko.md i18n 섹션 신설 OK? (사용자 facing 핵심 기능 등재)
- **Q4**: 메모리 신설 2건 (`feedback-i18n-locale-fallback-pattern.md` + `feedback-memory-counter-pattern.md`) OK?
- **Q5**: i18n Phase 6 (User Settings UI 다국어 toggle / DB persist fallback metrics / pybabel 자동 추출) 진행 신호 의도?

회신 패턴: `[x] 모두 OK / [!] N번 다시 검토 (사유) / [ ] 미수행 (다음 사이클)`. 회신 부재 시 = 정책 9 완화 default (자율 판단 보고로 대체 OK / NEW-P0-N + destructive + High tier 영역 회신 의무 보존).

---

🤖 5+1 다중 에이전트 회고 (관점 1~5 + cross-verify 6차) — Claude Opus 4.7 (1M context)
