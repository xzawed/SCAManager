"""Vimscript review guide — Tier 3.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Vimscript review checklist
- **Scope**: Mark `s:` script-local, `g:` global, `l:` function-local variables
- **Functions**: `function!` (redefine), `abort` flag (stop on error), namespace prefixes
- **Autocomplete**: Distinguish `setlocal` vs `set`; prevent plugin option conflicts
- **Performance**: Minimize slow `system()`; conditional `has('nvim')` code; regex compile (`\\V`)
- **Neovim**: Consider migration to `vim.api` / `vim.fn` Lua; `autoload` lazy loading
"""

COMPACT = "## Vimscript: s:/g:/l: scope, function! abort, setlocal vs set, autoload lazy"

FULL_KO = """\
## Vimscript 검토 기준
- **범위**: `s:` 스크립트 로컬, `g:` 전역, `l:` 함수 로컬 변수 명시
- **함수**: `function!`(재정의), `abort` 플래그(에러 시 중단), 네임스페이스 접두사
- **자동완성**: `setlocal` vs `set` 구분, 플러그인 옵션 충돌 방지
- **성능**: 느린 `system()` 최소화, `has('nvim')` 조건부 코드, 정규식 컴파일(`\\V`)
- **Neovim**: `vim.api`/`vim.fn` Lua 마이그레이션 고려, `autoload` 지연 로딩
"""

COMPACT_KO = "## Vimscript: s:/g:/l: 범위, function! abort, setlocal vs set, autoload 지연 로딩"

FULL_JA = """\
## Vimscript レビュー基準
- **スコープ**: `s:` スクリプトローカル、`g:` グローバル、`l:` 関数ローカル変数を明示
- **関数**: `function!` (再定義)、`abort` フラグ (エラー時停止)、名前空間プレフィックス
- **オートコンプリート**: `setlocal` vs `set` の区別、プラグインオプション衝突防止
- **パフォーマンス**: 遅い `system()` を最小化、`has('nvim')` 条件付きコード、正規表現コンパイル (`\\V`)
- **Neovim**: `vim.api` / `vim.fn` Lua への移行検討、`autoload` 遅延ロード
"""

COMPACT_JA = "## Vimscript: s:/g:/l: スコープ、function! abort、setlocal vs set、autoload 遅延"
