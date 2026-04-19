"""Ruby review guide — Tier 1 deep checklist."""

FULL = """\
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

COMPACT = "## Ruby: snake_case, safe navigation(&.), N+1 includes, rescue Exception 금지, eval 금지"
