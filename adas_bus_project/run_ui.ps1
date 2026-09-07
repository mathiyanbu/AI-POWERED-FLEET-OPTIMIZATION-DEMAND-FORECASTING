<#
One-click PowerShell launcher for UrbanShield ADAS.
Right-click -> Run with PowerShell, or double-click if your system allows.
This will use the workspace venv python if present, or fall back to `python` on PATH.
#>
Set-StrictMode -Version Latest
$scriptDir = Split-Path -LiteralPath $MyInvocation.MyCommand.Definition -Parent
$venvPy = Join-Path $scriptDir '.venv\Scripts\python.exe'
Write-Host "Launcher directory: $scriptDir"
if (Test-Path $venvPy) {
    Write-Host "Using virtualenv python: $venvPy"
    & $venvPy -u (Join-Path $scriptDir 'main.py')
} else {
    Write-Host "Virtualenv not found, falling back to python on PATH"
    & python -u (Join-Path $scriptDir 'main.py')
}
