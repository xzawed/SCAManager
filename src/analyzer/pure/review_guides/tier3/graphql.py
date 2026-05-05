"""GraphQL review guide — Tier 3.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## GraphQL review checklist
- **Schema design**: Noun-style type names; appropriate `!` non-null; distinguish Input vs Object types
- **N+1**: Required DataLoader pattern; avoid direct DB N+1 inside resolvers
- **Security**: Limit query depth; limit query complexity; disable introspection in production
- **Pagination**: Cursor-based (`edges/node/pageInfo`) vs offset; `first` / `after` args
- **Errors**: Consistent `errors` array vs `null` returns; don't expose sensitive info in error messages
- **Mutations**: Consider idempotency; validate input types; include sufficient info in return types
"""

COMPACT = "## GraphQL: DataLoader N+1, depth/complexity limits, prod introspection off, cursor pagination"

FULL_KO = """\
## GraphQL 검토 기준
- **스키마 설계**: 명사 타입 명명, `!` non-null 적절성, Input vs Object 타입 구분
- **N+1**: DataLoader 패턴 필수, Resolver 내 DB 직접 N+1 조회 방지
- **보안**: 쿼리 깊이 제한, 쿼리 복잡도 제한, introspection 프로덕션 비활성화
- **페이지네이션**: Cursor 기반(`edges/node/pageInfo`) vs offset 선택, `first`/`after` 인수
- **에러**: `errors` 배열 vs `null` 반환 일관성, 민감 정보 에러 메시지 노출 금지
- **Mutation**: 멱등성 고려, 입력 타입 검증, 반환 타입 충분한 정보 포함
"""

COMPACT_KO = "## GraphQL: DataLoader N+1, 쿼리 깊이/복잡도 제한, introspection 프로덕션 비활성, cursor 페이지네이션"

FULL_JA = """\
## GraphQL レビュー基準
- **スキーマ設計**: 名詞型の命名、`!` non-null の適切性、Input vs Object 型の区別
- **N+1**: DataLoader パターン必須、Resolver 内の DB 直接 N+1 クエリ防止
- **セキュリティ**: クエリ深さ制限、クエリ複雑度制限、本番で introspection 無効化
- **ページネーション**: Cursor ベース (`edges/node/pageInfo`) vs offset 選択、`first` / `after` 引数
- **エラー**: `errors` 配列 vs `null` 戻り値の一貫性、エラーメッセージへの機密情報露出禁止
- **Mutation**: 冪等性を考慮、入力型検証、戻り型に十分な情報を含める
"""

COMPACT_JA = "## GraphQL: DataLoader N+1、深さ/複雑度制限、本番 introspection オフ、cursor ページネーション"
