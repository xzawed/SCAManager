"""Shell/Bash review guide — Tier 2."""

FULL = """\
## Shell 검토 기준
- **안전 옵션**: 스크립트 상단 `set -euo pipefail` 필수 — 미설정 시 에러 무시
- **변수**: 변수 항상 `"${VAR}"` 쌍따옴표 감싸기, 공백·glob 안전, `${VAR:-default}` 기본값
- **명령 주입**: `eval` / `bash -c "$(사용자 입력)"` 금지, 외부 입력은 `--` 로 분리
- **배열**: 공백 포함 경로는 배열 사용(`cmd "${args[@]}"`), word splitting 위험
- **호환성**: `#!/bin/bash` vs `#!/bin/sh` 구분, bash 전용 문법 확인(`[[ ]]`, 배열)
- **임시 파일**: `mktemp` 사용, trap으로 정리(`trap 'rm -f "$tmp"' EXIT`)
- **에러 처리**: `||` / `&&` 체인 결과 확인, 서브쉘 에러 전파(`set -e` 제한사항)
"""

COMPACT = "## Shell: set -euo pipefail, 변수 쌍따옴표, eval 금지, mktemp+trap, 명령 주입 방지"
