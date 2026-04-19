"""Nim review guide — Tier 3."""

FULL = """\
## Nim 검토 기준
- **메모리**: GC 모드 선택(ORC/ARC 선호), `owned ref` 수명, `=destroy` 훅
- **에러**: `Result[T, E]` 타입(`results` 패키지) vs 예외, `try`/`except`/`finally`
- **pragma**: `{.raises: [].}` 예외 추적, `{.noSideEffect.}`, `{.pure.}` enum
- **매크로**: 매크로/템플릿 위생성(gensym), 과도한 매크로 복잡도 경계
- **백엔드**: C/JS 백엔드 타겟 고려, FFI `{.importc.}` 타입 매핑 검증
"""

COMPACT = "## Nim: ORC/ARC GC, Result 타입, {.raises.} pragma, 위생 매크로, FFI 타입 매핑"
