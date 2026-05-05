"""Ruby review guide — Tier 1 deep checklist.

Phase 4 PR-13 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Ruby review checklist
- **Style**: snake_case methods/variables, PascalCase classes, 2-space indentation (no tabs)
- **Methods**: Aim for ≤10 lines per method; explicit returns are encouraged for complex flows (otherwise `return` may be omitted)
- **Nil safety**: Use `&.` (safe navigation); distinguish `nil?` vs `empty?` vs `blank?`
- **Blocks**: Consistent `do...end` (multi-line) vs `{...}` (single-line); pick `yield` vs `Proc.new` carefully
- **ActiveRecord**: Avoid N+1 (`includes` / `eager_load`); no raw SQL `where("#{user_input}")`
- **Exceptions**: Avoid `rescue Exception` (use `rescue StandardError`); release resources in `ensure`
- **Security**: No `eval`; validate inputs to `system()` / `exec()`; allowlist `send()` calls
- **Tests**: RSpec `describe` / `context` / `it` nesting depth; FactoryBot vs fixture choice
"""

COMPACT = "## Ruby: snake_case, safe navigation(&.), N+1 includes, no rescue Exception, no eval"

FULL_KO = """\
## Ruby 검토 기준
- **스타일**: snake_case 메서드/변수, PascalCase 클래스, 2칸 들여쓰기(탭 금지)
- **메서드**: 메서드 길이 10줄 이하 권장, 반환값 명시(`return` 생략 가능하나 복잡한 경우 명시)
- **nil 안전**: `&.`(safe navigation) 활용, `nil?` vs `empty?` vs `blank?` 구분
- **블록**: `do...end`(멀티라인) vs `{...}`(단일라인) 일관성, `yield` vs `Proc.new` 선택
- **ActiveRecord**: N+1 쿼리(`includes`/`eager_load`), raw SQL `where("#{user_input}")` 금지
- **예외**: `rescue Exception` 금지(→ `rescue StandardError`), `ensure` 리소스 해제
- **보안**: `eval` 금지, `system()`/`exec()` 입력 검증, `send()` 화이트리스트 검사
- **테스트**: RSpec `describe`/`context`/`it` 중첩 적절성, FactoryBot vs fixture 선택
"""

COMPACT_KO = "## Ruby: snake_case, safe navigation(&.), N+1 includes, rescue Exception 금지, eval 금지"

FULL_JA = """\
## Ruby レビュー基準
- **スタイル**: snake_case メソッド/変数、PascalCase クラス、2 スペースインデント (タブ禁止)
- **メソッド**: メソッド長 10 行以下推奨、戻り値を明示 (`return` 省略可だが複雑な場合は明示)
- **nil 安全**: `&.` (safe navigation) 活用、`nil?` vs `empty?` vs `blank?` 区別
- **ブロック**: `do...end` (複数行) vs `{...}` (単一行) の一貫性、`yield` vs `Proc.new` の選択
- **ActiveRecord**: N+1 クエリ (`includes` / `eager_load`)、raw SQL `where("#{user_input}")` 禁止
- **例外**: `rescue Exception` 禁止 (→ `rescue StandardError`)、`ensure` でリソース解放
- **セキュリティ**: `eval` 禁止、`system()` / `exec()` の入力検証、`send()` ホワイトリスト確認
- **テスト**: RSpec `describe` / `context` / `it` のネスト適切性、FactoryBot vs fixture の選択
"""

COMPACT_JA = "## Ruby: snake_case、safe navigation (&.)、N+1 includes、rescue Exception 禁止、eval 禁止"
