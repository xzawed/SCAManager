"""TOML review guide — Tier 3."""

FULL = """\
## TOML 검토 기준
- **타입**: 문자열 따옴표 `"..."`, 리터럴 문자열 `'...'`(이스케이프 없음), 날짜 ISO 8601
- **pyproject.toml**: `[project]` 필드 완성도(name/version/dependencies/requires-python), `[tool.XX]` 설정 분리
- **Cargo.toml**: 의존성 버전 범위(`^1.0`, `~1.0.3`), `[dev-dependencies]` 분리, features 명확성
- **중복 키**: 동일 테이블 내 중복 키 금지(파서 에러), `[[array]]` 배열 테이블 순서
- **인라인 테이블**: 한 줄(`{key = "value"}`) — 복잡하면 표준 테이블 선호
"""

COMPACT = "## TOML: 타입 리터럴, pyproject 필수 필드, Cargo 버전 범위, 중복 키 금지, 인라인 테이블 최소화"
