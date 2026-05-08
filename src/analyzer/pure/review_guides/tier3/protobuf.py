"""Protocol Buffers review guide — Tier 3.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Protocol Buffers review checklist
- **Field numbers**: Don't change/reuse existing numbers (breaks compatibility);
  use `reserved` to protect removed numbers
- **Type choice**: `int32` vs `sint32` (negative efficiency); `bytes` vs `string` (UTF-8 guarantee)
- **Backward compat**: Add fields as optional only; no new `required` (proto2); careful with default reliance
- **Packages**: Explicit `package` namespace; absolute import paths
- **gRPC**: Justify streaming vs unary; semantic accuracy of error status codes
- **Performance**: Paginate large repeated fields; type safety of `google.protobuf.Any`
"""

COMPACT = (
    "## Protobuf: stable field numbers, reserved protection, "
    "sint32 negatives, additions optional only, gRPC status"
)

FULL_KO = """\
## Protocol Buffers 검토 기준
- **필드 번호**: 기존 번호 변경/재사용 금지(하위 호환성 파괴), reserved 선언으로 제거된 번호 보호
- **타입 선택**: `int32` vs `sint32`(음수 효율), `bytes` vs `string`(UTF-8 보장 여부)
- **하위 호환**: 필드 추가는 optional만, required(proto2) 신규 추가 금지, 기본값 의존 주의
- **패키지**: `package` 네임스페이스 명시, import 경로 절대 경로
- **gRPC**: streaming vs unary 선택 근거, 에러 status code 의미론적 정확성
- **성능**: 대용량 repeated 필드 페이지네이션, `google.protobuf.Any` 타입 안전성
"""

COMPACT_KO = (
    "## Protobuf: 필드 번호 불변, reserved 보호, "
    "sint32 음수, 하위 호환 optional만 추가, gRPC status"
)

FULL_JA = """\
## Protocol Buffers レビュー基準
- **フィールド番号**: 既存番号の変更/再利用禁止 (後方互換性破壊)、`reserved` で削除済み番号を保護
- **型選択**: `int32` vs `sint32` (負数効率)、`bytes` vs `string` (UTF-8 保証)
- **後方互換**: フィールド追加は optional のみ、新規 `required` (proto2) 禁止、デフォルト値依存に注意
- **パッケージ**: `package` 名前空間を明示、import パスは絶対パス
- **gRPC**: streaming vs unary の選択根拠、エラー status code の意味的正確性
- **パフォーマンス**: 大量 repeated フィールドのページネーション、`google.protobuf.Any` の型安全性
"""

COMPACT_JA = (
    "## Protobuf: フィールド番号不変、reserved 保護、"
    "sint32 負数、互換は optional のみ、gRPC status"
)
