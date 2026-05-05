"""OCaml review guide — Tier 3.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## OCaml review checklist
- **Types**: Trust inference but make public signatures explicit; `option` / `result` for errors
- **Pattern matching**: Exhaustive `match` (compiler warning); minimize `_` wildcard
- **Immutability**: Default immutable — comment justifications for `ref` / `mutable` fields
- **Modules**: Manage functor complexity; avoid `include` overuse; maintain `mli` interface files
- **Exceptions**: Prefer `result` types over `exception` (functional error handling); narrow `try/with` scope
"""

COMPACT = "## OCaml: option/result, exhaustive match, minimize ref, keep mli, result > exception"

FULL_KO = """\
## OCaml 검토 기준
- **타입**: 타입 추론 신뢰하되 공개 함수 시그니처 명시, `option`/`result` 에러 처리
- **패턴 매칭**: 완전한 match(컴파일러 경고), `_` 와일드카드 최소화
- **불변성**: 기본 불변 — `ref`/`mutable` 필드 사용 시 근거 주석
- **모듈**: functor 복잡도 관리, `include` 남용 주의, `mli` 인터페이스 파일 유지
- **예외**: `exception`보다 `result` 타입 선호(함수형 에러 처리), `try/with` 범위 최소화
"""

COMPACT_KO = "## OCaml: option/result, 완전 match, ref 최소화, mli 인터페이스 유지, result > exception"

FULL_JA = """\
## OCaml レビュー基準
- **型**: 型推論を信頼しつつ公開関数のシグネチャを明示、`option` / `result` でエラー処理
- **パターンマッチ**: `match` の網羅性 (コンパイラ警告)、`_` ワイルドカードを最小化
- **不変性**: デフォルトで不変 — `ref` / `mutable` フィールド使用時は根拠コメント
- **モジュール**: functor 複雑度を管理、`include` の濫用注意、`mli` インターフェースファイル維持
- **例外**: `exception` より `result` 型推奨 (関数的エラー処理)、`try/with` 範囲を最小化
"""

COMPACT_JA = "## OCaml: option/result、網羅 match、ref 最小化、mli 維持、result > exception"
