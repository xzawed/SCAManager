"""Zig review guide — Tier 3."""

FULL = """\
## Zig 검토 기준
- **에러 처리**: `try`/`catch`/`errdefer`, 에러 유니온 타입 명시, 에러 집합 범위
- **메모리**: 할당자 명시적 전달(Allocator 패턴), `defer allocator.free(...)`, comptime 스택 선호
- **comptime**: 컴파일타임 연산 활용, 타입 제네릭 구현, comptime 과도한 복잡도 경계
- **undefined**: 초기화 검증, `undefined` 사용 범위 문서화, 디버그/릴리즈 차이
- **안전성**: `@intCast`/`@floatCast` 오버플로, 경계 검사, 포인터 수명
"""

COMPACT = "## Zig: errdefer, 명시적 Allocator, comptime 제네릭, undefined 초기화, @intCast 오버플로"
