"""Makefile review guide — Tier 3."""

FULL = """\
## Makefile 검토 기준
- **PHONY**: `.PHONY: clean test build` — 파일명과 충돌 방지 필수
- **변수**: `$(VAR)` 참조, `:=` 즉시 확장 vs `=` 지연 확장 구분
- **에러**: 명령 앞 `-` 에러 무시 남용 주의, `set -e` 셸 스크립트와 차이
- **이식성**: `bash` 특정 문법 회피(`SHELL := /bin/bash` 명시 필요), tab vs space
- **의존성**: 타겟 의존성 정확성(빌드 순서), 자동 변수(`$@`, `$<`, `$^`) 활용
- **병렬화**: `-j` 플래그 호환성, 순서 의존성 명시(`order-only prerequisites`)
"""

COMPACT = "## Makefile: .PHONY 필수, := vs = 구분, tab 들여쓰기, 자동변수 $@/$<, -j 병렬화 호환"
