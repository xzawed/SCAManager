# SCAManager UI 전면 재설계 — Claude Design 연동 기획 스펙

**작성일**: 2026-05-25
**작성자**: Claude Code (브레인스토밍 기획안)
**상태**: 구현 완료 — 사이클 131 #625~#633 (design-tokens-v3 + base-html-shell + 페이지 redesign P1~P7) + #638 (docs) 머지

---

## 1. 목표

SCAManager의 UI/UX를 **무결점 프리미엄 서비스 수준**으로 전면 재설계한다.
디자인 작업은 **Claude Design (by Anthropic Labs, Research Preview)** 에서 수행하고,
Claude Code는 준비(Phase 1)와 구현(Phase 3)을 담당한다.

### 핵심 원칙

- **무결점 > 속도**: 빠른 결과보다 완성도 우선 (사용자 명시 모토)
- **디자인 결정은 Claude Design에서만**: Claude Code는 추정·임의 디자인 금지
- **4테마 동시 완성**: dark 먼저 확립 후 나머지 3테마 체계적 확장, 어느 한 테마도 품질 격차 없음

---

## 2. 디자인 방향

### A+B 하이브리드 — Developer Tool × Enterprise Analytics

**Developer Tool (Linear · Raycast · Vercel) 에서 가져올 것:**
- 고밀도 정보 레이아웃 (Linear 수준의 compact density)
- 날카로운 모노스페이스 혼합 타이포그래피 (Pretendard + JetBrains Mono)
- Subtle micro-interaction (hover elevation, 0.12s 이하 트랜지션)
- 어두운 배경 위 정밀한 accent glow 효과

**Enterprise Analytics (Datadog · Grafana Cloud) 에서 가져올 것:**
- 데이터 계층 시각화 (KPI → 트렌드 → 상세 흐름)
- 차트 캔버스 중심 레이아웃 구성
- 등급/점수 배지 시스템의 시각적 무게감
- 상태 변화를 즉시 인지할 수 있는 색상 시스템 (A/B/C/D/F 등급)

### 4테마 역할 정의

| 테마 | 성격 | 주 사용 맥락 |
|------|------|-------------|
| **dark** (기준) | Premium Dark — 가장 완성도 높은 기준 테마 | 야간 작업, 개발자 일상 환경 |
| **light** | Clean Professional — 비즈니스·발표·데모 | 외부 공유, 스크린샷, 고객사 데모 |
| **pastel** | Soft Focus — 눈 피로 최소화 | 장시간 모니터 작업, 취향 사용자 |
| **catppuccin** | Dev Aesthetic — 개발자 서브컬처 감성 | IDE 연계, 커스터마이징 선호 사용자 |

---

## 3. 전체 아키텍처

```
PHASE 1: Claude Code (준비)
  현재 서비스 분석 → Design Brief Package 생성
  docs/design/brief/ 에 패키지 파일 생성
         │
         ▼ 사용자가 Claude Design에 입력
PHASE 2: Claude Design (디자인)
  Design System 프로젝트 생성
  → Color Foundation (Dark Premium 기준)
  → 4테마 확장
  → Typography
  → Component Library
  → 12페이지 Prototype
         │
         ▼ 사용자가 결과물 전달 (스크린샷 + 토큰 명세)
PHASE 3: Claude Code (구현)
  tokens.css / themes.css 전면 교체
  → base.html 공통 컴포넌트
  → 12개 HTML 템플릿 순차 재작성
  → 4테마 × 8조합 검증
```

---

## 4. Phase 1 — Preparation Package 상세

### 파일 구조

```
docs/design/brief/
├── 00-service-overview.md       ← 서비스 정체성 + 사용자 페르소나
├── 01-current-tokens.json       ← tokens.css → 구조화 JSON 추출
├── 02-component-inventory.md    ← 전체 UI 컴포넌트 목록 + 사용처
├── 03-design-direction.md       ← A+B 하이브리드 방향 명세
├── 04-theme-roles.md            ← 4테마별 성격 + 사용 맥락 정의
├── 05-page-inventory.md         ← 12페이지 구조 + 정보 계층
└── screenshots/
    ├── dark/                    ← 12페이지 × dark 테마 (1440px)
    ├── light/                   ← 12페이지 × light 테마
    ├── pastel/                  ← 12페이지 × pastel 테마
    └── catppuccin/              ← 12페이지 × catppuccin 테마
```

