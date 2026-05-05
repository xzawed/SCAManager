"""Groovy/Gradle review guide — Tier 2.

Phase 4 PR-14 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Groovy review checklist
- **Types**: Avoid overusing `def` — declare explicit types when possible; use `@TypeChecked` / `@CompileStatic`
- **Null safety**: Safe navigation `?.`; Elvis `?:`; watch for null in GStrings
- **Gradle**: `implementation` vs `api` dependency scope; `buildscript` vs `plugins` block
- **Closures**: Be clear about delegates (`delegate`, `owner`, `this`); understand `return` inside closures
- **Security**: Watch shell command injection in GStrings; no `evaluate()` / `Eval.me()`
- **Tests**: Spock `given/when/then` structure; `@Unroll` parametrization; distinguish Mock / Stub / Spy
"""

COMPACT = "## Groovy: @CompileStatic, ?. Elvis, Gradle implementation vs api, no evaluate(), Spock"

FULL_KO = """\
## Groovy 검토 기준
- **타입**: `def` 과용 금지 — 가능한 명시적 타입 선언, `@TypeChecked`/`@CompileStatic`
- **null 안전**: `?.` 안전 탐색, `?:` Elvis 연산자, GString 내 null 삽입 주의
- **Gradle**: `implementation` vs `api` 의존성 범위, `buildscript` vs `plugins` 블록
- **클로저**: 델리게이트 명확성(`delegate`, `owner`, `this`), 클로저 내 `return` 동작
- **보안**: GString 내 셸 명령 주입, `evaluate()`/`Eval.me()` 금지
- **테스트**: Spock `given/when/then` 구조, `@Unroll` 파라미터화, Mock/Stub/Spy 구분
"""

COMPACT_KO = "## Groovy: @CompileStatic, ?. Elvis, Gradle implementation vs api, evaluate() 금지, Spock"

FULL_JA = """\
## Groovy レビュー基準
- **型**: `def` の濫用禁止 — 可能な限り明示的な型宣言、`@TypeChecked` / `@CompileStatic`
- **null 安全**: 安全ナビゲーション `?.`、Elvis 演算子 `?:`、GString 内の null 注入に注意
- **Gradle**: `implementation` vs `api` の依存スコープ、`buildscript` vs `plugins` ブロック
- **クロージャ**: デリゲートの明確化 (`delegate`、`owner`、`this`)、クロージャ内 `return` の動作
- **セキュリティ**: GString 内のシェルコマンド注入、`evaluate()` / `Eval.me()` 禁止
- **テスト**: Spock `given/when/then` 構造、`@Unroll` パラメータ化、Mock / Stub / Spy 区別
"""

COMPACT_JA = "## Groovy: @CompileStatic、?. Elvis、Gradle implementation vs api、evaluate() 禁止、Spock"
