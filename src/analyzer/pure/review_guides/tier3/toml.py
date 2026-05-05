"""TOML review guide — Tier 3.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## TOML review checklist
- **Types**: String quotes `"..."`, literal strings `'...'` (no escapes), ISO 8601 dates
- **pyproject.toml**: Complete `[project]` (name/version/dependencies/requires-python); separate `[tool.XX]` config
- **Cargo.toml**: Dependency version ranges (`^1.0`, `~1.0.3`); separate `[dev-dependencies]`; clear features
- **Duplicate keys**: Forbidden within a table (parser error); `[[array]]` table order matters
- **Inline tables**: One line (`{key = "value"}`) — prefer standard tables when complex
"""

COMPACT = "## TOML: type literals, pyproject required fields, Cargo version ranges, no duplicate keys, inline tables"

FULL_KO = """\
## TOML 검토 기준
- **타입**: 문자열 따옴표 `"..."`, 리터럴 문자열 `'...'`(이스케이프 없음), 날짜 ISO 8601
- **pyproject.toml**: `[project]` 필드 완성도(name/version/dependencies/requires-python), `[tool.XX]` 설정 분리
- **Cargo.toml**: 의존성 버전 범위(`^1.0`, `~1.0.3`), `[dev-dependencies]` 분리, features 명확성
- **중복 키**: 동일 테이블 내 중복 키 금지(파서 에러), `[[array]]` 배열 테이블 순서
- **인라인 테이블**: 한 줄(`{key = "value"}`) — 복잡하면 표준 테이블 선호
"""

COMPACT_KO = "## TOML: 타입 리터럴, pyproject 필수 필드, Cargo 버전 범위, 중복 키 금지, 인라인 테이블 최소화"

FULL_JA = """\
## TOML レビュー基準
- **型**: 文字列クォート `"..."`、リテラル文字列 `'...'` (エスケープなし)、ISO 8601 日付
- **pyproject.toml**: `[project]` フィールド完成度 (name/version/dependencies/requires-python)、`[tool.XX]` 設定分離
- **Cargo.toml**: 依存バージョン範囲 (`^1.0`、`~1.0.3`)、`[dev-dependencies]` 分離、features 明確性
- **重複キー**: 同一テーブル内の重複キー禁止 (パーサーエラー)、`[[array]]` 配列テーブル順序
- **インラインテーブル**: 1 行 (`{key = "value"}`) — 複雑な場合は標準テーブル推奨
"""

COMPACT_JA = "## TOML: 型リテラル、pyproject 必須フィールド、Cargo バージョン範囲、重複キー禁止、インラインテーブル最小化"
