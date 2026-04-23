"""PowerShell review guide — Tier 2."""

FULL = """\
## PowerShell 검토 기준
- **에러 처리**: `$ErrorActionPreference = 'Stop'`, `try/catch/finally`, `trap`
- **변수**: 타입 힌트(`[string]$Name`), `Set-StrictMode -Version Latest`
- **보안**: `Invoke-Expression` 금지, `ConvertTo-SecureString` 자격증명, `ExecutionPolicy`
- **파이프라인**: 파이프라인 입력 지원(`ValueFromPipeline`), 불필요한 `ForEach-Object` vs `foreach`
- **출력**: `Write-Verbose`/`Write-Debug` vs `Write-Host` 구분, `return` 명시
- **모듈**: `#Requires -Modules`, Export 함수 명시(`Export-ModuleMember`), 승인된 동사
"""

COMPACT = "## PowerShell: ErrorActionPreference=Stop, Invoke-Expression 금지, SecureString, Set-StrictMode"
