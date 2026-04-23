"""CSS/SCSS review guide — Tier 2."""

FULL = """\
## CSS/SCSS 검토 기준
- **성능**: `@import` 금지(블로킹) → `@use`(SCSS), 과도한 선택자 중첩(3단계 이하)
- **레이아웃**: `!important` 최소화, 매직 넘버 픽셀값 → CSS 변수(`--spacing-md`)
- **접근성**: `color` 단독 정보 전달 금지(대비율 4.5:1), `:focus` 스타일 제거 금지
- **반응형**: `px` 고정 대신 `rem`/`em`/`%`/`vw`, `@media` 모바일 우선(min-width)
- **BEM/모듈**: 전역 선택자 오염 최소화, CSS 모듈 또는 BEM 네이밍 일관성
- **SCSS**: `@mixin`/`@function` 재사용, 변수 파일 분리, `@extend` 남용 경고
- **애니메이션**: `transform`/`opacity` 선호(GPU 가속), `will-change` 남용 금지
"""

COMPACT = "## CSS: !important 최소화, CSS 변수, rem/em 단위, :focus 삭제 금지, @import→@use, BEM"
