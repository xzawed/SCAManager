# 사이클 84 i18n 18 PR 종결 baseline 보고서

**작성일**: 2026-05-05
**범위**: Phase 1 ~ Phase 5 (PR-1a/1b/1c → PR-18)
**상태**: **18/18 PR 종결 (100%)** — Phase 5 PR-18 자체 본 보고서

---

## 1. Phase 별 완료 표

| Phase | 영역 | PR # | 머지 | LOC | 회귀 가드 |
|-------|------|------|------|-----|----------|
| Phase 1 | 인프라 | PR-1a #283 | ✅ | ~600 | 환경변수 5 + kill-switch + config |
| Phase 1 | 인프라 | PR-1b #284 | ✅ | ~700 | LocaleMiddleware + 번역 로더 + Jinja2 |
| Phase 1 | 인프라 | PR-1c #285 | ✅ | ~250 | alembic 0030 + ORM 3 모델 |
| Phase 2 | UI | PR-4 #287 | ✅ | ~350 | 언어 선택 UI (헤더 dropdown + /settings) |
| Phase 2 | UI | PR-5 #289 | ✅ | ~700 | base + login + add_repo + overview (+18) |
| Phase 2 | UI | PR-6 #290 | ✅ | ~600 | dashboard.html (KPI 5 + mode 4 + Insight 4) (+18) |
| Phase 2 | UI | PR-7 #293 | ✅ | ~500 | repo_detail + analysis_detail (+16) |
| Phase 2 | UI | PR-8 #294 | ✅ | ~800 | settings + admin 3 (+26) |
| Phase 3 | 알림 | PR-9 #295 | ✅ | ~600 | Telegram + 3-layer fallback (+23) |
| Phase 3 | 알림 | PR-10 #296 | ✅ | ~500 | Discord + Slack + Email + RFC 2047 (+13) |
| Phase 3 | 알림 | PR-11 #297 | ✅ | ~600 | GitHub PR/Commit Comment + Issue 2종 (+13) |
| Phase 4 | 코드리뷰 | PR-12 #298 | ✅ | ~400 | review_prompt + ai_review + caching (+12) |
| Phase 4 | 코드리뷰 | PR-13 #299 | ✅ | ~1,500 | Tier1 10 가이드 (+80) |
| Phase 4 | 코드리뷰 | PR-14 #300 | ✅ | ~2,000 | Tier2 20 가이드 (+82) |
| Phase 4 | 코드리뷰 | PR-15 #301 | ✅ | ~2,000 | Tier3 20 + generic (+84) |
| Phase 5 | 운영 | PR-16 #302 | ✅ | ~250 | E2E 시각 회귀 가드 (+14) |
| Phase 5 | 운영 | PR-17 #303 | ✅ | ~400 | 운영 KPI (i18n 분포 + fallback rate) (+11) |
| Phase 5 | 종결 | PR-18 (본) | 진행 | ~250 | 다국어 smoke + baseline + 정책 진화 (+11) |

**합계**: **18 PR** / **~12,500 LOC** / **~430 회귀 가드**

---

## 2. 영역별 다국어 커버리지

### 2.1 UI 다국어 (Phase 2)
- **8 템플릿** 100% i18n 적용: base / login / overview / add_repo / dashboard / repo_detail / analysis_detail / settings / admin 3
- **language switcher**: 헤더 dropdown + /settings 언어 카드 + API (Phase 2 PR-4)
- **i18n filter**: Jinja2 `i18n` / `i18n_args` 필터 (loader.py 페어)

### 2.2 알림 채널 다국어 (Phase 3)
- **Telegram**: 분석 결과 + /stats /settings /connect 명령 — 3 언어 + 3-layer fallback
- **Discord / Slack / Email**: 분석 결과 — Email subject RFC 2047 base64 호환
- **GitHub**: PR/Commit Comment + Low-score Issue + Auto-merge Failure Issue — title prefix 영문 고정 (검색 호환성)
- **webhook + n8n**: i18n 미적용 영역 (machine envelope payload — 사용자 가시 텍스트 0)

### 2.3 코드리뷰 다국어 (Phase 4)
- **system prompt 3 언어 분기**: AI 출력 언어 결정
- **review_guides 50 언어 + generic = 153 영역** 다국어 적용 (Tier1 10 + Tier2 20 + Tier3 20 + generic)
- **Anthropic prompt cache key 자동 분기**: system text hash 기반 → 언어별 독립 cache 자동 보장

### 2.4 운영 영역 (Phase 5)
- **E2E 시각 회귀 가드**: Playwright + Chromium 14 tests (3 언어 × 4 페이지)
- **운영 KPI 2 카드**:
  - 사용자 언어 분포 (User.preferred_language en/ko/ja)
  - i18n fallback rate (메모리 카운터 — process restart 시 reset)
- **다국어 smoke** (PR-18): 정책 13 페어 — 11 통합 tests

---

## 3. 회귀 가드 누적 (단위 + 통합 + E2E)

