"""Crystal review guide — Tier 3."""

FULL = """\
## Crystal 검토 기준
- **null 안전**: `Nil` 공용체 타입, `not_nil!` 최소화, `try`/`if`로 nil 처리
- **타입**: 명시적 타입 어노테이션(public API), 제네릭 타입 제약
- **동시성**: Fiber 기반, `Channel` 통신, `Mutex` 공유 상태
- **예외**: `rescue`/`ensure`/`raise`, Ruby 유사 문법이지만 정적 타입 제약
- **C 바인딩**: `lib`/`fun` FFI 타입 안전성, `Pointer` 수동 메모리 관리
"""

COMPACT = "## Crystal: not_nil! 금지, 제네릭 타입 제약, Fiber/Channel, C FFI 타입 안전성"
