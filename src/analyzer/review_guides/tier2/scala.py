"""Scala review guide — Tier 2."""

FULL = """\
## Scala 검토 기준
- **불변성**: `val` 우선(`var` 최소화), 불변 컬렉션(`List`, `Map`) 선호
- **Option/Either**: `null` 반환 금지 → `Option[T]`, 에러는 `Either[Error, T]` or `Try`
- **패턴 매칭**: match 완전성(sealed trait), `_` 와일드카드 남용 주의
- **함수형**: `map`/`flatMap`/`filter` 체인, for-comprehension 가독성
- **Future**: `ExecutionContext` 명시, blocking 작업 `blocking {}` 감싸기
- **타입**: implicit 남용 금지(Scala 3: given/using), 타입 추론 과신 주의
- **Akka/Play**: Actor 메시지 불변성, HTTP 요청 파라미터 검증
"""

COMPACT = "## Scala: val/불변 컬렉션, Option/Either, sealed trait 완전 매칭, implicit 최소화"
