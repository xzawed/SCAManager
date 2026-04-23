"""Protocol Buffers review guide — Tier 3."""

FULL = """\
## Protocol Buffers 검토 기준
- **필드 번호**: 기존 번호 변경/재사용 금지(하위 호환성 파괴), reserved 선언으로 제거된 번호 보호
- **타입 선택**: `int32` vs `sint32`(음수 효율), `bytes` vs `string`(UTF-8 보장 여부)
- **하위 호환**: 필드 추가는 optional만, required(proto2) 신규 추가 금지, 기본값 의존 주의
- **패키지**: `package` 네임스페이스 명시, import 경로 절대 경로
- **gRPC**: streaming vs unary 선택 근거, 에러 status code 의미론적 정확성
- **성능**: 대용량 repeated 필드 페이지네이션, `google.protobuf.Any` 타입 안전성
"""

COMPACT = "## Protobuf: 필드 번호 불변, reserved 보호, sint32 음수, 하위 호환 optional만 추가, gRPC status"
