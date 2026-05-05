"""Gleam review guide — Tier 3.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Gleam review checklist
- **Types**: Exhaustive pattern matching (compiler-enforced); `Result(a, e)` for errors
- **Pipelines**: `|>` operator for functional style; single-direction data flow
- **Immutability**: All values immutable; record update syntax
- **BEAM interop**: Erlang/Elixir FFI via `external fn`; verify type boundaries
- **Modules**: Mark visibility (`pub`); explicit import selection
"""

COMPACT = "## Gleam: exhaustive matching, Result type, |> pipe, immutability, BEAM FFI boundaries"

FULL_KO = """\
## Gleam 검토 기준
- **타입**: 완전한 패턴 매칭(컴파일러 강제), `Result(a, e)` 에러 처리
- **파이프라인**: `|>` 연산자 함수형 스타일, 단방향 데이터 흐름
- **불변성**: 모든 값 불변, 레코드 업데이트 문법
- **BEAM 상호운용**: Erlang/Elixir FFI `external fn`, 타입 경계 검증
- **모듈**: 공개/비공개 명시(`pub`), import 명시적 선택
"""

COMPACT_KO = "## Gleam: 완전 패턴 매칭, Result 타입, |> 파이프, 불변성, BEAM FFI 타입 경계"

FULL_JA = """\
## Gleam レビュー基準
- **型**: 網羅的パターンマッチ (コンパイラ強制)、`Result(a, e)` でエラー処理
- **パイプライン**: `|>` 演算子の関数型スタイル、単一方向のデータフロー
- **不変性**: 全ての値が不変、レコード更新構文
- **BEAM 相互運用**: Erlang/Elixir FFI を `external fn` で、型境界を検証
- **モジュール**: 可視性 (`pub`) 明示、import の明示的選択
"""

COMPACT_JA = "## Gleam: 網羅マッチ、Result 型、|> パイプ、不変性、BEAM FFI 境界"
