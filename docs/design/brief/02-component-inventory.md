# SCAManager — UI 컴포넌트 인벤토리 (Claude Design 브리프용)

Claude Design의 Component Library 구성 시 아래 컴포넌트를 모두 포함해야 한다.

## 1순위: 기반 토큰

| 토큰 그룹 | 항목 수 | 비고 |
|---------|--------|------|
| Color (per theme) | ~25개 | bg-base, bg-card, bg-elevated, bg-nav, text-1/2/3, accent, border-subtle/strong, success/warning/danger, grade-a~f |
| Typography scale | 12개 | fs-xs(12) ~ fs-3xl(24) + display-sm(32)/md(44)/lg(60) |
| Spacing scale | 8개 | space-1(4px) ~ space-8(48px) |
| Radius scale | 5개 | xs(4) / sm(6) / md(10) / lg(14) / pill(999) |
| Elevation | 5단계 | elev-0 ~ elev-4 + elev-inset |
| Motion | 6개 | dur-fast(120ms)/base(220ms)/slow(360ms) + ease-out-expo/ease-out/ease-spring |

## 2순위: 원자 컴포넌트

| 컴포넌트 | 변형 | 사용 페이지 |
|---------|------|-----------|
| **Button** | primary / secondary / ghost / danger · size: sm/md/lg | 전체 |
| **Badge / Grade Pill** | A/B/C/D/F 등급 색상 + 점수 숫자 | overview, analysis_detail, repo_detail |
| **Score Bar** | 0~100 progress bar (등급 색 연동) | analysis_detail, repo_detail |
| **Toggle Switch** | on/off 슬라이더 | settings |
| **Input** | text / password / masked (••••) · focus 상태 | settings, add_repo |
| **Icon** | GitHub·Telegram·Discord·Slack·Email + 시스템 아이콘 | settings, nav |
| **Spinner / Loader** | 인라인 로딩 표시 | 전체 |

## 3순위: 분자 컴포넌트

| 컴포넌트 | 설명 | 사용 페이지 |
|---------|------|-----------|
| **KPI Card** | 지표명 + 큰 숫자 + delta(↑↓%) + 서브텍스트 | dashboard |
| **Repo Card** | 리포명 + 최신 등급 배지 + 점수 + 분석 날짜 | overview |
| **Issue Row** | 심각도 아이콘 + 메시지 + 파일:라인 + 카테고리 배지 | analysis_detail |
| **Stat Tile** | 라벨 + 값 + 아이콘 (소형 KPI) | repo_insights |
| **Sparkline Tile** | 미니 라인 차트 + 추세 수치 | repo_insights |
| **Alert Banner** | info / warning / danger 인라인 배너 | 전체 |
| **Empty State** | 아이콘 + 메시지 + CTA 버튼 | overview, dashboard |

## 4순위: 유기체 컴포넌트

| 컴포넌트 | 설명 | 사용 페이지 |
|---------|------|-----------|
| **Nav** | 로고 + 페이지 링크 + 테마 토글 + 사용자 메뉴 / 모바일 햄버거 | base.html (전체) |
| **Data Table** | 헤더 + 정렬 + 행 hover + 페이지네이션 | repo_detail, overview |
| **Chart Frame** | Chart.js 래퍼 — 라인/바/도넛 + 테마 색 동기화 | dashboard, repo_detail, analysis_detail |
| **Modal** | 오버레이 + 헤더 + 내용 + 액션 버튼 | analysis_detail (Issue 등록), repo_detail (삭제 확인) |
| **Settings Card** | 제목 + 설명 + 폼 그룹 + 저장 버튼 | settings |
| **Toast Notification** | 성공/에러 팝업 (우하단, 3초 자동 사라짐) | settings, add_repo |
| **Page Progress Bar** | 페이지 상단 로딩 인디케이터 (hx-boost 연동) | base.html (전체) |

## 특수 케이스

| 항목 | 설명 |
|------|------|
| **Landing Mesh BG** | CSS 애니메이션 그라디언트 배경 — landing.html 전용, always-dark |
| **Grade Color System** | A=green / B=blue / C=yellow / D=orange / F=red — 4테마 모두에서 WCAG AA 기준 충족 의무 |
| **JetBrains Mono 사용처** | 파일 경로, 커밋 SHA, 점수 숫자 (큰 KPI 숫자) — 코드·데이터 영역에 한정 |
