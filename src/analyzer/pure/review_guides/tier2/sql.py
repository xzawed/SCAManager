"""SQL review guide — Tier 2.

Phase 4 PR-14 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## SQL review checklist
- **Security**: Use parameterized queries — no string formatting for query composition (SQL Injection)
- **Performance**: No `SELECT *` → only needed columns; avoid N+1 (`JOIN` or subquery); verify index usage
- **Transactions**: Keep transactions short; pick appropriate isolation; ensure ROLLBACK paths
- **NULL**: Use `IS NULL` / `IS NOT NULL`; null-safe aggregates (`COALESCE`)
- **Naming**: snake_case for tables/columns; avoid reserved words (`date`, `user`, `order`)
- **Migrations**: Prefer non-destructive changes (ADD before DROP); prepare rollback SQL
- **Indexes**: Don't miss FK column indexes; avoid wasteful indexes on low-cardinality columns
"""

COMPACT = "## SQL: parameterized queries, no SELECT *, IS NULL, FK indexes, non-destructive migrations"

FULL_KO = """\
## SQL 검토 기준
- **보안**: 파라미터화 쿼리 사용 — 문자열 포맷팅으로 쿼리 조합 금지(SQL Injection)
- **성능**: `SELECT *` 금지 → 필요 컬럼만, N+1 방지(`JOIN` 또는 subquery), 인덱스 활용 확인
- **트랜잭션**: 긴 트랜잭션 최소화, 적절한 격리 수준 선택, ROLLBACK 경로 보장
- **NULL**: `NULL` 비교는 `IS NULL`/`IS NOT NULL`, NULL-safe 집계 함수(`COALESCE`)
- **명명**: 테이블·컬럼 snake_case, 예약어 컬럼명 금지(`date`, `user`, `order`)
- **마이그레이션**: 비파괴적 변경 선호(ADD COLUMN before DROP COLUMN), 롤백 SQL 준비
- **인덱스**: FK 컬럼 인덱스 누락, 카디널리티 낮은 컬럼 인덱스 낭비
"""

COMPACT_KO = "## SQL: 파라미터화 쿼리, SELECT * 금지, NULL IS NULL, FK 인덱스, 비파괴적 마이그레이션"

FULL_JA = """\
## SQL レビュー基準
- **セキュリティ**: パラメータ化クエリ使用 — 文字列フォーマットでのクエリ組み立て禁止 (SQL Injection)
- **パフォーマンス**: `SELECT *` 禁止 → 必要な列のみ、N+1 防止 (`JOIN` または subquery)、インデックス活用確認
- **トランザクション**: 長いトランザクションを最小化、適切な分離レベル選択、ROLLBACK 経路保証
- **NULL**: `NULL` 比較は `IS NULL` / `IS NOT NULL`、NULL-safe 集約関数 (`COALESCE`)
- **命名**: テーブル・カラムは snake_case、予約語のカラム名禁止 (`date`、`user`、`order`)
- **マイグレーション**: 非破壊的変更を推奨 (ADD COLUMN before DROP COLUMN)、ロールバック SQL 準備
- **インデックス**: FK カラムのインデックス漏れ、カーディナリティの低いカラムへの無駄なインデックス
"""

COMPACT_JA = "## SQL: パラメータ化クエリ、SELECT * 禁止、IS NULL、FK インデックス、非破壊マイグレーション"
