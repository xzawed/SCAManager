# SCAManager — 페이지 인벤토리 (Claude Design 브리프용)

Claude Design에서 12페이지 프로토타입을 생성할 때 아래 순서와 구조를 따른다.

## 프로토타입 생성 순서

```
1순위: landing     — 서비스 첫인상, 브랜드 집약
2순위: dashboard   — 가장 복잡한 KPI+차트 레이아웃
3순위: analysis_detail — 핵심 데이터 표시 페이지
4순위: overview    — 리포 목록 그리드
5순위: repo_detail — 차트+테이블 복합
6순위: settings    — 폼 카드 레이아웃
7순위: repo_insights — 스파크라인+KPI 집약
8순위: add_repo    — 단순 폼
9~12순위: admin 3종 — 어드민 전용
```

---

## 페이지별 상세

### 1. landing (`/`)
- **목적**: 미인증 사용자 → GitHub OAuth 로그인 유도
- **특수사항**: `base.html` 미상속 standalone — always-dark 고정
- **핵심 요소**: 애니메이션 메시 그라디언트 배경, 히어로 CTA 버튼 1개, 서비스 기능 소개
- **주의**: 이 페이지만 단일 다크 테마 — 4테마 적용 불필요

### 2. dashboard (`/dashboard`)
- **목적**: 전체 리포지토리 종합 현황 한눈에 파악
- **핵심 요소**:
  - KPI 카드 5개 (평균점수·분석건수·보안HIGH·활성리포·AutoMerge성공률)
  - 점수 추세 라인 차트 (전체 리포 시계열)
  - 자주 발생 이슈 테이블
  - Auto-merge 실패 사유 목록
- **레이아웃**: 데스크탑 5컬럼 KPI 그리드, 태블릿 3컬럼, 모바일 1컬럼

### 3. analysis_detail (`/repos/{id}/analysis/{id}`)
- **목적**: 개별 PR 분석 결과 상세 보기
- **핵심 요소**:
  - 점수 + 등급 배지 (큰 폰트, 페이지 상단)
  - 점수 breakdown 바 차트 (카테고리별)
  - AI 리뷰 텍스트 (마크다운)
  - 정적분석 이슈 목록 (심각도별 정렬)
  - GitHub Issue 등록 패널 (AI/정적 탭)
  - 이전/다음 분석 네비게이션

### 4. overview (`/overview`)
- **목적**: 사용자가 등록한 리포지토리 목록
- **핵심 요소**: 리포 카드 그리드 (이름·등급·최신점수·분석날짜), 리포 추가 CTA

### 5. repo_detail (`/repos/{id}`)
- **목적**: 특정 리포지토리의 분석 히스토리
- **핵심 요소**:
  - 점수 추세 라인 차트 (해당 리포 시계열)
  - 분석 목록 테이블 (필터·정렬 포함)
  - 일괄 Issue 등록 패널

### 6. settings (`/settings`)
- **목적**: PR 게이트·알림채널·Auto-merge 정책 설정
- **핵심 요소**: 의도 기반 6카드 (빠른설정 / PR게이트 / 이벤트피드백 / 알림채널 / 시스템 / 위험구역)
- **레이아웃**: 카드 스택 단일 컬럼, 저장 바 하단 sticky

### 7. repo_insights (`/repos/{id}/insights`)
- **목적**: 리포지토리 심층 KPI 분석
- **핵심 요소**: Stat tile + Sparkline tile 그리드, 이슈 빈도 분포

### 8. add_repo (`/repos/add`)
- **목적**: 새 리포지토리 등록
- **핵심 요소**: 리포 선택 드롭다운, Webhook URL 표시, 등록 버튼

### 9~11. admin (3종)
- **목적**: 어드민 전용 운영 화면
- **페이지**: `/admin/operations` · `/admin/rls-audit` · `/admin/tenants`
- **특이사항**: 일반 사용자 접근 불가, 테이블 중심 레이아웃
