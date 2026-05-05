"""C++ review guide — Tier 1 deep checklist.

Phase 4 PR-13 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## C++ review checklist
- **Smart pointers**: Prefer `unique_ptr` / `shared_ptr` over raw pointers; minimize direct `new` / `delete`
- **RAII**: Resource acquisition = initialization; no exception throws in destructors; mark copy/move constructors `= default` / `= delete`
- **Modern C++**: Use range-for, `auto`, structured bindings, `std::optional`, `std::variant` (C++17+)
- **Casting**: No C-style casts → use `static_cast` / `dynamic_cast` / `reinterpret_cast` explicitly
- **STL**: Prefer `std::vector`; don't modify containers during iteration; pre-size with `reserve()`
- **const correctness**: `const` reference parameters, `const` member functions, `constexpr` for compile-time constants
- **Exceptions**: Drop exception specifications (C++11+); mark `noexcept`; ensure exception-safe copies
- **Security**: Watch `memcpy` / `memset` size calculation errors, format string vulnerabilities, buffer overruns
"""

COMPACT = "## C++: unique_ptr, RAII, no C-style casts, const correctness, noexcept, prefer smart pointers"

FULL_KO = """\
## C++ 검토 기준
- **스마트 포인터**: raw pointer 대신 `unique_ptr`/`shared_ptr`, `new`/`delete` 직접 사용 최소화
- **RAII**: 리소스 획득=초기화, 소멸자에서 예외 throw 금지, 복사/이동 생성자 `= default`/`= delete`
- **모던 C++**: range-for, `auto`, structured binding, `std::optional`, `std::variant` 활용(C++17+)
- **캐스팅**: C-style cast 금지 → `static_cast`/`dynamic_cast`/`reinterpret_cast` 명시
- **STL**: `std::vector` 선호, 컨테이너 반복 중 수정 금지, `reserve()` 사전 크기 지정
- **const 정확성**: `const` 참조 매개변수, `const` 멤버 함수, `constexpr` 컴파일타임 상수
- **예외**: 예외 명세 제거(C++11+), noexcept 명시, exception-safe 복사 보장
- **보안**: `memcpy`/`memset` 크기 계산 오류, 포맷 문자열 취약점, 버퍼 오버런
"""

COMPACT_KO = "## C++: unique_ptr, RAII, C-style cast 금지, const 정확성, noexcept, 스마트 포인터 선호"

FULL_JA = """\
## C++ レビュー基準
- **スマートポインタ**: raw pointer より `unique_ptr` / `shared_ptr`、`new` / `delete` 直接使用を最小化
- **RAII**: リソース獲得=初期化、デストラクタでの例外 throw 禁止、コピー/ムーブコンストラクタ `= default` / `= delete`
- **モダン C++**: range-for、`auto`、structured binding、`std::optional`、`std::variant` 活用 (C++17+)
- **キャスト**: C-style cast 禁止 → `static_cast` / `dynamic_cast` / `reinterpret_cast` 明示
- **STL**: `std::vector` 推奨、コンテナ反復中の変更禁止、`reserve()` で事前サイズ指定
- **const 正確性**: `const` 参照パラメータ、`const` メンバ関数、`constexpr` コンパイル時定数
- **例外**: 例外仕様削除 (C++11+)、noexcept 明示、exception-safe コピー保証
- **セキュリティ**: `memcpy` / `memset` のサイズ計算ミス、フォーマット文字列脆弱性、バッファオーバーラン
"""

COMPACT_JA = "## C++: unique_ptr、RAII、C-style cast 禁止、const 正確性、noexcept、スマートポインタ推奨"
