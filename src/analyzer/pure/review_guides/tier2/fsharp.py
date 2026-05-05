"""F# review guide — Tier 2.

Phase 4 PR-14 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## F# review checklist
- **Immutability**: Prefer `let` immutable bindings; minimize `mutable`; use record `with` updates
- **Types**: Discriminated unions (DU) for domain modeling; `Option<T>` / `Result<T,E>` for errors; watch `unit` returns
- **Pipelines**: Readable `|>` chains; appropriate function composition (`>>`)
- **Async**: `async { }` computation expression; don't overuse `Async.RunSynchronously`
- **Pattern matching**: Exhaustive `match` (compiler warning); cap active pattern complexity
- **.NET interop**: Defensive null handling; `Option.ofObj`; `try/with` exception catch
"""

COMPACT = "## F#: immutable let, DU domain model, Option/Result, |> pipe, async computation, null defense"

FULL_KO = """\
## F# 검토 기준
- **불변성**: `let` 불변 바인딩 선호, `mutable` 최소화, 레코드 `with` 업데이트
- **타입**: 판별 유니온(DU) 도메인 모델링, `Option<T>`/`Result<T,E>` 에러 처리, `unit` 반환 주의
- **파이프라인**: `|>` 체인 가독성, 함수 합성(`>>`) 적절성
- **비동기**: `async { }` 컴퓨테이션 표현식, `Async.RunSynchronously` 남용 금지
- **패턴 매칭**: `match` 완전성(컴파일러 경고), 액티브 패턴 복잡도 경계
- **.NET 상호운용**: `null` 방어적 처리, `Option.ofObj`, `try/with` 예외 캐치
"""

COMPACT_KO = "## F#: 불변 let, DU 도메인 모델, Option/Result, |> 파이프, async 컴퓨테이션, null 방어"

FULL_JA = """\
## F# レビュー基準
- **不変性**: `let` 不変バインディング推奨、`mutable` を最小化、レコード `with` 更新
- **型**: 判別共用体 (DU) によるドメインモデリング、`Option<T>` / `Result<T,E>` でエラー処理、`unit` 戻り値に注意
- **パイプライン**: `|>` チェーンの可読性、関数合成 (`>>`) の適切性
- **非同期**: `async { }` コンピュテーション式、`Async.RunSynchronously` の濫用禁止
- **パターンマッチ**: `match` の網羅性 (コンパイラ警告)、アクティブパターンの複雑度を制限
- **.NET 相互運用**: `null` の防御的処理、`Option.ofObj`、`try/with` 例外キャッチ
"""

COMPACT_JA = "## F#: 不変 let、DU ドメインモデル、Option/Result、|> パイプ、async コンピュテーション、null 防御"
