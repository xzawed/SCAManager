"""Elm review guide — Tier 3.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Elm review checklist
- **Architecture**: Clear Model-Update-View pattern; exhaustive Msg union type handling
- **Types**: Handle all `Maybe` / `Result` (compiler-enforced); clear type aliases
- **Side effects**: Only via Cmd/Sub; JS interop through Ports
- **Performance**: Use `Html.Lazy.lazy` to minimize re-renders; `Html.Keyed`
- **Packages**: `elm.json` dependency version constraints; follow `elm-review` rules
"""

COMPACT = "## Elm: MVU pattern, exhaustive Maybe/Result, Cmd/Sub side effects, Port JS interop, elm-review"

FULL_KO = """\
## Elm 검토 기준
- **아키텍처**: Model-Update-View 패턴 명확성, Msg 유니온 타입 완전 처리
- **타입**: 모든 `Maybe`/`Result` 처리 누락 금지(컴파일러 강제), 타입 별칭 명확성
- **부작용**: Cmd/Sub 통해서만 부작용, JS 상호운용은 Port 경유
- **성능**: 불필요한 `Html.Lazy.lazy` 없는 재렌더링 최소화, `Html.Keyed`
- **패키지**: `elm.json` 의존성 버전 제약, `elm-review` 규칙 준수
"""

COMPACT_KO = "## Elm: MVU 패턴, Maybe/Result 완전 처리, Cmd/Sub 부작용, Port JS 상호운용, elm-review"

FULL_JA = """\
## Elm レビュー基準
- **アーキテクチャ**: Model-Update-View パターンの明確性、Msg 共用体型の網羅処理
- **型**: 全ての `Maybe` / `Result` 処理 (コンパイラ強制)、型エイリアスの明確性
- **副作用**: Cmd/Sub 経由のみで副作用、JS 相互運用は Port 経由
- **パフォーマンス**: `Html.Lazy.lazy` で再レンダリング最小化、`Html.Keyed`
- **パッケージ**: `elm.json` 依存バージョン制約、`elm-review` ルール遵守
"""

COMPACT_JA = "## Elm: MVU パターン、Maybe/Result 網羅処理、Cmd/Sub 副作用、Port JS 相互運用、elm-review"
