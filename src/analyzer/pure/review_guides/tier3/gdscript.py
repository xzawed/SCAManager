"""GDScript (Godot) review guide — Tier 3.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## GDScript review checklist
- **Type hints**: Explicit `: Type` for static typing (performance + readability); `@export` variable types
- **Node references**: `@onready var` for initialization; consistent `get_node()` vs `$`; null checks
- **Signals**: `signal` declaration + `emit` / `connect` pair; signals over polling
- **_process vs _physics_process**: Separate game logic; `delta`-based time movement
- **Memory**: `queue_free()` to release nodes; `preload` vs `load` (compile-time vs runtime)
- **Godot 4**: `await` signals; `Resource` immutability; minimize `Node` scene tree dependencies
"""

COMPACT = "## GDScript: type hints, @onready, signal emit/connect, delta movement, queue_free, await signal"

FULL_KO = """\
## GDScript 검토 기준
- **타입 힌트**: `: Type` 정적 타입 명시(성능 + 가독성), `@export` 변수 타입
- **노드 참조**: `@onready var` 초기화, `get_node()` vs `$` 일관성, null 체크
- **시그널**: `signal` 선언 + `emit`/`connect` 쌍, 불필요한 폴링 대신 시그널
- **_process vs _physics_process**: 게임 로직 분리, `delta` 시간 기반 이동
- **메모리**: `queue_free()` 노드 해제, `preload`/`load` 선택(컴파일타임 vs 런타임)
- **Godot 4**: `await` 시그널, `Resource` 불변성, `Node` 씬 트리 의존성 최소화
"""

COMPACT_KO = "## GDScript: 타입 힌트, @onready, signal emit/connect, delta 이동, queue_free, await 시그널"

FULL_JA = """\
## GDScript レビュー基準
- **型ヒント**: `: Type` で静的型を明示 (パフォーマンス + 可読性)、`@export` 変数の型
- **ノード参照**: `@onready var` で初期化、`get_node()` vs `$` の一貫性、null チェック
- **シグナル**: `signal` 宣言 + `emit` / `connect` ペア、ポーリングよりシグナル
- **_process vs _physics_process**: ゲームロジックを分離、`delta` 時間ベース移動
- **メモリ**: `queue_free()` でノード解放、`preload` / `load` 選択 (コンパイル時 vs 実行時)
- **Godot 4**: `await` シグナル、`Resource` 不変性、`Node` シーンツリー依存を最小化
"""

COMPACT_JA = "## GDScript: 型ヒント、@onready、signal emit/connect、delta 移動、queue_free、await シグナル"
