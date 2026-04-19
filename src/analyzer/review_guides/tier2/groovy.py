"""Groovy/Gradle review guide — Tier 2."""

FULL = """\
## Groovy 검토 기준
- **타입**: `def` 과용 금지 — 가능한 명시적 타입 선언, `@TypeChecked`/`@CompileStatic`
- **null 안전**: `?.` 안전 탐색, `?:` Elvis 연산자, GString 내 null 삽입 주의
- **Gradle**: `implementation` vs `api` 의존성 범위, `buildscript` vs `plugins` 블록
- **클로저**: 델리게이트 명확성(`delegate`, `owner`, `this`), 클로저 내 `return` 동작
- **보안**: GString 내 셸 명령 주입, `evaluate()`/`Eval.me()` 금지
- **테스트**: Spock `given/when/then` 구조, `@Unroll` 파라미터화, Mock/Stub/Spy 구분
"""

COMPACT = "## Groovy: @CompileStatic, ?. Elvis, Gradle implementation vs api, evaluate() 금지, Spock"
