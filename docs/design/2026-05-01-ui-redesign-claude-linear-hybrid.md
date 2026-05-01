# UI/UX 개편 설계서 — Claude × Linear 하이브리드 (2026-05-01)

## 개요

5-에이전트 종합 검증 (정찰 1 + 컨셉 4 — Linear/Datadog/Mobile/Claude) 후 사용자 승인된 **권장안 1: A + D 하이브리드** 의 세부 기획서.

**핵심 가치**: "한 화면 한 결정 (Linear) + AI 동료의 작업 노트 (Claude) — 친근하고 간단하지만 정보가 명확한 워크스페이스"

**현재 가장 빈약한 영역 3가지** (정찰 결과 → 본 개편의 우선 해결 대상):
1. Settings 6 카드 인지부담 (첫 진입 시 마비)
2. 모바일 정보 밀도 과다 (768px 이하 복잡)
3. 로딩/빈 상태 피드백 부재 (회색 빈 영역)

---

## 디자인 토큰 — Claude × Linear 하이브리드

### 색상 팔레트

| 토큰 | Light | Dark | 용도 |
|------|-------|------|------|
| `--bg-base` | `#F5F1E8` warm cream | `#1F1E1B` warm black | 페이지 배경 |
| `--bg-surface` | `#FAF7F0` | `#2A2825` | 카드/섹션 |
| `--bg-elevated` | `#FFFFFF` | `#33302C` | 모달/팝오버 |
| `--text-primary` | `#1F1E1B` | `#F5F1E8` | 본문 |
| `--text-muted` | `#6B6862` | `#A8A29A` | 메타 정보 |
| `--accent-primary` | `#D97757` Anthropic-inspired orange | `#E08968` | CTA, 링크 |
| `--accent-soft` | `#E8C5A8` | `#5C3D2E` | hover/active 배경 |
| `--border` | `#E5E1D5` | `#3D3A35` | 1px hairline |
| `--success` | `#9CAF88` sage | `#A8BA94` | A등급/성공 |
| `--warning` | `#D4A574` sand | `#DDB585` | C등급/주의 |
| `--danger` | `#C84E3F` muted red | `#D45F50` | F등급/실패 |
| 등급 | A `#9CAF88` · B `#A8A595` · C `#D4A574` · D `#C8895E` · F `#C84E3F` |

**원칙**: 채도 -20% (도서관/회의실 분위기), 등급 색상은 점·배지에만 (배경 채우기 금지)

### 타이포그래피

- **Heading**: `'Crimson Pro', Charter, Georgia, serif` (따뜻한 serif)
- **Body**: `'Inter', system-ui, -apple-system, sans-serif`
- **Code**: `'JetBrains Mono', Menlo, Consolas, monospace`
- **스케일**: H1 32px / H2 24px / H3 18px / Body 16px / Caption 13px (line-height 1.65)

### 레이아웃

- Container `max-width: 1040px`, padding 24px
- 8px base spacing (4·8·12·16·24·32·48·64)
- Breakpoints: 640 / 768 / 1024 / 1280

---

## 마이크로카피 가이드 (Claude 톤)

| 위치 | 현재 | 개편 |
|------|------|------|
| 점수 표시 | `Score: 84/100 (B)` | `84점 — 견고한 PR이에요` |
| 빈 상태 (분석) | `No analyses yet` | `아직 분석된 PR이 없어요. 첫 push를 기다리고 있어요.` |
| 빈 상태 (리포) | `No repositories` | `등록된 리포가 없어요. 첫 리포를 추가해 보세요.` |
| 에러 (5xx) | `Error 500: Internal Server Error` | `잠시 문제가 생겼어요. 다시 시도해 주세요.` |
| 로딩 (분석 중) | `Loading...` | `Claude가 코드를 읽고 있어요…` |
| Auto-merge 성공 | `PR #42 merged` | `PR #42 — 검토를 마치고 자동으로 합쳤어요` |
| Auto-merge 실패 | `Merge failed: branch_protection_blocked` | `Branch protection 때문에 합칠 수 없었어요. 관리자에게 요청해 보세요.` |
| 환영 인사 | (없음) | `안녕하세요, {user}님 👋` |

**톤 원칙**:
- 대화체 + 친절 + 정확
- "~어요" / "~이에요" 종결어미 일관
- 통계 → 의미 ("84/100" → "견고한")
- 에러 상황 → 다음 액션 제시

---

## Settings 6 → 3 카드 그룹핑

