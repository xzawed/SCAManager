"""Shell/Bash review guide — Tier 2.

Phase 4 PR-14 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Shell review checklist
- **Safety options**: `set -euo pipefail` at top of script — without it, errors are silently ignored
- **Variables**: Always quote `"${VAR}"`; whitespace/glob-safe; default with `${VAR:-default}`
- **Command injection**: No `eval` or `bash -c "$(user_input)"`; separate external input with `--`
- **Arrays**: Use arrays for paths with spaces (`cmd "${args[@]}"`); avoid word-splitting
- **Compatibility**: `#!/bin/bash` vs `#!/bin/sh` matters; verify bash-only syntax (`[[ ]]`, arrays)
- **Temp files**: Use `mktemp`; clean up with trap (`trap 'rm -f "$tmp"' EXIT`)
- **Error handling**: Check results in `||` / `&&` chains; subshell error propagation (`set -e` limitations)
"""

COMPACT = "## Shell: set -euo pipefail, quote variables, no eval, mktemp+trap, prevent injection"

FULL_KO = """\
## Shell 검토 기준
- **안전 옵션**: 스크립트 상단 `set -euo pipefail` 필수 — 미설정 시 에러 무시
- **변수**: 변수 항상 `"${VAR}"` 쌍따옴표 감싸기, 공백·glob 안전, `${VAR:-default}` 기본값
- **명령 주입**: `eval` / `bash -c "$(사용자 입력)"` 금지, 외부 입력은 `--` 로 분리
- **배열**: 공백 포함 경로는 배열 사용(`cmd "${args[@]}"`), word splitting 위험
- **호환성**: `#!/bin/bash` vs `#!/bin/sh` 구분, bash 전용 문법 확인(`[[ ]]`, 배열)
- **임시 파일**: `mktemp` 사용, trap으로 정리(`trap 'rm -f "$tmp"' EXIT`)
- **에러 처리**: `||` / `&&` 체인 결과 확인, 서브쉘 에러 전파(`set -e` 제한사항)
"""

COMPACT_KO = "## Shell: set -euo pipefail, 변수 쌍따옴표, eval 금지, mktemp+trap, 명령 주입 방지"

FULL_JA = """\
## Shell レビュー基準
- **安全オプション**: スクリプト先頭で `set -euo pipefail` 必須 — 未設定だとエラーが無視される
- **変数**: 変数は常に `"${VAR}"` でクォート、空白/glob 安全、`${VAR:-default}` デフォルト値
- **コマンド注入**: `eval` / `bash -c "$(user_input)"` 禁止、外部入力は `--` で分離
- **配列**: 空白を含むパスには配列を使用 (`cmd "${args[@]}"`)、word splitting に注意
- **互換性**: `#!/bin/bash` vs `#!/bin/sh` 区別、bash 専用構文確認 (`[[ ]]`、配列)
- **一時ファイル**: `mktemp` 使用、trap で後始末 (`trap 'rm -f "$tmp"' EXIT`)
- **エラー処理**: `||` / `&&` チェーンの結果確認、サブシェルのエラー伝播 (`set -e` 制限)
"""

COMPACT_JA = "## Shell: set -euo pipefail、変数クォート、eval 禁止、mktemp+trap、コマンド注入防止"
