"""C# review guide — Tier 1 deep checklist.

Phase 4 PR-13 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## C# review checklist
- **async/await**: No `async void` (except event handlers); use `ConfigureAwait(false)` in library code
- **Null safety**: Enable nullable reference types (`#nullable enable`); use `?.` / `??` / `??=`;
  minimize null-forgiving (`!`)
- **LINQ**: Understand deferred execution (force with `.ToList()`); avoid N+1 queries;
  prevent multiple enumeration of `IEnumerable`
- **IDisposable**: Use `using` declarations or `try/finally`; ensure `Dispose()` for unmanaged resources
- **Exceptions**: Avoid catching `Exception` directly; use `AggregateException.Flatten()`, `ExceptionDispatchInfo`
- **Collections**: `List<T>` vs `IReadOnlyList<T>` for public APIs; thread-safety with `ConcurrentDictionary`
- **DI**: Prefer constructor injection; do not inject Scoped services into Singletons (Captive Dependency)
- **Security**: No SQL string concatenation → parameterized queries; `SecureString` vs `string` for sensitive data
"""

COMPACT = "## C#: avoid async void, nullable enable, LINQ deferred exec, IDisposable using, Captive Dependency"

FULL_KO = """\
## C# 검토 기준
- **async/await**: `async void` 금지(이벤트 핸들러 제외), `ConfigureAwait(false)` 라이브러리 코드
- **null 안전**: nullable reference types(`#nullable enable`), `?.`/`??`/`??=` 활용, null forgiving(`!`) 최소화
- **LINQ**: 지연 실행 이해(`.ToList()` 강제 실행 시점), N+1 쿼리 방지, `IEnumerable` 다중 열거 방지
- **IDisposable**: `using` 선언 또는 `try/finally`, 비관리 리소스 `Dispose()` 보장
- **예외**: `Exception` 직접 catch 금지, `AggregateException.Flatten()`, `ExceptionDispatchInfo`
- **컬렉션**: `List<T>` vs `IReadOnlyList<T>` 공개 API, `ConcurrentDictionary` 스레드 안전성
- **DI**: 생성자 주입 선호, Scoped service를 Singleton에 주입 금지(Captive Dependency)
- **보안**: SQL 문자열 연결 금지 → 파라미터화 쿼리, `SecureString` vs `string` 민감 데이터
"""

COMPACT_KO = "## C#: async void 금지, nullable enable, LINQ 지연실행, IDisposable using, Captive Dependency"

FULL_JA = """\
## C# レビュー基準
- **async/await**: `async void` 禁止 (イベントハンドラを除く)、ライブラリコードで `ConfigureAwait(false)`
- **null 安全**: nullable reference types (`#nullable enable`)、`?.` / `??` / `??=` 活用、null forgiving (`!`) を最小化
- **LINQ**: 遅延実行を理解 (`.ToList()` で強制実行のタイミング)、N+1 クエリ防止、`IEnumerable` 多重列挙防止
- **IDisposable**: `using` 宣言または `try/finally`、非管理リソースの `Dispose()` 保証
- **例外**: `Exception` 直接 catch 禁止、`AggregateException.Flatten()`、`ExceptionDispatchInfo`
- **コレクション**: `List<T>` vs `IReadOnlyList<T>` 公開 API、`ConcurrentDictionary` のスレッド安全性
- **DI**: コンストラクタインジェクション推奨、Scoped service を Singleton に注入禁止 (Captive Dependency)
- **セキュリティ**: SQL 文字列連結禁止 → パラメータ化クエリ、機密データに `SecureString` vs `string`
"""

COMPACT_JA = "## C#: async void 禁止、nullable enable、LINQ 遅延実行、IDisposable using、Captive Dependency"
