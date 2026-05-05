"""Nim review guide — Tier 3.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Nim review checklist
- **Memory**: Choose GC mode (prefer ORC/ARC); `owned ref` lifetimes; `=destroy` hooks
- **Errors**: `Result[T, E]` (from `results` package) vs exceptions; `try` / `except` / `finally`
- **Pragmas**: `{.raises: [].}` for exception tracking; `{.noSideEffect.}`; `{.pure.}` enums
- **Macros**: Hygienic macros/templates (gensym); cap excessive macro complexity
- **Backends**: Consider C/JS backend targets; verify FFI `{.importc.}` type mapping
"""

COMPACT = "## Nim: ORC/ARC GC, Result type, {.raises.} pragma, hygienic macros, FFI type mapping"

FULL_KO = """\
## Nim 검토 기준
- **메모리**: GC 모드 선택(ORC/ARC 선호), `owned ref` 수명, `=destroy` 훅
- **에러**: `Result[T, E]` 타입(`results` 패키지) vs 예외, `try`/`except`/`finally`
- **pragma**: `{.raises: [].}` 예외 추적, `{.noSideEffect.}`, `{.pure.}` enum
- **매크로**: 매크로/템플릿 위생성(gensym), 과도한 매크로 복잡도 경계
- **백엔드**: C/JS 백엔드 타겟 고려, FFI `{.importc.}` 타입 매핑 검증
"""

COMPACT_KO = "## Nim: ORC/ARC GC, Result 타입, {.raises.} pragma, 위생 매크로, FFI 타입 매핑"

FULL_JA = """\
## Nim レビュー基準
- **メモリ**: GC モードの選択 (ORC/ARC 推奨)、`owned ref` 寿命、`=destroy` フック
- **エラー**: `Result[T, E]` 型 (`results` パッケージ) vs 例外、`try` / `except` / `finally`
- **pragma**: `{.raises: [].}` 例外追跡、`{.noSideEffect.}`、`{.pure.}` enum
- **マクロ**: マクロ/テンプレートの衛生性 (gensym)、過度なマクロ複雑度を制限
- **バックエンド**: C/JS バックエンドのターゲット考慮、FFI `{.importc.}` 型マッピング検証
"""

COMPACT_JA = "## Nim: ORC/ARC GC、Result 型、{.raises.} pragma、衛生マクロ、FFI 型マッピング"
