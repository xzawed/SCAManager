"""Makefile review guide — Tier 3.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Makefile review checklist
- **PHONY**: `.PHONY: clean test build` — required to avoid file-name conflicts
- **Variables**: `$(VAR)` reference; distinguish `:=` immediate vs `=` deferred expansion
- **Errors**: Cautious use of `-` to ignore errors; differs from `set -e` shell semantics
- **Portability**: Avoid bash-specific syntax (`SHELL := /bin/bash` if needed); tabs vs spaces
- **Dependencies**: Accurate target dependencies (build order); use automatic variables (`$@`, `$<`, `$^`)
- **Parallel**: `-j` flag compatibility; explicit `order-only prerequisites` when needed
"""

COMPACT = "## Makefile: .PHONY required, := vs =, tab indent, automatic vars $@/$<, -j parallel compat"

FULL_KO = """\
## Makefile 검토 기준
- **PHONY**: `.PHONY: clean test build` — 파일명과 충돌 방지 필수
- **변수**: `$(VAR)` 참조, `:=` 즉시 확장 vs `=` 지연 확장 구분
- **에러**: 명령 앞 `-` 에러 무시 남용 주의, `set -e` 셸 스크립트와 차이
- **이식성**: `bash` 특정 문법 회피(`SHELL := /bin/bash` 명시 필요), tab vs space
- **의존성**: 타겟 의존성 정확성(빌드 순서), 자동 변수(`$@`, `$<`, `$^`) 활용
- **병렬화**: `-j` 플래그 호환성, 순서 의존성 명시(`order-only prerequisites`)
"""

COMPACT_KO = "## Makefile: .PHONY 필수, := vs = 구분, tab 들여쓰기, 자동변수 $@/$<, -j 병렬화 호환"

FULL_JA = """\
## Makefile レビュー基準
- **PHONY**: `.PHONY: clean test build` — ファイル名との競合防止に必須
- **変数**: `$(VAR)` 参照、`:=` 即時展開 vs `=` 遅延展開を区別
- **エラー**: コマンド前の `-` でのエラー無視を濫用しない、`set -e` シェルとは異なる
- **可搬性**: bash 特有構文を回避 (`SHELL := /bin/bash` を明示)、tab vs space
- **依存**: ターゲット依存の正確性 (ビルド順)、自動変数 (`$@`、`$<`、`$^`) 活用
- **並列化**: `-j` フラグ互換性、順序依存を明示 (`order-only prerequisites`)
"""

COMPACT_JA = "## Makefile: .PHONY 必須、:= vs = 区別、tab インデント、自動変数 $@/$<、-j 並列互換"
