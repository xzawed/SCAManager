"""Clojure review guide — Tier 2.

Phase 4 PR-14 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Clojure review checklist
- **Immutability**: Use persistent data structures; minimize shared state via `atom` / `ref` / `agent`
- **Namespaces**: Explicit `require` / `use` / `import`; no `:refer :all`
- **Errors**: Structured errors with `ex-info` / `ex-data`; `try/catch/finally`; `:cause` chains
- **Sequences**: lazy seq vs realization (`doall` / `dorun` for infinite seqs); avoid head-holding leaks
- **Macros**: Pick macro vs function carefully; hygienic macros via `#` gensym; minimize `defmacro`
- **Concurrency**: `future` / `promise`; STM `dosync`; close channels in core.async `go` blocks
- **Security**: Parameterize SQL via `clojure.java.jdbc`; `read-string` → `edn/read-string`
"""

COMPACT = "## Clojure: persistent data, no :refer :all, lazy seq head leaks, STM, edn/read-string"

FULL_KO = """\
## Clojure 검토 기준
- **불변성**: 영속 자료구조 활용, `atom`/`ref`/`agent` 공유 상태 최소화
- **네임스페이스**: `require`/`use`/`import` 명시, `:refer :all` 금지
- **에러**: `ex-info`/`ex-data` 구조적 에러, `try/catch/finally`, `:cause` 체인
- **시퀀스**: lazy seq 무한 시퀀스 `doall`/`dorun` 실체화 필요 시점, 헤드 보유 누수
- **매크로**: 매크로 vs 함수 선택 기준, gensym `#` 위생 매크로, `defmacro` 최소화
- **동시성**: `future`/`promise`, STM `dosync`, core.async `go` 블록 채널 닫기
- **보안**: SQL `clojure.java.jdbc` 파라미터화, `read-string` → `edn/read-string`
"""

COMPACT_KO = "## Clojure: 불변 자료구조, :refer :all 금지, lazy seq 헤드 누수, STM, edn/read-string"

FULL_JA = """\
## Clojure レビュー基準
- **不変性**: 永続データ構造を活用、`atom` / `ref` / `agent` の共有状態を最小化
- **名前空間**: `require` / `use` / `import` を明示、`:refer :all` 禁止
- **エラー**: `ex-info` / `ex-data` 構造化エラー、`try/catch/finally`、`:cause` チェーン
- **シーケンス**: lazy seq 無限シーケンス時の `doall` / `dorun` 実体化、ヘッド保持リーク
- **マクロ**: マクロ vs 関数の選択基準、gensym `#` 衛生マクロ、`defmacro` 最小化
- **並行性**: `future` / `promise`、STM `dosync`、core.async `go` ブロックでチャネルクローズ
- **セキュリティ**: SQL `clojure.java.jdbc` パラメータ化、`read-string` → `edn/read-string`
"""

COMPACT_JA = "## Clojure: 永続データ、:refer :all 禁止、lazy seq ヘッドリーク、STM、edn/read-string"
