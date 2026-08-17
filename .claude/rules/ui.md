---
description: UI / 템플릿 작업 시 적용되는 SCAManager 규칙 (path-scoped) — 정책 11 (8 조합 시각 검증) 페어
paths:
  - "src/templates/**"
  - "src/static/**"
  - "src/ui/**"
---

# UI / 템플릿 규칙

> 여기 남은 것은 **결정 시점에 필요한 것만**(규칙 · 왜 한 줄 · 가드 파일명)이다. 서사가 짧아진 것이 규칙이 약해졌다는 뜻이 아니다.

## 세션 라우팅

- **background/시스템 세션 = `WorkerSessionLocal` alias 의무** (본문 = [`db.md`](db.md) §WorkerSessionLocal).
  이 영역 소비자 = `src/ui/routes/admin.py`(hybrid: tenants·operations=worker / rls-audit=bare).
  **hybrid 모듈은 두 심볼을 구분해 쓴다(alias 금지)**. 웹 경로는 bare `SessionLocal` 유지.
  *왜 여기 있나*: `db.md` path 매칭이 이 영역을 포함하지 않아 **자동 로드되지 않는다**.

## hx-boost — 이 영역 최다 재발 클래스

- **인라인 IIFE 금지 → named function + remove-before-add 재등록.**
  *왜*: IIFE 단독은 hx-boost 재방문에서 `opacity:0` 고착.
  핸들러명 = `document._<pageScope><Domain>Handler`. 상세 = 아카이브 §ui.
- 🔴 **차트는 `new Chart(` **앞**에 `if (typeof Chart === 'undefined') return;` early-return 가드.**
  *왜*: body swap 중 vendor `<script>` 가 비동기 재삽입되는 동안 인라인 빌더가 동기 실행돼 throw.
  가드: `tests/unit/ui/test_chart_race_guards.py`
  🔴 `(window.Chart && Chart.getChart)` 는 **destroy 가드일 뿐 race 가드가 아니다**(오분류 전례) —
  이 오분류도 같은 가드가 잡는다(`tests/unit/ui/test_chart_race_guards.py`).
- 🔴 **한 템플릿에 `new Chart(` 가 N개면 가드도 N개** + **vendor 로드 조건이 차트를 렌더하는 모든 분기를 포함**해야 한다.
  *왜*: substring 검사는 1개만 가드해도 통과했고, `repos` 모드가 vendor 미로드로 영구 공백이었다.
  개수·분기 축 집행: `tests/unit/ui/test_chart_race_guards.py` · 실브라우저 축 `e2e/test_repos_mode.py`.
- **여러 `<script>` block 이 공유하는 값은 IIFE `const` 로 선언 금지 → 고유 전역(`window._<scope>`) 노출 + 참조측 지역 `var` 재바인딩 + 미정의 가드.**
  *왜*: 별도 block 의 함수가 IIFE const 를 참조하면 전역만 탐색 → `ReferenceError` → 차트 영구 공백.
  범용 `window.I18N` 금지(타 페이지 전역 충돌). **운영 JS 미표시는 F12 console 우선**(정적 리뷰·5+1 에이전트 미검출 전례).
- 🔴 **외부 `<body>` 스크립트(`effects.js`)의 `init()` 에서 일괄 dispose 금지.**
  *왜*: hx-boost 마다 IIFE 재실행 + 이벤트로 init 이 2~3회 도는데, 2번째 dispose 가 1번째 안전망을
  해제하고 WeakMap 가드 때문에 재등록이 안 돼 count-up 이 "0" 에 영구 고착.
  누수는 `onceInView` sweep 의 `!el.isConnected` 자가정리에 위임.
  가드: `tests/unit/ui/test_hx_boost_listener_guards.py`
- 🔴 **pre-fill 하는 effect 는 DOM 속성 stamp 로 최초 클로저만 소유** (`dataset.cuBound`·`sbBound`·`fbBound`).
  *왜*: 이중 init 이 **서로 다른 클로저 2개**를 만들면 `seen` WeakMap(클로저별)이 못 막고,
  이전 클로저가 pre-fill 한 `"0"` 을 새 클로저가 target 으로 재-parse 해 "0/100" 고착.
  잔여: `setupChartLines`/`setupChartDonuts` 미적용(개요 미노출).
  stamp 소유권 집행: `tests/unit/ui/test_hx_boost_listener_guards.py` · 실브라우저 축 `e2e/test_overview_score.py`.
- **테마 전환도 remove-before-add** — `document.addEventListener('themechange', buildChart)` 직접 등록 금지(stale closure).
  핸들러명은 페이지별 고유(`_repoThemeHandler`·`_dashThemeHandler`·`_riThemeHandler`).

## 폼 / 접근성

