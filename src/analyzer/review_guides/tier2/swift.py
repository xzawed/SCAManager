"""Swift review guide — Tier 2."""

FULL = """\
## Swift 검토 기준
- **옵셔널**: 강제 언래핑(`!`) 최소화, `guard let`/`if let` 활용, `??` nil 병합 연산자
- **메모리**: ARC retain cycle — `[weak self]`/`[unowned self]` 클로저 캡처 목록
- **동시성**: Swift Concurrency(`async/await`, `Actor`), DispatchQueue 경쟁 조건
- **타입**: `struct` vs `class` 선택(값 타입 선호), `protocol` + `extension` 구성
- **에러**: `throws`/`try`/`catch`, `Result<T, Error>` 반환 타입
- **SwiftUI**: `@State`/`@Binding`/`@ObservedObject` 적절성, View 재연산 최소화
"""

COMPACT = "## Swift: 강제 언래핑 금지, [weak self], async/await, struct 선호, protocol+extension"
