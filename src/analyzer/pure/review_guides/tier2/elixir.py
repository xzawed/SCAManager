"""Elixir review guide — Tier 2.

Phase 4 PR-14 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Elixir review checklist
- **Pattern matching**: Exhaustive `case` / `cond` / `with`; explicit intent for `_` wildcards
- **Pipelines**: Readable `|>` chains; follow first-arg data-flow pattern
- **Processes**: Correct GenServer `handle_call` / `handle_cast` return tuples; avoid process leaks
- **Errors**: `{:ok, result}` / `{:error, reason}` tuple pattern; error propagation in `with` chains
- **Immutability**: Clear data transformation chains; serialize access to ETS shared state
- **Tests**: ExUnit `describe` / `test`; `Mox` for mocks; `ExUnit.Case async: true`
- **Security**: Validate external input via `Ecto.Changeset`; parameterize via Ecto for SQL injection
"""

COMPACT = "## Elixir: {:ok/:error} tuples, with error propagation, GenServer return, Ecto Changeset"

FULL_KO = """\
## Elixir 검토 기준
- **패턴 매칭**: `case`/`cond`/`with` 완전 매칭, `_` 와일드카드 명시적 의도
- **파이프라인**: `|>` 체인 가독성, 첫 인수 데이터 흐름 패턴 준수
- **프로세스**: GenServer `handle_call`/`handle_cast` 반환 튜플 정확성, 프로세스 누수
- **에러**: `{:ok, result}`/`{:error, reason}` 튜플 패턴, `with` 체인 에러 전파
- **불변성**: 데이터 변환 체인 명확성, ETS 공유 상태 접근 직렬화
- **테스트**: ExUnit `describe`/`test`, `Mox` 목킹, `ExUnit.Case async: true`
- **보안**: 외부 입력 `Ecto.Changeset` 검증, SQL injection Ecto 파라미터화
"""

COMPACT_KO = "## Elixir: {:ok/:error} 튜플, with 에러 전파, GenServer 반환 튜플, Ecto Changeset 검증"

FULL_JA = """\
## Elixir レビュー基準
- **パターンマッチ**: `case` / `cond` / `with` の網羅的マッチ、`_` ワイルドカードは意図を明示
- **パイプライン**: `|>` チェーンの可読性、第一引数のデータフローパターンに従う
- **プロセス**: GenServer `handle_call` / `handle_cast` の戻り値タプルの正確性、プロセス漏れ
- **エラー**: `{:ok, result}` / `{:error, reason}` タプルパターン、`with` チェーンでのエラー伝播
- **不変性**: データ変換チェーンの明確性、ETS 共有状態アクセスの直列化
- **テスト**: ExUnit `describe` / `test`、`Mox` モック、`ExUnit.Case async: true`
- **セキュリティ**: 外部入力を `Ecto.Changeset` で検証、SQL injection は Ecto でパラメータ化
"""

COMPACT_JA = "## Elixir: {:ok/:error} タプル、with エラー伝播、GenServer 戻り値タプル、Ecto Changeset"
