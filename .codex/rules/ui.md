---
description: UI / 템플릿 작업 시 적용되는 SCAManager 코딩 규칙 (Codex용 — path-scoped)
paths:
  - "src/templates/**"
  - "src/static/**"
  - "src/ui/**"
---

# UI / 템플릿 규칙 (Codex)

- **4-테마 지원**: dark / light / pastel / catppuccin. 신규 CSS 변수는 `var(--*)` 경유, `#hex` 직접 사용 금지.
- 🔴 **환각 토큰 금지**: 정의되지 않은 CSS 변수 참조 시 브라우저 invalid → 시각 깨짐. 신규 alias 는 `base.html` `:root` 블록에 흡수.
- 🔴 **모바일 클릭 영역 ≥44px**: `@media (max-width: 768px)` 분기에서 인터랙티브 요소 `min-height: 44px` 필수.
- **safe-area-inset**: sticky/fixed 요소 (`nav`, `.save-bar`) 에 `padding: max(*, env(safe-area-inset-*))` 패턴.
- **Chart.js**: `src/static/vendor/chart.umd.min.js` 로컬 호스팅 (CDN 금지). 테마 전환 시 `buildChart()` 재호출.
- **색 semantic 토큰**: `--success` / `--warning` / `--danger` 3종 사용. hex 직접 사용 금지.
- **analysis_detail context**: `current_user` 반드시 포함 — 누락 시 nav 사용자명 미표시.
- **Telegram HTML**: `parse_mode: "HTML"` 사용 — 동적 콘텐츠에 `html.escape()` 필수.
- **Chart.js CSS 변수**: `getComputedStyle(document.documentElement).getPropertyValue('--grade-a')` 동적 추출 후 Chart 옵션 주입.
- 🔴 **leaderboard_opt_in 컬럼 폐기 (부활 금지)**: 팀 리더보드 기능 완전 폐기 (alembic 0025). 향후 SaaS 전환 시 멀티 사용자 인사이트 모델 별도 신설 결정 — 기존 single-user opt-in 모델 부활 X.
- **/dashboard KPI 구조**: KPI 5 카드 (평균 점수 / 분석 건수 / 보안 HIGH / 활성 리포 / Auto-merge 성공률) + 점수 추세 라인 차트. KPI 그리드 반응형 4 단계 (desktop 5 / tablet 3 / mobile 2 / xs 1). 신규 KPI 카드 추가 시 `.dash-kpi min-height: 152px` 동일 높이 유지.
- 🔴 **Auto-merge KPI 시각 우선순위**: KPI 메인 (36px) = `final_success_rate_pct` (retry-aware). sub-text = 단순 시도 + delta. fallback: `final_success_rate_pct is none` 시 `value` 메인 표시.
