"""PHP review guide — Tier 2.

Phase 4 PR-14 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## PHP review checklist
- **Security**: No SQL string formatting → PDO/MySQLi prepared statements; `htmlspecialchars()` for XSS
- **Types**: `declare(strict_types=1)`; type hints; no `===` vs `==` mixing
- **Errors**: No `@` error suppression; use `try/catch`; configure `error_reporting`
- **Modern PHP**: Arrow functions, named arguments, union types (PHP 8.0+), `match` expressions
- **Dependencies**: Use Composer autoload; minimize `global` variables
- **Input validation**: No direct use of `$_GET` / `$_POST` / `$_REQUEST` — validate and sanitize
"""

COMPACT = "## PHP: prepared statements, htmlspecialchars, strict_types=1, no @, validate input"

FULL_KO = """\
## PHP 검토 기준
- **보안**: SQL 문자열 포맷팅 금지 → PDO/MySQLi prepared statement, `htmlspecialchars()` XSS 방어
- **타입**: strict_types=1 선언, 타입 힌트 사용, `===` vs `==` 혼용 금지
- **에러**: `@` 에러 억제 연산자 금지, `try/catch`, error_reporting 설정
- **현대 PHP**: 화살표 함수, named arguments, union types(PHP 8.0+), match 표현식
- **의존성**: Composer autoload 활용, 전역 변수(`global`) 최소화
- **입력 검증**: `$_GET`/`$_POST`/`$_REQUEST` 직접 사용 금지 — 검증·sanitize 필수
"""

COMPACT_KO = "## PHP: prepared statement, htmlspecialchars, strict_types=1, @ 연산자 금지, 입력 검증"

FULL_JA = """\
## PHP レビュー基準
- **セキュリティ**: SQL 文字列フォーマット禁止 → PDO/MySQLi prepared statement、`htmlspecialchars()` で XSS 防御
- **型**: `declare(strict_types=1)`、型ヒント使用、`===` vs `==` 混用禁止
- **エラー**: `@` エラー抑制演算子禁止、`try/catch`、`error_reporting` 設定
- **モダン PHP**: アロー関数、named arguments、union types (PHP 8.0+)、match 式
- **依存**: Composer autoload 活用、グローバル変数 (`global`) を最小化
- **入力検証**: `$_GET` / `$_POST` / `$_REQUEST` 直接使用禁止 — 検証・sanitize 必須
"""

COMPACT_JA = "## PHP: prepared statement、htmlspecialchars、strict_types=1、@ 禁止、入力検証"
