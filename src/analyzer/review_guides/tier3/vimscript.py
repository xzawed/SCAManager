"""Vimscript review guide — Tier 3."""

FULL = """\
## Vimscript 검토 기준
- **범위**: `s:` 스크립트 로컬, `g:` 전역, `l:` 함수 로컬 변수 명시
- **함수**: `function!`(재정의), `abort` 플래그(에러 시 중단), 네임스페이스 접두사
- **자동완성**: `setlocal` vs `set` 구분, 플러그인 옵션 충돌 방지
- **성능**: 느린 `system()` 최소화, `has('nvim')` 조건부 코드, 정규식 컴파일(`\\V`)
- **Neovim**: `vim.api`/`vim.fn` Lua 마이그레이션 고려, `autoload` 지연 로딩
"""

COMPACT = "## Vimscript: s:/g:/l: 범위, function! abort, setlocal vs set, autoload 지연 로딩"
