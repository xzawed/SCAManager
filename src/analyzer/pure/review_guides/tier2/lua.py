"""Lua review guide — Tier 2.

Phase 4 PR-14 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Lua review checklist
- **Globals**: Always declare `local` — global leakage hurts debugging and performance
- **nil checks**: Validate function argument nils; check table key existence before access
- **Error handling**: Wrap with `pcall` / `xpcall`; consistent error object types
- **Tables**: Arrays (1-indexed); careful when mixing with dicts; `#` length operator only reliable on sequences
- **Modules**: `return M` pattern; cache `require` results locally; watch for circular require
- **Performance**: Avoid string concat in loops (`..`) → `table.concat`; minimize repeated closure creation
- **Nginx/OpenResty**: cosocket non-blocking; shared dict races; phase restrictions
"""

COMPACT = "## Lua: local required, pcall error handling, # only sequences, table.concat, cache require"

FULL_KO = """\
## Lua 검토 기준
- **전역 변수**: `local` 선언 필수 — 전역 누출은 디버깅 어렵고 성능 저하
- **nil 체크**: 함수 인자 nil 검증, table 키 접근 전 존재 여부 확인
- **에러 처리**: `pcall`/`xpcall` 감싸기, 에러 객체 타입 일관성
- **테이블**: 배열(1-indexed), 딕셔너리 혼용 주의, `#` 길이 연산자는 시퀀스에만 신뢰
- **모듈**: `return M` 패턴, `require` 결과 로컬 캐싱, 순환 require 위험
- **성능**: 문자열 연결 루프(`..`) → `table.concat`, 클로저 생성 반복 최소화
- **Nginx/OpenResty**: cosocket non-blocking, shared dict 경쟁 조건, phase 제약
"""

COMPACT_KO = "## Lua: local 선언 필수, pcall 에러 처리, #은 시퀀스만, table.concat, require 캐싱"

FULL_JA = """\
## Lua レビュー基準
- **グローバル変数**: `local` 宣言必須 — グローバル漏れはデバッグ困難・パフォーマンス低下
- **nil チェック**: 関数引数の nil 検証、table キーアクセス前に存在確認
- **エラー処理**: `pcall` / `xpcall` でラップ、エラーオブジェクトの型を一貫化
- **テーブル**: 配列 (1-indexed)、辞書混用に注意、`#` 長さ演算子はシーケンスのみ信頼
- **モジュール**: `return M` パターン、`require` 結果のローカルキャッシュ、循環 require に注意
- **パフォーマンス**: ループ内文字列連結 (`..`) → `table.concat`、クロージャの繰り返し生成を最小化
- **Nginx/OpenResty**: cosocket non-blocking、shared dict の競合、phase 制約
"""

COMPACT_JA = "## Lua: local 必須、pcall エラー処理、# はシーケンスのみ、table.concat、require キャッシュ"