- 🔴 **`<form>` 밖 컨트롤은 `form="settingsForm"` 필수 — 없으면 데이터손실.**
  *왜*: form-owner 가 null 이면 제출되지 않아 서버가 기본값(checkbox False)으로 덮어쓴다.
  가드: `tests/unit/ui/test_settings_form_membership.py`
- 🔴 **`<input>`·`<select>`·`<textarea>` 는 접근 가능 이름 의무** — `aria-label="{{ '<i18n-key>' | i18n_args(locale | default('ko')) }}"`.
  *왜*: SonarCloud `Web:InputWithoutLabelCheck` MAJOR 신뢰성 버그 → 누적 시 Quality Gate **ERROR**.
  **placeholder·인접 텍스트는 불충분**. 하드코딩 금지(i18n.md).
  가드: `tests/unit/ui/test_input_aria_labels.py`
- **모바일 인터랙티브 요소 `min-height: 44px`**(WCAG 2.5.5) + `box-sizing: border-box`,
  input/select 모바일 `font-size ≥16px`(iOS focus zoom 회피).
- **sticky/fixed 요소는 `env(safe-area-inset-*)` 적용** + `<meta viewport-fit=cover>` 페어.

## 테마 / 토큰

- **정의되지 않은 토큰 참조 금지** — 발견 시 사용처 치환이 아니라 `base.html` `:root` 에 **alias 흡수**.
  *왜*: consumer 변경 0 으로 4-테마 일괄 해결. 신규 토큰은 항상 `var(--*)`, `#hex` 직접 금지.
- **시맨틱 색은 `--success`/`--warning`/`--danger` 3종만.** 등급 색(`--grade-a~f`)과 혼용 금지.
- **claude-dark 는 settings 토큰 8종 정의 의무** — 미정의 시 invalid `var()` → 카드 헤더 시각 깨짐.
- **scoped 토큰(`.dashboard-page --d-*`)은 4-테마 호환이 부분적이다** — glass 의 `backdrop-filter` 미적용.
  신규 시각 컴포넌트는 **정책 11 8조합 검증 의무**.

## Jinja2 / 템플릿 컨텍스트

- **`| lower | default(...)` 금지 → `{{ (value or 'fallback') | lower }}`.**
  *왜*: `lower` 가 `None` 을 truthy `'none'` 으로 만들어 `default` 가 발동하지 않는다. `| upper` 동일.
- **`analysis_detail` context 에 `current_user` 필수** — 누락 시 nav 사용자명·로그아웃 미표시.
  `analysis.result or {}` 는 falsy 평가로 AI 섹션 전체를 숨기므로 `{% else %}` fallback 의무.
- **Telegram `parse_mode: "HTML"`** — 동적 콘텐츠 전부 `html.escape()`. 4096자 초과 시 자동 절단.
- **`landing.html` 은 `base.html` 미상속(standalone)** — 인증 상태가 바뀌는 엔드포인트는
  `HX-Request` 감지 시 `200 + HX-Redirect: /` 로 전체 재로드. 상세 = 아카이브 §ui.

## 구조 / 배치

- **`settings.html` = 의도 기반 6 카드.** 백엔드 필드명·PRESETS 9필드 불변 원칙,
  **5-way 동기화**(ORM → dataclass → API body → 폼 → PRESETS) 대상. 상세 = 아카이브 §ui.
- **`ai_review_enabled` 는 상위 토글이며 PRESETS 미포함**(의도) — CSS `:has()` 로 하위 종속 완전 숨김,
  `display:none` 이라 값 보존. 4-way 동기화 상세 = [`api.md`](api.md).
  가드: `tests/unit/ui/test_settings_simplification.py`
- **저장 버튼 in-flight = htmx-native**(`hx-indicator`+`hx-disabled-elt`, JS 0).
  가드: `tests/unit/ui/test_settings_save_feedback.py`
- **KPI 카드 신설 시 시각 우선순위 = 사용자 가치 기준 결정 의무**(메인 36px = retry-aware 최종 성공률).
- **신규 정적 자원은 `src/static/vendor/` 하위**(외부 CDN 차단 환경 호환).
  추가·업그레이드 절차 · 500KB 한도 · 인벤토리 표 = [`docs/runbooks/static-assets.md`](../../docs/runbooks/static-assets.md).
- **`user_id = NULL` 리포 재등록은 GitHub 멤버십 검증 후 이전** — 권한 없으면 403(IDOR-인접 차단).
- **overview 등급 = `calculate_grade(avg_score)`**(최신 grade 아님) · `trend_data|length > 1` 일 때만 차트.
- **`leaderboard_opt_in` 폐기**(alembic 0025) · **`/insights*` → 301 `/dashboard`**(쿼리 보존).
