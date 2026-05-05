"""Zig review guide — Tier 3.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Zig review checklist
- **Error handling**: `try` / `catch` / `errdefer`; explicit error union types; bounded error sets
- **Memory**: Pass allocators explicitly (Allocator pattern); `defer allocator.free(...)`; prefer comptime stack
- **comptime**: Use compile-time computation; generic types; cap comptime complexity
- **undefined**: Verify initialization; document `undefined` usage scope; debug/release differences
- **Safety**: `@intCast` / `@floatCast` overflow; bounds checks; pointer lifetimes
"""

COMPACT = "## Zig: errdefer, explicit Allocator, comptime generics, init undefined, @intCast overflow"

FULL_KO = """\
## Zig 검토 기준
- **에러 처리**: `try`/`catch`/`errdefer`, 에러 유니온 타입 명시, 에러 집합 범위
- **메모리**: 할당자 명시적 전달(Allocator 패턴), `defer allocator.free(...)`, comptime 스택 선호
- **comptime**: 컴파일타임 연산 활용, 타입 제네릭 구현, comptime 과도한 복잡도 경계
- **undefined**: 초기화 검증, `undefined` 사용 범위 문서화, 디버그/릴리즈 차이
- **안전성**: `@intCast`/`@floatCast` 오버플로, 경계 검사, 포인터 수명
"""

COMPACT_KO = "## Zig: errdefer, 명시적 Allocator, comptime 제네릭, undefined 초기화, @intCast 오버플로"

FULL_JA = """\
## Zig レビュー基準
- **エラー処理**: `try` / `catch` / `errdefer`、エラー共用体型を明示、エラー集合の範囲
- **メモリ**: アロケータを明示的に渡す (Allocator パターン)、`defer allocator.free(...)`、comptime スタック推奨
- **comptime**: コンパイル時演算活用、ジェネリック型実装、comptime 過度な複雑度を制限
- **undefined**: 初期化検証、`undefined` 使用範囲を文書化、デバッグ/リリースの違い
- **安全性**: `@intCast` / `@floatCast` オーバーフロー、境界チェック、ポインタ寿命
"""

COMPACT_JA = "## Zig: errdefer、明示的 Allocator、comptime ジェネリック、undefined 初期化、@intCast オーバーフロー"
