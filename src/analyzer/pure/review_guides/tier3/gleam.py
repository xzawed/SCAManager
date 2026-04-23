"""Gleam review guide — Tier 3."""

FULL = """\
## Gleam 검토 기준
- **타입**: 완전한 패턴 매칭(컴파일러 강제), `Result(a, e)` 에러 처리
- **파이프라인**: `|>` 연산자 함수형 스타일, 단방향 데이터 흐름
- **불변성**: 모든 값 불변, 레코드 업데이트 문법
- **BEAM 상호운용**: Erlang/Elixir FFI `external fn`, 타입 경계 검증
- **모듈**: 공개/비공개 명시(`pub`), import 명시적 선택
"""

COMPACT = "## Gleam: 완전 패턴 매칭, Result 타입, |> 파이프, 불변성, BEAM FFI 타입 경계"
