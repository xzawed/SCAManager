"""Generic fallback review guide — used when language is undetected or has no specific guide.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Generic code review checklist
- **Readability**: Verify variables and function names clearly convey purpose
- **Error handling**: Verify exception/error paths are handled appropriately
- **Security**: External input validation, hardcoded secrets, missing permission checks
- **Duplication**: Extract repeated logic into functions/modules
- **Tests**: Verify tests exist for core logic
- **Dependencies**: Avoid adding unnecessary external dependencies
"""

COMPACT = "## Generic: clear naming, error handling, validate input, no hardcoded secrets, deduplicate"

FULL_KO = """\
## 일반 코드 검토 기준
- **가독성**: 변수·함수명이 목적을 명확히 전달하는지 확인
- **에러 처리**: 예외/에러 상황이 적절히 처리되는지 확인
- **보안**: 외부 입력 검증, 하드코딩 시크릿, 권한 검사 누락 여부
- **중복**: 동일 로직 반복 → 함수/모듈 추출 권장
- **테스트**: 핵심 로직에 대한 테스트 존재 여부
- **의존성**: 불필요한 외부 의존성 추가 여부
"""

COMPACT_KO = "## 일반: 명확한 명명, 에러 처리, 외부 입력 검증, 하드코딩 시크릿 금지, 중복 제거"

FULL_JA = """\
## 一般コードレビュー基準
- **可読性**: 変数・関数名が目的を明確に伝えるか確認
- **エラー処理**: 例外/エラー状況が適切に処理されているか確認
- **セキュリティ**: 外部入力検証、ハードコードされたシークレット、権限チェック漏れ
- **重複**: 同一ロジックの繰り返し → 関数/モジュール抽出推奨
- **テスト**: コアロジックに対するテストの存在確認
- **依存**: 不要な外部依存追加の有無
"""

COMPACT_JA = "## 一般: 明確な命名、エラー処理、外部入力検証、ハードコードシークレット禁止、重複排除"
