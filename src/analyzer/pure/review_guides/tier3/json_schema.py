"""JSON Schema review guide — Tier 3.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## JSON Schema review checklist
- **Version**: Specify draft via `$schema` (`draft-07`, `2020-12`)
- **Type constraints**: Explicit `type`; strict `additionalProperties: false`; list `required` fields
- **Reuse**: Extract common schemas via `$defs` / `definitions`; watch `$ref` circular references
- **Validation**: Constrain with `minLength` / `maxLength` / `pattern` / `format`; allowed values via `enum` / `const`
- **Security**: Avoid overly permissive schemas (`{}` allows anything); validate inputs with `format: "uri"`
- **Documentation**: `title` / `description` required for public APIs; include `examples`
"""

COMPACT = "## JSON Schema: $schema version, additionalProperties:false, $defs reuse, required, format validation"

FULL_KO = """\
## JSON Schema 검토 기준
- **버전**: `$schema` 키워드로 draft 버전 명시(`draft-07`, `2020-12`)
- **타입 제약**: `type` 명시, `additionalProperties: false` 엄격 검증, `required` 필드 목록
- **재사용**: `$defs`/`definitions` 공통 스키마 추출, `$ref` 순환 참조 주의
- **검증**: `minLength`/`maxLength`/`pattern`/`format` 제약, `enum`/`const` 허용값
- **보안**: 과도하게 관대한 스키마(`{}` 전체 허용) 금지, `format: "uri"` 입력 검증
- **문서화**: `title`/`description` 필드 공개 API 필수, 예시(`examples`) 포함
"""

COMPACT_KO = "## JSON Schema: $schema 버전, additionalProperties:false, $defs 재사용, required 명시, format 검증"

FULL_JA = """\
## JSON Schema レビュー基準
- **バージョン**: `$schema` キーワードで draft バージョン明示 (`draft-07`、`2020-12`)
- **型制約**: `type` 明示、`additionalProperties: false` で厳密検証、`required` フィールドリスト
- **再利用**: `$defs` / `definitions` で共通スキーマ抽出、`$ref` 循環参照に注意
- **検証**: `minLength` / `maxLength` / `pattern` / `format` 制約、`enum` / `const` 許容値
- **セキュリティ**: 過度に寛容なスキーマ (`{}` 全許可) 禁止、`format: "uri"` で入力検証
- **文書化**: `title` / `description` フィールドは公開 API で必須、`examples` 含める
"""

COMPACT_JA = "## JSON Schema: $schema バージョン、additionalProperties:false、$defs 再利用、required、format 検証"
