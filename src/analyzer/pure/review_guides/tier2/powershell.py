"""PowerShell review guide — Tier 2.

Phase 4 PR-14 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## PowerShell review checklist
- **Error handling**: `$ErrorActionPreference = 'Stop'`, `try/catch/finally`, `trap`
- **Variables**: Type hints (`[string]$Name`), `Set-StrictMode -Version Latest`
- **Security**: No `Invoke-Expression`; `ConvertTo-SecureString` for credentials; `ExecutionPolicy`
- **Pipeline**: Support pipeline input (`ValueFromPipeline`); avoid unnecessary `ForEach-Object` vs `foreach`
- **Output**: Distinguish `Write-Verbose` / `Write-Debug` vs `Write-Host`; explicit `return`
- **Modules**: `#Requires -Modules`, explicit `Export-ModuleMember`, approved verbs
"""

COMPACT = "## PowerShell: ErrorActionPreference=Stop, no Invoke-Expression, SecureString, Set-StrictMode"

FULL_KO = """\
## PowerShell 검토 기준
- **에러 처리**: `$ErrorActionPreference = 'Stop'`, `try/catch/finally`, `trap`
- **변수**: 타입 힌트(`[string]$Name`), `Set-StrictMode -Version Latest`
- **보안**: `Invoke-Expression` 금지, `ConvertTo-SecureString` 자격증명, `ExecutionPolicy`
- **파이프라인**: 파이프라인 입력 지원(`ValueFromPipeline`), 불필요한 `ForEach-Object` vs `foreach`
- **출력**: `Write-Verbose`/`Write-Debug` vs `Write-Host` 구분, `return` 명시
- **모듈**: `#Requires -Modules`, Export 함수 명시(`Export-ModuleMember`), 승인된 동사
"""

COMPACT_KO = "## PowerShell: ErrorActionPreference=Stop, Invoke-Expression 금지, SecureString, Set-StrictMode"

FULL_JA = """\
## PowerShell レビュー基準
- **エラー処理**: `$ErrorActionPreference = 'Stop'`、`try/catch/finally`、`trap`
- **変数**: 型ヒント (`[string]$Name`)、`Set-StrictMode -Version Latest`
- **セキュリティ**: `Invoke-Expression` 禁止、認証情報に `ConvertTo-SecureString`、`ExecutionPolicy`
- **パイプライン**: パイプライン入力サポート (`ValueFromPipeline`)、不要な `ForEach-Object` vs `foreach`
- **出力**: `Write-Verbose` / `Write-Debug` vs `Write-Host` 区別、`return` 明示
- **モジュール**: `#Requires -Modules`、`Export-ModuleMember` で Export 明示、承認済み動詞
"""

COMPACT_JA = "## PowerShell: ErrorActionPreference=Stop、Invoke-Expression 禁止、SecureString、Set-StrictMode"
