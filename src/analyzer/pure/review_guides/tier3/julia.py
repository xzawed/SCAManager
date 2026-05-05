"""Julia review guide — Tier 3.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Julia review checklist
- **Type stability**: Avoid type-unstable functions (`@code_warntype`); avoid abstract-type containers
- **Performance**: Declare globals `const`; minimize allocations in loops; use `@view` for slices
- **Multiple dispatch**: Clear method signatures; avoid ambiguity; `!` mutation convention
- **Broadcasting**: Use `.` dot broadcasting; avoid unnecessary vectorization
- **Packages**: Distinguish `using` vs `import`; pin deps via `Project.toml`
"""

COMPACT = "## Julia: type stability, const globals, @view slices, multiple-dispatch clarity, Project.toml"

FULL_KO = """\
## Julia 검토 기준
- **타입 안정성**: 타입 불안정 함수 회피(`@code_warntype`), 추상 타입 컨테이너 지양
- **성능**: 전역 변수 `const` 선언, 루프 내 메모리 할당 최소화, `@view` 슬라이스
- **멀티플 디스패치**: 메서드 명확한 시그니처, 충돌 방지(ambiguity), `!` 변경 함수 컨벤션
- **브로드캐스팅**: `.` 도트 브로드캐스팅 활용, 불필요한 벡터화 회피
- **패키지**: `using` vs `import` 구분, 의존성 `Project.toml` 명시
"""

COMPACT_KO = "## Julia: 타입 안정성, const 전역, @view 슬라이스, 멀티플 디스패치 명확성, Project.toml"

FULL_JA = """\
## Julia レビュー基準
- **型安定性**: 型不安定な関数を回避 (`@code_warntype`)、抽象型コンテナを避ける
- **パフォーマンス**: グローバル変数を `const` 宣言、ループ内アロケーションを最小化、`@view` スライス
- **多重ディスパッチ**: メソッドシグネチャを明確化、曖昧性 (ambiguity) 回避、`!` 変更関数の規約
- **ブロードキャスト**: `.` ドットブロードキャスト活用、不要なベクトル化回避
- **パッケージ**: `using` vs `import` の区別、依存を `Project.toml` で明示
"""

COMPACT_JA = "## Julia: 型安定性、const グローバル、@view スライス、多重ディスパッチ明確性、Project.toml"
