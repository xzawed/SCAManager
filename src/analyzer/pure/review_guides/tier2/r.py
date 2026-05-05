"""R review guide — Tier 2.

Phase 4 PR-14 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## R review checklist
- **Vectorization**: Prefer `apply` / `lapply` / `sapply` / `vapply` over for loops; use `Vectorize()`
- **Types**: `is.na()` for NA; distinguish `NULL` vs `NA` vs `NaN`; watch implicit conversions
- **Packages**: `library()` vs `require()` — scripts use `library()`, packages internal use `requireNamespace()`
- **Environment**: Minimize global env pollution; cautious `<<-` superassign; `local({})` to limit scope
- **Reproducibility**: `set.seed()` for RNG; record `sessionInfo()`; pin deps with `renv` / `packrat`
- **tidyverse**: `%>%` / `|>` pipe readability; `across()` for multi-column; pair `group_by` with `ungroup()`
"""

COMPACT = "## R: vectorize first, NA/NULL distinct, library() vs requireNamespace, watch <<-, set.seed"

FULL_KO = """\
## R 검토 기준
- **벡터화**: for 루프 대신 `apply`/`lapply`/`sapply`/`vapply` 권장, `Vectorize()` 활용
- **타입**: `is.na()` NA 체크, `NULL` vs `NA` vs `NaN` 구분, 암묵적 타입 변환 주의
- **패키지**: `library()` vs `require()` — 스크립트는 `library()`, 패키지 내부는 `requireNamespace()`
- **환경**: 전역 환경 오염 최소화, `<<-` 슈퍼 어사인 주의, `local({})` 스코프 제한
- **재현성**: `set.seed()` 난수 고정, `sessionInfo()` 기록, `renv`/`packrat` 의존성 고정
- **tidyverse**: `%>%`/`|>` 파이프 가독성, `across()` 다중 컬럼, `group_by` + `ungroup()` 쌍
"""

COMPACT_KO = "## R: 벡터화 우선, NA/NULL 구분, library() vs requireNamespace(), <<- 주의, set.seed"

FULL_JA = """\
## R レビュー基準
- **ベクトル化**: for ループより `apply` / `lapply` / `sapply` / `vapply` 推奨、`Vectorize()` 活用
- **型**: `is.na()` で NA チェック、`NULL` vs `NA` vs `NaN` の区別、暗黙的型変換に注意
- **パッケージ**: `library()` vs `require()` — スクリプトは `library()`、パッケージ内部は `requireNamespace()`
- **環境**: グローバル環境の汚染を最小化、`<<-` スーパーアサインに注意、`local({})` でスコープ制限
- **再現性**: `set.seed()` で乱数固定、`sessionInfo()` を記録、`renv` / `packrat` で依存固定
- **tidyverse**: `%>%` / `|>` パイプの可読性、`across()` 複数列、`group_by` + `ungroup()` ペア
"""

COMPACT_JA = "## R: ベクトル化優先、NA/NULL 区別、library() vs requireNamespace()、<<- 注意、set.seed"