추가: Dashboard·Analysis Detail은 모바일(390px) 스크린샷도 캡처.
총 스크린샷: 12×4 = 48장 + 모바일 추가 ~8장.

### 각 파일 역할

| 파일 | Claude Design이 이 파일로 하는 일 |
|------|----------------------------------|
| `00-service-overview.md` | 서비스 성격 파악 → 디자인 톤 결정 |
| `01-current-tokens.json` | 기존 토큰 체계 파악 → 신규 토큰 매핑 |
| `02-component-inventory.md` | Design System 컴포넌트 목록 확정 |
| `03-design-direction.md` | A+B 하이브리드 시각 언어 방향 제시 |
| `04-theme-roles.md` | 4테마 무드·색 팔레트 방향 제시 |
| `05-page-inventory.md` | 12페이지 프로토타입 생성 순서 + 목적 |
| `screenshots/` | 현재 상태 기준점 제공 |

### 스크린샷 캡처 방법

Playwright 스크립트(`scripts/capture_design_screenshots.py`)를 신규 작성하여 자동 캡처.
로컬 개발 서버 실행 중 상태에서 4테마 × 12페이지 순회.
테마 전환: `document.body.setAttribute('data-theme', theme)` 실행 후 캡처.

---

## 5. Phase 2 — Claude Design 작업 가이드

### 프로젝트 설정

```
Claude Design → New project → Design System 타입
프로젝트명: SCAManager Design System
```

### Design System 구축 순서 (레이어 순서 엄수)

| 순서 | 레이어 | 입력 파일 | 결과물 |
|------|--------|----------|--------|
| 1 | Color Foundation | `03-design-direction.md` + `04-theme-roles.md` | Dark Premium 원색 팔레트 |
| 2 | 4테마 확장 | Dark 팔레트 기준 유도 | 4세트 색상 토큰 |
| 3 | Typography | Pretendard + JetBrains Mono 혼합 | 타이포 스케일 |
| 4 | Component Library | `02-component-inventory.md` | 재사용 컴포넌트 세트 |
| 5 | Page Prototypes | `05-page-inventory.md` + 스크린샷 | 12페이지 프로토타입 |

### 컴포넌트 우선순위

```
1순위 (기반): Color token · Typography token · Spacing token
2순위 (원자): Button · Badge · Input · Icon
3순위 (분자): Card · Stat tile · Grade indicator · Score bar
4순위 (유기체): Nav · Data table · Chart frame · Modal
5순위 (페이지): Dashboard → Analysis Detail → Repo Detail → Settings → Landing
              → Overview → Add Repo → Repo Insights → Admin 3종
```

### Claude Design 프롬프트 전략

레이어별로 분리 입력. 한 번에 모든 것을 요청하지 않는다.

**Color Foundation 입력 예시:**
```
이 서비스는 GitHub 코드리뷰 자동화 + 점수/게이트 시스템입니다.
사용자는 개발자이며 하루에 수십 번 이 화면을 봅니다.

Developer Tool(Linear·Raycast)의 예리함과
Enterprise Analytics(Datadog·Grafana)의 데이터 시각화 깊이를
혼합한 독창적 Dark Premium 팔레트를 만들어주세요.

주요 제약:
- 다크 배경에서 코드 등급(A/B/C/D/F)이 즉시 구분되어야 함
- accent는 단일색이 아닌 2~3색 그라디언트 체계
- 정보 밀도가 높아도 시각적 피로감이 없을 것
```

### 4테마 레이어 검증 체크포인트

각 레이어 완성 후 Claude Design 내에서 확인:

| 체크 항목 | 기준 |
|----------|------|
| 등급 색상(A~F) 구분 | 4테마 모두에서 색맹 기준 구분 가능 |
| 텍스트 대비 | WCAG AA 이상 (4.5:1) |
| 카드 vs 페이지 배경 | 4테마 모두에서 구분 가능 |
| accent 색상 가시성 | 어두운/밝은 배경 양쪽에서 유효 |

---

## 6. Phase 3 — Claude Code 구현 설계

