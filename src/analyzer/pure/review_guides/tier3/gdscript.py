"""GDScript (Godot) review guide — Tier 3."""

FULL = """\
## GDScript 검토 기준
- **타입 힌트**: `: Type` 정적 타입 명시(성능 + 가독성), `@export` 변수 타입
- **노드 참조**: `@onready var` 초기화, `get_node()` vs `$` 일관성, null 체크
- **시그널**: `signal` 선언 + `emit`/`connect` 쌍, 불필요한 폴링 대신 시그널
- **_process vs _physics_process**: 게임 로직 분리, `delta` 시간 기반 이동
- **메모리**: `queue_free()` 노드 해제, `preload`/`load` 선택(컴파일타임 vs 런타임)
- **Godot 4**: `await` 시그널, `Resource` 불변성, `Node` 씬 트리 의존성 최소화
"""

COMPACT = "## GDScript: 타입 힌트, @onready, signal emit/connect, delta 이동, queue_free, await 시그널"
