param(
    [ValidateSet('auto', 'cpu', 'cuda')][string]$Device = 'auto',
    [string]$Models = ''
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $python = Join-Path $PSScriptRoot 'prototypes\meeting-mvp\.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Run: python scripts/manage.py setup --profile windows'
}
if ($Device -eq 'auto') {
    $Device = (& $python -c "import torch; print('cuda' if torch.cuda.is_available() else 'cpu')").Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Install Windows dependencies before starting.' }
}
$arguments = @('scripts/manage.py', 'run', '--profile', 'windows', '--device', $Device)
if ($Models) { $arguments += @('--models', $Models) }
Write-Host "Local original models; selected device: $Device"
& $python @arguments
exit $LASTEXITCODE