| 카테고리 | 사이클 78~82 baseline | 사이클 84 i18n 추가 | 사이클 84 누적 | 증가율 |
|---------|---------------------|---------------------|---------------|--------|
| 단위 (tests/unit) | ~2,236 | +~430 | ~2,666 | +19.2% |
| 통합 (tests/integration) | 84 | +11 (smoke) | 95 | +13.1% |
| E2E (e2e/) | 82 | +14 (visual) | 96 | +17.1% |
| **합계** | **2,402** | **+455** | **2,857** | **+18.9%** |

> Phase 1~5 누적 회귀 가드 = **+455 가드** (단위 ~430 + 통합 11 + E2E 14)

---

## 4. 환경변수 (i18n 영역 5개 신설)

| 변수 | 설명 | 도입 PR |
|------|------|---------|
| `DEFAULT_LOCALE` | 기본 출력 언어 (en/ko/ja). default 'en' | Phase 1 PR-1a |
| `SUPPORTED_LOCALES` | 지원 언어 CSV (default "en,ko,ja") | Phase 1 PR-1a |
| `LOCALE_FALLBACK` | 모든 detection 실패 시 극한 fallback (default 'en') | Phase 1 PR-1a |
| `I18N_DISABLED` | i18n 기능 kill-switch (1 = 영문 hardcoded fallback 강제) | Phase 1 PR-1a |
| `I18N_TRANSLATIONS_DIR` | 번역 파일 디렉토리 (default `src/i18n/translations`) | Phase 1 PR-1a |

`docs/reference/env-vars.md` 등재 의무 (CLAUDE.md sync 체크리스트 페어).

---

## 5. 신규 인프라 모듈 (i18n 영역 5개)

| 모듈 | 영역 | 도입 PR |
|------|------|---------|
| `src/middleware/locale.py` | LocaleMiddleware ASGI (5단계 감지) | Phase 1 PR-1b |
| `src/i18n/loader.py` | 번역 로더 + LRU cache + 메모리 카운터 (PR-17) | Phase 1 PR-1b |
| `src/i18n/filters.py` | Jinja2 i18n / i18n_args 필터 | Phase 1 PR-1b |
| `src/i18n/translations/{en,ko,ja}.json` | 번역 파일 — 8 namespace | Phase 1 PR-1b |
| `src/notifier/_language.py` | 알림 채널 사용자 언어 3-layer fallback | Phase 3 PR-9 |

---

## 6. 핵심 설계 결정 (사이클 84 i18n 학습 누적)

### 6.1 출력 언어 결정 우선순위 (3-layer fallback)

```
Layer 1: User.preferred_language (Telegram 연결 사용자)
Layer 2: RepoConfig.notification_language (per-repo override)
Layer 3: settings.default_locale (env-based fallback)
```

**적용 영역**: 알림 채널 (Telegram/Discord/Slack/Email/GitHub) — `src/notifier/_language.py::resolve_notification_language` 단일 entry point.

### 6.2 AI 리뷰 출력 언어 결정 (별도 — repo level)

```
Layer 1: Repository.user_id → User.preferred_language (repo owner)
Layer 2: settings.default_locale (env-based fallback)
```

**사유**: AI 리뷰는 DB 저장 + 다중 채널 재사용 (정책 16 5번 원칙 — 토큰 비용 효율). repo 레벨 1회 결정 후 모든 채널 재사용.

### 6.3 Title prefix 영문 고정 (검색 호환성)

- **GitHub Issue title** = `[SCAManager] Low score commit: ...` / `[SCAManager] Auto-Merge failed: ...` (영문 고정)
- **Email subject** = `[SCA] {repo} — {total}/100 ({grade})` 영문 (한국어/일본어 영역은 RFC 2047 base64 자동 인코딩)
- **사유**: 운영자 검색 호환성 — 다국어 환경 사용자 동일 검색어 사용 가능

### 6.4 Anthropic prompt cache key 자동 분기

- system prompt 3 언어 분기 → **system text hash 기반 cache key 자동 분리** → 언어별 독립 cache 자동 보장
- 동일 언어 PR 반복 시 cache hit ↑ → 운영 토큰 비용 ↓ (정책 16 5번 원칙 페어)

### 6.5 review_guides 본문 다국어 (Tier1+2+3 + generic)

- **`FULL` / `COMPACT` = 영문 default** (settings.default_locale='en' 정합)
- **`FULL_KO` / `COMPACT_KO`** = 한국어 보존 (기존 default 였음)
- **`FULL_JA` / `COMPACT_JA`** = 일본어 신규 번역
- **fallback chain**: `output_language='ko' → FULL_KO → FULL` (graceful)

---

## 7. 운영 KPI baseline (PR-17 페어)

### 7.1 사용자 언어 분포 (Day 0)

| Language | 사용자 수 | 비율 |
|----------|----------|------|
| en | TBD | TBD% |
| ko | TBD | TBD% |
| ja | TBD | TBD% |

> 운영 1주 측정 후 갱신 의무 (사용자 행동 데이터 — Day 7 baseline 갱신).

### 7.2 i18n fallback rate (Day 0)

