param([ValidateSet('auto', 'cpu', 'cuda')][string]$Device = 'auto')

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw 'Install Node.js 22.13 or newer, then reopen the terminal.'
}
if ($Device -eq 'auto') {
    $Device = 'cpu'
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        & nvidia-smi --query-gpu=name --format=csv,noheader
        if ($LASTEXITCODE -eq 0) { $Device = 'cuda' }
    }
}
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.14 -m venv .venv
    } else {
        & python -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.14, then retry.' }
}
Write-Host "Installing local runtime; selected device: $Device"
& $python scripts/manage.py setup --profile windows --device $Device
exit $LASTEXITCODE
