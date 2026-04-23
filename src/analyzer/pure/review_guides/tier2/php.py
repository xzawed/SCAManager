"""PHP review guide — Tier 2."""

FULL = """\
## PHP 검토 기준
- **보안**: SQL 문자열 포맷팅 금지 → PDO/MySQLi prepared statement, `htmlspecialchars()` XSS 방어
- **타입**: strict_types=1 선언, 타입 힌트 사용, `===` vs `==` 혼용 금지
- **에러**: `@` 에러 억제 연산자 금지, `try/catch`, error_reporting 설정
- **현대 PHP**: 화살표 함수, named arguments, union types(PHP 8.0+), match 표현식
- **의존성**: Composer autoload 활용, 전역 변수(`global`) 최소화
- **입력 검증**: `$_GET`/`$_POST`/`$_REQUEST` 직접 사용 금지 — 검증·sanitize 필수
"""

COMPACT = "## PHP: prepared statement, htmlspecialchars, strict_types=1, @ 연산자 금지, 입력 검증"
