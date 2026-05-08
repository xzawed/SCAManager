"""Java review guide — Tier 1 deep checklist.

Phase 4 PR-13 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Java review checklist
- **Naming**: PascalCase classes, camelCase methods/variables, UPPER_SNAKE constants
- **Null safety**: Use `Optional<T>`; prevent `NullPointerException` — return Optional rather than null
- **Exceptions**: Avoid overusing checked exceptions; on direct `Exception` catch, log + rethrow
- **Collections**: No raw types (`List` without generic); use `Collections.unmodifiableList()` for immutability
- **Concurrency**: Minimize `synchronized` scope; correct use of `volatile` / `AtomicXxx`; watch ThreadLocal leaks
- **Streams**: Excessive chaining hurts readability — split when needed;
  prefer `toList()` (Java 16+) over `collect(Collectors.toList())`
- **Security**: No SQL string formatting → PreparedStatement; validate input to `Runtime.exec()`
- **Dependencies**: Watch circular dependencies and SRP (single responsibility) violations
"""

COMPACT = "## Java: Optional, no raw types, minimize checked exceptions, PreparedStatement, circular deps"

FULL_KO = """\
## Java 검토 기준
- **네이밍**: PascalCase 클래스, camelCase 메서드/변수, UPPER_SNAKE 상수
- **null 안전**: `Optional<T>` 활용, `NullPointerException` 방지 — null 반환 대신 Optional 반환
- **예외**: checked exception 남발 금지, `Exception` 직접 catch 시 로그+재던지기
- **컬렉션**: raw type(`List` without generic) 금지, `Collections.unmodifiableList()` 불변 보장
- **동시성**: `synchronized` 범위 최소화, `volatile`/`AtomicXxx` 적절성, ThreadLocal 누수
- **스트림**: Stream API 과도한 체인으로 가독성 저하 시 분리, `collect(Collectors.toList())` → `toList()`(Java 16+)
- **보안**: SQL 문자열 포맷팅 금지 → PreparedStatement, `Runtime.exec()` 입력 검증
- **의존성**: 순환 의존성, 클래스 단일 책임 원칙(SRP) 위반 여부
"""

COMPACT_KO = "## Java: Optional 활용, raw type 금지, checked exception 최소화, PreparedStatement, 순환 의존성"

FULL_JA = """\
## Java レビュー基準
- **命名**: PascalCase クラス、camelCase メソッド/変数、UPPER_SNAKE 定数
- **null 安全**: `Optional<T>` 活用、`NullPointerException` 防止 — null 戻り値より Optional 戻り値
- **例外**: checked exception の濫用禁止、`Exception` 直接 catch 時はログ+再 throw
- **コレクション**: raw type (`List` without generic) 禁止、`Collections.unmodifiableList()` で不変保証
- **並行性**: `synchronized` 範囲を最小化、`volatile` / `AtomicXxx` の適切性、ThreadLocal 漏れ
- **ストリーム**: Stream API 過度なチェーンで可読性低下時は分割、`collect(Collectors.toList())` → `toList()` (Java 16+)
- **セキュリティ**: SQL 文字列フォーマット禁止 → PreparedStatement、`Runtime.exec()` の入力検証
- **依存**: 循環依存、クラス単一責任原則 (SRP) 違反確認
"""

COMPACT_JA = "## Java: Optional 活用、raw type 禁止、checked exception 最小化、PreparedStatement、循環依存"
