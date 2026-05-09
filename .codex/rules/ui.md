---
description: UI / 템플릿 작업 시 적용되는 SCAManager 코딩 규칙 (Codex용 — path-scoped)
paths:
  - "src/templates/**"
  - "src/static/**"
  - "src/ui/**"
---

# UI / 템플릿 규칙 (Codex)

- **4-테마 지원**: dark / light / glass / claude-dark. 신규 CSS 변수는 `var(--*)` 경유, `#hex` 직접 사용 금지.
- 🔴 **환각 토큰 금지**: 정의되지 않은 CSS 변수 참조 시 브라우저 invalid → 시각 깨짐. 신규 alias 는 `base.html` `:root` 블록에 흡수.
- 🔴 **모바일 클릭 영역 ≥44px**: `@media (max-width: 768px)` 분기에서 인터랙티브 요소 `min-height: 44px` 필수.
- **safe-area-inset**: sticky/fixed 요소 (`nav`, `.save-bar`) 에 `padding: max(*, env(safe-area-inset-*))` 패턴.
- **Chart.js**: `src/static/vendor/chart.umd.min.js` 로컬 호스팅 (CDN 금지). 테마 전환 시 `buildChart()` 재호출.
- **색 semantic 토큰**: `--success` / `--warning` / `--danger` 3종 사용. hex 직접 사용 금지.
- **analysis_detail context**: `current_user` 반드시 포함 — 누락 시 nav 사용자명 미표시.
- **Telegram HTML**: `parse_mode: "HTML"` 사용 — 동적 콘텐츠에 `html.escape()` 필수.
- **Chart.js CSS 변수**: `getComputedStyle(document.documentElement).getPropertyValue('--grade-a')` 동적 추출 후 Chart 옵션 주입.
