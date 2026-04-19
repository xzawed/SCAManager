"""GraphQL review guide — Tier 3."""

FULL = """\
## GraphQL 검토 기준
- **스키마 설계**: 명사 타입 명명, `!` non-null 적절성, Input vs Object 타입 구분
- **N+1**: DataLoader 패턴 필수, Resolver 내 DB 직접 N+1 조회 방지
- **보안**: 쿼리 깊이 제한, 쿼리 복잡도 제한, introspection 프로덕션 비활성화
- **페이지네이션**: Cursor 기반(`edges/node/pageInfo`) vs offset 선택, `first`/`after` 인수
- **에러**: `errors` 배열 vs `null` 반환 일관성, 민감 정보 에러 메시지 노출 금지
- **Mutation**: 멱등성 고려, 입력 타입 검증, 반환 타입 충분한 정보 포함
"""

COMPACT = "## GraphQL: DataLoader N+1, 쿼리 깊이/복잡도 제한, introspection 프로덕션 비활성, cursor 페이지네이션"