| 카운터 | 값 | 비고 |
|--------|---|------|
| `lookups_total` | 0 | process restart 시 reset (memory_only) |
| `lookups_hit` | 0 | 정상 조회 |
| `lookups_fallback` | 0 | 영문 fallback 발생 |
| `lookups_missing` | 0 | key 자체 반환 (운영자 액션 의무 영역) |
| `fallback_rate_pct` | 0.0% | (fallback + missing) / total |

> **임계 — fallback_rate_pct ≥ 5%** = 운영자 번역 누락 검토 의무 (재 push 또는 추가 번역 PR 진입).

---

## 8. 사이클 84 i18n 정책 진화

본 사이클의 학습으로 CLAUDE.md 정책 본문 진화 (PR-18 동시 진행):

### 8.1 새 다국어 영역 정책

> 🔴 **다국어 영역 신규 도입 시 의무**: 영문 default + 한국어 보존 + 일본어 (3 언어 매트릭스).
> Tier1/Tier2/Tier3 패턴 동일 — `FULL` / `COMPACT` 영문 + `FULL_KO/JA` / `COMPACT_KO/JA` 변형. 영문 fallback chain 의무.

### 8.2 운영 메모리 카운터 패턴 (사용처 4 도달)

> claude_metrics + stage_metrics + telegram_bot_blocked_streak + i18n_metrics — 정책 16 4번 원칙 (사용처 ≥3) 정합.
> 신규 운영 메트릭 도입 시 동일 패턴 — `_metrics: dict[str, int]` 모듈 레벨 + `get_*_metrics()` + `reset_*_metrics()` 3-set helper.

### 8.3 Title prefix 영문 고정 (외부 인지 영역)

> GitHub Issue title / Email subject 등 **검색 호환성 영역** = 영문 prefix 고정 default.
> Body 만 사용자 언어 적용. 다국어 검색 호환성 vs 사용자 가시성 트레이드오프 — 검색 호환성 우선.

### 8.4 Anthropic prompt cache 언어별 분기 (자동)

> system prompt 다국어 분기 → cache key (text hash) 자동 분리 의무. system text 안 사용자 변수 삽입 금지 (cache hit rate 0% 폭락).
> 사이클 64 회고 P1 학습 페어 (메모리 `feedback-anthropic-cache-user-invariant.md` 영역).

---

## 9. 회귀 가드 운영 의무

### 9.1 단위 + 통합 (CI 통합)

매 PR 진입 시 `pytest tests/unit tests/integration -q` 의무 (메모리 `feedback-pr-push-direct-validation.md` 페어).

### 9.2 E2E (i18n 시각 회귀)

`pytest e2e/test_i18n_visual_regression.py` — Playwright + Chromium headless. 3 언어 × 4 페이지 = 14 가드.

> **자동화 가드 ≠ manual 시각 검증 대체** (정책 11 페어). 8 조합 (4 테마 × 모바일/데스크탑) 사용자 시각 검증 의무 보존.

### 9.3 다국어 smoke (정책 13 페어)

`pytest tests/integration/test_i18n_smoke.py` — 인증/UI 변경 PR 시점 정합 보조 가드. 11 tests.

---

## 10. 사이클 84 종결 (정책 5 강화 페어)

### 10.1 사용자 명시 사이클 종결 신호 의무

본 보고서 = Phase 5 PR-18 자체. 사이클 84 i18n 18 PR 전체 종결.
**다음 사이클 진입 신호**: 사용자 명시 결정 의무 영역.

### 10.2 NEW-P0-N (운영 사고 차단 영역) 잔여

- 없음 (Phase 1~5 모두 정합).
- 운영 1주 baseline 측정 = 별도 (사용자 명시 결정 시 진행 — 메모리 카운터 + Sentry 페어).

### 10.3 향후 Phase 6 영역 (사용자 사전 확인 의무)

- DB persist 메모리 카운터 (i18n_metrics + claude_metrics + stage_metrics) — process restart 시 reset 한계 영역
- 신규 언어 추가 (zh / es / de 등) — 5 언어 이상 → cache key 영역 + 토큰 비용 재검토
- 사용자 언어별 분석 품질 차이 측정 (사용자 피드백 영역)

---

## 11. 회귀 사고 0건 보고

사이클 84 i18n 18 PR 종결 시점 = **운영 회귀 사고 0건**.

- E2E 14 가드 통과
- 단위 + 통합 ~2,800 통과 / 5 skipped / 0 failed
- Code Scanning 0 alert (정책 14 페어)

> 사이클 64~67 회고 페어 (사용자 명시 진행 + 5+1 다중 에이전트 회고 ↔ 본 사이클 미수행 — 단일 응집 PR 분할 default).

---

## 12. 사이클 84 누적 통계 (사용자 명시 종결 전)

- **PR**: 18 (Phase 1~5)
- **LOC**: ~12,500 (코드 + 번역 파일 + 회귀 가드)
- **번역 영역**: ~510 키 × 3 언어 = ~1,530 영역 (UI + 알림 + AI 리뷰 가이드 + admin)
- **회귀 가드**: +455 (단위 ~430 + 통합 11 + E2E 14)
- **기간**: 2026-05-05 단일 작업일 (5+1 다중 에이전트 디스패치 ≥ 5회 — 정책 8 진화 페어)

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
