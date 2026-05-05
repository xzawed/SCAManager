"""Crystal review guide — Tier 3.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Crystal review checklist
- **Null safety**: `Nil` union type; minimize `not_nil!`; handle nil with `try` / `if`
- **Types**: Explicit type annotations on public APIs; generic type constraints
- **Concurrency**: Fiber-based; `Channel` communication; `Mutex` for shared state
- **Exceptions**: `rescue` / `ensure` / `raise`; Ruby-like syntax but with static type constraints
- **C bindings**: `lib` / `fun` FFI type safety; manual `Pointer` memory management
"""

COMPACT = "## Crystal: avoid not_nil!, generic constraints, Fiber/Channel, C FFI type safety"

FULL_KO = """\
## Crystal 검토 기준
- **null 안전**: `Nil` 공용체 타입, `not_nil!` 최소화, `try`/`if`로 nil 처리
- **타입**: 명시적 타입 어노테이션(public API), 제네릭 타입 제약
- **동시성**: Fiber 기반, `Channel` 통신, `Mutex` 공유 상태
- **예외**: `rescue`/`ensure`/`raise`, Ruby 유사 문법이지만 정적 타입 제약
- **C 바인딩**: `lib`/`fun` FFI 타입 안전성, `Pointer` 수동 메모리 관리
"""

COMPACT_KO = "## Crystal: not_nil! 금지, 제네릭 타입 제약, Fiber/Channel, C FFI 타입 안전성"

FULL_JA = """\
## Crystal レビュー基準
- **null 安全**: `Nil` 共用体型、`not_nil!` を最小化、`try` / `if` で nil 処理
- **型**: 公開 API に明示的型アノテーション、ジェネリック型制約
- **並行性**: Fiber ベース、`Channel` 通信、`Mutex` で共有状態
- **例外**: `rescue` / `ensure` / `raise`、Ruby ライクな構文だが静的型制約あり
- **C バインディング**: `lib` / `fun` FFI 型安全性、`Pointer` 手動メモリ管理
"""

COMPACT_JA = "## Crystal: not_nil! 禁止、ジェネリック制約、Fiber/Channel、C FFI 型安全性"
