# Settings Page UI Redesign — 설계 문서

**날짜:** 2026-04-09  
**상태:** 승인됨

---

## 배경 및 목적

현재 설정 페이지(`src/templates/settings.html`)는 다음 문제가 있다:

1. **가독성 저하** — 카드들이 단순 세로 스택, 섹션 구분이 약함
2. **모바일 임계값 조작 불편** — range 슬라이더 단독 사용, 터치 정밀 조정 불가
3. **테마 무감각** — 카드 내부 색상(버튼, 타이틀 등)이 CSS 변수를 미활용, 테마 전환 시 변화 없음

---

## 최종 디자인 결정

| 항목 | 결정 |
|------|------|
| 임계값 UI | 슬라이더 + 우측 숫자 입력 인라인 (양방향 동기화) |
| 레이아웃 | 데스크탑 2컬럼 grid, 모바일(≤600px) 1컬럼 자동 전환 |
| 카드 스타일 | 그라디언트 컬러 헤더 (섹션별 고유 색상) |
| 테마 대응 | 타이틀·버튼·카드 헤더·저장 버튼·Hook 버튼 모두 CSS 변수화 |

---

## 섹션별 그라디언트 배정

| 카드 | Dark | Light | Glass |
|------|------|-------|-------|
| ⚡ Gate 엔진 | `#6366f1 → #4f46e5` | `#818cf8 → #6366f1` | `rgba(129,140,248,.88) → rgba(99,102,241,.88)` |
| 🔔 알림 채널 | `#f59e0b → #d97706` | `#fcd34d → #f59e0b` | `rgba(251,191,36,.88) → rgba(245,158,11,.88)` |
| 🔀 자동 Merge | `#10b981 → #059669` | `#34d399 → #059669` | `rgba(52,211,153,.88) → rgba(16,185,129,.88)` |
| 🔧 CLI Hook | `#8b5cf6 → #7c3aed` | `#c4b5fd → #8b5cf6` | `rgba(196,181,253,.88) → rgba(139,92,246,.88)` |

## 테마별 변수 체계

### 추가할 CSS 변수 (기존 3개 테마 각각)

```css
/* 공통 추가 변수 */
--title-gradient     /* 페이지 타이틀 그라디언트 텍스트 */
--grad-gate          /* Gate 카드 헤더 */
--grad-merge         /* Merge 카드 헤더 */
--grad-notify        /* 알림 카드 헤더 */
--grad-hook          /* Hook 카드 헤더 */
--btn-active-bg      /* Gate 모드 선택 버튼 배경 */
--btn-active-border  /* Gate 모드 선택 버튼 테두리 */
--btn-active-text    /* Gate 모드 선택 버튼 텍스트 */
--save-bg            /* 저장 버튼 그라디언트 */
--save-shadow        /* 저장 버튼 그림자 색 */
--hint-bg            /* 임계값 범위 힌트 배경 */
--hint-border        /* 임계값 범위 힌트 테두리 */
--hook-btn-bg        /* Hook 버튼 배경 */
--hook-btn-border    /* Hook 버튼 테두리 */
--hook-btn-text      /* Hook 버튼 텍스트 */
--hook-btn-hover-bg
--hook-btn-hover-border
```

---

## HTML 구조 변경

### 현재 → 변경 후

```
[현재] 단일 컬럼 세로 스택
  ├ Gate 엔진 카드
  ├ 자동 Merge 카드
  ├ 알림 설정 카드
  └ CLI Hook 카드

[변경 후] 2컬럼 grid
  ┌─────────────────┬─────────────────┐
  │  ⚡ Gate 엔진   │  🔔 알림 채널   │
  │  (임계값 포함)  │  (5개 입력폼)   │
  ├─────────────────┼─────────────────┤
  │  🔀 자동 Merge  │  🔧 CLI Hook    │
  └─────────────────┴─────────────────┘
  [💾 설정 저장 — sticky bottom]
```

### 임계값 컨트롤 구조

```html
<div class="threshold-ctrl">
  <input type="range" name="auto_approve_threshold" min="0" max="100"
         oninput="document.getElementById('approveVal').value=this.value">
  <input type="number" id="approveVal" class="num-input" min="0" max="100"
         oninput="this.previousElementSibling.value=this.value">
</div>
```

### 페이지 타이틀 그라디언트 텍스트

```html
<h1 class="page-title">리포지토리 설정</h1>
```
```css
.page-title {
  background: var(--title-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
```

---

## 수정 파일

- **`src/templates/settings.html`** — 전면 재작성 (CSS 변수 + HTML 구조)
- **`src/templates/base.html`** — 3개 테마 각각에 새 CSS 변수 추가

---

## 테스트

- `make test` — 기존 276개 단위 테스트 통과 확인 (HTML 변경이므로 pytest는 구조 변경 감지 안 함)
- 브라우저에서 3가지 테마 전환 확인
- 모바일 뷰(Chrome DevTools 375px) 에서 1컬럼 레이아웃 + 숫자 입력 확인
- 슬라이더 ↔ 숫자 입력 양방향 동기화 확인
- 폼 제출 후 값이 DB에 정상 저장되는지 확인 (기존 `name` 속성 유지 필수)
