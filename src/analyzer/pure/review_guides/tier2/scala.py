"""Scala review guide — Tier 2.

Phase 4 PR-14 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Scala review checklist
- **Immutability**: Prefer `val` (minimize `var`); use immutable collections (`List`, `Map`)
- **Option / Either**: No null returns → `Option[T]`; errors as `Either[Error, T]` or `Try`
- **Pattern matching**: Exhaustive `match` (sealed trait); avoid wildcard `_` overuse
- **Functional**: `map` / `flatMap` / `filter` chains; for-comprehension for readability
- **Future**: Explicit `ExecutionContext`; wrap blocking work with `blocking {}`
- **Types**: Avoid implicit overuse (Scala 3: `given/using`); don't over-trust type inference
- **Akka / Play**: Immutable Actor messages; validate HTTP request params
"""

COMPACT = "## Scala: val/immutable collections, Option/Either, sealed trait exhaustive, minimize implicit"

FULL_KO = """\
## Scala 검토 기준
- **불변성**: `val` 우선(`var` 최소화), 불변 컬렉션(`List`, `Map`) 선호
- **Option/Either**: `null` 반환 금지 → `Option[T]`, 에러는 `Either[Error, T]` or `Try`
- **패턴 매칭**: match 완전성(sealed trait), `_` 와일드카드 남용 주의
- **함수형**: `map`/`flatMap`/`filter` 체인, for-comprehension 가독성
- **Future**: `ExecutionContext` 명시, blocking 작업 `blocking {}` 감싸기
- **타입**: implicit 남용 금지(Scala 3: given/using), 타입 추론 과신 주의
- **Akka/Play**: Actor 메시지 불변성, HTTP 요청 파라미터 검증
"""

COMPACT_KO = "## Scala: val/불변 컬렉션, Option/Either, sealed trait 완전 매칭, implicit 최소화"

FULL_JA = """\
## Scala レビュー基準
- **不変性**: `val` 推奨 (`var` 最小化)、不変コレクション (`List`、`Map`) 推奨
- **Option / Either**: `null` 戻り値禁止 → `Option[T]`、エラーは `Either[Error, T]` または `Try`
- **パターンマッチ**: match の網羅性 (sealed trait)、`_` ワイルドカードの濫用注意
- **関数型**: `map` / `flatMap` / `filter` チェーン、for-comprehension の可読性
- **Future**: `ExecutionContext` 明示、blocking 作業を `blocking {}` でラップ
- **型**: implicit の濫用禁止 (Scala 3: given/using)、型推論への過信注意
- **Akka / Play**: Actor メッセージの不変性、HTTP リクエストパラメータ検証
"""

COMPACT_JA = "## Scala: val/不変コレクション、Option/Either、sealed trait 網羅マッチ、implicit 最小化"
