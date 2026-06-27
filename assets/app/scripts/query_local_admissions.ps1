param(
    [Parameter(Mandatory=$true)][string]$Province,
    [Parameter(Mandatory=$true)][string]$Subject,
    [int]$Score = 0,
    [int]$Rank = 0,
    [string[]]$Major = @(),
    [string[]]$ExcludeMajor = @(),
    [string[]]$Region = @(),
    [string]$Goal = "",
    [int]$Limit = 30
)

$ErrorActionPreference = "Stop"

function Get-AppRoot {
    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
}

$appRoot = Get-AppRoot
$scriptPath = Join-Path $PSScriptRoot "query_local_admissions.py"
$arguments = @(
    $scriptPath,
    "--province", $Province,
    "--subject", $Subject,
    "--limit", [string]$Limit
)

if ($Score -gt 0) {
    $arguments += @("--score", [string]$Score)
}
if ($Rank -gt 0) {
    $arguments += @("--rank", [string]$Rank)
}
foreach ($item in $Major) {
    if (-not [string]::IsNullOrWhiteSpace($item)) {
        $arguments += @("--major", $item.Trim())
    }
}
foreach ($item in $ExcludeMajor) {
    if (-not [string]::IsNullOrWhiteSpace($item)) {
        $arguments += @("--exclude-major", $item.Trim())
    }
}
foreach ($item in $Region) {
    if (-not [string]::IsNullOrWhiteSpace($item)) {
        $arguments += @("--region", $item.Trim())
    }
}
if (-not [string]::IsNullOrWhiteSpace($Goal)) {
    $arguments += @("--goal", $Goal.Trim())
}

Set-Location $appRoot
& python @arguments
exit $LASTEXITCODE