### 결과물 수령 및 전달 방법

Claude Design에서 두 가지를 받는다:

| 수령물 | 형태 | Claude Code 전달 방법 | 용도 |
|--------|------|----------------------|------|
| **토큰 명세** | 색상·타이포·spacing 값 목록 | `docs/design/output/tokens-spec.md` 에 값 붙여넣기 | `tokens.css` · `themes.css` 전면 교체 |
| **페이지 프로토타입** | Claude Design 스크린샷 | `docs/design/output/screenshots/` 에 저장 | HTML 템플릿 재작성 기준 |

**전달 절차**: 사용자가 Claude Design에서 Export 또는 스크린샷 캡처 → `docs/design/output/` 에 저장 → Claude Code 세션에서 해당 파일 참조하여 구현 시작.

### 구현 순서 (순서 강제)

```
[1단계] tokens.css 전면 교체
        색상·타이포·elevation·모션 토큰 신규 값 반영
        ↓
[2단계] themes.css 4테마 전면 교체
        dark / light / pastel / catppuccin 각 변수 세트
        ↓
[3단계] base.html 글로벌 컴포넌트 재작성
        nav · 버튼 · 카드 · 배지
        ↓
[4단계] 핵심 페이지 순차 재작성
        Dashboard → Analysis Detail → Repo Detail
        → Settings → Landing → Overview → 나머지 6페이지
        ↓
[5단계] 4테마 × 2뷰포트 8조합 전수 검증 (정책 11)
        ↓
[6단계] 전체 테스트 통과 확인
```

### PR 분할 계획

| PR | 대상 | 특이사항 |
|----|------|---------|
| PR-T1 | tokens.css + themes.css | 모든 페이지에 영향 — 단독 PR |
| PR-T2 | base.html 공통 컴포넌트 | nav·버튼·카드·배지 |
| PR-P1 | Dashboard | 차트·KPI 집약, 가장 복잡 |
| PR-P2 | Analysis Detail | 핵심 데이터 표시 |
| PR-P3 | Repo Detail + Repo Insights | 관련 페이지 묶음 |
| PR-P4 | Settings | 폼·카드 컴포넌트 집약 |
| PR-P5 | Landing | standalone (base.html 비상속) |
| PR-P6 | Overview + Add Repo + Admin 3종 | 나머지 |

### 각 PR 완료 조건

```
□ pylint 10.00/10 유지
□ 전체 테스트 통과 (단위 + 통합 + E2E)
□ 4테마 × 데스크탑/모바일 8조합 시각 확인 (정책 11)
□ WCAG AA 대비 기준 충족 (텍스트 4.5:1 이상)
□ hx-boost 재방문 시 초기화 정상 동작
□ Chart.js 테마 전환 시 색상 재빌드 정상 동작
□ Codex mutual 검증 OK (정책 18)
```

---

## 7. 현재 서비스 현황 (Phase 1 작업 기준점)

| 항목 | 현황 |
|------|------|
| 템플릿 수 | 12개 (landing · base · dashboard · overview · repo_detail · analysis_detail · settings · add_repo · repo_insights · admin 3종) |
| 테마 수 | 4개 (dark · light · pastel · catppuccin) |
| 토큰 파일 | `tokens.css` (테마 무관) + `themes.css` (4테마 정의) |
| 타이포그래피 | Pretendard Variable + Inter + JetBrains Mono |
| 차트 | Chart.js 4.4.0 (로컬 vendoring) |
| 애니메이션 | HTMX hx-boost + IIFE named function 패턴 |
| 기존 제약 | landing.html은 base.html 비상속 (always-dark standalone) |

---

## 8. 미결 사항 (Phase 2 진입 전 Claude Design에서 결정할 것)

- [ ] Dark Premium 신규 accent 색상 팔레트 (현재: `#6366f1` indigo 계열)
- [ ] 4테마 명칭 유지 여부 (dark/light/pastel/catppuccin → 리브랜딩 가능)
- [ ] 타이포그래피 Display 스케일 최종값 (현재: 32/44/60px)
- [ ] Grade 색상 체계 전면 교체 vs 세밀 조정 여부
- [ ] Landing 페이지 디자인 언어 (현재 always-dark → 신규 테마와 정합 방식)
