"""R review guide — Tier 2."""

FULL = """\
## R 검토 기준
- **벡터화**: for 루프 대신 `apply`/`lapply`/`sapply`/`vapply` 권장, `Vectorize()` 활용
- **타입**: `is.na()` NA 체크, `NULL` vs `NA` vs `NaN` 구분, 암묵적 타입 변환 주의
- **패키지**: `library()` vs `require()` — 스크립트는 `library()`, 패키지 내부는 `requireNamespace()`
- **환경**: 전역 환경 오염 최소화, `<<-` 슈퍼 어사인 주의, `local({})` 스코프 제한
- **재현성**: `set.seed()` 난수 고정, `sessionInfo()` 기록, `renv`/`packrat` 의존성 고정
- **tidyverse**: `%>%`/`|>` 파이프 가독성, `across()` 다중 컬럼, `group_by` + `ungroup()` 쌍
"""

COMPACT = "## R: 벡터화 우선, NA/NULL 구분, library() vs requireNamespace(), <<- 주의, set.seed"
