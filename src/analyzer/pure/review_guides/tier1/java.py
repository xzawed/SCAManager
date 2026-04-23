"""Java review guide — Tier 1 deep checklist."""

FULL = """\
## Java 검토 기준
- **네이밍**: PascalCase 클래스, camelCase 메서드/변수, UPPER_SNAKE 상수
- **null 안전**: `Optional<T>` 활용, `NullPointerException` 방지 — null 반환 대신 Optional 반환
- **예외**: checked exception 남발 금지, `Exception` 직접 catch 시 로그+재던지기
- **컬렉션**: raw type(`List` without generic) 금지, `Collections.unmodifiableList()` 불변 보장
- **동시성**: `synchronized` 범위 최소화, `volatile`/`AtomicXxx` 적절성, ThreadLocal 누수
- **스트림**: Stream API 과도한 체인으로 가독성 저하 시 분리, `collect(Collectors.toList())` → `toList()`(Java 16+)
- **보안**: SQL 문자열 포맷팅 금지 → PreparedStatement, `Runtime.exec()` 입력 검증
- **의존성**: 순환 의존성, 클래스 단일 책임 원칙(SRP) 위반 여부
"""

COMPACT = "## Java: Optional 활용, raw type 금지, checked exception 최소화, PreparedStatement, 순환 의존성"
