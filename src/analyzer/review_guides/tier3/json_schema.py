"""JSON Schema review guide — Tier 3."""

FULL = """\
## JSON Schema 검토 기준
- **버전**: `$schema` 키워드로 draft 버전 명시(`draft-07`, `2020-12`)
- **타입 제약**: `type` 명시, `additionalProperties: false` 엄격 검증, `required` 필드 목록
- **재사용**: `$defs`/`definitions` 공통 스키마 추출, `$ref` 순환 참조 주의
- **검증**: `minLength`/`maxLength`/`pattern`/`format` 제약, `enum`/`const` 허용값
- **보안**: 과도하게 관대한 스키마(`{}` 전체 허용) 금지, `format: "uri"` 입력 검증
- **문서화**: `title`/`description` 필드 공개 API 필수, 예시(`examples`) 포함
"""

COMPACT = "## JSON Schema: $schema 버전, additionalProperties:false, $defs 재사용, required 명시, format 검증"
