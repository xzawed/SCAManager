"""CSS/SCSS review guide — Tier 2.

Phase 4 PR-14 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## CSS/SCSS review checklist
- **Performance**: No `@import` (blocking) → `@use` (SCSS); avoid deep selector nesting (≤3 levels)
- **Layout**: Minimize `!important`; turn magic pixel values into CSS variables (`--spacing-md`)
- **Accessibility**: Don't convey info via color alone (contrast ≥4.5:1); never remove `:focus` styles
- **Responsive**: Prefer `rem` / `em` / `%` / `vw` over fixed `px`; `@media` mobile-first (`min-width`)
- **BEM / modules**: Minimize global selector pollution; consistent CSS modules or BEM naming
- **SCSS**: Reuse via `@mixin` / `@function`; separate variable files; warn on `@extend` overuse
- **Animation**: Prefer `transform` / `opacity` (GPU-accelerated); don't overuse `will-change`
"""

COMPACT = "## CSS: minimize !important, CSS vars, rem/em, keep :focus, @import→@use, BEM"

FULL_KO = """\
## CSS/SCSS 검토 기준
- **성능**: `@import` 금지(블로킹) → `@use`(SCSS), 과도한 선택자 중첩(3단계 이하)
- **레이아웃**: `!important` 최소화, 매직 넘버 픽셀값 → CSS 변수(`--spacing-md`)
- **접근성**: `color` 단독 정보 전달 금지(대비율 4.5:1), `:focus` 스타일 제거 금지
- **반응형**: `px` 고정 대신 `rem`/`em`/`%`/`vw`, `@media` 모바일 우선(min-width)
- **BEM/모듈**: 전역 선택자 오염 최소화, CSS 모듈 또는 BEM 네이밍 일관성
- **SCSS**: `@mixin`/`@function` 재사용, 변수 파일 분리, `@extend` 남용 경고
- **애니메이션**: `transform`/`opacity` 선호(GPU 가속), `will-change` 남용 금지
"""

COMPACT_KO = "## CSS: !important 최소화, CSS 변수, rem/em 단위, :focus 삭제 금지, @import→@use, BEM"

FULL_JA = """\
## CSS/SCSS レビュー基準
- **パフォーマンス**: `@import` 禁止 (ブロッキング) → `@use` (SCSS)、セレクタの深いネスト回避 (3 階層以下)
- **レイアウト**: `!important` を最小化、マジックナンバーのピクセル値 → CSS 変数 (`--spacing-md`)
- **アクセシビリティ**: 色のみでの情報伝達禁止 (コントラスト比 4.5:1)、`:focus` スタイル削除禁止
- **レスポンシブ**: `px` 固定の代わりに `rem` / `em` / `%` / `vw`、`@media` はモバイルファースト (min-width)
- **BEM / モジュール**: グローバルセレクタ汚染を最小化、CSS モジュールまたは BEM 命名の一貫性
- **SCSS**: `@mixin` / `@function` の再利用、変数ファイル分離、`@extend` の濫用に警告
- **アニメーション**: `transform` / `opacity` 推奨 (GPU 加速)、`will-change` の濫用禁止
"""

COMPACT_JA = "## CSS: !important 最小化、CSS 変数、rem/em 単位、:focus 維持、@import→@use、BEM"
