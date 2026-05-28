# SCAManager — 서비스 개요 (Claude Design 브리프용)

## 한 줄 정의

GitHub Push/PR 이벤트 시 정적 분석 + AI 코드리뷰를 자동 수행하고, 점수 기반 PR 게이트(Approve·Reject·Auto-merge)와 멀티채널 알림을 제공하는 개발자 도구 SaaS.

## 핵심 사용자

| 페르소나 | 설명 | 이 서비스를 쓰는 이유 |
|---------|------|-------------------|
| **개발자 (주 사용자)** | 하루 수십 번 PR을 올리는 백엔드/풀스택 개발자 | 내 코드가 몇 점인지, 어떤 문제가 있는지 빠르게 파악 |
| **팀 리드** | 코드 품질 기준을 설정하고 팀 통계를 모니터링 | 팀 전체 점수 추세, 자주 발생하는 문제 패턴 파악 |
| **DevOps** | PR 게이트 임계값·자동 머지 정책을 관리 | 자동화 파이프라인 신뢰성 확보 |

## 핵심 기능 (페이지별)

| 페이지 | 핵심 기능 |
|--------|---------|
| **Dashboard** | 전체 KPI (평균 점수·분석 건수·보안 이슈·Auto-merge 성공률) + 점수 추세 차트 |
| **Analysis Detail** | 개별 PR 분석 결과 — AI 리뷰 + 정적분석 이슈 목록 + 점수 breakdown + GitHub Issue 등록 |
| **Repo Detail** | 리포지토리별 점수 히스토리 차트 + 분석 목록 필터링 |
| **Repo Insights** | 리포지토리 KPI 심층 분석 (이슈 빈도·스파크라인·등급 분포) |
| **Settings** | PR 게이트 임계값 / 알림 채널 / Auto-merge 정책 설정 |
| **Overview** | 등록된 리포지토리 목록 + 각 리포 최신 점수·등급 |
| **Landing** | 미인증 사용자 진입점 — GitHub OAuth 로그인 유도 |

## 점수 시스템

- 0~100점, A(90+) / B(80+) / C(70+) / D(60+) / F(~60) 5등급
- **등급 색상은 즉시 인지 가능해야 함** — 대시보드와 리스트에서 색상만으로 품질 수준 파악

## 데이터 밀도 특성

- 분석 결과 페이지는 이슈 목록 (10~50건)이 한 화면에 공존
- Dashboard KPI는 5개 지표가 동시 표시
- 점수 히스토리 차트는 30건 이상의 데이터 포인트를 처리

## 기술 스택 (Claude Design이 알아야 할 것)

- **프레임워크**: FastAPI + Jinja2 (서버사이드 렌더링)
- **인터랙션**: HTMX hx-boost (SPA-like 네비게이션), vanilla JS
- **차트**: Chart.js 4.4.0 (로컬 vendoring)
- **폰트**: Pretendard Variable (한국어), Inter (영문 fallback), JetBrains Mono (코드)
- **현재 테마**: 4개 — dark (Polar Aurora) / light (Vercel-inspired) / pastel (Dreamy) / catppuccin (Dev)
