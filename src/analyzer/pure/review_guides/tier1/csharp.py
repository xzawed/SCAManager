"""C# review guide — Tier 1 deep checklist."""

FULL = """\
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

COMPACT = "## C#: async void 금지, nullable enable, LINQ 지연실행, IDisposable using, Captive Dependency"