| 신 카드 | 통합 대상 (현재) | 핵심 질문 |
|----|----|----|
| **① Reviews** | ② PR 들어왔을 때 (pr_review_comment + approve_mode + thresholds + auto_merge + merge_threshold) | "PR이 들어오면 어떻게 할까요?" |
| **② Notifications** | ③ 이벤트 후 피드백 + ④ 알림 채널 (commit_comment + create_issue + railway_alerts + 6 채널 URL) | "어디로 알려드릴까요?" |
| **③ System** | ⑤ 시스템 & 토큰 + ⑥ 위험 구역 (CLI hook + Webhook 재등록 + Railway 토큰 + 리포 삭제) | "고급 설정과 시스템 정보" |

**구현 원칙**:
- 백엔드 필드명 14종 + PRESETS 9 필드 **불변** (5-way sync 보존)
- HTML/CSS/JS 만 재구성
- 신규 사용자 온보딩 시 wizard (4-step: Connect → Reviews → Notify → Done)
- 기존 사용자는 3 카드 진입 시 모두 닫힘 → 펼쳐서 변경

---

## 단계별 PR 로드맵 (5 PR)

### Phase 1 — 기반 (3 PR, 점진 적용)

| PR | 범위 | 위험 | 파일 변경 |
|----|----|----|----|
| **Phase 1A (현재 PR)** | 디자인 토큰 추가 (`--claude-*` 네임스페이스, 기존 토큰 보존) + 폰트 로딩 + 본 기획서 | 매우 낮음 | base.html CSS 변수 증설, fonts.css 신규 |
| **Phase 1B** | 다크 모드 강화 (warm black) + 마이크로카피 5건 (overview, 빈 상태, 로딩) | 낮음 | overview.html, 공통 partial |
| **Phase 1C** | 등급 색상 적용 (sage/sand/muted red) — 기존 #4ade80 등 호환 alias 유지 | 중간 | base.html 등급 색 + 차트 색상 갱신 |

### Phase 2 — 핵심 화면 재설계 (2 PR)

| PR | 범위 |
|----|----|
| **Phase 2A** | Settings 6 → 3 카드 통합 (HTML 재구성 + 5-way sync 동작 보존 회귀 가드) |
| **Phase 2B** | Cmd+K 명령 팔레트 (5 진입점) + 키보드 단축키 |

### Phase 3 — 선택 (사용자 결정)
- TV mode (`/tv` 풀스크린) — 회의실 디스플레이 필요 시
- PWA (manifest + service worker) — 모바일 푸시 필요 시

---

## 마이그레이션 안전성

**원칙**: 기존 페이지 동작 절대 깨지 않음. 모든 변경은 **점진 추가 (Additive)**.

- Phase 1A: 신규 토큰 추가만, 기존 토큰 미변경 → 0 회귀
- Phase 1B: 다크 모드 + 마이크로카피 — 기능 변경 없음
- Phase 1C: 등급 색상 — 기존 hex (#4ade80 등) 별칭 유지
- Phase 2A: settings.html HTML 재구성 — 백엔드 필드 불변, e2e/test_settings.py 회귀 가드
- Phase 2B: Cmd+K — 신규 추가만 (기존 네비 미변경)

---

## 검증 방법

| 항목 | 도구 |
|----|----|
| HTML 회귀 | `tests/unit/ui/` + `e2e/test_settings.py` |
| 시각 회귀 | Playwright 스크린샷 (선택) |
| 색상 대비 (WCAG AA) | 브라우저 DevTools + `aXe` 확장 |
| 폰트 로딩 (FCP) | Lighthouse |
| 5-way sync | `tests/unit/ui/test_settings_*.py` |
| Settings preset | E2E `e2e/test_settings.py` 9 PRESETS 회귀 |

---

## 잔여 결정 사항 (작업 진행 중 정하기)

1. **Crimson Pro 로딩 전략** — Google Fonts (CDN, 외부 의존) vs self-host (성능)
2. **다크 모드 토글 위치** — 상단 navbar vs Profile 메뉴
3. **마이크로카피 한국어/영어 분리** — 모든 사용자 한국어 OK? 또는 i18n 도입?
4. **등급 색상 별칭 기간** — 호환 alias 를 언제까지 유지? (Phase 2 까지 권장)
5. **Cmd+K 단축키 표시 방식** — 상단 검색 바 / FAB / 푸터?

---

## 다음 단계

본 PR (Phase 1A) 머지 후 → Phase 1B (다크 모드 + 마이크로카피) → Phase 1C → Phase 2A → Phase 2B 순차 진행. 각 PR 마다 회귀 가드 + pylint + e2e 검증.
