"""Rust review guide — Tier 1 deep checklist.

Phase 4 PR-13 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Rust review checklist
- **Ownership**: Avoid unnecessary `clone()` overuse; check whether explicit lifetimes (`'a`) are required
- **Error handling**: Review `unwrap()` / `expect()` for panic risk; use `?` for propagation
- **Types**: Consistent `Result<T, E>` / `Option<T>` use; `Box<dyn Error>` vs concrete types
- **unsafe**: Minimize and document `unsafe` blocks; justify raw pointer usage with comments
- **Concurrency**: Watch deadlock risk in `Mutex` / `RwLock`; avoid overusing `Arc` vs `Rc` (single-thread)
- **Performance**: Avoid unnecessary heap allocations (`Box`, excessive `Vec`); pick `&str` vs `String` carefully
- **Pattern matching**: Exhaustive `match`; prefer `if let` vs `match` appropriately; handle nested `Option`
- **Dependencies**: Commit `Cargo.lock` (binaries); run `cargo audit` for vulnerabilities
"""

COMPACT = "## Rust: avoid unwrap→?, watch clone, document unsafe, Arc/Mutex deadlocks, cargo audit"

FULL_KO = """\
## Rust 검토 기준
- **소유권**: 불필요한 `clone()` 남용 확인, 참조 수명(`'a`) 명시 필요 여부
- **에러 처리**: `unwrap()`/`expect()` — panic 가능 지점 리뷰 필수, `?` 연산자 전파 패턴
- **타입**: `Result<T, E>` / `Option<T>` 일관 사용, `Box<dyn Error>` vs 구체 타입
- **unsafe**: `unsafe` 블록 최소화·문서화, raw pointer 사용 근거 주석
- **동시성**: `Mutex`/`RwLock` 데드락 위험, `Arc` 남용 vs `Rc` 단일 스레드
- **성능**: 불필요한 힙 할당(`Box`, `Vec` 과다), `&str` vs `String` 선택
- **패턴 매칭**: `match` 완전성, if let vs match 적절성, 중첩 `Option` 처리
- **의존성**: `Cargo.lock` 커밋(바이너리), `cargo audit` 취약점 여부
"""

COMPACT_KO = "## Rust: unwrap 금지→?, clone 남용, unsafe 최소화·문서화, Arc/Mutex 데드락, cargo audit"

FULL_JA = """\
## Rust レビュー基準
- **所有権**: 不要な `clone()` の濫用確認、参照ライフタイム (`'a`) 明示の要否
- **エラー処理**: `unwrap()` / `expect()` — panic 可能箇所のレビュー必須、`?` 演算子による伝播パターン
- **型**: `Result<T, E>` / `Option<T>` の一貫使用、`Box<dyn Error>` vs 具体型
- **unsafe**: `unsafe` ブロックを最小化・文書化、raw pointer 使用根拠コメント
- **並行性**: `Mutex` / `RwLock` のデッドロックリスク、`Arc` 濫用 vs `Rc` (単一スレッド)
- **パフォーマンス**: 不要なヒープアロケーション (`Box`、`Vec` 過多)、`&str` vs `String` の選択
- **パターンマッチ**: `match` の網羅性、`if let` vs `match` の適切性、ネスト `Option` 処理
- **依存**: `Cargo.lock` コミット (バイナリ)、`cargo audit` 脆弱性確認
"""

COMPACT_JA = "## Rust: unwrap 禁止→?、clone 濫用、unsafe 最小化・文書化、Arc/Mutex デッドロック、cargo audit"
