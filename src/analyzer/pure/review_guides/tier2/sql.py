"""SQL review guide — Tier 2."""

FULL = """\
## SQL 검토 기준
- **보안**: 파라미터화 쿼리 사용 — 문자열 포맷팅으로 쿼리 조합 금지(SQL Injection)
- **성능**: `SELECT *` 금지 → 필요 컬럼만, N+1 방지(`JOIN` 또는 subquery), 인덱스 활용 확인
- **트랜잭션**: 긴 트랜잭션 최소화, 적절한 격리 수준 선택, ROLLBACK 경로 보장
- **NULL**: `NULL` 비교는 `IS NULL`/`IS NOT NULL`, NULL-safe 집계 함수(`COALESCE`)
- **명명**: 테이블·컬럼 snake_case, 예약어 컬럼명 금지(`date`, `user`, `order`)
- **마이그레이션**: 비파괴적 변경 선호(ADD COLUMN before DROP COLUMN), 롤백 SQL 준비
- **인덱스**: FK 컬럼 인덱스 누락, 카디널리티 낮은 컬럼 인덱스 낭비
"""

COMPACT = "## SQL: 파라미터화 쿼리, SELECT * 금지, NULL IS NULL, FK 인덱스, 비파괴적 마이그레이션"
