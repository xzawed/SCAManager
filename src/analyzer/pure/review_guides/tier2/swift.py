"""Swift review guide — Tier 2.

Phase 4 PR-14 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Swift review checklist
- **Optionals**: Minimize force-unwrap (`!`); use `guard let` / `if let`; `??` nil-coalescing
- **Memory**: ARC retain cycles — `[weak self]` / `[unowned self]` capture lists in closures
- **Concurrency**: Swift Concurrency (`async/await`, `Actor`); watch DispatchQueue races
- **Types**: `struct` vs `class` (prefer value types); `protocol` + `extension` composition
- **Errors**: `throws` / `try` / `catch`; `Result<T, Error>` return type
- **SwiftUI**: Correct `@State` / `@Binding` / `@ObservedObject`; minimize view recomputation
"""

COMPACT = "## Swift: avoid force-unwrap, [weak self], async/await, prefer struct, protocol+extension"

FULL_KO = """\
## Swift 검토 기준
- **옵셔널**: 강제 언래핑(`!`) 최소화, `guard let`/`if let` 활용, `??` nil 병합 연산자
- **메모리**: ARC retain cycle — `[weak self]`/`[unowned self]` 클로저 캡처 목록
- **동시성**: Swift Concurrency(`async/await`, `Actor`), DispatchQueue 경쟁 조건
- **타입**: `struct` vs `class` 선택(값 타입 선호), `protocol` + `extension` 구성
- **에러**: `throws`/`try`/`catch`, `Result<T, Error>` 반환 타입
- **SwiftUI**: `@State`/`@Binding`/`@ObservedObject` 적절성, View 재연산 최소화
"""

COMPACT_KO = "## Swift: 강제 언래핑 금지, [weak self], async/await, struct 선호, protocol+extension"

FULL_JA = """\
## Swift レビュー基準
- **オプショナル**: 強制アンラップ (`!`) を最小化、`guard let` / `if let` を活用、`??` nil 結合演算子
- **メモリ**: ARC retain cycle — クロージャキャプチャリスト `[weak self]` / `[unowned self]`
- **並行性**: Swift Concurrency (`async/await`、`Actor`)、DispatchQueue 競合
- **型**: `struct` vs `class` 選択 (値型推奨)、`protocol` + `extension` 構成
- **エラー**: `throws` / `try` / `catch`、`Result<T, Error>` 戻り値型
- **SwiftUI**: `@State` / `@Binding` / `@ObservedObject` の適切性、View 再計算を最小化
"""

COMPACT_JA = "## Swift: 強制アンラップ禁止、[weak self]、async/await、struct 推奨、protocol+extension"
